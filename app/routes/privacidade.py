"""
Página de Privacidade/Transparência (Fase 12).

Pública (não exige login) — é justamente uma página de transparência
sobre o tratamento de dados, então não faz sentido escondê-la atrás
de autenticação. Não contém nenhum dado de usuário específico, só
informações gerais sobre o sistema.
"""

from flask import Blueprint, render_template

privacidade_bp = Blueprint("privacidade", __name__)


@privacidade_bp.route("/privacidade")
def index():
    return render_template("privacidade.html")
