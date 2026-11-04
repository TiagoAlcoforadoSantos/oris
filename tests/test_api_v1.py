"""Testes da API REST v1 (somente leitura) e da especificação OpenAPI."""

import pytest

from app import create_app
from app.extensions import db
from app.models import (Equipamento, PerfilUsuario, Servico, SituacaoAtivoInativo,
                        SituacaoUnidade, Unidade, Usuario)
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        db.session.add(Usuario(nome="Gestor", email="gestor@oris.com.br",
                               senha_hash=gerar_hash_senha(SENHA),
                               perfil=PerfilUsuario.GESTOR, ativo=True))
        u1 = Unidade(nome="UBS A", cnes="1111111", tipo="UBS", bairro="Várzea", cidade="Recife",
                     uf="PE", situacao=SituacaoUnidade.ATIVA)
        u2 = Unidade(nome="UBS B", cnes="2222222", tipo="UBS", cidade="Recife", uf="PE",
                     situacao=SituacaoUnidade.INATIVA)
        db.session.add_all([u1, u2])
        db.session.commit()
        s = Servico(nome="Endodontia", unidade_id=u1.id, situacao=SituacaoAtivoInativo.ATIVO)
        db.session.add(s)
        db.session.commit()
        db.session.add(Equipamento(nome="Autoclave #1", tipo="Autoclave", unidade_id=u1.id,
                                   servico_id=s.id, situacao=SituacaoAtivoInativo.ATIVO))
        db.session.commit()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def cliente(app):
    c = app.test_client()
    c.post("/login", data={"email": "gestor@oris.com.br", "senha": SENHA})
    return c


def test_sem_login_retorna_401_json(app):
    r = app.test_client().get("/api/v1/unidades")
    assert r.status_code == 401
    assert r.get_json()["erro"]["status"] == 401


def test_lista_unidades_com_filtro_e_paginacao(cliente):
    r = cliente.get("/api/v1/unidades")
    corpo = r.get_json()
    assert r.status_code == 200 and corpo["meta"]["total"] == 2
    r = cliente.get("/api/v1/unidades?situacao=ATIVA&limite=1")
    corpo = r.get_json()
    assert [u["nome"] for u in corpo["dados"]] == ["UBS A"]
    assert corpo["meta"]["limite"] == 1


def test_situacao_invalida_retorna_400(cliente):
    assert cliente.get("/api/v1/unidades?situacao=XPTO").status_code == 400
    assert cliente.get("/api/v1/unidades?pagina=abc").status_code == 400


def test_detalhe_unidade_inclui_servicos_e_equipamentos(cliente):
    r = cliente.get("/api/v1/unidades/1")
    dados = r.get_json()["dados"]
    assert dados["servicos"][0]["nome"] == "Endodontia"
    assert dados["equipamentos"][0]["tipo"] == "Autoclave"
    assert cliente.get("/api/v1/unidades/999").status_code == 404


def test_servicos_equipamentos_e_indicadores(cliente):
    assert cliente.get("/api/v1/servicos?unidade_id=1").get_json()["meta"]["total"] == 1
    assert cliente.get("/api/v1/equipamentos?tipo=Autoclave").get_json()["meta"]["total"] == 1
    ind = cliente.get("/api/v1/indicadores").get_json()["dados"]
    assert ind["unidades"] == {"total": 2, "ativas": 1, "inativas": 1, "manutencao": 0}


def test_api_somente_leitura(cliente):
    for metodo in ("post", "put", "delete"):
        assert getattr(cliente, metodo)("/api/v1/unidades").status_code == 405


def test_openapi_e_swagger_publicos(app):
    c = app.test_client()
    spec = c.get("/api/v1/openapi.json").get_json()
    assert spec["openapi"].startswith("3.")
    assert set(spec["paths"]) == {"/unidades", "/unidades/{unidade_id}", "/servicos",
                                  "/equipamentos", "/indicadores"}
    assert c.get("/api/docs").status_code == 200
