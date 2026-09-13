"""
Testes da FASE 13B — Stage 2A (UX/UI das Unidades de Saúde).

Esta etapa é puramente visual — não altera rotas, models, RBAC,
validações ou o fluxo de aprovação. Os testes aqui confirmam que:

1. As 3 telas de Unidades continuam acessíveis e com o mesmo RBAC.
2. Os indicadores agregados (total/ativas/inativas/manutenção) batem
   com os dados reais já carregados — nenhuma consulta nova.
3. O fluxo de aprovação (Fase 7) continua exatamente igual.
4. Os estados vazios e mensagens continuam funcionando.
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import Alteracao, PerfilUsuario, SituacaoUnidade, Unidade, Usuario
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

        db.session.add_all(
            [
                Unidade(nome="UBS Alfa", cnes="1111111", tipo="UBS", cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA),
                Unidade(nome="UBS Beta", cnes="2222222", tipo="UBS", cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA),
                Unidade(nome="UBS Gama", cnes="3333333", tipo="UBS", cidade="Recife", uf="PE", situacao=SituacaoUnidade.INATIVA),
                Unidade(nome="UBS Delta", cnes="4444444", tipo="UBS", cidade="Recife", uf="PE", situacao=SituacaoUnidade.MANUTENCAO),
            ]
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


def _unidade_id(app, cnes):
    with app.app_context():
        return Unidade.query.filter_by(cnes=cnes).first().id


# ----------------------------------------------------------------
# As 3 telas continuam acessíveis
# ----------------------------------------------------------------

def test_lista_unidades_acessivel(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/unidades")
    assert resp.status_code == 200
    assert "Unidades de Saúde" in resp.get_data(as_text=True)


def test_detalhe_unidade_acessivel(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_id(app, "1111111")
    resp = client.get(f"/unidades/{unidade_id}")
    assert resp.status_code == 200
    assert "UBS Alfa" in resp.get_data(as_text=True)


def test_formulario_nova_unidade_acessivel(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/unidades/nova")
    assert resp.status_code == 200


def test_formulario_editar_unidade_acessivel(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_id(app, "1111111")
    resp = client.get(f"/unidades/{unidade_id}/editar")
    assert resp.status_code == 200


def test_unidade_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/unidades/999999")
    assert resp.status_code == 404


# ----------------------------------------------------------------
# Indicadores agregados batem com os dados reais (sem consulta nova)
# ----------------------------------------------------------------

def test_indicadores_da_lista_batem_com_dados_reais(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/unidades").get_data(as_text=True)
    assert ">4<" in html  # total
    assert ">2<" in html  # ativas
    assert ">1<" in html  # inativas e manutenção (ambas 1)


def test_lista_vazia_mostra_estado_vazio(client, app):
    with app.app_context():
        Unidade.query.delete()
        db.session.commit()

    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/unidades").get_data(as_text=True)
    assert "Nenhuma unidade cadastrada ainda." in html


# ----------------------------------------------------------------
# RBAC preservado para os 4 perfis (nada mudou)
# ----------------------------------------------------------------

@pytest.mark.parametrize("perfil", [
    PerfilUsuario.ADMINISTRADOR,
    PerfilUsuario.GESTAO_INFORMACAO,
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL,
    PerfilUsuario.GESTOR,
])
def test_todos_os_perfis_visualizam_a_lista(client, perfil):
    _login(client, perfil)
    resp = client.get("/unidades")
    assert resp.status_code == 200


def test_gestor_nao_ve_botao_nova_unidade(client):
    _login(client, PerfilUsuario.GESTOR)
    html = client.get("/unidades").get_data(as_text=True)
    assert "Nova unidade" not in html


def test_gestor_nao_ve_botao_editar_na_lista_nem_no_detalhe(client, app):
    _login(client, PerfilUsuario.GESTOR)
    html = client.get("/unidades").get_data(as_text=True)
    assert ">Editar<" not in html

    unidade_id = _unidade_id(app, "1111111")
    html_detalhe = client.get(f"/unidades/{unidade_id}").get_data(as_text=True)
    assert ">Editar<" not in html_detalhe
    assert "Alterar situação" not in html_detalhe


def test_gestor_recebe_403_ao_tentar_criar_ou_editar(client, app):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/unidades/nova")
    assert resp.status_code == 403

    unidade_id = _unidade_id(app, "1111111")
    resp = client.get(f"/unidades/{unidade_id}/editar")
    assert resp.status_code == 403

    resp = client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "INATIVA"})
    assert resp.status_code == 403


def test_responsavel_pode_criar_e_ver_botoes(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    html = client.get("/unidades").get_data(as_text=True)
    assert "Nova unidade" in html


# ----------------------------------------------------------------
# Fluxo de aprovação (Fase 7) permanece intacto
# ----------------------------------------------------------------

def test_criacao_continua_gerando_alteracao_pendente(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    resp = client.post(
        "/unidades/nova",
        data={"nome": "UBS Nova Visual", "cnes": "5555555", "tipo": "UBS", "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "aguardando aprovação" in resp.get_data(as_text=True)

    with app.app_context():
        assert Unidade.query.filter_by(cnes="5555555").first() is None
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        assert alteracao is not None
        assert alteracao.status.value == "PENDENTE"


def test_edicao_continua_gerando_alteracao_pendente(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    unidade_id = _unidade_id(app, "1111111")

    resp = client.post(
        f"/unidades/{unidade_id}/editar",
        data={"nome": "UBS Alfa Renomeada", "cnes": "1111111", "tipo": "UBS", "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "aguardando aprovação" in resp.get_data(as_text=True)

    with app.app_context():
        unidade = db.session.get(Unidade, unidade_id)
        assert unidade.nome == "UBS Alfa"  # nome original, ainda não aplicado
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="EDITAR", registro_id=unidade_id).first()
        assert alteracao is not None
        assert alteracao.status.value == "PENDENTE"
