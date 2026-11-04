"""CRUD de Unidades de Saúde Bucal (Fase 5), com fluxo de aprovação integrado a partir da..."""

from flask import Blueprint, abort, flash, redirect, render_template, url_for

from app.extensions import db
from app.forms import AlterarSituacaoForm, UnidadeForm
from app.models import PerfilUsuario, Unidade
from app.services.alteracoes_service import registrar_alteracao
from app.utils.decorators import login_required, roles_required, usuario_atual

unidades_bp = Blueprint("unidades", __name__, url_prefix="/unidades")

PERFIS_QUE_ALTERAM_UNIDADES = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL.value,
)


def _buscar_unidade_ou_404(unidade_id):
    """Busca uma unidade pelo id ou aborta com 404 (tratado por uma página amigável - ver..."""
    unidade = db.session.get(Unidade, unidade_id)
    if unidade is None:
        abort(404)
    return unidade


def _usuario_pode_alterar():
    """Indica, só para a interface (esconder/mostrar botões), se o usuário atual pertence..."""
    usuario = usuario_atual()
    return usuario is not None and usuario.perfil.value in PERFIS_QUE_ALTERAM_UNIDADES


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


@unidades_bp.route("/nova", methods=["GET", "POST"])
@roles_required(*PERFIS_QUE_ALTERAM_UNIDADES)
def nova():
    form = UnidadeForm()

    if form.validate_on_submit():
        cnes = form.cnes.data.strip()

        if Unidade.query.filter_by(cnes=cnes).first() is not None:
            flash(f"Já existe uma unidade cadastrada com o CNES '{cnes}'.", "danger")
            return render_template("unidades/form.html", form=form, titulo="Nova Unidade")

        dados = {
            "nome": form.nome.data.strip(),
            "cnes": cnes,
            "tipo": form.tipo.data.strip(),
            "endereco": (form.endereco.data or "").strip() or None,
            "bairro": (form.bairro.data or "").strip() or None,
            "cidade": form.cidade.data.strip(),
            "uf": form.uf.data.strip().upper(),
            "situacao": form.situacao.data,
        }
        descricao = f"Criação de nova Unidade: {dados['nome']} (CNES {cnes})"

        alteracao = registrar_alteracao(
            usuario_atual(), "unidades", None, "CRIAR", dados, descricao
        )

        flash(
            f"Solicitação de cadastro da unidade '{dados['nome']}' registrada "
            f"(Alteração #{alteracao.id}) e aguardando aprovação.",
            "info",
        )
        return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))

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

        dados_novos = {
            "nome": form.nome.data.strip(),
            "cnes": cnes,
            "tipo": form.tipo.data.strip(),
            "endereco": (form.endereco.data or "").strip() or None,
            "bairro": (form.bairro.data or "").strip() or None,
            "cidade": form.cidade.data.strip(),
            "uf": form.uf.data.strip().upper(),
            "situacao": form.situacao.data,
        }

        campos_alterados = [
            f"{campo} '{getattr(unidade, campo)}' → '{valor}'"
            for campo, valor in dados_novos.items()
            if str(getattr(unidade, campo)) != str(valor)
        ]
        if not campos_alterados:
            flash("Nenhuma alteração foi detectada nos dados informados.", "warning")
            return render_template(
                "unidades/form.html", form=form, titulo=f"Editar Unidade — {unidade.nome}", unidade=unidade
            )

        descricao = f"Edição da Unidade {unidade.id} ({unidade.nome}): " + "; ".join(campos_alterados)

        alteracao = registrar_alteracao(
            usuario_atual(), "unidades", unidade.id, "EDITAR", dados_novos, descricao
        )

        flash(
            f"Solicitação de edição da unidade '{unidade.nome}' registrada "
            f"(Alteração #{alteracao.id}) e aguardando aprovação.",
            "info",
        )
        return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))

    if not form.is_submitted():
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

    if not form.validate_on_submit():
        flash("Situação inválida.", "danger")
        return redirect(url_for("unidades.visualizar", unidade_id=unidade.id))

    nova_situacao = form.situacao.data

    if nova_situacao == unidade.situacao.value:
        flash("A unidade já está nessa situação.", "warning")
        return redirect(url_for("unidades.visualizar", unidade_id=unidade.id))

    descricao = f"Alteração da Unidade {unidade.id} ({unidade.nome}): situação {unidade.situacao.value} → {nova_situacao}"

    alteracao = registrar_alteracao(
        usuario_atual(), "unidades", unidade.id, "ALTERAR_SITUACAO", {"situacao": nova_situacao}, descricao
    )

    flash(
        f"Solicitação de alteração de situação registrada (Alteração #{alteracao.id}) e aguardando aprovação.",
        "info",
    )
    return redirect(url_for("alteracoes.visualizar", alteracao_id=alteracao.id))
