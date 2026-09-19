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


def test_cnes_pode_ser_repetido_em_unidades_distintas(app):
    """CONTRATO NOVO (Stage "modelo de dados"): o CNES deixou de ser
    único. A documentação real do cliente mostra que o mesmo CNES
    pode corresponder a mais de um registro de Unidade (ex.: unidade
    mista — Policlínica + Maternidade sob o mesmo CNES). Este teste
    substitui o antigo `test_cnes_de_unidade_deve_ser_unico`, que
    verificava exatamente o comportamento oposto (CNES duplicado
    rejeitado por IntegrityError) — esse era o contrato antigo,
    incompatível com o modelo real do cliente."""
    from app.models import Unidade, SituacaoUnidade

    u1 = Unidade(nome="Policlínica Central", cnes="1234567", situacao=SituacaoUnidade.ATIVA)
    u2 = Unidade(nome="Maternidade Central", cnes="1234567", situacao=SituacaoUnidade.ATIVA)
    db.session.add_all([u1, u2])

    # Não deve levantar IntegrityError: duas Unidades com o mesmo
    # CNES são um cenário válido no modelo novo.
    db.session.commit()

    assert Unidade.query.filter_by(cnes="1234567").count() == 2


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


# ----------------------------------------------------------------
# 6. REDESENHO DO MODELO DE DADOS (Stage "modelo de dados")
#
# Cobre os cenários exigidos pela Stage: CNES não-único (id interno
# como identificador de negócio), unidade mista, Serviço/Equipamento
# sem Unidade, relação Serviço<->Equipamento independente de Unidade,
# CNES fictício 9999999 repetido, e que os vínculos/auditoria/
# aprovação que já existiam continuam intactos.
# ----------------------------------------------------------------

def test_duas_unidades_com_mesmo_cnes_tem_ids_internos_diferentes(app):
    """Item 1/2 da Stage: duas Unidades com o mesmo CNES devem
    coexistir, cada uma com seu próprio id interno — o id (não o
    CNES) é o identificador de negócio."""
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
    """Item 3 da Stage: uma Unidade que participa de um CNES com mais
    de uma tipologia (ex.: Policlínica + Maternidade) pode ser
    marcada com unidade_e_mista=True; o valor default é False."""
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
    """Item 4 da Stage: Serviço sem Unidade (ex.: ponto de vacinação
    municipal em shopping, conforme documentação do cliente)."""
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
    """Item 5 da Stage: Equipamento sem Unidade (ex.: ambulância do
    SAMU, conforme documentação do cliente)."""
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
    """Item 6 da Stage: um Equipamento sem Unidade ainda pode estar
    associado a um Serviço (a relação Equipamento->Serviço é
    independente de unidade_id)."""
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
    """Item 7 da Stage: um Equipamento (com ou sem Unidade) pode
    estar ligado a um Serviço que, por sua vez, não tem Unidade."""
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
    """Item 8 da Stage: o valor convencional 9999999 (CNES fictício,
    usado pelo cliente para registros sem CNES próprio) não recebe
    nenhum tratamento especial de unicidade — pode se repetir como
    qualquer outro valor de cnes."""
    from app.models import Unidade, SituacaoUnidade

    u1 = Unidade(nome="Ponto de Vacinação A", cnes="9999999", situacao=SituacaoUnidade.ATIVA)
    u2 = Unidade(nome="Ponto de Vacinação B", cnes="9999999", situacao=SituacaoUnidade.ATIVA)
    db.session.add_all([u1, u2])
    db.session.commit()

    assert Unidade.query.filter_by(cnes="9999999").count() == 2
    assert u1.id != u2.id


def test_vinculos_existentes_com_unidade_continuam_funcionando(app):
    """Item 9 da Stage: quando Unidade está presente, os
    relacionamentos Unidade->Serviço, Unidade->Equipamento e
    Equipamento->Serviço continuam funcionando exatamente como
    antes."""
    usuario, unidade, servico, equipamento = _criar_estrutura_basica()

    assert servico in list(unidade.servicos)
    assert equipamento in list(unidade.equipamentos)
    assert equipamento in list(servico.equipamentos)
    assert servico.unidade == unidade
    assert equipamento.unidade == unidade
    assert equipamento.servico == servico


def test_auditoria_e_aprovacao_continuam_intactas_apos_o_redesenho(app):
    """Item 10 da Stage: o mecanismo de Alteracao (aprovação) e
    Auditoria não foi alterado por esta Stage — só o modelo de
    Unidade/Serviço/Equipamento mudou."""
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
    """Item 11 da Stage: quando o vínculo é informado, a FK continua
    resolvendo corretamente a Unidade/Serviço relacionados (a
    obrigatoriedade foi removida, não a integridade referencial)."""
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
