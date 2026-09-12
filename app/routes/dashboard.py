"""
Dashboard do ORIS (Fase 9).

Visão geral da Rede de Saúde Bucal, com dados reais vindos do banco
— nenhum dado fictício. Acessível pelos 4 perfis (por isso usa
`login_required`, equivalente a `roles_required` com todos os
perfis).

A seção "Atividade recente" respeita a restrição de auditoria já
estabelecida na Fase 8: ADMINISTRADOR e GESTAO_INFORMACAO veem a
atividade de todo o sistema (mesmos dados de `/auditoria`);
RESPONSAVEL_SAUDE_BUCAL e GESTOR veem só a própria atividade, já que
esses dois perfis não têm acesso à auditoria administrativa completa.

A seção "Aprovações" reaproveita a listagem de Alterações pendentes
já existente (Fase 7) — nenhum mecanismo novo de aprovação é criado
aqui. O link para agir sobre uma alteração (aprovar/rejeitar) só
aparece para quem já tinha essa permissão desde a Fase 7.
"""

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
