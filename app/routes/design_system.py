"""
Página de referência do Design System do ORIS (Fase 13A).

Pública (não exige login) — é uma página de referência visual/
documentação, sem nenhum dado do sistema. Mostra a paleta, a
tipografia e os componentes básicos (botões, badges, alertas,
formulários) construídos com os tokens de app/static/css/tokens.css.

Não é uma funcionalidade de negócio: existe só para orientar a
aplicação consistente da identidade visual nas próximas telas
(Fase 13B).
"""

from flask import Blueprint, render_template

design_system_bp = Blueprint("design_system", __name__)


@design_system_bp.route("/design-system")
def index():
    return render_template("design_system.html")
