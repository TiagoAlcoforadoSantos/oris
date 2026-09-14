"""
Application factory do ORIS.

Nesta FASE 13B (Etapa 1), o ORIS aplica o Design System da Fase 13A à
estrutura global da aplicação: sidebar, header, breadcrumb e o
Dashboard — a primeira tela realmente redesenhada. Nenhuma regra de
negócio, model, autenticação, RBAC, aprovação, auditoria, importação
ou segurança foi alterada — só a camada visual/estrutural. As demais
telas (Unidades, Serviços, Equipamentos, Aprovações, Auditoria,
Importação, Usuários, Privacidade, Login) ainda não foram
redesenhadas — ficam para as próximas etapas da Fase 13B.

Fases anteriores continuam intactas: autenticação (Fase 3), RBAC
(Fase 4), fluxo de aprovação (Fase 7), auditoria (Fase 8), Dashboard
(Fase 9 — lógica), Importador (Fase 10), Administração de Usuários
(Fase 11), segurança/LGPD (Fase 12 — ver docs/SEGURANCA.md) e o
Design System (Fase 13A — ver app/static/css/tokens.css).
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
    # a Administração de Usuários, a página de Privacidade e a
    # página de referência do Design System.
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

    # Registra o comando de CLI para criar usuários (ver app/cli.py).
    from app.cli import register_cli_commands

    register_cli_commands(app)

    # Filtro de template puramente de apresentação (Fase 13B, Stage 3):
    # transforma o JSON salvo em Alteracao.dados_novos de volta em um
    # dicionário, para a tela de detalhe de aprovação poder mostrar os
    # valores propostos de forma organizada. Não altera nenhum dado
    # gravado nem nenhuma regra de negócio — só como o template lê um
    # campo que já existe.
    @app.template_filter("from_json")
    def from_json_filter(valor):
        import json

        if not valor:
            return {}
        try:
            return json.loads(valor)
        except (TypeError, ValueError):
            return {}

    # Filtro de apresentação: a partir do dicionário de dados_novos
    # (já convertido por from_json), devolve só os campos "amigáveis"
    # para mostrar na tela de aprovação — exclui chaves de id bruto
    # (ex.: unidade_id, servico_id), cujo valor é só um número sem
    # significado direto para quem está revisando a alteração; o
    # contexto relacional (qual unidade/serviço) já aparece em
    # `descricao`, escrita pelas rotas de Unidades/Serviços/
    # Equipamentos no momento da solicitação.
    @app.template_filter("campos_visiveis")
    def campos_visiveis_filter(dados):
        if not dados:
            return []
        return [(campo, valor) for campo, valor in dados.items() if not campo.endswith("_id")]

    # Rótulos amigáveis para os nomes de campo que aparecem em
    # Alteracao.dados_novos (Fase 13B, Stage 3) — só apresentação;
    # nomes de campo desconhecidos caem de volta em algo razoável
    # (capitalizado) em vez de quebrar.
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
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
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
            "fase": "13b-stage567 - ux/ui importacao usuarios e autenticacao",
        }

    return app
