"""Dashboard do ORIS (Fase 9)."""

from flask import Blueprint, render_template, request

from app.models import PerfilUsuario
from app.services.dashboard_service import (
    obter_alteracoes_pendentes,
    obter_atividade_recente,
    obter_indicadores,
    obter_resumo_unidades,
)
from app.utils.decorators import login_required, usuario_atual

dashboard_bp = Blueprint("dashboard", __name__)

PERFIS_COM_AUDITORIA_COMPLETA = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
)

PERFIS_QUE_APROVAM = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    usuario = usuario_atual()

    situacao_filtro = request.args.get("situacao")

    tem_auditoria_completa = usuario.perfil.value in PERFIS_COM_AUDITORIA_COMPLETA
    atividade_recente = obter_atividade_recente(
        usuario_id=None if tem_auditoria_completa else usuario.id
    )

    return render_template(
        "dashboard.html",
        indicadores=obter_indicadores(),
        unidades=obter_resumo_unidades(situacao_filtro),
        situacao_filtro=situacao_filtro,
        alteracoes_pendentes=obter_alteracoes_pendentes(),
        pode_aprovar=usuario.perfil.value in PERFIS_QUE_APROVAM,
        atividade_recente=atividade_recente,
        atividade_e_pessoal=not tem_auditoria_completa,
    )
