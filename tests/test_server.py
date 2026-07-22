"""MCP server surface tests: tool registration and structured error handling."""

from __future__ import annotations

from crypto_insight_mcp.server import mcp

from .conftest import payload_from_tool_result

EXPECTED_TOOLS = {"get_price", "get_market_history", "analyze_portfolio", "search_knowledge"}


async def test_all_four_tools_registered():
    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == EXPECTED_TOOLS


async def test_tools_have_descriptions():
    tools = await mcp.list_tools()
    for tool in tools:
        assert tool.description and len(tool.description) > 20, tool.name


async def test_guardrail_violation_returned_as_error_payload():
    result = await mcp.call_tool("get_price", {"symbols": []})
    payload = payload_from_tool_result(result)
    assert set(payload) == {"error"}
    assert "at least one ticker" in payload["error"]


async def test_invalid_days_returned_as_error_payload():
    result = await mcp.call_tool("get_market_history", {"symbol": "BTC", "days": 999})
    payload = payload_from_tool_result(result)
    assert "error" in payload
    assert "365" in payload["error"]  # tells the LLM the acceptable range


async def test_invalid_holdings_returned_as_error_payload():
    result = await mcp.call_tool("analyze_portfolio", {"holdings": {"BTC": -5}})
    payload = payload_from_tool_result(result)
    assert "error" in payload


async def test_empty_query_returned_as_error_payload():
    result = await mcp.call_tool("search_knowledge", {"query": "   "})
    payload = payload_from_tool_result(result)
    assert "error" in payload
    assert "non-empty" in payload["error"]
