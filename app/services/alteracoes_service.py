"""Serviço central do fluxo de aprovação de alterações (Fase 7), agora integrado à..."""

import json

from app.extensions import db
from app.models import Equipamento, Servico, Unidade
from app.models.enums import StatusAlteracao, TipoOperacaoAlteracao
from app.models.alteracao import Alteracao
from app.services.auditoria_service import registrar_auditoria
from app.utils.datetime_utils import utcnow

TABELA_MODELOS = {
    "unidades": Unidade,
    "servicos": Servico,
    "equipamentos": Equipamento,
}


def registrar_alteracao(usuario, tabela, registro_id, operacao, dados_novos, descricao):
    """Cria e salva uma Alteracao com status PENDENTE, e audita a solicitação (ação..."""
    alteracao = Alteracao(
        usuario_id=usuario.id,
        tabela=tabela,
        registro_id=registro_id,
        operacao=TipoOperacaoAlteracao(operacao),
        dados_novos=json.dumps(dados_novos, ensure_ascii=False),
        descricao=descricao,
        status=StatusAlteracao.PENDENTE,
    )
    db.session.add(alteracao)
    db.session.flush()  # obtém alteracao.id para referenciar na auditoria

    registrar_auditoria(
        usuario=usuario,
        acao="SOLICITAR_ALTERACAO",
        tabela=tabela,
        registro_id=registro_id,
        descricao=descricao,
    )

    db.session.commit()
    return alteracao


def _aplicar_alteracao(alteracao):
    """Aplica de fato a alteração no registro de negócio correspondente, dentro da..."""
    modelo = TABELA_MODELOS.get(alteracao.tabela)
    if modelo is None:
        return False, f"Tabela '{alteracao.tabela}' desconhecida.", None, None

    dados = json.loads(alteracao.dados_novos) if alteracao.dados_novos else {}

    if alteracao.operacao == TipoOperacaoAlteracao.CRIAR:
        novo_registro = modelo(**dados)
        db.session.add(novo_registro)
        db.session.flush()  # obtém o id gerado e detecta erros de constraint cedo
        alteracao.registro_id = novo_registro.id
        return True, novo_registro, None, dados

    registro = db.session.get(modelo, alteracao.registro_id)
    if registro is None:
        return False, "O registro afetado por esta alteração não existe mais.", None, None

    valor_anterior = {}
    valor_novo = {}
    for campo, valor in dados.items():
        valor_atual_bruto = getattr(registro, campo)
        valor_atual = valor_atual_bruto.value if hasattr(valor_atual_bruto, "value") else valor_atual_bruto

        if str(valor_atual) != str(valor):
            valor_anterior[campo] = valor_atual
            valor_novo[campo] = valor
        setattr(registro, campo, valor)

    db.session.flush()  # detecta erros de constraint (ex.: CNES duplicado) cedo
    return True, registro, valor_anterior or None, valor_novo or None


def aprovar_alteracao(alteracao, aprovador):
    """Aprova uma alteração PENDENTE"""
    if alteracao.status != StatusAlteracao.PENDENTE:
        return False, "Esta alteração já foi processada e não pode ser aprovada novamente."

    if alteracao.usuario_id == aprovador.id:
        return False, "Você não pode aprovar a própria alteração."

    try:
        sucesso, resultado, valor_anterior, valor_novo = _aplicar_alteracao(alteracao)
    except Exception:
        db.session.rollback()
        return False, "Não foi possível aplicar a alteração: conflito com os dados atuais."

    if not sucesso:
        db.session.rollback()
        return False, resultado

    alteracao.status = StatusAlteracao.APROVADO
    alteracao.approved_by = aprovador.id
    alteracao.approved_at = utcnow()

    solicitante = alteracao.usuario_criador
    registrar_auditoria(
        usuario=solicitante,
        acao=alteracao.operacao.value,
        tabela=alteracao.tabela,
        registro_id=alteracao.registro_id,
        descricao=alteracao.descricao,
        valor_anterior=valor_anterior,
        valor_novo=valor_novo,
    )

    registrar_auditoria(
        usuario=aprovador,
        acao="APROVAR_ALTERACAO",
        tabela="alteracoes",
        registro_id=alteracao.id,
        descricao=f"Aprovou a alteração #{alteracao.id} ({alteracao.tabela}): {alteracao.descricao}",
    )

    db.session.commit()
    return True, "Alteração aprovada e aplicada com sucesso."


def rejeitar_alteracao(alteracao, aprovador, motivo_rejeicao):
    """Rejeita uma alteração PENDENTE"""
    if alteracao.status != StatusAlteracao.PENDENTE:
        return False, "Esta alteração já foi processada e não pode ser rejeitada novamente."

    if alteracao.usuario_id == aprovador.id:
        return False, "Você não pode rejeitar a própria alteração."

    motivo_rejeicao = (motivo_rejeicao or "").strip()
    if not motivo_rejeicao:
        return False, "Informe a descrição do motivo da rejeição."

    alteracao.status = StatusAlteracao.REJEITADO
    alteracao.approved_by = aprovador.id
    alteracao.approved_at = utcnow()
    alteracao.motivo_rejeicao = motivo_rejeicao

    registrar_auditoria(
        usuario=aprovador,
        acao="REJEITAR_ALTERACAO",
        tabela="alteracoes",
        registro_id=alteracao.id,
        descricao=(
            f"Rejeitou a alteração #{alteracao.id} ({alteracao.tabela}): "
            f"{motivo_rejeicao}"
        ),
    )

    db.session.commit()
    return True, "Alteração rejeitada."
