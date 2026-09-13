"""
Testes da FASE 13B — Etapa 1 (estrutura global + Dashboard).

Esta etapa é puramente visual/estrutural — não altera nenhuma regra
de negócio, model, autenticação, RBAC, aprovação, auditoria,
importação ou os dados que o dashboard_service calcula. Os testes
aqui confirmam que:

1. A nova estrutura (sidebar/header) renderiza e respeita o RBAC já
   existente (mesmos itens visíveis por perfil que antes).
2. O Dashboard mostra os mesmos números reais do dashboard_service —
   nenhum dado fictício foi introduzido.
3. Os arquivos CSS novos são servidos corretamente.
4. Nada das fases anteriores quebrou (verificação pontual; a suíte
   completa das Fases 1-13A é executada junto — ver relatório).
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import Equipamento, PerfilUsuario, Servico, SituacaoUnidade, Unidade, Usuario
from app.services.dashboard_service import obter_indicadores
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}


@pytest.fixture
def app():
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()

        for perfil, email in EMAILS.items():
            db.session.add(
                Usuario(
                    nome=f"Usuário {perfil.value}",
                    email=email,
                    senha_hash=gerar_hash_senha(SENHA),
                    perfil=perfil,
                    ativo=True,
                )
            )

        unidade = Unidade(
            nome="UBS Estrutura Global", cnes="1350001", tipo="UBS",
            cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA,
        )
        db.session.add(unidade)
        db.session.commit()

        db.session.add(Servico(nome="Serviço Teste", unidade_id=unidade.id, situacao="ATIVO"))
        db.session.add(Equipamento(nome="Equip Teste", tipo="Clínico", unidade_id=unidade.id, situacao="ATIVO"))
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil):
    return client.post("/login", data={"email": EMAILS[perfil], "senha": SENHA}, follow_redirects=True)


# ----------------------------------------------------------------
# Estrutura global (sidebar/header) e RBAC do menu
# ----------------------------------------------------------------

def test_sidebar_e_header_renderizam_para_usuario_autenticado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/dashboard")
    html = resp.get_data(as_text=True)
    assert 'class="oris-sidebar"' in html
    assert 'class="oris-header"' in html
    assert 'class="oris-breadcrumb"' in html


def test_menu_administrador_mostra_auditoria_e_usuarios(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Auditoria</span>" in html
    assert "Usuários</span>" in html


def test_menu_gestao_informacao_mostra_auditoria_mas_nao_usuarios(client):
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Auditoria</span>" in html
    assert "Usuários</span>" not in html


def test_menu_responsavel_nao_mostra_auditoria_nem_usuarios(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Auditoria</span>" not in html
    assert "Usuários</span>" not in html


def test_menu_gestor_nao_mostra_auditoria_nem_usuarios(client):
    _login(client, PerfilUsuario.GESTOR)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Auditoria</span>" not in html
    assert "Usuários</span>" not in html


def test_todos_os_perfis_veem_itens_comuns_do_menu(client):
    for perfil in EMAILS:
        c = client.application.test_client()
        c.post("/login", data={"email": EMAILS[perfil], "senha": SENHA})
        html = c.get("/dashboard").get_data(as_text=True)
        for item in ("Dashboard</span>", "Unidades de Saúde</span>", "Serviços</span>", "Equipamentos</span>", "Importar</span>"):
            assert item in html, f"{item} ausente para {perfil.value}"


# ----------------------------------------------------------------
# Header: identidade do usuário e logout
# ----------------------------------------------------------------

def test_header_mostra_nome_perfil_e_logout(client):
    _login(client, PerfilUsuario.GESTOR)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Usuário GESTOR" in html
    assert "GESTOR" in html
    assert 'href="/logout"' in html


# ----------------------------------------------------------------
# Dashboard: dados reais, sem números fictícios
# ----------------------------------------------------------------

def test_dashboard_usa_indicadores_reais_do_service(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/dashboard").get_data(as_text=True)

    with app.app_context():
        indicadores = obter_indicadores()

    assert f'>{indicadores["unidades_total"]}<' in html
    assert f'>{indicadores["servicos_total"]}<' in html
    assert f'>{indicadores["equipamentos_total"]}<' in html
    assert f'>{indicadores["alteracoes_pendentes"]}<' in html


def test_dashboard_mostra_saudacao_com_primeiro_nome(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Olá, Usuário" in html


def test_dashboard_mostra_resumo_da_rede(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "UBS Estrutura Global" in html
    assert "1350001" in html


# ----------------------------------------------------------------
# Arquivos estáticos novos
# ----------------------------------------------------------------

def test_layout_css_e_servido(client):
    resp = client.get("/static/css/layout.css")
    assert resp.status_code == 200
    assert "oris-sidebar" in resp.get_data(as_text=True)


def test_dashboard_css_e_servido(client):
    resp = client.get("/static/css/dashboard.css")
    assert resp.status_code == 200
    assert "oris-kpi-card" in resp.get_data(as_text=True)


def test_bootstrap_icons_referenciado_no_layout(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "bootstrap-icons" in html


# ----------------------------------------------------------------
# CSP continua íntegra (Fase 12) — só ampliada para os novos domínios
# ----------------------------------------------------------------

def test_csp_permite_bootstrap_icons_sem_enfraquecer_seguranca(client):
    resp = client.get("/login")
    csp = resp.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "unsafe-eval" not in csp
    assert "cdn.jsdelivr.net" in csp


# ----------------------------------------------------------------
# Nada das fases anteriores quebrou (verificação pontual)
# ----------------------------------------------------------------

def test_login_continua_funcionando(client):
    resp = _login(client, PerfilUsuario.ADMINISTRADOR)
    assert "Bem-vindo ao ORIS" in resp.get_data(as_text=True)


def test_rbac_de_rotas_continua_funcionando(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/usuarios")
    assert resp.status_code == 403


def test_unidades_continua_acessivel_dentro_da_nova_estrutura(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/unidades")
    assert resp.status_code == 200
    assert "UBS Estrutura Global" in resp.get_data(as_text=True)
