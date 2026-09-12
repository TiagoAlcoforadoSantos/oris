"""
Testes da FASE 4 — RBAC (controle de acesso por perfil).

Roda contra SQLite em memória (TestingConfig), reaproveitando o
mesmo padrão de fixtures da Fase 3. Cria um usuário ativo para cada
um dos 4 perfis e um usuário inativo, e testa a matriz de acesso
das rotas /admin, /gestao, /responsavel e /gestor.
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import PerfilUsuario, Usuario
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}

EMAIL_INATIVO = "inativo@oris.com.br"


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

        db.session.add(
            Usuario(
                nome="Usuário Inativo",
                email=EMAIL_INATIVO,
                senha_hash=gerar_hash_senha(SENHA),
                perfil=PerfilUsuario.GESTOR,
                ativo=False,
            )
        )

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, email):
    return client.post("/login", data={"email": email, "senha": SENHA}, follow_redirects=True)


# ----------------------------------------------------------------
# 1. Usuário não autenticado é redirecionado para login
# ----------------------------------------------------------------

@pytest.mark.parametrize("rota", ["/admin", "/gestao", "/responsavel", "/gestor"])
def test_usuario_nao_autenticado_redireciona_para_login(client, rota):
    resp = client.get(rota, follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# 2-5. Acesso a /admin: só ADMINISTRADOR
# ----------------------------------------------------------------

def test_administrador_acessa_admin(client):
    _login(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "Área Administrativa" in resp.get_data(as_text=True)


def test_gestao_informacao_nao_acessa_admin(client):
    _login(client, EMAILS[PerfilUsuario.GESTAO_INFORMACAO])
    resp = client.get("/admin")
    assert resp.status_code == 403


def test_responsavel_saude_bucal_nao_acessa_admin(client):
    _login(client, EMAILS[PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL])
    resp = client.get("/admin")
    assert resp.status_code == 403


def test_gestor_nao_acessa_admin(client):
    _login(client, EMAILS[PerfilUsuario.GESTOR])
    resp = client.get("/admin")
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 6-7. Acesso a /gestao: GESTAO_INFORMACAO e ADMINISTRADOR
# ----------------------------------------------------------------

def test_gestao_informacao_acessa_gestao(client):
    _login(client, EMAILS[PerfilUsuario.GESTAO_INFORMACAO])
    resp = client.get("/gestao")
    assert resp.status_code == 200
    assert "Área de Gestão da Informação" in resp.get_data(as_text=True)


def test_administrador_acessa_gestao(client):
    _login(client, EMAILS[PerfilUsuario.ADMINISTRADOR])
    resp = client.get("/gestao")
    assert resp.status_code == 200


def test_responsavel_nao_acessa_gestao(client):
    _login(client, EMAILS[PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL])
    resp = client.get("/gestao")
    assert resp.status_code == 403


def test_gestor_nao_acessa_gestao(client):
    _login(client, EMAILS[PerfilUsuario.GESTOR])
    resp = client.get("/gestao")
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 8. RESPONSAVEL_SAUDE_BUCAL acessa /responsavel
# ----------------------------------------------------------------

def test_responsavel_acessa_responsavel(client):
    _login(client, EMAILS[PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL])
    resp = client.get("/responsavel")
    assert resp.status_code == 200
    assert "Área do Responsável pela Saúde Bucal" in resp.get_data(as_text=True)


def test_gestao_informacao_nao_acessa_responsavel(client):
    _login(client, EMAILS[PerfilUsuario.GESTAO_INFORMACAO])
    resp = client.get("/responsavel")
    assert resp.status_code == 403


def test_gestor_nao_acessa_responsavel(client):
    _login(client, EMAILS[PerfilUsuario.GESTOR])
    resp = client.get("/responsavel")
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 9-10. Acesso a /gestor: só GESTOR (e ADMINISTRADOR)
# ----------------------------------------------------------------

def test_gestor_acessa_gestor(client):
    _login(client, EMAILS[PerfilUsuario.GESTOR])
    resp = client.get("/gestor")
    assert resp.status_code == 200
    assert "Área do Gestor" in resp.get_data(as_text=True)


def test_gestor_nao_acessa_area_administrativa(client):
    _login(client, EMAILS[PerfilUsuario.GESTOR])
    resp = client.get("/admin")
    assert resp.status_code == 403


def test_responsavel_nao_acessa_gestor(client):
    _login(client, EMAILS[PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL])
    resp = client.get("/gestor")
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 11. Usuário autenticado sem permissão recebe página de acesso negado
# ----------------------------------------------------------------

def test_pagina_de_acesso_negado_e_exibida(client):
    _login(client, EMAILS[PerfilUsuario.GESTOR])
    resp = client.get("/admin")
    assert resp.status_code == 403
    assert "Acesso negado" in resp.get_data(as_text=True)
    assert "não possui permissão" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 12. Usuário inativo não consegue autenticar (continua valendo)
# ----------------------------------------------------------------

def test_usuario_inativo_nao_autentica(client):
    resp = _login(client, EMAIL_INATIVO)
    assert resp.status_code == 200
    assert "Email ou senha inválidos." in resp.get_data(as_text=True)

    # E, por consequência, também não acessa nenhuma área protegida
    resp = client.get("/gestor", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# Extra: rota "/" continua acessível a qualquer perfil autenticado
# e mostra apenas os links de área permitidos ao perfil
# ----------------------------------------------------------------

def test_index_mostra_apenas_links_permitidos_ao_perfil(client):
    _login(client, EMAILS[PerfilUsuario.GESTOR])
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Área do Gestor" in html
    assert "Área Administrativa" not in html
    assert "Área de Gestão da Informação" not in html
    assert "Área do Responsável pela Saúde Bucal" not in html
