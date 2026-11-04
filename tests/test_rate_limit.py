"""Testes unitários do rate limiting de login (SEC-005)."""

import pytest

from app.utils import rate_limit


@pytest.fixture(autouse=True)
def estado_limpo():
    rate_limit._tentativas.clear()
    yield
    rate_limit._tentativas.clear()


def _falhar(n, ip="10.0.0.1", email="a@oris.com.br"):
    for _ in range(n):
        rate_limit.registrar_tentativa_falha(ip, email)


def test_bloqueia_ao_atingir_o_limite():
    _falhar(rate_limit.LIMITE_TENTATIVAS - 1)
    assert not rate_limit.bloqueado("10.0.0.1", "a@oris.com.br")
    _falhar(1)
    assert rate_limit.bloqueado("10.0.0.1", "a@oris.com.br")


def test_chave_normaliza_email_e_separa_por_ip():
    _falhar(rate_limit.LIMITE_TENTATIVAS, email="  A@Oris.com.br ")
    assert rate_limit.bloqueado("10.0.0.1", "a@oris.com.br")
    assert not rate_limit.bloqueado("10.0.0.2", "a@oris.com.br")


def test_limpar_zera_o_contador():
    _falhar(rate_limit.LIMITE_TENTATIVAS)
    rate_limit.limpar_tentativas("10.0.0.1", "a@oris.com.br")
    assert not rate_limit.bloqueado("10.0.0.1", "a@oris.com.br")


def test_consultar_nao_cria_entradas():
    for i in range(50):
        assert not rate_limit.bloqueado("10.0.0.1", f"inexistente{i}@oris.com.br")
    assert rate_limit._tentativas == {}


def test_tentativas_expiradas_deixam_de_bloquear(monkeypatch):
    agora = 1_000_000.0
    monkeypatch.setattr(rate_limit.time, "time", lambda: agora)
    _falhar(rate_limit.LIMITE_TENTATIVAS)
    assert rate_limit.bloqueado("10.0.0.1", "a@oris.com.br")

    monkeypatch.setattr(rate_limit.time, "time", lambda: agora + rate_limit.JANELA_SEGUNDOS + 1)
    assert not rate_limit.bloqueado("10.0.0.1", "a@oris.com.br")
    assert ("10.0.0.1", "a@oris.com.br") not in rate_limit._tentativas


def test_memoria_nao_cresce_alem_do_teto(monkeypatch):
    monkeypatch.setattr(rate_limit, "MAX_CHAVES", 50)
    for i in range(500):
        rate_limit.registrar_tentativa_falha("10.0.0.1", f"u{i}@oris.com.br")
    assert len(rate_limit._tentativas) <= 50


def test_purga_remove_expiradas_antes_de_descartar_recentes(monkeypatch):
    monkeypatch.setattr(rate_limit, "MAX_CHAVES", 3)
    agora = 2_000_000.0
    monkeypatch.setattr(rate_limit.time, "time", lambda: agora)
    for i in range(3):
        rate_limit.registrar_tentativa_falha("ip", f"velho{i}@x.com")

    monkeypatch.setattr(rate_limit.time, "time", lambda: agora + rate_limit.JANELA_SEGUNDOS + 1)
    rate_limit.registrar_tentativa_falha("ip", "novo@x.com")
    assert list(rate_limit._tentativas) == [("ip", "novo@x.com")]
