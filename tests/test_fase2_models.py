"""Testes da FASE 2 - banco de dados e models."""

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from config import TestingConfig


@pytest.fixture
def app():
    """Cria uma app Flask com banco SQLite em memória, com as tabelas já criadas, para..."""
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


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


def _criar_estrutura_basica():
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
    from app.models.enums import TipoOperacaoAlteracao

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
        operacao=TipoOperacaoAlteracao.ALTERAR_SITUACAO,  # campo obrigatório desde a Fase 7
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


def test_cnes_pode_ser_repetido_em_unidades_distintas(app):
    """CONTRATO NOVO (Stage "modelo de dados")"""
    from app.models import Unidade, SituacaoUnidade

    u1 = Unidade(nome="Policlínica Central", cnes="1234567", situacao=SituacaoUnidade.ATIVA)
    u2 = Unidade(nome="Maternidade Central", cnes="1234567", situacao=SituacaoUnidade.ATIVA)
    db.session.add_all([u1, u2])

    db.session.commit()

    assert Unidade.query.filter_by(cnes="1234567").count() == 2


def test_campos_obrigatorios_de_usuario(app):
    from app.models import Usuario, PerfilUsuario

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


def test_duas_unidades_com_mesmo_cnes_tem_ids_internos_diferentes(app):
    from app.models import Unidade, SituacaoUnidade

    u1 = Unidade(nome="UBT Alto do Céu", cnes="2345678", situacao=SituacaoUnidade.ATIVA)
    u2 = Unidade(nome="USF Alto do Céu", cnes="2345678", situacao=SituacaoUnidade.ATIVA)
    db.session.add_all([u1, u2])
    db.session.commit()

    assert u1.id is not None
    assert u2.id is not None
    assert u1.id != u2.id
    assert u1.cnes == u2.cnes == "2345678"


def test_unidade_mista_marca_o_campo_unidade_e_mista(app):
    from app.models import Unidade, SituacaoUnidade

    unidade_simples = Unidade(nome="USF Comum", cnes="3456789", situacao=SituacaoUnidade.ATIVA)
    db.session.add(unidade_simples)
    db.session.commit()
    assert unidade_simples.unidade_e_mista is False

    policlinica = Unidade(
        nome="Policlínica Sul", cnes="4567890", situacao=SituacaoUnidade.ATIVA, unidade_e_mista=True,
    )
    maternidade = Unidade(
        nome="Maternidade Sul", cnes="4567890", situacao=SituacaoUnidade.ATIVA, unidade_e_mista=True,
    )
    db.session.add_all([policlinica, maternidade])
    db.session.commit()

    assert policlinica.unidade_e_mista is True
    assert maternidade.unidade_e_mista is True
    assert policlinica.cnes == maternidade.cnes


def test_servico_pode_existir_sem_unidade(app):
    from app.models import Servico, SituacaoAtivoInativo

    servico = Servico(
        nome="Ponto de Vacinação — Shopping X",
        unidade_id=None,
        situacao=SituacaoAtivoInativo.ATIVO,
    )
    db.session.add(servico)
    db.session.commit()

    assert servico.id is not None
    assert servico.unidade_id is None
    assert servico.unidade is None


def test_equipamento_pode_existir_sem_unidade(app):
    from app.models import Equipamento, SituacaoAtivoInativo

    equipamento = Equipamento(
        nome="Ambulância SAMU 07",
        tipo="Ambulância",
        unidade_id=None,
        situacao=SituacaoAtivoInativo.ATIVO,
    )
    db.session.add(equipamento)
    db.session.commit()

    assert equipamento.id is not None
    assert equipamento.unidade_id is None
    assert equipamento.unidade is None


def test_equipamento_sem_unidade_pode_estar_ligado_a_servico(app):
    from app.models import Equipamento, Servico, SituacaoAtivoInativo

    servico = Servico(nome="Espaço Mãe Coruja — Compaz", unidade_id=None, situacao=SituacaoAtivoInativo.ATIVO)
    db.session.add(servico)
    db.session.commit()

    equipamento = Equipamento(
        nome="Sala de Atendimento — Compaz",
        tipo="Estrutura de atendimento",
        unidade_id=None,
        servico_id=servico.id,
        situacao=SituacaoAtivoInativo.ATIVO,
    )
    db.session.add(equipamento)
    db.session.commit()

    assert equipamento.unidade_id is None
    assert equipamento.servico_id == servico.id
    assert equipamento.servico == servico
    assert equipamento in list(servico.equipamentos)


def test_equipamento_pode_estar_ligado_a_servico_sem_unidade(app):
    from app.models import Equipamento, Servico, SituacaoAtivoInativo, SituacaoUnidade, Unidade

    servico_sem_unidade = Servico(nome="Serviço Volante", unidade_id=None, situacao=SituacaoAtivoInativo.ATIVO)
    db.session.add(servico_sem_unidade)
    db.session.commit()

    unidade = Unidade(nome="UBS Referência", cnes="5678901", situacao=SituacaoUnidade.ATIVA)
    db.session.add(unidade)
    db.session.commit()

    equipamento_com_unidade = Equipamento(
        nome="Kit Odontológico Móvel",
        tipo="Kit móvel",
        unidade_id=unidade.id,
        servico_id=servico_sem_unidade.id,
        situacao=SituacaoAtivoInativo.ATIVO,
    )
    db.session.add(equipamento_com_unidade)
    db.session.commit()

    assert equipamento_com_unidade.unidade_id == unidade.id
    assert equipamento_com_unidade.servico_id == servico_sem_unidade.id
    assert equipamento_com_unidade.servico.unidade_id is None


def test_cnes_ficticio_9999999_pode_se_repetir(app):
    from app.models import Unidade, SituacaoUnidade

    u1 = Unidade(nome="Ponto de Vacinação A", cnes="9999999", situacao=SituacaoUnidade.ATIVA)
    u2 = Unidade(nome="Ponto de Vacinação B", cnes="9999999", situacao=SituacaoUnidade.ATIVA)
    db.session.add_all([u1, u2])
    db.session.commit()

    assert Unidade.query.filter_by(cnes="9999999").count() == 2
    assert u1.id != u2.id


def test_vinculos_existentes_com_unidade_continuam_funcionando(app):
    usuario, unidade, servico, equipamento = _criar_estrutura_basica()

    assert servico in list(unidade.servicos)
    assert equipamento in list(unidade.equipamentos)
    assert equipamento in list(servico.equipamentos)
    assert servico.unidade == unidade
    assert equipamento.unidade == unidade
    assert equipamento.servico == servico


def test_auditoria_e_aprovacao_continuam_intactas_apos_o_redesenho(app):
    from app.models import Alteracao, Auditoria, PerfilUsuario, StatusAlteracao, Usuario
    from app.models.enums import TipoOperacaoAlteracao

    usuario = Usuario(
        nome="Usuário Redesenho",
        email="redesenho@oris.local",
        senha_hash="placeholder",
        perfil=PerfilUsuario.ADMINISTRADOR,
    )
    db.session.add(usuario)
    db.session.commit()

    alteracao = Alteracao(
        usuario_id=usuario.id,
        tabela="servicos",
        registro_id=None,
        operacao=TipoOperacaoAlteracao.CRIAR,
        dados_novos='{"nome": "Serviço via Alteracao", "unidade_id": null}',
        descricao="Criação de serviço sem unidade, via fluxo de aprovação",
        status=StatusAlteracao.PENDENTE,
    )
    db.session.add(alteracao)
    db.session.commit()

    auditoria = Auditoria(
        usuario_id=usuario.id,
        acao="SOLICITAR_ALTERACAO",
        tabela="servicos",
        registro_id=None,
        descricao="Auditoria da solicitação acima",
    )
    db.session.add(auditoria)
    db.session.commit()

    assert alteracao.status == StatusAlteracao.PENDENTE
    assert auditoria.usuario == usuario


def test_integridade_da_fk_quando_relacionamento_existe(app):
    from app.models import Equipamento, Servico, SituacaoAtivoInativo, SituacaoUnidade, Unidade

    unidade = Unidade(nome="UBS com Vínculo", cnes="6789012", situacao=SituacaoUnidade.ATIVA)
    db.session.add(unidade)
    db.session.commit()

    servico = Servico(nome="Odontologia", unidade_id=unidade.id, situacao=SituacaoAtivoInativo.ATIVO)
    db.session.add(servico)
    db.session.commit()

    equipamento = Equipamento(
        nome="Cadeira Odontológica",
        tipo="Equipamento clínico",
        unidade_id=unidade.id,
        servico_id=servico.id,
        situacao=SituacaoAtivoInativo.ATIVO,
    )
    db.session.add(equipamento)
    db.session.commit()

    assert db.session.get(Servico, servico.id).unidade_id == unidade.id
    assert db.session.get(Equipamento, equipamento.id).unidade_id == unidade.id
    assert db.session.get(Equipamento, equipamento.id).servico_id == servico.id
