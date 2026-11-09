"""DAO de Unidades de Saúde Bucal - SQL explícito (PyMySQL / DB-API)."""

from app.bd import dao_auditoria
from app.bd.conexao import ErroBanco, consultar, consultar_um, transacao

CAMPOS = ("nome", "cnes", "unidade_e_mista", "tipo", "endereco",
          "bairro", "cidade", "uf", "situacao")


SQL_LISTAR = """
    SELECT u.id, u.nome, u.cnes, u.unidade_e_mista, u.tipo, u.bairro,
           u.cidade, u.uf, u.situacao, u.updated_at,
           (SELECT COUNT(*) FROM servicos s     WHERE s.unidade_id = u.id) AS qtd_servicos,
           (SELECT COUNT(*) FROM equipamentos e WHERE e.unidade_id = u.id) AS qtd_equipamentos
      FROM unidades u
     WHERE (%(situacao)s IS NULL OR u.situacao = %(situacao)s)
       AND (%(busca)s   IS NULL OR u.nome LIKE %(busca)s OR u.cnes LIKE %(busca)s
                                OR u.bairro LIKE %(busca)s)
     ORDER BY u.nome
"""

SQL_BUSCAR_POR_ID = """
    SELECT id, nome, cnes, unidade_e_mista, tipo, endereco, bairro,
           cidade, uf, situacao, created_at, updated_at
      FROM unidades
     WHERE id = %s
"""

SQL_OPCOES = "SELECT id, nome FROM unidades ORDER BY nome"

SQL_CONTAR_DEPENDENTES = """
    SELECT (SELECT COUNT(*) FROM servicos     WHERE unidade_id = %s) AS servicos,
           (SELECT COUNT(*) FROM equipamentos WHERE unidade_id = %s) AS equipamentos
"""


SQL_INSERIR = """
    INSERT INTO unidades
        (nome, cnes, unidade_e_mista, tipo, endereco, bairro, cidade, uf,
         situacao, created_at, updated_at)
    VALUES
        (%s, %s, %s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
"""

SQL_ATUALIZAR = """
    UPDATE unidades
       SET nome = %s, cnes = %s, unidade_e_mista = %s, tipo = %s,
           endereco = %s, bairro = %s, cidade = %s, uf = %s,
           situacao = %s, updated_at = UTC_TIMESTAMP()
     WHERE id = %s
"""

SQL_EXCLUIR = "DELETE FROM unidades WHERE id = %s"


def listar(situacao=None, busca=None):
    _, linhas = consultar(SQL_LISTAR, {
        "situacao": situacao or None,
        "busca": f"%{busca.strip()}%" if busca and busca.strip() else None,
    })
    return linhas


def buscar(unidade_id):
    return consultar_um(SQL_BUSCAR_POR_ID, (unidade_id,))


def opcoes():
    _, linhas = consultar(SQL_OPCOES)
    return [(linha["id"], linha["nome"]) for linha in linhas]


def contar_dependentes(unidade_id):
    return consultar_um(SQL_CONTAR_DEPENDENTES, (unidade_id, unidade_id))


def _valores(dados):
    return tuple(dados.get(campo) for campo in CAMPOS)


def inserir(dados, usuario_id):
    with transacao() as cur:
        dao_auditoria.definir_usuario(cur, usuario_id)
        cur.execute(SQL_INSERIR, _valores(dados))
        novo_id = cur.lastrowid  # ≈ getGeneratedKeys() do JDBC
        dao_auditoria.registrar(
            cur, usuario_id, "BD_INSERIR", "unidades", novo_id,
            f"INSERT de unidade via módulo BD: {dados['nome']}",
            valor_novo=dados,
        )
    return novo_id


def atualizar(unidade_id, dados, usuario_id):
    anterior = buscar(unidade_id)
    if anterior is None:
        raise ErroBanco("Unidade não encontrada.")
    with transacao() as cur:
        dao_auditoria.definir_usuario(cur, usuario_id)
        cur.execute(SQL_ATUALIZAR, _valores(dados) + (unidade_id,))
        mudou = {c: dados[c] for c in CAMPOS if str(anterior.get(c)) != str(dados.get(c))}
        dao_auditoria.registrar(
            cur, usuario_id, "BD_ALTERAR", "unidades", unidade_id,
            f"UPDATE de unidade via módulo BD: {dados['nome']}",
            valor_anterior={c: anterior.get(c) for c in mudou},
            valor_novo=mudou,
        )
        return cur.rowcount


def excluir(unidade_id, usuario_id):
    anterior = buscar(unidade_id)
    if anterior is None:
        raise ErroBanco("Unidade não encontrada.")

    dep = contar_dependentes(unidade_id)
    if dep["servicos"] or dep["equipamentos"]:
        raise ErroBanco(
            f"A unidade possui {dep['servicos']} serviço(s) e "
            f"{dep['equipamentos']} equipamento(s) vinculados. Exclua-os ou "
            f"desvincule-os antes (integridade referencial)."
        )

    with transacao() as cur:
        dao_auditoria.definir_usuario(cur, usuario_id)
        cur.execute(SQL_EXCLUIR, (unidade_id,))
        dao_auditoria.registrar(
            cur, usuario_id, "BD_EXCLUIR", "unidades", unidade_id,
            f"DELETE de unidade via módulo BD: {anterior['nome']}",
            valor_anterior={c: anterior.get(c) for c in CAMPOS},
        )
        return cur.rowcount
