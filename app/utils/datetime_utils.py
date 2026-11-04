"""Helper de data/hora usado pelos models."""

from datetime import datetime, timezone


def utcnow():
    """Retorna o horário atual em UTC, sem timezone (naive), para ser armazenado em..."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
