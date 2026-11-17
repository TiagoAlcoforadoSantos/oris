"""Segurança: a aplicação não pode iniciar em produção com SECRET_KEY padrão."""

import pytest

from app import create_app
from config import (DevelopmentConfig, ProductionConfig, SECRET_KEY_PADRAO,
                    TestingConfig)


class ProducaoComChavePadrao(ProductionConfig):
    SECRET_KEY = SECRET_KEY_PADRAO


class ProducaoSemChave(ProductionConfig):
    SECRET_KEY = ""


class ProducaoComChaveForte(ProductionConfig):
    SECRET_KEY = "k" * 48
    DATA_ENCRYPTION_KEY = "8YUlDwN5PXNRQGa8BFCUZkwAA95sjPiITg3aJ8u0MZs="


def test_producao_recusa_chave_padrao():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProducaoComChavePadrao)


def test_producao_recusa_chave_vazia():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProducaoSemChave)


def test_producao_recusa_chave_de_criptografia_ausente():
    class ProducaoSemChaveDeDados(ProductionConfig):
        SECRET_KEY = "k" * 48
        DATA_ENCRYPTION_KEY = ""

    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEY"):
        create_app(ProducaoSemChaveDeDados)


def test_producao_aceita_chave_propria():
    app = create_app(ProducaoComChaveForte)
    assert app.config["SECRET_KEY"] == "k" * 48
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_desenvolvimento_e_testes_inicializam_com_chave_de_dados():
    class DesenvolvimentoComChaveDeDados(DevelopmentConfig):
        DATA_ENCRYPTION_KEY = "8YUlDwN5PXNRQGa8BFCUZkwAA95sjPiITg3aJ8u0MZs="

    assert create_app(DesenvolvimentoComChaveDeDados).config["DATA_ENCRYPTION_KEY"]
    assert create_app(TestingConfig).config["SECRET_KEY"]
