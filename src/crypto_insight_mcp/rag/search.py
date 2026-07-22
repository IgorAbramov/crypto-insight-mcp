"""Semantic search over the ingested knowledge base.

Design note (ADR-0003): this module returns *retrieved chunks with sources*,
never a synthesised answer. Synthesis is the job of the LLM client on the
other side of the MCP boundary — the server stays a governed data provider.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings

from . import COLLECTION_NAME, EMBEDDINGS_MARKER
from .embeddings import default_embeddings, embeddings_by_provider

DEFAULT_PERSIST_DIR = ".chroma"


class KnowledgeBaseError(RuntimeError):
    """Raised when the knowledge base index is missing or unusable.

    The message is safe and actionable for an LLM caller.
    """


class KnowledgeBase:
    """Lazy wrapper around a persistent Chroma collection."""

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        embeddings: Embeddings | None = None,
    ) -> None:
        self.persist_dir = Path(
            persist_dir or os.environ.get("CIM_CHROMA_DIR", DEFAULT_PERSIST_DIR)
        )
        self._embeddings = embeddings
        self._store: Any = None

    def _resolve_embeddings(self) -> Embeddings:
        if self._embeddings is not None:
            return self._embeddings
        marker = self.persist_dir / EMBEDDINGS_MARKER
        if marker.exists():
            provider = json.loads(marker.read_text(encoding="utf-8")).get("provider", "")
            try:
                return embeddings_by_provider(provider)
            except Exception as exc:
                raise KnowledgeBaseError(
                    f"Cannot load the embedding backend {provider!r} the index was built with "
                    f"({exc}). Re-run `python -m crypto_insight_mcp.rag.ingest`."
                ) from exc
        return default_embeddings()

    @property
    def store(self) -> Any:
        if self._store is None:
            if not self.persist_dir.exists():
                raise KnowledgeBaseError(
                    f"Knowledge base index not found at {self.persist_dir}/. "
                    "Run `python -m crypto_insight_mcp.rag.ingest` first."
                )
            # Heavy imports kept local so `import crypto_insight_mcp` stays fast.
            import chromadb
            from chromadb.config import Settings
            from langchain_chroma import Chroma

            client = chromadb.PersistentClient(
                path=str(self.persist_dir), settings=Settings(anonymized_telemetry=False)
            )
            self._store = Chroma(
                client=client,
                collection_name=COLLECTION_NAME,
                embedding_function=self._resolve_embeddings(),
            )
        return self._store

    def search(self, query: str, k: int = 4) -> list[dict[str, Any]]:
        """Return the ``k`` most similar chunks as ``{source, snippet, score}``.

        ``score`` is a distance (lower = more similar), as returned by Chroma.
        """
        try:
            results = self.store.similarity_search_with_score(query, k=k)
        except KnowledgeBaseError:
            raise
        except Exception as exc:
            raise KnowledgeBaseError(
                "Knowledge base search failed. If the index was never built, run "
                "`python -m crypto_insight_mcp.rag.ingest`."
            ) from exc
        return [
            {
                "source": document.metadata.get("source", "unknown"),
                "snippet": document.page_content,
                "score": round(float(score), 4),
            }
            for document, score in results
        ]
