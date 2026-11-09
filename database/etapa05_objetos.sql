-- ORIS - Etapa 05/06 - Funcoes, procedimentos, triggers e views (MySQL 8.0+)
--
-- Cada comando termina com uma linha contendo apenas "$$" (equivale ao
-- DELIMITER $$ do cliente mysql). Quem le este arquivo:
--   * database/aplicar_migracoes.py  -> cria/recria os objetos (idempotente:
--     usa DROP ... IF EXISTS antes de cada CREATE);
--   * app/bd/objetos.py              -> mostra o codigo na tela /bd/rotinas.
--
-- Tabela usada: manutencoes (criada por aplicar_migracoes.py / schema.sql).
-- Os triggers de auditoria gravam em auditorias; o usuario responsavel vem
-- da variavel de sessao @oris_usuario_id (definida pela aplicacao antes de
-- cada escrita). Sem ela, usam o menor id de usuarios.

-- =====================================================================
-- FUNCOES
-- =====================================================================

DROP FUNCTION IF EXISTS fn_pct_equip_operantes $$

CREATE FUNCTION fn_pct_equip_operantes(p_unidade_id INT)
RETURNS DECIMAL(5,1)
READS SQL DATA
BEGIN
    -- % de equipamentos ATIVOS da unidade; NULL se ela nao tem equipamentos.
    DECLARE v_total INT DEFAULT 0;
    DECLARE v_ativos INT DEFAULT 0;

    SELECT COUNT(*), COALESCE(SUM(situacao = 'ATIVO'), 0)
      INTO v_total, v_ativos
      FROM equipamentos
     WHERE unidade_id = p_unidade_id;

    IF v_total = 0 THEN
        RETURN NULL;
    END IF;
    RETURN ROUND(100 * v_ativos / v_total, 1);
END $$

DROP FUNCTION IF EXISTS fn_classificar_unidade $$

CREATE FUNCTION fn_classificar_unidade(p_unidade_id INT)
RETURNS VARCHAR(20)
READS SQL DATA
BEGIN
    -- Classifica a unidade pelo % de equipamentos operantes (usa a funcao acima).
    DECLARE v_pct DECIMAL(5,1);

    SET v_pct = fn_pct_equip_operantes(p_unidade_id);
    IF v_pct IS NULL THEN
        RETURN 'SEM_EQUIPAMENTO';
    ELSEIF v_pct < 50 THEN
        RETURN 'CRITICA';
    ELSEIF v_pct < 80 THEN
        RETURN 'ATENCAO';
    END IF;
    RETURN 'ADEQUADA';
END $$

DROP FUNCTION IF EXISTS fn_custo_manutencao $$

CREATE FUNCTION fn_custo_manutencao(p_unidade_id INT, p_ano INT)
RETURNS DECIMAL(12,2)
READS SQL DATA
BEGIN
    -- Soma o custo das manutencoes CONCLUIDAS dos equipamentos da unidade.
    -- p_ano NULL = todos os anos.
    DECLARE v_total DECIMAL(12,2);

    SELECT COALESCE(SUM(m.custo), 0)
      INTO v_total
      FROM manutencoes m
      JOIN equipamentos e ON e.id = m.equipamento_id
     WHERE e.unidade_id = p_unidade_id
       AND m.situacao = 'CONCLUIDA'
       AND (p_ano IS NULL OR YEAR(m.data_conclusao) = p_ano);
    RETURN v_total;
END $$

-- =====================================================================
-- PROCEDIMENTOS
-- =====================================================================

DROP PROCEDURE IF EXISTS sp_abrir_manutencao $$

CREATE PROCEDURE sp_abrir_manutencao(
    IN  p_equipamento_id INT,
    IN  p_tipo           VARCHAR(20),
    IN  p_descricao      VARCHAR(255),
    OUT p_manutencao_id  INT)
BEGIN
    -- Abre uma manutencao. Os triggers trg_manutencoes_bi/ai validam o
    -- registro e, se for CORRETIVA, tiram o equipamento de operacao.
    IF NOT EXISTS (SELECT 1 FROM equipamentos WHERE id = p_equipamento_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Equipamento inexistente.';
    END IF;
    IF p_tipo NOT IN ('PREVENTIVA', 'CORRETIVA') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Tipo deve ser PREVENTIVA ou CORRETIVA.';
    END IF;

    INSERT INTO manutencoes
        (equipamento_id, tipo, descricao, data_abertura, custo, situacao, created_at, updated_at)
    VALUES
        (p_equipamento_id, p_tipo, p_descricao, CURDATE(), 0, 'ABERTA', UTC_TIMESTAMP(), UTC_TIMESTAMP());

    SET p_manutencao_id = LAST_INSERT_ID();
END $$

DROP PROCEDURE IF EXISTS sp_concluir_manutencao $$

CREATE PROCEDURE sp_concluir_manutencao(IN p_manutencao_id INT, IN p_custo DECIMAL(10,2))
BEGIN
    -- Conclui uma manutencao ABERTA e registra o custo. O trigger
    -- trg_manutencoes_au devolve o equipamento a operacao (se nao houver
    -- outra corretiva aberta).
    DECLARE v_situacao VARCHAR(20);

    SELECT situacao INTO v_situacao FROM manutencoes WHERE id = p_manutencao_id FOR UPDATE;
    IF v_situacao IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Manutencao inexistente.';
    ELSEIF v_situacao <> 'ABERTA' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Somente manutencoes ABERTAS podem ser concluidas.';
    END IF;

    UPDATE manutencoes
       SET situacao = 'CONCLUIDA', custo = p_custo,
           data_conclusao = CURDATE(), updated_at = UTC_TIMESTAMP()
     WHERE id = p_manutencao_id;
END $$

DROP PROCEDURE IF EXISTS sp_resumo_unidade $$

CREATE PROCEDURE sp_resumo_unidade(IN p_unidade_id INT)
BEGIN
    -- Devolve um conjunto de resultados com o resumo da unidade (usa as 3 funcoes).
    IF NOT EXISTS (SELECT 1 FROM unidades WHERE id = p_unidade_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Unidade inexistente.';
    END IF;

    SELECT u.id, u.nome AS unidade, u.situacao,
           (SELECT COUNT(*) FROM servicos s
             WHERE s.unidade_id = u.id AND s.situacao = 'ATIVO')      AS servicos_ativos,
           (SELECT COUNT(*) FROM equipamentos e
             WHERE e.unidade_id = u.id)                               AS equipamentos,
           fn_pct_equip_operantes(u.id)                               AS pct_operantes,
           fn_classificar_unidade(u.id)                               AS classificacao,
           fn_custo_manutencao(u.id, NULL)                            AS custo_manutencao
      FROM unidades u
     WHERE u.id = p_unidade_id;
END $$

DROP PROCEDURE IF EXISTS sp_inativar_unidade $$

CREATE PROCEDURE sp_inativar_unidade(IN p_unidade_id INT)
BEGIN
    -- Inativa a unidade e, em cascata, seus servicos e equipamentos.
    -- Os triggers de auditoria registram cada mudanca de situacao.
    DECLARE v_servicos INT DEFAULT 0;
    DECLARE v_equipamentos INT DEFAULT 0;

    IF NOT EXISTS (SELECT 1 FROM unidades WHERE id = p_unidade_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Unidade inexistente.';
    END IF;

    UPDATE unidades SET situacao = 'INATIVA', updated_at = UTC_TIMESTAMP() WHERE id = p_unidade_id;

    UPDATE servicos SET situacao = 'INATIVO', updated_at = UTC_TIMESTAMP()
     WHERE unidade_id = p_unidade_id AND situacao <> 'INATIVO';
    SET v_servicos = ROW_COUNT();

    UPDATE equipamentos SET situacao = 'INATIVO', updated_at = UTC_TIMESTAMP()
     WHERE unidade_id = p_unidade_id AND situacao <> 'INATIVO';
    SET v_equipamentos = ROW_COUNT();

    SELECT p_unidade_id AS unidade_id, v_servicos AS servicos_inativados,
           v_equipamentos AS equipamentos_inativados;
END $$

-- =====================================================================
-- TRIGGERS
-- =====================================================================

DROP TRIGGER IF EXISTS trg_manutencoes_bi $$

CREATE TRIGGER trg_manutencoes_bi BEFORE INSERT ON manutencoes
FOR EACH ROW
BEGIN
    -- Validacao e valores padrao antes de gravar.
    IF NEW.custo < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'O custo da manutencao nao pode ser negativo.';
    END IF;
    IF NEW.data_abertura IS NULL THEN
        SET NEW.data_abertura = CURDATE();
    END IF;
    IF NEW.data_conclusao IS NOT NULL AND NEW.data_conclusao < NEW.data_abertura THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A conclusao nao pode ser anterior a abertura.';
    END IF;
    IF NEW.situacao = 'CONCLUIDA' AND NEW.data_conclusao IS NULL THEN
        SET NEW.data_conclusao = CURDATE();
    END IF;
END $$

DROP TRIGGER IF EXISTS trg_manutencoes_bu $$

CREATE TRIGGER trg_manutencoes_bu BEFORE UPDATE ON manutencoes
FOR EACH ROW
BEGIN
    -- Regras de consistencia nas alteracoes.
    IF NEW.custo < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'O custo da manutencao nao pode ser negativo.';
    END IF;
    IF NEW.data_conclusao IS NOT NULL AND NEW.data_conclusao < NEW.data_abertura THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A conclusao nao pode ser anterior a abertura.';
    END IF;
    IF NEW.situacao = 'CONCLUIDA' AND NEW.data_conclusao IS NULL THEN
        SET NEW.data_conclusao = CURDATE();
    END IF;
    IF NEW.situacao = 'ABERTA' THEN
        SET NEW.data_conclusao = NULL;
    END IF;
END $$

DROP TRIGGER IF EXISTS trg_manutencoes_ai $$

CREATE TRIGGER trg_manutencoes_ai AFTER INSERT ON manutencoes
FOR EACH ROW
BEGIN
    -- Manutencao CORRETIVA aberta tira o equipamento de operacao.
    IF NEW.tipo = 'CORRETIVA' AND NEW.situacao = 'ABERTA' THEN
        UPDATE equipamentos
           SET situacao = 'INATIVO', updated_at = UTC_TIMESTAMP()
         WHERE id = NEW.equipamento_id AND situacao = 'ATIVO';
    END IF;
END $$

DROP TRIGGER IF EXISTS trg_manutencoes_au $$

CREATE TRIGGER trg_manutencoes_au AFTER UPDATE ON manutencoes
FOR EACH ROW
BEGIN
    -- Ao encerrar uma CORRETIVA (concluida/cancelada), devolve o equipamento
    -- a operacao, desde que nao reste outra corretiva aberta nele.
    IF OLD.situacao = 'ABERTA' AND NEW.situacao IN ('CONCLUIDA', 'CANCELADA')
       AND NEW.tipo = 'CORRETIVA'
       AND NOT EXISTS (SELECT 1 FROM manutencoes
                        WHERE equipamento_id = NEW.equipamento_id
                          AND tipo = 'CORRETIVA' AND situacao = 'ABERTA') THEN
        UPDATE equipamentos
           SET situacao = 'ATIVO', updated_at = UTC_TIMESTAMP()
         WHERE id = NEW.equipamento_id AND situacao = 'INATIVO';
    END IF;
END $$

DROP TRIGGER IF EXISTS trg_equipamentos_au $$

CREATE TRIGGER trg_equipamentos_au AFTER UPDATE ON equipamentos
FOR EACH ROW
BEGIN
    -- Trilha automatica: toda mudanca de situacao de equipamento vira linha em auditorias.
    DECLARE v_usuario INT;
    IF NOT (OLD.situacao <=> NEW.situacao) THEN
        SET v_usuario = COALESCE(@oris_usuario_id, (SELECT MIN(id) FROM usuarios));
        IF v_usuario IS NOT NULL THEN
            INSERT INTO auditorias
                (usuario_id, acao, tabela, registro_id, descricao, valor_anterior, valor_novo, data_hora)
            VALUES
                (v_usuario, 'TRG_EQUIPAMENTO_SITUACAO', 'equipamentos', NEW.id,
                 CONCAT('Trigger: situacao do equipamento "', NEW.nome, '" mudou'),
                 OLD.situacao, NEW.situacao, UTC_TIMESTAMP());
        END IF;
    END IF;
END $$

DROP TRIGGER IF EXISTS trg_unidades_au $$

CREATE TRIGGER trg_unidades_au AFTER UPDATE ON unidades
FOR EACH ROW
BEGIN
    -- Trilha automatica: toda mudanca de situacao de unidade vira linha em auditorias.
    DECLARE v_usuario INT;
    IF NOT (OLD.situacao <=> NEW.situacao) THEN
        SET v_usuario = COALESCE(@oris_usuario_id, (SELECT MIN(id) FROM usuarios));
        IF v_usuario IS NOT NULL THEN
            INSERT INTO auditorias
                (usuario_id, acao, tabela, registro_id, descricao, valor_anterior, valor_novo, data_hora)
            VALUES
                (v_usuario, 'TRG_UNIDADE_SITUACAO', 'unidades', NEW.id,
                 CONCAT('Trigger: situacao da unidade "', NEW.nome, '" mudou'),
                 OLD.situacao, NEW.situacao, UTC_TIMESTAMP());
        END IF;
    END IF;
END $$

-- =====================================================================
-- VIEWS
-- =====================================================================

CREATE OR REPLACE VIEW vw_painel_unidades AS
-- Autossuficiente de proposito: nao chama as funcoes (criar funcoes/triggers
-- exige privilegio extra do administrador; as views funcionam sem isso).
-- A logica equivale a fn_pct_equip_operantes / fn_classificar_unidade /
-- fn_custo_manutencao.
SELECT t.unidade_id, t.unidade, t.tipo, t.bairro, t.situacao, t.servicos_ativos,
       t.equipamentos_total, t.equipamentos_ativos, t.pct_operantes,
       CASE WHEN t.pct_operantes IS NULL THEN 'SEM_EQUIPAMENTO'
            WHEN t.pct_operantes < 50    THEN 'CRITICA'
            WHEN t.pct_operantes < 80    THEN 'ATENCAO'
            ELSE 'ADEQUADA' END                                       AS classificacao,
       t.manutencoes_abertas, t.custo_manutencao
  FROM (
    SELECT u.id AS unidade_id,
           u.nome AS unidade,
           COALESCE(NULLIF(TRIM(u.tipo), ''), '(nao informado)') AS tipo,
           u.bairro,
           u.situacao,
           (SELECT COUNT(*) FROM servicos s
             WHERE s.unidade_id = u.id AND s.situacao = 'ATIVO')          AS servicos_ativos,
           (SELECT COUNT(*) FROM equipamentos e WHERE e.unidade_id = u.id) AS equipamentos_total,
           (SELECT COUNT(*) FROM equipamentos e
             WHERE e.unidade_id = u.id AND e.situacao = 'ATIVO')          AS equipamentos_ativos,
           (SELECT ROUND(100 * SUM(e.situacao = 'ATIVO') / COUNT(*), 1)
              FROM equipamentos e WHERE e.unidade_id = u.id)              AS pct_operantes,
           (SELECT COUNT(*) FROM manutencoes m
              JOIN equipamentos e ON e.id = m.equipamento_id
             WHERE e.unidade_id = u.id AND m.situacao = 'ABERTA')         AS manutencoes_abertas,
           (SELECT COALESCE(SUM(m.custo), 0) FROM manutencoes m
              JOIN equipamentos e ON e.id = m.equipamento_id
             WHERE e.unidade_id = u.id AND m.situacao = 'CONCLUIDA')      AS custo_manutencao
      FROM unidades u
  ) t $$

CREATE OR REPLACE VIEW vw_manutencoes_detalhe AS
SELECT m.id,
       m.tipo,
       m.situacao,
       m.descricao,
       m.data_abertura,
       m.data_conclusao,
       m.custo,
       DATE_FORMAT(m.data_abertura, '%Y-%m')                          AS mes,
       DATEDIFF(COALESCE(m.data_conclusao, CURDATE()), m.data_abertura) AS dias_duracao,
       e.id   AS equipamento_id,
       e.nome AS equipamento,
       e.tipo AS tipo_equipamento,
       u.id   AS unidade_id,
       u.nome AS unidade
  FROM manutencoes m
  JOIN equipamentos e ON e.id = m.equipamento_id
  LEFT JOIN unidades u ON u.id = e.unidade_id $$

CREATE OR REPLACE VIEW vw_resumo_manutencao_mensal AS
SELECT mes,
       tipo,
       COUNT(*)                         AS qtd,
       SUM(situacao = 'CONCLUIDA')      AS concluidas,
       ROUND(SUM(custo), 2)             AS custo_total,
       ROUND(AVG(dias_duracao), 1)      AS dias_medios
  FROM vw_manutencoes_detalhe
 GROUP BY mes, tipo $$
