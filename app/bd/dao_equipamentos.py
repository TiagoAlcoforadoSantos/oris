"""DAO de Equipamentos - SQL explícito (PyMySQL / DB-API)."""

from app.bd import dao_auditoria
from app.bd.conexao import ErroBanco, consultar, consultar_um, transacao

CAMPOS = ("nome", "tipo", "unidade_id", "servico_id", "situacao")

SQL_LISTAR = """
    SELECT e.id, e.nome, e.tipo, e.situacao, e.updated_at,
           u.nome AS unidade_nome, s.nome AS servico_nome
      FROM equipamentos e
      LEFT JOIN unidades u ON u.id = e.unidade_id
      LEFT JOIN servicos s ON s.id = e.servico_id
     WHERE (%(situacao)s   IS NULL OR e.situacao   = %(situacao)s)
       AND (%(unidade_id)s IS NULL OR e.unidade_id = %(unidade_id)s)
     ORDER BY e.nome
"""

SQL_BUSCAR_POR_ID = """
    SELECT e.id, e.nome, e.tipo, e.unidade_id, e.servico_id, e.situacao,
           e.created_at, e.updated_at,
           u.nome AS unidade_nome, s.nome AS servico_nome
      FROM equipamentos e
      LEFT JOIN unidades u ON u.id = e.unidade_id
      LEFT JOIN servicos s ON s.id = e.servico_id
     WHERE e.id = %s
"""

SQL_UNIDADE_DO_SERVICO = "SELECT unidade_id FROM servicos WHERE id = %s"

SQL_INSERIR = """
    INSERT INTO equipamentos
        (nome, tipo, unidade_id, servico_id, situacao, created_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
"""

SQL_ATUALIZAR = """
    UPDATE equipamentos
       SET nome = %s, tipo = %s, unidade_id = %s, servico_id = %s,
           situacao = %s, updated_at = UTC_TIMESTAMP()
     WHERE id = %s
"""

SQL_EXCLUIR = "DELETE FROM equipamentos WHERE id = %s"


def listar(situacao=None, unidade_id=None):
    _, linhas = consultar(SQL_LISTAR, {
        "situacao": situacao or None,
        "unidade_id": unidade_id or None,
    })
    return linhas


def buscar(equipamento_id):
    return consultar_um(SQL_BUSCAR_POR_ID, (equipamento_id,))


def _validar_vinculo(dados):
    """Se houver serviço, ele precisa ser da mesma unidade escolhida."""
    if not dados.get("servico_id"):
        return
    linha = consultar_um(SQL_UNIDADE_DO_SERVICO, (dados["servico_id"],))
    if linha is None:
        raise ErroBanco("O serviço selecionado não existe.")
    if linha["unidade_id"] != dados.get("unidade_id"):
        raise ErroBanco("O serviço selecionado pertence a outra unidade.")


def _valores(dados):
    return tuple(dados.get(campo) for campo in CAMPOS)


def inserir(dados, usuario_id):
    _validar_vinculo(dados)
    with transacao() as cur:
        cur.execute(SQL_INSERIR, _valores(dados))
        novo_id = cur.lastrowid
        dao_auditoria.registrar(
            cur, usuario_id, "BD_INSERIR", "equipamentos", novo_id,
            f"INSERT de equipamento via módulo BD: {dados['nome']}", valor_novo=dados,
        )
    return novo_id


def atualizar(equipamento_id, dados, usuario_id):
    anterior = buscar(equipamento_id)
    if anterior is None:
        raise ErroBanco("Equipamento não encontrado.")
    _validar_vinculo(dados)
    with transacao() as cur:
        cur.execute(SQL_ATUALIZAR, _valores(dados) + (equipamento_id,))
        mudou = {c: dados[c] for c in CAMPOS if str(anterior.get(c)) != str(dados.get(c))}
        dao_auditoria.registrar(
            cur, usuario_id, "BD_ALTERAR", "equipamentos", equipamento_id,
            f"UPDATE de equipamento via módulo BD: {dados['nome']}",
            valor_anterior={c: anterior.get(c) for c in mudou}, valor_novo=mudou,
        )
        return cur.rowcount


def excluir(equipamento_id, usuario_id):
    anterior = buscar(equipamento_id)
    if anterior is None:
        raise ErroBanco("Equipamento não encontrado.")
    with transacao() as cur:
        cur.execute(SQL_EXCLUIR, (equipamento_id,))
        dao_auditoria.registrar(
            cur, usuario_id, "BD_EXCLUIR", "equipamentos", equipamento_id,
            f"DELETE de equipamento via módulo BD: {anterior['nome']}",
            valor_anterior={c: anterior.get(c) for c in CAMPOS},
        )
        return cur.rowcount
