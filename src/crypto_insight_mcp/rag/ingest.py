"""Index ``knowledge_base/*.md`` into a persistent Chroma collection.

Run as a module::

    python -m crypto_insight_mcp.rag.ingest

Environment variables:

* ``CIM_CHROMA_DIR`` — Chroma persist directory (default ``.chroma``).
* ``CIM_KB_DIR`` — source directory with ``*.md`` documents (default ``knowledge_base``).
* ``CIM_FORCE_HASH_EMBEDDINGS`` — skip the ONNX model, use the hash fallback.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import COLLECTION_NAME, EMBEDDINGS_MARKER
from .embeddings import default_embeddings

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


def load_documents(kb_dir: Path) -> list[Document]:
    """Read and chunk every markdown file in ``kb_dir``."""
    files = sorted(kb_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(
            f"No .md documents found in {kb_dir}. Add documents or set CIM_KB_DIR."
        )
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    documents: list[Document] = []
    for path in files:
        for chunk in splitter.split_text(path.read_text(encoding="utf-8")):
            documents.append(Document(page_content=chunk, metadata={"source": path.name}))
    return documents


def ingest(
    kb_dir: str | Path | None = None,
    persist_dir: str | Path | None = None,
    embeddings: Embeddings | None = None,
) -> int:
    """(Re)build the Chroma index from the knowledge base. Returns the chunk count."""
    # Heavy imports kept local so `import crypto_insight_mcp` stays fast.
    import chromadb
    from chromadb.config import Settings
    from langchain_chroma import Chroma

    kb_path = Path(kb_dir or os.environ.get("CIM_KB_DIR", "knowledge_base"))
    persist_path = Path(persist_dir or os.environ.get("CIM_CHROMA_DIR", ".chroma"))
    embeddings = embeddings or default_embeddings()

    documents = load_documents(kb_path)

    client = chromadb.PersistentClient(
        path=str(persist_path), settings=Settings(anonymized_telemetry=False)
    )
    # Rebuild from scratch: re-running ingest must not duplicate chunks.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # collection did not exist yet

    store = Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
    )
    store.add_documents(documents)

    provider = getattr(embeddings, "provider", embeddings.__class__.__name__)
    (persist_path / EMBEDDINGS_MARKER).write_text(
        json.dumps({"provider": provider}), encoding="utf-8"
    )
    return len(documents)


def main() -> None:
    count = ingest()
    persist_path = os.environ.get("CIM_CHROMA_DIR", ".chroma")
    print(f"Ingested {count} chunks into Chroma collection {COLLECTION_NAME!r} at {persist_path}/")


if __name__ == "__main__":
    main()
