"""Embedding backends for the knowledge base.

Two implementations behind the LangChain :class:`~langchain_core.embeddings.Embeddings`
interface:

* :class:`OnnxMiniLMEmbeddings` — production path. Wraps the ONNX build of
  ``all-MiniLM-L6-v2`` shipped with ``chromadb`` (no torch, ~80 MB). The model
  is downloaded on first use.
* :class:`HashEmbeddings` — deterministic feature-hashing fallback that needs
  no network and no model files. Quality is obviously lower than a trained
  model, but it is stable, fast and good enough for tests, CI and air-gapped
  demo environments.

:func:`default_embeddings` picks the best available backend at runtime and
never raises just because the machine is offline — a deliberate design goal:
the whole project must run without paid keys or downloads (see ADR-0002).
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

#: Set to any non-empty value to skip the ONNX model entirely (used in tests/CI).
FORCE_HASH_ENV = "CIM_FORCE_HASH_EMBEDDINGS"


class HashEmbeddings(Embeddings):
    """Deterministic offline embeddings based on signed feature hashing.

    Each token is hashed into one of ``dim`` buckets with a +/-1 sign; the
    resulting bag-of-words vector is L2-normalised. Identical texts always
    produce identical vectors, and texts sharing vocabulary land close in
    cosine space — sufficient for retrieval smoke tests and offline demos.
    """

    provider = "hash"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            index = digest % self.dim
            sign = 1.0 if (digest >> 16) % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            return vector
        return [component / norm for component in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class OnnxMiniLMEmbeddings(Embeddings):
    """LangChain adapter over chromadb's ONNX all-MiniLM-L6-v2 (384 dims).

    Raises on construction when the model cannot be loaded (e.g. no network
    for the first-time download) so callers can fall back explicitly.
    """

    provider = "onnx-minilm-l6-v2"

    def __init__(self) -> None:
        # Imported lazily: chromadb is heavy and this class may never be used.
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self._fn = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        # Force the model download/load now, so failure happens here and not
        # in the middle of an ingest run.
        self._fn(["warmup"])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in row] for row in self._fn(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def default_embeddings() -> Embeddings:
    """Best available embeddings: ONNX MiniLM if loadable, hash fallback otherwise."""
    if os.environ.get(FORCE_HASH_ENV):
        logger.info("%s set — using HashEmbeddings.", FORCE_HASH_ENV)
        return HashEmbeddings()
    try:
        return OnnxMiniLMEmbeddings()
    except Exception as exc:  # pragma: no cover - depends on network availability
        logger.warning(
            "ONNX MiniLM embeddings unavailable (%s: %s); falling back to deterministic "
            "HashEmbeddings. Retrieval quality will be reduced.",
            exc.__class__.__name__,
            exc,
        )
        return HashEmbeddings()


def embeddings_by_provider(provider: str) -> Embeddings:
    """Reconstruct the embedding backend recorded at ingest time.

    The index must be queried with the same embedding space it was built
    with; mixing backends silently returns garbage similarities.
    """
    if provider == HashEmbeddings.provider:
        return HashEmbeddings()
    if provider == OnnxMiniLMEmbeddings.provider:
        return OnnxMiniLMEmbeddings()
    raise ValueError(f"Unknown embeddings provider recorded in index: {provider!r}.")
