"""
Helper de data/hora usado pelos models.

`datetime.utcnow()` está depreciado a partir do Python 3.12. Esta
função entrega o mesmo resultado prático (um datetime "naive" em
UTC, compatível com a coluna DATETIME do MySQL) sem gerar o aviso
de depreciação.
"""

from datetime import datetime, timezone


def utcnow():
    """Retorna o horário atual em UTC, sem timezone (naive),
    para ser armazenado em colunas DATETIME do MySQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
