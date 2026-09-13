"""
Testes da FASE 13B — Stage 2B (UX/UI de Serviços e Equipamentos).

Esta etapa é puramente visual — não altera rotas, models, RBAC,
validações ou o fluxo de aprovação. Os testes aqui confirmam que:

1. As 8 telas (4 de Serviços + 4 de Equipamentos) continuam
   acessíveis, com o mesmo RBAC de sempre.
2. Os indicadores agregados (total/ativos/inativos) batem com os
   dados reais já carregados — nenhuma consulta nova.
3. O fluxo de aprovação (Fase 7) continua exatamente igual para as
   duas entidades.
4. A regra de compatibilidade Equipamento → Serviço → mesma Unidade
   continua intacta.
5. Os estados vazios continuam funcionando.
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Alteracao,
    Equipamento,
    PerfilUsuario,
    Servico,
    SituacaoAtivoInativo,
    SituacaoUnidade,
    Unidade,
    Usuario,
)
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

        unidade_a = Unidade(nome="UBS Alfa", cnes="1111111", tipo="UBS", cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA)
        unidade_b = Unidade(nome="UBS Beta", cnes="2222222", tipo="UBS", cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA)
        db.session.add_all([unidade_a, unidade_b])
        db.session.commit()

        servico_ativo = Servico(nome="Odontologia Geral", unidade_id=unidade_a.id, situacao=SituacaoAtivoInativo.ATIVO)
        servico_inativo = Servico(nome="Ortodontia", unidade_id=unidade_a.id, situacao=SituacaoAtivoInativo.INATIVO)
        servico_outra_unidade = Servico(nome="Endodontia", unidade_id=unidade_b.id, situacao=SituacaoAtivoInativo.ATIVO)
        db.session.add_all([servico_ativo, servico_inativo, servico_outra_unidade])
        db.session.commit()

        equipamento = Equipamento(
            nome="Cadeira Odontológica", tipo="Clínico", unidade_id=unidade_a.id,
            servico_id=servico_ativo.id, situacao=SituacaoAtivoInativo.ATIVO,
        )
        equipamento_sem_servico = Equipamento(
            nome="Compressor", tipo="Apoio", unidade_id=unidade_a.id,
            servico_id=None, situacao=SituacaoAtivoInativo.INATIVO,
        )
        db.session.add_all([equipamento, equipamento_sem_servico])
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil):
    return client.post("/login", data={"email": EMAILS[perfil], "senha": SENHA}, follow_redirects=True)


def _id(app, model, **filtros):
    with app.app_context():
        return model.query.filter_by(**filtros).first().id


# ----------------------------------------------------------------
# SERVIÇOS — telas acessíveis
# ----------------------------------------------------------------

def test_lista_servicos_acessivel(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/servicos")
    assert resp.status_code == 200
    assert "Serviços de Saúde Bucal" in resp.get_data(as_text=True)


def test_detalhe_servico_acessivel(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    servico_id = _id(app, Servico, nome="Odontologia Geral")
    resp = client.get(f"/servicos/{servico_id}")
    assert resp.status_code == 200
    assert "Odontologia Geral" in resp.get_data(as_text=True)


def test_formulario_novo_servico_acessivel(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/servicos/novo")
    assert resp.status_code == 200


def test_formulario_editar_servico_acessivel(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    servico_id = _id(app, Servico, nome="Odontologia Geral")
    resp = client.get(f"/servicos/{servico_id}/editar")
    assert resp.status_code == 200


def test_servico_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/servicos/999999")
    assert resp.status_code == 404


# ----------------------------------------------------------------
# EQUIPAMENTOS — telas acessíveis
# ----------------------------------------------------------------

def test_lista_equipamentos_acessivel(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/equipamentos")
    assert resp.status_code == 200
    assert "Equipamentos" in resp.get_data(as_text=True)


def test_detalhe_equipamento_acessivel(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    equipamento_id = _id(app, Equipamento, nome="Cadeira Odontológica")
    resp = client.get(f"/equipamentos/{equipamento_id}")
    assert resp.status_code == 200
    assert "Cadeira Odontológica" in resp.get_data(as_text=True)


def test_formulario_novo_equipamento_acessivel(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/equipamentos/novo")
    assert resp.status_code == 200


def test_formulario_editar_equipamento_acessivel(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    equipamento_id = _id(app, Equipamento, nome="Cadeira Odontológica")
    resp = client.get(f"/equipamentos/{equipamento_id}/editar")
    assert resp.status_code == 200


def test_equipamento_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/equipamentos/999999")
    assert resp.status_code == 404


# ----------------------------------------------------------------
# Indicadores agregados batem com dados reais (sem consulta nova)
# ----------------------------------------------------------------

def test_indicadores_de_servicos_batem_com_dados_reais(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/servicos").get_data(as_text=True)
    assert ">3<" in html  # total (2 na unidade A + 1 na unidade B)
    assert ">2<" in html  # ativos
    assert ">1<" in html  # inativos


def test_indicadores_de_equipamentos_batem_com_dados_reais(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/equipamentos").get_data(as_text=True)
    assert ">2<" in html  # total
    assert ">1<" in html  # ativos e inativos (ambos 1)


def test_lista_servicos_vazia_mostra_estado_vazio(client, app):
    with app.app_context():
        Equipamento.query.delete()
        Servico.query.delete()
        db.session.commit()

    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/servicos").get_data(as_text=True)
    assert "Nenhum serviço encontrado." in html


def test_lista_equipamentos_vazia_mostra_estado_vazio(client, app):
    with app.app_context():
        Equipamento.query.delete()
        db.session.commit()

    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/equipamentos").get_data(as_text=True)
    assert "Nenhum equipamento encontrado." in html


# ----------------------------------------------------------------
# Filtros continuam funcionando (mesma lógica, só visual)
# ----------------------------------------------------------------

def test_filtro_de_servicos_por_unidade_continua_funcionando(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_b_id = _id(app, Unidade, nome="UBS Beta")
    html = client.get(f"/servicos?unidade_id={unidade_b_id}").get_data(as_text=True)
    assert "Endodontia" in html
    assert "Odontologia Geral" not in html


def test_filtro_de_equipamentos_por_servico_continua_funcionando(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    servico_id = _id(app, Servico, nome="Odontologia Geral")
    html = client.get(f"/equipamentos?servico_id={servico_id}").get_data(as_text=True)
    assert "Cadeira Odontológica" in html
    assert "Compressor" not in html


# ----------------------------------------------------------------
# RBAC preservado para os 4 perfis (nada mudou)
# ----------------------------------------------------------------

@pytest.mark.parametrize("perfil", list(EMAILS.keys()))
def test_todos_os_perfis_visualizam_servicos_e_equipamentos(client, perfil):
    _login(client, perfil)
    assert client.get("/servicos").status_code == 200
    assert client.get("/equipamentos").status_code == 200


def test_gestor_nao_ve_botoes_de_alterar_servicos_e_equipamentos(client, app):
    _login(client, PerfilUsuario.GESTOR)

    html = client.get("/servicos").get_data(as_text=True)
    assert "Novo serviço" not in html
    assert ">Editar<" not in html

    html = client.get("/equipamentos").get_data(as_text=True)
    assert "Novo equipamento" not in html
    assert ">Editar<" not in html

    servico_id = _id(app, Servico, nome="Odontologia Geral")
    html_detalhe = client.get(f"/servicos/{servico_id}").get_data(as_text=True)
    assert "Alterar situação" not in html_detalhe

    equipamento_id = _id(app, Equipamento, nome="Cadeira Odontológica")
    html_detalhe = client.get(f"/equipamentos/{equipamento_id}").get_data(as_text=True)
    assert "Alterar situação" not in html_detalhe


def test_gestor_recebe_403_ao_tentar_criar_ou_editar_servico(client, app):
    _login(client, PerfilUsuario.GESTOR)
    assert client.get("/servicos/novo").status_code == 403

    servico_id = _id(app, Servico, nome="Odontologia Geral")
    assert client.get(f"/servicos/{servico_id}/editar").status_code == 403
    assert client.post(f"/servicos/{servico_id}/situacao", data={"situacao": "INATIVO"}).status_code == 403


def test_gestor_recebe_403_ao_tentar_criar_ou_editar_equipamento(client, app):
    _login(client, PerfilUsuario.GESTOR)
    assert client.get("/equipamentos/novo").status_code == 403

    equipamento_id = _id(app, Equipamento, nome="Cadeira Odontológica")
    assert client.get(f"/equipamentos/{equipamento_id}/editar").status_code == 403
    assert client.post(f"/equipamentos/{equipamento_id}/situacao", data={"situacao": "INATIVO"}).status_code == 403


def test_responsavel_pode_criar_servicos_e_equipamentos(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    assert "Novo serviço" in client.get("/servicos").get_data(as_text=True)
    assert "Novo equipamento" in client.get("/equipamentos").get_data(as_text=True)


# ----------------------------------------------------------------
# Fluxo de aprovação (Fase 7) permanece intacto para as 2 entidades
# ----------------------------------------------------------------

def test_criacao_de_servico_continua_gerando_alteracao_pendente(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    unidade_id = _id(app, Unidade, nome="UBS Alfa")

    resp = client.post(
        "/servicos/novo",
        data={"nome": "Novo Serviço Visual", "unidade_id": unidade_id, "situacao": "ATIVO"},
        follow_redirects=True,
    )
    assert "aguardando aprovação" in resp.get_data(as_text=True)

    with app.app_context():
        assert Servico.query.filter_by(nome="Novo Serviço Visual").first() is None
        alteracao = Alteracao.query.filter_by(tabela="servicos", operacao="CRIAR").first()
        assert alteracao is not None
        assert alteracao.status.value == "PENDENTE"


def test_criacao_de_equipamento_continua_gerando_alteracao_pendente(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    unidade_id = _id(app, Unidade, nome="UBS Alfa")

    resp = client.post(
        "/equipamentos/novo",
        data={"nome": "Novo Equip Visual", "tipo": "Clínico", "unidade_id": unidade_id, "servico_id": "", "situacao": "ATIVO"},
        follow_redirects=True,
    )
    assert "aguardando aprovação" in resp.get_data(as_text=True)

    with app.app_context():
        assert Equipamento.query.filter_by(nome="Novo Equip Visual").first() is None
        alteracao = Alteracao.query.filter_by(tabela="equipamentos", operacao="CRIAR").first()
        assert alteracao is not None
        assert alteracao.status.value == "PENDENTE"


def test_fluxo_completo_de_aprovacao_de_servico(client, app):
    """Solicitante não aprova a própria alteração; outro usuário aprova; aplica; audita."""
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    unidade_id = _id(app, Unidade, nome="UBS Alfa")
    client.post("/servicos/novo", data={"nome": "Servico Fluxo", "unidade_id": unidade_id, "situacao": "ATIVO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="servicos", operacao="CRIAR", status="PENDENTE").first()
        solicitante = Usuario.query.filter_by(email=EMAILS[PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL]).first()
        aprovador = Usuario.query.filter_by(email=EMAILS[PerfilUsuario.ADMINISTRADOR]).first()

        ok, _ = aprovar_alteracao(alteracao, solicitante)
        assert ok is False  # não pode aprovar a própria

        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True

        assert Servico.query.filter_by(nome="Servico Fluxo").first() is not None

        from app.models import Auditoria

        assert Auditoria.query.filter_by(acao="CRIAR", tabela="servicos").first() is not None
        assert Auditoria.query.filter_by(acao="APROVAR_ALTERACAO").first() is not None


# ----------------------------------------------------------------
# Regra de compatibilidade Equipamento -> Serviço -> mesma Unidade
# ----------------------------------------------------------------

def test_equipamento_com_servico_de_outra_unidade_e_bloqueado(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_a_id = _id(app, Unidade, nome="UBS Alfa")
    servico_outra_unidade_id = _id(app, Servico, nome="Endodontia")  # pertence à UBS Beta

    resp = client.post(
        "/equipamentos/novo",
        data={
            "nome": "Equip Incompatível", "tipo": "Clínico",
            "unidade_id": unidade_a_id, "servico_id": servico_outra_unidade_id, "situacao": "ATIVO",
        },
        follow_redirects=True,
    )
    assert "pertence a outra unidade" in resp.get_data(as_text=True)

    with app.app_context():
        assert Equipamento.query.filter_by(nome="Equip Incompatível").first() is None
