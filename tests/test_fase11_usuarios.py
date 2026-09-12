"""
Testes da FASE 11 — Administração de Usuários.

Roda contra SQLite em memória (TestingConfig). Cria um usuário para
cada perfil (incluindo dois ADMINISTRADOR, para poder testar a
proteção do "último administrador" sem travar os próprios testes).
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import Auditoria, PerfilUsuario, Usuario
from app.utils.security import gerar_hash_senha, verificar_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}

EMAIL_SEGUNDO_ADMIN = "admin2@oris.com.br"


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

        db.session.add(
            Usuario(
                nome="Segundo Admin",
                email=EMAIL_SEGUNDO_ADMIN,
                senha_hash=gerar_hash_senha(SENHA),
                perfil=PerfilUsuario.ADMINISTRADOR,
                ativo=True,
            )
        )
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil_ou_email):
    email = EMAILS.get(perfil_ou_email, perfil_ou_email)
    return client.post("/login", data={"email": email, "senha": SENHA}, follow_redirects=True)


def _usuario(app, perfil_ou_email):
    email = EMAILS.get(perfil_ou_email, perfil_ou_email)
    with app.app_context():
        return Usuario.query.filter_by(email=email).first()


DADOS_NOVO_USUARIO = {
    "nome": "Novo Usuário",
    "email": "novo.usuario@oris.com.br",
    "senha": "OutraSenhaForte123!",
    "perfil": "GESTAO_INFORMACAO",
    "ativo": "1",
}


# ----------------------------------------------------------------
# 1-5. Acesso
# ----------------------------------------------------------------

def test_administrador_acessa_usuarios(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/usuarios")
    assert resp.status_code == 200


def test_gestao_informacao_recebe_403(client):
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    resp = client.get("/usuarios")
    assert resp.status_code == 403


def test_responsavel_saude_bucal_recebe_403(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    resp = client.get("/usuarios")
    assert resp.status_code == 403


def test_gestor_recebe_403(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/usuarios")
    assert resp.status_code == 403


def test_usuario_nao_autenticado_nao_acessa(client):
    resp = client.get("/usuarios", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# 6-13. Criação
# ----------------------------------------------------------------

def test_admin_abre_formulario_de_criacao(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/usuarios/novo")
    assert resp.status_code == 200


def test_criacao_de_usuario_funciona(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.post("/usuarios/novo", data=DADOS_NOVO_USUARIO, follow_redirects=True)
    assert resp.status_code == 200
    assert "criado com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        criado = Usuario.query.filter_by(email="novo.usuario@oris.com.br").first()
        assert criado is not None
        assert criado.nome == "Novo Usuário"
        assert criado.perfil == PerfilUsuario.GESTAO_INFORMACAO
        assert criado.ativo is True


def test_email_duplicado_e_rejeitado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    dados = dict(DADOS_NOVO_USUARIO)
    dados["email"] = EMAILS[PerfilUsuario.GESTOR]  # já existe
    resp = client.post("/usuarios/novo", data=dados, follow_redirects=True)
    assert resp.status_code == 200
    assert "Já existe um usuário cadastrado" in resp.get_data(as_text=True)


def test_email_invalido_e_rejeitado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    dados = dict(DADOS_NOVO_USUARIO)
    dados["email"] = "nao-e-um-email"
    resp = client.post("/usuarios/novo", data=dados, follow_redirects=True)
    assert resp.status_code == 200
    assert "Email inválido." in resp.get_data(as_text=True)


def test_perfil_invalido_e_rejeitado(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    dados = dict(DADOS_NOVO_USUARIO)
    dados["perfil"] = "SUPER_ADMIN_INEXISTENTE"
    resp = client.post("/usuarios/novo", data=dados, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert Usuario.query.filter_by(email="novo.usuario@oris.com.br").first() is None


def test_senha_armazenada_como_bcrypt_hash(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post("/usuarios/novo", data=DADOS_NOVO_USUARIO)

    with app.app_context():
        criado = Usuario.query.filter_by(email="novo.usuario@oris.com.br").first()
        assert criado.senha_hash != DADOS_NOVO_USUARIO["senha"]
        assert criado.senha_hash.startswith("$2b$")
        assert verificar_senha(DADOS_NOVO_USUARIO["senha"], criado.senha_hash) is True


def test_senha_nao_aparece_em_resposta_html(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.post("/usuarios/novo", data=DADOS_NOVO_USUARIO, follow_redirects=True)
    assert DADOS_NOVO_USUARIO["senha"] not in resp.get_data(as_text=True)

    resp = client.get("/usuarios")
    assert DADOS_NOVO_USUARIO["senha"] not in resp.get_data(as_text=True)
    assert "$2b$" not in resp.get_data(as_text=True)


def test_senha_nao_aparece_em_auditoria(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post("/usuarios/novo", data=DADOS_NOVO_USUARIO)

    with app.app_context():
        registro = Auditoria.query.filter_by(acao="CRIAR_USUARIO").first()
        assert registro is not None
        texto = " ".join(filter(None, [registro.descricao, registro.valor_anterior, registro.valor_novo]))
        assert DADOS_NOVO_USUARIO["senha"] not in texto
        assert "$2b$" not in texto


# ----------------------------------------------------------------
# 14. Usuário aparece na listagem
# ----------------------------------------------------------------

def test_usuario_aparece_na_listagem(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post("/usuarios/novo", data=DADOS_NOVO_USUARIO)
    resp = client.get("/usuarios")
    assert "Novo Usuário" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 15-17. Edição
# ----------------------------------------------------------------

def test_edicao_de_nome_funciona(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    resp = client.post(
        f"/usuarios/{alvo.id}/editar",
        data={"nome": "Gestor Renomeado", "email": alvo.email, "perfil": "GESTOR"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        atualizado = db.session.get(Usuario, alvo.id)
        assert atualizado.nome == "Gestor Renomeado"


def test_edicao_de_email_funciona(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    client.post(
        f"/usuarios/{alvo.id}/editar",
        data={"nome": alvo.nome, "email": "gestor.novo@oris.com.br", "perfil": "GESTOR"},
    )

    with app.app_context():
        atualizado = db.session.get(Usuario, alvo.id)
        assert atualizado.email == "gestor.novo@oris.com.br"


def test_alteracao_de_perfil_funciona(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)

    client.post(
        f"/usuarios/{alvo.id}/editar",
        data={"nome": alvo.nome, "email": alvo.email, "perfil": "GESTAO_INFORMACAO"},
    )

    with app.app_context():
        atualizado = db.session.get(Usuario, alvo.id)
        assert atualizado.perfil == PerfilUsuario.GESTAO_INFORMACAO


# ----------------------------------------------------------------
# 18-21. Ativação / desativação e seus efeitos
# ----------------------------------------------------------------

def test_ativacao_funciona(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    client.post(f"/usuarios/{alvo.id}/situacao", data={"acao": "desativar"})
    resp = client.post(f"/usuarios/{alvo.id}/situacao", data={"acao": "ativar"}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        atualizado = db.session.get(Usuario, alvo.id)
        assert atualizado.ativo is True


def test_desativacao_funciona(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    resp = client.post(f"/usuarios/{alvo.id}/situacao", data={"acao": "desativar"}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        atualizado = db.session.get(Usuario, alvo.id)
        assert atualizado.ativo is False


def test_usuario_desativado_nao_consegue_login(client, app):
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post(f"/usuarios/{alvo.id}/situacao", data={"acao": "desativar"})
    client.get("/logout")

    resp = client.post("/login", data={"email": alvo.email, "senha": SENHA}, follow_redirects=True)
    assert "Email ou senha inválidos." in resp.get_data(as_text=True)


def test_usuario_inativo_nao_acessa_areas_protegidas(client, app):
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    # Loga como o próprio GESTOR primeiro (sessão válida)
    client.post("/login", data={"email": alvo.email, "senha": SENHA})
    resp = client.get("/unidades")
    assert resp.status_code == 200  # ainda ativo, acesso normal

    # Um ADMINISTRADOR desativa esse usuário em outra sessão
    client_admin = client.application.test_client()
    client_admin.post("/login", data={"email": EMAILS[PerfilUsuario.ADMINISTRADOR], "senha": SENHA})
    client_admin.post(f"/usuarios/{alvo.id}/situacao", data={"acao": "desativar"})

    # A sessão antiga do GESTOR não deve mais funcionar em NENHUMA
    # área protegida — nem nas que só exigem login_required.
    resp = client.get("/unidades", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# 22. Não existe exclusão física
# ----------------------------------------------------------------

def test_nao_existe_rota_de_exclusao_fisica(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    resp = client.post(f"/usuarios/{alvo.id}/excluir")
    assert resp.status_code == 404

    resp = client.delete(f"/usuarios/{alvo.id}")
    assert resp.status_code in (404, 405)

    with app.app_context():
        assert db.session.get(Usuario, alvo.id) is not None


# ----------------------------------------------------------------
# 23-24. Proteção do último administrador
# ----------------------------------------------------------------

def test_ultimo_administrador_ativo_nao_pode_ser_desativado(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    # Desativa o segundo administrador, deixando só um
    segundo_admin = _usuario(app, EMAIL_SEGUNDO_ADMIN)
    client.post(f"/usuarios/{segundo_admin.id}/situacao", data={"acao": "desativar"})

    admin_restante = _usuario(app, PerfilUsuario.ADMINISTRADOR)
    resp = client.post(f"/usuarios/{admin_restante.id}/situacao", data={"acao": "desativar"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "único" in resp.get_data(as_text=True)

    with app.app_context():
        atualizado = db.session.get(Usuario, admin_restante.id)
        assert atualizado.ativo is True


def test_ultimo_administrador_nao_pode_perder_o_perfil(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    segundo_admin = _usuario(app, EMAIL_SEGUNDO_ADMIN)
    client.post(f"/usuarios/{segundo_admin.id}/situacao", data={"acao": "desativar"})

    admin_restante = _usuario(app, PerfilUsuario.ADMINISTRADOR)
    resp = client.post(
        f"/usuarios/{admin_restante.id}/editar",
        data={"nome": admin_restante.nome, "email": admin_restante.email, "perfil": "GESTOR"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "único" in resp.get_data(as_text=True)

    with app.app_context():
        atualizado = db.session.get(Usuario, admin_restante.id)
        assert atualizado.perfil == PerfilUsuario.ADMINISTRADOR


def test_pode_desativar_administrador_quando_ha_outro_ativo(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    segundo_admin = _usuario(app, EMAIL_SEGUNDO_ADMIN)

    # Há 2 administradores ativos — desativar um deles é permitido
    resp = client.post(f"/usuarios/{segundo_admin.id}/situacao", data={"acao": "desativar"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "desativado com sucesso" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 25-28. Auditoria
# ----------------------------------------------------------------

def test_auditoria_registrada_na_criacao(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post("/usuarios/novo", data=DADOS_NOVO_USUARIO)

    with app.app_context():
        registro = Auditoria.query.filter_by(acao="CRIAR_USUARIO").first()
        assert registro is not None
        assert registro.tabela == "usuarios"


def test_auditoria_registrada_na_edicao(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    client.post(
        f"/usuarios/{alvo.id}/editar",
        data={"nome": "Nome Editado", "email": alvo.email, "perfil": "GESTOR"},
    )

    with app.app_context():
        registro = Auditoria.query.filter_by(acao="EDITAR_USUARIO", registro_id=alvo.id).first()
        assert registro is not None
        assert "Nome Editado" in registro.valor_novo


def test_auditoria_registrada_na_ativacao_e_desativacao(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    client.post(f"/usuarios/{alvo.id}/situacao", data={"acao": "desativar"})
    client.post(f"/usuarios/{alvo.id}/situacao", data={"acao": "ativar"})

    with app.app_context():
        assert Auditoria.query.filter_by(acao="DESATIVAR_USUARIO", registro_id=alvo.id).first() is not None
        assert Auditoria.query.filter_by(acao="ATIVAR_USUARIO", registro_id=alvo.id).first() is not None


def test_auditoria_registrada_na_alteracao_de_perfil(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)

    client.post(
        f"/usuarios/{alvo.id}/editar",
        data={"nome": alvo.nome, "email": alvo.email, "perfil": "GESTOR"},
    )

    with app.app_context():
        registro = Auditoria.query.filter_by(acao="ALTERAR_PERFIL", registro_id=alvo.id).first()
        assert registro is not None
        assert "GESTOR" in registro.valor_novo


# ----------------------------------------------------------------
# 29. Redefinição de senha auditada sem expor senha
# ----------------------------------------------------------------

def test_redefinicao_de_senha_e_auditada_sem_expor_senha(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    nova_senha = "SenhaNovaTemp123!"
    resp = client.post(
        f"/usuarios/{alvo.id}/senha",
        data={"nova_senha": nova_senha, "confirmar_senha": nova_senha},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "redefinida com sucesso" in resp.get_data(as_text=True)
    assert nova_senha not in resp.get_data(as_text=True)

    with app.app_context():
        atualizado = db.session.get(Usuario, alvo.id)
        assert verificar_senha(nova_senha, atualizado.senha_hash) is True

        registro = Auditoria.query.filter_by(acao="REDEFINIR_SENHA", registro_id=alvo.id).first()
        assert registro is not None
        texto = " ".join(filter(None, [registro.descricao, registro.valor_anterior, registro.valor_novo]))
        assert nova_senha not in texto
        assert "$2b$" not in texto


def test_redefinicao_de_senha_com_confirmacao_diferente_e_rejeitada(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    alvo = _usuario(app, PerfilUsuario.GESTOR)
    senha_hash_anterior = alvo.senha_hash

    client.post(
        f"/usuarios/{alvo.id}/senha",
        data={"nova_senha": "SenhaA12345678", "confirmar_senha": "SenhaB12345678"},
        follow_redirects=True,
    )

    with app.app_context():
        atualizado = db.session.get(Usuario, alvo.id)
        assert atualizado.senha_hash == senha_hash_anterior


# ----------------------------------------------------------------
# 30. Usuário inexistente / acesso a outros ids
# ----------------------------------------------------------------

def test_usuario_inexistente_retorna_404(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/usuarios/999999/editar")
    assert resp.status_code == 404


def test_outros_perfis_nao_conseguem_editar_usuario_por_id(client, app):
    alvo = _usuario(app, PerfilUsuario.GESTOR)

    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    resp = client.get(f"/usuarios/{alvo.id}/editar")
    assert resp.status_code == 403

    resp = client.post(f"/usuarios/{alvo.id}/situacao", data={"acao": "desativar"})
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 31-34. Fases anteriores continuam funcionando (checagens pontuais;
# a suíte completa é executada junto — ver relatório da fase)
# ----------------------------------------------------------------

def test_rbac_das_fases_anteriores_continua_funcionando(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/admin")
    assert resp.status_code == 403


def test_dashboard_continua_funcionando(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/dashboard")
    assert resp.status_code == 200


def test_importador_continua_funcionando(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/importacao")
    assert resp.status_code == 200


def test_fluxo_de_aprovacao_continua_funcionando(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    dados_unidade = {
        "nome": "UBS Pós-Fase11", "cnes": "5556667", "tipo": "UBS",
        "cidade": "Recife", "uf": "PE", "situacao": "ATIVA",
    }
    resp = client.post("/unidades/nova", data=dados_unidade, follow_redirects=True)
    assert "aguardando aprovação" in resp.get_data(as_text=True)
