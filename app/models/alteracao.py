"""
Model Alteracao.

Representa uma alteração sujeita a aprovação (workflow completo será
implementado na FASE 7). Aqui existe apenas a estrutura de dados:
quem criou, em qual tabela/registro, e (quando aplicável) quem
aprovou/rejeitou e quando.

`tabela` + `registro_id` referenciam de forma genérica o registro
afetado (ex.: tabela="unidades", registro_id=5), já que uma mesma
Alteração pode dizer respeito a diferentes entidades (Unidade,
Serviço, Equipamento). Por isso `registro_id` não é uma foreign key
tradicional.
"""

from app.extensions import db
from app.models.enums import StatusAlteracao
from app.utils.datetime_utils import utcnow


class Alteracao(db.Model):
    __tablename__ = "alteracoes"

    id = db.Column(db.Integer, primary_key=True)

    # Usuário que propôs/criou a alteração.
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )

    # Nome da tabela de negócio afetada (ex.: "unidades", "servicos").
    tabela = db.Column(db.String(100), nullable=False)

    # Id do registro afetado dentro da tabela indicada acima.
    registro_id = db.Column(db.Integer, nullable=False)

    descricao = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.Enum(StatusAlteracao, name="status_alteracao_enum"),
        nullable=False,
        default=StatusAlteracao.PENDENTE,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Usuário responsável por aprovar/rejeitar (preenchido só quando
    # a decisão acontecer — Fase 7).
    approved_by = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=True,
        index=True,
    )
    approved_at = db.Column(db.DateTime, nullable=True)

    # --- Relacionamentos ---

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
