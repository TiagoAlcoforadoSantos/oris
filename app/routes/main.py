"""
Rotas principais da aplicação, após o login.

Nesta fase existe apenas uma página simples para comprovar que a
autenticação funciona — o dashboard real (cards, tabelas etc.) será
implementado na FASE 9.
"""

from flask import Blueprint, render_template, session

from app.extensions import db
from app.models import Usuario
from app.utils.decorators import login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index():
    # login_required já garante que existe uma sessão autenticada
    # válida antes de chegar aqui.
    usuario = db.session.get(Usuario, session["usuario_id"])
    return render_template("index.html", usuario=usuario)
