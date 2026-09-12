"""
Application factory do ORIS.

Nesta FASE 10, o ORIS ganha um importador de planilhas (.xlsx/.csv)
para Unidades, Serviços e Equipamentos. O upload nunca grava direto
no banco — cada linha nova ou alterada vira uma solicitação PENDENTE,
reaproveitando o mesmo mecanismo de aprovação da Fase 7 e a mesma
auditoria da Fase 8. Reaproveita também a autenticação (Fase 3) e o
RBAC (Fase 4) sem alterá-los.

CORREÇÃO NESTA FASE: `CSRFProtect` passou a ser inicializado
globalmente. Antes, `{{ csrf_token() }}` só funcionava dentro de
templates que recebiam uma instância de `FlaskForm` (via
`form.hidden_tag()`) — mas o template `alteracoes/lista.html` (Fase 7)
usa `{{ csrf_token() }}` diretamente, sem nenhuma FlaskForm associada,
o que quebrava a página sempre que um aprovador de verdade (diferente
de quem solicitou) via a lista com alterações pendentes. Nenhum teste
anterior pegou esse caso porque reaproveitava a mesma sessão ao trocar
de usuário nos testes, mascarando o cenário. `CSRFProtect(app)` resolve
isso (registra `csrf_token` como global do Jinja de verdade) e também
passa a validar CSRF automaticamente nas rotas novas desta fase que
usam formulários simples (sem FlaskForm), como o importador.
"""

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from app.extensions import db
from config import get_config


def create_app(config_object=None):
    """Cria e configura a instância da aplicação Flask."""
    app = Flask(__name__)

    app.config.from_object(config_object or get_config())

    # Limite de tamanho de upload no nível do Flask (defesa extra,
    # além da checagem manual em app/routes/importacao.py).
    app.config.setdefault("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)  # 10 MB

    # Inicializa as extensões
    db.init_app(app)
    CSRFProtect(app)

    # Importa os models dentro do contexto da app para que o
    # SQLAlchemy registre todas as tabelas no metadata (necessário
    # para db.create_all() e para as migrações futuras).
    with app.app_context():
        from app import models  # noqa: F401

    # Registra os blueprints: autenticação (login/logout), rota
    # protegida inicial, áreas de teste do RBAC, os CRUDs de
    # Unidades/Serviços/Equipamentos, o fluxo de Alterações, a
    # consulta de Auditoria, o Dashboard e o Importador de planilhas.
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

    # Registra o comando de CLI para criar usuários (ver app/cli.py).
    from app.cli import register_cli_commands

    register_cli_commands(app)

    # Disponibiliza o usuário autenticado em todos os templates (ex.:
    # para o menu em base.html decidir se mostra o link "Auditoria",
    # que só faz sentido para ADMINISTRADOR/GESTAO_INFORMACAO).
    @app.context_processor
    def inject_usuario_logado():
        from app.utils.decorators import usuario_atual

        return {"usuario_logado": usuario_atual()}

    # Página de acesso negado, usada sempre que roles_required
    # bloquear um usuário autenticado sem o perfil necessário (ou
    # quando um solicitante tenta aprovar/rejeitar a própria
    # alteração — ver app/routes/alteracoes.py).
    @app.errorhandler(403)
    def acesso_negado(erro):
        return render_template("acesso_negado.html"), 403

    # Página amigável para registros/URLs inexistentes (ex.: unidade,
    # serviço, equipamento, alteração ou registro de auditoria com id
    # que não existe), sem expor detalhes internos.
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
            "fase": "10 - importador de planilhas",
        }

    return app
