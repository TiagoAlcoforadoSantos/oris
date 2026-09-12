"""
Application factory do ORIS.

Nesta FASE 6, o ORIS ganha o CRUD de Serviços e Equipamentos,
seguindo o mesmo padrão de Unidades (Fase 5), reaproveitando
autenticação (Fase 3) e RBAC (Fase 4). Ainda NÃO possui fluxo de
aprovação, auditoria completa ou dashboard real — isso fica para as
próximas fases.
"""

from flask import Flask, render_template

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

    # Registra os blueprints: autenticação (login/logout), rota
    # protegida inicial, áreas de teste do RBAC e os CRUDs de
    # Unidades, Serviços e Equipamentos.
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.areas import areas_bp
    from app.routes.unidades import unidades_bp
    from app.routes.servicos import servicos_bp
    from app.routes.equipamentos import equipamentos_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(areas_bp)
    app.register_blueprint(unidades_bp)
    app.register_blueprint(servicos_bp)
    app.register_blueprint(equipamentos_bp)

    # Registra o comando de CLI para criar usuários (ver app/cli.py).
    from app.cli import register_cli_commands

    register_cli_commands(app)

    # Página de acesso negado, usada sempre que roles_required
    # bloquear um usuário autenticado sem o perfil necessário.
    @app.errorhandler(403)
    def acesso_negado(erro):
        return render_template("acesso_negado.html"), 403

    # Página amigável para registros/URLs inexistentes (ex.: unidade,
    # serviço ou equipamento com id que não existe), sem expor
    # detalhes internos.
    @app.errorhandler(404)
    def nao_encontrado(erro):
        return render_template("nao_encontrado.html"), 404

    # Rota simples só para confirmar que a aplicação está de pé
    # e que a configuração foi carregada corretamente.
    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "app": "ORIS",
            "fase": "6 - crud de servicos e equipamentos",
        }

    return app
