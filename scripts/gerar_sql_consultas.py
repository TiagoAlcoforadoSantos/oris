"""Gera database/consultas_etapa03.sql a partir do catálogo usado pela aplicação..."""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.bd import consultas, dao_equipamentos, dao_servicos, dao_unidades  # noqa: E402

SAIDA = RAIZ / "database" / "consultas_etapa03.sql"


def literal(valor):
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)):
        return str(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def substituir_nomeados(sql, valores):
    return re.sub(r"%\((\w+)\)s", lambda m: literal(valores[m.group(1)]), sql)


def substituir_posicionais(sql, valores):
    it = iter(valores)
    return re.sub(r"%s", lambda m: literal(next(it)), sql)


def bloco(titulo, linhas_comentario, sql):
    out = ["-- " + "-" * 66, f"-- {titulo}"]
    out += [f"-- {linha}" if linha else "--" for linha in linhas_comentario]
    out.append("-- " + "-" * 66)
    out.append(sql.strip().rstrip(";") + ";")
    out.append("")
    return out


def quebrar(texto, largura=64):
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        if len(atual) + len(p) + 1 > largura:
            linhas.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    if atual:
        linhas.append(atual)
    return linhas


def main():
    out = [
        "-- ==================================================================",
        "-- ORIS — Plataforma de Governança da Rede de Saúde Bucal",
        "-- ETAPA 03 — SQL das consultas (e dos comandos de manipulação)",
        "--",
        "-- SGBD: MySQL 8.0+ (compatível com MariaDB 10.3+)",
        "-- Arquivo GERADO por scripts/gerar_sql_consultas.py a partir do",
        "-- código da aplicação (app/bd/consultas.py e app/bd/dao_*.py):",
        "-- é exatamente o SQL que o backend envia ao banco via PyMySQL",
        "-- (DB-API 2.0, equivalente ao JDBC). Na aplicação, os valores vão",
        "-- como parâmetros do driver (%s / %(nome)s ≈ '?' do PreparedStatement);",
        "-- aqui foram trocados por valores de exemplo para execução direta.",
        "--",
        "-- Para popular o banco com dados de demonstração antes de rodar:",
        "--   mysql -u <usuario> -p < database/seed_etapa03.sql",
        "-- ==================================================================",
        "",
        "USE oris_db;",
        "",
        "-- ##################################################################",
        f"-- PARTE 1 — CONSULTAS DA ETAPA 03 ({len(consultas.CONSULTAS)} consultas)",
        "-- ##################################################################",
        "",
    ]
    for c in consultas.CONSULTAS:
        exemplo = {p["nome"]: p.get("exemplo", p["padrao"]) or None for p in c["parametros"]}
        comentario = ["Pergunta:"] + quebrar(c["pergunta"])
        comentario += ["", f"Nível: {c['nivel']}", "Recursos de SQL:"]
        comentario += [f"  - {conceito}" for conceito in c["conceitos"]]
        if c["parametros"]:
            comentario += ["", "Parâmetros (valor de exemplo usado abaixo):"]
            comentario += [f"  - {p['nome']} = {literal(exemplo[p['nome']])}  ({p['rotulo']})"
                           for p in c["parametros"]]
        out += bloco(f"{c['id'].upper()} — {c['titulo']}", comentario,
                     substituir_nomeados(c["sql"], exemplo))

    out += [
        "-- ##################################################################",
        "-- PARTE 2 — COMANDOS DE INSERÇÃO / ALTERAÇÃO / EXCLUSÃO",
        "-- (executados pela interface, telas /bd/unidades, /bd/servicos,",
        "--  /bd/equipamentos). Valores ilustrativos. Toda escrita grava também",
        "-- um registro em `auditorias` NA MESMA TRANSAÇÃO.",
        "-- ##################################################################",
        "",
        "START TRANSACTION;",
        "",
    ]
    exemplos = [
        ("UNIDADES — INSERT", dao_unidades.SQL_INSERIR,
         ("USF Exemplo Etapa 03", "9199999", 0, "Unidade de Saúde da Família",
          "Rua Exemplo 100", "Várzea", "Recife", "PE", "ATIVA")),
        ("UNIDADES — UPDATE", dao_unidades.SQL_ATUALIZAR,
         ("USF Exemplo Etapa 03", "9199999", 0, "Unidade de Saúde da Família",
          "Rua Exemplo 100", "Várzea", "Recife", "PE", "MANUTENCAO", "@@ID_UNIDADE")),
        ("SERVIÇOS — INSERT", dao_servicos.SQL_INSERIR,
         ("Atenção Básica em Saúde Bucal", "@@ID_UNIDADE", "ATIVO")),
        ("SERVIÇOS — UPDATE", dao_servicos.SQL_ATUALIZAR,
         ("Atenção Básica em Saúde Bucal", "@@ID_UNIDADE", "INATIVO", "@@ID_SERVICO")),
        ("EQUIPAMENTOS — INSERT", dao_equipamentos.SQL_INSERIR,
         ("Autoclave 21 L #1", "Autoclave", "@@ID_UNIDADE", "@@ID_SERVICO", "ATIVO")),
        ("EQUIPAMENTOS — UPDATE", dao_equipamentos.SQL_ATUALIZAR,
         ("Autoclave 21 L #1", "Autoclave", "@@ID_UNIDADE", "@@ID_SERVICO", "INATIVO",
          "@@ID_EQUIP")),
        ("EQUIPAMENTOS — DELETE", dao_equipamentos.SQL_EXCLUIR, ("@@ID_EQUIP",)),
        ("SERVIÇOS — DELETE (só sem equipamentos vinculados)", dao_servicos.SQL_EXCLUIR,
         ("@@ID_SERVICO",)),
        ("UNIDADES — DELETE (só sem serviços/equipamentos vinculados)",
         dao_unidades.SQL_EXCLUIR, ("@@ID_UNIDADE",)),
    ]
    variaveis = {"@@ID_UNIDADE": "@id_unidade", "@@ID_SERVICO": "@id_servico",
                 "@@ID_EQUIP": "@id_equip"}
    captura = {"UNIDADES — INSERT": "@id_unidade", "SERVIÇOS — INSERT": "@id_servico",
               "EQUIPAMENTOS — INSERT": "@id_equip"}
    for titulo, sql, valores in exemplos:
        texto = substituir_posicionais(sql, valores)
        for marcador, var in variaveis.items():
            texto = texto.replace(literal(marcador), var)
        out += bloco(titulo, [], texto)
        if titulo in captura:
            out += [f"SET {captura[titulo]} = LAST_INSERT_ID();  -- ≈ cursor.lastrowid", ""]
    out += [
        "-- Registro de auditoria gravado junto com cada comando acima:",
        "-- INSERT INTO auditorias (usuario_id, acao, tabela, registro_id, descricao,",
        "--                         valor_anterior, valor_novo, data_hora)",
        "-- VALUES (%s, 'BD_INSERIR' | 'BD_ALTERAR' | 'BD_EXCLUIR', %s, %s, %s, %s, %s, UTC_TIMESTAMP());",
        "",
        "-- Exemplo didático: desfaz tudo o que foi feito na Parte 2.",
        "ROLLBACK;",
        "",
    ]
    SAIDA.write_text("\n".join(out), encoding="utf-8")
    print(f"Gerado: {SAIDA}")


if __name__ == "__main__":
    main()
