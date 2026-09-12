"""
Model Servico.

Representa um Serviço de Saúde Bucal oferecido por uma Unidade.
Uma Unidade possui vários Serviços; um Serviço pertence a uma única
Unidade.
"""

from app.extensions import db
from app.models.enums import SituacaoAtivoInativo
from app.models.mixins import TimestampMixin


class Servico(db.Model, TimestampMixin):
    __tablename__ = "servicos"

    id = db.Column(db.Integer, primary_key=True)

    unidade_id = db.Column(
        db.Integer,
        db.ForeignKey("unidades.id"),
        nullable=False,
        index=True,
    )

    nome = db.Column(db.String(150), nullable=False)

    situacao = db.Column(
        db.Enum(SituacaoAtivoInativo, name="situacao_servico_enum"),
        nullable=False,
        default=SituacaoAtivoInativo.ATIVO,
    )

    # --- Relacionamentos ---

    unidade = db.relationship("Unidade", back_populates="servicos")

    equipamentos = db.relationship(
        "Equipamento",
        back_populates="servico",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Servico id={self.id} nome={self.nome} unidade_id={self.unidade_id}>"
