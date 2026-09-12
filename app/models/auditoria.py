"""
Model Auditoria.

Registro de trilha de auditoria (audit log). Cada linha representa
uma ação relevante realizada por um usuário no sistema (ex.: LOGIN,
CRIOU_UNIDADE, APROVOU_ALTERACAO etc.).

A GRAVAÇÃO efetiva dos eventos (nos pontos do código onde cada ação
acontece) será feita a partir da FASE 3 em diante, conforme cada
funcionalidade for implementada. Nesta fase existe apenas a tabela.

Assim como em Alteracao, `registro_id` é genérico (não é uma FK
tradicional), pois uma auditoria pode referenciar qualquer entidade
do sistema.
"""

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

    # Ex.: LOGIN, LOGOUT, CRIOU_UNIDADE, APROVOU_ALTERACAO, ACESSO_NEGADO...
    acao = db.Column(db.String(100), nullable=False)

    # Tabela de negócio afetada pela ação (quando aplicável).
    tabela = db.Column(db.String(100), nullable=True)

    # Id do registro afetado dentro dessa tabela (quando aplicável).
    registro_id = db.Column(db.Integer, nullable=True)

    descricao = db.Column(db.Text, nullable=True)

    data_hora = db.Column(db.DateTime, nullable=False, default=utcnow)

    # --- Relacionamentos ---

    usuario = db.relationship("Usuario", back_populates="auditorias")

    def __repr__(self):
        return f"<Auditoria id={self.id} acao={self.acao} usuario_id={self.usuario_id}>"
