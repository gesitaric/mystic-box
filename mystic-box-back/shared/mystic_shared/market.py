"""Histórico de preços do mercado.

Toda venda (anúncio comprado ou ordem de compra atendida) grava um item na
`MarketSalesTable`, na mesma transação da venda: chave `file_name` + `saleId`
(`<instante ISO>#<id>`, para ordenar do mais antigo ao mais recente) e TTL em
`expiresAt`. Não guarda quem comprou nem quem vendeu.
"""

from .cards import MARKET_HISTORY_DAYS

SECONDS_PER_DAY = 24 * 60 * 60


def sale_record_put(table, file_name, price, sold_at, sale_id, now):
    """Item `Put` da transação que registra uma venda no histórico.

    `sold_at` é o instante em ISO 8601 (UTC) e `now` o mesmo instante em
    segundos, usado no TTL.
    """
    return {
        "Put": {
            "TableName": table,
            "Item": {
                "file_name": {"S": file_name},
                "saleId": {"S": f"{sold_at}#{sale_id}"},
                "price": {"N": str(price)},
                "soldAt": {"S": sold_at},
                "expiresAt": {"N": str(now + MARKET_HISTORY_DAYS * SECONDS_PER_DAY)},
            },
            "ConditionExpression": "attribute_not_exists(saleId)",
        }
    }


def summarize_sales(prices):
    """Resumo das vendas (do mais recente ao mais antigo), ou None se não houver."""
    if not prices:
        return None
    return {
        "count": len(prices),
        "last": prices[0],
        "average": round(sum(prices) / len(prices)),
        "min": min(prices),
        "max": max(prices),
    }
