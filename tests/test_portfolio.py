"""Portfolio analysis service tests (market data mocked)."""

from __future__ import annotations

import pytest

from crypto_insight_mcp.guardrails import DISCLAIMER, GuardrailViolation
from crypto_insight_mcp.services import portfolio_analysis


async def test_valuation_and_allocations(market_client):
    # 1 BTC @ 50k + 20 ETH @ 2.5k = 100k, a clean 50/50 split.
    result = await portfolio_analysis({"BTC": 1, "ETH": 20}, client=market_client)

    assert result["total_value"] == pytest.approx(100000.0)
    assert result["positions"]["BTC"]["value"] == pytest.approx(50000.0)
    assert result["positions"]["BTC"]["allocation_pct"] == pytest.approx(50.0)
    assert result["positions"]["ETH"]["allocation_pct"] == pytest.approx(50.0)
    assert result["positions"]["ETH"]["price"] == pytest.approx(2500.0)


async def test_hhi_for_even_split(market_client):
    # Two equal positions: HHI = 0.5^2 + 0.5^2 = 0.5.
    result = await portfolio_analysis({"BTC": 1, "ETH": 20}, client=market_client)
    assert result["hhi"] == pytest.approx(0.5)


async def test_concentration_warnings_trigger(market_client):
    # BTC dominates: 1 BTC = 50k vs 100 USDT = 100.
    result = await portfolio_analysis({"BTC": 1, "USDT": 100}, client=market_client)

    warnings = " ".join(result["warnings"])
    assert "BTC" in warnings and "concentration" in warnings.lower()
    assert "highly concentrated" in warnings.lower()  # HHI ~1.0 > 0.4
    assert result["hhi"] > 0.9


async def test_balanced_portfolio_has_no_warnings(market_client):
    # Four positions of 25k each: shares 0.25, HHI = 4 * 0.0625 = 0.25.
    holdings = {"BTC": 0.5, "ETH": 10, "USDT": 25000, "SOL": 200}
    result = await portfolio_analysis(holdings, client=market_client)

    assert result["warnings"] == []
    assert result["hhi"] == pytest.approx(0.25)


async def test_disclaimer_present(market_client):
    result = await portfolio_analysis({"BTC": 1}, client=market_client)
    assert result["disclaimer"] == DISCLAIMER


async def test_zero_positions_excluded_from_result(market_client):
    result = await portfolio_analysis({"BTC": 1, "ETH": 0}, client=market_client)
    assert "ETH" not in result["positions"]


async def test_invalid_holdings_rejected_before_any_request(handler):
    from .conftest import make_market_client

    client = make_market_client(handler)
    with pytest.raises(GuardrailViolation):
        await portfolio_analysis({}, client=client)
    assert handler.calls == 0  # guardrails fail fast, no upstream call
