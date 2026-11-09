"""Comando de linha de comando (Flask CLI) para criar usuários."""

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import PerfilUsuario, Usuario
from app.utils.security import gerar_hash_senha


@click.command("criar-usuario")
@with_appcontext
def criar_usuario_command():
    """Cria um usuário no ORIS (uso em desenvolvimento/teste)."""
    nome = click.prompt("Nome completo")
    email = click.prompt("Email").strip().lower()

    if Usuario.query.filter_by(email=email).first():
        click.echo(click.style(f"Já existe um usuário com o email '{email}'.", fg="red"))
        return

    senha = click.prompt("Senha", hide_input=True, confirmation_prompt=True)

    perfis_disponiveis = [perfil.value for perfil in PerfilUsuario]
    perfil_escolhido = click.prompt(
        "Perfil",
        type=click.Choice(perfis_disponiveis, case_sensitive=False),
        default=PerfilUsuario.GESTOR.value,
    )

    usuario = Usuario(
        nome=nome,
        email=email,
        senha_hash=gerar_hash_senha(senha),
        perfil=PerfilUsuario(perfil_escolhido),
        ativo=True,
    )

    db.session.add(usuario)
    db.session.commit()

    click.echo(click.style(f"Usuário '{email}' criado com sucesso (perfil: {perfil_escolhido}).", fg="green"))


@click.command("sincronizar-ldap")
@click.option("--simular", is_flag=True, help="Mostra o que mudaria, sem gravar nada.")
@click.option("--manter-ausentes", is_flag=True, help="Não desativa usuários LDAP que sumiram do diretório.")
@with_appcontext
def sincronizar_ldap_command(simular, manter_ausentes):
    """Popula usuários e grupos locais a partir do diretório LDAP (Requisito 3)."""
    from app.models import OrigemDiretorio
    from app.services.diretorio_service import DiretorioConfigError, sincronizar_usuarios
    from app.services.ldap_service import buscar_usuarios_ldap

    try:
        externos = buscar_usuarios_ldap()
        resumo = sincronizar_usuarios(
            externos, OrigemDiretorio.LDAP, desativar_ausentes=not manter_ausentes, simular=simular
        )
    except DiretorioConfigError as erro:
        click.echo(click.style(f"Configuração inválida: {erro}", fg="red"))
        raise SystemExit(1)

    prefixo = "[SIMULAÇÃO] " if simular else ""
    click.echo(
        click.style(
            f"{prefixo}{len(externos)} usuário(s) lido(s) do LDAP — criados: {resumo['criados']}, "
            f"atualizados: {resumo['atualizados']}, desativados: {resumo['desativados']}.",
            fg="green",
        )
    )
    for motivo in resumo["ignorados"]:
        click.echo(f"  ignorado: {motivo}")
    for motivo in resumo["protegidos"]:
        click.echo(click.style(f"  protegido: {motivo}", fg="yellow"))


def register_cli_commands(app):
    """Registra os comandos de CLI customizados na aplicação Flask."""
    app.cli.add_command(criar_usuario_command)
    app.cli.add_command(sincronizar_ldap_command)
