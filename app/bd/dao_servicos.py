"""DAO de Serviços - SQL explícito (PyMySQL / DB-API)."""

from app.bd import dao_auditoria
from app.bd.conexao import ErroBanco, consultar, consultar_um, transacao

CAMPOS = ("nome", "unidade_id", "situacao")

SQL_LISTAR = """
    SELECT s.id, s.nome, s.situacao, s.unidade_id, s.updated_at,
           u.nome AS unidade_nome,
           COUNT(e.id) AS qtd_equipamentos
      FROM servicos s
      LEFT JOIN unidades     u ON u.id = s.unidade_id
      LEFT JOIN equipamentos e ON e.servico_id = s.id
     WHERE (%(situacao)s   IS NULL OR s.situacao   = %(situacao)s)
       AND (%(unidade_id)s IS NULL OR s.unidade_id = %(unidade_id)s)
     GROUP BY s.id, s.nome, s.situacao, s.unidade_id, s.updated_at, u.nome
     ORDER BY s.nome
"""

SQL_BUSCAR_POR_ID = """
    SELECT s.id, s.nome, s.unidade_id, s.situacao, s.created_at, s.updated_at,
           u.nome AS unidade_nome
      FROM servicos s
      LEFT JOIN unidades u ON u.id = s.unidade_id
     WHERE s.id = %s
"""

SQL_OPCOES = """
    SELECT s.id, s.nome, u.nome AS unidade_nome
      FROM servicos s
      LEFT JOIN unidades u ON u.id = s.unidade_id
     ORDER BY s.nome
"""

SQL_INSERIR = """
    INSERT INTO servicos (nome, unidade_id, situacao, created_at, updated_at)
    VALUES (%s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
"""

SQL_ATUALIZAR = """
    UPDATE servicos
       SET nome = %s, unidade_id = %s, situacao = %s, updated_at = UTC_TIMESTAMP()
     WHERE id = %s
"""

SQL_CONTAR_EQUIPAMENTOS = "SELECT COUNT(*) AS total FROM equipamentos WHERE servico_id = %s"

SQL_EXCLUIR = "DELETE FROM servicos WHERE id = %s"


def listar(situacao=None, unidade_id=None):
    _, linhas = consultar(SQL_LISTAR, {
        "situacao": situacao or None,
        "unidade_id": unidade_id or None,
    })
    return linhas


def buscar(servico_id):
    return consultar_um(SQL_BUSCAR_POR_ID, (servico_id,))


def opcoes():
    _, linhas = consultar(SQL_OPCOES)
    return [
        (l["id"], f"{l['nome']} — {l['unidade_nome'] or 'sem unidade'}") for l in linhas
    ]


def _valores(dados):
    return tuple(dados.get(campo) for campo in CAMPOS)


def inserir(dados, usuario_id):
    with transacao() as cur:
        cur.execute(SQL_INSERIR, _valores(dados))
        novo_id = cur.lastrowid
        dao_auditoria.registrar(
            cur, usuario_id, "BD_INSERIR", "servicos", novo_id,
            f"INSERT de serviço via módulo BD: {dados['nome']}", valor_novo=dados,
        )
    return novo_id


def atualizar(servico_id, dados, usuario_id):
    anterior = buscar(servico_id)
    if anterior is None:
        raise ErroBanco("Serviço não encontrado.")
    with transacao() as cur:
        cur.execute(SQL_ATUALIZAR, _valores(dados) + (servico_id,))
        mudou = {c: dados[c] for c in CAMPOS if str(anterior.get(c)) != str(dados.get(c))}
        dao_auditoria.registrar(
            cur, usuario_id, "BD_ALTERAR", "servicos", servico_id,
            f"UPDATE de serviço via módulo BD: {dados['nome']}",
            valor_anterior={c: anterior.get(c) for c in mudou}, valor_novo=mudou,
        )
        return cur.rowcount


def excluir(servico_id, usuario_id):
    anterior = buscar(servico_id)
    if anterior is None:
        raise ErroBanco("Serviço não encontrado.")
    total = consultar_um(SQL_CONTAR_EQUIPAMENTOS, (servico_id,))["total"]
    if total:
        raise ErroBanco(
            f"O serviço possui {total} equipamento(s) vinculado(s). Exclua-os "
            f"ou desvincule-os antes (integridade referencial)."
        )
    with transacao() as cur:
        cur.execute(SQL_EXCLUIR, (servico_id,))
        dao_auditoria.registrar(
            cur, usuario_id, "BD_EXCLUIR", "servicos", servico_id,
            f"DELETE de serviço via módulo BD: {anterior['nome']}",
            valor_anterior={c: anterior.get(c) for c in CAMPOS},
        )
        return cur.rowcount
