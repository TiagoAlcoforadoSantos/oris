-- ==========================================================
-- ORIS — Migration 0001
-- CNES deixa de ser identificador único; Serviço e Equipamento
-- passam a poder existir sem Unidade associada.
--
-- Stage: "REDESENHO DO MODELO DE DADOS"
-- Motivação: a documentação real do cliente ("Documentação da
-- planilha REDE_SAUDE_RECIFE_GEO") mostra que:
--   1) o mesmo CNES pode corresponder a mais de um registro de
--      Unidade (unidade mista, ex.: Policlínica + Maternidade);
--   2) Serviço e Equipamento não pertencem obrigatoriamente a uma
--      Unidade (ex.: ponto de vacinação em shopping, ambulância do
--      SAMU).
--
-- Esta migration é 100% ADITIVA/NÃO-DESTRUTIVA:
--   - Nenhum DROP DATABASE / DROP TABLE / TRUNCATE.
--   - Nenhuma linha existente é apagada, movida ou reescrita.
--   - Apenas: (a) a constraint UNIQUE de unidades.cnes é removida e
--     substituída por um índice comum (para não perder a performance
--     de busca por CNES); (b) uma coluna nova é adicionada em
--     unidades (unidade_e_mista, com DEFAULT FALSE — todo registro
--     existente recebe automaticamente esse valor, sem precisar de
--     UPDATE manual); (c) as colunas unidade_id de servicos e
--     equipamentos passam de NOT NULL para NULL — isso NÃO afeta
--     nenhuma linha existente, porque toda linha hoje já tem
--     unidade_id preenchido (a constraint só fica mais permissiva
--     para o futuro).
--
-- As foreign keys (fk_servicos_unidade, fk_equipamentos_unidade,
-- fk_equipamentos_servico) NÃO precisam ser recriadas: uma FK do
-- MySQL/InnoDB já aceita valor NULL na coluna por padrão — ela só
-- passa a validar a referência quando um valor não-nulo é gravado.
-- Tornar a coluna nullable é suficiente; a integridade referencial
-- para os registros que já têm (ou vierem a ter) unidade_id
-- preenchido continua sendo garantida pela mesma FK de sempre.
--
-- Pré-requisito: nenhum. Não há dependência de outra migration
-- (este é o schema inicial reorganizado em migrations nesta Stage —
-- até aqui, o projeto usava só database/schema.sql + db.create_all()
-- para SQLite nos testes).
--
-- Como aplicar (MySQL 8 / MariaDB):
--   mysql -u <usuario> -p oris_db < database/migrations/0001_cnes_nao_unico_e_vinculos_opcionais.sql
--
-- Como reverter (ver observação de rollback no final do arquivo).
-- ==========================================================

USE oris_db;

-- ----------------------------------------------------------
-- 1) unidades.cnes: remove a constraint UNIQUE, mantém um índice
--    comum (não-único) para não perder performance de busca/filtro
--    por CNES.
-- ----------------------------------------------------------
ALTER TABLE unidades
    DROP INDEX uk_unidades_cnes,
    ADD INDEX ix_unidades_cnes (cnes);

-- ----------------------------------------------------------
-- 2) unidades.unidade_e_mista: nova coluna, aditiva. DEFAULT FALSE
--    garante que todo registro já existente passa a ter o valor
--    correto automaticamente, sem exigir UPDATE manual nem deixar
--    nenhuma linha com valor nulo/inconsistente.
-- ----------------------------------------------------------
ALTER TABLE unidades
    ADD COLUMN unidade_e_mista BOOLEAN NOT NULL DEFAULT FALSE AFTER cnes;

-- ----------------------------------------------------------
-- 3) servicos.unidade_id: NOT NULL -> NULL. Todas as linhas
--    existentes já têm um valor preenchido (a constraint antiga
--    exigia isso), então esta alteração não altera nenhum dado —
--    só passa a permitir NULL em cadastros futuros.
-- ----------------------------------------------------------
ALTER TABLE servicos
    MODIFY COLUMN unidade_id INT NULL;

-- ----------------------------------------------------------
-- 4) equipamentos.unidade_id: mesma lógica do item 3.
-- ----------------------------------------------------------
ALTER TABLE equipamentos
    MODIFY COLUMN unidade_id INT NULL;

-- ==========================================================
-- ROLLBACK (documentado, não executado automaticamente):
--
-- Reverter esta migration só é seguro se, no momento do rollback,
-- NÃO existir nenhuma linha que dependa do novo contrato, ou seja:
--   - nenhum servico/equipamento com unidade_id NULL;
--   - nenhum CNES duplicado entre unidades.
-- Caso existam, reverter exigiria decidir o que fazer com esses
-- registros primeiro (ex.: atribuir uma unidade, ou remover a
-- duplicidade) — isso é uma decisão de negócio, não uma operação
-- puramente técnica, e por isso não faz parte deste script.
--
-- Script de rollback (rodar só depois de garantir o acima):
--
-- ALTER TABLE equipamentos MODIFY COLUMN unidade_id INT NOT NULL;
-- ALTER TABLE servicos MODIFY COLUMN unidade_id INT NOT NULL;
-- ALTER TABLE unidades DROP COLUMN unidade_e_mista;
-- ALTER TABLE unidades DROP INDEX ix_unidades_cnes, ADD UNIQUE INDEX uk_unidades_cnes (cnes);
-- ==========================================================
