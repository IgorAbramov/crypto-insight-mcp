"""Async CoinGecko client with TTL caching and rate limiting.

Uses only the free, keyless CoinGecko endpoints so the project runs anywhere.
The client is deliberately small and dependency-injectable: tests pass an
``httpx.AsyncClient`` backed by ``httpx.MockTransport``.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..guardrails import TokenBucket

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

#: Static map for the most common tickers. Extension point: fall back to the
#: /search endpoint or a config file for long-tail assets.
SYMBOL_TO_ID: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "USDC": "usd-coin",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "SOL": "solana",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "TRX": "tron",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "POL": "matic-network",
    "LTC": "litecoin",
    "BCH": "bitcoin-cash",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "XLM": "stellar",
    "XMR": "monero",
    "ETC": "ethereum-classic",
    "UNI": "uniswap",
    "AAVE": "aave",
    "ATOM": "cosmos",
    "NEAR": "near",
    "ARB": "arbitrum",
    "OP": "optimism",
    "TON": "the-open-network",
    "DAI": "dai",
    "SHIB": "shiba-inu",
    "FIL": "filecoin",
}


class MarketDataError(RuntimeError):
    """Raised when market data cannot be fetched. Message is safe to show to an LLM."""


class _TTLCache:
    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self.ttl = ttl_seconds
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self.ttl:
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (time.monotonic(), value)


class MarketClient:
    """Thin, testable wrapper over the CoinGecko REST API."""

    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        cache_ttl_seconds: float = 30.0,
        rate_per_minute: int = 25,
    ) -> None:
        self._http = http or httpx.AsyncClient(base_url=COINGECKO_BASE, timeout=15.0)
        self._cache = _TTLCache(ttl_seconds=cache_ttl_seconds)
        self._bucket = TokenBucket(rate_per_minute=rate_per_minute)

    @staticmethod
    def resolve_id(symbol: str) -> str:
        coin_id = SYMBOL_TO_ID.get(symbol.upper())
        if coin_id is None:
            supported = ", ".join(sorted(SYMBOL_TO_ID))
            raise MarketDataError(f"Unknown symbol {symbol!r}. Supported symbols: {supported}.")
        return coin_id

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        cache_key = f"{path}?{sorted(params.items())}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        if not self._bucket.try_acquire():
            raise MarketDataError("Rate limit reached for market data API; retry in a few seconds.")
        try:
            response = await self._http.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MarketDataError(
                f"Market data API returned HTTP {exc.response.status_code} for {path}."
            ) from exc
        except httpx.HTTPError as exc:
            raise MarketDataError(f"Market data API request failed: {exc.__class__.__name__}.") from exc
        payload = response.json()
        self._cache.set(cache_key, payload)
        return payload

    async def get_prices(self, symbols: list[str], vs_currency: str = "usd") -> dict[str, dict[str, float]]:
        """Current price + 24h change for the given (already validated) symbols."""
        ids = {symbol: self.resolve_id(symbol) for symbol in symbols}
        payload = await self._get(
            "/simple/price",
            {
                "ids": ",".join(sorted(set(ids.values()))),
                "vs_currencies": vs_currency,
                "include_24hr_change": "true",
            },
        )
        result: dict[str, dict[str, float]] = {}
        for symbol, coin_id in ids.items():
            row = payload.get(coin_id)
            if row is None or vs_currency not in row:
                raise MarketDataError(f"No {vs_currency.upper()} quote returned for {symbol}.")
            result[symbol] = {
                "price": float(row[vs_currency]),
                "change_24h_pct": round(float(row.get(f"{vs_currency}_24h_change", 0.0)), 4),
            }
        return result

    async def get_market_history(
        self, symbol: str, days: int = 30, vs_currency: str = "usd"
    ) -> list[dict[str, float]]:
        """Daily closing prices for the last ``days`` days."""
        coin_id = self.resolve_id(symbol)
        payload = await self._get(
            f"/coins/{coin_id}/market_chart",
            {"vs_currency": vs_currency, "days": days, "interval": "daily"},
        )
        prices = payload.get("prices") or []
        return [{"timestamp_ms": int(ts), "price": float(price)} for ts, price in prices]

    async def aclose(self) -> None:
        await self._http.aclose()
