"""
Instâncias de extensões compartilhadas pela aplicação.

Ficam em um módulo separado para evitar import circular entre
app/__init__.py e os módulos de models/routes.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
