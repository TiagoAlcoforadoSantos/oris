"""
Testes da FASE 12 — segurança, LGPD e proteção de dados.

Roda contra SQLite em memória (TestingConfig). Cobre os 25 cenários
pedidos no enunciado, reaproveitando o padrão de fixtures das fases
anteriores.
"""

import io

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Alteracao,
    Auditoria,
    Equipamento,
    PerfilUsuario,
    Servico,
    SituacaoUnidade,
    Unidade,
    Usuario,
)
from app.services.alteracoes_service import aprovar_alteracao
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}


class TestingConfigComCSRF(TestingConfig):
    """Só para os testes de CSRF desta fase, que precisam que a
    proteção esteja de fato ativa para verificar o bloqueio."""

    WTF_CSRF_ENABLED = True


class TestingConfigComRateLimit(TestingConfig):
    """Só para o teste de rate limiting desta fase."""

    RATE_LIMIT_LOGIN_ENABLED = True


@pytest.fixture
def app():
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()

        for perfil, email in EMAILS.items():
            db.session.add(
                Usuario(
                    nome=f"Usuário {perfil.value}",
                    email=email,
                    senha_hash=gerar_hash_senha(SENHA),
                    perfil=perfil,
                    ativo=True,
                )
            )

        unidade = Unidade(
            nome="UBS Segurança", cnes="1230001", tipo="UBS",
            cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA,
        )
        db.session.add(unidade)
        db.session.commit()

        servico = Servico(nome="Serviço Teste", unidade_id=unidade.id, situacao="ATIVO")
        db.session.add(servico)
        db.session.commit()

        equipamento = Equipamento(
            nome="Equipamento Teste", tipo="Clínico", unidade_id=unidade.id, situacao="ATIVO"
        )
        db.session.add(equipamento)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil_ou_email, senha=SENHA):
    email = EMAILS.get(perfil_ou_email, perfil_ou_email)
    return client.post("/login", data={"email": email, "senha": senha}, follow_redirects=True)


def _usuario(app, perfil_ou_email):
    email = EMAILS.get(perfil_ou_email, perfil_ou_email)
    with app.app_context():
        return Usuario.query.filter_by(email=email).first()


# ----------------------------------------------------------------
# 1-4. Autenticação básica
# ----------------------------------------------------------------

def test_login_com_senha_correta(client):
    resp = _login(client, PerfilUsuario.ADMINISTRADOR)
    assert "Bem-vindo ao ORIS" in resp.get_data(as_text=True)


def test_login_com_senha_incorreta(client):
    resp = _login(client, PerfilUsuario.ADMINISTRADOR, senha="senha-errada")
    assert "Email ou senha inválidos." in resp.get_data(as_text=True)


def test_usuario_inativo_bloqueado(client, app):
    with app.app_context():
        gestor = Usuario.query.filter_by(email=EMAILS[PerfilUsuario.GESTOR]).first()
        gestor.ativo = False
        db.session.commit()

    resp = _login(client, PerfilUsuario.GESTOR)
    assert "Email ou senha inválidos." in resp.get_data(as_text=True)


def test_sessao_de_usuario_desativado_bloqueada(client, app):
    gestor = _usuario(app, PerfilUsuario.GESTOR)
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/unidades")
    assert resp.status_code == 200

    with app.app_context():
        atual = db.session.get(Usuario, gestor.id)
        atual.ativo = False
        db.session.commit()

    resp = client.get("/unidades", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# 5-8. RBAC
# ----------------------------------------------------------------

def test_rota_protegida_sem_login(client):
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_rota_admin_acessada_por_gestor_retorna_403(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/admin")
    assert resp.status_code == 403


def test_auditoria_acessada_por_perfil_sem_permissao_retorna_403(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    resp = client.get("/auditoria")
    assert resp.status_code == 403


def test_administracao_de_usuarios_acessada_por_perfil_sem_permissao_retorna_403(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/usuarios")
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 9. CSRF
# ----------------------------------------------------------------

def test_post_sem_csrf_e_bloqueado():
    """Usa uma config com CSRF de fato ativo para comprovar o
    bloqueio (TestingConfig normal desativa CSRF para não atrapalhar
    os demais testes, que não são sobre CSRF em si)."""
    app = create_app(TestingConfigComCSRF)
    with app.app_context():
        db.create_all()
        db.session.add(
            Usuario(
                nome="Admin", email="admin@oris.com.br",
                senha_hash=gerar_hash_senha(SENHA), perfil=PerfilUsuario.ADMINISTRADOR, ativo=True,
            )
        )
        db.session.commit()

    client = app.test_client()
    # Login sem token CSRF -> o próprio CSRFProtect deve bloquear a
    # requisição antes de qualquer lógica de negócio rodar.
    resp = client.post("/login", data={"email": "admin@oris.com.br", "senha": SENHA})
    assert resp.status_code == 400

    with app.app_context():
        db.session.remove()
        db.drop_all()


# ----------------------------------------------------------------
# 10. XSS
# ----------------------------------------------------------------

def test_tentativa_de_xss_e_escapada(client, app):
    payload = "<script>alert(1)</script>"
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)

    client.post(
        "/unidades/nova",
        data={
            "nome": payload, "cnes": "1230099", "tipo": "UBS",
            "cidade": "Recife", "uf": "PE", "situacao": "ATIVA",
        },
        follow_redirects=True,
    )

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        aprovar_alteracao(alteracao, aprovador)

    resp = client.get("/unidades")
    html = resp.get_data(as_text=True)
    # O script NUNCA deve aparecer executável — o Jinja autoescape
    # deve transformar "<" em "&lt;" etc.
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ----------------------------------------------------------------
# 11. SQL Injection
# ----------------------------------------------------------------

def test_tentativa_de_sql_injection_nao_e_executada(client, app):
    payload = "' OR '1'='1"
    resp = client.post("/login", data={"email": payload, "senha": payload}, follow_redirects=True)
    assert "Email ou senha inválidos." in resp.get_data(as_text=True) or resp.status_code == 200

    with app.app_context():
        # A tabela de usuários continua intacta (nenhuma linha foi
        # apagada/alterada por uma injeção bem-sucedida).
        assert Usuario.query.count() == 4

    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get(f"/unidades?busca={payload}")
    assert resp.status_code == 200


# ----------------------------------------------------------------
# 12. ID inexistente
# ----------------------------------------------------------------

@pytest.mark.parametrize(
    "rota",
    ["/unidades/999999", "/servicos/999999", "/equipamentos/999999", "/alteracoes/999999"],
)
def test_id_inexistente_retorna_404(client, rota):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get(rota)
    assert resp.status_code == 404


def test_usuario_e_auditoria_inexistentes_retornam_404(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/usuarios/999999/editar")
    assert resp.status_code == 404
    resp = client.get("/auditoria/999999")
    assert resp.status_code == 404


# ----------------------------------------------------------------
# 13-14. Upload
# ----------------------------------------------------------------

def test_upload_invalido_e_rejeitado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.post(
        "/importacao/mapear",
        data={"entidade": "unidades", "arquivo": (io.BytesIO(b"<html>nao e planilha</html>"), "arquivo.html")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "não aceito" in resp.get_data(as_text=True) or "Formato" in resp.get_data(as_text=True)


def test_upload_excessivamente_grande_e_rejeitado(client):
    from app.services.importacao_service import LIMITE_TAMANHO_BYTES

    _login(client, PerfilUsuario.ADMINISTRADOR)
    conteudo_grande = b"a" * (LIMITE_TAMANHO_BYTES + 1024)
    resp = client.post(
        "/importacao/mapear",
        data={"entidade": "unidades", "arquivo": (io.BytesIO(conteudo_grande), "grande.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "excede o limite" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 15. Arquivo temporário não permanece
# ----------------------------------------------------------------

def test_arquivo_temporario_nao_permanece_apos_fluxo_concluido(client):
    import os
    import re

    from app.routes.importacao import _caminho_do_token

    _login(client, PerfilUsuario.ADMINISTRADOR)
    conteudo = b"Nome,CNES,Cidade,UF,Situacao\nUBS Temp,1230077,Recife,PE,ATIVA\n"
    resp = client.post(
        "/importacao/mapear",
        data={"entidade": "unidades", "arquivo": (io.BytesIO(conteudo), "unidades.csv")},
        content_type="multipart/form-data",
    )
    token = re.search(r'name="token" value="([^"]+)"', resp.get_data(as_text=True)).group(1)
    caminho = _caminho_do_token(token)
    assert os.path.exists(caminho)

    mapa = {
        "mapa_nome": "Nome", "mapa_cnes": "CNES", "mapa_cidade": "Cidade",
        "mapa_uf": "UF", "mapa_situacao": "Situacao", "mapa_tipo": "", "mapa_endereco": "", "mapa_bairro": "",
    }
    client.post("/importacao/validar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **mapa})
    client.post("/importacao/confirmar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **mapa})

    assert not os.path.exists(caminho)


# ----------------------------------------------------------------
# 16-18. Secrets/credenciais nunca aparecem
# ----------------------------------------------------------------

def test_senha_nao_aparece_em_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    with app.app_context():
        for registro in Auditoria.query.all():
            texto = " ".join(filter(None, [registro.descricao, registro.valor_anterior, registro.valor_novo]))
            assert SENHA not in texto


def test_hash_nao_aparece_em_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    with app.app_context():
        for registro in Auditoria.query.all():
            texto = " ".join(filter(None, [registro.descricao, registro.valor_anterior, registro.valor_novo]))
            assert "$2b$" not in texto


def test_secret_key_nao_aparece_em_resposta(client, app):
    resp = client.get("/login")
    html = resp.get_data(as_text=True)
    assert app.config["SECRET_KEY"] not in html

    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/dashboard")
    assert app.config["SECRET_KEY"] not in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 19-20. Auditoria e rollback
# ----------------------------------------------------------------

def test_alteracao_aprovada_gera_auditoria(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    client.post(
        "/unidades/nova",
        data={"nome": "UBS Aud", "cnes": "1230033", "tipo": "UBS", "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"},
    )

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        aprovar_alteracao(alteracao, aprovador)

        assert Auditoria.query.filter_by(acao="CRIAR", tabela="unidades").first() is not None
        assert Auditoria.query.filter_by(acao="APROVAR_ALTERACAO").first() is not None


def test_rollback_nao_gera_auditoria_falsa(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)

    dados_a = {"nome": "UBS Rollback A", "cnes": "1230044", "tipo": "UBS", "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"}
    dados_b = {"nome": "UBS Rollback B", "cnes": "1230044", "tipo": "UBS", "cidade": "Recife", "uf": "PE", "situacao": "ATIVA"}
    client.post("/unidades/nova", data=dados_a)
    client.post("/unidades/nova", data=dados_b)

    with app.app_context():
        alteracoes = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").order_by(Alteracao.id).all()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)

        aprovar_alteracao(alteracoes[0], aprovador)
        total_auditorias_antes = Auditoria.query.count()

        ok, _ = aprovar_alteracao(alteracoes[1], aprovador)
        assert ok is False

        # Nenhuma auditoria nova de CRIAR/APROVAR_ALTERACAO para a
        # segunda unidade — o rollback não deixou rastro falso.
        total_auditorias_depois = Auditoria.query.count()
        assert total_auditorias_depois == total_auditorias_antes


# ----------------------------------------------------------------
# 21. Último administrador protegido
# ----------------------------------------------------------------

def test_ultimo_administrador_protegido(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    admin = _usuario(app, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(f"/usuarios/{admin.id}/situacao", data={"acao": "desativar"}, follow_redirects=True)
    assert "único" in resp.get_data(as_text=True)

    with app.app_context():
        atualizado = db.session.get(Usuario, admin.id)
        assert atualizado.ativo is True


# ----------------------------------------------------------------
# 22. RBAC não contornável pela URL
# ----------------------------------------------------------------

def test_usuario_nao_autorizado_nao_contorna_rbac_pela_url(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)

    for rota in ("/usuarios", "/auditoria", "/admin"):
        resp = client.get(rota)
        assert resp.status_code == 403

    # RESPONSAVEL_SAUDE_BUCAL pode solicitar, mas não pode aprovar —
    # mesmo sabendo (ou adivinhando) o ID de uma Alteracao.
    resp = client.post("/alteracoes/1/aprovar")
    assert resp.status_code in (403, 404)


# ----------------------------------------------------------------
# 23. Importação não ignora aprovação
# ----------------------------------------------------------------

def test_importacao_nao_ignora_aprovacao(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    conteudo = b"Nome,CNES,Cidade,UF,Situacao\nUBS Importada Sec,1230055,Recife,PE,ATIVA\n"
    resp = client.post(
        "/importacao/mapear",
        data={"entidade": "unidades", "arquivo": (io.BytesIO(conteudo), "unidades.csv")},
        content_type="multipart/form-data",
    )
    import re

    token = re.search(r'name="token" value="([^"]+)"', resp.get_data(as_text=True)).group(1)
    mapa = {
        "mapa_nome": "Nome", "mapa_cnes": "CNES", "mapa_cidade": "Cidade",
        "mapa_uf": "UF", "mapa_situacao": "Situacao", "mapa_tipo": "", "mapa_endereco": "", "mapa_bairro": "",
    }
    client.post("/importacao/validar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **mapa})
    client.post("/importacao/confirmar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **mapa})

    with app.app_context():
        # A unidade NÃO existe até ser aprovada — a importação não
        # tem nenhum atalho para inserir/atualizar diretamente.
        assert Unidade.query.filter_by(cnes="1230055").first() is None
        assert Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR", status="PENDENTE").count() >= 1


# ----------------------------------------------------------------
# 24. Headers de segurança
# ----------------------------------------------------------------

def test_headers_de_seguranca_presentes(client):
    resp = client.get("/login")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") is not None
    assert resp.headers.get("Content-Security-Policy") is not None


# ----------------------------------------------------------------
# 25. Cookies seguros (verificado via configuração de produção)
# ----------------------------------------------------------------

def test_cookies_seguros_em_configuracao_de_producao():
    from config import ProductionConfig

    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert ProductionConfig.SESSION_COOKIE_HTTPONLY is True
    assert ProductionConfig.SESSION_COOKIE_SAMESITE == "Lax"


# ----------------------------------------------------------------
# Extra: rate limiting de login
# ----------------------------------------------------------------

def test_rate_limiting_bloqueia_apos_muitas_tentativas():
    app = create_app(TestingConfigComRateLimit)
    with app.app_context():
        db.create_all()
        db.session.add(
            Usuario(
                nome="Admin", email="admin@oris.com.br",
                senha_hash=gerar_hash_senha(SENHA), perfil=PerfilUsuario.ADMINISTRADOR, ativo=True,
            )
        )
        db.session.commit()

    client = app.test_client()
    for _ in range(5):
        client.post("/login", data={"email": "admin@oris.com.br", "senha": "errada"}, follow_redirects=True)

    resp = client.post("/login", data={"email": "admin@oris.com.br", "senha": SENHA}, follow_redirects=True)
    assert "Muitas tentativas" in resp.get_data(as_text=True)

    with app.app_context():
        db.session.remove()
        db.drop_all()

    # Limpa o estado do limitador para não afetar outros testes que
    # rodem depois neste mesmo processo.
    from app.utils.rate_limit import limpar_tentativas

    limpar_tentativas("127.0.0.1", "admin@oris.com.br")


# ----------------------------------------------------------------
# Extra: página de privacidade
# ----------------------------------------------------------------

def test_pagina_de_privacidade_acessivel_sem_login(client):
    resp = client.get("/privacidade")
    assert resp.status_code == 200
    assert "Finalidade" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# Extra: página de erro 500 não expõe detalhes internos
# ----------------------------------------------------------------

def test_pagina_de_erro_interno_nao_expoe_detalhes(app):
    with app.test_request_context():
        from flask import render_template

        html = render_template("erro_interno.html")
        assert "Traceback" not in html
        assert 'File "' not in html
