"""
Model Unidade.

Representa um registro de Unidade de Saúde Bucal. `id` (interno,
auto-incremento) é o identificador de negócio da entidade — não o
CNES.

REDESENHO DO MODELO DE DADOS (Stage "modelo de dados" — ver
docs/migrations/0001... e o relatório da Stage): a documentação real
do cliente ("Documentação da planilha REDE_SAUDE_RECIFE_GEO") mostra
que o CNES NÃO é um identificador único de negócio — o mesmo CNES
pode aparecer em mais de um registro (ex.: "Policlínica" e
"Maternidade" sob o mesmo CNES, quando a unidade é mista). Por isso:

- `cnes` deixou de ter constraint UNIQUE — passou a ser só um
  atributo de referência, mantendo apenas um índice (não-único) para
  consulta/performance, já que ele continua sendo usado para agrupar
  registros que compartilham a mesma referência cadastral.
- `unidade_e_mista` foi adicionado para marcar explicitamente que
  este registro participa de um CNES que possui mais de uma
  tipologia (ex.: Policlínica + Maternidade) — sem transformar CNES
  em entidade própria nesta Stage.

O valor convencional `9999999` (CNES fictício, usado pelo cliente
para registros sem CNES próprio) não recebe nenhum tratamento
especial de unicidade — ele é só mais um valor de texto no campo
`cnes`, exatamente como qualquer outro, e pode se repetir livremente.
"""

from app.extensions import db
from app.models.enums import SituacaoUnidade
from app.models.mixins import TimestampMixin


class Unidade(db.Model, TimestampMixin):
    __tablename__ = "unidades"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(200), nullable=False)

    # Código CNES do registro — atributo de referência, NÃO é mais
    # único: o mesmo CNES pode ser compartilhado por vários registros
    # de Unidade (ex.: unidade mista, ou serviços que usam o CNES da
    # unidade à qual estão associados como referência). Mantido com
    # índice (não-único) porque ainda é um campo de busca/filtro
    # frequente.
    cnes = db.Column(db.String(20), nullable=False, index=True)

    # Marca que este registro participa de um CNES que possui mais de
    # uma tipologia (ex.: o mesmo CNES tem um registro "Policlínica" e
    # um registro "Maternidade"). Não é derivado automaticamente nesta
    # Stage — é um campo simples, preenchido por quem cadastra/aprova.
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

    # --- Relacionamentos ---

    # `delete-orphan` foi removido: Serviço e Equipamento agora podem
    # existir sem Unidade (unidade_id nullable), então deixar de
    # pertencer à coleção desta Unidade não é mais, por definição, um
    # estado inválido que deva apagar o registro — pode ser
    # simplesmente um serviço/equipamento que passou a não ter mais
    # vínculo com nenhuma unidade. `save-update` é mantido para
    # preservar a conveniência de salvar em cascata ao adicionar um
    # filho à coleção.
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
