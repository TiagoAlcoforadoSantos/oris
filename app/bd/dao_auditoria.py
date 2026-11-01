"""
DAO da trilha de auditoria — SQL explícito.

Recebe o MESMO cursor da operação de negócio, para que o INSERT em
`auditorias` faça parte da mesma transação (commit/rollback juntos).
Horários em UTC, igual ao restante do ORIS (app/utils/datetime_utils).
"""

import json

SQL_INSERIR_AUDITORIA = """
    INSERT INTO auditorias
        (usuario_id, acao, tabela, registro_id, descricao,
         valor_anterior, valor_novo, data_hora)
    VALUES
        (%s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())
"""


def _json(valor):
    if not valor:
        return None
    return json.dumps(valor, ensure_ascii=False, default=str)


def registrar(cur, usuario_id, acao, tabela, registro_id, descricao,
              valor_anterior=None, valor_novo=None):
    cur.execute(
        SQL_INSERIR_AUDITORIA,
        (usuario_id, acao, tabela, registro_id, descricao,
         _json(valor_anterior), _json(valor_novo)),
    )
