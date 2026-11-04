"""Consulta de auditoria (Fase 8)."""

from flask import Blueprint, abort, render_template, request

from app.extensions import db
from app.models import Auditoria, PerfilUsuario, Usuario
from app.utils.decorators import roles_required

auditoria_bp = Blueprint("auditoria", __name__, url_prefix="/auditoria")

PERFIS_QUE_CONSULTAM_AUDITORIA = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
)


def _buscar_registro_ou_404(auditoria_id):
    registro = db.session.get(Auditoria, auditoria_id)
    if registro is None:
        abort(404)
    return registro


@auditoria_bp.route("")
@roles_required(*PERFIS_QUE_CONSULTAM_AUDITORIA)
def listar():
    query = Auditoria.query

    usuario_id_filtro = request.args.get("usuario_id", type=int)
    if usuario_id_filtro:
        query = query.filter(Auditoria.usuario_id == usuario_id_filtro)

    acao_filtro = request.args.get("acao")
    if acao_filtro:
        query = query.filter(Auditoria.acao == acao_filtro)

    tabela_filtro = request.args.get("tabela")
    if tabela_filtro:
        query = query.filter(Auditoria.tabela == tabela_filtro)

    data_filtro = request.args.get("data")  # formato YYYY-MM-DD
    if data_filtro:
        query = query.filter(db.func.date(Auditoria.data_hora) == data_filtro)

    registros = query.order_by(Auditoria.data_hora.desc()).all()

    acoes_disponiveis = [
        linha[0] for linha in db.session.query(Auditoria.acao).distinct().order_by(Auditoria.acao).all()
    ]

    return render_template(
        "auditoria/lista.html",
        registros=registros,
        usuarios=Usuario.query.order_by(Usuario.nome).all(),
        acoes_disponiveis=acoes_disponiveis,
        usuario_id_filtro=usuario_id_filtro,
        acao_filtro=acao_filtro,
        tabela_filtro=tabela_filtro,
        data_filtro=data_filtro,
    )


@auditoria_bp.route("/<int:auditoria_id>")
@roles_required(*PERFIS_QUE_CONSULTAM_AUDITORIA)
def visualizar(auditoria_id):
    registro = _buscar_registro_ou_404(auditoria_id)
    return render_template("auditoria/detalhe.html", registro=registro)
