"""Model Servico."""

from app.extensions import db
from app.models.enums import SituacaoAtivoInativo
from app.models.mixins import TimestampMixin


class Servico(db.Model, TimestampMixin):
    __tablename__ = "servicos"

    id = db.Column(db.Integer, primary_key=True)

    unidade_id = db.Column(
        db.Integer,
        db.ForeignKey("unidades.id"),
        nullable=True,
        index=True,
    )

    nome = db.Column(db.String(150), nullable=False)

    situacao = db.Column(
        db.Enum(SituacaoAtivoInativo, name="situacao_servico_enum"),
        nullable=False,
        default=SituacaoAtivoInativo.ATIVO,
    )

    descricao_situacao = db.Column(db.Text, nullable=True)

    unidade = db.relationship("Unidade", back_populates="servicos")

    equipamentos = db.relationship(
        "Equipamento",
        back_populates="servico",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Servico id={self.id} nome={self.nome} unidade_id={self.unidade_id}>"
