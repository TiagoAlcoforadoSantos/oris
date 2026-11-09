#!/usr/bin/env python3
"""ORIS - instala e liga o projeto com UM comando (Windows, Linux e Mac).

Uso (na pasta do projeto):
    python iniciar.py              # instala tudo (se preciso) e liga o ORIS
    python iniciar.py --sem-seed   # nao pergunta/carrega os dados de demonstracao
    python iniciar.py --so-preparar  # prepara tudo mas nao sobe o servidor

Pre-requisitos: Python 3.10+ e MySQL Server 8.x instalado e LIGADO.
O script e seguro de repetir: so faz o que ainda nao foi feito.

O que faz, na ordem:
  1. Cria o ambiente virtual (venv) e instala o requirements.txt
  2. Cria o .env (com SECRET_KEY e senha do banco gerados na hora)
  3. Cria o banco oris_db e o usuario oris_user no MySQL (pede a senha do root,
     so na primeira vez; ela NAO e gravada em lugar nenhum)
  4. Cria as tabelas, funcoes, procedures, triggers e views
  5. (opcional) Carrega os dados de demonstracao e os usuarios de teste
  6. Sobe o servidor em http://127.0.0.1:5000
"""

import getpass
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VENV = RAIZ / "venv"
PY_VENV = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
SEEDS = ["database/seed_etapa03.sql", "database/seed_etapa06.sql"]
BANCO = "oris_db"
USUARIO_BD = "oris_user"


def passo(texto):
    print(f"\n==> {texto}", flush=True)


def ok(texto):
    print(f"OK: {texto}", flush=True)


def aviso(texto):
    print(f"AVISO: {texto}", flush=True)


def falhar(texto):
    print(f"\nERRO: {texto}", file=sys.stderr, flush=True)
    sys.exit(1)


def perguntar_sn(pergunta, padrao=True):
    sufixo = "[S/n]" if padrao else "[s/N]"
    resposta = input(f"{pergunta} {sufixo} ").strip().lower()
    if not resposta:
        return padrao
    return resposta.startswith("s")


# --------------------------------------------------------------------------
# Etapa 1 (roda no Python do sistema): venv + dependencias, depois re-executa
# este mesmo arquivo dentro do venv.
# --------------------------------------------------------------------------
def etapa_1(argumentos):
    if sys.version_info < (3, 10):
        falhar(f"Python 3.10+ necessario (voce tem {sys.version.split()[0]}).")
    os.chdir(RAIZ)
    if not (RAIZ / "run.py").exists():
        falhar("Rode este script dentro da pasta do projeto (onde esta o run.py).")

    passo("Preparando o ambiente virtual...")
    if not PY_VENV.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    ok("venv pronto.")

    passo("Instalando as dependencias (requirements.txt)...")
    r = subprocess.call([str(PY_VENV), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements.txt"])
    if r != 0:
        falhar("Falha ao instalar as dependencias. Veja a mensagem acima.")
    ok("Dependencias instaladas.")

    sys.exit(subprocess.call([str(PY_VENV), str(Path(__file__).resolve()), "--etapa-2", *argumentos]))


# --------------------------------------------------------------------------
# Etapa 2 (roda dentro do venv)
# --------------------------------------------------------------------------
def ler_env():
    valores = {}
    arquivo = RAIZ / ".env"
    if arquivo.exists():
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                valores[k.strip()] = v.strip()
    return valores


def criar_env():
    """Cria o .env a partir do exemplo, com SECRET_KEY e senha do banco novas."""
    passo("Conferindo o arquivo .env...")
    destino = RAIZ / ".env"
    if destino.exists():
        ok(".env ja existe (nao foi alterado).")
        return False
    exemplo = RAIZ / ".env.example"
    if not exemplo.exists():
        falhar("Nao existe .env nem .env.example.")
    texto = exemplo.read_text(encoding="utf-8")
    novos = {
        "SECRET_KEY": secrets.token_hex(32),
        "DB_PASSWORD": secrets.token_urlsafe(18),
        "DB_NAME": BANCO,
        "DB_USER": USUARIO_BD,
    }
    linhas = []
    for linha in texto.splitlines():
        chave = linha.split("=", 1)[0].strip()
        if "=" in linha and not linha.lstrip().startswith("#") and chave in novos:
            linha = f"{chave}={novos[chave]}"
        linhas.append(linha)
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    ok(".env criado com SECRET_KEY e senha do banco gerados automaticamente.")
    return True


def conectar(usuario, senha, banco=None, multi=False):
    import pymysql
    from pymysql.constants import CLIENT

    env = ler_env()
    return pymysql.connect(
        host=env.get("DB_HOST", "localhost"),
        port=int(env.get("DB_PORT", "3306")),
        user=usuario,
        password=senha,
        database=banco,
        charset="utf8mb4",
        autocommit=True,
        client_flag=CLIENT.MULTI_STATEMENTS if multi else 0,
    )


def banco_ja_funciona():
    env = ler_env()
    try:
        conectar(env.get("DB_USER", USUARIO_BD), env.get("DB_PASSWORD", ""), env.get("DB_NAME", BANCO)).close()
        return True
    except Exception:
        return False


def preparar_banco():
    passo("Preparando o banco de dados no MySQL...")
    if banco_ja_funciona():
        ok(f"O usuario '{USUARIO_BD}' ja acessa o banco '{BANCO}'. Nada a criar.")
        return
    env = ler_env()
    senha_app = env.get("DB_PASSWORD", "")
    print("Preciso criar o banco e o usuario da aplicacao. Informe a senha do usuario 'root' do MySQL")
    print("(ela so e usada agora, para criar o banco, e nao e gravada em lugar nenhum).")
    senha_root = os.environ.get("ORIS_MYSQL_ROOT_PASSWORD")
    if senha_root is None:
        senha_root = getpass.getpass("Senha do root do MySQL (Enter se nao tiver): ")
    try:
        con = conectar("root", senha_root)
    except Exception as e:
        falhar(
            f"Nao consegui entrar no MySQL como root ({e}).\n"
            "       Confira se o MySQL esta LIGADO e se a senha esta certa.\n"
            "       Windows: Servicos > MySQL80 > Iniciar.  Linux: sudo systemctl start mysql."
        )
    with con.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{BANCO}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"CREATE USER IF NOT EXISTS '{USUARIO_BD}'@'localhost' IDENTIFIED BY %s", (senha_app,))
        cur.execute(f"ALTER USER '{USUARIO_BD}'@'localhost' IDENTIFIED BY %s", (senha_app,))
        cur.execute(f"GRANT ALL PRIVILEGES ON `{BANCO}`.* TO '{USUARIO_BD}'@'localhost'")
        cur.execute("FLUSH PRIVILEGES")
        # Funcoes/triggers precisam disto quando o log binario esta ligado (padrao do MySQL 8).
        try:
            cur.execute("SELECT @@global.log_bin_trust_function_creators")
            if cur.fetchone()[0] != 1:
                print("O MySQL esta com log_bin_trust_function_creators=0; sem isso as funcoes e triggers do banco nao sao criadas.")
                if perguntar_sn("Ativar agora (SET GLOBAL, vale ate reiniciar o MySQL)?"):
                    cur.execute("SET GLOBAL log_bin_trust_function_creators = 1")
                    ok("Ativado. Para ficar permanente, ponha log_bin_trust_function_creators=1 no my.ini/my.cnf.")
        except Exception as e:
            aviso(f"Nao consegui conferir log_bin_trust_function_creators: {e}")
    con.close()
    if not banco_ja_funciona():
        falhar("Criei o banco, mas o usuario da aplicacao ainda nao conecta. Veja o DB_HOST/DB_PORT no .env.")
    ok(f"Banco '{BANCO}' e usuario '{USUARIO_BD}' prontos.")


def aplicar_migracoes():
    passo("Criando tabelas, funcoes, procedures, triggers e views...")
    r = subprocess.call([sys.executable, str(RAIZ / "database" / "aplicar_migracoes.py")], cwd=RAIZ)
    if r != 0:
        falhar("Nao consegui preparar o banco. Veja a mensagem acima.")
    ok("Banco atualizado.")


def carregar_seeds(sem_seed):
    passo("Dados de demonstracao...")
    env = ler_env()
    if sem_seed:
        ok("Pulado (--sem-seed).")
        return
    con = conectar(env.get("DB_USER", USUARIO_BD), env.get("DB_PASSWORD", ""), env.get("DB_NAME", BANCO))
    with con.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM unidades")
        existentes = cur.fetchone()[0]
    con.close()
    if existentes:
        print(f"O banco ja tem {existentes} unidade(s). Carregar os dados de demonstracao APAGA unidades/servicos/equipamentos/alteracoes.")
        if not perguntar_sn("Carregar mesmo assim?", padrao=False):
            ok("Mantive os dados atuais.")
            return
    elif not perguntar_sn("Carregar dados FICTICIOS de demonstracao e usuarios de teste?"):
        ok("Pulado.")
        return
    con = conectar(env.get("DB_USER", USUARIO_BD), env.get("DB_PASSWORD", ""), env.get("DB_NAME", BANCO), multi=True)
    for seed in SEEDS:
        sql = (RAIZ / seed).read_text(encoding="utf-8")
        with con.cursor() as cur:
            cur.execute(sql)
            while cur.nextset():
                pass
        ok(f"{seed} carregado.")
    con.close()
    print("\nUsuarios de demonstracao (senha de todos: Oris@2026 - TROQUE antes de colocar no ar):")
    print("  admin.demo@oris.example  (ADMINISTRADOR)")
    print("  gi.demo@oris.example     (GESTAO_INFORMACAO)")
    print("  rsb.demo@oris.example    (RESPONSAVEL_SAUDE_BUCAL)")
    print("  gestor.demo@oris.example (GESTOR)")


def ligar():
    passo("Iniciando o ORIS em http://127.0.0.1:5000 ...")
    print("Deixe esta janela ABERTA. Para parar: Ctrl+C.", flush=True)
    try:
        import threading
        import webbrowser

        threading.Timer(3, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    except Exception:
        pass
    os.chdir(RAIZ)
    sys.exit(subprocess.call([sys.executable, "run.py"]))


def etapa_2(argumentos):
    os.chdir(RAIZ)
    criar_env()
    preparar_banco()
    aplicar_migracoes()
    carregar_seeds("--sem-seed" in argumentos)
    if "--so-preparar" in argumentos:
        ok("Tudo preparado. Para ligar: python iniciar.py")
        return
    ligar()


def main():
    argumentos = [a for a in sys.argv[1:] if a != "--etapa-2"]
    if "--etapa-2" in sys.argv:
        etapa_2(argumentos)
    else:
        etapa_1(argumentos)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido.")
        sys.exit(130)
