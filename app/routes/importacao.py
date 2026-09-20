"""
Importador de planilhas (Fase 10).

Fluxo: upload → leitura → mapeamento de colunas → validação →
pré-visualização → confirmação → solicitação PENDENTE → aprovação
(Fase 7) → aplicação → auditoria (Fase 8).

O upload NUNCA escreve direto nas tabelas de negócio. Cada linha
válida da planilha vira uma solicitação de Alteracao PENDENTE (via
app.services.alteracoes_service.registrar_alteracao) — a aplicação
de fato só acontece quando alguém aprova em /alteracoes, exatamente
como qualquer outra alteração desde a Fase 7. Nenhum mecanismo novo
de aprovação foi criado aqui.

Segurança do upload: extensão validada contra uma lista fechada,
tamanho limitado, nome de arquivo em disco sempre gerado pelo
servidor (nunca o nome enviado pelo usuário), armazenamento em uma
pasta temporária dedicada (fora de `static`/`templates`), e remoção
do arquivo assim que ele deixa de ser necessário (falha de validação
ou confirmação concluída).
"""

import csv
import io
import os
import tempfile
import uuid

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import PerfilUsuario
from app.services.alteracoes_service import registrar_alteracao
from app.services.auditoria_service import registrar_auditoria
from app.services.importacao_service import (
    CAMPOS_POR_ENTIDADE,
    EXTENSOES_ACEITAS,
    LIMITE_LINHAS,
    LIMITE_TAMANHO_BYTES,
    LINHAS_PREVIA,
    RÓTULOS_CAMPOS,
    ArquivoInvalidoError,
    detectar_mapeamento_automatico,
    ler_planilha,
    validar_e_classificar,
)
from app.utils.decorators import login_required, roles_required, usuario_atual

importacao_bp = Blueprint("importacao", __name__, url_prefix="/importacao")

PERFIS_QUE_IMPORTAM = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL.value,
)

ENTIDADES_VALIDAS = ("unidades", "servicos", "equipamentos", "rede")

NOMES_SINGULAR = {"unidades": "unidade", "servicos": "serviço", "equipamentos": "equipamento", "rede": "registro"}

# Entidade "rede" (formato unificado, ex.: REDE_SAUDE_RECIFE_GEO): uma
# linha pode gerar sub-registros de mais de um tipo (ver
# app/services/importacao_service.py). Cada sub-registro precisa ser
# direcionado à sua própria tabela/nome singular na confirmação, em
# vez de usar a entidade "rede" (que não é uma tabela de negócio).
_TABELA_POR_TIPO_REDE = {"UNIDADE": "unidades", "SERVICO": "servicos", "EQUIPAMENTO": "equipamentos"}
_SINGULAR_POR_TIPO_REDE = {"UNIDADE": "unidade", "SERVICO": "serviço", "EQUIPAMENTO": "equipamento"}


# ----------------------------------------------------------------
# Armazenamento temporário do arquivo enviado
# ----------------------------------------------------------------

def _diretorio_temporario():
    """Pasta dedicada para os arquivos temporários da importação —
    fora de `static`/`templates`, então nunca é servida diretamente
    pelo Flask. Fica sob o diretório temporário do sistema."""
    caminho = os.path.join(tempfile.gettempdir(), "oris_importacoes")
    os.makedirs(caminho, exist_ok=True)
    return caminho


def _salvar_arquivo_temporario(arquivo, extensao):
    """Salva o arquivo enviado com um nome gerado pelo servidor (nunca
    o nome enviado pelo usuário) e devolve o token (nome do arquivo em
    disco) usado para localizá-lo nas próximas etapas."""
    token = f"{uuid.uuid4().hex}{extensao}"
    caminho = os.path.join(_diretorio_temporario(), token)
    arquivo.save(caminho)
    return token


def _caminho_do_token(token):
    """Resolve um token para o caminho completo em disco, sempre
    dentro da pasta temporária dedicada — o token é um nome de
    arquivo gerado pelo servidor (uuid4 + extensão fixa), nunca um
    caminho fornecido pelo usuário, então não há risco de path
    traversal aqui."""
    if not token or "/" in token or "\\" in token or ".." in token:
        abort(400)
    return os.path.join(_diretorio_temporario(), token)


def _remover_temporario(token):
    """Remove o arquivo temporário, se existir — best-effort: se já
    tiver sido removido ou o caminho não existir, não é um erro."""
    if not token:
        return
    caminho = _caminho_do_token(token)
    try:
        if os.path.exists(caminho):
            os.remove(caminho)
    except OSError:
        pass


def _validar_entidade_ou_400(entidade):
    if entidade not in ENTIDADES_VALIDAS:
        abort(400)


def _extrair_mapeamento_do_formulario(entidade):
    campos = CAMPOS_POR_ENTIDADE[entidade]["obrigatorios"] + CAMPOS_POR_ENTIDADE[entidade]["opcionais"]
    return {campo: (request.form.get(f"mapa_{campo}") or None) for campo in campos}


# ----------------------------------------------------------------
# Tela principal
# ----------------------------------------------------------------

@importacao_bp.route("")
@login_required
def index():
    usuario = usuario_atual()
    pode_importar = usuario.perfil.value in PERFIS_QUE_IMPORTAM
    return render_template(
        "importacao/index.html",
        pode_importar=pode_importar,
        entidades=ENTIDADES_VALIDAS,
        limite_linhas=LIMITE_LINHAS,
        limite_tamanho_mb=LIMITE_TAMANHO_BYTES // (1024 * 1024),
    )


@importacao_bp.route("/template/<entidade>")
@roles_required(*PERFIS_QUE_IMPORTAM)
def template(entidade):
    _validar_entidade_ou_400(entidade)

    campos = CAMPOS_POR_ENTIDADE[entidade]["obrigatorios"] + CAMPOS_POR_ENTIDADE[entidade]["opcionais"]
    cabecalho = [RÓTULOS_CAMPOS[campo] for campo in campos]

    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(cabecalho)

    conteudo = buffer.getvalue()
    return Response(
        conteudo,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=modelo_{entidade}.csv"},
    )


# ----------------------------------------------------------------
# Etapa 1: upload
# ----------------------------------------------------------------

@importacao_bp.route("/nova")
@roles_required(*PERFIS_QUE_IMPORTAM)
def nova():
    entidade = request.args.get("entidade", "unidades")
    _validar_entidade_ou_400(entidade)
    return render_template(
        "importacao/nova.html",
        entidade=entidade,
        entidades=ENTIDADES_VALIDAS,
        extensoes_aceitas=EXTENSOES_ACEITAS,
        limite_linhas=LIMITE_LINHAS,
        limite_tamanho_mb=LIMITE_TAMANHO_BYTES // (1024 * 1024),
    )


# ----------------------------------------------------------------
# Etapa 2: mapeamento de colunas
# ----------------------------------------------------------------

@importacao_bp.route("/mapear", methods=["POST"])
@roles_required(*PERFIS_QUE_IMPORTAM)
def mapear():
    entidade = request.form.get("entidade", "")
    _validar_entidade_ou_400(entidade)

    arquivo = request.files.get("arquivo")
    if arquivo is None or arquivo.filename == "":
        flash("Selecione um arquivo para enviar.", "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    nome_original = arquivo.filename
    extensao = os.path.splitext(nome_original)[1].lower()
    if extensao not in EXTENSOES_ACEITAS:
        flash("Formato de arquivo não aceito. Envie um arquivo .csv ou .xlsx.", "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    arquivo.stream.seek(0, os.SEEK_END)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)

    if tamanho == 0:
        flash("O arquivo está vazio.", "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    if tamanho > LIMITE_TAMANHO_BYTES:
        flash(f"O arquivo excede o limite de {LIMITE_TAMANHO_BYTES // (1024 * 1024)} MB.", "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    token = _salvar_arquivo_temporario(arquivo, extensao)
    caminho = _caminho_do_token(token)

    try:
        df = ler_planilha(caminho, extensao)
    except ArquivoInvalidoError as erro:
        _remover_temporario(token)
        flash(str(erro), "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    colunas = list(df.columns)
    mapeamento_sugerido = detectar_mapeamento_automatico(colunas, entidade)

    return render_template(
        "importacao/mapeamento.html",
        entidade=entidade,
        token=token,
        extensao=extensao,
        nome_original=nome_original,
        colunas=colunas,
        campos_obrigatorios=CAMPOS_POR_ENTIDADE[entidade]["obrigatorios"],
        campos_opcionais=CAMPOS_POR_ENTIDADE[entidade]["opcionais"],
        rotulos=RÓTULOS_CAMPOS,
        mapeamento_sugerido=mapeamento_sugerido,
    )


# ----------------------------------------------------------------
# Etapa 3: validação + Etapa 4: pré-visualização
# ----------------------------------------------------------------

@importacao_bp.route("/validar", methods=["POST"])
@roles_required(*PERFIS_QUE_IMPORTAM)
def validar():
    entidade = request.form.get("entidade", "")
    _validar_entidade_ou_400(entidade)

    token = request.form.get("token", "")
    extensao = request.form.get("extensao", "")
    caminho = _caminho_do_token(token)

    if not os.path.exists(caminho):
        flash("O arquivo temporário não foi encontrado — envie a planilha novamente.", "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    mapeamento = _extrair_mapeamento_do_formulario(entidade)

    campos_obrigatorios = CAMPOS_POR_ENTIDADE[entidade]["obrigatorios"]
    campos_sem_mapeamento = [campo for campo in campos_obrigatorios if not mapeamento.get(campo)]

    try:
        df = ler_planilha(caminho, extensao)
    except ArquivoInvalidoError as erro:
        _remover_temporario(token)
        flash(str(erro), "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    if campos_sem_mapeamento:
        nomes = ", ".join(RÓTULOS_CAMPOS[campo] for campo in campos_sem_mapeamento)
        flash(f"Selecione a coluna correspondente a: {nomes}.", "danger")
        return render_template(
            "importacao/mapeamento.html",
            entidade=entidade,
            token=token,
            extensao=extensao,
            nome_original="",
            colunas=list(df.columns),
            campos_obrigatorios=CAMPOS_POR_ENTIDADE[entidade]["obrigatorios"],
            campos_opcionais=CAMPOS_POR_ENTIDADE[entidade]["opcionais"],
            rotulos=RÓTULOS_CAMPOS,
            mapeamento_sugerido=mapeamento,
        )

    resultado = validar_e_classificar(df, mapeamento, entidade)

    if resultado["invalidos"] > 0:
        _remover_temporario(token)
        return render_template(
            "importacao/validacao_erros.html",
            entidade=entidade,
            resultado=resultado,
        )

    contagens = {"novo": 0, "alterado": 0, "sem_alteracao": 0}
    for linha in resultado["linhas"]:
        contagens[linha["classificacao"]] += 1

    return render_template(
        "importacao/previa.html",
        entidade=entidade,
        token=token,
        extensao=extensao,
        mapeamento=mapeamento,
        resultado=resultado,
        linhas_previa=resultado["linhas"][:LINHAS_PREVIA],
        contagens=contagens,
        campos_todos=CAMPOS_POR_ENTIDADE[entidade]["obrigatorios"] + CAMPOS_POR_ENTIDADE[entidade]["opcionais"],
        rotulos=RÓTULOS_CAMPOS,
    )


# ----------------------------------------------------------------
# Etapa 5: confirmação (cria as solicitações PENDENTES)
# ----------------------------------------------------------------

@importacao_bp.route("/confirmar", methods=["POST"])
@roles_required(*PERFIS_QUE_IMPORTAM)
def confirmar():
    entidade = request.form.get("entidade", "")
    _validar_entidade_ou_400(entidade)

    token = request.form.get("token", "")
    extensao = request.form.get("extensao", "")
    caminho = _caminho_do_token(token)

    if not os.path.exists(caminho):
        flash("O arquivo temporário não foi encontrado — envie a planilha novamente.", "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    mapeamento = _extrair_mapeamento_do_formulario(entidade)

    try:
        df = ler_planilha(caminho, extensao)
    except ArquivoInvalidoError as erro:
        _remover_temporario(token)
        flash(str(erro), "danger")
        return redirect(url_for("importacao.nova", entidade=entidade))

    # Nunca confia na classificação vinda do formulário (poderia ter
    # sido manipulada) — revalida tudo do zero antes de confirmar.
    resultado = validar_e_classificar(df, mapeamento, entidade)

    if resultado["invalidos"] > 0:
        _remover_temporario(token)
        flash(
            "Os dados no banco mudaram desde a pré-visualização e a planilha não é mais "
            "totalmente válida. Envie a planilha novamente.",
            "danger",
        )
        return redirect(url_for("importacao.nova", entidade=entidade))

    usuario = usuario_atual()
    singular = NOMES_SINGULAR[entidade]
    contagens = {"novo": 0, "alterado": 0, "sem_alteracao": 0}

    for linha in resultado["linhas"]:
        classificacao = linha["classificacao"]
        contagens[classificacao] += 1

        if entidade == "rede":
            tabela_alvo = _TABELA_POR_TIPO_REDE[linha["tipo"]]
            singular_alvo = _SINGULAR_POR_TIPO_REDE[linha["tipo"]]
        else:
            tabela_alvo = entidade
            singular_alvo = singular

        if classificacao == "novo":
            descricao = (
                f"Importação de planilha — linha {linha['numero_linha']}: "
                f"criação de {singular_alvo} '{linha['dados'].get('nome')}'."
            )
            registrar_alteracao(usuario, tabela_alvo, None, "CRIAR", linha["dados"], descricao)
        elif classificacao == "alterado":
            descricao = (
                f"Importação de planilha — linha {linha['numero_linha']}: "
                f"edição de {singular_alvo} '{linha['dados'].get('nome')}'."
            )
            registrar_alteracao(usuario, tabela_alvo, linha["registro_existente_id"], "EDITAR", linha["dados"], descricao)
        # "sem_alteracao": nada a fazer — não gera solicitação.

    registrar_auditoria(
        usuario=usuario,
        acao="IMPORTAR_PLANILHA",
        tabela=entidade,
        descricao=(
            f"Importação de planilha de {entidade}: {contagens['novo']} novo(s), "
            f"{contagens['alterado']} alterado(s), {contagens['sem_alteracao']} sem alteração."
        ),
    )
    db.session.commit()

    _remover_temporario(token)

    flash(
        f"Importação processada: {contagens['novo']} solicitação(ões) de criação e "
        f"{contagens['alterado']} de edição registradas para aprovação "
        f"({contagens['sem_alteracao']} linha(s) já estavam sem alteração).",
        "success",
    )
    return redirect(url_for("alteracoes.listar", status="PENDENTE"))
