CREATE DATABASE IF NOT EXISTS `banco_pystock`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `banco_pystock`;

CREATE TABLE IF NOT EXISTS `login` (
  `id`        INT           NOT NULL AUTO_INCREMENT,
  `usuario`   VARCHAR(100)  NOT NULL UNIQUE,
  `senha`     VARCHAR(64)   NOT NULL COMMENT 'SHA-256 hex',
  `nivel`     ENUM('admin','colaborador') NOT NULL DEFAULT 'colaborador',
  `nome`      VARCHAR(150)  NOT NULL,
  `cpf`       VARCHAR(14)   DEFAULT NULL,
  `email`     VARCHAR(255)  DEFAULT NULL,
  `telefone`  VARCHAR(20)   DEFAULT NULL,
  `cargo`     VARCHAR(100)  DEFAULT NULL,
  `criado_em` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- senha padrao: "admin123"  |  hash = SHA-256("admin123")
-- TROQUE a senha apos o primeiro login ou use setup_db.py para gerar o hash correto
INSERT INTO `login` (`usuario`, `senha`, `nivel`, `nome`) VALUES
('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'admin', 'Administrador');

CREATE TABLE IF NOT EXISTS `clientes` (
  `id`         INT          NOT NULL AUTO_INCREMENT,
  `cpf`        VARCHAR(14)  DEFAULT NULL,
  `nome`       VARCHAR(150) NOT NULL,
  `endereco`   VARCHAR(255) DEFAULT NULL,
  `contato`    VARCHAR(50)  DEFAULT NULL,
  `criado_em`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `clientes` (`cpf`, `nome`, `endereco`, `contato`) VALUES
('129.107.059-19', 'Geovani Debastiani', 'R. do Geovani', '(47) 9 9999-9999'),
('000.000.000-00', 'Pedro Ferreira',     'R. do Pedro',   '(00) 0 0000-0000'),
('165.444.456-44', 'Anderson Silva',     'R. do Anderson','(47) 0 0041-6547');

CREATE TABLE IF NOT EXISTS `fornecedores` (
  `id`        INT          NOT NULL AUTO_INCREMENT,
  `nome`      VARCHAR(150) NOT NULL,
  `endereco`  VARCHAR(255) DEFAULT NULL,
  `contato`   VARCHAR(50)  DEFAULT NULL,
  `criado_em` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `fornecedores` (`nome`, `endereco`, `contato`) VALUES
('Tirol',     'R. da Tirol',    '(47) 9 9544-5444'),
('Coca-Cola', 'R. da Coca-Cola','(18) 9 9928-4555'),
('LG',        'R. da LG',       '(47) 9 9284-5613'),
('LongaVita', 'R. LongaVita',   '(47) 0 0001-1564');

CREATE TABLE IF NOT EXISTS `produtos` (
  `id`              INT            NOT NULL AUTO_INCREMENT,
  `cod_produto`     VARCHAR(50)    NOT NULL UNIQUE,
  `descricao`       VARCHAR(255)   NOT NULL,
  `valor_unitario`  DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
  `qtde_estoque`    INT            NOT NULL DEFAULT 0,
  `estoque_minimo`  INT            NOT NULL DEFAULT 5,
  `fornecedor`      VARCHAR(150)   DEFAULT NULL,
  `criado_em`       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `produtos` (`cod_produto`, `descricao`, `valor_unitario`, `qtde_estoque`, `estoque_minimo`, `fornecedor`) VALUES
('001', 'Leite 1L Tirol',    3.50,  14973, 100, 'Tirol'),
('002', 'Coca-Cola 2L',      8.90,    320,  50, 'Coca-Cola'),
('003', 'Leite Condensado',  4.50,      3,  10, 'LongaVita');

CREATE TABLE IF NOT EXISTS `movimentacoes_estoque` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `produto_id`  INT          NOT NULL,
  `tipo`        ENUM('entrada','saida') NOT NULL,
  `quantidade`  INT          NOT NULL,
  `motivo`      VARCHAR(255) DEFAULT NULL,
  `criado_em`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`produto_id`) REFERENCES `produtos`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `vendas` (
  `id`           INT           NOT NULL AUTO_INCREMENT,
  `vendedor`     VARCHAR(150)  NOT NULL,
  `cliente_cpf`  VARCHAR(14)   DEFAULT NULL,
  `produto_id`   INT           NOT NULL,
  `quantidade`   INT           NOT NULL,
  `total`        DECIMAL(10,2) NOT NULL,
  `criado_em`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`produto_id`) REFERENCES `produtos`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
