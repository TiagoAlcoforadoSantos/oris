"""
Mixin de timestamps reutilizado pelos models.

Mantém created_at/updated_at padronizados em uma única definição,
evitando repetição de código em cada model.
"""

from app.extensions import db
from app.utils.datetime_utils import utcnow


class TimestampMixin:
    """Adiciona created_at e updated_at às tabelas que o utilizarem."""

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
