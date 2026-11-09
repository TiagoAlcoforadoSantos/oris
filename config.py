"""Configurações da aplicação ORIS."""

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

# Valor de fallback usado apenas em desenvolvimento. Em produção a aplicação
# se recusa a iniciar com ele (ver create_app).
SECRET_KEY_PADRAO = "dev-key-insegura-trocar-no-env"


class Config:
    """Configuração base, compartilhada por todos os ambientes."""

    SECRET_KEY = os.getenv("SECRET_KEY", SECRET_KEY_PADRAO)

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

    SESSION_LIFETIME_MINUTES = int(os.getenv("SESSION_LIFETIME_MINUTES", "60"))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_LIFETIME_MINUTES)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    WTF_CSRF_ENABLED = True

    RATE_LIMIT_LOGIN_ENABLED = True

    # --- Diretório externo: LDAP e OIDC (Requisito 3) ---
    # Nada sensível fica no código: tudo vem do .env. Mapeamento
    # grupo -> perfil RBAC, em JSON, ex.:
    #   {"oris-admin": "ADMINISTRADOR", "oris-gestao": "GESTAO_INFORMACAO"}
    DIRETORIO_MAPA_GRUPO_PERFIL = os.getenv("DIRETORIO_MAPA_GRUPO_PERFIL", "{}")

    LDAP_URI = os.getenv("LDAP_URI", "")  # ex.: ldaps://ldap.exemplo.com
    LDAP_USE_STARTTLS = os.getenv("LDAP_USE_STARTTLS", "false").lower() == "true"
    LDAP_ALLOW_INSECURE = os.getenv("LDAP_ALLOW_INSECURE", "false").lower() == "true"
    LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
    LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "")
    LDAP_USER_BASE = os.getenv("LDAP_USER_BASE", "")
    LDAP_USER_FILTER = os.getenv("LDAP_USER_FILTER", "(objectClass=person)")
    LDAP_GROUP_BASE = os.getenv("LDAP_GROUP_BASE", "")
    LDAP_GROUP_FILTER = os.getenv("LDAP_GROUP_FILTER", "(objectClass=groupOfNames)")
    LDAP_ATTR_ID = os.getenv("LDAP_ATTR_ID", "uid")
    LDAP_ATTR_NOME = os.getenv("LDAP_ATTR_NOME", "cn")
    LDAP_ATTR_EMAIL = os.getenv("LDAP_ATTR_EMAIL", "mail")
    LDAP_ATTR_GROUP_NAME = os.getenv("LDAP_ATTR_GROUP_NAME", "cn")
    LDAP_ATTR_GROUP_MEMBER = os.getenv("LDAP_ATTR_GROUP_MEMBER", "member")

    OIDC_ENABLED = os.getenv("OIDC_ENABLED", "false").lower() == "true"
    OIDC_ISSUER = os.getenv("OIDC_ISSUER", "")  # ex.: https://login.exemplo.com/realms/oris
    OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
    OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid profile email")
    OIDC_CLAIM_GROUPS = os.getenv("OIDC_CLAIM_GROUPS", "groups")
    OIDC_ALLOW_INSECURE = os.getenv("OIDC_ALLOW_INSECURE", "false").lower() == "true"

    # --- Exportação de relatórios para nuvem: Amazon S3 (Requisito 4) ---
    # Credenciais NÃO ficam aqui: o boto3 as obtém da cadeia padrão da
    # AWS (variáveis AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, perfil
    # ~/.aws ou IAM Role da instância).
    S3_BUCKET = os.getenv("S3_BUCKET", "")
    S3_REGION = os.getenv("S3_REGION", "")
    S3_PREFIX = os.getenv("S3_PREFIX", "oris/relatorios")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")  # opcional (MinIO/LocalStack)
    S3_URL_EXPIRA_SEGUNDOS = int(os.getenv("S3_URL_EXPIRA_SEGUNDOS", "900"))


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
    RATE_LIMIT_LOGIN_ENABLED = False
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
