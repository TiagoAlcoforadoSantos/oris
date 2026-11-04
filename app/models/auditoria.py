"""Model Auditoria."""

from app.extensions import db
from app.utils.datetime_utils import utcnow


class Auditoria(db.Model):
    __tablename__ = "auditorias"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )

    acao = db.Column(db.String(100), nullable=False)

    tabela = db.Column(db.String(100), nullable=True)

    registro_id = db.Column(db.Integer, nullable=True)

    descricao = db.Column(db.Text, nullable=True)

    valor_anterior = db.Column(db.Text, nullable=True)
    valor_novo = db.Column(db.Text, nullable=True)

    data_hora = db.Column(db.DateTime, nullable=False, default=utcnow)


    usuario = db.relationship("Usuario", back_populates="auditorias")

    def __repr__(self):
        return f"<Auditoria id={self.id} acao={self.acao} usuario_id={self.usuario_id}>"
