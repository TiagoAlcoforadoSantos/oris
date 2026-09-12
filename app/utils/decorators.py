"""
Decorators de controle de acesso.

- `login_required`: garante apenas que existe uma sessão autenticada
  (já existia desde a Fase 3).
- `roles_required(*perfis)`: além de exigir autenticação, garante que
  o usuário autenticado possua um dos perfis informados — é o RBAC da
  Fase 4.

A autorização é sempre verificada aqui, no backend, nunca apenas
escondendo botões/links na interface.
"""

from functools import wraps

from flask import abort, redirect, session, url_for

from app.extensions import db


def _sessao_autenticada() -> bool:
    """Verifica os dois indicadores mínimos de sessão autenticada,
    definidos no login (app/routes/auth.py)."""
    return bool(session.get("autenticado") and session.get("usuario_id"))


def usuario_atual():
    """Retorna o objeto Usuario correspondente à sessão atual, ou
    None se não houver sessão autenticada ou o usuário não existir
    mais no banco.

    Importa Usuario aqui dentro (e não no topo do módulo) para evitar
    import circular entre app.models e app.utils.decorators.
    """
    from app.models import Usuario

    if not _sessao_autenticada():
        return None

    return db.session.get(Usuario, session["usuario_id"])


def login_required(view_func):
    """Garante que a rota só seja acessada por um usuário autenticado.

    Se não houver sessão autenticada, redireciona para a tela de
    login.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not _sessao_autenticada():
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapper


def roles_required(*perfis_permitidos):
    """Restringe o acesso à rota a usuários autenticados cujo perfil
    esteja entre `perfis_permitidos`.

    Uso:
        @roles_required("ADMINISTRADOR")
        @roles_required("ADMINISTRADOR", "GESTAO_INFORMACAO")

    Fluxo de verificação:
    1. Usuário precisa estar autenticado (sessão válida) — senão,
       redireciona para /login.
    2. O usuário autenticado precisa existir e estar ativo — senão,
       a sessão é encerrada e o usuário é levado de volta ao login
       (trata o caso de um usuário desativado após o login).
    3. O perfil do usuário precisa estar entre os perfis permitidos
       — senão, HTTP 403 (página de acesso negado).
    """

    perfis_permitidos_set = {str(p) for p in perfis_permitidos}

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not _sessao_autenticada():
                return redirect(url_for("auth.login"))

            usuario = usuario_atual()

            if usuario is None or not usuario.ativo:
                session.clear()
                return redirect(url_for("auth.login"))

            if usuario.perfil.value not in perfis_permitidos_set:
                abort(403)

            return view_func(*args, **kwargs)

        return wrapper

    return decorator
