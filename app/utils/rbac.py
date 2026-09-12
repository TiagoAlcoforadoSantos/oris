"""
Matriz de acesso das áreas de teste do RBAC (Fase 4).

Fica centralizada aqui para ser usada tanto pelos decorators das
rotas (app/routes/areas.py) quanto pela página inicial, que só
mostra os links das áreas que o usuário autenticado pode acessar
— evitando duplicar a mesma lista de perfis em dois lugares.
"""

from app.models import PerfilUsuario

ADMINISTRADOR = PerfilUsuario.ADMINISTRADOR.value
GESTAO_INFORMACAO = PerfilUsuario.GESTAO_INFORMACAO.value
RESPONSAVEL_SAUDE_BUCAL = PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL.value
GESTOR = PerfilUsuario.GESTOR.value

# endpoint -> (título exibido no menu, perfis que podem acessar)
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
    """Retorna a lista de (endpoint, título) das áreas de teste do
    RBAC que o `usuario` pode acessar, para exibição no menu.

    Não substitui a checagem de autorização das rotas — é só para a
    interface não oferecer links que o backend recusaria de qualquer
    forma.
    """
    if usuario is None:
        return []

    return [
        (endpoint, titulo)
        for endpoint, (titulo, perfis_permitidos) in AREAS_DE_TESTE_RBAC.items()
        if usuario.perfil.value in perfis_permitidos
    ]
