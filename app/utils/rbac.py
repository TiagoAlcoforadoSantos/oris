"""Matriz de acesso das áreas de teste do RBAC (Fase 4)."""

from app.models import PerfilUsuario

ADMINISTRADOR = PerfilUsuario.ADMINISTRADOR.value
GESTAO_INFORMACAO = PerfilUsuario.GESTAO_INFORMACAO.value
RESPONSAVEL_SAUDE_BUCAL = PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL.value
GESTOR = PerfilUsuario.GESTOR.value

AREAS_DE_TESTE_RBAC = {
    "areas.admin": ("Área Administrativa", {ADMINISTRADOR}),
    "areas.gestao": ("Área de Gestão da Informação", {ADMINISTRADOR, GESTAO_INFORMACAO}),
    "areas.responsavel": (
        "Área do Responsável pela Saúde Bucal",
        {ADMINISTRADOR, RESPONSAVEL_SAUDE_BUCAL},
    ),
    "areas.gestor": ("Área do Gestor", {ADMINISTRADOR, GESTOR}),
}


def areas_visiveis_para(usuario):
    """Retorna a lista de (endpoint, título) das áreas de teste do RBAC que o `usuario`..."""
    if usuario is None:
        return []

    return [
        (endpoint, titulo)
        for endpoint, (titulo, perfis_permitidos) in AREAS_DE_TESTE_RBAC.items()
        if usuario.perfil.value in perfis_permitidos
    ]
