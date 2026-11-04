"""Model Usuario."""

from app.extensions import db
from app.models.enums import PerfilUsuario
from app.models.mixins import TimestampMixin


class Usuario(db.Model, TimestampMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)

    email = db.Column(db.String(150), nullable=False, unique=True, index=True)

    senha_hash = db.Column(db.String(255), nullable=False)

    perfil = db.Column(
        db.Enum(PerfilUsuario, name="perfil_usuario_enum"),
        nullable=False,
    )

    ativo = db.Column(db.Boolean, nullable=False, default=True)


    alteracoes_criadas = db.relationship(
        "Alteracao",
        back_populates="usuario_criador",
        foreign_keys="Alteracao.usuario_id",
        lazy="dynamic",
    )

    alteracoes_aprovadas = db.relationship(
        "Alteracao",
        back_populates="usuario_aprovador",
        foreign_keys="Alteracao.approved_by",
        lazy="dynamic",
    )

    auditorias = db.relationship(
        "Auditoria",
        back_populates="usuario",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Usuario id={self.id} email={self.email} perfil={self.perfil}>"
