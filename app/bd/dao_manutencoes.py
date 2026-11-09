"""DAO de Manutenções (Etapa 06) - SQL explícito (PyMySQL / DB-API).

As regras de integridade (custo >= 0, conclusão >= abertura) e o efeito
sobre a situação do equipamento ficam nos TRIGGERS do MySQL
(database/etapa05_objetos.sql); a violação chega aqui como erro do
driver, traduzido para ErroBanco.
"""

from app.bd import dao_auditoria
from app.bd.conexao import ErroBanco, consultar, consultar_um, transacao

CAMPOS = ("equipamento_id", "tipo", "descricao", "data_abertura", "data_conclusao", "custo", "situacao")

SQL_LISTAR = """
    SELECT m.id, m.tipo, m.descricao, m.situacao, m.data_abertura, m.data_conclusao, m.custo,
           m.updated_at, e.nome AS equipamento_nome, u.nome AS unidade_nome
      FROM manutencoes m
      JOIN equipamentos e ON e.id = m.equipamento_id
      LEFT JOIN unidades u ON u.id = e.unidade_id
     WHERE (%(situacao)s   IS NULL OR m.situacao = %(situacao)s)
       AND (%(unidade_id)s IS NULL OR e.unidade_id = %(unidade_id)s)
     ORDER BY m.data_abertura DESC, m.id DESC
"""

SQL_BUSCAR_POR_ID = """
    SELECT m.id, m.equipamento_id, m.tipo, m.descricao, m.data_abertura, m.data_conclusao,
           m.custo, m.situacao, m.created_at, m.updated_at, e.nome AS equipamento_nome
      FROM manutencoes m
      JOIN equipamentos e ON e.id = m.equipamento_id
     WHERE m.id = %s
"""

SQL_INSERIR = """
    INSERT INTO manutencoes
        (equipamento_id, tipo, descricao, data_abertura, data_conclusao, custo, situacao,
         created_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
"""

SQL_ATUALIZAR = """
    UPDATE manutencoes
       SET equipamento_id = %s, tipo = %s, descricao = %s, data_abertura = %s,
           data_conclusao = %s, custo = %s, situacao = %s, updated_at = UTC_TIMESTAMP()
     WHERE id = %s
"""

SQL_EXCLUIR = "DELETE FROM manutencoes WHERE id = %s"

SQL_OPCOES_ABERTAS = """
    SELECT m.id, m.tipo, m.descricao, e.nome AS equipamento_nome
      FROM manutencoes m
      JOIN equipamentos e ON e.id = m.equipamento_id
     WHERE m.situacao = 'ABERTA'
     ORDER BY m.id DESC
"""


def listar(situacao=None, unidade_id=None):
    _, linhas = consultar(SQL_LISTAR, {"situacao": situacao or None, "unidade_id": unidade_id or None})
    return linhas


def buscar(manutencao_id):
    return consultar_um(SQL_BUSCAR_POR_ID, (manutencao_id,))


def opcoes_abertas():
    _, linhas = consultar(SQL_OPCOES_ABERTAS)
    return [(l["id"], f"#{l['id']} · {l['equipamento_nome']} · {l['tipo'].capitalize()} · {l['descricao'][:40]}")
            for l in linhas]


def _valores(dados):
    return tuple(dados.get(campo) for campo in CAMPOS)


def _executar(cur, sql, parametros):
    """Os triggers sinalizam violações de regra com SQLSTATE 45000."""
    try:
        cur.execute(sql, parametros)
    except Exception as erro:
        args = getattr(erro, "args", ())
        if len(args) >= 2 and getattr(erro, "args", [None])[0] == 1644:
            raise ErroBanco(str(args[1])) from erro
        raise


def inserir(dados, usuario_id):
    with transacao() as cur:
        dao_auditoria.definir_usuario(cur, usuario_id)
        _executar(cur, SQL_INSERIR, _valores(dados))
        novo_id = cur.lastrowid
        dao_auditoria.registrar(
            cur, usuario_id, "BD_INSERIR", "manutencoes", novo_id,
            f"INSERT de manutenção via módulo BD: {dados['descricao']}", valor_novo=dados,
        )
    return novo_id


def atualizar(manutencao_id, dados, usuario_id):
    anterior = buscar(manutencao_id)
    if anterior is None:
        raise ErroBanco("Manutenção não encontrada.")
    with transacao() as cur:
        dao_auditoria.definir_usuario(cur, usuario_id)
        _executar(cur, SQL_ATUALIZAR, _valores(dados) + (manutencao_id,))
        mudou = {c: dados[c] for c in CAMPOS if str(anterior.get(c)) != str(dados.get(c))}
        dao_auditoria.registrar(
            cur, usuario_id, "BD_ALTERAR", "manutencoes", manutencao_id,
            f"UPDATE de manutenção via módulo BD: {dados['descricao']}",
            valor_anterior={c: anterior.get(c) for c in mudou}, valor_novo=mudou,
        )
        return cur.rowcount


def excluir(manutencao_id, usuario_id):
    anterior = buscar(manutencao_id)
    if anterior is None:
        raise ErroBanco("Manutenção não encontrada.")
    with transacao() as cur:
        dao_auditoria.definir_usuario(cur, usuario_id)
        cur.execute(SQL_EXCLUIR, (manutencao_id,))
        dao_auditoria.registrar(
            cur, usuario_id, "BD_EXCLUIR", "manutencoes", manutencao_id,
            f"DELETE de manutenção via módulo BD: {anterior['descricao']}",
            valor_anterior={c: anterior.get(c) for c in CAMPOS},
        )
        return cur.rowcount
