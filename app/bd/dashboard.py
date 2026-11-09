"""Dashboard estatístico integrado (Etapa 06) - todos os números vêm do MySQL.

Usa as VIEWS criadas em database/etapa05_objetos.sql. Filtros interativos: período (data de
abertura da manutenção), tipo e situação da unidade e tipo de manutenção.
Todos os filtros viajam como parâmetros do driver (%(nome)s).
"""

from datetime import date

from app.bd.conexao import consultar, consultar_um

SITUACOES_UNIDADE = ("ATIVA", "INATIVA", "MANUTENCAO")
TIPOS_MANUTENCAO = ("PREVENTIVA", "CORRETIVA")

# Filtros comuns (repetidos de forma literal em cada SQL, como exige
# tests/test_bd_sql_estatico.py - nada de SQL montado por f-string):
#   unidades   : (%(unidade_tipo)s IS NULL OR p.tipo = ...) AND (%(unidade_situacao)s IS NULL OR ...)
#   manutencoes: os de unidades + tipo_manutencao, data_ini e data_fim (data de abertura)

SQL_KPI_UNIDADES = """
    SELECT COUNT(*)                              AS unidades,
           COALESCE(SUM(p.servicos_ativos), 0)   AS servicos_ativos,
           COALESCE(SUM(p.equipamentos_total), 0) AS equipamentos,
           COALESCE(SUM(p.equipamentos_ativos), 0) AS equipamentos_ativos,
           COALESCE(SUM(p.classificacao = 'CRITICA'), 0) AS unidades_criticas,
           ROUND(AVG(p.pct_operantes), 1)        AS media_pct_operantes
      FROM vw_painel_unidades p
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)

"""

SQL_KPI_MANUT = """
    SELECT COUNT(*)                                 AS total,
           COALESCE(SUM(m.situacao = 'ABERTA'), 0)  AS abertas,
           COALESCE(SUM(m.custo), 0)                AS custo_total,
           ROUND(AVG(CASE WHEN m.situacao = 'CONCLUIDA' THEN m.custo END), 2) AS custo_medio,
           ROUND(AVG(m.dias_duracao), 1)            AS dias_medios
      FROM vw_manutencoes_detalhe m JOIN vw_painel_unidades p ON p.unidade_id = m.unidade_id
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)

    AND (%(tipo_manutencao)s IS NULL OR m.tipo = %(tipo_manutencao)s)
    AND (%(data_ini)s IS NULL OR m.data_abertura >= %(data_ini)s)
    AND (%(data_fim)s IS NULL OR m.data_abertura <= %(data_fim)s)

"""

SQL_CLASSIFICACAO = """
    SELECT p.classificacao AS rotulo, COUNT(*) AS total
      FROM vw_painel_unidades p
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)

     GROUP BY p.classificacao
     ORDER BY total DESC
"""

SQL_EQUIP_POR_TIPO = """
    SELECT COALESCE(NULLIF(TRIM(e.tipo), ''), '(não informado)') AS rotulo,
           SUM(e.situacao = 'ATIVO')   AS ativos,
           SUM(e.situacao = 'INATIVO') AS inativos
      FROM equipamentos e
      JOIN vw_painel_unidades p ON p.unidade_id = e.unidade_id
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)

     GROUP BY rotulo
     ORDER BY COUNT(*) DESC
     LIMIT 8
"""

SQL_MENSAL = """
    SELECT m.mes AS rotulo, COUNT(*) AS qtd, ROUND(SUM(m.custo), 2) AS custo
      FROM vw_manutencoes_detalhe m JOIN vw_painel_unidades p ON p.unidade_id = m.unidade_id
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)

    AND (%(tipo_manutencao)s IS NULL OR m.tipo = %(tipo_manutencao)s)
    AND (%(data_ini)s IS NULL OR m.data_abertura >= %(data_ini)s)
    AND (%(data_fim)s IS NULL OR m.data_abertura <= %(data_fim)s)

     GROUP BY m.mes
     ORDER BY m.mes
"""

SQL_CUSTO_POR_TIPO = """
    SELECT m.tipo AS rotulo, COUNT(*) AS qtd, ROUND(SUM(m.custo), 2) AS custo
      FROM vw_manutencoes_detalhe m JOIN vw_painel_unidades p ON p.unidade_id = m.unidade_id
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)

    AND (%(tipo_manutencao)s IS NULL OR m.tipo = %(tipo_manutencao)s)
    AND (%(data_ini)s IS NULL OR m.data_abertura >= %(data_ini)s)
    AND (%(data_fim)s IS NULL OR m.data_abertura <= %(data_fim)s)

     GROUP BY m.tipo
     ORDER BY m.tipo
"""

SQL_TOP_UNIDADES_CUSTO = """
    SELECT m.unidade AS rotulo, ROUND(SUM(m.custo), 2) AS custo
      FROM vw_manutencoes_detalhe m JOIN vw_painel_unidades p ON p.unidade_id = m.unidade_id
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)

    AND (%(tipo_manutencao)s IS NULL OR m.tipo = %(tipo_manutencao)s)
    AND (%(data_ini)s IS NULL OR m.data_abertura >= %(data_ini)s)
    AND (%(data_fim)s IS NULL OR m.data_abertura <= %(data_fim)s)

     GROUP BY m.unidade_id, m.unidade
     ORDER BY custo DESC, rotulo
     LIMIT 5
"""

SQL_MANUT_POR_TIPO_EQUIP = """
    SELECT COALESCE(NULLIF(TRIM(m.tipo_equipamento), ''), '(não informado)') AS rotulo,
           COUNT(*) AS qtd
      FROM vw_manutencoes_detalhe m JOIN vw_painel_unidades p ON p.unidade_id = m.unidade_id
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)

    AND (%(tipo_manutencao)s IS NULL OR m.tipo = %(tipo_manutencao)s)
    AND (%(data_ini)s IS NULL OR m.data_abertura >= %(data_ini)s)
    AND (%(data_fim)s IS NULL OR m.data_abertura <= %(data_fim)s)

     GROUP BY rotulo
     ORDER BY qtd DESC
     LIMIT 6
"""

SQL_UNIDADES_ATENCAO = """
    SELECT p.unidade, p.tipo, p.situacao, p.equipamentos_total, p.pct_operantes,
           p.classificacao, p.manutencoes_abertas
      FROM vw_painel_unidades p
     WHERE 
    (%(unidade_tipo)s IS NULL OR p.tipo = %(unidade_tipo)s)
    AND (%(unidade_situacao)s IS NULL OR p.situacao = %(unidade_situacao)s)
 AND p.classificacao IN ('CRITICA', 'ATENCAO')
     ORDER BY p.pct_operantes, p.unidade
     LIMIT 10
"""

SQL_TIPOS_UNIDADE = "SELECT DISTINCT tipo FROM vw_painel_unidades ORDER BY tipo"


def _data(valor):
    try:
        return date.fromisoformat(valor).isoformat() if valor else None
    except ValueError:
        return None


def ler_filtros(args):
    """Valida os filtros vindos da URL; valor inválido vira 'sem filtro'."""
    situacao = args.get("unidade_situacao")
    tipo_m = args.get("tipo_manutencao")
    return {
        "unidade_tipo": (args.get("unidade_tipo") or "").strip()[:100] or None,
        "unidade_situacao": situacao if situacao in SITUACOES_UNIDADE else None,
        "tipo_manutencao": tipo_m if tipo_m in TIPOS_MANUTENCAO else None,
        "data_ini": _data(args.get("data_ini")),
        "data_fim": _data(args.get("data_fim")),
    }


def opcoes_filtros():
    _, linhas = consultar(SQL_TIPOS_UNIDADE)
    return {"tipos_unidade": [l["tipo"] for l in linhas]}


def _numero(v, casas=2):
    return None if v is None else round(float(v), casas)


def _serie(linhas, *colunas):
    return {"rotulos": [str(l["rotulo"]) for l in linhas],
            **{c: [float(l[c] or 0) for l in linhas] for c in colunas}}


def _tendencia(mensal):
    """Variação % do último mês do período em relação ao anterior (qtd de manutenções)."""
    qtds = mensal["qtd"]
    if len(qtds) < 2 or not qtds[-2]:
        return None
    return round(100 * (qtds[-1] - qtds[-2]) / qtds[-2], 1)


def dados(filtros):
    ku = consultar_um(SQL_KPI_UNIDADES, filtros) or {}
    km = consultar_um(SQL_KPI_MANUT, filtros) or {}
    equip = int(ku.get("equipamentos") or 0)
    ativos = int(ku.get("equipamentos_ativos") or 0)

    mensal = _serie(consultar(SQL_MENSAL, filtros)[1], "qtd", "custo")
    resultado = {
        "kpis": {
            "unidades": int(ku.get("unidades") or 0),
            "servicos_ativos": int(ku.get("servicos_ativos") or 0),
            "equipamentos": equip,
            "pct_operantes": round(100 * ativos / equip, 1) if equip else None,
            "unidades_criticas": int(ku.get("unidades_criticas") or 0),
            "manutencoes": int(km.get("total") or 0),
            "manutencoes_abertas": int(km.get("abertas") or 0),
            "custo_total": _numero(km.get("custo_total")) or 0,
            "custo_medio": _numero(km.get("custo_medio")),
            "dias_medios": _numero(km.get("dias_medios"), 1),
            "tendencia_manutencoes": _tendencia(mensal),
        },
        "classificacao": _serie(consultar(SQL_CLASSIFICACAO, filtros)[1], "total"),
        "equip_por_tipo": _serie(consultar(SQL_EQUIP_POR_TIPO, filtros)[1], "ativos", "inativos"),
        "mensal": mensal,
        "custo_por_tipo": _serie(consultar(SQL_CUSTO_POR_TIPO, filtros)[1], "qtd", "custo"),
        "top_unidades_custo": _serie(consultar(SQL_TOP_UNIDADES_CUSTO, filtros)[1], "custo"),
        "manut_por_tipo_equip": _serie(consultar(SQL_MANUT_POR_TIPO_EQUIP, filtros)[1], "qtd"),
        "unidades_atencao": [
            {**l, "pct_operantes": _numero(l["pct_operantes"], 1)}
            for l in consultar(SQL_UNIDADES_ATENCAO, filtros)[1]
        ],
    }
    return resultado
