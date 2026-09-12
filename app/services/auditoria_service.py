"""
Serviço central de auditoria (Fase 8).

Um único ponto (`registrar_auditoria`) para criar registros de
`Auditoria` — evita espalhar a lógica de montagem/serialização pelo
projeto. Rotas e outros serviços (login/logout, CRUDs, fluxo de
aprovação) chamam esta função em vez de instanciar `Auditoria`
diretamente.

IMPORTANTE sobre transação: esta função só faz `db.session.add(...)`
— NÃO comita. Quem chama decide quando commitar, para que o registro
de auditoria sempre viaje na mesma transação da operação que ele
descreve (login, aprovação, etc.) — se a operação falhar e sofrer
rollback, a auditoria correspondente também é desfeita, evitando
"auditoria de algo que não aconteceu" ou "algo que aconteceu sem
auditoria" (ver Fase 8, item 11).
"""

import json

from app.extensions import db
from app.models import Auditoria


def registrar_auditoria(
    usuario,
    acao,
    tabela=None,
    registro_id=None,
    descricao=None,
    valor_anterior=None,
    valor_novo=None,
):
    """Cria (sem commitar) um registro de Auditoria.

    `valor_anterior`/`valor_novo`, quando informados, devem ser
    dicts com APENAS os campos relevantes para a ação (nunca senha
    ou senha_hash) — são serializados para JSON aqui.
    """
    auditoria = Auditoria(
        usuario_id=usuario.id,
        acao=acao,
        tabela=tabela,
        registro_id=registro_id,
        descricao=descricao,
        valor_anterior=json.dumps(valor_anterior, ensure_ascii=False) if valor_anterior else None,
        valor_novo=json.dumps(valor_novo, ensure_ascii=False) if valor_novo else None,
    )
    db.session.add(auditoria)
    return auditoria
