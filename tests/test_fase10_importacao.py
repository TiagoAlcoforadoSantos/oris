"""
Testes da FASE 10 — importador de planilhas.

Roda contra SQLite em memória (TestingConfig). Gera arquivos CSV/XLSX
em memória (sem tocar disco fora do que a própria aplicação usa como
armazenamento temporário) para simular os uploads.
"""

import io
import os

import openpyxl
import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Alteracao,
    Auditoria,
    Equipamento,
    PerfilUsuario,
    Servico,
    SituacaoAtivoInativo,
    SituacaoUnidade,
    Unidade,
    Usuario,
)
from app.services.alteracoes_service import aprovar_alteracao, rejeitar_alteracao
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"

EMAILS = {
    PerfilUsuario.ADMINISTRADOR: "admin@oris.com.br",
    PerfilUsuario.GESTAO_INFORMACAO: "gestao@oris.com.br",
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL: "responsavel@oris.com.br",
    PerfilUsuario.GESTOR: "gestor@oris.com.br",
}

CABECALHO_UNIDADES = ["Nome da Unidade", "Codigo CNES", "Municipio", "Estado", "Situacao"]

MAPA_UNIDADES = {
    "mapa_nome": "Nome da Unidade",
    "mapa_cnes": "Codigo CNES",
    "mapa_cidade": "Municipio",
    "mapa_uf": "Estado",
    "mapa_situacao": "Situacao",
    "mapa_tipo": "",
    "mapa_endereco": "",
    "mapa_bairro": "",
}

# Formato unificado (Stage "importador x modelo de dados redesenhado"),
# ex.: REDE_SAUDE_RECIFE_GEO — uma linha pode descrever Unidade,
# Equipamento e/ou Serviço ao mesmo tempo (ver
# app/services/importacao_service.py).
CABECALHO_REDE = [
    "UNIDADE", "EQUIPAMENTO DE SAUDE", "TIPO EQUIPAMENTO", "TIPO SERVICO",
    "CNES", "UNIDADE E MISTA", "NOME", "NOME CURTO", "DS", "ENDERECO", "BAIRRO", "ATIVO",
]

MAPA_REDE = {
    "mapa_unidade_flag": "UNIDADE",
    "mapa_equipamento_flag": "EQUIPAMENTO DE SAUDE",
    "mapa_tipo_equipamento": "TIPO EQUIPAMENTO",
    "mapa_tipo_servico": "TIPO SERVICO",
    "mapa_cnes": "CNES",
    "mapa_unidade_mista": "UNIDADE E MISTA",
    "mapa_nome": "NOME",
    "mapa_nome_curto": "NOME CURTO",
    "mapa_ds": "DS",
    "mapa_endereco": "ENDERECO",
    "mapa_bairro": "BAIRRO",
    "mapa_ativo": "ATIVO",
}


def _linha_rede(unidade="N", equipamento="N", tipo_equip="", tipo_servico="", cnes="9999999",
                 mista="N", nome="", nome_curto="", ds="", endereco="", bairro="", ativo="S"):
    """Monta uma linha no formato unificado, na ordem de CABECALHO_REDE,
    com valores default sensatos — só é preciso informar o que o teste
    realmente exercita."""
    return [unidade, equipamento, tipo_equip, tipo_servico, cnes, mista, nome, nome_curto, ds, endereco, bairro, ativo]


def _csv_bytes(linhas):
    """`linhas` é uma lista de listas (cada uma uma linha da planilha,
    já incluindo o cabeçalho se houver)."""
    conteudo = "\n".join(",".join(str(v) for v in linha) for linha in linhas) + "\n"
    return conteudo.encode("utf-8")


def _xlsx_bytes(linhas):
    workbook = openpyxl.Workbook()
    planilha = workbook.active
    for linha in linhas:
        planilha.append(linha)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer.read()


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

        unidade_existente = Unidade(
            nome="UBS Existente",
            cnes="9990001",
            tipo="UBS",
            cidade="Recife",
            uf="PE",
            situacao=SituacaoUnidade.ATIVA,
        )
        db.session.add(unidade_existente)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, perfil):
    return client.post("/login", data={"email": EMAILS[perfil], "senha": SENHA}, follow_redirects=True)


def _usuario(app, perfil):
    with app.app_context():
        return Usuario.query.filter_by(email=EMAILS[perfil]).first()


def _upload_e_mapear(client, conteudo_bytes, nome_arquivo, entidade="unidades"):
    data = {"entidade": entidade, "arquivo": (io.BytesIO(conteudo_bytes), nome_arquivo)}
    return client.post("/importacao/mapear", data=data, content_type="multipart/form-data")


def _extrair_token(html):
    import re

    m = re.search(r'name="token" value="([^"]+)"', html)
    return m.group(1) if m else None


def _fluxo_completo_unidade_valida(client, linhas, mapa=None):
    """Faz upload + mapeamento + validação de uma planilha de unidades
    válida, retornando (token, resposta_da_previa)."""
    resp = _upload_e_mapear(client, _csv_bytes(linhas), "unidades.csv")
    token = _extrair_token(resp.get_data(as_text=True))
    resp = client.post(
        "/importacao/validar",
        data={"entidade": "unidades", "token": token, "extensao": ".csv", **(mapa or MAPA_UNIDADES)},
    )
    return token, resp


def _fluxo_completo_rede(client, linhas, mapa=None):
    """Mesmo fluxo de `_fluxo_completo_unidade_valida`, mas para a
    entidade "rede" (formato unificado)."""
    resp = _upload_e_mapear(client, _csv_bytes(linhas), "rede.csv", entidade="rede")
    token = _extrair_token(resp.get_data(as_text=True))
    resp = client.post(
        "/importacao/validar",
        data={"entidade": "rede", "token": token, "extensao": ".csv", **(mapa or MAPA_REDE)},
    )
    return token, resp


def _confirmar_rede(client, token, mapa=None, follow_redirects=True):
    return client.post(
        "/importacao/confirmar",
        data={"entidade": "rede", "token": token, "extensao": ".csv", **(mapa or MAPA_REDE)},
        follow_redirects=follow_redirects,
    )


# ----------------------------------------------------------------
# 1-3. Acesso
# ----------------------------------------------------------------

def test_pagina_de_importacao_acessivel_para_perfil_autorizado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get("/importacao/nova?entidade=unidades")
    assert resp.status_code == 200


def test_gestor_nao_pode_importar(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/importacao/nova?entidade=unidades")
    assert resp.status_code == 403


def test_usuario_nao_autenticado_nao_acessa(client):
    resp = client.get("/importacao", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ----------------------------------------------------------------
# 4-5. Upload XLSX e CSV válidos
# ----------------------------------------------------------------

def test_upload_xlsx_valido(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS Nova XLSX", "1112223", "Recife", "PE", "ATIVA"]]
    resp = _upload_e_mapear(client, _xlsx_bytes(linhas), "unidades.xlsx")
    assert resp.status_code == 200
    assert "Mapeamento de Colunas" in resp.get_data(as_text=True)


def test_upload_csv_valido(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS Nova CSV", "1112224", "Recife", "PE", "ATIVA"]]
    resp = _upload_e_mapear(client, _csv_bytes(linhas), "unidades.csv")
    assert resp.status_code == 200
    assert "Mapeamento de Colunas" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 6-9. Rejeições de arquivo
# ----------------------------------------------------------------

def test_extensao_invalida_e_rejeitada(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = _upload_e_mapear(client, b"conteudo qualquer", "arquivo.txt")
    assert resp.status_code == 302
    resp = client.get(resp.headers["Location"])
    assert "não aceito" in resp.get_data(as_text=True) or "Formato" in resp.get_data(as_text=True)


def test_arquivo_vazio_e_rejeitado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = _upload_e_mapear(client, b"", "unidades.csv")
    assert resp.status_code == 302
    resp = client.get(resp.headers["Location"])
    assert "vazio" in resp.get_data(as_text=True).lower()


def test_planilha_sem_cabecalho_e_rejeitada(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    conteudo = _csv_bytes([["", "", "", "", ""], ["UBS Teste", "1234567", "Recife", "PE", "ATIVA"]])
    resp = _upload_e_mapear(client, conteudo, "unidades.csv")
    assert resp.status_code == 302
    resp = client.get(resp.headers["Location"])
    assert "cabeçalho" in resp.get_data(as_text=True).lower()


def test_planilha_sem_dados_e_rejeitada(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = _upload_e_mapear(client, _csv_bytes([CABECALHO_UNIDADES]), "unidades.csv")
    assert resp.status_code == 302
    resp = client.get(resp.headers["Location"])
    assert "nenhuma linha" in resp.get_data(as_text=True).lower()


# ----------------------------------------------------------------
# 10. Mapeamento correto funciona
# ----------------------------------------------------------------

def test_mapeamento_correto_funciona(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS Mapeada", "1112225", "Recife", "PE", "ATIVA"]]
    token, resp = _fluxo_completo_unidade_valida(client, linhas)
    assert resp.status_code == 200
    assert "UBS Mapeada" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 11-15. Erros de validação
# ----------------------------------------------------------------

def test_campo_obrigatorio_ausente_gera_erro(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["", "1112226", "Recife", "PE", "ATIVA"]]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    assert resp.status_code == 200
    assert "obrigatório" in resp.get_data(as_text=True).lower()


def test_cnes_invalido_gera_erro(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS X", "abc123", "Recife", "PE", "ATIVA"]]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    assert resp.status_code == 200
    assert "CNES deve conter apenas números" in resp.get_data(as_text=True)


def test_cnes_duplicado_dentro_da_planilha_nao_e_mais_erro(client):
    # Stage "modelo de dados" (migration 0001): CNES deixou de ser
    # identificador único — o mesmo CNES pode aparecer em mais de um
    # registro de Unidade (ex.: unidade mista). Duas linhas com o
    # mesmo CNES na mesma planilha não é mais um erro de validação.
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [
        CABECALHO_UNIDADES,
        ["UBS A", "1112227", "Recife", "PE", "ATIVA"],
        ["UBS B", "1112227", "Recife", "PE", "ATIVA"],
    ]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "duplicado" not in html.lower()
    assert "UBS A" in html
    assert "UBS B" in html
    assert html.count("oris-import-badge-novo") == 2


def test_uf_invalida_gera_erro(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS X", "1112228", "Recife", "Pernambuco", "ATIVA"]]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    assert resp.status_code == 200
    assert "sigla da UF" in resp.get_data(as_text=True)


def test_situacao_invalida_gera_erro(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS X", "1112229", "Recife", "PE", "FECHADA"]]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    assert resp.status_code == 200
    assert "ATIVA, INATIVA ou MANUTENCAO" in resp.get_data(as_text=True)


# ----------------------------------------------------------------
# 16. Prévia mostra os dados corretos
# ----------------------------------------------------------------

def test_previa_mostra_dados_corretos(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS Prévia", "1112230", "Recife", "PE", "ATIVA"]]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    html = resp.get_data(as_text=True)
    assert "UBS Prévia" in html
    assert "1112230" in html
    assert "Recife" in html


# ----------------------------------------------------------------
# 17-19. Classificação novo/existente sem alteração/existente alterado
# ----------------------------------------------------------------

def test_registro_novo_e_identificado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS Totalmente Nova", "1112231", "Recife", "PE", "ATIVA"]]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    html = resp.get_data(as_text=True)
    assert "Novo" in html


def test_registro_existente_sem_alteracao_e_identificado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    # Mesmos dados da unidade já existente (criada no fixture)
    linhas = [CABECALHO_UNIDADES, ["UBS Existente", "9990001", "Recife", "PE", "ATIVA"]]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    html = resp.get_data(as_text=True)
    assert "Sem alteração" in html


def test_registro_existente_alterado_e_identificado(client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    # Mesmo CNES da unidade existente, mas nome diferente
    linhas = [CABECALHO_UNIDADES, ["UBS Existente (Renomeada)", "9990001", "Recife", "PE", "ATIVA"]]
    _, resp = _fluxo_completo_unidade_valida(client, linhas)
    html = resp.get_data(as_text=True)
    assert "Alterado" in html


# ----------------------------------------------------------------
# 20-21. Confirmação não aplica direto; fica PENDENTE
# ----------------------------------------------------------------

def test_confirmacao_nao_aplica_diretamente_e_fica_pendente(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_UNIDADES, ["UBS Pendente", "1112232", "Recife", "PE", "ATIVA"]]
    token, _ = _fluxo_completo_unidade_valida(client, linhas)

    resp = client.post(
        "/importacao/confirmar",
        data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        # 20. não foi aplicada diretamente
        assert Unidade.query.filter_by(cnes="1112232").first() is None
        # 21. fica PENDENTE
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        assert alteracao is not None
        assert alteracao.status.value == "PENDENTE"


# ----------------------------------------------------------------
# 22-24. Segregação de funções e aprovação (Fase 7)
# ----------------------------------------------------------------

def test_solicitante_nao_aprova_a_propria_importacao(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_UNIDADES, ["UBS Auto", "1112233", "Recife", "PE", "ATIVA"]]
    token, _ = _fluxo_completo_unidade_valida(client, linhas)
    client.post("/importacao/confirmar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        solicitante = _usuario(app, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
        ok, mensagem = aprovar_alteracao(alteracao, solicitante)
        assert ok is False
        assert "própria alteração" in mensagem


def test_usuario_autorizado_aprova_e_alteracao_e_aplicada(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_UNIDADES, ["UBS Aprovada", "1112234", "Recife", "PE", "ATIVA"]]
    token, _ = _fluxo_completo_unidade_valida(client, linhas)
    client.post("/importacao/confirmar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        # 23. usuário autorizado consegue aprovar
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True
        # 24. após aprovação, a alteração é aplicada
        unidade = Unidade.query.filter_by(cnes="1112234").first()
        assert unidade is not None
        assert unidade.nome == "UBS Aprovada"


# ----------------------------------------------------------------
# 25. Rejeição não altera o registro original
# ----------------------------------------------------------------

def test_rejeicao_nao_altera_registro_original(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    # Solicita edição da unidade já existente
    linhas = [CABECALHO_UNIDADES, ["UBS Existente (Tentativa)", "9990001", "Recife", "PE", "ATIVA"]]
    token, _ = _fluxo_completo_unidade_valida(client, linhas)
    client.post("/importacao/confirmar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="EDITAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        ok, _ = rejeitar_alteracao(alteracao, aprovador)
        assert ok is True

        unidade = Unidade.query.filter_by(cnes="9990001").first()
        assert unidade.nome == "UBS Existente"  # nome original, não o da planilha


# ----------------------------------------------------------------
# 26. Auditoria gerada corretamente
# ----------------------------------------------------------------

def test_auditoria_e_gerada_corretamente(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_UNIDADES, ["UBS Auditada", "1112235", "Recife", "PE", "ATIVA"]]
    token, _ = _fluxo_completo_unidade_valida(client, linhas)
    client.post("/importacao/confirmar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES})

    with app.app_context():
        assert Auditoria.query.filter_by(acao="SOLICITAR_ALTERACAO", tabela="unidades").first() is not None
        assert Auditoria.query.filter_by(acao="IMPORTAR_PLANILHA", tabela="unidades").first() is not None

        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        aprovar_alteracao(alteracao, aprovador)

        assert Auditoria.query.filter_by(acao="CRIAR", tabela="unidades", registro_id=alteracao.registro_id).first() is not None
        assert Auditoria.query.filter_by(acao="APROVAR_ALTERACAO").first() is not None


# ----------------------------------------------------------------
# 27. Senha/hash nunca aparecem nos dados registrados
# ----------------------------------------------------------------

def test_senha_e_hash_nao_aparecem_nos_dados_registrados(client, app):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS Segura", "1112236", "Recife", "PE", "ATIVA"]]
    token, _ = _fluxo_completo_unidade_valida(client, linhas)
    client.post("/importacao/confirmar", data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES})

    with app.app_context():
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").first()
        assert "senha" not in alteracao.dados_novos.lower()
        assert "$2b$" not in alteracao.dados_novos

        for registro in Auditoria.query.all():
            texto = " ".join(filter(None, [registro.descricao, registro.valor_anterior, registro.valor_novo]))
            assert "$2b$" not in texto
            assert SENHA not in texto


# ----------------------------------------------------------------
# 28. Arquivo temporário é removido após processamento
# ----------------------------------------------------------------

def test_arquivo_temporario_e_removido_apos_processamento(client):
    from app.routes.importacao import _caminho_do_token

    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["UBS Temp", "1112237", "Recife", "PE", "ATIVA"]]
    resp = _upload_e_mapear(client, _csv_bytes(linhas), "unidades.csv")
    token = _extrair_token(resp.get_data(as_text=True))

    caminho = _caminho_do_token(token)
    assert os.path.exists(caminho)

    client.post(
        "/importacao/validar",
        data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES},
    )
    client.post(
        "/importacao/confirmar",
        data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES},
    )

    assert not os.path.exists(caminho)


def test_arquivo_temporario_e_removido_quando_validacao_falha(client):
    from app.routes.importacao import _caminho_do_token

    _login(client, PerfilUsuario.ADMINISTRADOR)
    linhas = [CABECALHO_UNIDADES, ["", "1112238", "Recife", "PE", "ATIVA"]]  # nome ausente -> invalido
    resp = _upload_e_mapear(client, _csv_bytes(linhas), "unidades.csv")
    token = _extrair_token(resp.get_data(as_text=True))
    caminho = _caminho_do_token(token)
    assert os.path.exists(caminho)

    client.post(
        "/importacao/validar",
        data={"entidade": "unidades", "token": token, "extensao": ".csv", **MAPA_UNIDADES},
    )

    assert not os.path.exists(caminho)


# ----------------------------------------------------------------
# 29. Template de planilha pode ser obtido
# ----------------------------------------------------------------

@pytest.mark.parametrize("entidade", ["unidades", "servicos", "equipamentos"])
def test_template_de_planilha_pode_ser_obtido(client, entidade):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    resp = client.get(f"/importacao/template/{entidade}")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert len(resp.get_data()) > 0


def test_gestor_nao_pode_baixar_template(client):
    _login(client, PerfilUsuario.GESTOR)
    resp = client.get("/importacao/template/unidades")
    assert resp.status_code == 403


# ----------------------------------------------------------------
# 30. A suíte completa das Fases 1-9 é executada junto com esta —
# ver `pytest tests/` (relatório da fase). Este teste apenas garante
# que os blueprints/serviços novos não quebraram o restante da app.
# ----------------------------------------------------------------

def test_rotas_da_aplicacao_continuam_registradas_apos_fase10(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "unidades.listar" in endpoints
    assert "alteracoes.listar" in endpoints
    assert "auditoria.listar" in endpoints
    assert "dashboard.index" in endpoints
    assert "importacao.index" in endpoints


# ==================================================================
# Entidade "rede" — formato unificado (Stage "importador x modelo de
# dados redesenhado", ex.: REDE_SAUDE_RECIFE_GEO). Uma linha pode
# descrever Unidade, Serviço e/ou Equipamento simultaneamente; CNES
# não é identificador único; vínculos com Unidade são opcionais.
# ==================================================================

def _aprovar_todas_pendentes(app, tabela=None):
    """Aprova, como ADMINISTRADOR, toda Alteracao PENDENTE (opcionalmente
    filtrando por tabela) criada por outro usuário — helper só para
    reduzir repetição nos testes abaixo."""
    with app.app_context():
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        query = Alteracao.query.filter_by(status="PENDENTE") if tabela is None else Alteracao.query.filter_by(status="PENDENTE", tabela=tabela)
        for alteracao in query.all():
            ok, mensagem = aprovar_alteracao(alteracao, aprovador)
            assert ok is True, mensagem


# 1. Duas unidades com o mesmo CNES (unidade mista)
def test_rede_duas_unidades_com_mesmo_cnes(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [
        CABECALHO_REDE,
        _linha_rede(unidade="S", cnes="5551111", nome="Policlínica Recife"),
        _linha_rede(unidade="S", cnes="5551111", nome="Maternidade Recife", mista="S"),
    ]
    token, resp = _fluxo_completo_rede(client, linhas)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Policlínica Recife" in html
    assert "Maternidade Recife" in html
    assert html.count("oris-import-badge-novo") == 2

    _confirmar_rede(client, token)
    _aprovar_todas_pendentes(app, tabela="unidades")

    with app.app_context():
        unidades = Unidade.query.filter_by(cnes="5551111").all()
        assert len(unidades) == 2
        assert {u.nome for u in unidades} == {"Policlínica Recife", "Maternidade Recife"}


# 2. Unidade com CNES 9999999 (convenção "sem CNES real")
def test_rede_unidade_com_cnes_9999999(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(unidade="S", cnes="9999999", nome="UBS Sem CNES Próprio")]
    _, resp = _fluxo_completo_rede(client, linhas)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "UBS Sem CNES Próprio" in html
    assert "Novo" in html


# 3. Serviço sem unidade
def test_rede_servico_sem_unidade(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(tipo_servico="Vacinação em Shopping", cnes="9999999")]
    token, resp = _fluxo_completo_rede(client, linhas)
    assert resp.status_code == 200
    assert "erro" not in resp.get_data(as_text=True).lower() or "SERVICO" in resp.get_data(as_text=True)

    _confirmar_rede(client, token)
    _aprovar_todas_pendentes(app, tabela="servicos")

    with app.app_context():
        servico = Servico.query.filter_by(nome="Vacinação em Shopping").first()
        assert servico is not None
        assert servico.unidade_id is None


# 4. Equipamento sem unidade
def test_rede_equipamento_sem_unidade(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(equipamento="S", cnes="9999999", nome="Ambulância SAMU", tipo_equip="Ambulância")]
    token, _ = _fluxo_completo_rede(client, linhas)

    _confirmar_rede(client, token)
    _aprovar_todas_pendentes(app, tabela="equipamentos")

    with app.app_context():
        equipamento = Equipamento.query.filter_by(nome="Ambulância SAMU").first()
        assert equipamento is not None
        assert equipamento.unidade_id is None


# 5. Equipamento relacionado a um Serviço já existente (link seguro:
#    exatamente uma correspondência por nome)
def test_rede_equipamento_relacionado_a_servico_existente(client, app):
    with app.app_context():
        db.session.add(Servico(nome="Endodontia", unidade_id=None, situacao=SituacaoAtivoInativo.ATIVO))
        db.session.commit()

    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [
        CABECALHO_REDE,
        _linha_rede(equipamento="S", cnes="9999999", nome="Cadeira Odontológica", tipo_equip="Cadeira", tipo_servico="Endodontia"),
    ]
    token, _ = _fluxo_completo_rede(client, linhas)
    _confirmar_rede(client, token)
    _aprovar_todas_pendentes(app, tabela="equipamentos")

    with app.app_context():
        servico = Servico.query.filter_by(nome="Endodontia").first()
        equipamento = Equipamento.query.filter_by(nome="Cadeira Odontológica").first()
        assert equipamento is not None
        assert equipamento.servico_id == servico.id


# 6. Serviço com nome ambíguo (mais de uma correspondência) não é
#    vinculado automaticamente ao Equipamento — vira aviso, não erro
def test_rede_equipamento_relacionado_a_servico_ambiguo_gera_aviso_sem_erro(client, app):
    with app.app_context():
        db.session.add(Servico(nome="Fisioterapia", unidade_id=None, situacao=SituacaoAtivoInativo.ATIVO))
        db.session.add(Servico(nome="Fisioterapia", unidade_id=None, situacao=SituacaoAtivoInativo.ATIVO))
        db.session.commit()

    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [
        CABECALHO_REDE,
        _linha_rede(equipamento="S", cnes="9999999", nome="Aparelho de Fisioterapia", tipo_equip="Aparelho", tipo_servico="Fisioterapia"),
    ]
    token, resp = _fluxo_completo_rede(client, linhas)
    assert resp.status_code == 200
    assert "ambígua" in resp.get_data(as_text=True).lower()

    _confirmar_rede(client, token)
    _aprovar_todas_pendentes(app, tabela="equipamentos")

    with app.app_context():
        equipamento = Equipamento.query.filter_by(nome="Aparelho de Fisioterapia").first()
        assert equipamento is not None
        assert equipamento.servico_id is None  # ambíguo -> sem vínculo automático, não é erro


# 7. Unidade com múltiplos serviços (vínculo seguro via CNES único)
def test_rede_unidade_com_multiplos_servicos(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [
        CABECALHO_REDE,
        _linha_rede(unidade="S", cnes="5552222", nome="UBS Multi Serviço"),
    ]
    token, _ = _fluxo_completo_rede(client, linhas)
    _confirmar_rede(client, token)
    _aprovar_todas_pendentes(app, tabela="unidades")

    linhas_servicos = [
        CABECALHO_REDE,
        _linha_rede(tipo_servico="Clínica Geral", cnes="5552222"),
        _linha_rede(tipo_servico="Odontopediatria", cnes="5552222"),
    ]
    token, resp = _fluxo_completo_rede(client, linhas_servicos)
    assert resp.status_code == 200
    _confirmar_rede(client, token)
    _aprovar_todas_pendentes(app, tabela="servicos")

    with app.app_context():
        unidade = Unidade.query.filter_by(cnes="5552222").first()
        assert unidade.servicos.count() == 2


# 8-10. Classificação de linha (UNIDADE / EQUIPAMENTO / SERVICO)
def test_rede_classificacao_unidade(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(unidade="S", cnes="5553333", nome="UBS Classificação")]
    _, resp = _fluxo_completo_rede(client, linhas)
    html = resp.get_data(as_text=True)
    # O nome das colunas mapeadas ("TIPO SERVICO" etc.) sempre aparece
    # nos campos ocultos do formulário, então a checagem é pela célula
    # de "Tipo" da prévia, não por substring solta na página inteira.
    assert "<td>UNIDADE</td>" in html
    assert "<td>SERVICO</td>" not in html
    assert "<td>EQUIPAMENTO</td>" not in html


def test_rede_classificacao_equipamento(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(equipamento="S", cnes="5554444", nome="Autoclave", tipo_equip="Esterilização")]
    _, resp = _fluxo_completo_rede(client, linhas)
    html = resp.get_data(as_text=True)
    assert "<td>EQUIPAMENTO</td>" in html
    assert "<td>UNIDADE</td>" not in html


def test_rede_classificacao_servico(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(tipo_servico="Prótese Dentária", cnes="5555555")]
    _, resp = _fluxo_completo_rede(client, linhas)
    html = resp.get_data(as_text=True)
    assert "<td>SERVICO</td>" in html
    assert "<td>UNIDADE</td>" not in html


# 11. Linha com dados insuficientes (nenhum indicador preenchido)
def test_rede_linha_com_dados_insuficientes_gera_erro(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(unidade="N", equipamento="N", tipo_servico="", cnes="5556666")]
    _, resp = _fluxo_completo_rede(client, linhas)
    assert resp.status_code == 200
    assert "dados suficientes" in resp.get_data(as_text=True).lower()


# 12. Prévia contendo tipos diferentes na mesma planilha
def test_rede_previa_contendo_tipos_diferentes(client):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [
        CABECALHO_REDE,
        _linha_rede(unidade="S", cnes="5557777", nome="UBS Mista Tipos"),
        _linha_rede(equipamento="S", cnes="5557777", nome="Cadeira X", tipo_equip="Cadeira"),
        _linha_rede(tipo_servico="Clínica Geral", cnes="5557777"),
    ]
    _, resp = _fluxo_completo_rede(client, linhas)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "UNIDADE" in html
    assert "EQUIPAMENTO" in html
    assert "SERVICO" in html


# 13. Fluxo de aprovação após importação (fica PENDENTE, só aplica ao aprovar)
def test_rede_fluxo_de_aprovacao_apos_importacao(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(unidade="S", cnes="5558888", nome="UBS Aprovação Rede")]
    token, _ = _fluxo_completo_rede(client, linhas)
    _confirmar_rede(client, token)

    with app.app_context():
        assert Unidade.query.filter_by(cnes="5558888").first() is None
        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").order_by(Alteracao.id.desc()).first()
        assert alteracao.status.value == "PENDENTE"

        solicitante = _usuario(app, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
        ok, mensagem = aprovar_alteracao(alteracao, solicitante)
        assert ok is False  # segregação de funções também vale para a importação "rede"

        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        ok, _ = aprovar_alteracao(alteracao, aprovador)
        assert ok is True
        assert Unidade.query.filter_by(cnes="5558888").first() is not None


# 14. Auditoria gerada corretamente para a importação "rede"
def test_rede_auditoria_apos_aplicacao_aprovada(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(unidade="S", cnes="5559999", nome="UBS Auditoria Rede")]
    token, _ = _fluxo_completo_rede(client, linhas)
    _confirmar_rede(client, token)

    with app.app_context():
        assert Auditoria.query.filter_by(acao="IMPORTAR_PLANILHA", tabela="rede").first() is not None
        assert Auditoria.query.filter_by(acao="SOLICITAR_ALTERACAO", tabela="unidades").first() is not None

        alteracao = Alteracao.query.filter_by(tabela="unidades", operacao="CRIAR").order_by(Alteracao.id.desc()).first()
        aprovador = _usuario(app, PerfilUsuario.ADMINISTRADOR)
        aprovar_alteracao(alteracao, aprovador)

        assert Auditoria.query.filter_by(acao="CRIAR", tabela="unidades", registro_id=alteracao.registro_id).first() is not None


# 15. Revalidação na confirmação evita gravação parcial ("rollback" a
#     nível de importação): se os dados mudaram entre a prévia e a
#     confirmação (aqui simulado com um mapeamento que invalida uma
#     linha), nenhuma Alteracao é criada para o lote.
def test_rede_confirmacao_com_revalidacao_invalida_nao_grava_nada(client, app):
    _login(client, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL)
    linhas = [CABECALHO_REDE, _linha_rede(unidade="S", cnes="5551010", nome="UBS Rollback")]
    token, resp = _fluxo_completo_rede(client, linhas)
    assert resp.status_code == 200

    with app.app_context():
        antes = Alteracao.query.count()

    mapa_quebrado = dict(MAPA_REDE)
    mapa_quebrado["mapa_cnes"] = ""  # desmapeia CNES -> linha fica inválida na revalidação
    resp = _confirmar_rede(client, token, mapa=mapa_quebrado, follow_redirects=True)
    assert resp.status_code == 200
    assert "mudaram" in resp.get_data(as_text=True).lower() or "novamente" in resp.get_data(as_text=True).lower()

    with app.app_context():
        depois = Alteracao.query.count()
        assert depois == antes
        assert Unidade.query.filter_by(cnes="5551010").first() is None
