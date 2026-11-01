"""
Conexão explícita com o SGBD (MySQL/MariaDB) via PyMySQL — DB-API 2.0.

Equivalência com JDBC (para a disciplina de Banco de Dados):

    Java / JDBC                              Python / DB-API (PyMySQL)
    ---------------------------------------  ---------------------------------------
    DriverManager.getConnection(url,u,p)     pymysql.connect(host, user, password…)
    conn.setAutoCommit(false)                autocommit=False (padrão aqui)
    conn.prepareStatement("… ? …")           cursor = conn.cursor()
    ps.setString(1, x); ps.executeUpdate()   cursor.execute("… %s …", (x,))
    ResultSet rs = ps.executeQuery()         cursor.fetchall() / fetchone()
    rs.getString("nome")                     linha["nome"]  (DictCursor)
    ps.getGeneratedKeys()                    cursor.lastrowid
    conn.commit() / conn.rollback()          conn.commit() / conn.rollback()
    conn.close()                             conn.close()

Os parâmetros SEMPRE são passados separados do texto SQL (nunca por
concatenação de strings): o driver faz o escape, o que impede SQL
Injection — mesma garantia do PreparedStatement.
"""

from contextlib import contextmanager

import pymysql
from flask import current_app
from pymysql.cursors import DictCursor


class ErroBanco(Exception):
    """Erro de banco já traduzido para uma mensagem amigável, que pode
    ser mostrada ao usuário sem expor detalhes internos (SQL, stack)."""


def abrir_conexao():
    """Abre uma nova conexão com o banco configurado no .env.

    Equivale a `DriverManager.getConnection(...)` no JDBC.
    `autocommit=False` → toda escrita precisa de commit explícito.
    """
    cfg = current_app.config
    return pymysql.connect(
        host=cfg.get("DB_HOST", "localhost"),
        port=int(cfg.get("DB_PORT", 3306)),
        user=cfg.get("DB_USER"),
        password=cfg.get("DB_PASSWORD", ""),
        database=cfg.get("DB_NAME"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


@contextmanager
def transacao():
    """Abre conexão + cursor e controla a transação explicitamente.

    Uso:
        with transacao() as cur:
            cur.execute("INSERT INTO ... VALUES (%s, %s)", (a, b))
            cur.execute("INSERT INTO auditorias ...", (...))
        # sem exceção → COMMIT; com exceção → ROLLBACK

    Assim a operação de negócio e o seu registro de auditoria são
    gravados juntos (atomicidade) — ou nenhum dos dois é gravado.
    """
    conn = abrir_conexao()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except pymysql.err.IntegrityError as erro:
        conn.rollback()
        raise ErroBanco(_traduzir_erro_integridade(erro)) from erro
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def consultar(sql, parametros=None):
    """Executa um SELECT e devolve (colunas, linhas).

    Usado pelas telas de listagem e pelas consultas da Etapa 03.
    Não abre transação de escrita — é só leitura.
    """
    conn = abrir_conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            linhas = cur.fetchall()
            colunas = [descricao[0] for descricao in (cur.description or [])]
        return colunas, list(linhas)
    finally:
        conn.close()


def consultar_um(sql, parametros=None):
    """Executa um SELECT e devolve só a primeira linha (ou None)."""
    _, linhas = consultar(sql, parametros)
    return linhas[0] if linhas else None


def _traduzir_erro_integridade(erro):
    """Converte o código de erro do MySQL em mensagem compreensível."""
    codigo = erro.args[0] if erro.args else None
    if codigo == 1451:  # ER_ROW_IS_REFERENCED_2 — FK impede a exclusão
        return (
            "Não é possível excluir: existem registros vinculados a este "
            "item (restrição de chave estrangeira)."
        )
    if codigo == 1452:  # ER_NO_REFERENCED_ROW_2 — FK aponta para algo inexistente
        return "O registro relacionado informado não existe."
    if codigo == 1062:  # ER_DUP_ENTRY
        return "Já existe um registro com esse valor único."
    return "O banco recusou a operação por violar uma restrição de integridade."
