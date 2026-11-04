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


def register_cli_commands(app):
    """Registra os comandos de CLI customizados na aplicação Flask."""
    app.cli.add_command(criar_usuario_command)
