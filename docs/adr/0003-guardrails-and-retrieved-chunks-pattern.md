# ADR-0003: Guardrails at the tool boundary; return retrieved chunks, not answers

Status: accepted · Date: 2026-07

## Context

The server's callers are LLMs, which changes the threat and failure model:
inputs may be malformed in creative ways, error strings become model inputs
that steer the next action, any analytical output risks being repeated to an
end user as advice, and a financial domain amplifies the cost of all three.
Separately, for the RAG tool there is a design fork: should the server
synthesise an answer from retrieved documents (server-side LLM call), or
return raw retrieved chunks and let the calling model synthesise?

## Decision

**Guardrails are a dedicated module applied at every tool boundary.** All
inputs pass validators that raise `GuardrailViolation` with messages written
for an LLM audience (what was wrong + acceptable values). Outbound calls to
CoinGecko go through a token-bucket rate limiter. Every analytical response
carries a mandatory not-financial-advice `disclaimer` field. Handled errors
are returned as structured `{"error": ...}` payloads — a bad tool call must
never crash the server, and upstream failures must never leak stack traces
or parameterised URLs into model context. Consequential actions stay behind
a human approval gate (demonstrated in `agent_demo`).

**`search_knowledge` returns retrieved chunks with sources — it does not
synthesise answers.** Synthesis belongs to the client LLM, which holds the
conversation context and its own safety layer.

## Consequences

- Clear separation of responsibility: the server is a governed, auditable
  data provider; reasoning stays with the agent. No second LLM (with its own
  key, cost, latency and injection surface) inside the server.
- Source filenames travel with every chunk, so client answers are citable
  and retrieval quality can be evaluated offline (roadmap: evaluation harness).
- Validators and limits are unit-tested in isolation; new tools inherit the
  pattern by construction (validate → call service → disclaimer → structured
  errors).
- Trade-off: clients that want a one-shot "ask the docs" endpoint must do
  their own synthesis; accepted as the correct MCP division of labour.
