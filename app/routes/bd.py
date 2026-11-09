"""Módulo "Banco de Dados" — Etapa 03 (interface funcional com dashboard)."""

import os
from decimal import Decimal, InvalidOperation

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
                   request, url_for)

from app.bd import consultas as cat_consultas
from app.bd import dashboard as dash_bd
from app.bd import objetos
from app.bd import dao_equipamentos, dao_manutencoes, dao_servicos, dao_unidades, estatistica
from app.bd.conexao import ErroBanco
from app.bd.forms import EquipamentoBDForm, ExcluirForm, ManutencaoBDForm, ServicoBDForm, UnidadeBDForm
from app.models import PerfilUsuario
from app.utils.decorators import login_required, roles_required, usuario_atual

bd_bp = Blueprint("bd", __name__, url_prefix="/bd")

PERFIS_ESCRITA_BD = (PerfilUsuario.ADMINISTRADOR.value, PerfilUsuario.GESTAO_INFORMACAO.value)

EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"}


ENTIDADES = {
    "unidades": {
        "titulo": "Unidades de Saúde",
        "singular": "unidade",
        "icone": "bi-hospital",
        "dao": dao_unidades,
        "form": UnidadeBDForm,
        "colunas": [("nome", "Nome"), ("cnes", "CNES"), ("tipo", "Tipo"), ("bairro", "Bairro"),
                    ("situacao", "Situação"), ("qtd_servicos", "Serviços"),
                    ("qtd_equipamentos", "Equip.")],
        "filtro_situacao": [("ATIVA", "Ativa"), ("INATIVA", "Inativa"), ("MANUTENCAO", "Manutenção")],
        "busca": True,
        "filtro_unidade": False,
    },
    "servicos": {
        "titulo": "Serviços",
        "singular": "serviço",
        "icone": "bi-clipboard2-pulse",
        "dao": dao_servicos,
        "form": ServicoBDForm,
        "colunas": [("nome", "Nome"), ("unidade_nome", "Unidade"), ("situacao", "Situação"),
                    ("qtd_equipamentos", "Equip.")],
        "filtro_situacao": [("ATIVO", "Ativo"), ("INATIVO", "Inativo")],
        "busca": False,
        "filtro_unidade": True,
    },
    "equipamentos": {
        "titulo": "Equipamentos",
        "singular": "equipamento",
        "icone": "bi-tools",
        "dao": dao_equipamentos,
        "form": EquipamentoBDForm,
        "colunas": [("nome", "Nome"), ("tipo", "Tipo"), ("unidade_nome", "Unidade"),
                    ("servico_nome", "Serviço"), ("situacao", "Situação")],
        "filtro_situacao": [("ATIVO", "Ativo"), ("INATIVO", "Inativo")],
        "busca": False,
        "filtro_unidade": True,
    },
    "manutencoes": {
        "titulo": "Manutenções",
        "singular": "manutenção",
        "icone": "bi-wrench-adjustable",
        "dao": dao_manutencoes,
        "form": ManutencaoBDForm,
        "colunas": [("equipamento_nome", "Equipamento"), ("unidade_nome", "Unidade"), ("tipo", "Tipo"),
                    ("data_abertura", "Abertura"), ("custo", "Custo (R$)"), ("situacao", "Situação")],
        "filtro_situacao": [("ABERTA", "Aberta"), ("CONCLUIDA", "Concluída"), ("CANCELADA", "Cancelada")],
        "busca": False,
        "filtro_unidade": True,
    },
}


def _entidade_ou_404(nome):
    cfg = ENTIDADES.get(nome)
    if cfg is None:
        abort(404)
    return cfg


def _pode_escrever():
    usuario = usuario_atual()
    return usuario is not None and usuario.perfil.value in PERFIS_ESCRITA_BD


def _preencher_choices(nome, form):
    if hasattr(form, "unidade_id"):
        form.unidade_id.choices = [("", "— Nenhuma —")] + dao_unidades.opcoes()
    if hasattr(form, "equipamento_id"):
        form.equipamento_id.choices = dao_equipamentos.opcoes()
    if hasattr(form, "servico_id"):
        form.servico_id.choices = [("", "— Nenhum —")] + dao_servicos.opcoes()


def _sql_da_tela(cfg, *nomes):
    dao = cfg["dao"]
    return [(n, getattr(dao, n).strip()) for n in nomes if hasattr(dao, n)]


@bd_bp.route("")
@login_required
def index():
    totais = {}
    erro = None
    try:
        for nome, cfg in ENTIDADES.items():
            totais[nome] = len(cfg["dao"].listar())
    except Exception:  # banco indisponível → página continua abrindo
        current_app.logger.exception("Falha ao consultar o banco no hub /bd")
        erro = "Não foi possível conectar ao MySQL. Verifique o .env e se o serviço está ativo."
    return render_template(
        "bd/index.html", entidades=ENTIDADES, totais=totais, erro=erro,
        consultas=cat_consultas.CONSULTAS, pode_escrever=_pode_escrever(),
    )


@bd_bp.route("/consultas")
@login_required
def consultas():
    return render_template("bd/consultas.html", consultas=cat_consultas.CONSULTAS)


@bd_bp.route("/consultas/<consulta_id>")
@login_required
def executar_consulta(consulta_id):
    consulta = cat_consultas.CONSULTAS_POR_ID.get(consulta_id)
    if consulta is None:
        abort(404)
    parametros = cat_consultas.ler_parametros(consulta, request.args)
    colunas, linhas, erro = [], [], None
    try:
        colunas, linhas = cat_consultas.executar(consulta_id, parametros)
    except Exception:
        current_app.logger.exception("Falha ao executar consulta %s", consulta_id)
        erro = "Não foi possível executar a consulta no banco."
    return render_template(
        "bd/consulta_resultado.html", consulta=consulta, parametros=parametros,
        colunas=colunas, linhas=linhas, erro=erro, consultas=cat_consultas.CONSULTAS,
    )


# --------------------------------------------------------------------------
# Dashboard integrado (Etapa 06)
# --------------------------------------------------------------------------
@bd_bp.route("/dashboard")
@login_required
def dashboard_integrado():
    erro, opcoes = None, {"tipos_unidade": []}
    try:
        opcoes = dash_bd.opcoes_filtros()
    except Exception:
        current_app.logger.exception("Falha ao montar filtros do dashboard")
        erro = "Não foi possível conectar ao MySQL. Verifique o .env e se o serviço está ativo."
    return render_template("bd/dashboard.html", opcoes=opcoes, erro=erro)


@bd_bp.route("/dashboard/dados")
@login_required
def dashboard_dados():
    filtros = dash_bd.ler_filtros(request.args)
    try:
        return jsonify({"filtros": filtros, **dash_bd.dados(filtros)})
    except Exception:
        current_app.logger.exception("Falha ao calcular o dashboard")
        return jsonify({"erro": "Não foi possível carregar os dados do banco."}), 500


# --------------------------------------------------------------------------
# Funções, procedimentos e triggers (Etapas 05/06)
# --------------------------------------------------------------------------
def _ler_parametro(p, bruto):
    """Valida UM parâmetro de rotina; devolve o valor ou levanta ValueError."""
    tipo, bruto = p["tipo"], (bruto or "").strip()
    if tipo in ("unidade", "equipamento", "manutencao_aberta"):
        valor = int(bruto)
        if valor <= 0:
            raise ValueError
        return valor
    if tipo == "ano":
        if not bruto:
            return None
        valor = int(bruto)
        if not 2000 <= valor <= 2100:
            raise ValueError
        return valor
    if tipo == "tipo_manutencao":
        if bruto not in ("PREVENTIVA", "CORRETIVA"):
            raise ValueError
        return bruto
    if tipo == "texto":
        if not 1 <= len(bruto) <= 255:
            raise ValueError
        return bruto
    if tipo == "custo":
        try:
            valor = Decimal(bruto.replace(",", "."))
        except InvalidOperation:
            raise ValueError from None
        if valor < 0 or valor > Decimal("99999999.99"):
            raise ValueError
        return valor
    raise ValueError


def _contexto_rotinas():
    ctx = {"funcoes": objetos.FUNCOES, "procedimentos": objetos.PROCEDIMENTOS,
           "triggers": objetos.TRIGGERS, "views": objetos.VIEWS,
           "existentes": None, "efeitos": [], "unidades": [], "equipamentos": [],
           "manutencoes_abertas": [], "erro": None, "fontes": {},
           "pode_escrever": _pode_escrever(), "form": ExcluirForm()}
    try:
        ctx["existentes"] = objetos.objetos_existentes()
        ctx["efeitos"] = objetos.efeitos_triggers()
        ctx["unidades"] = dao_unidades.opcoes()
        ctx["equipamentos"] = dao_equipamentos.opcoes()
        ctx["manutencoes_abertas"] = dao_manutencoes.opcoes_abertas()
    except Exception:
        current_app.logger.exception("Falha ao consultar rotinas do banco")
        ctx["erro"] = "Não foi possível consultar o MySQL. Verifique o .env e se o serviço está ativo."
    for nome in [*objetos.FUNCOES, *objetos.PROCEDIMENTOS, *objetos.TRIGGERS, *objetos.VIEWS]:
        ctx["fontes"][nome] = objetos.codigo_fonte(nome)
    return ctx


@bd_bp.route("/rotinas")
@login_required
def rotinas():
    return render_template("bd/rotinas.html", resultado=None, **_contexto_rotinas())


@bd_bp.route("/rotinas/executar", methods=["POST"])
@login_required
def rotinas_executar():
    if not ExcluirForm().validate_on_submit():  # só valida o token CSRF
        abort(400)
    nome = request.form.get("objeto", "")
    catalogo = objetos.FUNCOES.get(nome) or objetos.PROCEDIMENTOS.get(nome)
    if catalogo is None:
        abort(404)
    eh_procedimento = nome in objetos.PROCEDIMENTOS
    if eh_procedimento and catalogo["escrita"] and not _pode_escrever():
        abort(403)

    resultado = {"objeto": nome, "titulo": catalogo["titulo"], "colunas": [], "linhas": [],
                 "valor": None, "erro": None, "procedimento": eh_procedimento, "parametros": {}}
    try:
        valores = tuple(_ler_parametro(p, request.form.get(p["nome"])) for p in catalogo["parametros"])
        resultado["parametros"] = {p["nome"]: ("todos" if v is None else str(v)) for p, v in zip(catalogo["parametros"], valores)}
        if eh_procedimento:
            colunas, linhas = objetos.chamar_procedimento(nome, valores, usuario_atual().id)
            resultado.update(colunas=colunas, linhas=linhas)
        else:
            resultado["valor"] = objetos.executar_funcao(nome, valores)
    except ValueError:
        resultado["erro"] = "Parâmetro inválido. Confira os valores informados."
    except ErroBanco as erro:
        resultado["erro"] = str(erro)
    except Exception:
        current_app.logger.exception("Falha ao executar %s", nome)
        resultado["erro"] = "Não foi possível executar a rotina no banco."
    return render_template("bd/rotinas.html", resultado=resultado, **_contexto_rotinas())


def _imagens_estatistica():
    pasta = os.path.join(current_app.static_folder, "estatistica")
    if not os.path.isdir(pasta):
        return []
    return sorted(
        f for f in os.listdir(pasta)
        if os.path.splitext(f)[1].lower() in EXTENSOES_IMAGEM
    )


@bd_bp.route("/estatistica")
@login_required
def estatistica_painel():
    dados, medidas, erro = {}, {}, None
    try:
        dados, medidas = estatistica.dados_graficos()
    except Exception:
        current_app.logger.exception("Falha ao montar painel estatístico")
        erro = "Não foi possível carregar os dados do banco."
    return render_template(
        "bd/estatistica.html", dados=dados, medidas=medidas, erro=erro,
        imagens=_imagens_estatistica(),
        sql_amostra=estatistica.SQL_MEDIDAS_EQUIP_POR_UNIDADE.strip(),
    )


@bd_bp.route("/<entidade>")
@login_required
def listar(entidade):
    cfg = _entidade_ou_404(entidade)
    situacao = request.args.get("situacao") or None
    if situacao not in {s for s, _ in cfg["filtro_situacao"]}:
        situacao = None
    filtros = {"situacao": situacao}
    if cfg["busca"]:
        filtros["busca"] = request.args.get("busca") or None
    if cfg["filtro_unidade"]:
        filtros["unidade_id"] = request.args.get("unidade_id", type=int)

    linhas, erro, unidades = [], None, []
    try:
        linhas = cfg["dao"].listar(**filtros)
        if cfg["filtro_unidade"]:
            unidades = dao_unidades.opcoes()
    except Exception:
        current_app.logger.exception("Falha ao listar %s", entidade)
        erro = "Não foi possível consultar o banco de dados."

    return render_template(
        "bd/lista.html", entidade=entidade, cfg=cfg, linhas=linhas, filtros=filtros,
        unidades=unidades, erro=erro, pode_escrever=_pode_escrever(),
        form_excluir=ExcluirForm(), sql_exibido=_sql_da_tela(cfg, "SQL_LISTAR", "SQL_EXCLUIR"),
    )


@bd_bp.route("/<entidade>/novo", methods=["GET", "POST"])
@roles_required(*PERFIS_ESCRITA_BD)
def novo(entidade):
    cfg = _entidade_ou_404(entidade)
    form = cfg["form"]()
    _preencher_choices(entidade, form)

    if form.validate_on_submit():
        try:
            novo_id = cfg["dao"].inserir(form.dados(), usuario_atual().id)
            flash(f"Registro #{novo_id} inserido em `{entidade}` (INSERT + COMMIT).", "success")
            return redirect(url_for("bd.listar", entidade=entidade))
        except ErroBanco as erro:
            flash(str(erro), "danger")

    return render_template(
        "bd/form.html", entidade=entidade, cfg=cfg, form=form, modo="novo",
        sql_exibido=_sql_da_tela(cfg, "SQL_INSERIR"),
    )


@bd_bp.route("/<entidade>/<int:registro_id>/editar", methods=["GET", "POST"])
@roles_required(*PERFIS_ESCRITA_BD)
def editar(entidade, registro_id):
    cfg = _entidade_ou_404(entidade)
    registro = cfg["dao"].buscar(registro_id)
    if registro is None:
        abort(404)

    form = cfg["form"](data=registro) if request.method == "GET" else cfg["form"]()
    _preencher_choices(entidade, form)

    if form.validate_on_submit():
        try:
            cfg["dao"].atualizar(registro_id, form.dados(), usuario_atual().id)
            flash(f"Registro #{registro_id} de `{entidade}` alterado (UPDATE + COMMIT).", "success")
            return redirect(url_for("bd.listar", entidade=entidade))
        except ErroBanco as erro:
            flash(str(erro), "danger")

    return render_template(
        "bd/form.html", entidade=entidade, cfg=cfg, form=form, modo="editar",
        registro=registro, sql_exibido=_sql_da_tela(cfg, "SQL_BUSCAR_POR_ID", "SQL_ATUALIZAR"),
    )


@bd_bp.route("/<entidade>/<int:registro_id>/excluir", methods=["POST"])
@roles_required(*PERFIS_ESCRITA_BD)
def excluir(entidade, registro_id):
    cfg = _entidade_ou_404(entidade)
    form = ExcluirForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        cfg["dao"].excluir(registro_id, usuario_atual().id)
        flash(f"Registro #{registro_id} excluído de `{entidade}` (DELETE + COMMIT).", "success")
    except ErroBanco as erro:
        flash(str(erro), "danger")
    return redirect(url_for("bd.listar", entidade=entidade))
