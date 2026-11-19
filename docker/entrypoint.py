#!/usr/bin/env python3
"""Entrypoint do contêiner ORIS.

Ordem: espera o MySQL -> cria/atualiza tabelas, funcoes, triggers e views ->
(opcional) carrega os dados ficticios de demonstracao -> liga o gunicorn.
Idempotente: pode reiniciar o contêiner quantas vezes quiser.

Variaveis: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, SECRET_KEY (se vazia,
e gerada a cada partida), ORIS_SEED (true/false; so carrega se o banco nao tem unidades).
"""

import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

RAIZ = Path(__file__).resolve().parent.parent
SEEDS = ["database/seed_etapa03.sql", "database/seed_etapa06.sql"]


def log(msg):
    print(f"[oris] {msg}", flush=True)


def conectar(multi=False):
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "oris_user"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "oris_db"),
        charset="utf8mb4",
        client_flag=CLIENT.MULTI_STATEMENTS if multi else 0,
    )


def esperar_banco(tentativas=60):
    for i in range(1, tentativas + 1):
        try:
            conectar().close()
            log("MySQL respondeu.")
            return
        except pymysql.MySQLError as exc:
            log(f"aguardando o MySQL ({i}/{tentativas}): {exc.args[0] if exc.args else exc}")
            time.sleep(2)
    log("ERRO: o MySQL nao respondeu a tempo.")
    sys.exit(1)


def preparar_schema():
    log("criando/atualizando tabelas, triggers e views...")
    r = subprocess.call([sys.executable, str(RAIZ / "database" / "aplicar_migracoes.py")], cwd=RAIZ)
    if r != 0:
        log("ERRO: nao consegui preparar o banco.")
        sys.exit(1)


def carregar_seed():
    if os.environ.get("ORIS_SEED", "true").strip().lower() != "true":
        log("seed desligado (ORIS_SEED != true).")
        return
    con = conectar()
    with con.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM unidades")
        existentes = cur.fetchone()[0]
    con.close()
    if existentes:
        log(f"banco ja tem {existentes} unidade(s); seed NAO sera recarregado (ele apagaria dados).")
        return
    log("carregando dados ficticios de demonstracao...")
    con = conectar(multi=True)
    for seed in SEEDS:
        sql = (RAIZ / seed).read_text(encoding="utf-8")
        # Os seeds trazem "USE oris_db;" fixo: aponta para o banco configurado.
        banco = os.environ.get("DB_NAME", "oris_db")
        if not re.fullmatch(r"[A-Za-z0-9_]+", banco):
            log("ERRO: DB_NAME invalido.")
            sys.exit(1)
        sql = sql.replace("USE oris_db;", f"USE {banco};")
        with con.cursor() as cur:
            cur.execute(sql)
            while cur.nextset():
                pass
        con.commit()
        log(f"{seed} carregado.")
    con.close()
    trocar_senha_demo()


def trocar_senha_demo():
    """Se ORIS_DEMO_SENHA existir, os usuarios de demonstracao (@oris.example) passam a usar
    essa senha em vez da senha publica do repositorio. Obrigatorio em hospedagem na internet."""
    senha = os.environ.get("ORIS_DEMO_SENHA", "")
    if not senha:
        return
    sys.path.insert(0, str(RAIZ))
    from app.utils.security import gerar_hash_senha

    con = conectar()
    with con.cursor() as cur:
        cur.execute("UPDATE usuarios SET senha_hash = %s WHERE email LIKE %s",
                    (gerar_hash_senha(senha), "%@oris.example"))
    con.commit()
    con.close()
    log("senha dos usuarios de demonstracao trocada por ORIS_DEMO_SENHA.")


def main():
    if not os.environ.get("SECRET_KEY"):
        os.environ["SECRET_KEY"] = secrets.token_hex(32)
        log("SECRET_KEY nao definida: gerada para esta execucao (sessoes caem se reiniciar).")
    if not os.environ.get("DATA_ENCRYPTION_KEY"):
        from cryptography.fernet import Fernet

        os.environ["DATA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        log("DATA_ENCRYPTION_KEY nao definida: gerada para esta execucao. Alteracoes pendentes e "
            "uploads cifrados ficam ilegiveis se reiniciar; em producao defina a chave (docker-compose.aws.yml exige).")
    esperar_banco()
    preparar_schema()
    carregar_seed()
    log("ligando o servidor em 0.0.0.0:5000")
    # 1 worker + threads: o rate limit de login e em memoria e precisa ser unico.
    os.execvp("gunicorn", ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1",
                           "--threads", "4", "--access-logfile", "-", "run:app"])


if __name__ == "__main__":
    main()
