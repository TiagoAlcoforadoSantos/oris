-- Migracao 0002 (Fase 14 - Requisito 3): origem do usuario + grupos.
-- Aditiva: nao remove nem altera dados existentes.
-- Usuarios existentes ficam com origem = 'LOCAL'.

ALTER TABLE usuarios
    ADD COLUMN origem ENUM('LOCAL', 'LDAP', 'OIDC') NOT NULL DEFAULT 'LOCAL' AFTER ativo,
    ADD COLUMN identificador_externo VARCHAR(255) NULL AFTER origem,
    ADD KEY ix_usuarios_identificador_externo (identificador_externo);

CREATE TABLE IF NOT EXISTS grupos (
    id INT NOT NULL AUTO_INCREMENT,
    nome VARCHAR(150) NOT NULL,
    origem ENUM('LOCAL', 'LDAP', 'OIDC') NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_grupos_nome (nome),
    UNIQUE KEY uk_grupos_nome_origem (nome, origem)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuario_grupos (
    usuario_id INT NOT NULL,
    grupo_id INT NOT NULL,
    PRIMARY KEY (usuario_id, grupo_id),
    CONSTRAINT fk_usuario_grupos_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE,
    CONSTRAINT fk_usuario_grupos_grupo FOREIGN KEY (grupo_id) REFERENCES grupos (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ROLLBACK (manual):
--   DROP TABLE usuario_grupos;
--   DROP TABLE grupos;
--   ALTER TABLE usuarios DROP KEY ix_usuarios_identificador_externo,
--       DROP COLUMN identificador_externo, DROP COLUMN origem;
