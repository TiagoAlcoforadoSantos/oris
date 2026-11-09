"""Catálogo das consultas da Etapa 03 - SQL explícito."""

from app.bd.conexao import consultar

OPCOES_SITUACAO_UNIDADE = [("", "Todas"), ("ATIVA", "Ativa"),
                           ("INATIVA", "Inativa"), ("MANUTENCAO", "Manutenção")]

CONSULTAS = [
    {
        "id": "c1",
        "titulo": "Capacidade instalada por unidade",
        "pergunta": (
            "Quantos serviços e equipamentos ativos cada unidade possui, e "
            "qual o percentual do seu parque de equipamentos que está operante?"
        ),
        "nivel": "Intermediária",
        "conceitos": ["JOIN (LEFT JOIN em 3 tabelas)", "GROUP BY",
                      "COUNT(DISTINCT CASE …) — agregação condicional",
                      "NULLIF para evitar divisão por zero", "Filtro parametrizado"],
        "explicacao": (
            "Unidades é ligada a Serviços e a Equipamentos por LEFT JOIN (unidades "
            "sem nenhum vínculo também aparecem, com zero). Como as duas junções "
            "multiplicam as linhas entre si (fan-out), as contagens usam "
            "COUNT(DISTINCT …) para não contar o mesmo registro várias vezes."
        ),
        "parametros": [
            {"nome": "situacao", "rotulo": "Situação da unidade", "tipo": "select",
             "opcoes": OPCOES_SITUACAO_UNIDADE, "padrao": "", "exemplo": "ATIVA"},
        ],
        "sql": """
SELECT u.id,
       u.nome      AS unidade,
       u.bairro,
       u.situacao,
       COUNT(DISTINCT CASE WHEN s.situacao = 'ATIVO'   THEN s.id END) AS servicos_ativos,
       COUNT(DISTINCT CASE WHEN e.situacao = 'ATIVO'   THEN e.id END) AS equip_ativos,
       COUNT(DISTINCT CASE WHEN e.situacao = 'INATIVO' THEN e.id END) AS equip_inativos,
       ROUND(100 * COUNT(DISTINCT CASE WHEN e.situacao = 'ATIVO' THEN e.id END)
                 / NULLIF(COUNT(DISTINCT e.id), 0), 1)                AS pct_equip_operantes
  FROM unidades u
  LEFT JOIN servicos     s ON s.unidade_id = u.id
  LEFT JOIN equipamentos e ON e.unidade_id = u.id
 WHERE (%(situacao)s IS NULL OR u.situacao = %(situacao)s)
 GROUP BY u.id, u.nome, u.bairro, u.situacao
 ORDER BY equip_ativos DESC, u.nome
""",
        "grafico": {"tipo": "bar", "rotulo": "unidade",
                    "series": ["servicos_ativos", "equip_ativos", "equip_inativos"]},
    },
    {
        "id": "c2",
        "titulo": "Cobertura da rede por bairro",
        "pergunta": (
            "Em cada bairro, quantas unidades existem, quantas estão ativas e "
            "qual a média de equipamentos ativos por unidade?"
        ),
        "nivel": "Intermediária/Avançada",
        "conceitos": ["Tabela derivada (subconsulta no FROM)", "LEFT JOIN",
                      "SUM de expressão booleana", "AVG", "GROUP BY + HAVING parametrizado",
                      "COALESCE"],
        "explicacao": (
            "Primeiro uma tabela derivada conta os equipamentos ativos por unidade; "
            "ela é juntada às unidades e o resultado é agregado por bairro. O HAVING "
            "filtra DEPOIS da agregação (só bairros com pelo menos N unidades) — o "
            "que não seria possível com WHERE."
        ),
        "parametros": [
            {"nome": "minimo", "rotulo": "Mínimo de unidades no bairro", "tipo": "int",
             "padrao": 1, "min": 1, "max": 100, "exemplo": 2},
        ],
        "sql": """
SELECT COALESCE(u.bairro, '(sem bairro)')                      AS bairro,
       COUNT(*)                                                AS unidades,
       SUM(u.situacao = 'ATIVA')                               AS ativas,
       ROUND(100 * SUM(u.situacao = 'ATIVA') / COUNT(*), 1)    AS pct_ativas,
       COALESCE(SUM(eq.qtd), 0)                                AS equip_ativos,
       ROUND(AVG(COALESCE(eq.qtd, 0)), 2)                      AS media_equip_por_unidade
  FROM unidades u
  LEFT JOIN (SELECT unidade_id, COUNT(*) AS qtd
               FROM equipamentos
              WHERE situacao = 'ATIVO'
              GROUP BY unidade_id) AS eq
         ON eq.unidade_id = u.id
 GROUP BY COALESCE(u.bairro, '(sem bairro)')
HAVING COUNT(*) >= %(minimo)s
 ORDER BY unidades DESC, bairro
""",
        "grafico": {"tipo": "bar", "rotulo": "bairro", "series": ["unidades", "ativas"]},
    },
    {
        "id": "c3",
        "titulo": "Unidades ativas sem nenhum equipamento operante",
        "pergunta": (
            "Quais unidades estão ATIVAS mas não têm nenhum equipamento ativo "
            "(lacuna de capacidade que exige ação da gestão)?"
        ),
        "nivel": "Avançada",
        "conceitos": ["NOT EXISTS (anti-junção)", "Subconsulta correlacionada escalar",
                      "DATEDIFF", "UTC_TIMESTAMP()"],
        "explicacao": (
            "O NOT EXISTS executa, para cada unidade, uma subconsulta que depende da "
            "linha externa (correlacionada) e descarta quem tem ao menos um "
            "equipamento ativo. Uma segunda subconsulta escalar conta os serviços "
            "ativos e DATEDIFF mostra há quantos dias o cadastro não é atualizado."
        ),
        "parametros": [],
        "sql": """
SELECT u.id,
       u.nome,
       u.cnes,
       u.bairro,
       (SELECT COUNT(*)
          FROM servicos s
         WHERE s.unidade_id = u.id
           AND s.situacao = 'ATIVO')                AS servicos_ativos,
       DATEDIFF(UTC_TIMESTAMP(), u.updated_at)      AS dias_sem_atualizacao
  FROM unidades u
 WHERE u.situacao = 'ATIVA'
   AND NOT EXISTS (SELECT 1
                     FROM equipamentos e
                    WHERE e.unidade_id = u.id
                      AND e.situacao = 'ATIVO')
 ORDER BY servicos_ativos DESC, u.nome
""",
        "grafico": None,
    },
    {
        "id": "c4",
        "titulo": "Ranking de bairros por equipamentos (curva de Pareto)",
        "pergunta": (
            "Quais bairros concentram os equipamentos ativos da rede, qual a "
            "participação de cada um e a participação acumulada?"
        ),
        "nivel": "Avançada",
        "conceitos": ["CTE (WITH)", "INNER JOIN", "RANK() OVER",
                      "SUM() OVER () — total sem GROUP BY",
                      "SUM() OVER (ORDER BY … ROWS …) — soma acumulada"],
        "explicacao": (
            "A CTE agrega equipamentos ativos por bairro. Na consulta principal, "
            "funções de janela calculam a posição no ranking, o percentual de cada "
            "bairro sobre o total e o percentual acumulado — base da análise de "
            "Pareto (quais poucos bairros concentram a maior parte da capacidade)."
        ),
        "parametros": [],
        "sql": """
WITH equip_bairro AS (
    SELECT COALESCE(u.bairro, '(sem bairro)') AS bairro,
           COUNT(e.id)                        AS qtd
      FROM equipamentos e
      JOIN unidades u ON u.id = e.unidade_id
     WHERE e.situacao = 'ATIVO'
     GROUP BY COALESCE(u.bairro, '(sem bairro)')
)
SELECT RANK() OVER (ORDER BY qtd DESC)                         AS posicao,
       bairro,
       qtd                                                     AS equip_ativos,
       ROUND(100 * qtd / SUM(qtd) OVER (), 1)                  AS pct_do_total,
       ROUND(100 * SUM(qtd) OVER (ORDER BY qtd DESC, bairro
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                 / SUM(qtd) OVER (), 1)                        AS pct_acumulado
  FROM equip_bairro
 ORDER BY posicao, bairro
""",
        "grafico": {"tipo": "pareto", "rotulo": "bairro",
                    "series": ["equip_ativos"], "linha": "pct_acumulado"},
    },
    {
        "id": "c5",
        "titulo": "Desempenho do fluxo de aprovação por solicitante",
        "pergunta": (
            "Nos últimos N dias, quantas alterações cada usuário solicitou, qual a "
            "taxa de aprovação, quanto tempo a decisão levou e quem revisou?"
        ),
        "nivel": "Avançada",
        "conceitos": ["Auto-relacionamento: JOIN duplo com a mesma tabela (usuarios)",
                      "INNER + LEFT JOIN", "TIMESTAMPDIFF", "GROUP_CONCAT(DISTINCT …)",
                      "INTERVAL parametrizado"],
        "explicacao": (
            "A tabela usuarios entra duas vezes com apelidos diferentes: como "
            "solicitante (INNER JOIN em alteracoes.usuario_id) e como revisor (LEFT "
            "JOIN em alteracoes.approved_by, que é nulo enquanto pendente). "
            "TIMESTAMPDIFF mede o tempo até a decisão e GROUP_CONCAT lista os revisores."
        ),
        "parametros": [
            {"nome": "dias", "rotulo": "Período (últimos N dias)", "tipo": "int",
             "padrao": 90, "min": 1, "max": 3650, "exemplo": 90},
        ],
        "sql": """
SELECT sol.nome                                                  AS solicitante,
       sol.perfil,
       COUNT(*)                                                  AS total,
       SUM(a.status = 'PENDENTE')                                AS pendentes,
       SUM(a.status = 'APROVADO')                                AS aprovadas,
       SUM(a.status = 'REJEITADO')                               AS rejeitadas,
       ROUND(100 * SUM(a.status = 'APROVADO')
                 / NULLIF(SUM(a.status <> 'PENDENTE'), 0), 1)    AS taxa_aprovacao_pct,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, a.created_at, a.approved_at)) / 60, 1)
                                                                 AS horas_medias_decisao,
       GROUP_CONCAT(DISTINCT apr.nome ORDER BY apr.nome SEPARATOR ', ')
                                                                 AS revisores
  FROM alteracoes a
  JOIN usuarios sol      ON sol.id = a.usuario_id
  LEFT JOIN usuarios apr ON apr.id = a.approved_by
 WHERE a.created_at >= UTC_TIMESTAMP() - INTERVAL %(dias)s DAY
 GROUP BY sol.id, sol.nome, sol.perfil
 ORDER BY total DESC, solicitante
""",
        "grafico": {"tipo": "stacked", "rotulo": "solicitante",
                    "series": ["aprovadas", "rejeitadas", "pendentes"]},
    },
    {
        "id": "c6",
        "titulo": "CNES compartilhado por mais de uma unidade",
        "pergunta": (
            "Quais códigos CNES aparecem em mais de um registro de unidade e, "
            "nesses casos, todas estão corretamente marcadas como 'unidade mista'?"
        ),
        "nivel": "Intermediária",
        "conceitos": ["GROUP BY + HAVING COUNT(*) > 1 (detecção de duplicidade)",
                      "GROUP_CONCAT ordenado", "CASE para diagnóstico"],
        "explicacao": (
            "Desde a migration 0001 o CNES não é único (unidades mistas). Esta "
            "consulta de qualidade de dados agrupa por CNES, mantém só os repetidos "
            "(HAVING) e confere se a flag unidade_e_mista está coerente em todos."
        ),
        "parametros": [],
        "sql": """
SELECT u.cnes,
       COUNT(*)                                              AS registros,
       GROUP_CONCAT(u.nome ORDER BY u.nome SEPARATOR ' | ')  AS unidades,
       SUM(u.unidade_e_mista)                                AS marcadas_como_mista,
       CASE WHEN SUM(u.unidade_e_mista) = COUNT(*) THEN 'OK'
            ELSE 'REVISAR: há registro sem a marcação de unidade mista'
       END                                                   AS diagnostico
  FROM unidades u
 GROUP BY u.cnes
HAVING COUNT(*) > 1
 ORDER BY registros DESC, u.cnes
""",
        "grafico": None,
    },
    {
        "id": "c7",
        "titulo": "Equipamentos vinculados a serviço de outra unidade",
        "pergunta": (
            "Existe algum equipamento cujo serviço associado pertence a uma unidade "
            "diferente da unidade do próprio equipamento (inconsistência herdada de "
            "planilhas)?"
        ),
        "nivel": "Avançada",
        "conceitos": ["JOIN em 4 instâncias (unidades usada 2x)",
                      "Operador null-safe <=>", "NOT na condição de junção",
                      "Auditoria de integridade de negócio"],
        "explicacao": (
            "A tabela unidades entra duas vezes: uma para a unidade do equipamento e "
            "outra para a unidade do serviço. O operador <=> compara tratando NULL "
            "como valor, então NOT (a <=> b) encontra divergências inclusive quando "
            "um dos lados é nulo — algo que o '=' comum não detecta."
        ),
        "parametros": [],
        "sql": """
SELECT e.id,
       e.nome   AS equipamento,
       ue.nome  AS unidade_do_equipamento,
       s.nome   AS servico,
       us.nome  AS unidade_do_servico
  FROM equipamentos e
  JOIN servicos      s  ON s.id  = e.servico_id
  LEFT JOIN unidades ue ON ue.id = e.unidade_id
  LEFT JOIN unidades us ON us.id = s.unidade_id
 WHERE NOT (e.unidade_id <=> s.unidade_id)
 ORDER BY e.nome
""",
        "grafico": None,
    },
]

OPCOES_CLASSIFICACAO = [("", "Todas"), ("CRITICA", "Crítica"), ("ATENCAO", "Atenção"),
                        ("ADEQUADA", "Adequada"), ("SEM_EQUIPAMENTO", "Sem equipamento")]
OPCOES_TIPO_MANUT = [("", "Todos"), ("PREVENTIVA", "Preventiva"), ("CORRETIVA", "Corretiva")]
OPCOES_SITUACAO_MANUT = [("", "Todas"), ("ABERTA", "Aberta"), ("CONCLUIDA", "Concluída"),
                         ("CANCELADA", "Cancelada")]

# Views da Etapa 06 (criadas em database/etapa05_objetos.sql). Entram no mesmo
# catálogo: aparecem com filtros/parâmetros e gráfico, como as consultas.
CONSULTAS += [
    {
        "id": "v1",
        "titulo": "View: painel das unidades",
        "pergunta": "Qual a saúde operacional de cada unidade (equipamentos operantes, classificação, "
                    "manutenções abertas e custo)?",
        "nivel": "View",
        "conceitos": ["CREATE VIEW", "Subconsultas escalares", "Chamada de FUNÇÕES do banco",
                      "Filtro por classificação"],
        "explicacao": "vw_painel_unidades consolida, por unidade, contagens por subconsulta e chama as funções "
                      "fn_pct_equip_operantes, fn_classificar_unidade e fn_custo_manutencao. A consulta abaixo "
                      "só filtra a view.",
        "parametros": [
            {"nome": "classificacao", "rotulo": "Classificação", "tipo": "select",
             "opcoes": OPCOES_CLASSIFICACAO, "padrao": "", "exemplo": "CRITICA"},
            {"nome": "situacao", "rotulo": "Situação da unidade", "tipo": "select",
             "opcoes": OPCOES_SITUACAO_UNIDADE, "padrao": "", "exemplo": "ATIVA"},
        ],
        "sql": """
SELECT unidade_id AS id, unidade, tipo, situacao, servicos_ativos, equipamentos_total,
       equipamentos_ativos, pct_operantes, classificacao, manutencoes_abertas, custo_manutencao
  FROM vw_painel_unidades
 WHERE (%(classificacao)s IS NULL OR classificacao = %(classificacao)s)
   AND (%(situacao)s IS NULL OR situacao = %(situacao)s)
 ORDER BY pct_operantes IS NULL, pct_operantes, unidade
""",
        "grafico": {"tipo": "bar", "rotulo": "unidade", "series": ["pct_operantes"]},
    },
    {
        "id": "v2",
        "titulo": "View: manutenções detalhadas",
        "pergunta": "Quais manutenções existem, em qual equipamento/unidade e quanto tempo levaram?",
        "nivel": "View",
        "conceitos": ["CREATE VIEW", "JOIN em 3 tabelas", "DATEDIFF", "Filtros por tipo e situação"],
        "explicacao": "vw_manutencoes_detalhe junta manutenções, equipamentos e unidades e calcula a duração "
                      "em dias (até hoje, se ainda aberta).",
        "parametros": [
            {"nome": "tipo", "rotulo": "Tipo", "tipo": "select", "opcoes": OPCOES_TIPO_MANUT,
             "padrao": "", "exemplo": "CORRETIVA"},
            {"nome": "situacao", "rotulo": "Situação", "tipo": "select", "opcoes": OPCOES_SITUACAO_MANUT,
             "padrao": "", "exemplo": "ABERTA"},
        ],
        "sql": """
SELECT id, unidade, equipamento, tipo, situacao, data_abertura, data_conclusao, dias_duracao, custo
  FROM vw_manutencoes_detalhe
 WHERE (%(tipo)s IS NULL OR tipo = %(tipo)s)
   AND (%(situacao)s IS NULL OR situacao = %(situacao)s)
 ORDER BY data_abertura DESC, id DESC
 LIMIT 200
""",
        "grafico": None,
    },
    {
        "id": "v3",
        "titulo": "View: manutenção por mês",
        "pergunta": "Quantas manutenções e qual custo por mês, separados por tipo?",
        "nivel": "View",
        "conceitos": ["View sobre outra view", "GROUP BY", "SUM/AVG", "Série temporal"],
        "explicacao": "vw_resumo_manutencao_mensal agrega vw_manutencoes_detalhe por mês e tipo.",
        "parametros": [
            {"nome": "tipo", "rotulo": "Tipo", "tipo": "select", "opcoes": OPCOES_TIPO_MANUT,
             "padrao": "", "exemplo": "PREVENTIVA"},
        ],
        "sql": """
SELECT mes, tipo, qtd, concluidas, custo_total, dias_medios
  FROM vw_resumo_manutencao_mensal
 WHERE (%(tipo)s IS NULL OR tipo = %(tipo)s)
 ORDER BY mes, tipo
""",
        "grafico": {"tipo": "bar", "rotulo": "mes", "series": ["qtd"]},
    },
]

CONSULTAS_POR_ID = {c["id"]: c for c in CONSULTAS}


def ler_parametros(consulta, origem):
    """Lê e valida os parâmetros da consulta a partir de um dict (ex."""
    valores = {}
    for p in consulta["parametros"]:
        bruto = origem.get(p["nome"], p["padrao"])
        if p["tipo"] == "int":
            try:
                valor = int(bruto)
            except (TypeError, ValueError):
                valor = p["padrao"]
            valor = max(p.get("min", valor), min(p.get("max", valor), valor))
        else:  # select
            permitidos = {op[0] for op in p["opcoes"]}
            valor = bruto if bruto in permitidos else p["padrao"]
            valor = valor or None
        valores[p["nome"]] = valor
    return valores


def executar(consulta_id, parametros):
    consulta = CONSULTAS_POR_ID[consulta_id]
    return consultar(consulta["sql"], parametros)
