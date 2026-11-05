"""Guarda anti SQL Injection do módulo BD (SQL explícito, Etapa 03).

Análise estática (AST) de `app/bd/`: todo SQL enviado ao banco precisa ser uma
constante literal, e os valores vêm sempre por parâmetros (`%s` / `%(nome)s`).
Se alguém passar a montar SQL com f-string, `+`, `%` ou `.format()`, este teste falha.
"""

import ast
import pathlib

import pytest

PASTA_BD = pathlib.Path(__file__).resolve().parent.parent / "app" / "bd"
ARQUIVOS = sorted(PASTA_BD.glob("*.py"))
FUNCOES_SQL = {"execute", "executemany", "consultar", "consultar_um"}


def _arvore(arquivo):
    return ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))


def _nome_da_chamada(no):
    func = no.func
    return getattr(func, "attr", getattr(func, "id", None))


def _primeiro_argumento_seguro(arg):
    """Aceita apenas: constante SQL_*, o parâmetro `sql` das funções de conexão
    ou o `sql` do catálogo de consultas (consulta["sql"])."""
    if isinstance(arg, ast.Name):
        return arg.id.startswith("SQL_") or arg.id == "sql"
    if isinstance(arg, ast.Subscript):
        chave = arg.slice
        return isinstance(chave, ast.Constant) and chave.value == "sql"
    return False


def test_pasta_bd_tem_arquivos():
    assert len(ARQUIVOS) >= 5


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda a: a.name)
def test_chamadas_ao_banco_nao_montam_sql_dinamicamente(arquivo):
    for no in ast.walk(_arvore(arquivo)):
        if isinstance(no, ast.Call) and _nome_da_chamada(no) in FUNCOES_SQL and no.args:
            assert _primeiro_argumento_seguro(no.args[0]), (
                f"{arquivo.name}:{no.lineno} monta SQL dinamicamente: "
                f"{ast.unparse(no.args[0])[:80]}"
            )


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda a: a.name)
def test_constantes_sql_sao_literais(arquivo):
    for no in ast.walk(_arvore(arquivo)):
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id.startswith("SQL_"):
                    assert isinstance(no.value, ast.Constant) and isinstance(no.value.value, str), (
                        f"{arquivo.name}:{no.lineno} {alvo.id} deve ser string literal "
                        "(sem f-string, concatenação ou formatação)"
                    )


def test_o_proprio_guarda_detecta_sql_montado_com_fstring():
    codigo = 'def f(cur, nome):\n    cur.execute(f"SELECT * FROM unidades WHERE nome = \'{nome}\'")\n'
    chamada = next(n for n in ast.walk(ast.parse(codigo)) if isinstance(n, ast.Call))
    assert not _primeiro_argumento_seguro(chamada.args[0])


def test_o_proprio_guarda_detecta_concatenacao():
    codigo = 'def f(cur, nome):\n    cur.execute("SELECT * FROM unidades WHERE nome = " + nome)\n'
    chamada = next(n for n in ast.walk(ast.parse(codigo)) if isinstance(n, ast.Call))
    assert not _primeiro_argumento_seguro(chamada.args[0])
