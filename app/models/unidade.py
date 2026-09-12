"""
Model Unidade.

Representa uma Unidade de Saúde Bucal. É a entidade central do MVP
do ORIS: Serviços e Equipamentos sempre se relacionam a uma Unidade.

O campo `cnes` já está estruturado para permitir, no futuro, a
conciliação/integração com o CNES real (Fase futura) — aqui apenas o
campo existe, com índice único, sem nenhuma integração implementada.
"""

from app.extensions import db
from app.models.enums import SituacaoUnidade
from app.models.mixins import TimestampMixin


class Unidade(db.Model, TimestampMixin):
    __tablename__ = "unidades"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(200), nullable=False)

    # Código CNES da unidade. Único para evitar cadastro duplicado da
    # mesma unidade (regra de validação mencionada no MVP).
    cnes = db.Column(db.String(20), nullable=False, unique=True, index=True)

    tipo = db.Column(db.String(100), nullable=True)

    endereco = db.Column(db.String(255), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    uf = db.Column(db.String(2), nullable=True)

    situacao = db.Column(
        db.Enum(SituacaoUnidade, name="situacao_unidade_enum"),
        nullable=False,
        default=SituacaoUnidade.ATIVA,
    )

    # --- Relacionamentos ---

    servicos = db.relationship(
        "Servico",
        back_populates="unidade",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    equipamentos = db.relationship(
        "Equipamento",
        back_populates="unidade",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Unidade id={self.id} nome={self.nome} cnes={self.cnes}>"
