"""
Serviço central de dados do dashboard (Fase 9).

Reúne, em um único lugar, as consultas usadas pelo dashboard —
todas feitas com SQLAlchemy simples, direto no banco (nada de dados
fictícios). Não implementa nenhuma regra de negócio nova: só agrega
contagens e listagens que já existiam desde as Fases 2, 5, 6, 7 e 8.
"""

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
    """Contagens gerais de Unidades, Serviços, Equipamentos e
    Alterações, calculadas diretamente do banco."""
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
    """Lista de unidades (nome, CNES, cidade, UF, situação) para a
    seção "Resumo da rede", com filtro opcional por situação."""
    query = Unidade.query
    if situacao_filtro in {item.value for item in SituacaoUnidade}:
        query = query.filter_by(situacao=SituacaoUnidade(situacao_filtro))
    return query.order_by(Unidade.nome).all()


def obter_alteracoes_pendentes():
    """Alterações com status PENDENTE, mais recentes primeiro, para a
    seção "Aprovações" do dashboard — reaproveita o model existente,
    sem criar nenhum mecanismo novo de aprovação."""
    return (
        Alteracao.query.filter_by(status=StatusAlteracao.PENDENTE)
        .order_by(Alteracao.created_at.desc())
        .limit(QUANTIDADE_ALTERACOES_PENDENTES_EXIBIDAS)
        .all()
    )


def obter_atividade_recente(usuario_id=None):
    """Registros de auditoria mais recentes, para a seção "Atividade
    recente" — reaproveita a estrutura da Fase 8. Os templates que
    exibem esses registros nunca mostram senha/hash, porque o model
    Auditoria (Fase 8) nunca armazena esses campos em primeiro lugar.

    Se `usuario_id` for informado, retorna só a atividade DAQUELE
    usuário — usado para RESPONSAVEL_SAUDE_BUCAL e GESTOR no
    dashboard, que (desde a Fase 8) não têm acesso à auditoria
    administrativa completa; ADMINISTRADOR e GESTAO_INFORMACAO
    continuam vendo a atividade de todo o sistema, como em
    `/auditoria`.
    """
    query = Auditoria.query
    if usuario_id is not None:
        query = query.filter_by(usuario_id=usuario_id)
    return query.order_by(Auditoria.data_hora.desc()).limit(QUANTIDADE_ATIVIDADES_RECENTES_EXIBIDAS).all()
