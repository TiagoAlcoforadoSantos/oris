"""
Model Grupo e tabela de associação usuário<->grupo.

Grupos são populados a partir de diretórios externos (LDAP/OIDC) pelo
módulo app/services/diretorio_service.py. O ORIS não dá permissão a
um grupo diretamente: a permissão continua sendo o `perfil` do
usuário (RBAC); o mapeamento grupo -> perfil fica na configuração
`DIRETORIO_MAPA_GRUPO_PERFIL` e é aplicado na sincronização.
"""

from app.extensions import db
from app.models.enums import OrigemDiretorio
from app.models.mixins import TimestampMixin

usuario_grupos = db.Table(
    "usuario_grupos",
    db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"), primary_key=True),
    db.Column("grupo_id", db.Integer, db.ForeignKey("grupos.id"), primary_key=True),
)


class Grupo(db.Model, TimestampMixin):
    __tablename__ = "grupos"
    __table_args__ = (db.UniqueConstraint("nome", "origem", name="uk_grupos_nome_origem"),)

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, index=True)
    origem = db.Column(
        db.Enum(OrigemDiretorio, name="origem_grupo_enum"),
        nullable=False,
        default=OrigemDiretorio.LOCAL,
    )

    usuarios = db.relationship("Usuario", secondary=usuario_grupos, back_populates="grupos")

    def __repr__(self):
        return f"<Grupo id={self.id} nome={self.nome} origem={self.origem}>"
