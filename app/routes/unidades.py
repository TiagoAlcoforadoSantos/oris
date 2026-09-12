"""
CRUD de Unidades de Saúde Bucal (Fase 5).

Regras de acesso (reaproveitando roles_required da Fase 4):

- Consultar (listar/visualizar): qualquer usuário autenticado, dos 4
  perfis — inclusive GESTOR, que é só leitura.
- Criar / editar / alterar situação: ADMINISTRADOR, GESTAO_INFORMACAO
  e RESPONSAVEL_SAUDE_BUCAL (conforme a matriz de acesso definida na
  Fase 4, onde "Alterar dados" é SIM/SIM*/SIM*/NÃO para
  ADMIN/GESTAO/RESPONSAVEL/GESTOR). GESTOR nunca pode alterar dados.

Nenhuma exclusão física é feita — apenas alteração de situação
(ATIVA/INATIVA/MANUTENCAO), preservando o histórico.
"""

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms import AlterarSituacaoForm, UnidadeForm
from app.models import PerfilUsuario, Unidade
from app.utils.decorators import login_required, roles_required

unidades_bp = Blueprint("unidades", __name__, url_prefix="/unidades")

# Perfis autorizados a criar/editar/alterar situação de unidades.
PERFIS_QUE_ALTERAM_UNIDADES = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL.value,
)


def _buscar_unidade_ou_404(unidade_id):
    """Busca uma unidade pelo id ou aborta com 404 (tratado por uma
    página amigável — ver errorhandler em app/__init__.py)."""
    unidade = db.session.get(Unidade, unidade_id)
    if unidade is None:
        abort(404)
    return unidade


# ----------------------------------------------------------------
# Consulta — qualquer usuário autenticado (inclusive GESTOR)
# ----------------------------------------------------------------

@unidades_bp.route("")
@login_required
def listar():
    unidades = Unidade.query.order_by(Unidade.nome).all()
    return render_template(
        "unidades/lista.html",
        unidades=unidades,
        pode_alterar=_usuario_pode_alterar(),
    )


@unidades_bp.route("/<int:unidade_id>")
@login_required
def visualizar(unidade_id):
    unidade = _buscar_unidade_ou_404(unidade_id)
    return render_template(
        "unidades/detalhe.html",
        unidade=unidade,
        pode_alterar=_usuario_pode_alterar(),
        form_situacao=AlterarSituacaoForm(situacao=unidade.situacao.value),
    )


def _usuario_pode_alterar():
    """Indica, só para a interface (esconder/mostrar botões), se o
    usuário atual pertence a um perfil que pode alterar unidades. A
    proteção de verdade é sempre feita pelos decorators nas rotas de
    escrita abaixo."""
    from app.utils.decorators import usuario_atual

    usuario = usuario_atual()
    return usuario is not None and usuario.perfil.value in PERFIS_QUE_ALTERAM_UNIDADES


# ----------------------------------------------------------------
# Escrita — ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL
# ----------------------------------------------------------------

@unidades_bp.route("/nova", methods=["GET", "POST"])
@roles_required(*PERFIS_QUE_ALTERAM_UNIDADES)
def nova():
    form = UnidadeForm()

    if form.validate_on_submit():
        cnes = form.cnes.data.strip()

        if Unidade.query.filter_by(cnes=cnes).first() is not None:
            flash(f"Já existe uma unidade cadastrada com o CNES '{cnes}'.", "danger")
            return render_template("unidades/form.html", form=form, titulo="Nova Unidade")

        unidade = Unidade(
            nome=form.nome.data.strip(),
            cnes=cnes,
            tipo=form.tipo.data.strip(),
            endereco=(form.endereco.data or "").strip() or None,
            bairro=(form.bairro.data or "").strip() or None,
            cidade=form.cidade.data.strip(),
            uf=form.uf.data.strip().upper(),
            situacao=form.situacao.data,
        )

        try:
            db.session.add(unidade)
            db.session.commit()
        except IntegrityError:
            # Segurança extra contra corrida entre a checagem acima e o
            # commit — a constraint única do banco é o critério final.
            db.session.rollback()
            flash(f"Já existe uma unidade cadastrada com o CNES '{cnes}'.", "danger")
            return render_template("unidades/form.html", form=form, titulo="Nova Unidade")

        flash(f"Unidade '{unidade.nome}' cadastrada com sucesso.", "success")
        return redirect(url_for("unidades.visualizar", unidade_id=unidade.id))

    return render_template("unidades/form.html", form=form, titulo="Nova Unidade")


@unidades_bp.route("/<int:unidade_id>/editar", methods=["GET", "POST"])
@roles_required(*PERFIS_QUE_ALTERAM_UNIDADES)
def editar(unidade_id):
    unidade = _buscar_unidade_ou_404(unidade_id)

    form = UnidadeForm()

    if form.validate_on_submit():
        cnes = form.cnes.data.strip()

        cnes_em_uso = Unidade.query.filter(
            Unidade.cnes == cnes, Unidade.id != unidade.id
        ).first()
        if cnes_em_uso is not None:
            flash(f"Já existe outra unidade cadastrada com o CNES '{cnes}'.", "danger")
            return render_template(
                "unidades/form.html", form=form, titulo=f"Editar Unidade — {unidade.nome}", unidade=unidade
            )

        unidade.nome = form.nome.data.strip()
        unidade.cnes = cnes
        unidade.tipo = form.tipo.data.strip()
        unidade.endereco = (form.endereco.data or "").strip() or None
        unidade.bairro = (form.bairro.data or "").strip() or None
        unidade.cidade = form.cidade.data.strip()
        unidade.uf = form.uf.data.strip().upper()
        unidade.situacao = form.situacao.data

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f"Já existe outra unidade cadastrada com o CNES '{cnes}'.", "danger")
            return render_template(
                "unidades/form.html", form=form, titulo=f"Editar Unidade — {unidade.nome}", unidade=unidade
            )

        flash(f"Unidade '{unidade.nome}' atualizada com sucesso.", "success")
        return redirect(url_for("unidades.visualizar", unidade_id=unidade.id))

    if not form.is_submitted():
        # Pré-carrega os valores atuais no formulário (GET).
        form.nome.data = unidade.nome
        form.cnes.data = unidade.cnes
        form.tipo.data = unidade.tipo
        form.endereco.data = unidade.endereco
        form.bairro.data = unidade.bairro
        form.cidade.data = unidade.cidade
        form.uf.data = unidade.uf
        form.situacao.data = unidade.situacao.value

    return render_template(
        "unidades/form.html", form=form, titulo=f"Editar Unidade — {unidade.nome}", unidade=unidade
    )


@unidades_bp.route("/<int:unidade_id>/situacao", methods=["POST"])
@roles_required(*PERFIS_QUE_ALTERAM_UNIDADES)
def alterar_situacao(unidade_id):
    unidade = _buscar_unidade_ou_404(unidade_id)

    form = AlterarSituacaoForm()

    if form.validate_on_submit():
        unidade.situacao = form.situacao.data
        db.session.commit()
        flash(f"Situação da unidade '{unidade.nome}' alterada para {unidade.situacao.value}.", "success")
    else:
        flash("Situação inválida.", "danger")

    return redirect(url_for("unidades.visualizar", unidade_id=unidade.id))
