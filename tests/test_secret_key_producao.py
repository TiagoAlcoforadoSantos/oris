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


def test_producao_recusa_chave_padrao():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProducaoComChavePadrao)


def test_producao_recusa_chave_vazia():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProducaoSemChave)


def test_producao_aceita_chave_propria():
    app = create_app(ProducaoComChaveForte)
    assert app.config["SECRET_KEY"] == "k" * 48
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_desenvolvimento_e_testes_continuam_com_chave_padrao():
    assert create_app(DevelopmentConfig).config["SECRET_KEY"] == SECRET_KEY_PADRAO
    assert create_app(TestingConfig).config["SECRET_KEY"] == SECRET_KEY_PADRAO
