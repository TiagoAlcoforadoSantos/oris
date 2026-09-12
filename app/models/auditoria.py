"""
Model Auditoria.

Registro de trilha de auditoria (audit log). Cada linha representa
uma ação relevante realizada por um usuário no sistema (ex.: LOGIN,
CRIAR, APROVAR_ALTERACAO etc.). A partir da FASE 8, a gravação
efetiva desses eventos passa a acontecer de fato, via
app/services/auditoria_service.py.

Assim como em Alteracao, `registro_id` é genérico (não é uma FK
tradicional), pois uma auditoria pode referenciar qualquer entidade
do sistema.

CAMPOS ADICIONADOS NA FASE 8 — `valor_anterior` e `valor_novo`:

Os campos originais (Fase 2) não tinham onde guardar "o que mudou"
numa edição ou alteração de situação — só que uma ação ocorreu.
Sem isso não seria possível responder "qual era o valor?" / "qual
passou a ser o valor?", que é um requisito explícito da Fase 8. A
alternativa de reconstruir isso a partir de outras tabelas seria bem
mais complexa; um par de campos de texto (JSON) com só os campos que
de fato mudaram é a solução mais simples e suficiente aqui — não é
um sistema de versionamento completo, só um retrato do antes/depois
relevante para aquele evento específico.
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

    # Ex.: LOGIN, LOGOUT, CRIAR, EDITAR, ALTERAR_SITUACAO,
    # SOLICITAR_ALTERACAO, APROVAR_ALTERACAO, REJEITAR_ALTERACAO.
    acao = db.Column(db.String(100), nullable=False)

    # Tabela de negócio afetada pela ação (quando aplicável).
    tabela = db.Column(db.String(100), nullable=True)

    # Id do registro afetado dentro dessa tabela (quando aplicável).
    registro_id = db.Column(db.Integer, nullable=True)

    descricao = db.Column(db.Text, nullable=True)

    # Fase 8: retrato (em JSON) dos campos relevantes antes/depois da
    # ação — só quando fizer sentido (edição, alteração de situação).
    # Nunca contém senha ou senha_hash.
    valor_anterior = db.Column(db.Text, nullable=True)
    valor_novo = db.Column(db.Text, nullable=True)

    data_hora = db.Column(db.DateTime, nullable=False, default=utcnow)

    # --- Relacionamentos ---

    usuario = db.relationship("Usuario", back_populates="auditorias")

    def __repr__(self):
        return f"<Auditoria id={self.id} acao={self.acao} usuario_id={self.usuario_id}>"
