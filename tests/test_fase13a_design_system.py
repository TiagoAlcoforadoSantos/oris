"""Testes da FASE 13A - Design System e identidade visual."""

import pytest

from app import create_app
from app.extensions import db
from app.models import PerfilUsuario, Usuario
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"


@pytest.fixture
def app():
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()
        db.session.add(
            Usuario(
                nome="Admin",
                email="admin@oris.com.br",
                senha_hash=gerar_hash_senha(SENHA),
                perfil=PerfilUsuario.ADMINISTRADOR,
                ativo=True,
            )
        )
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client):
    return client.post("/login", data={"email": "admin@oris.com.br", "senha": SENHA}, follow_redirects=True)


def test_pagina_design_system_acessivel_sem_login(client):
    resp = client.get("/design-system")
    assert resp.status_code == 200


def test_pagina_design_system_mostra_paleta_e_tipografia(client):
    resp = client.get("/design-system")
    html = resp.get_data(as_text=True)
    assert "Turquesa ORIS" in html
    assert "Space Grotesk" in html
    assert "IBM Plex Sans" in html


def test_tokens_css_e_servido(client):
    resp = client.get("/static/css/tokens.css")
    assert resp.status_code == 200
    conteudo = resp.get_data(as_text=True)
    assert "--oris-navy" in conteudo
    assert "--oris-teal" in conteudo
    assert "#18B7B0" in conteudo


def test_design_system_css_e_servido(client):
    resp = client.get("/static/css/oris-design-system.css")
    assert resp.status_code == 200
    conteudo = resp.get_data(as_text=True)
    assert "var(--oris-navy)" in conteudo


def test_layout_base_referencia_tokens_e_fontes(client):
    resp = client.get("/login")
    html = resp.get_data(as_text=True)
    assert "tokens.css" in html
    assert "oris-design-system.css" in html
    assert "fonts.googleapis.com" in html


def test_headers_de_seguranca_continuam_presentes_incluindo_fontes(client):
    resp = client.get("/login")
    csp = resp.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "fonts.googleapis.com" in csp
    assert "fonts.gstatic.com" in csp
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_fluxo_de_login_continua_funcionando(client):
    resp = _login(client)
    assert "Bem-vindo ao ORIS" in resp.get_data(as_text=True)


def test_dashboard_continua_funcionando(client):
    _login(client)
    resp = client.get("/dashboard")
    assert resp.status_code == 200


def test_rbac_continua_funcionando(client, app):
    with app.app_context():
        db.session.add(
            Usuario(
                nome="Gestor",
                email="gestor@oris.com.br",
                senha_hash=gerar_hash_senha(SENHA),
                perfil=PerfilUsuario.GESTOR,
                ativo=True,
            )
        )
        db.session.commit()

    client.post("/login", data={"email": "gestor@oris.com.br", "senha": SENHA}, follow_redirects=True)
    resp = client.get("/usuarios")
    assert resp.status_code == 403


def test_privacidade_continua_funcionando(client):
    resp = client.get("/privacidade")
    assert resp.status_code == 200
