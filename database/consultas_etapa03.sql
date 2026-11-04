-- ORIS - Plataforma de Governança da Rede de Saúde Bucal
-- ETAPA 03 - SQL das consultas (e dos comandos de manipulação)
--
-- SGBD: MySQL 8.0+ (compatível com MariaDB 10.3+)
-- Arquivo GERADO por scripts/gerar_sql_consultas.py a partir do
-- código da aplicação (app/bd/consultas.py e app/bd/dao_*.py):
-- é exatamente o SQL que o backend envia ao banco via PyMySQL
-- (DB-API 2.0, equivalente ao JDBC). Na aplicação, os valores vão
-- como parâmetros do driver (%s / %(nome)s ≈ '?' do PreparedStatement);
-- aqui foram trocados por valores de exemplo para execução direta.
--
-- Para popular o banco com dados de demonstração antes de rodar:
--   mysql -u <usuario> -p < database/seed_etapa03.sql

USE oris_db;

-- ##################################################################
-- PARTE 1 - CONSULTAS DA ETAPA 03 (7 consultas)
-- ##################################################################

-- C1 - Capacidade instalada por unidade
-- Pergunta:
-- Quantos serviços e equipamentos ativos cada unidade possui, e
-- qual o percentual do seu parque de equipamentos que está
-- operante?
--
-- Nível: Intermediária
-- Recursos de SQL:
--   - JOIN (LEFT JOIN em 3 tabelas)
--   - GROUP BY
--   - COUNT(DISTINCT CASE …) - agregação condicional
--   - NULLIF para evitar divisão por zero
--   - Filtro parametrizado
--
-- Parâmetros (valor de exemplo usado abaixo):
--   - situacao = 'ATIVA'  (Situação da unidade)
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
 WHERE ('ATIVA' IS NULL OR u.situacao = 'ATIVA')
 GROUP BY u.id, u.nome, u.bairro, u.situacao
 ORDER BY equip_ativos DESC, u.nome;

-- C2 - Cobertura da rede por bairro
-- Pergunta:
-- Em cada bairro, quantas unidades existem, quantas estão ativas e
-- qual a média de equipamentos ativos por unidade?
--
-- Nível: Intermediária/Avançada
-- Recursos de SQL:
--   - Tabela derivada (subconsulta no FROM)
--   - LEFT JOIN
--   - SUM de expressão booleana
--   - AVG
--   - GROUP BY + HAVING parametrizado
--   - COALESCE
--
-- Parâmetros (valor de exemplo usado abaixo):
--   - minimo = 2  (Mínimo de unidades no bairro)
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
HAVING COUNT(*) >= 2
 ORDER BY unidades DESC, bairro;

-- C3 - Unidades ativas sem nenhum equipamento operante
-- Pergunta:
-- Quais unidades estão ATIVAS mas não têm nenhum equipamento ativo
-- (lacuna de capacidade que exige ação da gestão)?
--
-- Nível: Avançada
-- Recursos de SQL:
--   - NOT EXISTS (anti-junção)
--   - Subconsulta correlacionada escalar
--   - DATEDIFF
--   - UTC_TIMESTAMP()
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
 ORDER BY servicos_ativos DESC, u.nome;

-- C4 - Ranking de bairros por equipamentos (curva de Pareto)
-- Pergunta:
-- Quais bairros concentram os equipamentos ativos da rede, qual a
-- participação de cada um e a participação acumulada?
--
-- Nível: Avançada
-- Recursos de SQL:
--   - CTE (WITH)
--   - INNER JOIN
--   - RANK() OVER
--   - SUM() OVER () - total sem GROUP BY
--   - SUM() OVER (ORDER BY … ROWS …) - soma acumulada
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
 ORDER BY posicao, bairro;

-- C5 - Desempenho do fluxo de aprovação por solicitante
-- Pergunta:
-- Nos últimos N dias, quantas alterações cada usuário solicitou,
-- qual a taxa de aprovação, quanto tempo a decisão levou e quem
-- revisou?
--
-- Nível: Avançada
-- Recursos de SQL:
--   - Auto-relacionamento: JOIN duplo com a mesma tabela (usuarios)
--   - INNER + LEFT JOIN
--   - TIMESTAMPDIFF
--   - GROUP_CONCAT(DISTINCT …)
--   - INTERVAL parametrizado
--
-- Parâmetros (valor de exemplo usado abaixo):
--   - dias = 90  (Período (últimos N dias))
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
 WHERE a.created_at >= UTC_TIMESTAMP() - INTERVAL 90 DAY
 GROUP BY sol.id, sol.nome, sol.perfil
 ORDER BY total DESC, solicitante;

-- C6 - CNES compartilhado por mais de uma unidade
-- Pergunta:
-- Quais códigos CNES aparecem em mais de um registro de unidade e,
-- nesses casos, todas estão corretamente marcadas como 'unidade
-- mista'?
--
-- Nível: Intermediária
-- Recursos de SQL:
--   - GROUP BY + HAVING COUNT(*) > 1 (detecção de duplicidade)
--   - GROUP_CONCAT ordenado
--   - CASE para diagnóstico
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
 ORDER BY registros DESC, u.cnes;

-- C7 - Equipamentos vinculados a serviço de outra unidade
-- Pergunta:
-- Existe algum equipamento cujo serviço associado pertence a uma
-- unidade diferente da unidade do próprio equipamento
-- (inconsistência herdada de planilhas)?
--
-- Nível: Avançada
-- Recursos de SQL:
--   - JOIN em 4 instâncias (unidades usada 2x)
--   - Operador null-safe <=>
--   - NOT na condição de junção
--   - Auditoria de integridade de negócio
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
 ORDER BY e.nome;

-- ##################################################################
-- PARTE 2 - COMANDOS DE INSERÇÃO / ALTERAÇÃO / EXCLUSÃO
-- (executados pela interface, telas /bd/unidades, /bd/servicos,
--  /bd/equipamentos). Valores ilustrativos. Toda escrita grava também
-- um registro em `auditorias` NA MESMA TRANSAÇÃO.
-- ##################################################################

START TRANSACTION;

-- UNIDADES - INSERT
INSERT INTO unidades
        (nome, cnes, unidade_e_mista, tipo, endereco, bairro, cidade, uf,
         situacao, created_at, updated_at)
    VALUES
        ('USF Exemplo Etapa 03', '9199999', 0, 'Unidade de Saúde da Família', 'Rua Exemplo 100', 'Várzea', 'Recife', 'PE', 'ATIVA', UTC_TIMESTAMP(), UTC_TIMESTAMP());

SET @id_unidade = LAST_INSERT_ID();  -- ≈ cursor.lastrowid

-- UNIDADES - UPDATE
UPDATE unidades
       SET nome = 'USF Exemplo Etapa 03', cnes = '9199999', unidade_e_mista = 0, tipo = 'Unidade de Saúde da Família',
           endereco = 'Rua Exemplo 100', bairro = 'Várzea', cidade = 'Recife', uf = 'PE',
           situacao = 'MANUTENCAO', updated_at = UTC_TIMESTAMP()
     WHERE id = @id_unidade;

-- SERVIÇOS - INSERT
INSERT INTO servicos (nome, unidade_id, situacao, created_at, updated_at)
    VALUES ('Atenção Básica em Saúde Bucal', @id_unidade, 'ATIVO', UTC_TIMESTAMP(), UTC_TIMESTAMP());

SET @id_servico = LAST_INSERT_ID();  -- ≈ cursor.lastrowid

-- SERVIÇOS - UPDATE
UPDATE servicos
       SET nome = 'Atenção Básica em Saúde Bucal', unidade_id = @id_unidade, situacao = 'INATIVO', updated_at = UTC_TIMESTAMP()
     WHERE id = @id_servico;

-- EQUIPAMENTOS - INSERT
INSERT INTO equipamentos
        (nome, tipo, unidade_id, servico_id, situacao, created_at, updated_at)
    VALUES ('Autoclave 21 L #1', 'Autoclave', @id_unidade, @id_servico, 'ATIVO', UTC_TIMESTAMP(), UTC_TIMESTAMP());

SET @id_equip = LAST_INSERT_ID();  -- ≈ cursor.lastrowid

-- EQUIPAMENTOS - UPDATE
UPDATE equipamentos
       SET nome = 'Autoclave 21 L #1', tipo = 'Autoclave', unidade_id = @id_unidade, servico_id = @id_servico,
           situacao = 'INATIVO', updated_at = UTC_TIMESTAMP()
     WHERE id = @id_equip;

-- EQUIPAMENTOS - DELETE
DELETE FROM equipamentos WHERE id = @id_equip;

-- SERVIÇOS - DELETE (só sem equipamentos vinculados)
DELETE FROM servicos WHERE id = @id_servico;

-- UNIDADES - DELETE (só sem serviços/equipamentos vinculados)
DELETE FROM unidades WHERE id = @id_unidade;

-- Registro de auditoria gravado junto com cada comando acima:
-- INSERT INTO auditorias (usuario_id, acao, tabela, registro_id, descricao,
--                         valor_anterior, valor_novo, data_hora)
-- VALUES (%s, 'BD_INSERIR' | 'BD_ALTERAR' | 'BD_EXCLUIR', %s, %s, %s, %s, %s, UTC_TIMESTAMP());

-- Exemplo didático: desfaz tudo o que foi feito na Parte 2.
ROLLBACK;
