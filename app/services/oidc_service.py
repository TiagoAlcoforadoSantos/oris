"""
Login via OpenID Connect (Requisito 3 — consumo de credenciais OIDC).

Fluxo Authorization Code com PKCE (S256):

1. `iniciar_autorizacao` monta a URL do provedor (descoberta via
   `/.well-known/openid-configuration`) e gera `state`, `nonce` e
   `code_verifier` — guardados na sessão do navegador.
2. O provedor redireciona de volta com `code` e `state`; a rota
   confere o `state` (anti-CSRF).
3. `concluir_autorizacao` troca o `code` no endpoint de token (canal
   direto servidor-a-servidor, por HTTPS), valida `iss`, `aud` e
   `nonce` do id_token e lê as claims (sub, nome, e-mail, grupos) do
   `userinfo`. Como o id_token chega direto do provedor por TLS, a
   assinatura dele não precisa ser revalidada (OIDC Core, 3.1.3.7).
4. As claims viram um `UsuarioExterno`, provisionado nas tabelas locais
   por app/services/diretorio_service.py.

Só usa a biblioteca padrão (urllib). Endpoints http:// são recusados
exceto com OIDC_ALLOW_INSECURE=true (laboratório).
"""

import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request

from flask import current_app

from app.services.diretorio_service import DiretorioConfigError, UsuarioExterno

TIMEOUT_SEGUNDOS = 10


class OidcError(Exception):
    """Falha no fluxo OIDC (mensagem segura para log; ao usuário vai
    sempre uma mensagem genérica)."""


def oidc_habilitado(config=None):
    config = config if config is not None else current_app.config
    return bool(
        config.get("OIDC_ENABLED") and config.get("OIDC_ISSUER") and config.get("OIDC_CLIENT_ID")
    )


def _exigir_https(url, config):
    if not url.lower().startswith("https://") and not config.get("OIDC_ALLOW_INSECURE"):
        raise DiretorioConfigError(f"Endpoint OIDC sem HTTPS recusado: {url}")


def _http_get_json(url, cabecalhos=None):
    requisicao = urllib.request.Request(url, headers=cabecalhos or {})
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:  # noqa: S310
        return json.loads(resposta.read().decode("utf-8"))


def _http_post_form(url, dados):
    corpo = urllib.parse.urlencode(dados).encode("utf-8")
    requisicao = urllib.request.Request(
        url, data=corpo, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:  # noqa: S310
        return json.loads(resposta.read().decode("utf-8"))


def _descobrir(config):
    issuer = config["OIDC_ISSUER"].rstrip("/")
    _exigir_https(issuer, config)
    return _http_get_json(f"{issuer}/.well-known/openid-configuration")


def _b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def iniciar_autorizacao(redirect_uri, config=None):
    """Devolve (url_de_autorizacao, estado). `estado` deve ser guardado
    na sessão até o callback."""
    config = config if config is not None else current_app.config
    metadados = _descobrir(config)

    estado = {
        "state": secrets.token_urlsafe(24),
        "nonce": secrets.token_urlsafe(24),
        "code_verifier": secrets.token_urlsafe(48),
    }
    desafio = _b64url(hashlib.sha256(estado["code_verifier"].encode("ascii")).digest())
    parametros = {
        "response_type": "code",
        "client_id": config["OIDC_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "scope": config.get("OIDC_SCOPES", "openid profile email"),
        "state": estado["state"],
        "nonce": estado["nonce"],
        "code_challenge": desafio,
        "code_challenge_method": "S256",
    }
    url = f"{metadados['authorization_endpoint']}?{urllib.parse.urlencode(parametros)}"
    return url, estado


def _payload_jwt(token):
    try:
        carga = token.split(".")[1]
        carga += "=" * (-len(carga) % 4)
        return json.loads(base64.urlsafe_b64decode(carga.encode("ascii")))
    except (IndexError, ValueError) as erro:
        raise OidcError("id_token malformado.") from erro


def concluir_autorizacao(codigo, estado, redirect_uri, config=None):
    """Troca o `code` por tokens, valida o id_token e devolve um
    `UsuarioExterno` com as claims do usuário."""
    config = config if config is not None else current_app.config
    metadados = _descobrir(config)
    _exigir_https(metadados["token_endpoint"], config)

    tokens = _http_post_form(
        metadados["token_endpoint"],
        {
            "grant_type": "authorization_code",
            "code": codigo,
            "redirect_uri": redirect_uri,
            "client_id": config["OIDC_CLIENT_ID"],
            "client_secret": config.get("OIDC_CLIENT_SECRET", ""),
            "code_verifier": estado["code_verifier"],
        },
    )

    id_token = tokens.get("id_token")
    if not id_token:
        raise OidcError("Resposta sem id_token.")
    claims = _payload_jwt(id_token)

    if claims.get("iss", "").rstrip("/") != config["OIDC_ISSUER"].rstrip("/"):
        raise OidcError("Emissor (iss) do id_token inesperado.")
    audiencia = claims.get("aud")
    audiencias = audiencia if isinstance(audiencia, list) else [audiencia]
    if config["OIDC_CLIENT_ID"] not in audiencias:
        raise OidcError("Audiência (aud) do id_token inesperada.")
    if not secrets.compare_digest(str(claims.get("nonce", "")), estado["nonce"]):
        raise OidcError("nonce do id_token não confere.")

    if tokens.get("access_token") and metadados.get("userinfo_endpoint"):
        _exigir_https(metadados["userinfo_endpoint"], config)
        info = _http_get_json(
            metadados["userinfo_endpoint"], {"Authorization": f"Bearer {tokens['access_token']}"}
        )
        if info.get("sub") != claims.get("sub"):
            raise OidcError("sub do userinfo difere do id_token.")
        claims = {**claims, **info}

    if claims.get("email_verified") is not True:
        raise OidcError("E-mail não verificado no provedor.")

    grupos = claims.get(config.get("OIDC_CLAIM_GROUPS", "groups"), []) or []
    if isinstance(grupos, str):
        grupos = [grupos]

    return UsuarioExterno(
        identificador=str(claims.get("sub", "")),
        nome=claims.get("name") or claims.get("preferred_username") or "",
        email=claims.get("email", ""),
        grupos=[str(g) for g in grupos],
    )
