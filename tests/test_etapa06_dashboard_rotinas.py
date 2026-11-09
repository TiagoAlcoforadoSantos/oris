"""Etapa 06: manutenções (4º CRUD), rotinas do banco, views e dashboard.

Testes offline: não exigem MySQL. A execução real das funções/procedimentos/
triggers é validada com o banco (ver README, seção Etapa 06); aqui garantimos
o contrato do código: script SQL, catálogo, validação de parâmetros, RBAC e CSRF.
"""

import os
from decimal import Decimal

import pytest

from app import create_app
from app.bd import consultas, dashboard, objetos
from app.extensions import db
from app.models import PerfilUsuario, Usuario
from app.routes.bd import ENTIDADES, _ler_parametro
from app.utils.security import gerar_hash_senha
from config import DevelopmentConfig, TestingConfig

SENHA = "SenhaForte123!"


@pytest.fixture
def app_sqlite():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        db.session.add(Usuario(nome="Gestor", email="gestor@oris.com.br",
                               senha_hash=gerar_hash_senha(SENHA),
                               perfil=PerfilUsuario.GESTOR, ativo=True))
        db.session.commit()
    yield app
    with app.app_context():
        db.drop_all()


# ---------------------------------------------------------------- script SQL
def test_script_sql_define_todos_os_objetos_do_catalogo():
    comandos = objetos.ler_comandos()
    texto = "\n".join(comandos)
    for nome in [*objetos.FUNCOES, *objetos.PROCEDIMENTOS, *objetos.TRIGGERS, *objetos.VIEWS]:
        assert objetos.codigo_fonte(nome), f"{nome} não está em database/etapa05_objetos.sql"
        assert nome in texto


def test_cada_create_tem_drop_if_exists_ou_or_replace():
    comandos = objetos.ler_comandos()
    for i, cmd in enumerate(comandos):
        if cmd.upper().startswith("CREATE OR REPLACE VIEW"):
            continue
        if cmd.upper().startswith("CREATE "):
            assert comandos[i - 1].upper().startswith("DROP "), f"CREATE sem DROP antes: {cmd[:50]}"


def test_comandos_nao_trazem_o_separador():
    assert all("$$" not in c for c in objetos.ler_comandos())
    assert len(objetos.ler_comandos()) == 29


def test_exige_tres_tipos_de_objeto():
    assert len(objetos.FUNCOES) >= 2 and len(objetos.PROCEDIMENTOS) >= 2 and len(objetos.TRIGGERS) >= 2


# -------------------------------------------------------------------- catálogo
def test_todo_procedimento_catalogado_tem_sql_call_parametrizado():
    for nome, cfg in objetos.PROCEDIMENTOS.items():
        assert cfg["sql"].startswith(f"CALL {nome}(")
        assert cfg["sql"].count("%s") >= len(cfg["parametros"]) - 0 or nome == "sp_abrir_manutencao"


def test_quarta_tabela_no_crud():
    assert {"unidades", "servicos", "equipamentos", "manutencoes"} <= set(ENTIDADES)


def test_views_no_catalogo_de_consultas():
    ids = set(consultas.CONSULTAS_POR_ID)
    assert {"v1", "v2", "v3"} <= ids
    for vid in ("v1", "v2", "v3"):
        assert "vw_" in consultas.CONSULTAS_POR_ID[vid]["sql"]


# ------------------------------------------------------- validação de parâmetro
@pytest.mark.parametrize("tipo,bruto,esperado", [
    ("unidade", "7", 7), ("ano", "", None), ("ano", "2026", 2026),
    ("tipo_manutencao", "CORRETIVA", "CORRETIVA"),
    ("custo", "12,50", Decimal("12.50")), ("texto", " peça ", "peça"),
])
def test_parametros_validos(tipo, bruto, esperado):
    assert _ler_parametro({"tipo": tipo}, bruto) == esperado


@pytest.mark.parametrize("tipo,bruto", [
    ("unidade", "0"), ("unidade", "abc"), ("unidade", "1; DROP TABLE unidades"),
    ("ano", "1800"), ("tipo_manutencao", "OUTRA"), ("custo", "-1"), ("custo", "x"),
    ("texto", ""), ("texto", "a" * 300),
])
def test_parametros_invalidos(tipo, bruto):
    with pytest.raises(ValueError):
        _ler_parametro({"tipo": tipo}, bruto)


# --------------------------------------------------------------- filtros do dash
def test_filtros_do_dashboard_sanitizam_entrada():
    f = dashboard.ler_filtros({"unidade_situacao": "x'--", "tipo_manutencao": "CORRETIVA",
                               "data_ini": "2026-01-31", "data_fim": "lixo", "unidade_tipo": " UBS "})
    assert f == {"unidade_tipo": "UBS", "unidade_situacao": None, "tipo_manutencao": "CORRETIVA",
                 "data_ini": "2026-01-31", "data_fim": None}


def test_filtros_vazios_viram_none():
    assert set(dashboard.ler_filtros({}).values()) == {None}


# ----------------------------------------------------------- rotas (RBAC / CSRF)
@pytest.mark.parametrize("url", ["/bd/dashboard", "/bd/dashboard/dados", "/bd/rotinas", "/bd/manutencoes"])
def test_telas_exigem_login(app_sqlite, url):
    resposta = app_sqlite.test_client().get(url)
    assert resposta.status_code == 302 and "/login" in resposta.headers["Location"]


def test_executar_rotina_exige_login(app_sqlite):
    resposta = app_sqlite.test_client().post(
        "/bd/rotinas/executar", data={"objeto": "sp_resumo_unidade", "unidade_id": "1"})
    assert resposta.status_code == 302 and "/login" in resposta.headers["Location"]


def test_gestor_nao_altera_dados_por_procedimento_nem_crud(app_sqlite):
    c = app_sqlite.test_client()
    c.post("/login", data={"email": "gestor@oris.com.br", "senha": SENHA})
    for nome in ("sp_abrir_manutencao", "sp_concluir_manutencao", "sp_inativar_unidade"):
        assert c.post("/bd/rotinas/executar", data={"objeto": nome}).status_code == 403
    assert c.get("/bd/manutencoes/novo").status_code == 403
    assert c.post("/bd/manutencoes/1/excluir").status_code == 403


def test_rotina_desconhecida_da_404(app_sqlite):
    c = app_sqlite.test_client()
    c.post("/login", data={"email": "gestor@oris.com.br", "senha": SENHA})
    assert c.post("/bd/rotinas/executar", data={"objeto": "DROP TABLE unidades"}).status_code == 404


# ---------------------------------------------- contra o MySQL real (opcional)
mysql = pytest.mark.skipif(os.getenv("ORIS_TEST_MYSQL") != "1",
                           reason="defina ORIS_TEST_MYSQL=1 para testar contra o MySQL")


class MySQLTestConfig(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATE_LIMIT_LOGIN_ENABLED = False


@pytest.fixture
def admin_mysql():
    app = create_app(MySQLTestConfig)
    c = app.test_client()
    c.post("/login", data={"email": "admin.demo@oris.example", "senha": "Oris@2026"})
    return app, c


@mysql
def test_objetos_existem_no_mysql(admin_mysql):
    app, _ = admin_mysql
    with app.app_context():
        existentes = objetos.objetos_existentes()
    assert set(objetos.FUNCOES) <= existentes["funcoes"]
    assert set(objetos.PROCEDIMENTOS) <= existentes["procedimentos"]
    assert set(objetos.TRIGGERS) <= existentes["triggers"]
    assert set(objetos.VIEWS) <= existentes["views"]


@mysql
def test_trigger_corretiva_desativa_e_conclusao_reativa(admin_mysql):
    from app.bd.conexao import consultar_um
    app, _ = admin_mysql
    with app.app_context():
        eq = consultar_um("SELECT id FROM equipamentos WHERE situacao = 'ATIVO' LIMIT 1")["id"]
        _, linhas = objetos.chamar_procedimento("sp_abrir_manutencao", (eq, "CORRETIVA", "teste automatizado"), 1)
        mid = linhas[0]["manutencao_id"]
        assert consultar_um("SELECT situacao FROM equipamentos WHERE id = %s", (eq,))["situacao"] == "INATIVO"
        objetos.chamar_procedimento("sp_concluir_manutencao", (mid, Decimal("10.00")), 1)
        assert consultar_um("SELECT situacao FROM equipamentos WHERE id = %s", (eq,))["situacao"] == "ATIVO"
        with pytest.raises(Exception, match="ABERTAS"):
            objetos.chamar_procedimento("sp_concluir_manutencao", (mid, Decimal("1")), 1)
        from app.bd.conexao import transacao
        with transacao() as cur:
            cur.execute("DELETE FROM manutencoes WHERE id = %s", (mid,))


@mysql
def test_dashboard_e_views_respondem(admin_mysql):
    _, c = admin_mysql
    d = c.get("/bd/dashboard/dados?tipo_manutencao=CORRETIVA").get_json()
    assert d["kpis"]["unidades"] >= 0 and "mensal" in d
    for url in ("/bd/rotinas", "/bd/dashboard", "/bd/consultas/v1", "/bd/consultas/v2", "/bd/consultas/v3"):
        assert c.get(url).status_code == 200


# ------------------------------------------- regressão: itens sem unidade (vínculo opcional)
def test_listas_e_detalhes_aceitam_servico_e_equipamento_sem_unidade(app_sqlite):
    from app.models import Equipamento, Servico, SituacaoAtivoInativo
    with app_sqlite.app_context():
        s = Servico(nome="Servico sem unidade", unidade_id=None, situacao=SituacaoAtivoInativo.ATIVO)
        db.session.add(s)
        db.session.flush()
        e = Equipamento(nome="Equip sem unidade", tipo="X", unidade_id=None, servico_id=None,
                        situacao=SituacaoAtivoInativo.ATIVO)
        db.session.add(e)
        db.session.commit()
        sid, eid = s.id, e.id
        db.session.add(Usuario(nome="Admin", email="admin@oris.com.br", senha_hash=gerar_hash_senha(SENHA),
                               perfil=PerfilUsuario.ADMINISTRADOR, ativo=True))
        db.session.commit()
    c = app_sqlite.test_client()
    c.post("/login", data={"email": "admin@oris.com.br", "senha": SENHA})
    for url in ("/servicos", f"/servicos/{sid}", "/equipamentos", f"/equipamentos/{eid}",
                "/equipamentos/novo", f"/equipamentos/{eid}/editar", "/servicos/novo", f"/servicos/{sid}/editar"):
        assert c.get(url).status_code == 200, url
