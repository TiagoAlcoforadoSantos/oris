-- ==========================================================
-- ORIS — Plataforma de Governança da Rede de Saúde Bucal
-- Schema do banco de dados MySQL — FASE 2
--
-- Este arquivo reflete os models SQLAlchemy definidos em
-- app/models/. Ele pode ser usado para criar o banco manualmente,
-- mas o método recomendado (usado em desenvolvimento/testes) é
-- deixar o SQLAlchemy criar as tabelas a partir dos models
-- (db.create_all()), garantindo que código e schema nunca fiquem
-- dessincronizados.
--
-- Nesta fase NÃO existem: login funcional, RBAC, fluxo de aprovação
-- ou dashboard — apenas a estrutura de dados.
-- ==========================================================

CREATE DATABASE IF NOT EXISTS oris_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE oris_db;

-- ----------------------------------------------------------
-- Tabela: usuarios
-- Usuários do sistema. O campo senha_hash armazenará um hash
-- bcrypt a partir da FASE 3 — nesta fase o campo só existe.
-- O campo perfil já define os 4 perfis previstos; as regras de
-- permissão de cada perfil (RBAC) serão implementadas na FASE 4.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id INT NOT NULL AUTO_INCREMENT,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    perfil ENUM('ADMINISTRADOR', 'GESTAO_INFORMACAO', 'RESPONSAVEL_SAUDE_BUCAL', 'GESTOR') NOT NULL,
    ativo BOOL NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_usuarios_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- Tabela: unidades
-- Unidade de Saúde Bucal — entidade central do MVP.
-- O CNES é único para evitar cadastro duplicado da mesma unidade.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS unidades (
    id INT NOT NULL AUTO_INCREMENT,
    nome VARCHAR(200) NOT NULL,
    cnes VARCHAR(20) NOT NULL,
    tipo VARCHAR(100) NULL,
    endereco VARCHAR(255) NULL,
    bairro VARCHAR(100) NULL,
    cidade VARCHAR(100) NULL,
    uf VARCHAR(2) NULL,
    situacao ENUM('ATIVA', 'INATIVA', 'MANUTENCAO') NOT NULL DEFAULT 'ATIVA',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_unidades_cnes (cnes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- Tabela: servicos
-- Um Serviço pertence a uma única Unidade.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS servicos (
    id INT NOT NULL AUTO_INCREMENT,
    unidade_id INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    situacao ENUM('ATIVO', 'INATIVO') NOT NULL DEFAULT 'ATIVO',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_servicos_unidade_id (unidade_id),
    CONSTRAINT fk_servicos_unidade
        FOREIGN KEY (unidade_id) REFERENCES unidades (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- Tabela: equipamentos
-- Sempre pertence a uma Unidade; associação a um Serviço é
-- opcional (servico_id pode ser NULL).
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipamentos (
    id INT NOT NULL AUTO_INCREMENT,
    unidade_id INT NOT NULL,
    servico_id INT NULL,
    nome VARCHAR(150) NOT NULL,
    tipo VARCHAR(100) NULL,
    situacao ENUM('ATIVO', 'INATIVO') NOT NULL DEFAULT 'ATIVO',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_equipamentos_unidade_id (unidade_id),
    KEY ix_equipamentos_servico_id (servico_id),
    CONSTRAINT fk_equipamentos_unidade
        FOREIGN KEY (unidade_id) REFERENCES unidades (id),
    CONSTRAINT fk_equipamentos_servico
        FOREIGN KEY (servico_id) REFERENCES servicos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- Tabela: alteracoes
-- Fluxo de aprovação (FASE 7). `tabela` + `registro_id` referenciam
-- de forma genérica o registro afetado (ex.: tabela='unidades',
-- registro_id=5), por isso registro_id não é uma foreign key
-- tradicional. `registro_id` é NULL enquanto uma operação CRIAR
-- ainda está PENDENTE (o registro ainda não existe).
-- `operacao` e `dados_novos` foram adicionados na FASE 7: sem eles
-- não haveria como saber, no momento da aprovação, o que aplicar
-- (criar/editar/mudar situação) nem com quais valores — ver
-- app/models/alteracao.py para a justificativa completa.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS alteracoes (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    tabela VARCHAR(100) NOT NULL,
    registro_id INT NULL,
    operacao ENUM('CRIAR', 'EDITAR', 'ALTERAR_SITUACAO') NOT NULL,
    dados_novos TEXT NULL,
    descricao TEXT NULL,
    status ENUM('PENDENTE', 'APROVADO', 'REJEITADO') NOT NULL DEFAULT 'PENDENTE',
    created_at DATETIME NOT NULL,
    approved_by INT NULL,
    approved_at DATETIME NULL,
    PRIMARY KEY (id),
    KEY ix_alteracoes_usuario_id (usuario_id),
    KEY ix_alteracoes_approved_by (approved_by),
    CONSTRAINT fk_alteracoes_usuario_criador
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
    CONSTRAINT fk_alteracoes_usuario_aprovador
        FOREIGN KEY (approved_by) REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- Tabela: auditorias
-- Trilha de auditoria (audit log), funcional a partir da FASE 8.
-- `valor_anterior`/`valor_novo` guardam (em JSON) só os campos que
-- realmente mudaram numa edição/alteração de situação — nunca senha
-- ou senha_hash.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS auditorias (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    acao VARCHAR(100) NOT NULL,
    tabela VARCHAR(100) NULL,
    registro_id INT NULL,
    descricao TEXT NULL,
    valor_anterior TEXT NULL,
    valor_novo TEXT NULL,
    data_hora DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_auditorias_usuario_id (usuario_id),
    CONSTRAINT fk_auditorias_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
