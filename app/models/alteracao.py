"""
Model Alteracao.

Representa uma alteração sujeita a aprovação. Guarda quem criou, em
qual tabela/registro, e (quando aplicável) quem aprovou/rejeitou e
quando.

`tabela` + `registro_id` referenciam de forma genérica o registro
afetado (ex.: tabela="unidades", registro_id=5), já que uma mesma
Alteração pode dizer respeito a diferentes entidades (Unidade,
Serviço, Equipamento). Por isso `registro_id` não é uma foreign key
tradicional.

CAMPOS ADICIONADOS NA FASE 7 — `operacao` e `dados_novos`:

A estrutura original (Fase 2) não guardava QUAL operação estava
pendente nem OS DADOS necessários para aplicá-la depois. Sem isso,
não haveria como, no momento da aprovação, saber o que fazer (criar
um registro novo? editar quais campos? só mudar a situação?) nem com
quais valores. A alternativa seria aplicar a mudança na hora e só
"marcar" como pendente — mas isso contraria exatamente o que a Fase 7
pede ("a alteração não deve ser considerada efetivada antes da
aprovação"). Por isso dois campos mínimos foram adicionados:

- `operacao`: CRIAR, EDITAR ou ALTERAR_SITUACAO — indica como aplicar
  a alteração quando ela for aprovada.
- `dados_novos`: um JSON (texto) com os valores necessários para
  aplicar a operação (ex.: todos os campos de uma Unidade nova, ou
  apenas a nova situação). Optamos por um único campo de texto (JSON)
  em vez de uma tabela própria por campo alterado, para não criar uma
  arquitetura de versionamento — o suficiente aqui é reconstruir os
  valores no momento de aplicar.

`registro_id` também passou a ser opcional (`nullable=True`): para
uma operação CRIAR, o registro ainda não existe enquanto a alteração
está PENDENTE — só passa a existir (e só então `registro_id` é
preenchido) quando a criação é aprovada.
"""

from app.extensions import db
from app.models.enums import StatusAlteracao, TipoOperacaoAlteracao
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

    # Id do registro afetado dentro da tabela indicada acima. Nulo
    # enquanto uma operação CRIAR ainda está PENDENTE (o registro
    # ainda não existe) — ver docstring do módulo.
    registro_id = db.Column(db.Integer, nullable=True)

    # Fase 7: qual operação esta alteração representa.
    operacao = db.Column(
        db.Enum(TipoOperacaoAlteracao, name="tipo_operacao_alteracao_enum"),
        nullable=False,
    )

    # Fase 7: valores necessários para aplicar a operação quando
    # aprovada, serializados em JSON (ex.: '{"situacao": "INATIVA"}').
    dados_novos = db.Column(db.Text, nullable=True)

    descricao = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.Enum(StatusAlteracao, name="status_alteracao_enum"),
        nullable=False,
        default=StatusAlteracao.PENDENTE,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Usuário responsável por aprovar/rejeitar.
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
