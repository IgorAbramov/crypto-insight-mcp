"""Domain services shared by the MCP server and the FastAPI gateway.

Pure async functions, no MCP or HTTP framework imports: the same logic is
exposed twice — over MCP (stdio) for AI agents and over REST for humans and
systems. Every function validates its inputs through guardrails and stamps
analytical outputs with the mandatory disclaimer.

Dependencies (market client, knowledge base) are injectable keyword arguments
so the whole layer is unit-testable offline; when omitted, lazy process-wide
singletons are used.
"""

from __future__ import annotations

from .guardrails import (
    GuardrailViolation,
    validate_days,
    validate_holdings,
    validate_query,
    validate_symbols,
    with_disclaimer,
)
from .market.client import MarketClient, MarketDataError
from .rag.search import KnowledgeBase

MAX_SEARCH_RESULTS = 10

_market_client: MarketClient | None = None
_knowledge_base: KnowledgeBase | None = None


def get_market_client() -> MarketClient:
    """Process-wide market client (created on first use)."""
    global _market_client
    if _market_client is None:
        _market_client = MarketClient()
    return _market_client


def get_knowledge_base() -> KnowledgeBase:
    """Process-wide knowledge base (created on first use)."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base


async def price_lookup(
    symbols: list[str],
    vs_currency: str = "usd",
    *,
    client: MarketClient | None = None,
) -> dict:
    """Current spot prices with 24h change for a list of ticker symbols."""
    symbols = validate_symbols(symbols)
    client = client or get_market_client()
    prices = await client.get_prices(symbols, vs_currency=vs_currency)
    return with_disclaimer({"vs_currency": vs_currency, "prices": prices})


async def market_history(
    symbol: str,
    days: int = 30,
    vs_currency: str = "usd",
    *,
    client: MarketClient | None = None,
) -> dict:
    """Daily price history for one symbol plus min/max/change statistics."""
    symbol = validate_symbols([symbol])[0]
    days = validate_days(days)
    client = client or get_market_client()
    points = await client.get_market_history(symbol, days=days, vs_currency=vs_currency)
    if not points:
        raise MarketDataError(f"No price history returned for {symbol}.")
    prices = [point["price"] for point in points]
    first, last = prices[0], prices[-1]
    change_pct = ((last - first) / first * 100.0) if first else 0.0
    return with_disclaimer(
        {
            "symbol": symbol,
            "vs_currency": vs_currency,
            "days": days,
            "points": points,
            "stats": {
                "min": min(prices),
                "max": max(prices),
                "first": first,
                "last": last,
                "change_pct": round(change_pct, 4),
            },
        }
    )


async def portfolio_analysis(
    holdings: dict[str, float],
    vs_currency: str = "usd",
    *,
    client: MarketClient | None = None,
) -> dict:
    """Value a portfolio and flag concentration risk.

    Returns total value, per-position breakdown with allocation percentages,
    the Herfindahl–Hirschman concentration index (sum of squared allocation
    shares, 1/N..1) and human-readable warnings. Deliberately descriptive,
    not prescriptive: no buy/sell recommendations are produced here.
    """
    holdings = validate_holdings(holdings)
    client = client or get_market_client()
    prices = await client.get_prices(list(holdings), vs_currency=vs_currency)

    values = {symbol: amount * prices[symbol]["price"] for symbol, amount in holdings.items()}
    total_value = sum(values.values())

    positions: dict[str, dict] = {}
    warnings: list[str] = []
    hhi = 0.0
    for symbol, amount in holdings.items():
        value = values[symbol]
        share = (value / total_value) if total_value else 0.0
        hhi += share * share
        positions[symbol] = {
            "amount": amount,
            "price": prices[symbol]["price"],
            "value": round(value, 2),
            "allocation_pct": round(share * 100.0, 2),
        }
        if share > 0.5:
            warnings.append(
                f"{symbol} makes up {share * 100.0:.1f}% of the portfolio — "
                "single-asset concentration risk."
            )
    hhi = round(hhi, 4)
    if hhi > 0.4:
        warnings.append(f"Portfolio is highly concentrated (HHI={hhi:.2f}, threshold 0.40).")

    return with_disclaimer(
        {
            "vs_currency": vs_currency,
            "total_value": round(total_value, 2),
            "positions": positions,
            "hhi": hhi,
            "warnings": warnings,
        }
    )


async def knowledge_search(
    query: str,
    k: int = 4,
    *,
    kb: KnowledgeBase | None = None,
) -> dict:
    """Semantic search over the internal knowledge base.

    Returns retrieved chunks with their sources; answer synthesis is left to
    the LLM client (see ADR-0003).
    """
    query = validate_query(query)
    if not isinstance(k, int) or isinstance(k, bool) or not (1 <= k <= MAX_SEARCH_RESULTS):
        raise GuardrailViolation(f"'k' must be an integer between 1 and {MAX_SEARCH_RESULTS}.")
    kb = kb or get_knowledge_base()
    results = kb.search(query, k=k)
    return with_disclaimer({"query": query, "results": results})
