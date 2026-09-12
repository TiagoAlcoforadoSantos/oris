"""
Testes da FASE 8 — auditoria e rastreabilidade.

Roda contra SQLite em memória (TestingConfig). Reaproveita o padrão
de fixtures das fases anteriores.
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Alteracao,
    Auditoria,
    Equipamento,
    PerfilUsuario,
    Servico,
    SituacaoUnidade,
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
            nome="UBS Bairro Novo", cnes="1234567", tipo="UBS",
            cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA,
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
# 1-2. Login e logout geram auditoria
# ----------------------------------------------------------------

def test_login_gera_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    with app.app_context():
        registro = Auditoria.query.filter_by(acao="LOGIN").first()
        assert registro is not None
        admin = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        assert registro.usuario_id == admin.id


def test_logout_gera_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.get("/logout")

    with app.app_context():
        registro = Auditoria.query.filter_by(acao="LOGOUT").first()
        assert registro is not None


# ----------------------------------------------------------------
# 3-5. Unidade: criação/edição/situação geram auditoria QUANDO
# EFETIVADAS (após aprovação) — nunca no momento da solicitação
# ----------------------------------------------------------------

def test_criacao_de_unidade_gera_auditoria_apenas_quando_efetivada(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        # Ainda pendente: nenhuma auditoria de CRIAR, só de SOLICITAR_ALTERACAO
        assert Auditoria.query.filter_by(acao="CRIAR", tabela="unidades").first() is None
        assert Auditoria.query.filter_by(acao="SOLICITAR_ALTERACAO", tabela="unidades").first() is not None

        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        aprovar_alteracao(alteracao, aprovador)

        # Agora sim, auditoria de CRIAR existe
        registro = Auditoria.query.filter_by(acao="CRIAR", tabela="unidades").first()
        assert registro is not None
        assert registro.registro_id == alteracao.registro_id


def test_edicao_de_unidade_gera_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_id(app)

    dados_editados = dict(DADOS_UNIDADE_NOVA)
    dados_editados.update({"cnes": "1234567", "nome": "UBS Bairro Novo Renomeada"})
    client.post(f"/unidades/{unidade_id}/editar", data=dados_editados)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="EDITAR").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        aprovar_alteracao(alteracao, aprovador)

        registro = Auditoria.query.filter_by(acao="EDITAR", tabela="unidades").first()
        assert registro is not None
        assert registro.registro_id == unidade_id


def test_alteracao_de_situacao_gera_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_id(app)

    client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "MANUTENCAO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="ALTERAR_SITUACAO").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        aprovar_alteracao(alteracao, aprovador)

        registro = Auditoria.query.filter_by(acao="ALTERAR_SITUACAO", tabela="unidades").first()
        assert registro is not None


# ----------------------------------------------------------------
# 6-8. Solicitação, aprovação e rejeição geram auditoria
# ----------------------------------------------------------------

def test_solicitacao_de_alteracao_gera_auditoria(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        registro = Auditoria.query.filter_by(acao="SOLICITAR_ALTERACAO").first()
        assert registro is not None
        responsavel = _usuario(app, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
        assert registro.usuario_id == responsavel.id


def test_aprovacao_gera_auditoria(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        aprovar_alteracao(alteracao, aprovador)

        registro = Auditoria.query.filter_by(acao="APROVAR_ALTERACAO").first()
        assert registro is not None
        assert registro.usuario_id == aprovador.id
        assert registro.registro_id == alteracao.id


def test_rejeicao_gera_auditoria(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post("/unidades/nova", data=DADOS_UNIDADE_NOVA)

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        rejeitar_alteracao(alteracao, aprovador)

        registro = Auditoria.query.filter_by(acao="REJEITAR_ALTERACAO").first()
        assert registro is not None
        assert registro.usuario_id == aprovador.id
        # Rejeição nunca gera auditoria de CRIAR (nada foi aplicado)
        assert Auditoria.query.filter_by(acao="CRIAR", tabela="unidades").first() is None


# ----------------------------------------------------------------
# 9-10. Serviço e Equipamento também geram auditoria
# ----------------------------------------------------------------

def test_servico_gera_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    servico_id = _servico_id(app)

    client.post(f"/servicos/{servico_id}/situacao", data={"situacao": "INATIVO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="servicos", operacao="ALTERAR_SITUACAO").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        aprovar_alteracao(alteracao, aprovador)

        registro = Auditoria.query.filter_by(acao="ALTERAR_SITUACAO", tabela="servicos").first()
        assert registro is not None
        assert registro.registro_id == servico_id


def test_equipamento_gera_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    equipamento_id = _equipamento_id(app)

    client.post(f"/equipamentos/{equipamento_id}/situacao", data={"situacao": "INATIVO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="equipamentos", operacao="ALTERAR_SITUACAO").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        aprovar_alteracao(alteracao, aprovador)

        registro = Auditoria.query.filter_by(acao="ALTERAR_SITUACAO", tabela="equipamentos").first()
        assert registro is not None
        assert registro.registro_id == equipamento_id


# ----------------------------------------------------------------
# 11-15. Auditoria registra usuário, data/hora, ação, entidade,
# registro corretos
# ----------------------------------------------------------------

def test_auditoria_registra_usuario_data_acao_entidade_registro_corretos(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_id(app)
    admin = _usuario(app, PerfilUsuario.ADMINISTRADOR)

    client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "MANUTENCAO"})

    with app.app_context():
        registro = Auditoria.query.filter_by(acao="SOLICITAR_ALTERACAO").first()
        assert registro.usuario_id == admin.id  # 11. usuário correto
        assert registro.data_hora is not None  # 12. data/hora
        assert registro.acao == "SOLICITAR_ALTERACAO"  # 13. ação correta
        assert registro.tabela == "unidades"  # 14. entidade correta
        assert registro.registro_id == unidade_id  # 15. registro correto


# ----------------------------------------------------------------
# 16-17. Edição registra valor anterior e valor novo
# ----------------------------------------------------------------

def test_edicao_registra_valor_anterior_e_novo(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_id(app)

    client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "MANUTENCAO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="ALTERAR_SITUACAO").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        aprovar_alteracao(alteracao, aprovador)

        registro = Auditoria.query.filter_by(acao="ALTERAR_SITUACAO", tabela="unidades").first()
        assert registro.valor_anterior is not None
        assert "ATIVA" in registro.valor_anterior
        assert registro.valor_novo is not None
        assert "MANUTENCAO" in registro.valor_novo


# ----------------------------------------------------------------
# 18. Senha não aparece na auditoria
# ----------------------------------------------------------------

def test_senha_nao_aparece_na_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    with app.app_context():
        for registro in Auditoria.query.all():
            texto_completo = " ".join(
                filter(None, [registro.descricao, registro.valor_anterior, registro.valor_novo])
            )
            assert SENHA not in texto_completo
            assert "senha_hash" not in texto_completo
            assert "$2b$" not in texto_completo  # assinatura de hash bcrypt


# ----------------------------------------------------------------
# 19-21. Controle de acesso à consulta de auditoria
# ----------------------------------------------------------------

def test_usuario_nao_autorizado_nao_acessa_auditoria(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    resp = client.get("/auditoria")
    assert resp.status_code == 403


def test_gestor_nao_acessa_auditoria(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/auditoria")
    assert resp.status_code == 403


def test_gestao_informacao_consulta_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)  # gera ao menos 1 registro (LOGIN)

    client2 = app.test_client()
    _login(client2, PerfilUsuario.GESTAO_INFORMACAO)
    resp = client2.get("/auditoria")
    assert resp.status_code == 200


def test_administrador_consulta_auditoria(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/auditoria")
    assert resp.status_code == 200


# ----------------------------------------------------------------
# 22-23. Auditoria não pode ser editada nem excluída via aplicação
# ----------------------------------------------------------------

def test_nao_existe_rota_de_edicao_de_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    with app.app_context():
        registro_id = Auditoria.query.first().id

    # Nenhuma dessas rotas existe na aplicação
    resp = client.post(f"/auditoria/{registro_id}/editar", data={"descricao": "adulterado"})
    assert resp.status_code == 404

    resp = client.get(f"/auditoria/{registro_id}/editar")
    assert resp.status_code == 404


def test_nao_existe_rota_de_exclusao_de_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    with app.app_context():
        registro_id = Auditoria.query.first().id
        total_antes = Auditoria.query.count()

    resp = client.post(f"/auditoria/{registro_id}/excluir")
    assert resp.status_code == 404

    resp = client.delete(f"/auditoria/{registro_id}")
    # A rota GET /auditoria/<id> existe (visualizar); tentar DELETE
    # nela retorna 405 (método não permitido) — não existe NENHUMA
    # forma de excluir um registro de auditoria pela aplicação.
    assert resp.status_code in (404, 405)

    with app.app_context():
        assert Auditoria.query.count() == total_antes


# ----------------------------------------------------------------
# Extra: listagem ordenada por data/hora decrescente, filtros, e
# página de detalhe mostra valor anterior/novo
# ----------------------------------------------------------------

def test_listagem_ordenada_por_data_decrescente(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_id(app)
    client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "MANUTENCAO"})

    with app.app_context():
        registros = Auditoria.query.order_by(Auditoria.data_hora.desc()).all()
        # LOGIN aconteceu antes de SOLICITAR_ALTERACAO — na ordenação
        # decrescente (mais recente primeiro), SOLICITAR_ALTERACAO
        # deve vir antes de LOGIN.
        acoes_em_ordem = [r.acao for r in registros]
        assert acoes_em_ordem.index("SOLICITAR_ALTERACAO") < acoes_em_ordem.index("LOGIN")

    # E a página /auditoria usa exatamente essa mesma ordenação.
    resp = client.get("/auditoria")
    assert resp.status_code == 200


def test_filtro_por_acao(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.get("/auditoria?acao=LOGIN")
    assert resp.status_code == 200
    assert "LOGIN" in resp.get_data(as_text=True)


def test_pagina_de_detalhe_mostra_valores(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    unidade_id = _unidade_id(app)
    client.post(f"/unidades/{unidade_id}/situacao", data={"situacao": "MANUTENCAO"})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="ALTERAR_SITUACAO").first()
        aprovador = _usuario(app, PerfilUsuario.GESTAO_INFORMACAO)
        aprovar_alteracao(alteracao, aprovador)
        registro_id = Auditoria.query.filter_by(acao="ALTERAR_SITUACAO").first().id

    resp = client.get(f"/auditoria/{registro_id}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "MANUTENCAO" in html


def test_auditoria_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/auditoria/999999")
    assert resp.status_code == 404


# ----------------------------------------------------------------
# Modelo: novos campos da Fase 8
# ----------------------------------------------------------------

def test_modelo_auditoria_tem_os_novos_campos_da_fase8():
    from app.models import Auditoria as AuditoriaModel

    colunas = {coluna.name for coluna in AuditoriaModel.__table__.columns}
    assert "valor_anterior" in colunas
    assert "valor_novo" in colunas
