"""
Model Equipamento.

Um Equipamento sempre pertence a uma Unidade e, opcionalmente, pode
estar associado a um Serviço específico dessa mesma unidade.
"""

from app.extensions import db
from app.models.enums import SituacaoAtivoInativo
from app.models.mixins import TimestampMixin


class Equipamento(db.Model, TimestampMixin):
    __tablename__ = "equipamentos"

    id = db.Column(db.Integer, primary_key=True)

    unidade_id = db.Column(
        db.Integer,
        db.ForeignKey("unidades.id"),
        nullable=False,
        index=True,
    )

    # Associação a um Serviço é opcional: um equipamento pode ser da
    # unidade como um todo, sem estar vinculado a um serviço específico.
    servico_id = db.Column(
        db.Integer,
        db.ForeignKey("servicos.id"),
        nullable=True,
        index=True,
    )

    nome = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(100), nullable=True)

    situacao = db.Column(
        db.Enum(SituacaoAtivoInativo, name="situacao_equipamento_enum"),
        nullable=False,
        default=SituacaoAtivoInativo.ATIVO,
    )

    # --- Relacionamentos ---

    unidade = db.relationship("Unidade", back_populates="equipamentos")
    servico = db.relationship("Servico", back_populates="equipamentos")

    def __repr__(self):
        return f"<Equipamento id={self.id} nome={self.nome} unidade_id={self.unidade_id}>"
