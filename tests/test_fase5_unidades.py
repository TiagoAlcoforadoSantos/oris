"""
Testes da FASE 5 — CRUD de Unidades.

Roda contra SQLite em memória (TestingConfig), reaproveitando o
padrão de fixtures das fases anteriores. Cria um usuário para cada
perfil e uma unidade de exemplo.

ATUALIZADO NA FASE 7: criar/editar/alterar situação de uma Unidade
não grava mais direto no banco — registra uma Alteracao PENDENTE que
só é aplicada quando aprovada (ver tests/test_fase7_alteracoes.py
para a cobertura completa do fluxo de aprovação). Os testes desta
fase que antes verificavam a escrita imediata (#4, #5, #6 e o cenário
de edição usado em #12) foram ajustados para refletir esse novo
comportamento — continuam confirmando exatamente a mesma regra de
autorização (quem pode ou não solicitar a operação), só que a
verificação final passa a ser "uma Alteracao PENDENTE foi criada"
(e, quando faz sentido, "e a aprovação realmente aplica a mudança")
em vez de "o registro foi alterado na hora".
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import Alteracao, PerfilUsuario, SituacaoUnidade, Unidade, Usuario
from app.services.alteracoes_service import aprovar_alteracao
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

        unidade_exemplo = Unidade(
            nome="UBS Bairro Novo",
            cnes="1234567",
            tipo="UBS",
            endereco="Rua Teste, 100",
            bairro="Bairro Novo",
            cidade="Recife",
            uf="PE",
            situacao=SituacaoUnidade.ATIVA,
        )
        db.session.add(unidade_exemplo)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil):
    return client.post(
        "/login",
        data={"email": EMAILS[perfil], "senha": SENHA},
        follow_redirects=True,
    )


def _unidade_exemplo_id(app):
    with app.app_context():
        return Unidade.query.filter_by(cnes="1234567").first().id


def _usuario(app, perfil):
    with app.app_context():
        return Usuario.query.filter_by(email=EMAILS[perfil]).first()


DADOS_UNIDADE_NOVA = {
    "nome": "UBS Vila Feliz",
    "cnes": "7654321",
    "tipo": "UBS",
    "endereco": "Av. Central, 500",
    "bairro": "Vila Feliz",
    "cidade": "Recife",
    "uf": "PE",
    "situacao": "ATIVA",
}


# ----------------------------------------------------------------
# 1. Usuário não autenticado não acessa /unidades
# ----------------------------------------------------------------

def test_usuario_nao_autenticado_nao_acessa_unidades(client):
    resp = client.get("/unidades", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# 2. Usuário autorizado consegue listar unidades
# ----------------------------------------------------------------

def test_usuario_autenticado_lista_unidades(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/unidades")
    assert resp.status_code == 200
    assert "UBS Bairro Novo" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 3. Usuário autorizado consegue visualizar unidade
# ----------------------------------------------------------------

def test_usuario_autenticado_visualiza_unidade(client, app):
    _login(client, PerfilUsuario.GESTOR)
    unidade_id = _unidade_exemplo_id(app)

    resp = client.get(f"/unidades/{unidade_id}")
    assert resp.status_code == 200
    assert "UBS Bairro Novo" in resp.get_data(as_text=True)
    assert "1234567" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 4. Usuário autorizado consegue SOLICITAR a criação de uma unidade
#    (Fase 7: fica PENDENTE; só é criada de fato quando aprovada —
#    ver test_fase7_alteracoes.py para o fluxo de aprovação completo)
# ----------------------------------------------------------------

def test_administrador_solicita_criacao_de_unidade(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA, follow_redirects=True)
    assert resp.status_code == 200
    assert "aguardando aprovação" in resp.get_data(as_text=True)

    with app.app_context():
        # A unidade ainda NÃO existe — só a solicitação (Alteracao PENDENTE)
        assert Unidade.query.filter_by(cnes="7654321").first() is None

        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        assert alteracao is not None
        assert alteracao.status.value == "PENDENTE"
        assert alteracao.registro_id is None


def test_responsavel_saude_bucal_solicita_criacao_de_unidade(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    resp = client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA, follow_redirects=True)
    assert resp.status_code == 200
    assert "aguardando aprovação" in resp.get_data(as_text=True)


def test_aprovar_solicitacao_de_criacao_efetiva_a_unidade(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True

        criada = Unidade.query.filter_by(cnes="7654321").first()
        assert criada is not None
        assert criada.nome == "UBS Vila Feliz"
        assert criada.uf == "PE"


# ----------------------------------------------------------------
# 5. Usuário autorizado consegue SOLICITAR a edição de uma unidade
# ----------------------------------------------------------------

def test_administrador_solicita_edicao_de_unidade(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_exemplo_id(app)

    dados_editados = {
        "nome": "UBS Bairro Novo (Reformada)",
        "cnes": "1234567",
        "tipo": "UBS",
        "endereco": "Rua Teste, 100",
        "bairro": "Bairro Novo",
        "cidade": "Recife",
        "uf": "PE",
        "situacao": "ATIVA",
    }
    resp = client.post(f"/unidades/{unidade_id}/editar", data=dados_editados, follow_redirects=True)
    assert resp.status_code == 200
    assert "aguardando aprovação" in resp.get_data(as_text=True)

    with app.app_context():
        # O nome ainda NÃO mudou — a edição está pendente de aprovação
        unidade = db.session.get(Unidade, unidade_id)
        assert unidade.nome == "UBS Bairro Novo"

        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="EDITAR").first()
        assert alteracao is not None
        assert alteracao.registro_id == unidade_id


def test_aprovar_solicitacao_de_edicao_aplica_a_mudanca(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_exemplo_id(app)

    dados_editados = {
        "nome": "UBS Bairro Novo (Reformada)",
        "cnes": "1234567",
        "tipo": "UBS",
        "endereco": "Rua Teste, 100",
        "bairro": "Bairro Novo",
        "cidade": "Recife",
        "uf": "PE",
        "situacao": "ATIVA",
    }
    client.post(f"/unidades/{unidade_id}/editar", data=dados_editados)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="EDITAR").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True

        editada = db.session.get(Unidade, unidade_id)
        assert editada.nome == "UBS Bairro Novo (Reformada)"


# ----------------------------------------------------------------
# 6. Usuário autorizado consegue SOLICITAR alteração de situação
# ----------------------------------------------------------------

def test_administrador_solicita_alteracao_de_situacao(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_exemplo_id(app)

    resp = client.post(
        f"/unidades/{unidade_id}/situacao",
        data={"situacao": "MANUTENCAO"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "aguardando aprovação" in resp.get_data(as_text=True)

    with app.app_context():
        unidade = db.session.get(Unidade, unidade_id)
        assert unidade.situacao == SituacaoUnidade.ATIVA  # ainda não mudou

        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="ALTERAR_SITUACAO").first()
        assert alteracao is not None


def test_aprovar_alteracao_de_situacao_aplica_a_mudanca(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_exemplo_id(app)

    client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "MANUTENCAO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="ALTERAR_SITUACAO").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True

        unidade = db.session.get(Unidade, unidade_id)
        assert unidade.situacao == SituacaoUnidade.MANUTENCAO


# ----------------------------------------------------------------
# 7. GESTOR consegue consultar unidades
# ----------------------------------------------------------------

def test_gestor_consulta_unidades(client, app):
    _login(client, PerfilUsuario.GESTOR)
    unidade_id = _unidade_exemplo_id(app)

    resp_lista = client.get("/unidades")
    resp_detalhe = client.get(f"/unidades/{unidade_id}")

    assert resp_lista.status_code == 200
    assert resp_detalhe.status_code == 200


# ----------------------------------------------------------------
# 8. GESTOR não consegue criar unidade
# ----------------------------------------------------------------

def test_gestor_nao_cria_unidade(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/unidades/nova")
    assert resp.status_code == 403

    resp = client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 9. GESTOR não consegue editar unidade
# ----------------------------------------------------------------

def test_gestor_nao_edita_unidade(client, app):
    _login(client, PerfilUsuario.GESTOR)
    unidade_id = _unidade_exemplo_id(app)

    resp = client.get(f"/unidades/{unidade_id}/editar")
    assert resp.status_code == 403

    resp = client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "INATIVA"})
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 10. Usuário sem permissão recebe 403 ao tentar operação protegida
#     (mesmo teste do GESTOR acima cobre isso; aqui garantimos a
#     página de acesso negado é exibida)
# ----------------------------------------------------------------

def test_pagina_acesso_negado_ao_tentar_criar_unidade(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/unidades/nova")
    assert resp.status_code == 403
    assert "Acesso negado" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 11. Cadastro sem campos obrigatórios falha
# ----------------------------------------------------------------

def test_cadastro_sem_nome_falha(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    dados_invalidos = dict(DADOS_UNIDADE_NOVA)
    dados_invalidos["nome"] = ""

    resp = client.post("/unidades/nova", data=dados_invalidos, follow_redirects=True)
    assert resp.status_code == 200
    assert "Informe o nome da unidade." in resp.get_data(as_text=True)

    with app.app_context():
        assert Unidade.query.filter_by(cnes="7654321").first() is None
        assert Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first() is None


def test_cadastro_sem_cnes_falha(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    dados_invalidos = dict(DADOS_UNIDADE_NOVA)
    dados_invalidos["cnes"] = ""

    resp = client.post("/unidades/nova", data=dados_invalidos, follow_redirects=True)
    assert resp.status_code == 200
    assert "Informe o código CNES." in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 12. CNES duplicado é rejeitado
# ----------------------------------------------------------------

def test_cnes_duplicado_e_rejeitado_no_cadastro(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    dados_duplicados = dict(DADOS_UNIDADE_NOVA)
    dados_duplicados["cnes"] = "1234567"  # já usado pela unidade de exemplo

    resp = client.post("/unidades/nova", data=dados_duplicados, follow_redirects=True)
    assert resp.status_code == 200
    assert "Já existe uma unidade cadastrada com o CNES" in resp.get_data(as_text=True)

    with app.app_context():
        # Continua existindo só uma unidade com esse CNES, e nenhuma
        # solicitação chegou a ser registrada.
        assert Unidade.query.filter_by(cnes="1234567").count() == 1
        assert Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first() is None


def test_cnes_duplicado_e_rejeitado_na_edicao(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    # Cria uma segunda unidade diretamente no banco (o cadastro via
    # rota agora passa pelo fluxo de aprovação — ver testes acima —
    # então, para testar a edição, criamos a unidade já existente
    # diretamente, como o setup do teste faz com a unidade de exemplo).
    with app.app_context():
        segunda_unidade = Unidade(
            nome="UBS Vila Feliz",
            cnes="7654321",
            tipo="UBS",
            cidade="Recife",
            uf="PE",
            situacao=SituacaoUnidade.ATIVA,
        )
        db.session.add(segunda_unidade)
        db.session.commit()
        segunda_unidade_id = segunda_unidade.id

    dados_editados = dict(DADOS_UNIDADE_NOVA)
    dados_editados["cnes"] = "1234567"  # CNES da primeira unidade

    resp = client.post(f"/unidades/{segunda_unidade_id}/editar", data=dados_editados, follow_redirects=True)
    assert resp.status_code == 200
    assert "Já existe outra unidade cadastrada com o CNES" in resp.get_data(as_text=True)

    with app.app_context():
        assert Alteracao.query.filter_by(tabela="unidades", operacao="EDITAR").first() is None


# ----------------------------------------------------------------
# 13. Unidade inexistente retorna 404 / tratamento amigável
# ----------------------------------------------------------------

def test_unidade_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.get("/unidades/99999")
    assert resp.status_code == 404
    assert "não encontrado" in resp.get_data(as_text=True).lower() or "Não encontrado" in resp.get_data(as_text=True)


def test_editar_unidade_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.get("/unidades/99999/editar")
    assert resp.status_code == 404


# ----------------------------------------------------------------
# 14. Situação inválida é rejeitada
# ----------------------------------------------------------------

def test_situacao_invalida_e_rejeitada_no_cadastro(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    dados_invalidos = dict(DADOS_UNIDADE_NOVA)
    dados_invalidos["situacao"] = "SITUACAO_QUE_NAO_EXISTE"

    resp = client.post("/unidades/nova", data=dados_invalidos, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert Unidade.query.filter_by(cnes="7654321").first() is None
        assert Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first() is None


def test_situacao_invalida_e_rejeitada_ao_alterar(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_exemplo_id(app)

    resp = client.post(
        f"/unidades/{unidade_id}/situacao",
        data={"situacao": "SITUACAO_QUE_NAO_EXISTE"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Situação inválida." in resp.get_data(as_text=True)

    with app.app_context():
        unidade = db.session.get(Unidade, unidade_id)
        assert unidade.situacao == SituacaoUnidade.ATIVA  # não mudou
        assert Alteracao.query.filter_by(tabela="unidades", operacao="ALTERAR_SITUACAO").first() is None
