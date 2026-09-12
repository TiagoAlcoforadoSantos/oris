"""
Serviço central do fluxo de aprovação de alterações (Fase 7), agora
integrado à auditoria (Fase 8).

Centraliza aqui, em um único lugar, a lógica de:

- registrar uma alteração pendente (chamado pelas rotas de
  Unidade/Serviço/Equipamento, em vez de escreverem direto no banco)
  — e também audita a SOLICITAÇÃO (ação SOLICITAR_ALTERACAO);
- aplicar uma alteração pendente (criar o registro, editar campos, ou
  só mudar a situação — depende de `operacao`), calculando o
  antes/depois relevante para a auditoria;
- aprovar/rejeitar uma alteração, com todas as regras de segurança
  (perfil autorizado, alteração PENDENTE, solicitante nunca decide
  sobre a própria alteração) — e também audita a DECISÃO
  (APROVAR_ALTERACAO/REJEITAR_ALTERACAO) e, quando aprovada, a
  mudança efetivamente aplicada (CRIAR/EDITAR/ALTERAR_SITUACAO).

IMPORTANTE (Fase 8, distinção exigida): uma solicitação PENDENTE
nunca gera um registro de auditoria como se já tivesse sido aplicada
— a ação CRIAR/EDITAR/ALTERAR_SITUACAO só é auditada quando a
alteração é de fato aprovada e aplicada. Enquanto pendente, a única
auditoria existente é SOLICITAR_ALTERACAO.

Todas as auditorias desta fase são adicionadas à mesma sessão/
transação da operação que descrevem (via
app.services.auditoria_service.registrar_auditoria, que só faz
`add`, nunca `commit`) — se a operação falhar e sofrer rollback, a
auditoria correspondente cai junto.

Assim, `app/routes/unidades.py`, `servicos.py`, `equipamentos.py` e
`alteracoes.py` reaproveitam as mesmas funções em vez de duplicar a
lógica de workflow (e de auditoria) em cada rota.
"""

import json

from app.extensions import db
from app.models import Equipamento, Servico, Unidade
from app.models.enums import StatusAlteracao, TipoOperacaoAlteracao
from app.models.alteracao import Alteracao
from app.services.auditoria_service import registrar_auditoria
from app.utils.datetime_utils import utcnow

# Mapeia o nome da tabela (usado em Alteracao.tabela) para o model
# SQLAlchemy correspondente.
TABELA_MODELOS = {
    "unidades": Unidade,
    "servicos": Servico,
    "equipamentos": Equipamento,
}


def registrar_alteracao(usuario, tabela, registro_id, operacao, dados_novos, descricao):
    """Cria e salva uma Alteracao com status PENDENTE, e audita a
    solicitação (ação SOLICITAR_ALTERACAO) na mesma transação.

    Não aplica nada no registro de negócio — só registra a
    solicitação, para ser aplicada (ou não) no momento da aprovação.

    `dados_novos` é um dict com os valores necessários para aplicar a
    operação depois; é serializado para JSON aqui.
    """
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
    """Aplica de fato a alteração no registro de negócio
    correspondente, dentro da transação corrente (sem commit — quem
    chama decide quando commitar/reverter).

    Retorna (True, registro_afetado, valor_anterior, valor_novo) em
    caso de sucesso, ou (False, mensagem_de_erro, None, None) em caso
    de falha "esperada" (ex.: registro não existe mais). `valor_
    anterior`/`valor_novo` são dicts com só os campos relevantes,
    prontos para a auditoria — nunca incluem senha/senha_hash, pois
    nenhuma operação de Unidade/Serviço/Equipamento lida com esse
    campo. Erros inesperados do banco (ex.: violação de unicidade)
    não são tratados aqui — sobem para quem chamou decidir o rollback
    (ver aprovar_alteracao).
    """
    modelo = TABELA_MODELOS.get(alteracao.tabela)
    if modelo is None:
        return False, f"Tabela '{alteracao.tabela}' desconhecida.", None, None

    dados = json.loads(alteracao.dados_novos) if alteracao.dados_novos else {}

    if alteracao.operacao == TipoOperacaoAlteracao.CRIAR:
        novo_registro = modelo(**dados)
        db.session.add(novo_registro)
        db.session.flush()  # obtém o id gerado e detecta erros de constraint cedo
        alteracao.registro_id = novo_registro.id
        # Para criação não existe "antes" — o "depois" é o registro novo.
        return True, novo_registro, None, dados

    # EDITAR ou ALTERAR_SITUACAO: o registro já precisa existir.
    registro = db.session.get(modelo, alteracao.registro_id)
    if registro is None:
        return False, "O registro afetado por esta alteração não existe mais.", None, None

    valor_anterior = {}
    valor_novo = {}
    for campo, valor in dados.items():
        valor_atual_bruto = getattr(registro, campo)
        # Normaliza Enums (ex.: situacao) para o valor "puro" (ex.:
        # "ATIVA") antes de comparar — comparar a representação padrão
        # de um Enum ("SituacaoUnidade.ATIVA") sempre daria "mudou".
        valor_atual = valor_atual_bruto.value if hasattr(valor_atual_bruto, "value") else valor_atual_bruto

        # Só registra na auditoria os campos que realmente mudaram.
        if str(valor_atual) != str(valor):
            valor_anterior[campo] = valor_atual
            valor_novo[campo] = valor
        setattr(registro, campo, valor)

    db.session.flush()  # detecta erros de constraint (ex.: CNES duplicado) cedo
    return True, registro, valor_anterior or None, valor_novo or None


def aprovar_alteracao(alteracao, aprovador):
    """Aprova uma alteração PENDENTE: aplica a mudança e marca como
    APROVADO, tudo em uma única transação — se a aplicação falhar
    (ex.: conflito de dados), nada é salvo e o status permanece
    PENDENTE. Audita tanto a mudança efetivada (CRIAR/EDITAR/
    ALTERAR_SITUACAO) quanto a decisão (APROVAR_ALTERACAO).

    Retorna (True, mensagem) ou (False, mensagem).
    """
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

    # Audita a mudança de fato efetivada no registro de negócio —
    # atribuída ao solicitante original, que é quem "fez" a alteração
    # em si (o aprovador apenas autorizou; isso é auditado à parte).
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

    # Audita a decisão de aprovação em si, atribuída ao aprovador.
    registrar_auditoria(
        usuario=aprovador,
        acao="APROVAR_ALTERACAO",
        tabela="alteracoes",
        registro_id=alteracao.id,
        descricao=f"Aprovou a alteração #{alteracao.id} ({alteracao.tabela}): {alteracao.descricao}",
    )

    db.session.commit()
    return True, "Alteração aprovada e aplicada com sucesso."


def rejeitar_alteracao(alteracao, aprovador):
    """Rejeita uma alteração PENDENTE: nada é aplicado (a mudança
    nunca chegou a ser escrita no registro de negócio), só o status
    da própria Alteracao muda. Audita a decisão (REJEITAR_ALTERACAO).

    Mesma regra de segregação de funções da aprovação: o solicitante
    não pode decidir sobre a própria alteração.
    """
    if alteracao.status != StatusAlteracao.PENDENTE:
        return False, "Esta alteração já foi processada e não pode ser rejeitada novamente."

    if alteracao.usuario_id == aprovador.id:
        return False, "Você não pode rejeitar a própria alteração."

    alteracao.status = StatusAlteracao.REJEITADO
    alteracao.approved_by = aprovador.id
    alteracao.approved_at = utcnow()

    registrar_auditoria(
        usuario=aprovador,
        acao="REJEITAR_ALTERACAO",
        tabela="alteracoes",
        registro_id=alteracao.id,
        descricao=f"Rejeitou a alteração #{alteracao.id} ({alteracao.tabela}): {alteracao.descricao}",
    )

    db.session.commit()
    return True, "Alteração rejeitada."
