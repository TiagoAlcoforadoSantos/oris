"""Model Alteracao."""

from app.extensions import db
from app.models.enums import StatusAlteracao, TipoOperacaoAlteracao
from app.utils.datetime_utils import utcnow


class Alteracao(db.Model):
    __tablename__ = "alteracoes"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )

    tabela = db.Column(db.String(100), nullable=False)

    registro_id = db.Column(db.Integer, nullable=True)

    operacao = db.Column(
        db.Enum(TipoOperacaoAlteracao, name="tipo_operacao_alteracao_enum"),
        nullable=False,
    )

    dados_novos = db.Column(db.Text, nullable=True)

    descricao = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.Enum(StatusAlteracao, name="status_alteracao_enum"),
        nullable=False,
        default=StatusAlteracao.PENDENTE,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    approved_by = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=True,
        index=True,
    )
    approved_at = db.Column(db.DateTime, nullable=True)


    usuario_criador = db.relationship(
        "Usuario",
        back_populates="alteracoes_criadas",
        foreign_keys=[usuario_id],
    )

    usuario_aprovador = db.relationship(
        "Usuario",
        back_populates="alteracoes_aprovadas",
        foreign_keys=[approved_by],
    )

    def __repr__(self):
        return (
            f"<Alteracao id={self.id} tabela={self.tabela} "
            f"registro_id={self.registro_id} status={self.status}>"
        )
