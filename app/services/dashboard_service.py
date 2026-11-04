"""Serviço central de dados do dashboard (Fase 9)."""

from app.models import (
    Alteracao,
    Auditoria,
    Equipamento,
    Servico,
    SituacaoAtivoInativo,
    SituacaoUnidade,
    StatusAlteracao,
    Unidade,
)

QUANTIDADE_ALTERACOES_PENDENTES_EXIBIDAS = 20
QUANTIDADE_ATIVIDADES_RECENTES_EXIBIDAS = 15


def obter_indicadores():
    """Contagens gerais de Unidades, Serviços, Equipamentos e Alterações, calculadas..."""
    return {
        "unidades_total": Unidade.query.count(),
        "unidades_ativas": Unidade.query.filter_by(situacao=SituacaoUnidade.ATIVA).count(),
        "unidades_inativas": Unidade.query.filter_by(situacao=SituacaoUnidade.INATIVA).count(),
        "unidades_manutencao": Unidade.query.filter_by(situacao=SituacaoUnidade.MANUTENCAO).count(),
        "servicos_total": Servico.query.count(),
        "servicos_ativos": Servico.query.filter_by(situacao=SituacaoAtivoInativo.ATIVO).count(),
        "servicos_inativos": Servico.query.filter_by(situacao=SituacaoAtivoInativo.INATIVO).count(),
        "equipamentos_total": Equipamento.query.count(),
        "equipamentos_ativos": Equipamento.query.filter_by(situacao=SituacaoAtivoInativo.ATIVO).count(),
        "equipamentos_inativos": Equipamento.query.filter_by(situacao=SituacaoAtivoInativo.INATIVO).count(),
        "alteracoes_pendentes": Alteracao.query.filter_by(status=StatusAlteracao.PENDENTE).count(),
        "alteracoes_aprovadas": Alteracao.query.filter_by(status=StatusAlteracao.APROVADO).count(),
        "alteracoes_rejeitadas": Alteracao.query.filter_by(status=StatusAlteracao.REJEITADO).count(),
    }


def obter_resumo_unidades(situacao_filtro=None):
    """Lista de unidades (nome, CNES, cidade, UF, situação) para a     seção "Resumo da..."""
    query = Unidade.query
    if situacao_filtro in {item.value for item in SituacaoUnidade}:
        query = query.filter_by(situacao=SituacaoUnidade(situacao_filtro))
    return query.order_by(Unidade.nome).all()


def obter_alteracoes_pendentes():
    """Alterações com status PENDENTE, mais recentes primeiro, para a     seção "Aprovações"..."""
    return (
        Alteracao.query.filter_by(status=StatusAlteracao.PENDENTE)
        .order_by(Alteracao.created_at.desc())
        .limit(QUANTIDADE_ALTERACOES_PENDENTES_EXIBIDAS)
        .all()
    )


def obter_atividade_recente(usuario_id=None):
    """Registros de auditoria mais recentes, para a seção "Atividade     recente" —..."""
    query = Auditoria.query
    if usuario_id is not None:
        query = query.filter_by(usuario_id=usuario_id)
    return query.order_by(Auditoria.data_hora.desc()).limit(QUANTIDADE_ATIVIDADES_RECENTES_EXIBIDAS).all()
