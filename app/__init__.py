"""
Application factory do ORIS.

Nesta FASE 12, o ORIS passa por uma auditoria técnica de segurança e
ganha os controles de proteção de dados/LGPD compatíveis com o seu
escopo (ver docs/SEGURANCA.md para o relatório completo). Reaproveita
tudo das fases anteriores sem quebrar nada — autenticação (Fase 3),
RBAC (Fase 4), fluxo de aprovação (Fase 7), auditoria (Fase 8),
Dashboard (Fase 9), Importador (Fase 10) e Administração de Usuários
(Fase 11).

Novidades desta fase:
- Cabeçalhos HTTP de segurança básicos em toda resposta.
- Página de erro 500 amigável (nunca expõe stack trace/SQL/caminhos).
- Rate limiting leve (em memória, sem Redis) para tentativas de login.
- Página `/privacidade` documentando finalidade, dados tratados,
  controles e retenção.
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
    # consulta de Auditoria, o Dashboard, o Importador de planilhas,
    # a Administração de Usuários e a página de Privacidade.
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

    # Registra o comando de CLI para criar usuários (ver app/cli.py).
    from app.cli import register_cli_commands

    register_cli_commands(app)

    # Disponibiliza o usuário autenticado em todos os templates (ex.:
    # para o menu em base.html decidir se mostra os links "Auditoria"
    # e "Usuários", que só fazem sentido para perfis específicos).
    @app.context_processor
    def inject_usuario_logado():
        from app.utils.decorators import usuario_atual

        return {"usuario_logado": usuario_atual()}

    # Cabeçalhos HTTP de segurança básicos (Fase 12 — achado SEC-003).
    # `unsafe-inline` em script-src é necessário porque vários
    # templates usam pequenos handlers inline (ex.:
    # onchange="this.form.submit()") em filtros de listagem — uma
    # limitação conhecida, documentada em docs/SEGURANCA.md como
    # melhoria para a fase de UX/UI (mover para arquivos .js próprios
    # permitiria remover essa exceção).
    @app.after_request
    def aplicar_headers_de_seguranca(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'",
        )
        return response

    # Página de acesso negado, usada sempre que roles_required
    # bloquear um usuário autenticado sem o perfil necessário (ou
    # quando um solicitante tenta aprovar/rejeitar a própria
    # alteração — ver app/routes/alteracoes.py).
    @app.errorhandler(403)
    def acesso_negado(erro):
        return render_template("acesso_negado.html"), 403

    # Página amigável para registros/URLs inexistentes (ex.: unidade,
    # serviço, equipamento, alteração, registro de auditoria ou
    # usuário com id que não existe), sem expor detalhes internos.
    @app.errorhandler(404)
    def nao_encontrado(erro):
        return render_template("nao_encontrado.html"), 404

    # Página amigável para erros inesperados (Fase 12 — achado
    # SEC-004): nunca expõe stack trace, SQL, caminhos de arquivo ou
    # qualquer outro detalhe interno ao usuário, independentemente do
    # que causou o erro. Em produção (DEBUG=False) o Flask já chamaria
    # este handler; isto só garante uma página amigável em vez da
    # página padrão do Werkzeug.
    @app.errorhandler(500)
    def erro_interno(erro):
        return render_template("erro_interno.html"), 500

    # Rota simples só para confirmar que a aplicação está de pé
    # e que a configuração foi carregada corretamente.
    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "app": "ORIS",
            "fase": "12 - seguranca, lgpd e protecao de dados",
        }

    return app
