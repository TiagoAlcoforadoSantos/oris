"""Rotas principais da aplicação, após o login."""

from flask import Blueprint, render_template

from app.utils.decorators import login_required, usuario_atual
from app.utils.rbac import areas_visiveis_para

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index():
    usuario = usuario_atual()
    areas = areas_visiveis_para(usuario)
    return render_template("index.html", usuario=usuario, areas=areas)
