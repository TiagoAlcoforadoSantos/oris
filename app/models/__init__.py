"""
Ponto único de importação dos models do ORIS.

Importar os models aqui garante que o SQLAlchemy conheça todas as
tabelas (metadata) quando `db.create_all()` for chamado, e permite
fazer `from app.models import Usuario, Unidade, ...` no resto do
código.
"""

from app.models.enums import (
    PerfilUsuario,
    SituacaoAtivoInativo,
    SituacaoUnidade,
    StatusAlteracao,
    TipoOperacaoAlteracao,
)
from app.models.usuario import Usuario
from app.models.unidade import Unidade
from app.models.servico import Servico
from app.models.equipamento import Equipamento
from app.models.alteracao import Alteracao
from app.models.auditoria import Auditoria

__all__ = [
    "Usuario",
    "Unidade",
    "Servico",
    "Equipamento",
    "Alteracao",
    "Auditoria",
    "PerfilUsuario",
    "SituacaoUnidade",
    "SituacaoAtivoInativo",
    "StatusAlteracao",
    "TipoOperacaoAlteracao",
]
