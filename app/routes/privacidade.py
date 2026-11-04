"""Página de Privacidade/Transparência (Fase 12)."""

from flask import Blueprint, render_template

privacidade_bp = Blueprint("privacidade", __name__)


@privacidade_bp.route("/privacidade")
def index():
    return render_template("privacidade.html")
