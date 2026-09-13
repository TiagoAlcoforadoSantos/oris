"""
Rate limiting leve para tentativas de login (Fase 12 — achado
SEC-005).

Implementação propositalmente simples: um dicionário em memória do
próprio processo, sem Redis nem infraestrutura externa — adequado ao
escopo acadêmico do ORIS. Isso significa que o contador zera se a
aplicação for reiniciada, e não é compartilhado entre múltiplos
processos/workers; para produção com múltiplos workers, a
recomendação (documentada em docs/SEGURANCA.md) é usar um backend
compartilhado (ex.: Redis) — fora do escopo desta fase.

A trava é por (endereço IP, email tentado), para não bloquear todo o
prédio/rede por causa de uma única conta, nem deixar um único IP
tentar todas as contas do sistema sem limite.
"""

import time
from collections import defaultdict
from threading import Lock

JANELA_SEGUNDOS = 5 * 60  # 5 minutos
LIMITE_TENTATIVAS = 5

_tentativas = defaultdict(list)
_lock = Lock()


def _chave(ip, email):
    return (ip or "desconhecido", (email or "").strip().lower())


def registrar_tentativa_falha(ip, email):
    """Registra uma tentativa de login malsucedida para (ip, email)."""
    agora = time.time()
    with _lock:
        chave = _chave(ip, email)
        _tentativas[chave] = [t for t in _tentativas[chave] if agora - t < JANELA_SEGUNDOS]
        _tentativas[chave].append(agora)


def limpar_tentativas(ip, email):
    """Zera o contador após um login bem-sucedido."""
    with _lock:
        _tentativas.pop(_chave(ip, email), None)


def bloqueado(ip, email):
    """True se (ip, email) excedeu o limite de tentativas na janela
    atual — o chamador decide a mensagem/; nunca revela aqui se a
    conta existe ou não."""
    agora = time.time()
    with _lock:
        chave = _chave(ip, email)
        tentativas_recentes = [t for t in _tentativas[chave] if agora - t < JANELA_SEGUNDOS]
        _tentativas[chave] = tentativas_recentes
        return len(tentativas_recentes) >= LIMITE_TENTATIVAS
