"""MCP server exposing crypto market data and knowledge-base search.

Thin FastMCP wrappers over :mod:`crypto_insight_mcp.services` — all business
logic lives there and is tested without MCP. Guardrail and upstream errors
are returned as structured ``{"error": ...}`` payloads instead of raising, so
a misbehaving tool call can never crash the server and the calling LLM gets a
message it can act on.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import services
from .guardrails import GuardrailViolation
from .market.client import MarketDataError
from .rag.search import KnowledgeBaseError

INSTRUCTIONS = """\
crypto-insight gives you governed, read-only access to cryptocurrency market
data (CoinGecko free API) and semantic search over an internal knowledge base
(regulation, AML/KYC, custody, listing policy).

Rules of engagement:
- Every analytical response carries a `disclaimer` field. Always surface it to
  the end user: this data is informational only, never financial advice.
- `search_knowledge` returns retrieved document chunks with sources, not a
  final answer. Synthesise your answer from the chunks and cite the sources.
- On {"error": ...} responses, read the message — it explains what was wrong
  with the input and what values are acceptable.
"""

mcp = FastMCP("crypto-insight", instructions=INSTRUCTIONS)

_HANDLED_ERRORS = (GuardrailViolation, MarketDataError, KnowledgeBaseError)


@mcp.tool()
async def get_price(symbols: list[str], vs_currency: str = "usd") -> dict:
    """Get current spot price and 24h change for one or more ticker symbols.

    Args:
        symbols: Ticker symbols, e.g. ["BTC", "ETH"]. Max 25 per call.
        vs_currency: Quote currency (default "usd").
    """
    try:
        return await services.price_lookup(symbols, vs_currency=vs_currency)
    except _HANDLED_ERRORS as exc:
        return {"error": str(exc)}


@mcp.tool()
async def get_market_history(symbol: str, days: int = 30, vs_currency: str = "usd") -> dict:
    """Get daily price history for a symbol plus min/max/change statistics.

    Args:
        symbol: Single ticker symbol, e.g. "BTC".
        days: Look-back window in days, 1..365 (default 30).
        vs_currency: Quote currency (default "usd").
    """
    try:
        return await services.market_history(symbol, days=days, vs_currency=vs_currency)
    except _HANDLED_ERRORS as exc:
        return {"error": str(exc)}


@mcp.tool()
async def analyze_portfolio(holdings: dict[str, float], vs_currency: str = "usd") -> dict:
    """Value a portfolio and flag concentration risk (informational only).

    Args:
        holdings: Mapping of ticker symbol to amount held,
            e.g. {"BTC": 0.5, "ETH": 10}. Max 50 positions.
        vs_currency: Quote currency (default "usd").

    Returns total value, per-position allocation percentages, the HHI
    concentration index and warnings. No investment recommendations.
    """
    try:
        return await services.portfolio_analysis(holdings, vs_currency=vs_currency)
    except _HANDLED_ERRORS as exc:
        return {"error": str(exc)}


@mcp.tool()
async def search_knowledge(query: str, k: int = 4) -> dict:
    """Semantic search over the internal knowledge base (MiCA, AML/KYC, custody, listing).

    Args:
        query: Natural-language question or keywords, max 500 characters.
        k: Number of chunks to retrieve, 1..10 (default 4).

    Returns retrieved chunks with `source` and `snippet` — synthesise the
    answer yourself and cite the sources.
    """
    try:
        return await services.knowledge_search(query, k=k)
    except _HANDLED_ERRORS as exc:
        return {"error": str(exc)}


def main() -> None:
    """Console-script entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
