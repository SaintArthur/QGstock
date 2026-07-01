from __future__ import annotations

from typing import Any


def resumo_estoque(produtos: list[tuple[Any, ...]]) -> dict[str, Any]:
    total_skus = len(produtos)
    valor_total = sum(float(p[3]) * int(p[4]) for p in produtos)
    abaixo_minimo = [p for p in produtos if int(p[4]) <= int(p[5])]
    zerados = [p for p in produtos if int(p[4]) == 0]

    return {
        "total_skus": total_skus,
        "valor_total": valor_total,
        "abaixo_minimo": len(abaixo_minimo),
        "zerados": len(zerados),
        "produtos_criticos": abaixo_minimo,
    }


def resumo_vendas(vendas: list[tuple[Any, ...]]) -> dict[str, Any]:
    total_registros = len(vendas)
    receita_total = sum(float(v[5]) for v in vendas)
    itens_vendidos = sum(int(v[4]) for v in vendas)

    por_vendedor: dict[str, float] = {}
    for v in vendas:
        por_vendedor[v[1]] = por_vendedor.get(v[1], 0.0) + float(v[5])

    ranking = sorted(por_vendedor.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_registros": total_registros,
        "receita_total": receita_total,
        "itens_vendidos": itens_vendidos,
        "ranking_vendedores": ranking,
    }


def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(parte: float, total: float) -> str:
    if total == 0:
        return "0,0%"
    return f"{(parte / total * 100):.1f}%".replace(".", ",")
