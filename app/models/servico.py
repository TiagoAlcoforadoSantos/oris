"""
Model Servico.

Representa um Serviço de Saúde Bucal. Uma Unidade pode possuir vários
Serviços — mas, a partir do REDESENHO DO MODELO DE DADOS (ver
docs/migrations/0001... e o relatório da Stage), um Serviço NÃO
pertence obrigatoriamente a uma Unidade.

A documentação real do cliente ("Documentação da planilha
REDE_SAUDE_RECIFE_GEO") descreve serviços sem vínculo com uma unidade
tradicional (ex.: um ponto municipal de vacinação instalado em um
shopping) — por isso `unidade_id` passou a ser opcional
(`nullable=True`). Quando presente, a FK continua garantindo que ele
aponte para uma Unidade existente; quando ausente, o Serviço
simplesmente não tem Unidade associada.
"""

from app.extensions import db
from app.models.enums import SituacaoAtivoInativo
from app.models.mixins import TimestampMixin


class Servico(db.Model, TimestampMixin):
    __tablename__ = "servicos"

    id = db.Column(db.Integer, primary_key=True)

    # Vínculo opcional (Stage "modelo de dados"): um Serviço pode
    # existir sem nenhuma Unidade associada. Quando informado, a FK
    # continua sendo validada normalmente.
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

    # --- Relacionamentos ---

    unidade = db.relationship("Unidade", back_populates="servicos")

    equipamentos = db.relationship(
        "Equipamento",
        back_populates="servico",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Servico id={self.id} nome={self.nome} unidade_id={self.unidade_id}>"
