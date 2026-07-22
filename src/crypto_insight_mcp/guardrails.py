"""Responsible-AI guardrails: input validation, rate limiting, disclaimers.

Every tool exposed to an AI agent goes through this module. The goal is to keep
agent-facing surfaces predictable and safe:

* strict input validation (fail fast, clear error messages the LLM can act on);
* rate limiting for outbound third-party API calls;
* a mandatory disclaimer on every analytical output, so downstream LLMs cannot
  accidentally present market data as financial advice.
"""

from __future__ import annotations

import re
import threading
import time

DISCLAIMER = (
    "Informational market data / document retrieval only. "
    "This is NOT financial, investment, legal or tax advice."
)

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9]{2,10}$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

MAX_SYMBOLS = 25
MAX_QUERY_LEN = 500
MAX_HISTORY_DAYS = 365
MAX_HOLDINGS = 50


class GuardrailViolation(ValueError):
    """Raised when agent-provided input violates a guardrail.

    The message is written to be actionable for an LLM caller: it explains
    what was wrong and what the acceptable range is.
    """


def validate_symbols(symbols: list[str]) -> list[str]:
    """Validate and normalise a list of ticker symbols (e.g. ["BTC", "eth"])."""
    if not symbols:
        raise GuardrailViolation("Provide at least one ticker symbol, e.g. ['BTC'].")
    if len(symbols) > MAX_SYMBOLS:
        raise GuardrailViolation(f"Too many symbols ({len(symbols)}); maximum is {MAX_SYMBOLS} per call.")
    normalised = []
    for raw in symbols:
        sym = str(raw).strip().upper()
        if not _SYMBOL_RE.match(sym):
            raise GuardrailViolation(
                f"Invalid ticker symbol {raw!r}: expected 2-10 alphanumeric characters, e.g. 'BTC'."
            )
        normalised.append(sym)
    return normalised


def validate_query(query: str) -> str:
    """Validate a free-text knowledge-base query."""
    cleaned = _CONTROL_CHARS_RE.sub("", str(query)).strip()
    if not cleaned:
        raise GuardrailViolation("Query must be a non-empty string.")
    if len(cleaned) > MAX_QUERY_LEN:
        raise GuardrailViolation(f"Query too long ({len(cleaned)} chars); maximum is {MAX_QUERY_LEN}.")
    return cleaned


def validate_days(days: int) -> int:
    if not isinstance(days, int) or isinstance(days, bool):
        raise GuardrailViolation("'days' must be an integer.")
    if days < 1 or days > MAX_HISTORY_DAYS:
        raise GuardrailViolation(f"'days' must be between 1 and {MAX_HISTORY_DAYS}.")
    return days


def validate_holdings(holdings: dict[str, float]) -> dict[str, float]:
    """Validate a portfolio mapping of symbol -> amount held."""
    if not holdings:
        raise GuardrailViolation("Provide at least one holding, e.g. {'BTC': 0.5}.")
    if len(holdings) > MAX_HOLDINGS:
        raise GuardrailViolation(f"Too many holdings ({len(holdings)}); maximum is {MAX_HOLDINGS}.")
    validated: dict[str, float] = {}
    for raw_symbol, raw_amount in holdings.items():
        symbol = validate_symbols([raw_symbol])[0]
        try:
            amount = float(raw_amount)
        except (TypeError, ValueError) as exc:
            raise GuardrailViolation(f"Amount for {symbol} must be a number, got {raw_amount!r}.") from exc
        if amount < 0:
            raise GuardrailViolation(f"Amount for {symbol} must be >= 0, got {amount}.")
        if amount > 0:
            validated[symbol] = amount
    if not validated:
        raise GuardrailViolation("All holding amounts are zero; nothing to analyse.")
    return validated


class TokenBucket:
    """Simple thread-safe token bucket used to rate-limit outbound API calls."""

    def __init__(self, rate_per_minute: int = 25, capacity: int | None = None) -> None:
        self.rate_per_second = rate_per_minute / 60.0
        self.capacity = float(capacity if capacity is not None else rate_per_minute)
        self._tokens = self.capacity
        self._updated_at = time.monotonic()
        self._lock = threading.Lock()

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Take a token if available; returns False when the caller should back off."""
        with self._lock:
            now = time.monotonic()
            self._tokens = min(self.capacity, self._tokens + (now - self._updated_at) * self.rate_per_second)
            self._updated_at = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


def with_disclaimer(payload: dict) -> dict:
    """Attach the mandatory disclaimer to an analytical tool response."""
    payload["disclaimer"] = DISCLAIMER
    return payload
