# ADR-0001: Official Python MCP SDK (FastMCP) with a src-layout package

Status: accepted · Date: 2026-07

## Context

The project's primary interface is an MCP server that AI agents (Claude
Desktop, IDE agents, custom orchestrators) connect to over stdio. Options
considered: the official `mcp` Python SDK with its FastMCP API, the
third-party `fastmcp` 2.x package, or implementing the JSON-RPC protocol
directly. The codebase also needs a layout that survives growth: the same
domain logic must be reachable from the MCP server, a REST gateway, tests and
a demo agent.

## Decision

Use the official `mcp>=1.2` SDK and its bundled FastMCP API: tools are typed
Python functions, schemas are derived from signatures and docstrings, and the
SDK tracks protocol revisions — the highest-risk surface to hand-roll.

Structure the code as an installable package in `src/` layout, with a strict
separation: `services.py` holds pure domain functions; `server.py` (MCP) and
`api.py` (REST) are thin transport adapters. Tests import services and the
`mcp` object directly — no subprocess needed. The src-layout prevents the
classic "accidentally importing the repo directory" failure and mirrors how
the package behaves once installed.

## Consequences

- Tool schemas stay in sync with code automatically; docstrings become the
  agent-facing contract, so they are written and reviewed as documentation.
- Transport adapters stay ~10 lines per tool; new interfaces (e.g. an SSE
  deployment) reuse `services.py` unchanged.
- We depend on the SDK's release cadence for new protocol features; accepted,
  since tracking the spec by hand is strictly worse.
