"""
CRUD de Equipamentos (Fase 6).

Mesmo padrão de Unidades (Fase 5) e Serviços (Fase 6):

- Consultar (listar/visualizar): qualquer usuário autenticado.
- Criar / editar / alterar situação: ADMINISTRADOR, GESTAO_INFORMACAO
  e RESPONSAVEL_SAUDE_BUCAL. GESTOR nunca altera dados.

Todo Equipamento pertence obrigatoriamente a uma Unidade. O vínculo
com um Serviço é opcional — mas, se informado, o Serviço precisa
existir E pertencer à MESMA Unidade selecionada para o equipamento;
caso contrário, a inconsistência é bloqueada com uma mensagem
amigável (nunca uma exceção crua).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms import AlterarSituacaoAtivoInativoForm, EquipamentoForm
from app.models import Equipamento, PerfilUsuario, Servico, SituacaoAtivoInativo, Unidade
from app.utils.decorators import login_required, roles_required, usuario_atual

equipamentos_bp = Blueprint("equipamentos", __name__, url_prefix="/equipamentos")

PERFIS_QUE_ALTERAM = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL.value,
)


def _usuario_pode_alterar():
    usuario = usuario_atual()
    return usuario is not None and usuario.perfil.value in PERFIS_QUE_ALTERAM


def _buscar_equipamento_ou_404(equipamento_id):
    equipamento = db.session.get(Equipamento, equipamento_id)
    if equipamento is None:
        abort(404)
    return equipamento


def _preencher_choices(form):
    form.unidade_id.choices = [
        (unidade.id, f"{unidade.nome} ({unidade.cnes})")
        for unidade in Unidade.query.order_by(Unidade.nome).all()
    ]
    form.servico_id.choices = [("", "Nenhum")] + [
        (servico.id, f"{servico.nome} — {servico.unidade.nome}")
        for servico in Servico.query.order_by(Servico.nome).all()
    ]


def _validar_servico_pertence_a_unidade(servico_id, unidade_id):
    """Retorna (servico, mensagem_de_erro). `servico` é None e a
    mensagem é preenchida se houver qualquer inconsistência; do
    contrário, `servico` é o objeto (ou None, se nenhum foi
    selecionado) e a mensagem é None."""
    if servico_id is None:
        return None, None

    servico = db.session.get(Servico, servico_id)
    if servico is None:
        return None, "O serviço selecionado não existe."

    if servico.unidade_id != unidade_id:
        return None, (
            f"O serviço '{servico.nome}' pertence a outra unidade "
            "e não pode ser associado a este equipamento."
        )

    return servico, None


# ----------------------------------------------------------------
# Consulta — qualquer usuário autenticado
# ----------------------------------------------------------------

@equipamentos_bp.route("")
@login_required
def listar():
    query = Equipamento.query

    unidade_id_filtro = request.args.get("unidade_id", type=int)
    servico_id_filtro = request.args.get("servico_id", type=int)
    situacao_filtro = request.args.get("situacao")

    if unidade_id_filtro:
        query = query.filter(Equipamento.unidade_id == unidade_id_filtro)

    if servico_id_filtro:
        query = query.filter(Equipamento.servico_id == servico_id_filtro)

    if situacao_filtro in {s.value for s in SituacaoAtivoInativo}:
        query = query.filter(Equipamento.situacao == SituacaoAtivoInativo(situacao_filtro))

    equipamentos = query.order_by(Equipamento.nome).all()
    unidades = Unidade.query.order_by(Unidade.nome).all()
    servicos = Servico.query.order_by(Servico.nome).all()

    return render_template(
        "equipamentos/lista.html",
        equipamentos=equipamentos,
        unidades=unidades,
        servicos=servicos,
        unidade_id_filtro=unidade_id_filtro,
        servico_id_filtro=servico_id_filtro,
        situacao_filtro=situacao_filtro,
        pode_alterar=_usuario_pode_alterar(),
    )


@equipamentos_bp.route("/<int:equipamento_id>")
@login_required
def visualizar(equipamento_id):
    equipamento = _buscar_equipamento_ou_404(equipamento_id)
    return render_template(
        "equipamentos/detalhe.html",
        equipamento=equipamento,
        pode_alterar=_usuario_pode_alterar(),
        form_situacao=AlterarSituacaoAtivoInativoForm(situacao=equipamento.situacao.value),
    )


# ----------------------------------------------------------------
# Escrita — ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL
# ----------------------------------------------------------------

@equipamentos_bp.route("/novo", methods=["GET", "POST"])
@roles_required(*PERFIS_QUE_ALTERAM)
def novo():
    form = EquipamentoForm()
    _preencher_choices(form)

    if form.validate_on_submit():
        unidade = db.session.get(Unidade, form.unidade_id.data)
        if unidade is None:
            flash("A unidade selecionada não existe.", "danger")
            return render_template("equipamentos/form.html", form=form, titulo="Novo Equipamento")

        servico, erro = _validar_servico_pertence_a_unidade(form.servico_id.data, unidade.id)
        if erro:
            flash(erro, "danger")
            return render_template("equipamentos/form.html", form=form, titulo="Novo Equipamento")

        equipamento = Equipamento(
            nome=form.nome.data.strip(),
            tipo=form.tipo.data.strip(),
            unidade_id=unidade.id,
            servico_id=servico.id if servico else None,
            situacao=form.situacao.data,
        )
        db.session.add(equipamento)
        db.session.commit()

        flash(f"Equipamento '{equipamento.nome}' cadastrado com sucesso.", "success")
        return redirect(url_for("equipamentos.visualizar", equipamento_id=equipamento.id))

    return render_template("equipamentos/form.html", form=form, titulo="Novo Equipamento")


@equipamentos_bp.route("/<int:equipamento_id>/editar", methods=["GET", "POST"])
@roles_required(*PERFIS_QUE_ALTERAM)
def editar(equipamento_id):
    equipamento = _buscar_equipamento_ou_404(equipamento_id)

    form = EquipamentoForm()
    _preencher_choices(form)

    if form.validate_on_submit():
        unidade = db.session.get(Unidade, form.unidade_id.data)
        if unidade is None:
            flash("A unidade selecionada não existe.", "danger")
            return render_template(
                "equipamentos/form.html",
                form=form,
                titulo=f"Editar Equipamento — {equipamento.nome}",
                equipamento=equipamento,
            )

        servico, erro = _validar_servico_pertence_a_unidade(form.servico_id.data, unidade.id)
        if erro:
            flash(erro, "danger")
            return render_template(
                "equipamentos/form.html",
                form=form,
                titulo=f"Editar Equipamento — {equipamento.nome}",
                equipamento=equipamento,
            )

        equipamento.nome = form.nome.data.strip()
        equipamento.tipo = form.tipo.data.strip()
        equipamento.unidade_id = unidade.id
        equipamento.servico_id = servico.id if servico else None
        equipamento.situacao = form.situacao.data
        db.session.commit()

        flash(f"Equipamento '{equipamento.nome}' atualizado com sucesso.", "success")
        return redirect(url_for("equipamentos.visualizar", equipamento_id=equipamento.id))

    if not form.is_submitted():
        form.nome.data = equipamento.nome
        form.tipo.data = equipamento.tipo
        form.unidade_id.data = equipamento.unidade_id
        form.servico_id.data = equipamento.servico_id
        form.situacao.data = equipamento.situacao.value

    return render_template(
        "equipamentos/form.html",
        form=form,
        titulo=f"Editar Equipamento — {equipamento.nome}",
        equipamento=equipamento,
    )


@equipamentos_bp.route("/<int:equipamento_id>/situacao", methods=["POST"])
@roles_required(*PERFIS_QUE_ALTERAM)
def alterar_situacao(equipamento_id):
    equipamento = _buscar_equipamento_ou_404(equipamento_id)

    form = AlterarSituacaoAtivoInativoForm()

    if form.validate_on_submit():
        equipamento.situacao = form.situacao.data
        db.session.commit()
        flash(
            f"Situação do equipamento '{equipamento.nome}' alterada para {equipamento.situacao.value}.",
            "success",
        )
    else:
        flash("Situação inválida.", "danger")

    return redirect(url_for("equipamentos.visualizar", equipamento_id=equipamento.id))
