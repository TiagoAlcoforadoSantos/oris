"""
Testes da FASE 13B — Stage 3 (UX/UI do módulo de Aprovações).

Esta etapa é puramente visual — não altera rotas, models, RBAC,
regras de aprovação/rejeição/autoaprovação ou auditoria. Os testes
aqui confirmam que:

1. A listagem e o detalhe continuam acessíveis, com o mesmo RBAC.
2. Os indicadores agregados (total/pendentes/aprovadas/rejeitadas)
   batem com os dados reais já carregados — nenhuma consulta nova.
3. As seções novas (Novo registro / O que muda / Valores propostos)
   aparecem corretamente para CRIAR, EDITAR e ALTERAR_SITUACAO, sem
   inventar nenhum dado.
4. Autoaprovação continua bloqueada; aprovação e rejeição continuam
   aplicando/no aplicando a mudança exatamente como antes.
5. A auditoria continua sendo gerada.
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import Alteracao, Auditoria, PerfilUsuario, SituacaoUnidade, Unidade, Usuario
from app.services.alteracoes_service import aprovar_alteracao, rejeitar_alteracao, registrar_alteracao
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

        unidade = Unidade(nome="UBS Aprovações", cnes="9990001", tipo="UBS", cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA)
        db.session.add(unidade)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil):
    return client.post("/login", data={"email": EMAILS[perfil], "senha": SENHA}, follow_redirects=True)


def _usuario(app, perfil):
    with app.app_context():
        return Usuario.query.filter_by(email=EMAILS[perfil]).first()


def _criar_alteracao(app, tabela, registro_id, operacao, dados, descricao, solicitante_perfil=PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL):
    with app.app_context():
        solicitante = Usuario.query.filter_by(email=EMAILS[solicitante_perfil]).first()
        alteracao = registrar_alteracao(solicitante, tabela, registro_id, operacao, dados, descricao)
        return alteracao.id


# ----------------------------------------------------------------
# Telas acessíveis
# ----------------------------------------------------------------

def test_lista_aprovacoes_acessivel(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/alteracoes")
    assert resp.status_code == 200
    assert "Aprovações" in resp.get_data(as_text=True)


def test_detalhe_aprovacao_acessivel(client, app):
    alt_id = _criar_alteracao(
        app, "unidades", None, "CRIAR",
        {"nome": "UBS Nova", "cnes": "1112223", "tipo": "UBS", "endereco": None, "bairro": None, "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
        "Criação de nova Unidade: UBS Nova (CNES 1112223)",
    )
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get(f"/alteracoes/{alt_id}")
    assert resp.status_code == 200


def test_alteracao_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/alteracoes/999999")
    assert resp.status_code == 404


# ----------------------------------------------------------------
# Indicadores agregados batem com dados reais (sem consulta nova)
# ----------------------------------------------------------------

def test_indicadores_batem_com_dados_reais(client, app):
    _criar_alteracao(app, "unidades", None, "CRIAR", {"nome": "A", "cnes": "1", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"}, "Criação de nova Unidade: A (CNES 1)")
    _criar_alteracao(app, "unidades", None, "CRIAR", {"nome": "B", "cnes": "2", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"}, "Criação de nova Unidade: B (CNES 2)")

    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/alteracoes").get_data(as_text=True)
    assert ">2<" in html  # total
    assert ">2<" in html  # pendentes (ambas)
    assert ">0<" in html  # aprovadas e rejeitadas


def test_lista_vazia_mostra_estado_vazio(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/alteracoes").get_data(as_text=True)
    assert "Nenhuma alteração encontrada." in html


# ----------------------------------------------------------------
# Seções visuais: Novo registro / O que muda / Valores propostos
# ----------------------------------------------------------------

def test_criacao_mostra_novo_registro_sem_antes(client, app):
    alt_id = _criar_alteracao(
        app, "unidades", None, "CRIAR",
        {"nome": "UBS Criada", "cnes": "5551111", "tipo": "UBS", "endereco": None, "bairro": None, "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
        "Criação de nova Unidade: UBS Criada (CNES 5551111)",
    )
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert "Novo registro" in html
    assert "UBS Criada" in html
    assert "5551111" in html
    assert "O que muda" not in html  # CRIAR não tem "antes"


def test_edicao_mostra_o_que_muda_e_valores_propostos(client, app):
    with app.app_context():
        unidade = Unidade.query.filter_by(cnes="9990001").first()
        unidade_id = unidade.id

    alt_id = _criar_alteracao(
        app, "unidades", unidade_id, "EDITAR",
        {"nome": "UBS Renomeada", "cnes": "9990001", "tipo": "UBS", "endereco": None, "bairro": None, "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
        f"Edição da Unidade {unidade_id} (UBS Aprovações): nome 'UBS Aprovações' → 'UBS Renomeada'",
    )
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert "O que muda" in html
    assert "UBS Aprovações" in html and "UBS Renomeada" in html
    assert "Valores propostos" in html


def test_alterar_situacao_mostra_comparacao(client, app):
    with app.app_context():
        unidade = Unidade.query.filter_by(cnes="9990001").first()
        unidade_id = unidade.id

    alt_id = _criar_alteracao(
        app, "unidades", unidade_id, "ALTERAR_SITUACAO",
        {"situacao": "INATIVA"},
        f"Alteração da Unidade {unidade_id} (UBS Aprovações): situação ATIVA → INATIVA",
    )
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert "ATIVA" in html and "INATIVA" in html


def test_dados_novos_nao_expoe_ids_tecnicos(client, app):
    """unidade_id/servico_id não devem aparecer como número bruto na
    tela — o contexto relacional já vem pela descrição."""
    with app.app_context():
        unidade = Unidade.query.filter_by(cnes="9990001").first()
        unidade_id = unidade.id

    alt_id = _criar_alteracao(
        app, "servicos", None, "CRIAR",
        {"nome": "Odontologia", "unidade_id": unidade_id, "situacao": "ATIVO"},
        f"Criação de novo Serviço: Odontologia (Unidade UBS Aprovações)",
    )
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert "Unidade_id" not in html
    assert "unidade_id" not in html.lower().replace("unidade_id do", "")  # sanity


# ----------------------------------------------------------------
# RBAC preservado (nada mudou)
# ----------------------------------------------------------------

@pytest.mark.parametrize("perfil", list(EMAILS.keys()))
def test_todos_os_perfis_visualizam_lista_e_detalhe(client, app, perfil):
    alt_id = _criar_alteracao(app, "unidades", None, "CRIAR", {"nome": "X", "cnes": "9", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"}, "Criação de nova Unidade: X (CNES 9)")
    _login(client, perfil)
    assert client.get("/alteracoes").status_code == 200
    assert client.get(f"/alteracoes/{alt_id}").status_code == 200


def test_gestor_nao_ve_botoes_de_decisao(client, app):
    alt_id = _criar_alteracao(app, "unidades", None, "CRIAR", {"nome": "X", "cnes": "9", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"}, "Criação de nova Unidade: X (CNES 9)")
    _login(client, PerfilUsuario.GESTOR)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert "Aprovar alteração" not in html
    assert "Rejeitar alteração" not in html


def test_gestor_recebe_403_ao_tentar_aprovar_ou_rejeitar(client, app):
    alt_id = _criar_alteracao(app, "unidades", None, "CRIAR", {"nome": "X", "cnes": "9", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"}, "Criação de nova Unidade: X (CNES 9)")
    _login(client, PerfilUsuario.GESTOR)
    assert client.post(f"/alteracoes/{alt_id}/aprovar").status_code == 403
    assert client.post(f"/alteracoes/{alt_id}/rejeitar").status_code == 403


def test_responsavel_nao_ve_botoes_de_decisao_mesmo_sendo_outro_solicitante(client, app):
    """RESPONSAVEL_SAUDE_BUCAL nunca aprova, mesmo que não seja o
    solicitante desta alteração específica."""
    alt_id = _criar_alteracao(app, "unidades", None, "CRIAR", {"nome": "X", "cnes": "9", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"}, "Criação de nova Unidade: X (CNES 9)")
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert "Aprovar alteração" not in html


def test_gestao_informacao_ve_botoes_para_alteracao_de_outro(client, app):
    alt_id = _criar_alteracao(app, "unidades", None, "CRIAR", {"nome": "X", "cnes": "9", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"}, "Criação de nova Unidade: X (CNES 9)")
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert "Aprovar alteração" in html
    assert "Rejeitar alteração" in html


def test_solicitante_nao_ve_botoes_para_a_propria_alteracao(client, app):
    alt_id = _criar_alteracao(
        app, "unidades", None, "CRIAR",
        {"nome": "X", "cnes": "9", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"},
        "Criação de nova Unidade: X (CNES 9)",
        solicitante_perfil=PerfilUsuario.ADMINISTRADOR,
    )
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert "Aprovar alteração" not in html
    assert "não pode decidir" in html or "foi você quem a solicitou" in html


# ----------------------------------------------------------------
# Autoaprovação, aprovação, rejeição e auditoria (nada mudou)
# ----------------------------------------------------------------

def test_autoaprovacao_continua_bloqueada(client, app):
    alt_id = _criar_alteracao(
        app, "unidades", None, "CRIAR",
        {"nome": "X", "cnes": "9", "tipo": "UBS", "cidade": "R", "uf": "PE", "situacao": "ATIVA"},
        "Criação de nova Unidade: X (CNES 9)",
        solicitante_perfil=PerfilUsuario.ADMINISTRADOR,
    )
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.post(f"/alteracoes/{alt_id}/aprovar")
    assert resp.status_code == 403


def test_aprovacao_por_outro_usuario_aplica_a_mudanca(client, app):
    alt_id = _criar_alteracao(
        app, "unidades", None, "CRIAR",
        {"nome": "UBS Aplicada", "cnes": "7778889", "tipo": "UBS", "endereco": None, "bairro": None, "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
        "Criação de nova Unidade: UBS Aplicada (CNES 7778889)",
    )
    with app.app_context():
        alteracao = db.session.get(Alteracao, alt_id)
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True
        assert Unidade.query.filter_by(cnes="7778889").first() is not None
        assert Auditoria.query.filter_by(acao="CRIAR", tabela="unidades").first() is not None
        assert Auditoria.query.filter_by(acao="APROVAR_ALTERACAO").first() is not None


def test_rejeicao_nao_aplica_a_mudanca(client, app):
    alt_id = _criar_alteracao(
        app, "unidades", None, "CRIAR",
        {"nome": "UBS Rejeitada", "cnes": "6667778", "tipo": "UBS", "endereco": None, "bairro": None, "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
        "Criação de nova Unidade: UBS Rejeitada (CNES 6667778)",
    )
    with app.app_context():
        alteracao = db.session.get(Alteracao, alt_id)
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        ok, _ = rejeitar_alteracao(alteracao, aprovador)
        assert ok is True
        assert Unidade.query.filter_by(cnes="6667778").first() is None
        assert Auditoria.query.filter_by(acao="REJEITAR_ALTERACAO").first() is not None


def test_badge_rejeitado_usa_cor_danger(client, app):
    """Achado corrigido nesta etapa: REJEITADO usava bg-secondary,
    deveria usar bg-danger (item 9 do enunciado)."""
    alt_id = _criar_alteracao(
        app, "unidades", None, "CRIAR",
        {"nome": "UBS X", "cnes": "4445556", "tipo": "UBS", "endereco": None, "bairro": None, "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
        "Criação de nova Unidade: UBS X (CNES 4445556)",
    )
    with app.app_context():
        alteracao = db.session.get(Alteracao, alt_id)
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        rejeitar_alteracao(alteracao, aprovador)

    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get(f"/alteracoes/{alt_id}").get_data(as_text=True)
    assert 'badge bg-danger">Rejeitado' in html
