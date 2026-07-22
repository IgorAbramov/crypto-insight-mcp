"""FastAPI gateway over the same domain services the MCP server uses.

One domain, two interfaces: MCP (stdio) for AI agents, REST for humans,
dashboards and system integrations. Both share :mod:`crypto_insight_mcp.services`,
so guardrails and disclaimers are enforced identically.

Run with::

    uvicorn crypto_insight_mcp.api:app
"""

from __future__ import annotations

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import __version__, services
from .guardrails import GuardrailViolation
from .market.client import MarketDataError
from .rag.search import KnowledgeBaseError

app = FastAPI(
    title="crypto-insight-mcp API",
    description=(
        "REST gateway to the crypto-insight domain services. Informational "
        "market data and document retrieval only — not financial advice."
    ),
    version=__version__,
)


@app.exception_handler(GuardrailViolation)
async def guardrail_handler(request: Request, exc: GuardrailViolation) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(MarketDataError)
async def market_error_handler(request: Request, exc: MarketDataError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"error": str(exc)})


@app.exception_handler(KnowledgeBaseError)
async def kb_error_handler(request: Request, exc: KnowledgeBaseError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": str(exc)})


class PortfolioRequest(BaseModel):
    """Request body for /portfolio/analyze."""

    holdings: dict[str, float] = Field(
        ..., description="Ticker symbol -> amount held", examples=[{"BTC": 0.5, "ETH": 10}]
    )
    vs_currency: str = Field("usd", description="Quote currency")


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}


@app.get("/prices")
async def prices(
    symbols: str = Query(..., description="Comma-separated tickers, e.g. BTC,ETH"),
    vs: str = Query("usd", description="Quote currency"),
) -> dict:
    """Current prices with 24h change."""
    symbol_list = [part for part in (item.strip() for item in symbols.split(",")) if part]
    return await services.price_lookup(symbol_list, vs_currency=vs)


@app.post("/portfolio/analyze")
async def analyze_portfolio(request: PortfolioRequest) -> dict:
    """Portfolio valuation with concentration warnings."""
    return await services.portfolio_analysis(request.holdings, vs_currency=request.vs_currency)


@app.get("/knowledge/search")
async def knowledge_search(
    q: str = Query(..., description="Natural-language query"),
    k: int = Query(4, ge=1, le=10, description="Number of chunks to retrieve"),
) -> dict:
    """Semantic search over the knowledge base; returns chunks with sources."""
    return await services.knowledge_search(q, k=k)
