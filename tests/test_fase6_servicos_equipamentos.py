"""
Testes da FASE 6 — CRUD de Serviços e Equipamentos.

Roda contra SQLite em memória (TestingConfig), reaproveitando o
padrão de fixtures das fases anteriores. Cria um usuário para cada
perfil, uma unidade "A" com um serviço próprio, e uma unidade "B"
(sem serviços) — usada para testar a inconsistência
serviço-de-outra-unidade.
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Equipamento,
    PerfilUsuario,
    Servico,
    SituacaoAtivoInativo,
    SituacaoUnidade,
    Unidade,
    Usuario,
)
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}


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

        unidade_a = Unidade(
            nome="UBS Unidade A", cnes="1111111", tipo="UBS",
            cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA,
        )
        unidade_b = Unidade(
            nome="UBS Unidade B", cnes="2222222", tipo="UBS",
            cidade="Recife", uf="PE", situacao=SituacaoUnidade.ATIVA,
        )
        db.session.add_all([unidade_a, unidade_b])
        db.session.commit()

        servico_a = Servico(nome="Odontologia Geral", unidade_id=unidade_a.id, situacao=SituacaoAtivoInativo.ATIVO)
        db.session.add(servico_a)
        db.session.commit()

        equipamento_a = Equipamento(
            nome="Cadeira Odontológica",
            tipo="Equipamento clínico",
            unidade_id=unidade_a.id,
            servico_id=servico_a.id,
            situacao=SituacaoAtivoInativo.ATIVO,
        )
        db.session.add(equipamento_a)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil):
    return client.post("/login", data={"email": EMAILS[perfil], "senha": SENHA}, follow_redirects=True)


def _ids(app):
    with app.app_context():
        unidade_a = Unidade.query.filter_by(cnes="1111111").first()
        unidade_b = Unidade.query.filter_by(cnes="2222222").first()
        servico_a = Servico.query.filter_by(unidade_id=unidade_a.id).first()
        equipamento_a = Equipamento.query.filter_by(unidade_id=unidade_a.id).first()
        return {
            "unidade_a": unidade_a.id,
            "unidade_b": unidade_b.id,
            "servico_a": servico_a.id,
            "equipamento_a": equipamento_a.id,
        }


# ==================================================================
# SERVIÇOS
# ==================================================================

# 1. Usuário não autenticado não acessa serviços
def test_nao_autenticado_nao_acessa_servicos(client):
    resp = client.get("/servicos", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# 2. Perfil autorizado consegue listar serviços
def test_gestor_lista_servicos(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/servicos")
    assert resp.status_code == 200
    assert "Odontologia Geral" in resp.get_data(as_text=True)


# 3. Perfil autorizado consegue criar serviço
def test_administrador_cria_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/servicos/novo",
        data={"nome": "Prótese Dentária", "unidade_id": ids["unidade_a"], "situacao": "ATIVO"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "cadastrado com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        assert Servico.query.filter_by(nome="Prótese Dentária").first() is not None


# 4. Perfil autorizado consegue visualizar serviço
def test_visualizar_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)

    resp = client.get(f"/servicos/{ids['servico_a']}")
    assert resp.status_code == 200
    assert "Odontologia Geral" in resp.get_data(as_text=True)
    assert "UBS Unidade A" in resp.get_data(as_text=True)


# 5. Perfil autorizado consegue editar serviço
def test_editar_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)

    resp = client.post(
        f"/servicos/{ids['servico_a']}/editar",
        data={"nome": "Odontologia Geral (Renomeado)", "unidade_id": ids["unidade_a"], "situacao": "ATIVO"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "atualizado com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        servico = db.session.get(Servico, ids["servico_a"])
        assert servico.nome == "Odontologia Geral (Renomeado)"


# 6. Perfil autorizado consegue alterar situação
def test_alterar_situacao_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(f"/servicos/{ids['servico_a']}/situacao", data={"situacao": "INATIVO"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "alterada para INATIVO" in resp.get_data(as_text=True)

    with app.app_context():
        servico = db.session.get(Servico, ids["servico_a"])
        assert servico.situacao == SituacaoAtivoInativo.INATIVO


# 7. GESTOR consegue consultar
def test_gestor_consulta_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.GESTOR)

    assert client.get("/servicos").status_code == 200
    assert client.get(f"/servicos/{ids['servico_a']}").status_code == 200


# 8. GESTOR não consegue criar
def test_gestor_nao_cria_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.GESTOR)

    assert client.get("/servicos/novo").status_code == 403
    resp = client.post("/servicos/novo", data={"nome": "X", "unidade_id": ids["unidade_a"], "situacao": "ATIVO"})
    assert resp.status_code == 403


# 9. GESTOR não consegue editar
def test_gestor_nao_edita_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.GESTOR)

    assert client.get(f"/servicos/{ids['servico_a']}/editar").status_code == 403
    resp = client.post(f"/servicos/{ids['servico_a']}/situacao", data={"situacao": "INATIVO"})
    assert resp.status_code == 403


# 10. Unidade inexistente é rejeitada
def test_servico_com_unidade_inexistente_e_rejeitado(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/servicos/novo",
        data={"nome": "Serviço Órfão", "unidade_id": 999999, "situacao": "ATIVO"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert Servico.query.filter_by(nome="Serviço Órfão").first() is None


# 11. Serviço sem unidade é rejeitado
def test_servico_sem_unidade_e_rejeitado(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/servicos/novo",
        data={"nome": "Serviço Sem Unidade", "situacao": "ATIVO"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert Servico.query.filter_by(nome="Serviço Sem Unidade").first() is None


# 12. Situação inválida é rejeitada
def test_situacao_invalida_e_rejeitada_no_cadastro_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/servicos/novo",
        data={"nome": "Serviço Situação Inválida", "unidade_id": ids["unidade_a"], "situacao": "NAO_EXISTE"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert Servico.query.filter_by(nome="Serviço Situação Inválida").first() is None


# ==================================================================
# EQUIPAMENTOS
# ==================================================================

# 13. Usuário não autenticado não acessa equipamentos
def test_nao_autenticado_nao_acessa_equipamentos(client):
    resp = client.get("/equipamentos", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# 14. Perfil autorizado consegue listar equipamentos
def test_gestor_lista_equipamentos(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/equipamentos")
    assert resp.status_code == 200
    assert "Cadeira Odontológica" in resp.get_data(as_text=True)


# 15. Perfil autorizado consegue criar equipamento
def test_administrador_cria_equipamento(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/equipamentos/novo",
        data={
            "nome": "Autoclave",
            "tipo": "Esterilização",
            "unidade_id": ids["unidade_a"],
            "servico_id": ids["servico_a"],
            "situacao": "ATIVO",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "cadastrado com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        criado = Equipamento.query.filter_by(nome="Autoclave").first()
        assert criado is not None
        assert criado.servico_id == ids["servico_a"]


def test_criar_equipamento_sem_servico(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/equipamentos/novo",
        data={
            "nome": "Compressor",
            "tipo": "Equipamento de apoio",
            "unidade_id": ids["unidade_a"],
            "servico_id": "",
            "situacao": "ATIVO",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "cadastrado com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        criado = Equipamento.query.filter_by(nome="Compressor").first()
        assert criado is not None
        assert criado.servico_id is None


# 16. Perfil autorizado consegue visualizar equipamento
def test_visualizar_equipamento(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)

    resp = client.get(f"/equipamentos/{ids['equipamento_a']}")
    assert resp.status_code == 200
    assert "Cadeira Odontológica" in resp.get_data(as_text=True)
    assert "UBS Unidade A" in resp.get_data(as_text=True)


# 17. Perfil autorizado consegue editar equipamento
def test_editar_equipamento(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)

    resp = client.post(
        f"/equipamentos/{ids['equipamento_a']}/editar",
        data={
            "nome": "Cadeira Odontológica (Nova)",
            "tipo": "Equipamento clínico",
            "unidade_id": ids["unidade_a"],
            "servico_id": ids["servico_a"],
            "situacao": "ATIVO",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "atualizado com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        equipamento = db.session.get(Equipamento, ids["equipamento_a"])
        assert equipamento.nome == "Cadeira Odontológica (Nova)"


# 18. Perfil autorizado consegue alterar situação
def test_alterar_situacao_equipamento(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        f"/equipamentos/{ids['equipamento_a']}/situacao", data={"situacao": "INATIVO"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert "alterada para INATIVO" in resp.get_data(as_text=True)

    with app.app_context():
        equipamento = db.session.get(Equipamento, ids["equipamento_a"])
        assert equipamento.situacao == SituacaoAtivoInativo.INATIVO


# 19. GESTOR consegue consultar
def test_gestor_consulta_equipamento(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.GESTOR)

    assert client.get("/equipamentos").status_code == 200
    assert client.get(f"/equipamentos/{ids['equipamento_a']}").status_code == 200


# 20. GESTOR não consegue criar
def test_gestor_nao_cria_equipamento(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.GESTOR)

    assert client.get("/equipamentos/novo").status_code == 403
    resp = client.post(
        "/equipamentos/novo",
        data={"nome": "X", "tipo": "Y", "unidade_id": ids["unidade_a"], "servico_id": "", "situacao": "ATIVO"},
    )
    assert resp.status_code == 403


# 21. GESTOR não consegue editar
def test_gestor_nao_edita_equipamento(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.GESTOR)

    assert client.get(f"/equipamentos/{ids['equipamento_a']}/editar").status_code == 403
    resp = client.post(f"/equipamentos/{ids['equipamento_a']}/situacao", data={"situacao": "INATIVO"})
    assert resp.status_code == 403


# 22. Unidade inexistente é rejeitada
def test_equipamento_com_unidade_inexistente_e_rejeitado(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/equipamentos/novo",
        data={"nome": "Equip Órfão", "tipo": "X", "unidade_id": 999999, "servico_id": "", "situacao": "ATIVO"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert Equipamento.query.filter_by(nome="Equip Órfão").first() is None


# 23. Serviço inexistente é rejeitado
def test_equipamento_com_servico_inexistente_e_rejeitado(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/equipamentos/novo",
        data={
            "nome": "Equip Servico Invalido",
            "tipo": "X",
            "unidade_id": ids["unidade_a"],
            "servico_id": 999999,
            "situacao": "ATIVO",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert Equipamento.query.filter_by(nome="Equip Servico Invalido").first() is None


# 24. Equipamento com serviço pertencente a outra unidade é rejeitado
def test_equipamento_com_servico_de_outra_unidade_e_rejeitado(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    # servico_a pertence à unidade_a; tentamos associá-lo à unidade_b
    resp = client.post(
        "/equipamentos/novo",
        data={
            "nome": "Equip Inconsistente",
            "tipo": "X",
            "unidade_id": ids["unidade_b"],
            "servico_id": ids["servico_a"],
            "situacao": "ATIVO",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "pertence a outra unidade" in resp.get_data(as_text=True)

    with app.app_context():
        assert Equipamento.query.filter_by(nome="Equip Inconsistente").first() is None


# 25. Situação inválida é rejeitada
def test_situacao_invalida_e_rejeitada_no_cadastro_equipamento(client, app):
    ids = _ids(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)

    resp = client.post(
        "/equipamentos/novo",
        data={
            "nome": "Equip Situacao Invalida",
            "tipo": "X",
            "unidade_id": ids["unidade_a"],
            "servico_id": "",
            "situacao": "NAO_EXISTE",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert Equipamento.query.filter_by(nome="Equip Situacao Invalida").first() is None
