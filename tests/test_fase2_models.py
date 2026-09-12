"""
Testes da FASE 2 — banco de dados e models.

Esta suíte cobre:

1. Import dos models (garante que não há erro de sintaxe/relacionamento
   quebrado ao carregar app/models).
2. A aplicação continua iniciando normalmente.
3. A rota /health continua funcionando.
4. Relacionamentos entre models estão corretamente definidos.
5. Constraints básicas (unicidade de email e de CNES, obrigatoriedade
   de campos not null) estão configuradas.

Os testes rodam contra SQLite em memória (TestingConfig), então não
dependem de um MySQL disponível para serem executados. A validação
específica em MySQL real (criação das tabelas, FKs, ENUMs) foi feita
manualmente durante o desenvolvimento desta fase e está documentada
no relatório da fase — ver seção "Testes executados" no relatório.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from config import TestingConfig


@pytest.fixture
def app():
    """Cria uma app Flask com banco SQLite em memória, com as
    tabelas já criadas, para cada teste."""
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# ----------------------------------------------------------------
# 1. Import dos models
# ----------------------------------------------------------------

def test_models_podem_ser_importados():
    from app.models import (
        Usuario,
        Unidade,
        Servico,
        Equipamento,
        Alteracao,
        Auditoria,
        PerfilUsuario,
        SituacaoUnidade,
        SituacaoAtivoInativo,
        StatusAlteracao,
    )

    # Se o import funcionou, as classes existem e têm __tablename__
    assert Usuario.__tablename__ == "usuarios"
    assert Unidade.__tablename__ == "unidades"
    assert Servico.__tablename__ == "servicos"
    assert Equipamento.__tablename__ == "equipamentos"
    assert Alteracao.__tablename__ == "alteracoes"
    assert Auditoria.__tablename__ == "auditorias"


def test_todas_as_tabelas_sao_registradas_no_metadata(app):
    tabelas_esperadas = {
        "usuarios",
        "unidades",
        "servicos",
        "equipamentos",
        "alteracoes",
        "auditorias",
    }
    assert tabelas_esperadas.issubset(set(db.metadata.tables.keys()))


# ----------------------------------------------------------------
# 2 e 3. App continua iniciando e /health continua funcionando
# ----------------------------------------------------------------

def test_app_e_criada_com_sucesso():
    app = create_app(TestingConfig)
    assert app is not None


def test_health_check_continua_funcionando(app):
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["app"] == "ORIS"


# ----------------------------------------------------------------
# 4. Relacionamentos entre models
# ----------------------------------------------------------------

def _criar_estrutura_basica():
    """Helper: cria um usuário + unidade + serviço + equipamento
    encadeados, para testar os relacionamentos."""
    from app.models import Usuario, Unidade, Servico, Equipamento, PerfilUsuario, SituacaoUnidade

    usuario = Usuario(
        nome="Usuário Teste",
        email="usuario.teste@oris.local",
        senha_hash="placeholder-fase3",
        perfil=PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL,
    )
    db.session.add(usuario)
    db.session.commit()

    unidade = Unidade(
        nome="UBS Teste",
        cnes="0000001",
        situacao=SituacaoUnidade.ATIVA,
    )
    db.session.add(unidade)
    db.session.commit()

    servico = Servico(unidade_id=unidade.id, nome="Odontologia Geral")
    db.session.add(servico)
    db.session.commit()

    equipamento = Equipamento(
        unidade_id=unidade.id,
        servico_id=servico.id,
        nome="Cadeira Odontológica",
    )
    db.session.add(equipamento)
    db.session.commit()

    return usuario, unidade, servico, equipamento


def test_relacionamento_unidade_servicos_equipamentos(app):
    usuario, unidade, servico, equipamento = _criar_estrutura_basica()

    assert servico in list(unidade.servicos)
    assert equipamento in list(unidade.equipamentos)
    assert equipamento in list(servico.equipamentos)
    assert equipamento.unidade_id == unidade.id
    assert equipamento.servico_id == servico.id


def test_relacionamento_alteracao_usuario_criador_e_aprovador(app):
    from app.models import Usuario, Alteracao, PerfilUsuario, StatusAlteracao

    criador = Usuario(
        nome="Criador",
        email="criador@oris.local",
        senha_hash="placeholder-fase3",
        perfil=PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL,
    )
    aprovador = Usuario(
        nome="Aprovador",
        email="aprovador@oris.local",
        senha_hash="placeholder-fase3",
        perfil=PerfilUsuario.GESTAO_INFORMACAO,
    )
    db.session.add_all([criador, aprovador])
    db.session.commit()

    alteracao = Alteracao(
        usuario_id=criador.id,
        tabela="unidades",
        registro_id=1,
        descricao="Alteração de teste",
        status=StatusAlteracao.APROVADO,
        approved_by=aprovador.id,
    )
    db.session.add(alteracao)
    db.session.commit()

    assert alteracao.usuario_criador == criador
    assert alteracao.usuario_aprovador == aprovador
    assert alteracao in list(criador.alteracoes_criadas)
    assert alteracao in list(aprovador.alteracoes_aprovadas)


def test_relacionamento_auditoria_usuario(app):
    from app.models import Usuario, Auditoria, PerfilUsuario

    usuario = Usuario(
        nome="Usuário Auditado",
        email="auditado@oris.local",
        senha_hash="placeholder-fase3",
        perfil=PerfilUsuario.ADMINISTRADOR,
    )
    db.session.add(usuario)
    db.session.commit()

    auditoria = Auditoria(
        usuario_id=usuario.id,
        acao="CRIOU_UNIDADE",
        tabela="unidades",
        registro_id=1,
        descricao="Teste de auditoria",
    )
    db.session.add(auditoria)
    db.session.commit()

    assert auditoria.usuario == usuario
    assert auditoria in list(usuario.auditorias)


# ----------------------------------------------------------------
# 5. Constraints básicas
# ----------------------------------------------------------------

def test_email_de_usuario_deve_ser_unico(app):
    from app.models import Usuario, PerfilUsuario

    u1 = Usuario(
        nome="Primeiro",
        email="duplicado@oris.local",
        senha_hash="x",
        perfil=PerfilUsuario.GESTOR,
    )
    db.session.add(u1)
    db.session.commit()

    u2 = Usuario(
        nome="Segundo",
        email="duplicado@oris.local",
        senha_hash="y",
        perfil=PerfilUsuario.GESTOR,
    )
    db.session.add(u2)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_cnes_de_unidade_deve_ser_unico(app):
    from app.models import Unidade, SituacaoUnidade

    u1 = Unidade(nome="Unidade A", cnes="9999999", situacao=SituacaoUnidade.ATIVA)
    db.session.add(u1)
    db.session.commit()

    u2 = Unidade(nome="Unidade B", cnes="9999999", situacao=SituacaoUnidade.ATIVA)
    db.session.add(u2)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_campos_obrigatorios_de_usuario(app):
    from app.models import Usuario, PerfilUsuario

    # Sem email (campo obrigatório) deve falhar ao gravar
    usuario_sem_email = Usuario(
        nome="Sem Email",
        email=None,
        senha_hash="x",
        perfil=PerfilUsuario.GESTOR,
    )
    db.session.add(usuario_sem_email)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()
