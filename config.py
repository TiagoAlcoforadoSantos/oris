"""
Configurações da aplicação ORIS.

As configurações sensíveis (senhas, chaves) NUNCA devem ficar
diretamente no código. Elas são lidas do arquivo .env através
da biblioteca python-dotenv.
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

# Carrega as variáveis definidas no arquivo .env para o ambiente
load_dotenv()


class Config:
    """Configuração base, compartilhada por todos os ambientes."""

    # Chave usada pelo Flask para assinar cookies de sessão.
    # Nunca deixar um valor fixo em produção — sempre vir do .env.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-insegura-trocar-no-env")

    # --- Banco de dados (MySQL via SQLAlchemy) ---
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "oris_db")
    DB_USER = os.getenv("DB_USER", "oris_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Sessão ---
    SESSION_LIFETIME_MINUTES = int(os.getenv("SESSION_LIFETIME_MINUTES", "60"))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_LIFETIME_MINUTES)

    # Cookies de sessão mais seguros
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Proteção CSRF (Flask-WTF)
    WTF_CSRF_ENABLED = True


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # em dev normalmente não há HTTPS


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # exige HTTPS em produção


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    # Banco de dados em memória (SQLite) apenas para testes automatizados,
    # evitando depender de um MySQL real durante a suíte de testes.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    """Retorna a classe de configuração de acordo com FLASK_ENV."""
    env = os.getenv("FLASK_ENV", "development")
    return config_by_name.get(env, DevelopmentConfig)
