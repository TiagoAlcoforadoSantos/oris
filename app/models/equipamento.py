"""
Model Equipamento.

Representa um Equipamento de Saúde. A partir do REDESENHO DO MODELO
DE DADOS (ver docs/migrations/0001... e o relatório da Stage), um
Equipamento NÃO pertence obrigatoriamente a uma Unidade — a
documentação real do cliente descreve equipamentos sem unidade (ex.:
uma ambulância do SAMU).

Associação a um Serviço continua opcional e, importante, INDEPENDENTE
de Unidade: `servico_id` é uma coluna própria (não depende de
`unidade_id` estar preenchido), então um Equipamento sem Unidade
ainda pode estar associado a um Serviço — e um Serviço sem Unidade
ainda pode ter Equipamentos associados a ele. Esta já era a estrutura
física do relacionamento (FK direta Equipamento→Serviço); o que
mudou nesta Stage é que ela deixa de depender implicitamente de as
duas entidades pertencerem à mesma Unidade, porque agora nenhuma das
duas exige Unidade.
"""

from app.extensions import db
from app.models.enums import SituacaoAtivoInativo
from app.models.mixins import TimestampMixin


class Equipamento(db.Model, TimestampMixin):
    __tablename__ = "equipamentos"

    id = db.Column(db.Integer, primary_key=True)

    # Vínculo opcional (Stage "modelo de dados"): um Equipamento pode
    # existir sem nenhuma Unidade associada.
    unidade_id = db.Column(
        db.Integer,
        db.ForeignKey("unidades.id"),
        nullable=True,
        index=True,
    )

    # Associação a um Serviço é opcional e independente de Unidade —
    # um equipamento pode estar vinculado a um serviço mesmo quando
    # nenhum dos dois (ou só um deles) tem unidade_id preenchido.
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
