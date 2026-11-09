"""Rotas de autenticação"""

import secrets

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from app.extensions import db
from app.forms import LoginForm
from app.models import OrigemDiretorio, Usuario
from app.services.auditoria_service import registrar_auditoria
from app.services.diretorio_service import DiretorioConfigError, provisionar_usuario_externo
from app.services.oidc_service import OidcError, concluir_autorizacao, iniciar_autorizacao, oidc_habilitado
from app.utils.decorators import usuario_atual
from app.utils.rate_limit import bloqueado, limpar_tentativas, registrar_tentativa_falha
from app.utils.security import verificar_senha

auth_bp = Blueprint("auth", __name__)

MENSAGEM_LOGIN_INVALIDO = "Email ou senha inválidos."
MENSAGEM_MUITAS_TENTATIVAS = (
    "Muitas tentativas de login para esta conta. Aguarde alguns minutos e tente novamente."
)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("autenticado") and session.get("usuario_id"):
        return redirect(url_for("main.index"))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        senha = form.senha.data
        ip = request.remote_addr
        rate_limit_ativo = current_app.config.get("RATE_LIMIT_LOGIN_ENABLED", True)

        if rate_limit_ativo and bloqueado(ip, email):
            flash(MENSAGEM_MUITAS_TENTATIVAS, "danger")
            return render_template("login.html", form=form)

        usuario = Usuario.query.filter_by(email=email).first()

        # Mensagem sempre genérica: usuário inexistente, senha errada
        # ou usuário inativo resultam na mesma resposta ao usuário.
        # Contas provisionadas por LDAP/OIDC nunca autenticam com senha
        # local: a autenticação é sempre no diretório.
        login_valido = (
            usuario is not None
            and usuario.ativo
            and usuario.origem == OrigemDiretorio.LOCAL
            and verificar_senha(senha, usuario.senha_hash)
        )

        if login_valido:
            if rate_limit_ativo:
                limpar_tentativas(ip, email)

            session.clear()
            session["usuario_id"] = usuario.id
            session["autenticado"] = True
            session.permanent = True

            registrar_auditoria(usuario=usuario, acao="LOGIN")
            db.session.commit()

            return redirect(url_for("main.index"))

        if rate_limit_ativo:
            registrar_tentativa_falha(ip, email)
        flash(MENSAGEM_LOGIN_INVALIDO, "danger")

    return render_template("login.html", form=form)


MENSAGEM_SSO_NEGADO = "Não foi possível entrar com o login institucional. Procure um administrador."


def _uri_callback_oidc():
    return url_for("auth.login_oidc_callback", _external=True)


@auth_bp.route("/login/oidc")
def login_oidc():
    if not oidc_habilitado():
        abort(404)
    try:
        url, estado = iniciar_autorizacao(_uri_callback_oidc())
    except Exception:
        current_app.logger.exception("Falha ao iniciar o login OIDC")
        flash(MENSAGEM_SSO_NEGADO, "danger")
        return redirect(url_for("auth.login"))
    session["oidc_estado"] = estado
    return redirect(url)


@auth_bp.route("/login/oidc/callback")
def login_oidc_callback():
    if not oidc_habilitado():
        abort(404)

    estado = session.pop("oidc_estado", None)
    state_recebido = request.args.get("state", "")
    codigo = request.args.get("code", "")
    if (
        not estado
        or not codigo
        or not secrets.compare_digest(state_recebido.encode("utf-8"), estado["state"].encode("utf-8"))
    ):
        flash(MENSAGEM_SSO_NEGADO, "danger")
        return redirect(url_for("auth.login"))

    try:
        externo = concluir_autorizacao(codigo, estado, _uri_callback_oidc())
        usuario = provisionar_usuario_externo(externo, OrigemDiretorio.OIDC)
    except (OidcError, DiretorioConfigError, OSError, ValueError, KeyError):
        current_app.logger.exception("Falha no callback OIDC")
        db.session.rollback()
        flash(MENSAGEM_SSO_NEGADO, "danger")
        return redirect(url_for("auth.login"))

    if usuario is None:
        flash(MENSAGEM_SSO_NEGADO, "danger")
        return redirect(url_for("auth.login"))

    session.clear()
    session["usuario_id"] = usuario.id
    session["autenticado"] = True
    session.permanent = True
    registrar_auditoria(usuario=usuario, acao="LOGIN", descricao="Login via OIDC.")
    db.session.commit()
    return redirect(url_for("main.index"))


@auth_bp.route("/logout")
def logout():
    usuario = usuario_atual()
    if usuario is not None:
        registrar_auditoria(usuario=usuario, acao="LOGOUT")
        db.session.commit()

    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))
