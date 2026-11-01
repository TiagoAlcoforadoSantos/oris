"""
Testes da ETAPA 03 — módulo Banco de Dados (SQL explícito).

Duas camadas:

1. Testes que NÃO precisam de MySQL (rodam sempre, com SQLite da suíte):
   catálogo de consultas, validação de parâmetros e controle de acesso
   (login e RBAC são verificados antes de qualquer acesso ao banco).

2. Testes de integração contra MySQL/MariaDB REAL — rodam só quando a
   variável ORIS_TEST_MYSQL=1 estiver definida e o banco configurado no
   .env estiver populado com database/seed_etapa03.sql:

       ORIS_TEST_MYSQL=1 pytest tests/test_etapa03_bd.py
"""

import os
import re

import pytest

from app import create_app
from app.bd import consultas
from app.extensions import db
from app.models import PerfilUsuario, Usuario
from app.utils.security import gerar_hash_senha
from config import DevelopmentConfig, TestingConfig

SENHA = "SenhaForte123!"


# ----------------------------------------------------------------------
# 1) Sem MySQL
# ----------------------------------------------------------------------

def test_catalogo_tem_pelo_menos_4_consultas_e_uma_com_join():
    assert len(consultas.CONSULTAS) >= 4
    assert any(re.search(r"\bJOIN\b", c["sql"], re.I) for c in consultas.CONSULTAS)


def test_ids_unicos_e_campos_obrigatorios():
    ids = [c["id"] for c in consultas.CONSULTAS]
    assert len(ids) == len(set(ids))
    for c in consultas.CONSULTAS:
        for campo in ("titulo", "pergunta", "nivel", "conceitos", "sql", "parametros"):
            assert c[campo] is not None


def test_parametros_do_sql_batem_com_os_declarados():
    for c in consultas.CONSULTAS:
        usados = set(re.findall(r"%\((\w+)\)s", c["sql"]))
        declarados = {p["nome"] for p in c["parametros"]}
        assert usados == declarados, c["id"]
        # Com parâmetros nomeados, um '%' solto quebraria a formatação do driver
        sem_params = re.sub(r"%\(\w+\)s", "", c["sql"])
        assert "%" not in sem_params, c["id"]


def test_ler_parametros_limita_inteiros_e_aplica_whitelist():
    c2 = consultas.CONSULTAS_POR_ID["c2"]
    assert consultas.ler_parametros(c2, {"minimo": "999999"})["minimo"] == 100
    assert consultas.ler_parametros(c2, {"minimo": "abc"})["minimo"] == 1
    c1 = consultas.CONSULTAS_POR_ID["c1"]
    assert consultas.ler_parametros(c1, {"situacao": "ATIVA' OR 1=1 --"})["situacao"] is None
    assert consultas.ler_parametros(c1, {"situacao": "ATIVA"})["situacao"] == "ATIVA"


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


def test_rotas_bd_exigem_login(app_sqlite):
    c = app_sqlite.test_client()
    for url in ("/bd", "/bd/unidades", "/bd/consultas", "/bd/consultas/c1", "/bd/estatistica"):
        resposta = c.get(url)
        assert resposta.status_code == 302 and "/login" in resposta.headers["Location"]


def test_gestor_nao_pode_inserir_alterar_ou_excluir(app_sqlite):
    c = app_sqlite.test_client()
    c.post("/login", data={"email": "gestor@oris.com.br", "senha": SENHA})
    for entidade in ("unidades", "servicos", "equipamentos"):
        assert c.get(f"/bd/{entidade}/novo").status_code == 403
        assert c.post(f"/bd/{entidade}/novo", data={}).status_code == 403
        assert c.get(f"/bd/{entidade}/1/editar").status_code == 403
        assert c.post(f"/bd/{entidade}/1/excluir").status_code == 403


# ----------------------------------------------------------------------
# 2) Integração com MySQL real
# ----------------------------------------------------------------------

mysql = pytest.mark.skipif(os.getenv("ORIS_TEST_MYSQL") != "1",
                           reason="defina ORIS_TEST_MYSQL=1 para testar contra o MySQL")


class MySQLTestConfig(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATE_LIMIT_LOGIN_ENABLED = False


@pytest.fixture
def cliente_admin():
    app = create_app(MySQLTestConfig)
    c = app.test_client()
    c.post("/login", data={"email": "admin.demo@oris.example", "senha": "Oris@2026"})
    return app, c


@mysql
def test_todas_as_consultas_executam_no_mysql(cliente_admin):
    app, c = cliente_admin
    with app.app_context():
        for consulta in consultas.CONSULTAS:
            params = consultas.ler_parametros(consulta, {})
            colunas, _ = consultas.executar(consulta["id"], params)
            assert colunas, consulta["id"]
    for consulta in consultas.CONSULTAS:
        assert c.get(f"/bd/consultas/{consulta['id']}").status_code == 200


@mysql
def test_telas_abrem(cliente_admin):
    _, c = cliente_admin
    for url in ("/bd", "/bd/unidades", "/bd/servicos", "/bd/equipamentos",
                "/bd/estatistica", "/bd/consultas"):
        assert c.get(url).status_code == 200, url


@mysql
def test_ciclo_insert_update_delete_com_integridade(cliente_admin):
    app, c = cliente_admin
    from app.bd import dao_servicos, dao_unidades

    c.post("/bd/unidades/novo", data={
        "nome": "USF Pytest", "cnes": "9188888", "tipo": "USF",
        "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"})
    with app.app_context():
        uid = dao_unidades.listar(busca="USF Pytest")[0]["id"]

    c.post(f"/bd/unidades/{uid}/editar", data={
        "nome": "USF Pytest 2", "cnes": "9188888", "tipo": "USF",
        "cidade": "Recife", "uf": "PE", "situacao": "MANUTENCAO"})
    c.post("/bd/servicos/novo", data={"nome": "Serv Pytest", "unidade_id": str(uid),
                                      "situacao": "ATIVO"})
    with app.app_context():
        assert dao_unidades.buscar(uid)["situacao"] == "MANUTENCAO"
        sid = dao_servicos.listar(unidade_id=uid)[0]["id"]

    # Exclusão bloqueada pela integridade referencial
    r = c.post(f"/bd/unidades/{uid}/excluir", follow_redirects=True)
    assert "integridade referencial" in r.get_data(as_text=True)

    c.post(f"/bd/servicos/{sid}/excluir")
    c.post(f"/bd/unidades/{uid}/excluir")
    with app.app_context():
        assert dao_unidades.buscar(uid) is None
