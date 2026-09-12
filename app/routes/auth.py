"""
Rotas de autenticação: login e logout.

Fluxo do login (POST /login):
1. Recebe email e senha do formulário.
2. Procura o usuário pelo email.
3. Verifica se o usuário existe.
4. Verifica se o usuário está ativo.
5. Valida a senha com bcrypt (app.utils.security.verificar_senha).
6. Se tudo correto, cria a sessão autenticada.
7. Redireciona para a área autenticada (rota "/").

Em qualquer passo de falha (usuário não existe, senha errada, ou
usuário inativo) a mensagem exibida é sempre a mesma — genérica —
para não revelar se o email existe ou não, nem o motivo específico
da negação.
"""

from flask import Blueprint, flash, redirect, render_template, session, url_for

from app.forms import LoginForm
from app.models import Usuario
from app.utils.security import verificar_senha

auth_bp = Blueprint("auth", __name__)

MENSAGEM_LOGIN_INVALIDO = "Email ou senha inválidos."


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

        usuario = Usuario.query.filter_by(email=email).first()

        # Mensagem sempre genérica: usuário inexistente, senha errada
        # ou usuário inativo resultam na mesma resposta ao usuário.
        login_valido = (
            usuario is not None
            and usuario.ativo
            and verificar_senha(senha, usuario.senha_hash)
        )

        if login_valido:
            # Sessão guarda apenas o mínimo necessário para identificar
            # o usuário — nunca senha ou senha_hash.
            session.clear()
            session["usuario_id"] = usuario.id
            session["autenticado"] = True
            session.permanent = True
            return redirect(url_for("main.index"))

        flash(MENSAGEM_LOGIN_INVALIDO, "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
def logout():
    # Remove toda a sessão (autenticação e qualquer outro dado
    # eventualmente guardado nela), garantindo que nada de acesso
    # anterior sobreviva ao logout.
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))
