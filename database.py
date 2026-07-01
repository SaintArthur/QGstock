from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor

from config import DatabaseConfig


@dataclass(frozen=True)
class UsuarioAutenticado:
    login: str
    nome: str
    nivel: str


def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, cfg: DatabaseConfig) -> None:
        self._conn: MySQLConnection = mysql.connector.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            passwd=cfg.password,
            database=cfg.database,
            charset="utf8mb4",
        )

    def fechar(self) -> None:
        if self._conn.is_connected():
            self._conn.close()

    @contextmanager
    def _cursor(self) -> Generator[MySQLCursor, None, None]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    def autenticar(self, usuario: str, senha: str) -> UsuarioAutenticado | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT usuario, nome, nivel FROM login WHERE usuario = %s AND senha = %s",
                (usuario, hash_senha(senha)),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return UsuarioAutenticado(login=row[0], nome=row[1], nivel=row[2])

    def listar_colaboradores(self) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT usuario, nivel, nome, cpf, email, telefone, cargo FROM login ORDER BY nome"
            )
            return cur.fetchall()

    def cadastrar_colaborador(
        self,
        usuario: str,
        senha: str,
        nivel: str,
        nome: str,
        cpf: str,
        email: str,
        telefone: str,
        cargo: str,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO login (usuario, senha, nivel, nome, cpf, email, telefone, cargo) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (usuario, hash_senha(senha), nivel, nome, cpf, email, telefone, cargo),
            )

    def atualizar_colaborador(
        self,
        usuario_original: str,
        usuario: str,
        nivel: str,
        nome: str,
        cpf: str,
        email: str,
        telefone: str,
        cargo: str,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE login SET usuario=%s, nivel=%s, nome=%s, cpf=%s, "
                "email=%s, telefone=%s, cargo=%s WHERE usuario=%s",
                (usuario, nivel, nome, cpf, email, telefone, cargo, usuario_original),
            )

    def remover_colaborador(self, usuario: str) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM login WHERE usuario = %s", (usuario,))

    def listar_fornecedores(self) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            cur.execute("SELECT id, nome, endereco, contato FROM fornecedores ORDER BY nome")
            return cur.fetchall()

    def cadastrar_fornecedor(self, nome: str, endereco: str, contato: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO fornecedores (nome, endereco, contato) VALUES (%s, %s, %s)",
                (nome, endereco, contato),
            )

    def atualizar_fornecedor(
        self, fornecedor_id: int, nome: str, endereco: str, contato: str
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE fornecedores SET nome=%s, endereco=%s, contato=%s WHERE id=%s",
                (nome, endereco, contato, fornecedor_id),
            )

    def remover_fornecedor(self, fornecedor_id: int) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM fornecedores WHERE id = %s", (fornecedor_id,))

    def listar_produtos(self) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, cod_produto, descricao, valor_unitario, qtde_estoque, "
                "estoque_minimo, fornecedor FROM produtos ORDER BY descricao"
            )
            return cur.fetchall()

    def cadastrar_produto(
        self,
        cod: str,
        descricao: str,
        valor: float,
        qtde: int,
        estoque_minimo: int,
        fornecedor: str,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO produtos (cod_produto, descricao, valor_unitario, qtde_estoque, "
                "estoque_minimo, fornecedor) VALUES (%s, %s, %s, %s, %s, %s)",
                (cod, descricao, valor, qtde, estoque_minimo, fornecedor),
            )

    def atualizar_produto(
        self,
        produto_id: int,
        cod: str,
        descricao: str,
        valor: float,
        qtde: int,
        estoque_minimo: int,
        fornecedor: str,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                "UPDATE produtos SET cod_produto=%s, descricao=%s, valor_unitario=%s, "
                "qtde_estoque=%s, estoque_minimo=%s, fornecedor=%s WHERE id=%s",
                (cod, descricao, valor, qtde, estoque_minimo, fornecedor, produto_id),
            )

    def remover_produto(self, produto_id: int) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))

    def ajustar_estoque(self, produto_id: int, quantidade: int, tipo: str, motivo: str) -> None:
        with self._cursor() as cur:
            if tipo == "entrada":
                cur.execute(
                    "UPDATE produtos SET qtde_estoque = qtde_estoque + %s WHERE id = %s",
                    (quantidade, produto_id),
                )
            else:
                cur.execute(
                    "UPDATE produtos SET qtde_estoque = GREATEST(0, qtde_estoque - %s) WHERE id = %s",
                    (quantidade, produto_id),
                )
            cur.execute(
                "INSERT INTO movimentacoes_estoque (produto_id, tipo, quantidade, motivo) "
                "VALUES (%s, %s, %s, %s)",
                (produto_id, tipo, quantidade, motivo),
            )

    def listar_movimentacoes(self, produto_id: int | None = None) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            if produto_id is not None:
                cur.execute(
                    "SELECT m.id, p.descricao, m.tipo, m.quantidade, m.motivo, m.criado_em "
                    "FROM movimentacoes_estoque m JOIN produtos p ON m.produto_id = p.id "
                    "WHERE m.produto_id = %s ORDER BY m.criado_em DESC",
                    (produto_id,),
                )
            else:
                cur.execute(
                    "SELECT m.id, p.descricao, m.tipo, m.quantidade, m.motivo, m.criado_em "
                    "FROM movimentacoes_estoque m JOIN produtos p ON m.produto_id = p.id "
                    "ORDER BY m.criado_em DESC LIMIT 200"
                )
            return cur.fetchall()

    def produtos_com_estoque_baixo(self) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT id, cod_produto, descricao, qtde_estoque, estoque_minimo, fornecedor "
                "FROM produtos WHERE qtde_estoque <= estoque_minimo ORDER BY descricao"
            )
            return cur.fetchall()

    def listar_clientes(self) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            cur.execute("SELECT id, cpf, nome, endereco, contato FROM clientes ORDER BY nome")
            return cur.fetchall()

    def cadastrar_cliente(self, cpf: str, nome: str, endereco: str, contato: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO clientes (cpf, nome, endereco, contato) VALUES (%s, %s, %s, %s)",
                (cpf, nome, endereco, contato),
            )

    def remover_cliente(self, cliente_id: int) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))

    def registrar_venda(
        self,
        vendedor: str,
        cliente_cpf: str,
        produto_id: int,
        quantidade: int,
        total: float,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO vendas (vendedor, cliente_cpf, produto_id, quantidade, total) "
                "VALUES (%s, %s, %s, %s, %s)",
                (vendedor, cliente_cpf, produto_id, quantidade, total),
            )
            cur.execute(
                "UPDATE produtos SET qtde_estoque = GREATEST(0, qtde_estoque - %s) WHERE id = %s",
                (quantidade, produto_id),
            )
            cur.execute(
                "INSERT INTO movimentacoes_estoque (produto_id, tipo, quantidade, motivo) "
                "VALUES (%s, 'saida', %s, %s)",
                (produto_id, quantidade, f"Venda para {cliente_cpf}"),
            )

    def listar_vendas(self) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT v.id, v.vendedor, v.cliente_cpf, p.descricao, v.quantidade, "
                "v.total, v.criado_em "
                "FROM vendas v JOIN produtos p ON v.produto_id = p.id "
                "ORDER BY v.criado_em DESC"
            )
            return cur.fetchall()

    def kpis_dashboard(self) -> dict[str, Any]:
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM produtos")
            total_skus = cur.fetchone()[0]

            cur.execute("SELECT COALESCE(SUM(valor_unitario * qtde_estoque), 0) FROM produtos")
            valor_estoque = float(cur.fetchone()[0])

            cur.execute(
                "SELECT COALESCE(SUM(total), 0) FROM vendas WHERE DATE(criado_em) = CURDATE()"
            )
            vendas_hoje = float(cur.fetchone()[0])

            cur.execute(
                "SELECT COALESCE(SUM(total), 0) FROM vendas "
                "WHERE MONTH(criado_em) = MONTH(CURDATE()) AND YEAR(criado_em) = YEAR(CURDATE())"
            )
            vendas_mes = float(cur.fetchone()[0])

            cur.execute(
                "SELECT COUNT(*) FROM produtos WHERE qtde_estoque <= estoque_minimo"
            )
            alertas_estoque = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM clientes")
            total_clientes = cur.fetchone()[0]

        return {
            "total_skus": total_skus,
            "valor_estoque": valor_estoque,
            "vendas_hoje": vendas_hoje,
            "vendas_mes": vendas_mes,
            "alertas_estoque": alertas_estoque,
            "total_clientes": total_clientes,
        }

    def ranking_vendedores(self) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT vendedor, COUNT(*) as num_vendas, SUM(total) as total_vendido "
                "FROM vendas GROUP BY vendedor ORDER BY total_vendido DESC"
            )
            return cur.fetchall()

    def relatorio_vendas_periodo(
        self, data_inicio: str, data_fim: str
    ) -> list[tuple[Any, ...]]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT v.id, v.vendedor, v.cliente_cpf, p.descricao, v.quantidade, "
                "v.total, v.criado_em "
                "FROM vendas v JOIN produtos p ON v.produto_id = p.id "
                "WHERE DATE(v.criado_em) BETWEEN %s AND %s ORDER BY v.criado_em",
                (data_inicio, data_fim),
            )
            return cur.fetchall()
