"""
Painel estatístico — consultas SQL explícitas + estatística descritiva.

Alimenta os gráficos da tela /bd/estatistica (integração com a
disciplina de Estatística). As medidas que o SQL calcula nativamente
(média, desvio padrão, variância, mínimo, máximo) vêm do próprio
banco; mediana, quartis e moda — que o MySQL não tem como função
agregada padrão — são calculadas em Python sobre a amostra lida.
"""

import statistics

from app.bd.conexao import consultar, consultar_um

SQL_UNIDADES_POR_SITUACAO = """
    SELECT situacao AS rotulo, COUNT(*) AS total
      FROM unidades
     GROUP BY situacao
     ORDER BY total DESC
"""

SQL_UNIDADES_POR_TIPO = """
    SELECT COALESCE(NULLIF(TRIM(tipo), ''), '(não informado)') AS rotulo, COUNT(*) AS total
      FROM unidades
     GROUP BY rotulo
     ORDER BY total DESC
"""

SQL_EQUIPAMENTOS_POR_TIPO = """
    SELECT COALESCE(NULLIF(TRIM(tipo), ''), '(não informado)') AS rotulo,
           SUM(situacao = 'ATIVO')   AS ativos,
           SUM(situacao = 'INATIVO') AS inativos
      FROM equipamentos
     GROUP BY rotulo
     ORDER BY COUNT(*) DESC
"""

# Amostra: nº de equipamentos ATIVOS em cada unidade ATIVA (inclui zero)
SQL_AMOSTRA_EQUIP_POR_UNIDADE = """
    SELECT u.id, COUNT(e.id) AS qtd
      FROM unidades u
      LEFT JOIN equipamentos e
             ON e.unidade_id = u.id AND e.situacao = 'ATIVO'
     WHERE u.situacao = 'ATIVA'
     GROUP BY u.id
"""

SQL_MEDIDAS_EQUIP_POR_UNIDADE = """
    SELECT COUNT(*)             AS n,
           AVG(qtd)             AS media,
           STDDEV_SAMP(qtd)     AS desvio_padrao,
           VAR_SAMP(qtd)        AS variancia,
           MIN(qtd)             AS minimo,
           MAX(qtd)             AS maximo
      FROM (SELECT u.id, COUNT(e.id) AS qtd
              FROM unidades u
              LEFT JOIN equipamentos e
                     ON e.unidade_id = u.id AND e.situacao = 'ATIVO'
             WHERE u.situacao = 'ATIVA'
             GROUP BY u.id) AS amostra
"""

SQL_ALTERACOES_POR_MES = """
    SELECT DATE_FORMAT(created_at, '%Y-%m') AS mes,
           SUM(status = 'APROVADO')  AS aprovadas,
           SUM(status = 'REJEITADO') AS rejeitadas,
           SUM(status = 'PENDENTE')  AS pendentes
      FROM alteracoes
     GROUP BY mes
     ORDER BY mes
"""

SQL_OPERACOES_BD_POR_TIPO = """
    SELECT acao AS rotulo, COUNT(*) AS total
      FROM auditorias
     WHERE acao LIKE 'BD\\_%'
     GROUP BY acao
     ORDER BY acao
"""


def _rotulos_valores(linhas, *colunas):
    return {
        "rotulos": [str(l["rotulo"]) for l in linhas],
        **{c: [float(l[c] or 0) for l in linhas] for c in colunas},
    }


def _num(valor, casas=2):
    return None if valor is None else round(float(valor), casas)


def medidas_descritivas():
    _, linhas = consultar(SQL_AMOSTRA_EQUIP_POR_UNIDADE)
    amostra = sorted(int(l["qtd"]) for l in linhas)
    sql = consultar_um(SQL_MEDIDAS_EQUIP_POR_UNIDADE) or {}

    medidas = {
        "n": int(sql.get("n") or 0),
        "media": _num(sql.get("media")),
        "desvio_padrao": _num(sql.get("desvio_padrao")),
        "variancia": _num(sql.get("variancia")),
        "minimo": sql.get("minimo"),
        "maximo": sql.get("maximo"),
        "mediana": None, "moda": None, "q1": None, "q3": None, "iqr": None, "cv": None,
    }
    if amostra:
        medidas["mediana"] = _num(statistics.median(amostra))
        medidas["moda"] = ", ".join(str(m) for m in statistics.multimode(amostra))
    if len(amostra) >= 2:
        q1, _, q3 = statistics.quantiles(amostra, n=4, method="inclusive")
        medidas.update(q1=_num(q1), q3=_num(q3), iqr=_num(q3 - q1))
    if medidas["media"] and medidas["desvio_padrao"] is not None:
        medidas["cv"] = _num(100 * medidas["desvio_padrao"] / medidas["media"], 1)

    # Distribuição de frequências (histograma de valores discretos)
    frequencias = {}
    for valor in amostra:
        frequencias[valor] = frequencias.get(valor, 0) + 1
    maximo = max(amostra) if amostra else 0
    histograma = {
        "rotulos": [str(v) for v in range(0, maximo + 1)],
        "frequencias": [frequencias.get(v, 0) for v in range(0, maximo + 1)],
    }
    return medidas, histograma


def dados_graficos():
    _, situacao = consultar(SQL_UNIDADES_POR_SITUACAO)
    _, tipo_unidade = consultar(SQL_UNIDADES_POR_TIPO)
    _, tipo_equip = consultar(SQL_EQUIPAMENTOS_POR_TIPO)
    _, alteracoes = consultar(SQL_ALTERACOES_POR_MES)
    _, operacoes = consultar(SQL_OPERACOES_BD_POR_TIPO)
    medidas, histograma = medidas_descritivas()

    return {
        "situacao": _rotulos_valores(situacao, "total"),
        "tipo_unidade": _rotulos_valores(tipo_unidade, "total"),
        "tipo_equipamento": _rotulos_valores(tipo_equip, "ativos", "inativos"),
        "alteracoes_mes": {
            "rotulos": [l["mes"] for l in alteracoes],
            **{c: [int(l[c] or 0) for l in alteracoes]
               for c in ("aprovadas", "rejeitadas", "pendentes")},
        },
        "operacoes_bd": _rotulos_valores(operacoes, "total"),
        "histograma": histograma,
    }, medidas
