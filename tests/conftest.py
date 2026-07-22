"""Shared offline test fixtures.

No test in this suite touches the network: CoinGecko is replaced with
``httpx.MockTransport`` and embeddings with the deterministic
:class:`HashEmbeddings` fallback.
"""

from __future__ import annotations

import json

import httpx
import pytest

from crypto_insight_mcp.market.client import COINGECKO_BASE, MarketClient

#: /simple/price fixture: four assets so balanced portfolios are possible.
SIMPLE_PRICE_PAYLOAD = {
    "bitcoin": {"usd": 50000.0, "usd_24h_change": 2.5},
    "ethereum": {"usd": 2500.0, "usd_24h_change": -1.25},
    "tether": {"usd": 1.0, "usd_24h_change": 0.01},
    "solana": {"usd": 125.0, "usd_24h_change": 5.0},
}

#: /coins/{id}/market_chart fixture: 4 daily points, +20% over the window.
MARKET_CHART_PAYLOAD = {
    "prices": [
        [1700000000000, 50000.0],
        [1700086400000, 48000.0],
        [1700172800000, 62000.0],
        [1700259200000, 60000.0],
    ]
}


class CountingHandler:
    """MockTransport handler that serves fixtures and counts requests."""

    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.status_code != 200:
            return httpx.Response(self.status_code, json={"error": "upstream error"})
        if request.url.path.endswith("/simple/price"):
            return httpx.Response(200, json=SIMPLE_PRICE_PAYLOAD)
        if "/market_chart" in request.url.path:
            return httpx.Response(200, json=MARKET_CHART_PAYLOAD)
        return httpx.Response(404, json={"error": "not found"})


def make_market_client(handler: CountingHandler, **kwargs) -> MarketClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url=COINGECKO_BASE)
    return MarketClient(http=http, **kwargs)


@pytest.fixture
def handler() -> CountingHandler:
    return CountingHandler()


@pytest.fixture
def market_client(handler: CountingHandler) -> MarketClient:
    return make_market_client(handler)


def payload_from_tool_result(result) -> dict:
    """Normalise FastMCP.call_tool results across mcp SDK versions."""
    if isinstance(result, dict):
        return result
    if isinstance(result, tuple):  # (content_blocks, structured_output)
        content, structured = result
        if isinstance(structured, dict):
            inner = structured.get("result", structured)
            if isinstance(inner, dict):
                return inner
        result = content
    block = result[0]
    return json.loads(block.text)
