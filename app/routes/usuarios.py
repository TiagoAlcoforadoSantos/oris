"""
Administração de Usuários (Fase 11).

Exclusiva do perfil ADMINISTRADOR — todas as rotas usam
`roles_required(PerfilUsuario.ADMINISTRADOR.value)`, nunca dependendo
apenas de esconder o link "Usuários" do menu.

REGRA DO ÚLTIMO ADMINISTRADOR (itens 6 e 7 da Fase 11): o sistema
nunca pode ficar sem nenhum ADMINISTRADOR ativo. Isso é verificado
sempre que uma ação poderia reduzir essa contagem a zero:

- desativar um usuário que é ADMINISTRADOR ativo;
- mudar o perfil de um ADMINISTRADOR ativo para outro perfil.

A regra vale tanto para um administrador mexendo em outro quanto para
um administrador mexendo na própria conta — é a mesma verificação
("isso deixaria o sistema sem administrador?"), sem tratamento
especial para autoalteração além disso.

Nenhuma exclusão física é feita — apenas ativação/desativação.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms import AcaoAlteracaoForm, CriarUsuarioForm, EditarUsuarioForm, RedefinirSenhaForm
from app.models import PerfilUsuario, Usuario
from app.services.auditoria_service import registrar_auditoria
from app.utils.decorators import roles_required, usuario_atual
from app.utils.security import gerar_hash_senha

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

PERFIL_ADMINISTRADOR = PerfilUsuario.ADMINISTRADOR.value

PERFIS_CHOICES = [perfil.value for perfil in PerfilUsuario]


def _buscar_usuario_ou_404(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        abort(404)
    return usuario


def _total_administradores_ativos(excluir_id=None):
    query = Usuario.query.filter_by(perfil=PerfilUsuario.ADMINISTRADOR, ativo=True)
    if excluir_id is not None:
        query = query.filter(Usuario.id != excluir_id)
    return query.count()


def _e_ultimo_administrador_ativo(usuario):
    """True se `usuario` é ADMINISTRADOR, está ativo, e não existe
    nenhum OUTRO administrador ativo além dele."""
    if usuario.perfil != PerfilUsuario.ADMINISTRADOR or not usuario.ativo:
        return False
    return _total_administradores_ativos(excluir_id=usuario.id) == 0


# ----------------------------------------------------------------
# Listagem, com busca simples e filtros
# ----------------------------------------------------------------

@usuarios_bp.route("")
@roles_required(PERFIL_ADMINISTRADOR)
def listar():
    query = Usuario.query

    busca = request.args.get("busca", "").strip()
    if busca:
        termo = f"%{busca}%"
        query = query.filter(db.or_(Usuario.nome.ilike(termo), Usuario.email.ilike(termo)))

    perfil_filtro = request.args.get("perfil")
    if perfil_filtro in PERFIS_CHOICES:
        query = query.filter(Usuario.perfil == PerfilUsuario(perfil_filtro))

    situacao_filtro = request.args.get("situacao")
    if situacao_filtro in ("1", "0"):
        query = query.filter(Usuario.ativo == (situacao_filtro == "1"))

    usuarios = query.order_by(Usuario.nome).all()

    return render_template(
        "usuarios/lista.html",
        usuarios=usuarios,
        busca=busca,
        perfil_filtro=perfil_filtro,
        situacao_filtro=situacao_filtro,
        perfis=PERFIS_CHOICES,
        form_acao=AcaoAlteracaoForm(),
    )


# ----------------------------------------------------------------
# Criar
# ----------------------------------------------------------------

@usuarios_bp.route("/novo", methods=["GET", "POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def novo():
    form = CriarUsuarioForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        if Usuario.query.filter_by(email=email).first() is not None:
            flash(f"Já existe um usuário cadastrado com o email '{email}'.", "danger")
            return render_template("usuarios/form.html", form=form, titulo="Novo Usuário")

        novo_usuario = Usuario(
            nome=form.nome.data.strip(),
            email=email,
            senha_hash=gerar_hash_senha(form.senha.data),
            perfil=PerfilUsuario(form.perfil.data),
            ativo=(form.ativo.data == "1"),
        )
        db.session.add(novo_usuario)
        db.session.flush()  # obtém o id para a auditoria

        registrar_auditoria(
            usuario=usuario_atual(),
            acao="CRIAR_USUARIO",
            tabela="usuarios",
            registro_id=novo_usuario.id,
            descricao=f"Criação do usuário '{novo_usuario.nome}' ({novo_usuario.email}), perfil {novo_usuario.perfil.value}.",
        )
        db.session.commit()

        flash(f"Usuário '{novo_usuario.nome}' criado com sucesso.", "success")
        return redirect(url_for("usuarios.listar"))

    return render_template("usuarios/form.html", form=form, titulo="Novo Usuário")


# ----------------------------------------------------------------
# Editar (nome, email, perfil)
# ----------------------------------------------------------------

@usuarios_bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def editar(usuario_id):
    usuario = _buscar_usuario_ou_404(usuario_id)
    form = EditarUsuarioForm()

    if form.validate_on_submit():
        email_novo = form.email.data.strip().lower()
        nome_novo = form.nome.data.strip()
        perfil_novo = PerfilUsuario(form.perfil.data)

        email_em_uso = Usuario.query.filter(Usuario.email == email_novo, Usuario.id != usuario.id).first()
        if email_em_uso is not None:
            flash(f"Já existe outro usuário cadastrado com o email '{email_novo}'.", "danger")
            return render_template(
                "usuarios/form.html", form=form, titulo=f"Editar Usuário — {usuario.nome}", usuario=usuario
            )

        # Regra do último administrador: bloqueia ANTES de aplicar
        # qualquer mudança, se a troca de perfil deixaria o sistema
        # sem nenhum ADMINISTRADOR ativo.
        if perfil_novo != usuario.perfil and _e_ultimo_administrador_ativo(usuario):
            flash(
                "Não é possível alterar o perfil deste usuário: ele é o único "
                "ADMINISTRADOR ativo do sistema.",
                "danger",
            )
            return render_template(
                "usuarios/form.html", form=form, titulo=f"Editar Usuário — {usuario.nome}", usuario=usuario
            )

        nome_anterior, email_anterior, perfil_anterior = usuario.nome, usuario.email, usuario.perfil

        usuario.nome = nome_novo
        usuario.email = email_novo
        usuario.perfil = perfil_novo

        if nome_anterior != nome_novo or email_anterior != email_novo:
            registrar_auditoria(
                usuario=usuario_atual(),
                acao="EDITAR_USUARIO",
                tabela="usuarios",
                registro_id=usuario.id,
                descricao=f"Edição do usuário #{usuario.id}.",
                valor_anterior={"nome": nome_anterior, "email": email_anterior},
                valor_novo={"nome": nome_novo, "email": email_novo},
            )

        if perfil_anterior != perfil_novo:
            registrar_auditoria(
                usuario=usuario_atual(),
                acao="ALTERAR_PERFIL",
                tabela="usuarios",
                registro_id=usuario.id,
                descricao=f"Alteração de perfil do usuário #{usuario.id}: {perfil_anterior.value} → {perfil_novo.value}.",
                valor_anterior={"perfil": perfil_anterior.value},
                valor_novo={"perfil": perfil_novo.value},
            )

        db.session.commit()

        flash(f"Usuário '{usuario.nome}' atualizado com sucesso.", "success")
        return redirect(url_for("usuarios.listar"))

    if not form.is_submitted():
        form.nome.data = usuario.nome
        form.email.data = usuario.email
        form.perfil.data = usuario.perfil.value

    return render_template(
        "usuarios/form.html",
        form=form,
        titulo=f"Editar Usuário — {usuario.nome}",
        usuario=usuario,
        form_senha=RedefinirSenhaForm(),
    )


# ----------------------------------------------------------------
# Ativar / desativar
# ----------------------------------------------------------------

@usuarios_bp.route("/<int:usuario_id>/situacao", methods=["POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def alterar_situacao(usuario_id):
    usuario = _buscar_usuario_ou_404(usuario_id)
    form = AcaoAlteracaoForm()

    if not form.validate_on_submit():
        flash("Não foi possível processar a solicitação.", "danger")
        return redirect(url_for("usuarios.listar"))

    situacao_desejada = request.form.get("acao") == "ativar"

    if situacao_desejada == usuario.ativo:
        flash("O usuário já está nessa situação.", "warning")
        return redirect(url_for("usuarios.listar"))

    if not situacao_desejada and _e_ultimo_administrador_ativo(usuario):
        flash(
            "Não é possível desativar este usuário: ele é o único "
            "ADMINISTRADOR ativo do sistema.",
            "danger",
        )
        return redirect(url_for("usuarios.listar"))

    usuario.ativo = situacao_desejada
    acao = "ATIVAR_USUARIO" if situacao_desejada else "DESATIVAR_USUARIO"

    registrar_auditoria(
        usuario=usuario_atual(),
        acao=acao,
        tabela="usuarios",
        registro_id=usuario.id,
        descricao=f"{'Ativação' if situacao_desejada else 'Desativação'} do usuário '{usuario.nome}' ({usuario.email}).",
    )
    db.session.commit()

    flash(f"Usuário '{usuario.nome}' {'ativado' if situacao_desejada else 'desativado'} com sucesso.", "success")
    return redirect(url_for("usuarios.listar"))


# ----------------------------------------------------------------
# Redefinir senha (administrativo)
# ----------------------------------------------------------------

@usuarios_bp.route("/<int:usuario_id>/senha", methods=["POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def redefinir_senha(usuario_id):
    usuario = _buscar_usuario_ou_404(usuario_id)
    form = RedefinirSenhaForm()

    if not form.validate_on_submit():
        for campo, erros in form.errors.items():
            for erro in erros:
                flash(erro, "danger")
        return redirect(url_for("usuarios.editar", usuario_id=usuario.id))

    usuario.senha_hash = gerar_hash_senha(form.nova_senha.data)

    # Nunca registrar a senha em si — só o fato de que foi redefinida.
    registrar_auditoria(
        usuario=usuario_atual(),
        acao="REDEFINIR_SENHA",
        tabela="usuarios",
        registro_id=usuario.id,
        descricao=f"Redefinição administrativa da senha do usuário '{usuario.nome}' ({usuario.email}).",
    )
    db.session.commit()

    flash(f"Senha do usuário '{usuario.nome}' redefinida com sucesso.", "success")
    return redirect(url_for("usuarios.editar", usuario_id=usuario.id))
