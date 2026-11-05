"""Rate limiting leve para tentativas de login (Fase 12 - achado SEC-005)."""

import time
from threading import Lock

JANELA_SEGUNDOS = 5 * 60  # 5 minutos
LIMITE_TENTATIVAS = 5

# Teto de chaves (IP, email) mantidas em memória. Sem ele, um atacante que varie
# o email a cada requisição faria o dicionário crescer indefinidamente.
MAX_CHAVES = 10_000

_tentativas = {}
_lock = Lock()


def _chave(ip, email):
    return (ip or "desconhecido", (email or "").strip().lower())


def _recentes(tentativas, agora):
    return [t for t in tentativas if agora - t < JANELA_SEGUNDOS]


def _purgar(agora):
    """Remove chaves expiradas; se ainda exceder o teto, descarta as mais antigas.

    Deve ser chamada com `_lock` já adquirido.
    """
    for chave in [c for c, ts in _tentativas.items() if not _recentes(ts, agora)]:
        del _tentativas[chave]

    # Deixa uma vaga livre para a chave que está prestes a ser inserida.
    excesso = len(_tentativas) - (MAX_CHAVES - 1)
    if excesso > 0:
        mais_antigas = sorted(_tentativas, key=lambda c: max(_tentativas[c]))[:excesso]
        for chave in mais_antigas:
            del _tentativas[chave]


def registrar_tentativa_falha(ip, email):
    """Registra uma tentativa de login malsucedida para (ip, email)."""
    agora = time.time()
    with _lock:
        chave = _chave(ip, email)
        if chave not in _tentativas and len(_tentativas) >= MAX_CHAVES:
            _purgar(agora)
        _tentativas[chave] = _recentes(_tentativas.get(chave, []), agora) + [agora]


def limpar_tentativas(ip, email):
    """Zera o contador após um login bem-sucedido."""
    with _lock:
        _tentativas.pop(_chave(ip, email), None)


def bloqueado(ip, email):
    """True se (ip, email) excedeu o limite de tentativas na janela atual - o chamador
    decide o que fazer (a rota de login exibe uma mensagem genérica).

    Apenas consulta: não cria entradas para chaves que nunca falharam.
    """
    agora = time.time()
    with _lock:
        chave = _chave(ip, email)
        tentativas_recentes = _recentes(_tentativas.get(chave, []), agora)
        if tentativas_recentes:
            _tentativas[chave] = tentativas_recentes
        else:
            _tentativas.pop(chave, None)
        return len(tentativas_recentes) >= LIMITE_TENTATIVAS
