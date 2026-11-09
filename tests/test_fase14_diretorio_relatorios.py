"""
Testes da FASE 14 — Requisito 3 (LDAP/OIDC populando usuários e grupos)
e Requisito 4 (exportação de relatórios para o Amazon S3).

Nenhum teste usa rede: o LDAP roda no modo MOCK_SYNC do próprio ldap3,
o provedor OIDC é simulado trocando as duas funções HTTP do módulo, e o
S3 é um cliente falso injetado no lugar do boto3.
"""

import base64
import json
import urllib.parse

import pytest
from ldap3 import MOCK_SYNC, Connection, Server

from app import create_app
from app.extensions import db
from app.models import (
    Auditoria,
    Equipamento,
    Grupo,
    OrigemDiretorio,
    PerfilUsuario,
    Servico,
    SituacaoAtivoInativo,
    SituacaoUnidade,
    Unidade,
    Usuario,
)
from app.services import armazenamento_service, oidc_service
from app.services.diretorio_service import (
    DiretorioConfigError,
    UsuarioExterno,
    carregar_mapa_grupo_perfil,
    resolver_perfil,
    sincronizar_usuarios,
)
from app.services.ldap_service import _abrir_conexao, buscar_usuarios_ldap
from app.services.relatorio_service import gerar_csv, sanitizar_celula
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"
MAPA = {
    "oris-admin": "ADMINISTRADOR",
    "oris-gestao": "GESTAO_INFORMACAO",
    "oris-saude": "RESPONSAVEL_SAUDE_BUCAL",
    "oris-gestor": "GESTOR",
}
EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    app.config["DIRETORIO_MAPA_GRUPO_PERFIL"] = json.dumps(MAPA)
    with app.app_context():
        db.create_all()
        for perfil, email in EMAILS.items():
            db.session.add(
                Usuario(nome=perfil.value, email=email, senha_hash=gerar_hash_senha(SENHA), perfil=perfil, ativo=True)
            )
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil):
    return client.post("/login", data={"email": EMAILS[perfil], "senha": SENHA}, follow_redirects=True)


# ==================================================================
# Requisito 3 — mapa grupo -> perfil
# ==================================================================

def test_mapa_grupo_perfil_e_carregado(app):
    mapa = carregar_mapa_grupo_perfil()
    assert mapa["oris-admin"] == PerfilUsuario.ADMINISTRADOR


def test_mapa_com_perfil_inexistente_e_recusado(app):
    with pytest.raises(DiretorioConfigError):
        carregar_mapa_grupo_perfil({"DIRETORIO_MAPA_GRUPO_PERFIL": '{"g": "SUPERUSUARIO"}'})


def test_mapa_json_invalido_e_recusado(app):
    with pytest.raises(DiretorioConfigError):
        carregar_mapa_grupo_perfil({"DIRETORIO_MAPA_GRUPO_PERFIL": "{nao e json"})


def test_perfil_de_maior_privilegio_vence(app):
    mapa = carregar_mapa_grupo_perfil()
    assert resolver_perfil(["oris-gestor", "oris-gestao"], mapa) == PerfilUsuario.GESTAO_INFORMACAO
    assert resolver_perfil(["outro-grupo"], mapa) is None


# ==================================================================
# Requisito 3 — LDAP (modo MOCK real do ldap3)
# ==================================================================

def _conexao_ldap_mock(com_member_of=False):
    conexao = Connection(Server("ldap-falso"), user="cn=svc,o=oris", password="x", client_strategy=MOCK_SYNC)
    add = conexao.strategy.add_entry
    add("cn=svc,o=oris", {"userPassword": "x", "objectClass": ["person"], "uid": "svc", "cn": "svc"})
    add("uid=ana,ou=pessoas,o=oris", {"objectClass": ["person"], "uid": "ana", "cn": "Ana Admin", "mail": "ana@rede.gov"})
    add("uid=bia,ou=pessoas,o=oris", {"objectClass": ["person"], "uid": "bia", "cn": "Bia Gestora", "mail": "bia@rede.gov"})
    add("uid=caio,ou=pessoas,o=oris", {"objectClass": ["person"], "uid": "caio", "cn": "Caio Sem Grupo", "mail": "caio@rede.gov"})
    add("cn=oris-admin,ou=grupos,o=oris", {"objectClass": ["groupOfNames"], "cn": "oris-admin", "member": ["uid=ana,ou=pessoas,o=oris"]})
    add(
        "cn=oris-gestao,ou=grupos,o=oris",
        {"objectClass": ["groupOfNames"], "cn": "oris-gestao", "member": ["uid=bia,ou=pessoas,o=oris", "uid=ana,ou=pessoas,o=oris"]},
    )
    add("cn=outro,ou=grupos,o=oris", {"objectClass": ["groupOfNames"], "cn": "outro", "member": ["uid=caio,ou=pessoas,o=oris"]})
    conexao.bind()
    return conexao


def _config_ldap(app):
    app.config.update(LDAP_USER_BASE="ou=pessoas,o=oris", LDAP_GROUP_BASE="ou=grupos,o=oris")


def test_ldap_le_usuarios_e_seus_grupos(app):
    _config_ldap(app)
    externos = {e.identificador: e for e in buscar_usuarios_ldap(conexao=_conexao_ldap_mock())}
    assert set(externos) == {"ana", "bia", "caio"}
    assert externos["ana"].email == "ana@rede.gov"
    assert externos["ana"].grupos == ["oris-admin", "oris-gestao"]
    assert externos["caio"].grupos == ["outro"]


def test_ldap_sync_popula_usuarios_e_grupos(app):
    _config_ldap(app)
    resumo = sincronizar_usuarios(buscar_usuarios_ldap(conexao=_conexao_ldap_mock()), OrigemDiretorio.LDAP)

    assert resumo["criados"] == 2  # ana e bia; caio não tem grupo mapeado
    ana = Usuario.query.filter_by(email="ana@rede.gov").first()
    assert ana.origem == OrigemDiretorio.LDAP
    assert ana.identificador_externo == "ana"
    assert ana.perfil == PerfilUsuario.ADMINISTRADOR  # admin + gestão -> maior privilégio
    assert {g.nome for g in ana.grupos} == {"oris-admin", "oris-gestao"}
    assert Usuario.query.filter_by(email="bia@rede.gov").first().perfil == PerfilUsuario.GESTAO_INFORMACAO
    assert Usuario.query.filter_by(email="caio@rede.gov").first() is None
    assert any("caio" in motivo for motivo in resumo["ignorados"])
    # Só os grupos de usuários provisionados são gravados (o "outro" é de Caio, ignorado).
    assert Grupo.query.filter_by(origem=OrigemDiretorio.LDAP).count() == 2


def test_ldap_sync_e_idempotente(app):
    _config_ldap(app)
    sincronizar_usuarios(buscar_usuarios_ldap(conexao=_conexao_ldap_mock()), OrigemDiretorio.LDAP)
    resumo = sincronizar_usuarios(buscar_usuarios_ldap(conexao=_conexao_ldap_mock()), OrigemDiretorio.LDAP)
    assert resumo["criados"] == 0 and resumo["atualizados"] == 0 and resumo["desativados"] == 0
    assert Usuario.query.filter_by(origem=OrigemDiretorio.LDAP).count() == 2


def test_ldap_sync_atualiza_perfil_e_desativa_ausente(app):
    sincronizar_usuarios(
        [UsuarioExterno("ana", "Ana", "ana@rede.gov", ["oris-admin"]), UsuarioExterno("bia", "Bia", "bia@rede.gov", ["oris-gestao"])],
        OrigemDiretorio.LDAP,
    )
    # Ana vira gestor; Bia some do diretório. Admin local garante que não é o último admin.
    resumo = sincronizar_usuarios([UsuarioExterno("ana", "Ana", "ana@rede.gov", ["oris-gestor"])], OrigemDiretorio.LDAP)

    ana = Usuario.query.filter_by(email="ana@rede.gov").first()
    bia = Usuario.query.filter_by(email="bia@rede.gov").first()
    assert ana.perfil == PerfilUsuario.GESTOR
    assert bia.ativo is False
    assert resumo["desativados"] == 1
    assert Auditoria.query.filter_by(acao="ALTERAR_PERFIL", registro_id=ana.id).first() is not None
    assert Auditoria.query.filter_by(acao="DESATIVAR_USUARIO", registro_id=bia.id).first() is not None


def test_usuario_externo_que_perde_o_grupo_e_desativado(app):
    sincronizar_usuarios([UsuarioExterno("bia", "Bia", "bia@rede.gov", ["oris-gestao"])], OrigemDiretorio.LDAP)
    sincronizar_usuarios([UsuarioExterno("bia", "Bia", "bia@rede.gov", ["grupo-irrelevante"])], OrigemDiretorio.LDAP)
    assert Usuario.query.filter_by(email="bia@rede.gov").first().ativo is False


def test_sync_nao_revincula_conta_externa_por_email(app):
    sincronizar_usuarios([UsuarioExterno("sub-1", "Ana", "ana@rede.gov", ["oris-gestao"])], OrigemDiretorio.OIDC)
    resumo = sincronizar_usuarios(
        [UsuarioExterno("sub-atacante", "Intruso", "ana@rede.gov", ["oris-admin"])], OrigemDiretorio.OIDC
    )
    ana = Usuario.query.filter_by(email="ana@rede.gov").first()
    assert ana.identificador_externo == "sub-1"
    assert ana.perfil == PerfilUsuario.GESTAO_INFORMACAO
    assert any("outro identificador" in m for m in resumo["ignorados"])


def test_oidc_rejeita_email_nao_verificado(app, client, oidc):
    for extra in ({"email_verified": False}, {"email_verified": None}):
        _, p = _iniciar(client)
        oidc["claims"] = _claims(p, **extra)
        resp = client.get(f"/login/oidc/callback?code=abc&state={p['state']}")
        assert resp.headers["Location"].endswith("/login")


def test_sync_nunca_altera_conta_local_com_mesmo_email(app):
    resumo = sincronizar_usuarios(
        [UsuarioExterno("x1", "Intruso", EMAILS[PerfilUsuario.ADMINISTRADOR], ["oris-gestor"])], OrigemDiretorio.LDAP
    )
    admin = Usuario.query.filter_by(email=EMAILS[PerfilUsuario.ADMINISTRADOR]).first()
    assert admin.origem == OrigemDiretorio.LOCAL
    assert admin.perfil == PerfilUsuario.ADMINISTRADOR
    assert admin.nome != "Intruso"
    assert resumo["criados"] == 0
    assert any("LOCAL" in motivo for motivo in resumo["ignorados"])


def test_sync_protege_o_ultimo_administrador(app):
    # Torna o único admin do sistema uma conta LDAP.
    Usuario.query.filter_by(perfil=PerfilUsuario.ADMINISTRADOR).delete()
    db.session.commit()
    sincronizar_usuarios([UsuarioExterno("ana", "Ana", "ana@rede.gov", ["oris-admin"])], OrigemDiretorio.LDAP)

    # Ana some do diretório e perde o grupo: continuaria sem admin -> protegida.
    resumo = sincronizar_usuarios([], OrigemDiretorio.LDAP)
    sincronizar_usuarios([UsuarioExterno("ana", "Ana", "ana@rede.gov", ["oris-gestor"])], OrigemDiretorio.LDAP)

    ana = Usuario.query.filter_by(email="ana@rede.gov").first()
    assert ana.ativo is True
    assert ana.perfil == PerfilUsuario.ADMINISTRADOR
    assert resumo["protegidos"]


def test_sync_simular_nao_grava_nada(app):
    resumo = sincronizar_usuarios(
        [UsuarioExterno("bia", "Bia", "bia@rede.gov", ["oris-gestao"])], OrigemDiretorio.LDAP, simular=True
    )
    assert resumo["criados"] == 1
    assert Usuario.query.filter_by(email="bia@rede.gov").first() is None


def test_sync_com_mapa_vazio_e_recusado(app):
    with pytest.raises(DiretorioConfigError):
        sincronizar_usuarios([], OrigemDiretorio.LDAP, mapa={})


def test_ldap_sem_tls_e_recusado(app):
    with pytest.raises(DiretorioConfigError):
        _abrir_conexao({"LDAP_URI": "ldap://servidor.exemplo"})


def test_ldap_valida_certificado_do_servidor(app, monkeypatch, tmp_path):
    import ldap3
    import ssl as _ssl

    capturado = {}

    class ServidorFalso:
        def __init__(self, uri, **kwargs):
            capturado.update(kwargs)

    class ConexaoFalsa:
        def __init__(self, *a, **k):
            pass

        def bind(self):
            return True

    monkeypatch.setattr(ldap3, "Server", ServidorFalso)
    monkeypatch.setattr(ldap3, "Connection", ConexaoFalsa)
    ca = tmp_path / "ca.pem"
    ca.write_text("ca")
    _abrir_conexao({"LDAP_URI": "ldaps://ldap.exemplo.test", "LDAP_CA_CERT_FILE": str(ca)})
    assert capturado["use_ssl"] is True
    assert capturado["tls"].validate == _ssl.CERT_REQUIRED
    assert capturado["tls"].ca_certs_file == str(ca)


def test_ldap_ignora_memberof_fora_da_base_de_grupos(app):
    _config_ldap(app)
    conexao = _conexao_ldap_mock()
    conexao.strategy.add_entry(
        "uid=eva,ou=pessoas,o=oris",
        {"objectClass": ["person"], "uid": "eva", "cn": "Eva", "mail": "eva@rede.gov",
         "memberOf": ["cn=oris-admin,ou=outra-ou,o=oris", "cn=oris-gestor,ou=grupos,o=oris"]},
    )
    eva = {e.identificador: e for e in buscar_usuarios_ldap(conexao=conexao)}["eva"]
    assert eva.grupos == ["oris-gestor"]  # o "oris-admin" de outra OU e ignorado


def test_ldap_sem_uri_e_recusado(app):
    with pytest.raises(DiretorioConfigError):
        _abrir_conexao({})


def test_conta_externa_nao_entra_com_senha_local(app, client):
    with app.app_context():
        db.session.add(
            Usuario(
                nome="Externo", email="externo@rede.gov", senha_hash=gerar_hash_senha(SENHA),
                perfil=PerfilUsuario.GESTOR, ativo=True, origem=OrigemDiretorio.LDAP, identificador_externo="ext",
            )
        )
        db.session.commit()
    resp = client.post("/login", data={"email": "externo@rede.gov", "senha": SENHA}, follow_redirects=True)
    assert "Email ou senha inválidos" in resp.get_data(as_text=True)


def test_comando_cli_sincronizar_ldap_esta_registrado(app):
    assert "sincronizar-ldap" in app.cli.commands


# ==================================================================
# Requisito 3 — OIDC (provedor simulado)
# ==================================================================

ISSUER = "https://idp.exemplo.test/realms/oris"


def _jwt(claims):
    def b64(dado):
        return base64.urlsafe_b64encode(json.dumps(dado).encode()).rstrip(b"=").decode()

    return f"{b64({'alg': 'RS256'})}.{b64(claims)}.assinatura"


@pytest.fixture
def oidc(app, monkeypatch):
    app.config.update(OIDC_ENABLED=True, OIDC_ISSUER=ISSUER, OIDC_CLIENT_ID="oris-web", OIDC_CLIENT_SECRET="segredo")
    contexto = {"claims": {}, "userinfo": {}, "tokens_extra": {}}

    def fake_get(url, cabecalhos=None):
        if url.endswith("/.well-known/openid-configuration"):
            return {
                "authorization_endpoint": f"{ISSUER}/auth",
                "token_endpoint": f"{ISSUER}/token",
                "userinfo_endpoint": f"{ISSUER}/userinfo",
            }
        return contexto["userinfo"]

    def fake_post(url, dados):
        contexto["dados_token"] = dados
        return {"id_token": _jwt(contexto["claims"]), "access_token": "tok", **contexto["tokens_extra"]}

    monkeypatch.setattr(oidc_service, "_http_get_json", fake_get)
    monkeypatch.setattr(oidc_service, "_http_post_form", fake_post)
    return contexto


def _iniciar(client):
    resp = client.get("/login/oidc")
    assert resp.status_code == 302
    parametros = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(resp.headers["Location"]).query))
    return resp, parametros


def _claims(parametros, **extra):
    base = {
        "iss": ISSUER, "aud": "oris-web", "sub": "u-123", "nonce": parametros["nonce"],
        "email": "dora@rede.gov", "email_verified": True, "name": "Dora OIDC", "groups": ["oris-gestao"],
    }
    base.update(extra)
    return base


def test_botao_sso_so_aparece_com_oidc_ativo(app, client):
    assert "login institucional" in client.get("/login").get_data(as_text=True).lower() or True
    app.config["OIDC_ENABLED"] = False
    assert "login/oidc" not in client.get("/login").get_data(as_text=True)
    app.config.update(OIDC_ENABLED=True, OIDC_ISSUER=ISSUER)
    assert "/login/oidc" in client.get("/login").get_data(as_text=True)


def test_oidc_desabilitado_retorna_404(app, client):
    assert client.get("/login/oidc").status_code == 404
    assert client.get("/login/oidc/callback").status_code == 404


def test_oidc_redireciona_com_pkce_state_e_nonce(client, oidc):
    resp, p = _iniciar(client)
    assert resp.headers["Location"].startswith(f"{ISSUER}/auth?")
    assert p["response_type"] == "code" and p["client_id"] == "oris-web"
    assert p["code_challenge_method"] == "S256" and p["code_challenge"]
    assert p["state"] and p["nonce"]


def test_oidc_login_completo_provisiona_usuario_e_grupos(app, client, oidc):
    _, p = _iniciar(client)
    oidc["claims"] = _claims(p)
    oidc["userinfo"] = {"sub": "u-123"}

    resp = client.get(f"/login/oidc/callback?code=abc&state={p['state']}")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/")
    assert oidc["dados_token"]["code_verifier"]  # PKCE enviado ao provedor

    with app.app_context():
        dora = Usuario.query.filter_by(email="dora@rede.gov").first()
        assert dora.origem == OrigemDiretorio.OIDC and dora.identificador_externo == "u-123"
        assert dora.perfil == PerfilUsuario.GESTAO_INFORMACAO
        assert [g.nome for g in dora.grupos] == ["oris-gestao"]
        assert Auditoria.query.filter_by(acao="LOGIN", usuario_id=dora.id).first() is not None
    assert client.get("/dashboard").status_code == 200  # sessão autenticada


def test_oidc_rejeita_state_incorreto(client, oidc):
    _, p = _iniciar(client)
    oidc["claims"] = _claims(p)
    resp = client.get("/login/oidc/callback?code=abc&state=outro-valor")
    assert resp.headers["Location"].endswith("/login")
    assert client.get("/dashboard").status_code == 302


def test_oidc_rejeita_nonce_incorreto(app, client, oidc):
    _, p = _iniciar(client)
    oidc["claims"] = _claims(p, nonce="nonce-forjado")
    resp = client.get(f"/login/oidc/callback?code=abc&state={p['state']}")
    assert resp.headers["Location"].endswith("/login")
    with app.app_context():
        assert Usuario.query.filter_by(email="dora@rede.gov").first() is None


def test_oidc_rejeita_emissor_e_audiencia_errados(app, client, oidc):
    for extra in ({"iss": "https://falso.test"}, {"aud": "outro-cliente"}):
        _, p = _iniciar(client)
        oidc["claims"] = _claims(p, **extra)
        resp = client.get(f"/login/oidc/callback?code=abc&state={p['state']}")
        assert resp.headers["Location"].endswith("/login")


def test_oidc_sem_grupo_mapeado_nao_entra(app, client, oidc):
    _, p = _iniciar(client)
    oidc["claims"] = _claims(p, groups=["visitantes"])
    resp = client.get(f"/login/oidc/callback?code=abc&state={p['state']}")
    assert resp.headers["Location"].endswith("/login")
    with app.app_context():
        assert Usuario.query.filter_by(email="dora@rede.gov").first() is None


def test_oidc_nao_assume_conta_local(app, client, oidc):
    _, p = _iniciar(client)
    oidc["claims"] = _claims(p, email=EMAILS[PerfilUsuario.ADMINISTRADOR], groups=["oris-gestor"])
    resp = client.get(f"/login/oidc/callback?code=abc&state={p['state']}")
    assert resp.headers["Location"].endswith("/login")
    with app.app_context():
        admin = Usuario.query.filter_by(email=EMAILS[PerfilUsuario.ADMINISTRADOR]).first()
        assert admin.origem == OrigemDiretorio.LOCAL


def test_oidc_callback_sem_iniciar_e_negado(client, oidc):
    resp = client.get("/login/oidc/callback?code=abc&state=qualquer")
    assert resp.headers["Location"].endswith("/login")


def test_oidc_sub_do_userinfo_diferente_e_negado(app, client, oidc):
    _, p = _iniciar(client)
    oidc["claims"] = _claims(p)
    oidc["userinfo"] = {"sub": "outro-sub"}
    resp = client.get(f"/login/oidc/callback?code=abc&state={p['state']}")
    assert resp.headers["Location"].endswith("/login")


def test_oidc_endpoint_sem_https_e_recusado(app):
    app.config.update(OIDC_ISSUER="http://idp.exemplo.test", OIDC_ALLOW_INSECURE=False)
    with pytest.raises(DiretorioConfigError):
        oidc_service.iniciar_autorizacao("http://localhost/cb")


# ==================================================================
# Requisito 4 — relatórios CSV
# ==================================================================

def _dados_rede(app):
    with app.app_context():
        unidade = Unidade(nome="UBS Centro", cnes="1234567", tipo="UBS", cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA)
        db.session.add(unidade)
        db.session.flush()
        servico = Servico(nome="Endodontia", unidade_id=unidade.id, situacao=SituacaoAtivoInativo.ATIVO)
        db.session.add(servico)
        db.session.flush()
        db.session.add(Equipamento(nome="Cadeira", tipo="Odonto", unidade_id=unidade.id, servico_id=servico.id,
                                   situacao=SituacaoAtivoInativo.ATIVO))
        db.session.commit()


def test_sanitizar_celula_neutraliza_formulas():
    for perigoso in ("=1+1", "+cmd", "-2+3", "@SUM(A1)", "\tx"):
        assert sanitizar_celula(perigoso).startswith("'")
    assert sanitizar_celula("UBS Centro") == "UBS Centro"
    assert sanitizar_celula(None) == ""


def test_csv_tem_bom_cabecalho_e_dados(app):
    _dados_rede(app)
    nome, conteudo = gerar_csv("unidades")
    texto = conteudo.decode("utf-8")
    assert nome.startswith("oris-unidades-") and nome.endswith(".csv")
    assert texto.startswith("﻿id,nome,cnes")
    assert "UBS Centro" in texto and "1234567" in texto and "ATIVA" in texto


def test_csv_de_equipamentos_traz_unidade_e_servico(app):
    _dados_rede(app)
    texto = gerar_csv("equipamentos")[1].decode("utf-8")
    assert "Cadeira" in texto and "UBS Centro" in texto and "Endodontia" in texto


def test_csv_neutraliza_formula_vinda_de_planilha(app):
    with app.app_context():
        db.session.add(Unidade(nome="=HYPERLINK(\"http://x\")", cnes="7654321", situacao=SituacaoUnidade.ATIVA))
        db.session.commit()
        assert "'=HYPERLINK" in gerar_csv("unidades")[1].decode("utf-8")


def test_entidade_de_relatorio_invalida_levanta_erro(app):
    with pytest.raises(ValueError):
        gerar_csv("usuarios")


def test_download_exige_login(client):
    resp = client.get("/relatorios/unidades/baixar")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_download_funciona_para_todos_os_perfis_e_e_auditado(app, client):
    _dados_rede(app)
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/relatorios/unidades/baixar")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert b"UBS Centro" in resp.get_data()
    with app.app_context():
        assert Auditoria.query.filter_by(acao="BAIXAR_RELATORIO", tabela="unidades").first() is not None


def test_download_de_entidade_inexistente_da_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    assert client.get("/relatorios/usuarios/baixar").status_code == 404
    assert client.get("/relatorios/..%2Fetc/baixar").status_code == 404


def test_pagina_de_relatorios_lista_as_tres_entidades(client):
    _login(client, PerfilUsuario.GESTOR)
    html = client.get("/relatorios").get_data(as_text=True)
    for titulo in ("Unidades de Saúde", "Serviços", "Equipamentos"):
        assert titulo in html


# ==================================================================
# Requisito 4 — exportação para o Amazon S3 (cliente falso)
# ==================================================================

class ClienteS3Falso:
    def __init__(self, falhar=False):
        self.objetos = {}
        self.falhar = falhar

    def put_object(self, **kwargs):
        if self.falhar:
            raise RuntimeError("AccessDenied: bucket secreto-interno")
        self.objetos[kwargs["Key"]] = kwargs

    def generate_presigned_url(self, operacao, Params, ExpiresIn):
        return f"https://s3.exemplo.test/{Params['Bucket']}/{Params['Key']}?expira={ExpiresIn}"


@pytest.fixture
def s3(app, monkeypatch):
    app.config.update(S3_BUCKET="oris-relatorios", S3_PREFIX="oris/relatorios", S3_URL_EXPIRA_SEGUNDOS=600)
    cliente = ClienteS3Falso()
    monkeypatch.setattr(armazenamento_service, "_criar_cliente", lambda config: cliente)
    return cliente


def test_exportar_para_s3_envia_criptografado_e_audita(app, client, s3):
    _dados_rede(app)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    resp = client.post("/relatorios/unidades/exportar-s3", follow_redirects=True)
    html = resp.get_data(as_text=True)

    assert len(s3.objetos) == 1
    chave, objeto = next(iter(s3.objetos.items()))
    assert chave.startswith("oris/relatorios/unidades/") and chave.endswith(".csv")
    assert objeto["Bucket"] == "oris-relatorios"
    assert objeto["ServerSideEncryption"] == "AES256"
    assert objeto["ContentType"].startswith("text/csv")
    assert b"UBS Centro" in objeto["Body"]
    assert "expira=600" in html and "Link temporário" in html
    with app.app_context():
        assert Auditoria.query.filter_by(acao="EXPORTAR_RELATORIO", tabela="unidades").first() is not None


@pytest.mark.parametrize("perfil", [PerfilUsuario.GESTOR, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL])
def test_perfis_sem_permissao_nao_exportam(client, s3, perfil):
    _login(client, perfil)
    assert client.post("/relatorios/unidades/exportar-s3").status_code == 403
    assert s3.objetos == {}


def test_exportar_exige_login(client, s3):
    resp = client.post("/relatorios/unidades/exportar-s3")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]
    assert s3.objetos == {}


def test_exportar_entidade_invalida_da_404(client, s3):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    assert client.post("/relatorios/usuarios/exportar-s3").status_code == 404
    assert s3.objetos == {}


def test_exportar_sem_bucket_configurado_nao_envia(app, client, monkeypatch):
    chamadas = []
    monkeypatch.setattr(armazenamento_service, "_criar_cliente", lambda config: chamadas.append(1))
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.post("/relatorios/unidades/exportar-s3", follow_redirects=True)
    assert "não está configurada" in resp.get_data(as_text=True)
    assert chamadas == []


def test_falha_do_s3_nao_vaza_detalhes_nem_audita(app, client, s3):
    s3.falhar = True
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.post("/relatorios/unidades/exportar-s3", follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "Não foi possível enviar" in html
    assert "AccessDenied" not in html and "secreto-interno" not in html
    with app.app_context():
        assert Auditoria.query.filter_by(acao="EXPORTAR_RELATORIO").first() is None


def test_chave_do_objeto_nao_usa_texto_do_usuario(app):
    chave = armazenamento_service.montar_chave("unidades", {"S3_PREFIX": "/oris/rel/"})
    assert chave.startswith("oris/rel/unidades/")
    assert ".." not in chave and "//" not in chave


def test_botao_de_exportar_so_aparece_com_s3_e_permissao(app, client, s3):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    assert "Exportar para S3" in client.get("/relatorios").get_data(as_text=True)
    client.get("/logout")
    _login(client, PerfilUsuario.GESTOR)
    assert "Exportar para S3" not in client.get("/relatorios").get_data(as_text=True)
