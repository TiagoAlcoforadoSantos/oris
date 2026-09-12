"""
CRUD de Serviços de Saúde Bucal (Fase 6).

Segue exatamente o mesmo padrão estabelecido para Unidades na Fase 5:

- Consultar (listar/visualizar): qualquer usuário autenticado.
- Criar / editar / alterar situação: ADMINISTRADOR, GESTAO_INFORMACAO
  e RESPONSAVEL_SAUDE_BUCAL. GESTOR nunca altera dados.

Todo Serviço pertence obrigatoriamente a uma Unidade existente — a
lista de unidades do formulário vem sempre do banco no momento da
requisição, e a existência da unidade é conferida de novo no
backend antes de salvar (defesa em profundidade).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms import AlterarSituacaoAtivoInativoForm, ServicoForm
from app.models import PerfilUsuario, Servico, SituacaoAtivoInativo, Unidade
from app.utils.decorators import login_required, roles_required, usuario_atual

servicos_bp = Blueprint("servicos", __name__, url_prefix="/servicos")

PERFIS_QUE_ALTERAM = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL.value,
)


def _usuario_pode_alterar():
    usuario = usuario_atual()
    return usuario is not None and usuario.perfil.value in PERFIS_QUE_ALTERAM


def _buscar_servico_ou_404(servico_id):
    servico = db.session.get(Servico, servico_id)
    if servico is None:
        abort(404)
    return servico


def _preencher_choices_unidade(form):
    form.unidade_id.choices = [
        (unidade.id, f"{unidade.nome} ({unidade.cnes})")
        for unidade in Unidade.query.order_by(Unidade.nome).all()
    ]


# ----------------------------------------------------------------
# Consulta — qualquer usuário autenticado
# ----------------------------------------------------------------

@servicos_bp.route("")
@login_required
def listar():
    query = Servico.query

    # Filtros simples via querystring (?unidade_id=..&situacao=..)
    unidade_id_filtro = request.args.get("unidade_id", type=int)
    situacao_filtro = request.args.get("situacao")

    if unidade_id_filtro:
        query = query.filter(Servico.unidade_id == unidade_id_filtro)

    if situacao_filtro in {s.value for s in SituacaoAtivoInativo}:
        query = query.filter(Servico.situacao == SituacaoAtivoInativo(situacao_filtro))

    servicos = query.order_by(Servico.nome).all()
    unidades = Unidade.query.order_by(Unidade.nome).all()

    return render_template(
        "servicos/lista.html",
        servicos=servicos,
        unidades=unidades,
        unidade_id_filtro=unidade_id_filtro,
        situacao_filtro=situacao_filtro,
        pode_alterar=_usuario_pode_alterar(),
    )


@servicos_bp.route("/<int:servico_id>")
@login_required
def visualizar(servico_id):
    servico = _buscar_servico_ou_404(servico_id)
    return render_template(
        "servicos/detalhe.html",
        servico=servico,
        pode_alterar=_usuario_pode_alterar(),
        form_situacao=AlterarSituacaoAtivoInativoForm(situacao=servico.situacao.value),
    )


# ----------------------------------------------------------------
# Escrita — ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL
# ----------------------------------------------------------------

@servicos_bp.route("/novo", methods=["GET", "POST"])
@roles_required(*PERFIS_QUE_ALTERAM)
def novo():
    form = ServicoForm()
    _preencher_choices_unidade(form)

    if form.validate_on_submit():
        unidade = db.session.get(Unidade, form.unidade_id.data)
        if unidade is None:
            flash("A unidade selecionada não existe.", "danger")
            return render_template("servicos/form.html", form=form, titulo="Novo Serviço")

        servico = Servico(
            nome=form.nome.data.strip(),
            unidade_id=unidade.id,
            situacao=form.situacao.data,
        )
        db.session.add(servico)
        db.session.commit()

        flash(f"Serviço '{servico.nome}' cadastrado com sucesso.", "success")
        return redirect(url_for("servicos.visualizar", servico_id=servico.id))

    return render_template("servicos/form.html", form=form, titulo="Novo Serviço")


@servicos_bp.route("/<int:servico_id>/editar", methods=["GET", "POST"])
@roles_required(*PERFIS_QUE_ALTERAM)
def editar(servico_id):
    servico = _buscar_servico_ou_404(servico_id)

    form = ServicoForm()
    _preencher_choices_unidade(form)

    if form.validate_on_submit():
        unidade = db.session.get(Unidade, form.unidade_id.data)
        if unidade is None:
            flash("A unidade selecionada não existe.", "danger")
            return render_template(
                "servicos/form.html", form=form, titulo=f"Editar Serviço — {servico.nome}", servico=servico
            )

        servico.nome = form.nome.data.strip()
        servico.unidade_id = unidade.id
        servico.situacao = form.situacao.data
        db.session.commit()

        flash(f"Serviço '{servico.nome}' atualizado com sucesso.", "success")
        return redirect(url_for("servicos.visualizar", servico_id=servico.id))

    if not form.is_submitted():
        form.nome.data = servico.nome
        form.unidade_id.data = servico.unidade_id
        form.situacao.data = servico.situacao.value

    return render_template(
        "servicos/form.html", form=form, titulo=f"Editar Serviço — {servico.nome}", servico=servico
    )


@servicos_bp.route("/<int:servico_id>/situacao", methods=["POST"])
@roles_required(*PERFIS_QUE_ALTERAM)
def alterar_situacao(servico_id):
    servico = _buscar_servico_ou_404(servico_id)

    form = AlterarSituacaoAtivoInativoForm()

    if form.validate_on_submit():
        servico.situacao = form.situacao.data
        db.session.commit()
        flash(f"Situação do serviço '{servico.nome}' alterada para {servico.situacao.value}.", "success")
    else:
        flash("Situação inválida.", "danger")

    return redirect(url_for("servicos.visualizar", servico_id=servico.id))
