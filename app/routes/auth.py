"""
Rotas de autenticação: login e logout.

Fluxo do login (POST /login):
1. Verifica rate limiting (Fase 12): se este (IP, email) já falhou
   demais vezes na janela atual, bloqueia sem sequer checar a senha.
2. Recebe email e senha do formulário.
3. Procura o usuário pelo email.
4. Verifica se o usuário está ativo.
5. Valida a senha com bcrypt (app.utils.security.verificar_senha).
6. Se tudo correto, cria a sessão autenticada e audita a ação LOGIN
   (Fase 8).
7. Redireciona para a área autenticada (rota "/").

Em qualquer passo de falha (usuário não existe, senha errada, ou
usuário inativo) a mensagem exibida é sempre a mesma — genérica —
para não revelar se o email existe ou não, nem o motivo específico
da negação. Login malsucedido NÃO é auditado nesta fase (a Fase 8
pede auditoria de LOGIN/LOGOUT bem-sucedidos; tentativas falhas não
identificam de forma confiável um usuário para atribuir o evento).

O logout audita a ação LOGOUT antes de limpar a sessão (precisa do
usuário ainda identificado na sessão para saber quem registrar).

PROTEÇÃO CONTRA SESSION FIXATION: `session.clear()` é chamado logo
antes de estabelecer a nova sessão autenticada — qualquer dado que
já existisse na sessão do navegador (inclusive um valor que um
atacante tivesse tentado "plantar" antes do login) é descartado nesse
momento. Como o Flask usa sessões assinadas do lado do cliente (sem
um ID de sessão do lado do servidor para "fixar"), essa é a mitigação
adequada ao mecanismo em uso.
"""

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
    # Se já existe uma sessão autenticada, não faz sentido mostrar o
    # login de novo — manda direto para a área interna.
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
        login_valido = (
            usuario is not None
            and usuario.ativo
            and verificar_senha(senha, usuario.senha_hash)
        )

        if login_valido:
            if rate_limit_ativo:
                limpar_tentativas(ip, email)

            # Descarta qualquer dado de sessão pré-existente (proteção
            # contra session fixation) e guarda apenas o mínimo
            # necessário para identificar o usuário — nunca senha ou
            # senha_hash.
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
    # Precisa capturar o usuário ANTES de limpar a sessão, para saber
    # quem registrar na auditoria.
    usuario = usuario_atual()
    if usuario is not None:
        registrar_auditoria(usuario=usuario, acao="LOGOUT")
        db.session.commit()

    # Remove toda a sessão (autenticação e qualquer outro dado
    # eventualmente guardado nela), garantindo que nada de acesso
    # anterior sobreviva ao logout.
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))
