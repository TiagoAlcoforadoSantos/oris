"""
Rotas de teste do RBAC (Fase 4).

Estas rotas NÃO são funcionalidades reais do ORIS — servem apenas
para comprovar que a autorização por perfil (`roles_required`) está
funcionando corretamente. As telas reais de cada área (gestão de
usuários, validação de alterações, cadastro de unidades etc.) serão
implementadas nas fases seguintes.

Os perfis permitidos em cada rota vêm de app.utils.rbac
(AREAS_DE_TESTE_RBAC), a mesma matriz usada para decidir quais links
aparecem na página inicial — evitando duplicar a lista de perfis em
dois lugares.
"""

from flask import Blueprint, render_template

from app.utils.decorators import roles_required, usuario_atual
from app.utils.rbac import AREAS_DE_TESTE_RBAC

areas_bp = Blueprint("areas", __name__)


def _perfis(endpoint):
    return AREAS_DE_TESTE_RBAC[endpoint][1]


def _titulo(endpoint):
    return AREAS_DE_TESTE_RBAC[endpoint][0]


@areas_bp.route("/admin")
@roles_required(*_perfis("areas.admin"))
def admin():
    return render_template(
        "area_perfil.html",
        titulo=_titulo("areas.admin"),
        usuario=usuario_atual(),
    )


@areas_bp.route("/gestao")
@roles_required(*_perfis("areas.gestao"))
def gestao():
    return render_template(
        "area_perfil.html",
        titulo=_titulo("areas.gestao"),
        usuario=usuario_atual(),
    )


@areas_bp.route("/responsavel")
@roles_required(*_perfis("areas.responsavel"))
def responsavel():
    return render_template(
        "area_perfil.html",
        titulo=_titulo("areas.responsavel"),
        usuario=usuario_atual(),
    )


@areas_bp.route("/gestor")
@roles_required(*_perfis("areas.gestor"))
def gestor():
    return render_template(
        "area_perfil.html",
        titulo=_titulo("areas.gestor"),
        usuario=usuario_atual(),
    )
