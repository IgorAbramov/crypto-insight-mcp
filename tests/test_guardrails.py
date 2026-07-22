"""Guardrail validation and rate-limiter tests (pure unit tests, no I/O)."""

from __future__ import annotations

import pytest

from crypto_insight_mcp import guardrails
from crypto_insight_mcp.guardrails import (
    DISCLAIMER,
    GuardrailViolation,
    TokenBucket,
    validate_days,
    validate_holdings,
    validate_query,
    validate_symbols,
    with_disclaimer,
)


class TestValidateSymbols:
    def test_normalises_to_upper(self):
        assert validate_symbols(["btc", " Eth "]) == ["BTC", "ETH"]

    def test_empty_list_rejected(self):
        with pytest.raises(GuardrailViolation):
            validate_symbols([])

    def test_too_many_symbols_rejected(self):
        with pytest.raises(GuardrailViolation, match="Too many"):
            validate_symbols(["BTC"] * 26)

    @pytest.mark.parametrize("bad", ["", "B", "X" * 11, "BTC/USD", "BTC ETH", "b$c"])
    def test_malformed_symbols_rejected(self, bad):
        with pytest.raises(GuardrailViolation, match="Invalid ticker"):
            validate_symbols([bad])


class TestValidateQuery:
    def test_strips_and_returns(self):
        assert validate_query("  what is MiCA?  ") == "what is MiCA?"

    def test_control_chars_removed(self):
        assert validate_query("mica\x00\x08 rules\x1f") == "mica rules"

    @pytest.mark.parametrize("bad", ["", "   ", "\x00\x01"])
    def test_empty_rejected(self, bad):
        with pytest.raises(GuardrailViolation):
            validate_query(bad)

    def test_too_long_rejected(self):
        with pytest.raises(GuardrailViolation, match="too long"):
            validate_query("x" * 501)


class TestValidateDays:
    @pytest.mark.parametrize("ok", [1, 30, 365])
    def test_valid(self, ok):
        assert validate_days(ok) == ok

    @pytest.mark.parametrize("bad", [0, -1, 366, "30", 3.5, True])
    def test_invalid(self, bad):
        with pytest.raises(GuardrailViolation):
            validate_days(bad)


class TestValidateHoldings:
    def test_valid_holdings_normalised(self):
        assert validate_holdings({"btc": 0.5, "ETH": 10}) == {"BTC": 0.5, "ETH": 10.0}

    def test_zero_positions_dropped(self):
        assert validate_holdings({"BTC": 1, "ETH": 0}) == {"BTC": 1.0}

    def test_all_zero_rejected(self):
        with pytest.raises(GuardrailViolation, match="zero"):
            validate_holdings({"BTC": 0, "ETH": 0.0})

    def test_negative_amount_rejected(self):
        with pytest.raises(GuardrailViolation, match=">= 0"):
            validate_holdings({"BTC": -1})

    def test_non_numeric_amount_rejected(self):
        with pytest.raises(GuardrailViolation, match="must be a number"):
            validate_holdings({"BTC": "lots"})

    def test_empty_rejected(self):
        with pytest.raises(GuardrailViolation):
            validate_holdings({})

    def test_too_many_positions_rejected(self):
        holdings = {f"C{i:03d}": 1.0 for i in range(51)}
        with pytest.raises(GuardrailViolation, match="Too many"):
            validate_holdings(holdings)

    def test_bad_symbol_inside_holdings_rejected(self):
        with pytest.raises(GuardrailViolation, match="Invalid ticker"):
            validate_holdings({"B!": 1})


class TestTokenBucket:
    def test_exhaustion_and_refill(self, monkeypatch):
        clock = {"now": 0.0}
        monkeypatch.setattr(guardrails.time, "monotonic", lambda: clock["now"])

        bucket = TokenBucket(rate_per_minute=60, capacity=2)  # 1 token/second
        assert bucket.try_acquire()
        assert bucket.try_acquire()
        assert not bucket.try_acquire()  # exhausted

        clock["now"] += 1.0  # one token regenerates
        assert bucket.try_acquire()
        assert not bucket.try_acquire()

    def test_refill_never_exceeds_capacity(self, monkeypatch):
        clock = {"now": 0.0}
        monkeypatch.setattr(guardrails.time, "monotonic", lambda: clock["now"])

        bucket = TokenBucket(rate_per_minute=60, capacity=2)
        clock["now"] += 3600.0  # an hour passes; capacity still caps at 2
        assert bucket.try_acquire()
        assert bucket.try_acquire()
        assert not bucket.try_acquire()


def test_with_disclaimer_adds_key():
    payload = with_disclaimer({"data": 1})
    assert payload["disclaimer"] == DISCLAIMER
    assert "NOT financial" in payload["disclaimer"]
