"""Enumerações usadas pelos models do ORIS."""

import enum


class PerfilUsuario(str, enum.Enum):
    """Perfis de acesso previstos para o ORIS."""

    ADMINISTRADOR = "ADMINISTRADOR"
    GESTAO_INFORMACAO = "GESTAO_INFORMACAO"
    RESPONSAVEL_SAUDE_BUCAL = "RESPONSAVEL_SAUDE_BUCAL"
    GESTOR = "GESTOR"


class OrigemDiretorio(str, enum.Enum):
    """De onde vem um usuário ou grupo: cadastro local do ORIS ou um
    diretório externo (LDAP / OIDC) — ver app/services/diretorio_service.py."""

    LOCAL = "LOCAL"
    LDAP = "LDAP"
    OIDC = "OIDC"


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
    """Status do fluxo de aprovação de uma Alteração."""

    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"


class TipoOperacaoAlteracao(str, enum.Enum):
    """Tipo de operação que uma Alteração pendente representa (Fase 7)."""

    CRIAR = "CRIAR"
    EDITAR = "EDITAR"
    ALTERAR_SITUACAO = "ALTERAR_SITUACAO"
