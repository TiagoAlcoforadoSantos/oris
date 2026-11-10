-- Justificativas de situacao para unidades, servicos e equipamentos,
-- e motivo separado para a decisao de rejeicao.
USE oris_db;

ALTER TABLE unidades
    ADD COLUMN descricao_situacao TEXT NULL;

ALTER TABLE servicos
    MODIFY COLUMN situacao ENUM('ATIVO', 'INATIVO', 'MANUTENCAO') NOT NULL DEFAULT 'ATIVO',
    ADD COLUMN descricao_situacao TEXT NULL;

ALTER TABLE equipamentos
    MODIFY COLUMN situacao ENUM('ATIVO', 'INATIVO', 'MANUTENCAO') NOT NULL DEFAULT 'ATIVO',
    ADD COLUMN descricao_situacao TEXT NULL;

ALTER TABLE alteracoes
    ADD COLUMN motivo_rejeicao TEXT NULL;

-- ROLLBACK (manual):
-- ALTER TABLE alteracoes DROP COLUMN motivo_rejeicao;
-- ALTER TABLE equipamentos MODIFY COLUMN situacao ENUM('ATIVO', 'INATIVO') NOT NULL DEFAULT 'ATIVO',
--     DROP COLUMN descricao_situacao;
-- ALTER TABLE servicos MODIFY COLUMN situacao ENUM('ATIVO', 'INATIVO') NOT NULL DEFAULT 'ATIVO',
--     DROP COLUMN descricao_situacao;
-- ALTER TABLE unidades DROP COLUMN descricao_situacao;
