"""
Model Usuario.

Representa os usuários do sistema ORIS. Nesta fase, o campo
`senha_hash` já existe com o tamanho adequado para armazenar um hash
bcrypt, mas a geração/verificação do hash será implementada somente
na FASE 3 (login). Aqui nenhuma senha em texto puro é manipulada.

O campo `perfil` já define os 4 perfis previstos, mas as REGRAS de
permissão de cada perfil (RBAC) serão implementadas na FASE 4.
"""

from app.extensions import db
from app.models.enums import PerfilUsuario
from app.models.mixins import TimestampMixin


class Usuario(db.Model, TimestampMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)

    # Email é o identificador único do usuário para login (Fase 3).
    email = db.Column(db.String(150), nullable=False, unique=True, index=True)

    # Armazena o HASH da senha (bcrypt, gerado na Fase 3).
    # Tamanho 255 é suficiente para hashes bcrypt (60 caracteres) com
    # margem para eventuais formatos maiores.
    senha_hash = db.Column(db.String(255), nullable=False)

    perfil = db.Column(
        db.Enum(PerfilUsuario, name="perfil_usuario_enum"),
        nullable=False,
    )

    # Permite desativar um usuário sem excluí-lo (mantém rastreabilidade
    # / auditoria, alinhado aos requisitos futuros de LGPD).
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    # --- Relacionamentos ---

    # Alterações criadas por este usuário (Fase 7 usa isso no fluxo).
    alteracoes_criadas = db.relationship(
        "Alteracao",
        back_populates="usuario_criador",
        foreign_keys="Alteracao.usuario_id",
        lazy="dynamic",
    )

    # Alterações aprovadas/rejeitadas por este usuário.
    alteracoes_aprovadas = db.relationship(
        "Alteracao",
        back_populates="usuario_aprovador",
        foreign_keys="Alteracao.approved_by",
        lazy="dynamic",
    )

    # Registros de auditoria gerados pelas ações deste usuário.
    auditorias = db.relationship(
        "Auditoria",
        back_populates="usuario",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Usuario id={self.id} email={self.email} perfil={self.perfil}>"
