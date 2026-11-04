"""Serviço central de auditoria (Fase 8)."""

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
    """Cria (sem commitar) um registro de Auditoria."""
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
