"""
Decorators de controle de acesso.

Nesta fase existe apenas `login_required`, que verifica se há uma
sessão autenticada válida. O controle por PERFIL (RBAC) — ex.
`role_required("ADMINISTRADOR")` — será implementado na FASE 4.
"""

from functools import wraps

from flask import redirect, session, url_for


def login_required(view_func):
    """Garante que a rota só seja acessada por um usuário autenticado.

    Verifica dois indicadores mínimos na sessão (`autenticado` e
    `usuario_id`), definidos no login (app/routes/auth.py). Se
    ausentes, redireciona para a tela de login — nunca confia apenas
    na interface, a verificação acontece sempre no backend.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("autenticado") or not session.get("usuario_id"):
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapper
