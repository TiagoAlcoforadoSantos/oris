"""
Serviço central do fluxo de aprovação de alterações (Fase 7).

Centraliza aqui, em um único lugar, a lógica de:

- registrar uma alteração pendente (chamado pelas rotas de
  Unidade/Serviço/Equipamento, em vez de escreverem direto no banco);
- aplicar uma alteração pendente (criar o registro, editar campos, ou
  só mudar a situação — depende de `operacao`);
- aprovar/rejeitar uma alteração, com todas as regras de segurança:
  perfil autorizado, alteração PENDENTE, e o solicitante nunca pode
  decidir sobre a própria alteração.

Assim, `app/routes/unidades.py`, `servicos.py`, `equipamentos.py` e
`alteracoes.py` reaproveitam as mesmas funções em vez de duplicar a
lógica de workflow em cada rota.
"""

import json

from app.extensions import db
from app.models import Equipamento, Servico, Unidade
from app.models.enums import StatusAlteracao, TipoOperacaoAlteracao
from app.models.alteracao import Alteracao
from app.utils.datetime_utils import utcnow

# Mapeia o nome da tabela (usado em Alteracao.tabela) para o model
# SQLAlchemy correspondente.
TABELA_MODELOS = {
    "unidades": Unidade,
    "servicos": Servico,
    "equipamentos": Equipamento,
}


def registrar_alteracao(usuario, tabela, registro_id, operacao, dados_novos, descricao):
    """Cria e salva uma Alteracao com status PENDENTE.

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
    db.session.commit()
    return alteracao


def _aplicar_alteracao(alteracao):
    """Aplica de fato a alteração no registro de negócio
    correspondente, dentro da transação corrente (sem commit — quem
    chama decide quando commitar/reverter).

    Retorna (True, registro_afetado) em caso de sucesso, ou
    (False, mensagem_de_erro) em caso de falha "esperada" (ex.:
    registro não existe mais). Erros inesperados do banco (ex.:
    violação de unicidade) não são tratados aqui — sobem para quem
    chamou decidir o rollback (ver aprovar_alteracao).
    """
    modelo = TABELA_MODELOS.get(alteracao.tabela)
    if modelo is None:
        return False, f"Tabela '{alteracao.tabela}' desconhecida."

    dados = json.loads(alteracao.dados_novos) if alteracao.dados_novos else {}

    if alteracao.operacao == TipoOperacaoAlteracao.CRIAR:
        novo_registro = modelo(**dados)
        db.session.add(novo_registro)
        db.session.flush()  # obtém o id gerado e detecta erros de constraint cedo
        alteracao.registro_id = novo_registro.id
        return True, novo_registro

    # EDITAR ou ALTERAR_SITUACAO: o registro já precisa existir.
    registro = db.session.get(modelo, alteracao.registro_id)
    if registro is None:
        return False, "O registro afetado por esta alteração não existe mais."

    for campo, valor in dados.items():
        setattr(registro, campo, valor)

    db.session.flush()  # detecta erros de constraint (ex.: CNES duplicado) cedo
    return True, registro


def aprovar_alteracao(alteracao, aprovador):
    """Aprova uma alteração PENDENTE: aplica a mudança e marca como
    APROVADO, tudo em uma única transação — se a aplicação falhar
    (ex.: conflito de dados), nada é salvo e o status permanece
    PENDENTE.

    Retorna (True, mensagem) ou (False, mensagem).
    """
    if alteracao.status != StatusAlteracao.PENDENTE:
        return False, "Esta alteração já foi processada e não pode ser aprovada novamente."

    if alteracao.usuario_id == aprovador.id:
        return False, "Você não pode aprovar a própria alteração."

    try:
        sucesso, resultado = _aplicar_alteracao(alteracao)
    except Exception:
        db.session.rollback()
        return False, "Não foi possível aplicar a alteração: conflito com os dados atuais."

    if not sucesso:
        db.session.rollback()
        return False, resultado

    alteracao.status = StatusAlteracao.APROVADO
    alteracao.approved_by = aprovador.id
    alteracao.approved_at = utcnow()
    db.session.commit()
    return True, "Alteração aprovada e aplicada com sucesso."


def rejeitar_alteracao(alteracao, aprovador):
    """Rejeita uma alteração PENDENTE: nada é aplicado (a mudança
    nunca chegou a ser escrita no registro de negócio), só o status
    da própria Alteracao muda.

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
    db.session.commit()
    return True, "Alteração rejeitada."
