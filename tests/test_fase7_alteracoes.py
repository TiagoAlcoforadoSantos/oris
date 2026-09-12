"""
Testes da FASE 7 — fluxo de alterações + aprovação.

Roda contra SQLite em memória (TestingConfig). Cria um usuário de
cada perfil e uma unidade de exemplo, para exercitar o fluxo de
ponta a ponta: solicitar → PENDENTE → aprovar/rejeitar.
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Alteracao,
    Equipamento,
    PerfilUsuario,
    Servico,
    SituacaoUnidade,
    StatusAlteracao,
    Unidade,
    Usuario,
)
from app.services.alteracoes_service import aprovar_alteracao, rejeitar_alteracao
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}

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

        unidade = Unidade(
            nome="UBS Bairro Novo",
            cnes="1234567",
            tipo="UBS",
            cidade="Recife",
            uf="PE",
            situacao=SituacaoUnidade.ATIVA,
        )
        db.session.add(unidade)
        db.session.commit()

        servico = Servico(nome="Odontologia Geral", unidade_id=unidade.id, situacao="ATIVO")
        db.session.add(servico)
        db.session.commit()

        equipamento = Equipamento(
            nome="Cadeira Odontológica", tipo="Clínico", unidade_id=unidade.id, situacao="ATIVO"
        )
        db.session.add(equipamento)
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


def _unidade_id(app):
    with app.app_context():
        return Unidade.query.filter_by(cnes="1234567").first().id


def _servico_id(app):
    with app.app_context():
        return Servico.query.filter_by(nome="Odontologia Geral").first().id


def _equipamento_id(app):
    with app.app_context():
        return Equipamento.query.filter_by(nome="Cadeira Odontológica").first().id


# ----------------------------------------------------------------
# 1-3. Criar alteração: fica PENDENTE e registra o solicitante
# ----------------------------------------------------------------

def test_usuario_autorizado_cria_alteracao(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    resp = client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        assert alteracao is not None
        # 2. fica PENDENTE
        assert alteracao.status == StatusAlteracao.PENDENTE
        # 3. registra o usuário solicitante
        responsavel = _usuario(app, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
        assert alteracao.usuario_id == responsavel.id


# ----------------------------------------------------------------
# 4-5. GESTAO_INFORMACAO e ADMINISTRADOR conseguem visualizar
# ----------------------------------------------------------------

def test_gestao_informacao_visualiza_alteracoes(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    client_gestao = client
    _login(client_gestao, PerfilUsuario.GESTAO_INFORMACAO)
    resp = client_gestao.get("/alteracoes")
    assert resp.status_code == 200
    assert "UBS Vila Feliz" in resp.get_data(as_text=True)


def test_administrador_visualiza_alteracoes(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao_id = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first().id

    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get(f"/alteracoes/{alteracao_id}")
    assert resp.status_code == 200


# ----------------------------------------------------------------
# 6-7. GESTOR e RESPONSAVEL_SAUDE_BUCAL não conseguem aprovar
# ----------------------------------------------------------------

def test_gestor_nao_consegue_aprovar(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)
    with app.app_context():
        alteracao_id = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first().id

    _login(client, PerfilUsuario.GESTOR)
    resp = client.post(f"/alteracoes/{alteracao_id}/aprovar")
    assert resp.status_code == 403


def test_responsavel_saude_bucal_nao_consegue_aprovar(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)
    with app.app_context():
        alteracao_id = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first().id

    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    resp = client.post(f"/alteracoes/{alteracao_id}/aprovar")
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 8. Solicitante não consegue aprovar a própria alteração
# ----------------------------------------------------------------

def test_solicitante_nao_aprova_a_propria_alteracao_via_service(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        criador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        ok, mensagem = aprovar_alteracao(alteracao, criador)
        assert ok is False
        assert "própria alteração" in mensagem
        assert alteracao.status == StatusAlteracao.PENDENTE


def test_solicitante_nao_aprova_a_propria_alteracao_via_rota(client, app):
    # ADMINISTRADOR pode aprovar em geral, mas não a própria alteração
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao_id = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first().id

    # Mesma sessão (o próprio administrador que criou) tenta aprovar
    resp = client.post(f"/alteracoes/{alteracao_id}/aprovar")
    assert resp.status_code == 403

    with app.app_context():
        alteracao = db.session.get(Alteracao, alteracao_id)
        assert alteracao.status == StatusAlteracao.PENDENTE


# ----------------------------------------------------------------
# 9-12. Outro usuário autorizado aprova; status/approved_by/approved_at
# ----------------------------------------------------------------

def test_outro_usuario_autorizado_aprova_e_registra_dados(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)

        ok, mensagem = aprovar_alteracao(alteracao, aprovador)

        assert ok is True
        # 10. status -> APROVADO
        assert alteracao.status == StatusAlteracao.APROVADO
        # 11. approved_by registrado
        assert alteracao.approved_by == aprovador.id
        # 12. approved_at registrado
        assert alteracao.approved_at is not None


# ----------------------------------------------------------------
# 13-14. Rejeição altera status e registra responsável/data
# ----------------------------------------------------------------

def test_rejeicao_altera_status_e_registra_responsavel_e_data(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)

        ok, mensagem = rejeitar_alteracao(alteracao, aprovador)

        assert ok is True
        assert alteracao.status == StatusAlteracao.REJEITADO
        assert alteracao.approved_by == aprovador.id
        assert alteracao.approved_at is not None

        # A unidade nunca chegou a ser criada
        assert Unidade.query.filter_by(cnes="7654321").first() is None


# ----------------------------------------------------------------
# 15-16. Alteração já decidida não pode ser decidida de novo
# ----------------------------------------------------------------

def test_alteracao_ja_aprovada_nao_pode_ser_aprovada_novamente(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        aprovar_alteracao(alteracao, aprovador)

        outro_aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        ok, mensagem = aprovar_alteracao(alteracao, outro_aprovador)
        assert ok is False
        assert "já foi processada" in mensagem


def test_alteracao_ja_rejeitada_nao_pode_ser_rejeitada_novamente(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        rejeitar_alteracao(alteracao, aprovador)

        outro_aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        ok, mensagem = rejeitar_alteracao(alteracao, outro_aprovador)
        assert ok is False
        assert "já foi processada" in mensagem


# ----------------------------------------------------------------
# 17. Alteração inexistente retorna 404
# ----------------------------------------------------------------

def test_alteracao_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/alteracoes/999999")
    assert resp.status_code == 404


def test_aprovar_alteracao_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.post("/alteracoes/999999/aprovar")
    assert resp.status_code == 404


# ----------------------------------------------------------------
# 18. Usuário não autenticado não acessa alterações
# ----------------------------------------------------------------

def test_usuario_nao_autenticado_nao_acessa_alteracoes(client):
    resp = client.get("/alteracoes", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# 19. Usuário sem permissão recebe 403 (RESPONSAVEL/GESTOR ao
#     tentar aprovar/rejeitar — RBAC de rota)
# ----------------------------------------------------------------

def test_gestor_recebe_403_ao_tentar_rejeitar(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)
    with app.app_context():
        alteracao_id = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first().id

    _login(client, PerfilUsuario.GESTOR)
    resp = client.post(f"/alteracoes/{alteracao_id}/rejeitar")
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 20-22. Alteração de Unidade, Serviço e Equipamento
# ----------------------------------------------------------------

def test_alteracao_relacionada_a_unidade(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    unidade_id = _unidade_id(app)

    client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "MANUTENCAO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="ALTERAR_SITUACAO").first()
        assert alteracao is not None
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True

        unidade = db.session.get(Unidade, unidade_id)
        assert unidade.situacao.value == "MANUTENCAO"


def test_alteracao_relacionada_a_servico(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    servico_id = _servico_id(app)

    client.post(f"/servicos/{servico_id}/situacao", data={"situacao": "INATIVO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="servicos", operacao="ALTERAR_SITUACAO").first()
        assert alteracao is not None
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True

        servico = db.session.get(Servico, servico_id)
        assert servico.situacao.value == "INATIVO"


def test_alteracao_relacionada_a_equipamento(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    equipamento_id = _equipamento_id(app)

    client.post(f"/equipamentos/{equipamento_id}/situacao", data={"situacao": "INATIVO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="equipamentos", operacao="ALTERAR_SITUACAO").first()
        assert alteracao is not None
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True

        equipamento = db.session.get(Equipamento, equipamento_id)
        assert equipamento.situacao.value == "INATIVO"


# ----------------------------------------------------------------
# 23. Rollback em caso de erro (conflito de CNES detectado só no
#     momento de aplicar duas criações pendentes com o mesmo CNES)
# ----------------------------------------------------------------

def test_rollback_ao_aprovar_alteracao_com_conflito_de_dados(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)

    dados_a = dict(DADOS_UNIDADE_NOVA)
    dados_b = dict(DADOS_UNIDADE_NOVA)
    dados_b["nome"] = "UBS Outro Nome"
    # mesmo CNES em A e B — nenhuma delas existe ainda, então nenhuma
    # bloqueia a outra na hora de SOLICITAR.
    client.post("/unidades/nova", data=dados_a)
    client.post("/unidades/nova", data=dados_b)

    with app.app_context():
        alteracoes = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").order_by(Alteracao.id).all()
        assert len(alteracoes) == 2
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)

        ok_a, _ = aprovar_alteracao(alteracoes[0], aprovador)
        assert ok_a is True

        ok_b, mensagem_b = aprovar_alteracao(alteracoes[1], aprovador)
        assert ok_b is False
        assert "conflito" in mensagem_b.lower()

        # A segunda alteração continua PENDENTE — nada foi aplicado
        # parcialmente, e só existe uma unidade com esse CNES.
        assert alteracoes[1].status == StatusAlteracao.PENDENTE
        assert Unidade.query.filter_by(cnes="7654321").count() == 1


# ----------------------------------------------------------------
# 24. Suíte completa das Fases 1-6 continua passando — ver execução
#     conjunta de `pytest tests/` no relatório da Fase 7. Este teste
#     aqui só garante que o próprio model está consistente após a
#     extensão da Fase 7.
# ----------------------------------------------------------------

def test_modelo_alteracao_tem_os_novos_campos_da_fase7():
    from app.models import Alteracao as AlteracaoModel
    from app.models.enums import TipoOperacaoAlteracao

    colunas = {coluna.name for coluna in AlteracaoModel.__table__.columns}
    assert "operacao" in colunas
    assert "dados_novos" in colunas
    # registro_id precisa ser opcional (CRIAR ainda não tem registro)
    assert AlteracaoModel.__table__.columns["registro_id"].nullable is True

    assert {item.value for item in TipoOperacaoAlteracao} == {"CRIAR", "EDITAR", "ALTERAR_SITUACAO"}
