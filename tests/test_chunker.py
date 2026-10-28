"""
Unit tests for HeaderAwareChunker (src/retrieval/chunker.py).
Tests table extraction, breadcrumb context injection, short chunk merging, and metadata tracking.
"""

from pathlib import Path
import pytest
from src.ingestion.chunker import HeaderAwareChunker
from src.ingestion.urls import AUTHORIZED_URLS


def test_chunker_page_2_package():
    chunker = HeaderAwareChunker()
    page_files = list(Path("data/markdown").glob("page_2_*.md"))
    assert page_files, "page_2 markdown must exist in data/markdown/"

    markdown_text = page_files[0].read_text(encoding="utf-8")
    meta = AUTHORIZED_URLS[1]

    chunks = chunker.chunk_markdown(markdown_text, meta)
    assert len(chunks) > 5

    # 1. Verify breadcrumb context on every single chunk
    for chunk in chunks:
        assert chunk.page_content.startswith("[Document:")
        assert "Source: https://www.placidway.com/package/7903/" in chunk.page_content
        assert chunk.metadata["source_url"] == meta["url"]
        assert chunk.metadata["document_title"] == meta["title"]
        assert chunk.metadata["page_type"] == (meta.get("page_type") or meta.get("type"))

    # 2. Verify Table Chunk
    table_chunks = [c for c in chunks if c.metadata.get("is_table")]
    assert len(table_chunks) >= 1
    table_chunk = table_chunks[0]

    # Verify summary text contains key numbers
    assert "18,995" in table_chunk.page_content or "18995" in table_chunk.page_content
    assert "30,000" in table_chunk.page_content or "30000" in table_chunk.page_content

    # Verify raw table is intact in metadata
    raw_tbl = table_chunk.metadata.get("raw_table")
    assert raw_tbl is not None
    assert "| Out-Patient Program | 3 Weeks | $18,995 |" in raw_tbl
    assert "| In-Patient Program | 3 Weeks | $30,000 |" in raw_tbl

    # Verify extracted key figures
    assert table_chunk.metadata["key_figures"].get("out-patient_program") == 18995
    assert table_chunk.metadata["key_figures"].get("in-patient_program") == 30000


def test_chunker_merges_small_sections():
    chunker = HeaderAwareChunker(min_chunk_words=30)
    text = """
# Alternative Cancer Treatment

## Doctor Overview
Founder and leadership.

## Doctor Biography
Dr. Carlos Bautista has two decades of experience treating complex cancer cases with compassion and holistic medicine.
    """.strip()

    meta = {"title": "Test Doc", "url": "https://example.com", "type": "Profile", "id": 99}
    chunks = chunker.chunk_markdown(text, meta)

    # Short 3-word section "Founder and leadership" should be merged
    assert any("Founder and leadership" in c.page_content and "Dr. Carlos Bautista" in c.page_content for c in chunks)


def test_chunk_all_across_all_markdown_files():
    chunker = HeaderAwareChunker()
    all_chunks = chunker.chunk_all()
    assert len(all_chunks) > 50, "Total chunks across 7 files should be substantive"

    # Verify that all 7 pages are represented in chunk metadata
    represented_pages = {c.metadata["page_id"] for c in all_chunks}
    for expected_id in [1, 2, 3, 4, 5, 6, 7]:
        assert expected_id in represented_pages, f"Page {expected_id} must have generated chunks"

    # Verify table chunks exist
    table_chunks = [c for c in all_chunks if c.metadata.get("is_table")]
    assert len(table_chunks) >= 5, "At least 5 tables across the 7 pages should be extracted"

