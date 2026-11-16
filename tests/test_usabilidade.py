"""Testes das melhorias de usabilidade (textos, perfil por extenso, diff de edição, login)."""

import pytest

from app import create_app
from app.extensions import db
from app.models import Alteracao, PerfilUsuario, SituacaoUnidade, Unidade, Usuario
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"
EMAIL = "responsavel.ux@oris.com.br"


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        db.session.add(Usuario(
            nome="Maria Souza", email=EMAIL, senha_hash=gerar_hash_senha(SENHA),
            perfil=PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL, ativo=True,
        ))
        db.session.add(Unidade(
            nome="UBS Teste UX", cnes="9990002", tipo="UBS", cidade="Recife", uf="PE",
            situacao=SituacaoUnidade.ATIVA,
        ))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client):
    return client.post("/login", data={"email": EMAIL, "senha": SENHA}, follow_redirects=True)


def test_inicio_nao_mostra_texto_de_desenvolvimento(client):
    html = _login(client).get_data(as_text=True)
    assert "provisória" not in html
    assert "Fase 4" not in html
    assert "Olá, Maria" in html


def test_perfil_aparece_por_extenso(client):
    html = _login(client).get_data(as_text=True)
    assert "Responsável pela Saúde Bucal" in html
    assert "RESPONSAVEL_SAUDE_BUCAL" not in html


def test_edicao_so_do_nome_nao_lista_situacao_como_alterada(app, client):
    _login(client)
    with app.app_context():
        unidade_id = Unidade.query.first().id
    resposta = client.post(f"/unidades/{unidade_id}/editar", data={
        "nome": "UBS Teste UX Renomeada", "cnes": "9990002", "tipo": "UBS",
        "endereco": "", "bairro": "", "cidade": "Recife", "uf": "PE",
        "situacao": "ATIVA", "descricao_situacao": "",
    })
    assert resposta.status_code == 302
    with app.app_context():
        descricao = Alteracao.query.one().descricao
    assert "nome 'UBS Teste UX' → 'UBS Teste UX Renomeada'" in descricao
    assert "situacao" not in descricao


def test_erro_de_login_aparece_dentro_do_cartao(client):
    html = client.post("/login", data={"email": EMAIL, "senha": "errada"}, follow_redirects=True).get_data(as_text=True)
    cartao = html.split('class="oris-login-card"')[1]
    assert "Email ou senha inválidos." in cartao.split("<form")[0]
    assert html.count("Email ou senha inválidos.") == 1


def test_menu_usa_nomes_claros(client):
    html = _login(client).get_data(as_text=True)
    assert "Indicadores de manutenção" in html
    assert "Rotinas do banco" in html
    assert "Dashboard BD" not in html
