"""RAG pipeline: local embeddings, Chroma ingestion and semantic search."""

COLLECTION_NAME = "crypto_knowledge"

#: File written next to the Chroma index recording which embedding backend
#: built it, so search-time code reconstructs the same embedding space.
EMBEDDINGS_MARKER = "cim_embeddings.json"

from .embeddings import HashEmbeddings, default_embeddings  # noqa: E402
from .search import KnowledgeBase, KnowledgeBaseError  # noqa: E402

__all__ = [
    "COLLECTION_NAME",
    "EMBEDDINGS_MARKER",
    "HashEmbeddings",
    "default_embeddings",
    "KnowledgeBase",
    "KnowledgeBaseError",
]
