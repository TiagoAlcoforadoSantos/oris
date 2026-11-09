"""DAO da trilha de auditoria - SQL explícito."""

import json

SQL_INSERIR_AUDITORIA = """
    INSERT INTO auditorias
        (usuario_id, acao, tabela, registro_id, descricao,
         valor_anterior, valor_novo, data_hora)
    VALUES
        (%s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())
"""

SQL_DEFINIR_USUARIO = "SET @oris_usuario_id = %s"


def _json(valor):
    if not valor:
        return None
    return json.dumps(valor, ensure_ascii=False, default=str)


def definir_usuario(cur, usuario_id):
    """Informa aos triggers do MySQL quem está operando (variável de sessão
    @oris_usuario_id, lida por trg_equipamentos_au e trg_unidades_au)."""
    cur.execute(SQL_DEFINIR_USUARIO, (usuario_id,))


def registrar(cur, usuario_id, acao, tabela, registro_id, descricao,
              valor_anterior=None, valor_novo=None):
    cur.execute(
        SQL_INSERIR_AUDITORIA,
        (usuario_id, acao, tabela, registro_id, descricao,
         _json(valor_anterior), _json(valor_novo)),
    )
