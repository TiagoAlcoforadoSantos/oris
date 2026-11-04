"""Rotas de autenticação"""

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.extensions import db
from app.forms import LoginForm
from app.models import Usuario
from app.services.auditoria_service import registrar_auditoria
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

        login_valido = (
            usuario is not None
            and usuario.ativo
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


@auth_bp.route("/logout")
def logout():
    usuario = usuario_atual()
    if usuario is not None:
        registrar_auditoria(usuario=usuario, acao="LOGOUT")
        db.session.commit()

    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))
