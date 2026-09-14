"""
Testes da FASE 13B — Stage 4 (UX/UI da tela de Auditoria).

Esta etapa é puramente visual — não altera rotas, models, RBAC ou a
lógica que gera os registros de auditoria. Os testes aqui confirmam
que:

1. A listagem e o detalhe continuam acessíveis apenas para
   ADMINISTRADOR e GESTAO_INFORMACAO — os demais perfis continuam
   recebendo 403 (RBAC inalterado).
2. Auditoria continua sendo somente leitura — nenhuma rota de
   edição/exclusão foi criada.
3. Os filtros existentes (usuário, ação, entidade, data) continuam
   funcionando exatamente como antes.
4. A tela diferencia "nenhum registro" de "nenhum resultado para o
   filtro".
5. Antes/Depois são exibidos corretamente quando existem, sem
   inventar nenhum dado (reaproveitando os filtros já criados na
   Stage 3 para Alteracao.dados_novos).
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import PerfilUsuario, Usuario
from app.services.auditoria_service import registrar_auditoria
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
        db.session.commit()

        admin = Usuario.query.filter_by(email=EMAILS[PerfilUsuario.ADMINISTRADOR]).first()
        registrar_auditoria(admin, "LOGIN")
        registrar_auditoria(admin, "CRIAR", tabela="unidades", registro_id=1, descricao="Criação da Unidade Teste")
        registrar_auditoria(
            admin, "EDITAR", tabela="unidades", registro_id=1, descricao="Edição da Unidade Teste",
            valor_anterior={"nome": "Unidade Teste"}, valor_novo={"nome": "Unidade Renomeada"},
        )
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil):
    return client.post("/login", data={"email": EMAILS[perfil], "senha": SENHA}, follow_redirects=True)


def _ultimo_registro_id(app):
    from app.models import Auditoria

    with app.app_context():
        return Auditoria.query.order_by(Auditoria.id.desc()).first().id


# ----------------------------------------------------------------
# RBAC preservado (nada mudou)
# ----------------------------------------------------------------

def test_administrador_acessa_lista_e_detalhe(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    assert client.get("/auditoria").status_code == 200
    assert client.get(f"/auditoria/{_ultimo_registro_id(app)}").status_code == 200


def test_gestao_informacao_acessa_lista_e_detalhe(client, app):
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    assert client.get("/auditoria").status_code == 200
    assert client.get(f"/auditoria/{_ultimo_registro_id(app)}").status_code == 200


def test_responsavel_recebe_403(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    assert client.get("/auditoria").status_code == 403
    assert client.get(f"/auditoria/{_ultimo_registro_id(app)}").status_code == 403


def test_gestor_recebe_403(client, app):
    _login(client, PerfilUsuario.GESTOR)
    assert client.get("/auditoria").status_code == 403
    assert client.get(f"/auditoria/{_ultimo_registro_id(app)}").status_code == 403


def test_usuario_nao_autenticado_nao_acessa(client):
    resp = client.get("/auditoria", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# Somente leitura — nenhuma rota de edição/exclusão
# ----------------------------------------------------------------

def test_auditoria_continua_somente_leitura(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    registro_id = _ultimo_registro_id(app)

    assert client.post(f"/auditoria/{registro_id}/editar").status_code == 404
    assert client.post(f"/auditoria/{registro_id}/excluir").status_code == 404
    resp = client.delete(f"/auditoria/{registro_id}")
    assert resp.status_code in (404, 405)

    with app.app_context():
        from app.models import Auditoria

        assert db.session.get(Auditoria, registro_id) is not None


def test_pagina_de_auditoria_nao_mostra_nenhuma_acao_de_edicao_ou_exclusao(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    registro_id = _ultimo_registro_id(app)
    html = client.get(f"/auditoria/{registro_id}").get_data(as_text=True)
    assert "Editar" not in html
    assert "Excluir" not in html
    assert 'method="POST"' not in html  # nenhum formulário de mutação nesta tela


def test_lista_mostra_aviso_de_somente_leitura(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/auditoria").get_data(as_text=True)
    assert "Somente leitura" in html


# ----------------------------------------------------------------
# Filtros existentes continuam funcionando (mesma lógica)
# ----------------------------------------------------------------

def test_filtro_por_acao_continua_funcionando(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/auditoria?acao=LOGIN").get_data(as_text=True)
    assert "LOGIN" in html
    assert "Criação da Unidade Teste" not in html


def test_filtro_por_tabela_continua_funcionando(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/auditoria?tabela=unidades").get_data(as_text=True)
    assert "Criação da Unidade Teste" in html


def test_filtro_por_usuario_continua_funcionando(client, app):
    with app.app_context():
        admin = Usuario.query.filter_by(email=EMAILS[PerfilUsuario.ADMINISTRADOR]).first()
        admin_id = admin.id
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get(f"/auditoria?usuario_id={admin_id}").get_data(as_text=True)
    assert "Usuário ADMINISTRADOR" in html


# ----------------------------------------------------------------
# Estados vazios diferenciados
# ----------------------------------------------------------------

def test_filtro_sem_resultado_mostra_mensagem_especifica(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/auditoria?acao=ACAO_QUE_NAO_EXISTE").get_data(as_text=True)
    assert "Nenhum registro de auditoria encontrado." in html
    assert "ajustar os critérios" in html


# ----------------------------------------------------------------
# Antes/Depois — sem inventar dados
# ----------------------------------------------------------------

def test_detalhe_mostra_antes_e_depois_quando_existem(client, app):
    from app.models import Auditoria

    _login(client, PerfilUsuario.ADMINISTRADOR)
    with app.app_context():
        registro_id = Auditoria.query.filter_by(acao="EDITAR").first().id
    html = client.get(f"/auditoria/{registro_id}").get_data(as_text=True)
    assert "Antes" in html
    assert "Depois" in html
    assert "Unidade Teste" in html
    assert "Unidade Renomeada" in html


def test_detalhe_sem_valores_nao_mostra_secao_antes_depois(client, app):
    from app.models import Auditoria

    with app.app_context():
        registro_login = Auditoria.query.filter_by(acao="LOGIN").first()
        registro_id = registro_login.id

    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get(f"/auditoria/{registro_id}").get_data(as_text=True)
    assert "oris-section-label\">Antes" not in html
    assert "oris-section-label\">Depois" not in html


def test_senha_e_hash_nunca_aparecem_na_auditoria_redesenhada(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/auditoria")
    assert SENHA not in resp.get_data(as_text=True)
    assert "$2b$" not in resp.get_data(as_text=True)
