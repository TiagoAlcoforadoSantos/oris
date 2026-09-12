"""
CRUD de Serviços de Saúde Bucal (Fase 6), com fluxo de aprovação
integrado a partir da Fase 7.

Segue exatamente o mesmo padrão estabelecido para Unidades:

- Consultar (listar/visualizar): qualquer usuário autenticado.
- Solicitar (criar / editar / alterar situação): ADMINISTRADOR,
  GESTAO_INFORMACAO e RESPONSAVEL_SAUDE_BUCAL. GESTOR nunca altera
  dados.

A PARTIR DA FASE 7: nenhuma dessas operações grava direto no banco —
cada uma registra uma Alteracao PENDENTE (via
app.services.alteracoes_service.registrar_alteracao) e só é aplicada
quando aprovada em /alteracoes.

Todo Serviço pertence obrigatoriamente a uma Unidade existente — a
lista de unidades do formulário vem sempre do banco no momento da
requisição, e a existência da unidade é conferida de novo no
backend antes de registrar a solicitação (defesa em profundidade).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms import AlterarSituacaoAtivoInativoForm, ServicoForm
from app.models import PerfilUsuario, Servico, SituacaoAtivoInativo, Unidade
from app.services.alteracoes_service import registrar_alteracao
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
# Solicitação de escrita — ADMINISTRADOR, GESTAO_INFORMACAO,
# RESPONSAVEL_SAUDE_BUCAL. Cria Alteracao PENDENTE em vez de gravar
# direto no banco.
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

        dados = {
            "nome": form.nome.data.strip(),
            "unidade_id": unidade.id,
            "situacao": form.situacao.data,
        }
        descricao = f"Criação de novo Serviço: {dados['nome']} (Unidade {unidade.nome})"

        alteracao = registrar_alteracao(
            usuario_atual(), "servicos", None, "CRIAR", dados, descricao
        )

        flash(
            f"Solicitação de cadastro do serviço '{dados['nome']}' registrada "
            f"(Alteração #{alteracao.id}) e aguardando aprovação.",
            "info",
        )
        return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))

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

        dados_novos = {
            "nome": form.nome.data.strip(),
            "unidade_id": unidade.id,
            "situacao": form.situacao.data,
        }

        valores_atuais = {
            "nome": servico.nome,
            "unidade_id": servico.unidade_id,
            "situacao": servico.situacao.value,
        }
        campos_alterados = [
            f"{campo} '{valores_atuais[campo]}' → '{valor}'"
            for campo, valor in dados_novos.items()
            if str(valores_atuais[campo]) != str(valor)
        ]
        if not campos_alterados:
            flash("Nenhuma alteração foi detectada nos dados informados.", "warning")
            return render_template(
                "servicos/form.html", form=form, titulo=f"Editar Serviço — {servico.nome}", servico=servico
            )

        descricao = f"Edição do Serviço {servico.id} ({servico.nome}): " + "; ".join(campos_alterados)

        alteracao = registrar_alteracao(
            usuario_atual(), "servicos", servico.id, "EDITAR", dados_novos, descricao
        )

        flash(
            f"Solicitação de edição do serviço '{servico.nome}' registrada "
            f"(Alteração #{alteracao.id}) e aguardando aprovação.",
            "info",
        )
        return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))

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

    if not form.validate_on_submit():
        flash("Situação inválida.", "danger")
        return redirect(url_for("servicos.visualizar", servico_id=servico.id))

    nova_situacao = form.situacao.data

    if nova_situacao == servico.situacao.value:
        flash("O serviço já está nessa situação.", "warning")
        return redirect(url_for("servicos.visualizar", servico_id=servico.id))

    descricao = f"Alteração do Serviço {servico.id} ({servico.nome}): situação {servico.situacao.value} → {nova_situacao}"

    alteracao = registrar_alteracao(
        usuario_atual(), "servicos", servico.id, "ALTERAR_SITUACAO", {"situacao": nova_situacao}, descricao
    )

    flash(
        f"Solicitação de alteração de situação registrada (Alteração #{alteracao.id}) e aguardando aprovação.",
        "info",
    )
    return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))
