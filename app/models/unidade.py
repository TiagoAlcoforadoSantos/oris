"""Model Unidade."""

from app.extensions import db
from app.models.enums import SituacaoUnidade
from app.models.mixins import TimestampMixin


class Unidade(db.Model, TimestampMixin):
    __tablename__ = "unidades"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(200), nullable=False)

    cnes = db.Column(db.String(20), nullable=False, index=True)

    unidade_e_mista = db.Column(db.Boolean, nullable=False, default=False)

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

    descricao_situacao = db.Column(db.Text, nullable=True)

    servicos = db.relationship(
        "Servico",
        back_populates="unidade",
        lazy="dynamic",
        cascade="save-update, merge",
    )

    equipamentos = db.relationship(
        "Equipamento",
        back_populates="unidade",
        lazy="dynamic",
        cascade="save-update, merge",
    )

    def __repr__(self):
        return f"<Unidade id={self.id} nome={self.nome} cnes={self.cnes}>"
