# ADR-0002: Embedded Chroma + local embeddings with an offline fallback

Status: accepted · Date: 2026-07

## Context

The RAG pipeline needs a vector store and an embedding model. A portfolio
project has a hard requirement most production systems don't: **anyone must
be able to clone the repo and run everything — including tests and CI — with
zero paid API keys and, ideally, zero network access.** Options considered:
managed vector DBs (Pinecone, Weaviate Cloud), self-hosted server-mode
stores (Qdrant, Milvus), embedded Chroma; and for embeddings: OpenAI/Voyage
APIs, sentence-transformers (torch), or chromadb's ONNX MiniLM-L6-v2.

## Decision

Use **Chroma in embedded mode** persisted to a local directory, accessed
through `langchain-chroma` so the store remains swappable behind LangChain's
`VectorStore` interface.

Use **ONNX all-MiniLM-L6-v2** (bundled with chromadb, no torch, ~80 MB
download on first use) as the production embedding path, and a deterministic
**`HashEmbeddings` fallback** (signed feature hashing, no downloads) selected
automatically when the model can't be loaded. The provider used at ingest
time is recorded in a marker file next to the index, and search-time code
reconstructs the same embedding space — mixing spaces would silently return
garbage similarities.

Tests and CI always run on `HashEmbeddings` (`CIM_FORCE_HASH_EMBEDDINGS=1`).

## Consequences

- `pip install` + `pytest` works on an air-gapped machine; CI needs no
  secrets and cannot flake on third-party quota.
- Embedded Chroma scales to one process only — fine for a demo/small team,
  not for production fan-out. A managed-store adapter (e.g. Pinecone) is an
  explicit roadmap item; the LangChain interface keeps that a localized change.
- Hash-fallback retrieval quality is markedly lower than MiniLM; the fallback
  logs a warning so degraded mode is never silent.
