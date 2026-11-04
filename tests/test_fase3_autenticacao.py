"""Testes da FASE 3 - autenticação (login, bcrypt, sessão, logout)."""

import re

import pytest

from app import create_app
from app.extensions import db
from app.models import PerfilUsuario, Usuario
from app.utils.security import gerar_hash_senha, verificar_senha
from config import TestingConfig

EMAIL_ATIVO = "usuario.ativo@oris.com.br"
EMAIL_INATIVO = "usuario.inativo@oris.com.br"
SENHA_CORRETA = "SenhaForte123!"


@pytest.fixture
def app():
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()

        usuario_ativo = Usuario(
            nome="Usuário Ativo",
            email=EMAIL_ATIVO,
            senha_hash=gerar_hash_senha(SENHA_CORRETA),
            perfil=PerfilUsuario.GESTOR,
            ativo=True,
        )
        usuario_inativo = Usuario(
            nome="Usuário Inativo",
            email=EMAIL_INATIVO,
            senha_hash=gerar_hash_senha(SENHA_CORRETA),
            perfil=PerfilUsuario.GESTOR,
            ativo=False,
        )
        db.session.add_all([usuario_ativo, usuario_inativo])
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_check_continua_funcionando(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_pagina_login_responde_200(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "ORIS" in resp.get_data(as_text=True)


def test_login_usuario_inexistente_falha(client):
    resp = client.post(
        "/login",
        data={"email": "nao.existe@oris.com.br", "senha": "qualquer"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Email ou senha inválidos." in resp.get_data(as_text=True)


def test_login_senha_incorreta_falha(client):
    resp = client.post(
        "/login",
        data={"email": EMAIL_ATIVO, "senha": "senha-errada"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Email ou senha inválidos." in resp.get_data(as_text=True)


def test_login_senha_correta_funciona(client):
    resp = client.post(
        "/login",
        data={"email": EMAIL_ATIVO, "senha": SENHA_CORRETA},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Bem-vindo ao ORIS" in resp.get_data(as_text=True)


def test_usuario_inativo_nao_consegue_logar(client):
    resp = client.post(
        "/login",
        data={"email": EMAIL_INATIVO, "senha": SENHA_CORRETA},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Email ou senha inválidos." in resp.get_data(as_text=True)
    assert "Bem-vindo ao ORIS" not in resp.get_data(as_text=True)


def test_sessao_e_criada_apos_login_correto(client):
    client.post("/login", data={"email": EMAIL_ATIVO, "senha": SENHA_CORRETA})

    with client.session_transaction() as sess:
        assert sess.get("autenticado") is True
        assert sess.get("usuario_id") is not None
        assert "senha" not in sess
        assert "senha_hash" not in sess


def test_rota_protegida_bloqueia_usuario_nao_autenticado(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_usuario_autenticado_acessa_rota_protegida(client):
    client.post("/login", data={"email": EMAIL_ATIVO, "senha": SENHA_CORRETA})

    resp = client.get("/")
    assert resp.status_code == 200
    assert "Usuário Ativo" in resp.get_data(as_text=True)


def test_logout_remove_autenticacao(client):
    client.post("/login", data={"email": EMAIL_ATIVO, "senha": SENHA_CORRETA})
    client.get("/logout")

    with client.session_transaction() as sess:
        assert "autenticado" not in sess
        assert "usuario_id" not in sess


def test_apos_logout_rota_protegida_exige_login_novamente(client):
    client.post("/login", data={"email": EMAIL_ATIVO, "senha": SENHA_CORRETA})
    client.get("/logout")

    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_senha_armazenada_e_hash_bcrypt(app):
    with app.app_context():
        usuario = Usuario.query.filter_by(email=EMAIL_ATIVO).first()

        assert usuario.senha_hash != SENHA_CORRETA

        assert usuario.senha_hash.startswith("$2b$") or usuario.senha_hash.startswith("$2a$")

        assert verificar_senha(SENHA_CORRETA, usuario.senha_hash) is True
        assert verificar_senha("senha-errada", usuario.senha_hash) is False


def test_gerar_hash_senha_produz_hashes_diferentes_a_cada_chamada():
    hash1 = gerar_hash_senha(SENHA_CORRETA)
    hash2 = gerar_hash_senha(SENHA_CORRETA)

    assert hash1 != hash2
    assert verificar_senha(SENHA_CORRETA, hash1) is True
    assert verificar_senha(SENHA_CORRETA, hash2) is True
