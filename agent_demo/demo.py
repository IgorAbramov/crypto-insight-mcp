"""Agent demo: "assess the risk of my portfolio" with a human-in-the-loop gate.

Two modes:

* **Offline scripted mode (default)** — no LLM involved. The script walks the
  same tool chain an agent would use (prices -> portfolio analysis ->
  knowledge-base search), drafts a risk note, and asks a human to approve the
  proposed follow-up action before "executing" it (execution is simulated —
  this project never places orders).

* **LLM mode (``--llm``)** — a real tool-use loop through the Anthropic API,
  if the ``anthropic`` package is installed (``pip install -e ".[agent]"``)
  and ``ANTHROPIC_API_KEY`` is set. The same human approval gate applies.

Usage::

    python agent_demo/demo.py "0.5 BTC, 10 ETH, 5000 USDT"
    python agent_demo/demo.py "0.5 BTC, 10 ETH, 5000 USDT" --llm

Note: market data comes from the free CoinGecko API, so the demo needs
internet access; if the API is unreachable it exits with a clear message.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

# Allow running straight from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_insight_mcp import services  # noqa: E402
from crypto_insight_mcp.guardrails import GuardrailViolation  # noqa: E402
from crypto_insight_mcp.market.client import MarketDataError  # noqa: E402
from crypto_insight_mcp.rag.search import KnowledgeBaseError  # noqa: E402

HOLDING_RE = re.compile(r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<symbol>[A-Za-z0-9]{2,10})")

DEFAULT_PORTFOLIO = "0.5 BTC, 10 ETH, 5000 USDT"


def parse_holdings(text: str) -> dict[str, float]:
    """Parse "0.5 BTC, 10 ETH" into {"BTC": 0.5, "ETH": 10.0}."""
    holdings: dict[str, float] = {}
    for match in HOLDING_RE.finditer(text):
        symbol = match.group("symbol").upper()
        holdings[symbol] = holdings.get(symbol, 0.0) + float(match.group("amount"))
    if not holdings:
        raise GuardrailViolation(
            f"Could not parse any holdings from {text!r}. Expected e.g. '0.5 BTC, 10 ETH'."
        )
    return holdings


def ask_approval(prompt: str) -> bool:
    """Human-in-the-loop gate. Defaults to 'no' on empty/EOF input."""
    try:
        answer = input(f"{prompt} [y/N] ")
    except EOFError:
        print("(no input available — treating as 'no')")
        return False
    return answer.strip().lower() in {"y", "yes"}


def _fmt_money(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency.upper()}"


async def run_offline(holdings: dict[str, float], *, client=None, kb=None) -> int:
    """Scripted agent scenario, no LLM. Returns a process exit code."""
    vs = "usd"

    print("=" * 72)
    print("crypto-insight agent demo — offline scripted mode (no LLM)")
    print("=" * 72)

    # Step 1: current prices (same call the MCP tool `get_price` makes).
    print("\n[1/5] Fetching current prices...")
    prices = await services.price_lookup(list(holdings), vs_currency=vs, client=client)
    for symbol, row in prices["prices"].items():
        print(f"    {symbol}: {_fmt_money(row['price'], vs)} ({row['change_24h_pct']:+.2f}% 24h)")

    # Step 2: portfolio analysis (`analyze_portfolio`).
    print("\n[2/5] Analysing portfolio...")
    analysis = await services.portfolio_analysis(holdings, vs_currency=vs, client=client)
    print(f"    Total value: {_fmt_money(analysis['total_value'], vs)}")
    for symbol, position in analysis["positions"].items():
        print(
            f"    {symbol}: {position['amount']} x {_fmt_money(position['price'], vs)}"
            f" = {_fmt_money(position['value'], vs)} ({position['allocation_pct']}%)"
        )
    print(f"    Concentration (HHI): {analysis['hhi']}")
    for warning in analysis["warnings"]:
        print(f"    WARNING: {warning}")
    if not analysis["warnings"]:
        print("    No concentration warnings.")

    # Step 3: ground the risk note in the knowledge base (`search_knowledge`).
    print("\n[3/5] Searching the knowledge base for relevant guidance...")
    if analysis["warnings"]:
        query = "concentration risk and custody controls for large crypto holdings"
    else:
        query = "custody basics and client asset protection"
    try:
        knowledge = await services.knowledge_search(query, k=3, kb=kb)
        for row in knowledge["results"]:
            snippet = " ".join(row["snippet"].split())[:100]
            print(f"    [{row['source']}] {snippet}...")
        sources = sorted({row["source"] for row in knowledge["results"]})
    except KnowledgeBaseError as exc:
        print(f"    Knowledge base unavailable: {exc}")
        print("    (continuing without document grounding)")
        sources = []

    # Step 4: draft the risk note.
    print("\n[4/5] Draft risk note")
    print("-" * 72)
    print(f"  Portfolio value: {_fmt_money(analysis['total_value'], vs)} | HHI: {analysis['hhi']}")
    if analysis["warnings"]:
        print("  Risk flags:")
        for warning in analysis["warnings"]:
            print(f"    - {warning}")
        proposed_action = (
            "Send the portfolio owner a concentration-risk notice referencing "
            "internal custody guidance."
        )
    else:
        print("  Risk flags: none raised by automated checks.")
        proposed_action = "Archive this review; no notice required."
    if sources:
        print(f"  Grounding sources: {', '.join(sources)}")
    print(f"  Disclaimer: {analysis['disclaimer']}")
    print("-" * 72)

    # Step 5: human-in-the-loop before any action is taken.
    print(f"\n[5/5] Proposed action: {proposed_action}")
    if ask_approval("Approve this action?"):
        print("    APPROVED — executing action (simulated: nothing is sent or traded).")
        outcome = "executed (simulated)"
    else:
        print("    NOT APPROVED — action discarded. Nothing was executed.")
        outcome = "discarded by human reviewer"

    print("\nFinal report")
    print(f"  action:  {proposed_action}")
    print(f"  outcome: {outcome}")
    print("  This demo is informational only and never places real orders.")
    return 0


# --------------------------------------------------------------------------
# LLM mode: a real tool-use loop through the Anthropic API (optional extra).
# --------------------------------------------------------------------------

LLM_TOOLS = [
    {
        "name": "get_price",
        "description": "Current spot price and 24h change for ticker symbols.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
                "vs_currency": {"type": "string", "default": "usd"},
            },
            "required": ["symbols"],
        },
    },
    {
        "name": "analyze_portfolio",
        "description": "Value a portfolio and flag concentration risk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "holdings": {"type": "object", "additionalProperties": {"type": "number"}},
                "vs_currency": {"type": "string", "default": "usd"},
            },
            "required": ["holdings"],
        },
    },
    {
        "name": "search_knowledge",
        "description": "Semantic search over internal docs (MiCA, AML/KYC, custody, listing).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 4},
            },
            "required": ["query"],
        },
    },
]


async def _dispatch_tool(name: str, arguments: dict) -> dict:
    try:
        if name == "get_price":
            return await services.price_lookup(
                arguments["symbols"], vs_currency=arguments.get("vs_currency", "usd")
            )
        if name == "analyze_portfolio":
            return await services.portfolio_analysis(
                arguments["holdings"], vs_currency=arguments.get("vs_currency", "usd")
            )
        if name == "search_knowledge":
            return await services.knowledge_search(
                arguments["query"], k=int(arguments.get("k", 4))
            )
        return {"error": f"Unknown tool {name!r}."}
    except (GuardrailViolation, MarketDataError, KnowledgeBaseError) as exc:
        return {"error": str(exc)}


async def run_llm(holdings: dict[str, float]) -> int:
    """Tool-use loop with Claude. Requires `pip install -e ".[agent]"` and a key."""
    try:
        import anthropic
    except ImportError:
        print('LLM mode needs the optional dependency: pip install -e ".[agent]"')
        return 1
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("LLM mode needs ANTHROPIC_API_KEY (see .env.example).")
        return 1

    model = os.environ.get("CIM_DEMO_MODEL", "claude-sonnet-4-5")
    client = anthropic.AsyncAnthropic()

    system = (
        "You are a portfolio risk analyst assistant. Use the tools to fetch "
        "prices, analyse the portfolio and ground your advice in the internal "
        "knowledge base. Cite document sources. You must NOT execute anything; "
        "finish with a concise risk note and a single proposed follow-up action. "
        "Always include the data disclaimer."
    )
    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "Assess the risk of this portfolio and propose one follow-up action: "
                f"{json.dumps(holdings)}"
            ),
        }
    ]

    print("=" * 72)
    print(f"crypto-insight agent demo — LLM mode ({model})")
    print("=" * 72)

    for _ in range(8):  # hard cap on loop iterations
        response = await client.messages.create(
            model=model, max_tokens=1500, system=system, tools=LLM_TOOLS, messages=messages
        )
        tool_results = []
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\n{block.text.strip()}")
            elif block.type == "tool_use":
                print(f"\n  -> tool call: {block.name}({json.dumps(block.input)})")
                result = await _dispatch_tool(block.name, dict(block.input))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue
        break

    # Human-in-the-loop: the model only proposes; a human decides.
    if ask_approval("\nApprove the proposed follow-up action?"):
        print("    APPROVED — executing action (simulated: nothing is sent or traded).")
    else:
        print("    NOT APPROVED — action discarded. Nothing was executed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio risk agent demo.")
    parser.add_argument(
        "portfolio",
        nargs="?",
        default=DEFAULT_PORTFOLIO,
        help=f'e.g. "{DEFAULT_PORTFOLIO}" (default)',
    )
    parser.add_argument("--llm", action="store_true", help="Use the Anthropic API tool-use loop")
    args = parser.parse_args()

    try:
        holdings = parse_holdings(args.portfolio)
        runner = run_llm(holdings) if args.llm else run_offline(holdings)
        exit_code = asyncio.run(runner)
    except GuardrailViolation as exc:
        print(f"Input error: {exc}")
        exit_code = 2
    except MarketDataError as exc:
        print(f"Market data unavailable: {exc}")
        print("The demo needs access to api.coingecko.com — check your connection and retry.")
        exit_code = 3
    except KeyboardInterrupt:
        print("\nInterrupted.")
        exit_code = 130
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
