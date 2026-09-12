"""
Application factory do ORIS.

Nesta FASE 3, a aplicação passa a ter autenticação: login (com
bcrypt), sessão Flask e logout. Ainda NÃO possui RBAC funcional,
CRUDs de negócio, fluxo de aprovação ou dashboard real — isso fica
para as próximas fases.
"""

from flask import Flask

from app.extensions import db
from config import get_config


def create_app(config_object=None):
    """Cria e configura a instância da aplicação Flask."""
    app = Flask(__name__)

    app.config.from_object(config_object or get_config())

    # Inicializa as extensões
    db.init_app(app)

    # Importa os models dentro do contexto da app para que o
    # SQLAlchemy registre todas as tabelas no metadata (necessário
    # para db.create_all() e para as migrações futuras).
    with app.app_context():
        from app import models  # noqa: F401

    # Registra as rotas de autenticação (login/logout) e a rota
    # protegida inicial.
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Registra o comando de CLI para criar usuários (ver app/cli.py).
    from app.cli import register_cli_commands

    register_cli_commands(app)

    # Rota simples só para confirmar que a aplicação está de pé
    # e que a configuração foi carregada corretamente.
    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "app": "ORIS",
            "fase": "3 - autenticacao (login, bcrypt, sessao, logout)",
        }

    return app
