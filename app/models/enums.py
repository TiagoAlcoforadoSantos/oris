"""
Enumerações usadas pelos models do ORIS.

Ficam centralizadas aqui para reaproveitamento entre models, formulários
e futuras regras de negócio (RBAC, fluxo de aprovação etc.), evitando
strings "soltas" espalhadas pelo código.
"""

import enum


class PerfilUsuario(str, enum.Enum):
    """Perfis de acesso previstos para o ORIS.

    As REGRAS de permissão de cada perfil NÃO são implementadas nesta
    fase — apenas o campo/valor é definido, para ser usado no RBAC
    (Fase 4) e no login (Fase 3).
    """

    ADMINISTRADOR = "ADMINISTRADOR"
    GESTAO_INFORMACAO = "GESTAO_INFORMACAO"
    RESPONSAVEL_SAUDE_BUCAL = "RESPONSAVEL_SAUDE_BUCAL"
    GESTOR = "GESTOR"


class SituacaoUnidade(str, enum.Enum):
    """Situações possíveis de uma Unidade de Saúde Bucal."""

    ATIVA = "ATIVA"
    INATIVA = "INATIVA"
    MANUTENCAO = "MANUTENCAO"


class SituacaoAtivoInativo(str, enum.Enum):
    """Situação simples (ativo/inativo) usada por Serviço e Equipamento."""

    ATIVO = "ATIVO"
    INATIVO = "INATIVO"


class StatusAlteracao(str, enum.Enum):
    """Status do fluxo de aprovação de uma Alteração.

    O FLUXO em si (quem aprova, quando, notificações etc.) será
    implementado na Fase 7 — aqui apenas os valores possíveis existem.
    """

    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"
