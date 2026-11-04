"""Testes de segurança da API REST v1 (cabeçalhos e sessão)."""

import pytest

from app import create_app
from app.extensions import db
from app.models import PerfilUsuario, Unidade, SituacaoUnidade, Usuario
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"
EMAIL = "gestor@oris.com.br"


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        db.session.add(Usuario(nome="Gestor", email=EMAIL,
                               senha_hash=gerar_hash_senha(SENHA),
                               perfil=PerfilUsuario.GESTOR, ativo=True))
        db.session.add(Unidade(nome="UBS A", cnes="1111111", tipo="UBS", cidade="Recife",
                               uf="PE", situacao=SituacaoUnidade.ATIVA))
        db.session.commit()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def cliente(app):
    c = app.test_client()
    c.post("/login", data={"email": EMAIL, "senha": SENHA})
    return c


@pytest.mark.parametrize("url", [
    "/api/v1/unidades", "/api/v1/unidades/1", "/api/v1/servicos",
    "/api/v1/equipamentos", "/api/v1/indicadores",
])
def test_respostas_autenticadas_nao_sao_cacheaveis(cliente, url):
    r = cliente.get(url)
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"


def test_resposta_401_tambem_nao_e_cacheavel(app):
    r = app.test_client().get("/api/v1/unidades")
    assert r.status_code == 401
    assert r.headers["Cache-Control"] == "no-store"


def test_api_mantem_headers_de_seguranca_globais(cliente):
    r = cliente.get("/api/v1/indicadores")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
