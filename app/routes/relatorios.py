"""
Relatórios (Requisito 4): download local em CSV e exportação para o
Amazon S3.

RBAC (sempre no backend):
- baixar CSV: qualquer usuário autenticado (os mesmos dados já são
  consultáveis nas listagens de Unidades/Serviços/Equipamentos);
- exportar para a nuvem: só ADMINISTRADOR e GESTAO_INFORMACAO — enviar
  dados da rede para fora do sistema é uma ação mais sensível.

Toda geração/exportação é auditada (BAIXAR_RELATORIO /
EXPORTAR_RELATORIO), na mesma transação.
"""

from flask import Blueprint, Response, abort, flash, redirect, render_template, url_for

from app.extensions import db
from app.models import PerfilUsuario
from app.services.armazenamento_service import (
    ArmazenamentoError,
    enviar_relatorio,
    gerar_url_download,
    s3_configurado,
)
from app.services.auditoria_service import registrar_auditoria
from app.services.relatorio_service import ENTIDADES_RELATORIO, gerar_csv
from app.utils.decorators import login_required, roles_required, usuario_atual

relatorios_bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")

PERFIS_QUE_EXPORTAM = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
)

TITULOS = {"unidades": "Unidades de Saúde", "servicos": "Serviços", "equipamentos": "Equipamentos"}


def _validar_entidade_ou_404(entidade):
    if entidade not in ENTIDADES_RELATORIO:
        abort(404)


@relatorios_bp.route("")
@login_required
def index():
    usuario = usuario_atual()
    return render_template(
        "relatorios/index.html",
        entidades=ENTIDADES_RELATORIO,
        titulos=TITULOS,
        pode_exportar=usuario.perfil.value in PERFIS_QUE_EXPORTAM,
        s3_ativo=s3_configurado(),
    )


@relatorios_bp.route("/<entidade>/baixar")
@login_required
def baixar(entidade):
    _validar_entidade_ou_404(entidade)
    nome_arquivo, conteudo = gerar_csv(entidade)

    registrar_auditoria(
        usuario=usuario_atual(),
        acao="BAIXAR_RELATORIO",
        tabela=entidade,
        descricao=f"Download do relatório de {entidade} ({nome_arquivo}).",
    )
    db.session.commit()

    return Response(
        conteudo,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


@relatorios_bp.route("/<entidade>/exportar-s3", methods=["POST"])
@roles_required(*PERFIS_QUE_EXPORTAM)
def exportar_s3(entidade):
    _validar_entidade_ou_404(entidade)

    if not s3_configurado():
        flash("A exportação para a nuvem não está configurada neste ambiente.", "warning")
        return redirect(url_for("relatorios.index"))

    _, conteudo = gerar_csv(entidade)
    try:
        chave = enviar_relatorio(conteudo, entidade)
        link = gerar_url_download(chave)
    except ArmazenamentoError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("relatorios.index"))

    registrar_auditoria(
        usuario=usuario_atual(),
        acao="EXPORTAR_RELATORIO",
        tabela=entidade,
        descricao=f"Relatório de {entidade} exportado para o armazenamento em nuvem (objeto {chave}).",
    )
    db.session.commit()

    flash(f"Relatório enviado à nuvem. Link temporário de download: {link}", "success")
    return redirect(url_for("relatorios.index"))
