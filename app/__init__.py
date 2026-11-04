"""Application factory do ORIS."""

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from app.extensions import db
from config import get_config


def create_app(config_object=None):
    """Cria e configura a instância da aplicação Flask."""
    app = Flask(__name__)

    app.config.from_object(config_object or get_config())

    app.json.ensure_ascii = False

    app.config.setdefault("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)  # 10 MB

    db.init_app(app)
    CSRFProtect(app)

    with app.app_context():
        from app import models  # noqa: F401

    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.areas import areas_bp
    from app.routes.unidades import unidades_bp
    from app.routes.servicos import servicos_bp
    from app.routes.equipamentos import equipamentos_bp
    from app.routes.alteracoes import alteracoes_bp
    from app.routes.auditoria import auditoria_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.importacao import importacao_bp
    from app.routes.usuarios import usuarios_bp
    from app.routes.privacidade import privacidade_bp
    from app.routes.design_system import design_system_bp
    from app.routes.bd import bd_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(areas_bp)
    app.register_blueprint(unidades_bp)
    app.register_blueprint(servicos_bp)
    app.register_blueprint(equipamentos_bp)
    app.register_blueprint(alteracoes_bp)
    app.register_blueprint(auditoria_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(importacao_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(privacidade_bp)
    app.register_blueprint(design_system_bp)
    app.register_blueprint(bd_bp)
    app.register_blueprint(api_bp)

    from app.cli import register_cli_commands

    register_cli_commands(app)

    @app.template_filter("from_json")
    def from_json_filter(valor):
        import json

        if not valor:
            return {}
        try:
            return json.loads(valor)
        except (TypeError, ValueError):
            return {}

    @app.template_filter("campos_visiveis")
    def campos_visiveis_filter(dados):
        if not dados:
            return []
        return [(campo, valor) for campo, valor in dados.items() if not campo.endswith("_id")]

    RÓTULOS_CAMPOS_ALTERACAO = {
        "nome": "Nome",
        "cnes": "CNES",
        "tipo": "Tipo",
        "endereco": "Endereço",
        "bairro": "Bairro",
        "cidade": "Cidade",
        "uf": "UF",
        "situacao": "Situação",
    }

    @app.template_filter("rotulo_campo")
    def rotulo_campo_filter(campo):
        return RÓTULOS_CAMPOS_ALTERACAO.get(campo, campo.replace("_", " ").capitalize())

    @app.context_processor
    def inject_usuario_logado():
        from app.utils.decorators import usuario_atual

        return {"usuario_logado": usuario_atual()}

    @app.after_request
    def aplicar_headers_de_seguranca(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'",
        )
        return response

    @app.errorhandler(403)
    def acesso_negado(erro):
        return render_template("acesso_negado.html"), 403

    @app.errorhandler(404)
    def nao_encontrado(erro):
        return render_template("nao_encontrado.html"), 404

    @app.errorhandler(500)
    def erro_interno(erro):
        return render_template("erro_interno.html"), 500

    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "app": "ORIS",
            "fase": "13b-final - ui/ux polish e consistencia global",
        }

    return app
