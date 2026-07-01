"""
Script de inicializacao do banco de dados QGstock.
Execute uma vez antes de rodar o app pela primeira vez.

Uso:
    python setup_db.py [--senha-admin SENHA]
"""
from __future__ import annotations

import argparse
import hashlib
import sys

import mysql.connector
from mysql.connector import MySQLConnection

from config import load_config


def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


DDL = """
CREATE TABLE IF NOT EXISTS `login` (
  `id`        INT           NOT NULL AUTO_INCREMENT,
  `usuario`   VARCHAR(100)  NOT NULL,
  `senha`     VARCHAR(64)   NOT NULL,
  `nivel`     ENUM('admin','colaborador') NOT NULL DEFAULT 'colaborador',
  `nome`      VARCHAR(150)  NOT NULL,
  `cpf`       VARCHAR(14)   DEFAULT NULL,
  `email`     VARCHAR(255)  DEFAULT NULL,
  `telefone`  VARCHAR(20)   DEFAULT NULL,
  `cargo`     VARCHAR(100)  DEFAULT NULL,
  `criado_em` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_usuario` (`usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `clientes` (
  `id`        INT          NOT NULL AUTO_INCREMENT,
  `cpf`       VARCHAR(14)  DEFAULT NULL,
  `nome`      VARCHAR(150) NOT NULL,
  `endereco`  VARCHAR(255) DEFAULT NULL,
  `contato`   VARCHAR(50)  DEFAULT NULL,
  `criado_em` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `fornecedores` (
  `id`        INT          NOT NULL AUTO_INCREMENT,
  `nome`      VARCHAR(150) NOT NULL,
  `endereco`  VARCHAR(255) DEFAULT NULL,
  `contato`   VARCHAR(50)  DEFAULT NULL,
  `criado_em` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `produtos` (
  `id`             INT            NOT NULL AUTO_INCREMENT,
  `cod_produto`    VARCHAR(50)    NOT NULL,
  `descricao`      VARCHAR(255)   NOT NULL,
  `valor_unitario` DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
  `qtde_estoque`   INT            NOT NULL DEFAULT 0,
  `estoque_minimo` INT            NOT NULL DEFAULT 5,
  `fornecedor`     VARCHAR(150)   DEFAULT NULL,
  `criado_em`      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cod_produto` (`cod_produto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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
  `id`          INT           NOT NULL AUTO_INCREMENT,
  `vendedor`    VARCHAR(150)  NOT NULL,
  `cliente_cpf` VARCHAR(14)   DEFAULT NULL,
  `produto_id`  INT           NOT NULL,
  `quantidade`  INT           NOT NULL,
  `total`       DECIMAL(10,2) NOT NULL,
  `criado_em`   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`produto_id`) REFERENCES `produtos`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def criar_banco(conn: MySQLConnection, nome_banco: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{nome_banco}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.execute(f"USE `{nome_banco}`")
        for statement in DDL.strip().split(";"):
            statement = statement.strip()
            if statement:
                cur.execute(statement)
    conn.commit()


def criar_admin(conn: MySQLConnection, senha: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM login WHERE usuario = 'admin'")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO login (usuario, senha, nivel, nome) VALUES (%s, %s, 'admin', %s)",
                ("admin", hash_senha(senha), "Administrador"),
            )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicializa o banco de dados QGstock")
    parser.add_argument("--senha-admin", default="admin123", help="Senha do usuario admin padrao")
    args = parser.parse_args()

    cfg = load_config()
    print(f"Conectando em {cfg.host}:{cfg.port} como {cfg.user}...")

    try:
        conn: MySQLConnection = mysql.connector.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            passwd=cfg.password,
            charset="utf8mb4",
        )
    except Exception as exc:
        print(f"Erro ao conectar: {exc}")
        sys.exit(1)

    try:
        print(f"Criando banco '{cfg.database}'...")
        criar_banco(conn, cfg.database)
        conn.database = cfg.database

        print("Criando usuario admin...")
        criar_admin(conn, args.senha_admin)
    finally:
        conn.close()

    print()
    print("Banco inicializado com sucesso.")
    print(f"  Usuario: admin")
    print(f"  Senha:   {args.senha_admin}")
    print()
    print("Altere a senha do admin apos o primeiro login.")


if __name__ == "__main__":
    main()
