"""
Testes da FASE 1 — estrutura inicial do projeto.

Nesta fase ainda não existem models de negócio, login ou rotas de
CRUD. O objetivo aqui é apenas garantir que:

- a aplicação Flask é criada corretamente;
- a configuração é carregada;
- a rota de health check responde;
- rotas inexistentes retornam 404.

Usamos a configuração de TESTE (SQLite em memória) para não
depender de um MySQL real durante a suíte automatizada.
"""

from app import create_app
from config import TestingConfig


def _make_test_client():
    app = create_app(TestingConfig)
    return app.test_client()


def test_app_e_criada_com_sucesso():
    app = create_app(TestingConfig)
    assert app is not None
    assert app.config["TESTING"] is True


def test_health_check_retorna_ok():
    client = _make_test_client()
    response = client.get("/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["app"] == "ORIS"


def test_rota_inexistente_retorna_404():
    client = _make_test_client()
    response = client.get("/uma-rota-que-nao-existe")

    assert response.status_code == 404
