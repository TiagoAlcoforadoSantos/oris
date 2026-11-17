"""Criptografia autenticada para dados sensíveis armazenados pelo ORIS."""

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

PREFIXO_TEXTO_CIFRADO = "oris-fernet-v1:"


class DadosCifradosInvalidos(Exception):
    """O conteúdo cifrado foi alterado ou não corresponde à chave configurada."""


def _cifrador(chave=None):
    chave = chave if chave is not None else current_app.config.get("DATA_ENCRYPTION_KEY")
    if not chave:
        raise RuntimeError("DATA_ENCRYPTION_KEY não configurada.")
    try:
        if isinstance(chave, str):
            chave = chave.encode("ascii")
        return Fernet(chave)
    except (TypeError, ValueError, UnicodeEncodeError) as erro:
        raise RuntimeError("DATA_ENCRYPTION_KEY inválida; gere uma chave Fernet válida.") from erro


def validar_chave(chave):
    """Valida a chave durante a inicialização, antes de aceitar dados."""
    _cifrador(chave)


def cifrar_bytes(conteudo):
    return _cifrador().encrypt(conteudo)


def decifrar_bytes(conteudo):
    try:
        return _cifrador().decrypt(conteudo)
    except InvalidToken as erro:
        raise DadosCifradosInvalidos("O conteúdo cifrado não pôde ser validado.") from erro


def cifrar_texto(conteudo):
    cifrado = cifrar_bytes(conteudo.encode("utf-8")).decode("ascii")
    return PREFIXO_TEXTO_CIFRADO + cifrado


def decifrar_texto(conteudo):
    if not conteudo or not conteudo.startswith(PREFIXO_TEXTO_CIFRADO):
        return conteudo
    cifrado = conteudo[len(PREFIXO_TEXTO_CIFRADO):].encode("ascii")
    return decifrar_bytes(cifrado).decode("utf-8")
