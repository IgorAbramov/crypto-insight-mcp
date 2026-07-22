"""RAG pipeline tests: offline ingest + search with deterministic embeddings."""

from __future__ import annotations

import pytest

from crypto_insight_mcp.rag.embeddings import HashEmbeddings
from crypto_insight_mcp.rag.ingest import ingest
from crypto_insight_mcp.rag.search import KnowledgeBase, KnowledgeBaseError

CUSTODY_DOC = """# Custody note

Cold storage keeps private keys on devices that never touch the internet.
Hardware security modules and air-gapped signers protect client assets.
Withdrawals from cold storage require manual approval ceremonies.
"""

LISTING_DOC = """# Listing note

New tokens require a legal classification review and a security audit before
admission to trading. The listing committee votes and records minutes.
Delisting requires thirty days of customer notice.
"""


@pytest.fixture
def kb_dir(tmp_path):
    directory = tmp_path / "kb"
    directory.mkdir()
    (directory / "custody.md").write_text(CUSTODY_DOC, encoding="utf-8")
    (directory / "listing.md").write_text(LISTING_DOC, encoding="utf-8")
    return directory


def test_ingest_reports_chunk_count(kb_dir, tmp_path):
    count = ingest(kb_dir=kb_dir, persist_dir=tmp_path / "chroma", embeddings=HashEmbeddings())
    assert count >= 2  # both docs indexed (small docs -> one chunk each)


def test_search_finds_relevant_chunk_with_source(kb_dir, tmp_path):
    persist = tmp_path / "chroma"
    embeddings = HashEmbeddings()
    ingest(kb_dir=kb_dir, persist_dir=persist, embeddings=embeddings)

    kb = KnowledgeBase(persist_dir=persist, embeddings=embeddings)
    results = kb.search("cold storage private keys offline", k=2)

    assert results, "expected at least one result"
    top = results[0]
    assert top["source"] == "custody.md"
    assert "cold storage" in top["snippet"].lower()
    assert set(top) == {"source", "snippet", "score"}

    listing = kb.search("listing committee legal review before trading", k=2)
    assert listing[0]["source"] == "listing.md"


def test_reingest_replaces_collection(kb_dir, tmp_path):
    persist = tmp_path / "chroma"
    embeddings = HashEmbeddings()
    first = ingest(kb_dir=kb_dir, persist_dir=persist, embeddings=embeddings)
    second = ingest(kb_dir=kb_dir, persist_dir=persist, embeddings=embeddings)
    assert first == second  # rebuild, not append

    kb = KnowledgeBase(persist_dir=persist, embeddings=embeddings)
    results = kb.search("cold storage", k=10)
    sources = [row["source"] for row in results]
    assert sources.count("custody.md") == sources.count("listing.md")  # no duplicates


def test_missing_index_raises_actionable_error(tmp_path):
    kb = KnowledgeBase(persist_dir=tmp_path / "nowhere", embeddings=HashEmbeddings())
    with pytest.raises(KnowledgeBaseError, match="ingest"):
        kb.search("anything")


def test_ingest_fails_clearly_on_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="No .md documents"):
        ingest(kb_dir=empty, persist_dir=tmp_path / "chroma", embeddings=HashEmbeddings())


def test_hash_embeddings_are_deterministic():
    embeddings = HashEmbeddings()
    first = embeddings.embed_query("markets in crypto assets")
    second = embeddings.embed_query("markets in crypto assets")
    assert first == second
    assert len(first) == 384
    norm = sum(x * x for x in first)
    assert norm == pytest.approx(1.0)
