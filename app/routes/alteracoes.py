"""
Rotas de Alterações — fluxo de aprovação (Fase 7).

- Consultar (listar/visualizar): qualquer usuário autenticado, para
  acompanhar o status das solicitações (inclusive as próprias).
- Aprovar/Rejeitar: somente ADMINISTRADOR e GESTAO_INFORMACAO
  (app.utils.decorators.roles_required), com a regra extra — sempre
  verificada no backend — de que o solicitante nunca pode aprovar ou
  rejeitar a própria alteração (ver app/services/alteracoes_service.py).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms import AcaoAlteracaoForm
from app.models import Alteracao, PerfilUsuario, StatusAlteracao
from app.services.alteracoes_service import aprovar_alteracao, rejeitar_alteracao
from app.utils.decorators import login_required, roles_required, usuario_atual

alteracoes_bp = Blueprint("alteracoes", __name__, url_prefix="/alteracoes")

PERFIS_QUE_APROVAM = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
)


def _buscar_alteracao_ou_404(alteracao_id):
    alteracao = db.session.get(Alteracao, alteracao_id)
    if alteracao is None:
        abort(404)
    return alteracao


@alteracoes_bp.route("")
@login_required
def listar():
    query = Alteracao.query

    status = request.args.get("status")
    if status in (item.value for item in StatusAlteracao):
        query = query.filter(Alteracao.status == status)

    tabela = request.args.get("tabela")
    if tabela in ("unidades", "servicos", "equipamentos"):
        query = query.filter(Alteracao.tabela == tabela)

    alteracoes = query.order_by(Alteracao.created_at.desc()).all()

    usuario = usuario_atual()
    pode_decidir = usuario is not None and usuario.perfil.value in PERFIS_QUE_APROVAM

    return render_template(
        "alteracoes/lista.html",
        alteracoes=alteracoes,
        filtro_status=status,
        filtro_tabela=tabela,
        pode_decidir=pode_decidir,
        usuario_atual_id=usuario.id if usuario else None,
    )


@alteracoes_bp.route("/<int:alteracao_id>")
@login_required
def visualizar(alteracao_id):
    alteracao = _buscar_alteracao_ou_404(alteracao_id)

    usuario = usuario_atual()
    pode_decidir = (
        usuario is not None
        and usuario.perfil.value in PERFIS_QUE_APROVAM
        and alteracao.status == StatusAlteracao.PENDENTE
        and alteracao.usuario_id != usuario.id
    )

    return render_template(
        "alteracoes/detalhe.html",
        alteracao=alteracao,
        pode_decidir=pode_decidir,
        form=AcaoAlteracaoForm(),
    )


@alteracoes_bp.route("/<int:alteracao_id>/aprovar", methods=["POST"])
@roles_required(*PERFIS_QUE_APROVAM)
def aprovar(alteracao_id):
    alteracao = _buscar_alteracao_ou_404(alteracao_id)
    form = AcaoAlteracaoForm()

    if not form.validate_on_submit():
        flash("Não foi possível processar a solicitação.", "danger")
        return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))

    aprovador = usuario_atual()

    # A segregação de funções é regra de negócio (não uma questão de
    # perfil), mas tratamos a tentativa de auto-aprovação como acesso
    # negado (403) — consistente com o resto da aplicação, que nunca
    # confia apenas na interface para bloquear ações indevidas.
    if alteracao.usuario_id == aprovador.id:
        abort(403)

    sucesso, mensagem = aprovar_alteracao(alteracao, aprovador)
    flash(mensagem, "success" if sucesso else "danger")
    return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))


@alteracoes_bp.route("/<int:alteracao_id>/rejeitar", methods=["POST"])
@roles_required(*PERFIS_QUE_APROVAM)
def rejeitar(alteracao_id):
    alteracao = _buscar_alteracao_ou_404(alteracao_id)
    form = AcaoAlteracaoForm()

    if not form.validate_on_submit():
        flash("Não foi possível processar a solicitação.", "danger")
        return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))

    aprovador = usuario_atual()

    if alteracao.usuario_id == aprovador.id:
        abort(403)

    sucesso, mensagem = rejeitar_alteracao(alteracao, aprovador)
    flash(mensagem, "success" if sucesso else "danger")
    return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))
