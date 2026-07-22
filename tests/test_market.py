"""Market client tests against httpx.MockTransport — no live requests."""

from __future__ import annotations

import pytest

from crypto_insight_mcp.market.client import MarketClient, MarketDataError

from .conftest import CountingHandler, make_market_client


async def test_get_prices(market_client: MarketClient):
    prices = await market_client.get_prices(["BTC", "ETH"])
    assert prices["BTC"] == {"price": 50000.0, "change_24h_pct": 2.5}
    assert prices["ETH"]["price"] == 2500.0
    assert prices["ETH"]["change_24h_pct"] == -1.25


async def test_get_market_history_maps_points(market_client: MarketClient):
    points = await market_client.get_market_history("BTC", days=4)
    assert len(points) == 4
    assert points[0] == {"timestamp_ms": 1700000000000, "price": 50000.0}
    assert all(set(p) == {"timestamp_ms", "price"} for p in points)


async def test_cache_prevents_second_request(handler: CountingHandler):
    client = make_market_client(handler)
    await client.get_prices(["BTC"])
    await client.get_prices(["BTC"])  # served from TTL cache
    assert handler.calls == 1


async def test_different_params_bypass_cache(handler: CountingHandler):
    client = make_market_client(handler)
    await client.get_prices(["BTC"])
    await client.get_prices(["ETH"])
    assert handler.calls == 2


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_http_errors_become_market_data_error(status):
    handler = CountingHandler(status_code=status)
    client = make_market_client(handler)
    with pytest.raises(MarketDataError, match=str(status)):
        await client.get_prices(["BTC"])


async def test_error_message_is_llm_safe():
    handler = CountingHandler(status_code=500)
    client = make_market_client(handler)
    with pytest.raises(MarketDataError) as excinfo:
        await client.get_prices(["BTC"])
    message = str(excinfo.value)
    assert "Traceback" not in message
    assert "?" not in message  # no URLs with query params leaked


async def test_unknown_symbol_lists_supported(market_client: MarketClient):
    with pytest.raises(MarketDataError, match="Unknown symbol"):
        await market_client.get_prices(["NOPECOIN"])


async def test_rate_limit_exhaustion_raises(handler: CountingHandler):
    client = make_market_client(handler, cache_ttl_seconds=0.0, rate_per_minute=1)
    await client.get_prices(["BTC"])
    with pytest.raises(MarketDataError, match="Rate limit"):
        await client.get_prices(["ETH"])
