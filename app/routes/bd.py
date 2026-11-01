"""
Módulo "Banco de Dados" — Etapa 03 (interface funcional com dashboard).

Rotas:
    /bd                                  → painel do módulo (hub)
    /bd/<entidade>                       → visualização (SELECT) com filtros
    /bd/<entidade>/novo                  → INSERT
    /bd/<entidade>/<id>/editar           → UPDATE
    /bd/<entidade>/<id>/excluir  (POST)  → DELETE
    /bd/consultas                        → catálogo das consultas
    /bd/consultas/<id>                   → executa e mostra resultado + SQL
    /bd/estatistica                      → gráficos (disciplina de Estatística)

<entidade> ∈ {unidades, servicos, equipamentos} — 3 tabelas com CRUD
completo (o requisito mínimo é 2).

TODO acesso ao banco aqui passa pela camada app/bd (SQL explícito via
PyMySQL/DB-API, equivalente ao JDBC) — nenhuma linha usa o ORM.

Acesso:
- Visualizar, consultas e estatística: qualquer usuário autenticado.
- INSERT/UPDATE/DELETE: ADMINISTRADOR e GESTAO_INFORMACAO (curadores
  de dados). Como estas escritas são diretas (não passam pelo fluxo de
  aprovação da Fase 7), ficam restritas a esses perfis e TODAS geram
  registro na trilha de auditoria, na mesma transação.
"""

import os

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, url_for)

from app.bd import consultas as cat_consultas
from app.bd import dao_equipamentos, dao_servicos, dao_unidades, estatistica
from app.bd.conexao import ErroBanco
from app.bd.forms import EquipamentoBDForm, ExcluirForm, ServicoBDForm, UnidadeBDForm
from app.models import PerfilUsuario
from app.utils.decorators import login_required, roles_required, usuario_atual

bd_bp = Blueprint("bd", __name__, url_prefix="/bd")

PERFIS_ESCRITA_BD = (PerfilUsuario.ADMINISTRADOR.value, PerfilUsuario.GESTAO_INFORMACAO.value)

EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"}


# ----------------------------------------------------------------------
# Configuração de cada entidade (tela genérica de CRUD)
# ----------------------------------------------------------------------

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
    if hasattr(form, "servico_id"):
        form.servico_id.choices = [("", "— Nenhum —")] + dao_servicos.opcoes()


def _sql_da_tela(cfg, *nomes):
    dao = cfg["dao"]
    return [(n, getattr(dao, n).strip()) for n in nomes if hasattr(dao, n)]


# ----------------------------------------------------------------------
# Hub
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Consultas da Etapa 03
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Painel estatístico
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# CRUD genérico (SELECT / INSERT / UPDATE / DELETE)
# ----------------------------------------------------------------------

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
