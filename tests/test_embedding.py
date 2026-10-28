"""
Unit tests for EmbeddingService and HybridRetrieverService (src/ingestion/embedding.py & src/retrieval/retrieve.py).
Tests native Qdrant dual-vector indexing, RRF hybrid retrieval, and .debug export generation.
"""

import json
from pathlib import Path
import pytest
from langchain_core.documents import Document
from qdrant_client import QdrantClient

from src.ingestion.embedding import EmbeddingService
from src.retrieval.retrieve import HybridRetrieverService
from src.utils.config import settings


@pytest.fixture
def in_memory_embedding_service(tmp_path):
    # Use in-memory Qdrant client to keep tests fast and isolated
    client = QdrantClient(":memory:")
    service = EmbeddingService(collection_name="test_placidway", client=client)
    return service


def test_embedding_service_indexing_and_debug_export(in_memory_embedding_service):
    service = in_memory_embedding_service

    sample_docs = [
        Document(
            page_content="[Document: Alternative Adenocarcinoma Package | Section: Pricing | Source: https://www.placidway.com/package/7903/]\n\n"
                         "### Table Summary: Package Pricing\n"
                         "The Out-Patient Program for adenocarcinoma costs $18,995 USD for 3 weeks.",
            metadata={
                "chunk_id": "page_2_table_1",
                "page_id": 2,
                "document_title": "Alternative Adenocarcinoma Package",
                "source_url": "https://www.placidway.com/package/7903/",
                "page_type": "Treatment Package",
                "section_path": "Pricing",
                "is_table": True,
                "raw_table": "| Out-Patient | 3 Weeks | $18,995 |",
                "key_figures": {"out-patient": 18995},
            },
        ),
        Document(
            page_content="[Document: ITC Profile | Section: Medical Leadership | Source: https://www.placidway.com/profile/5/]\n\n"
                         "Dr. Carlos Bautista is the Medical Director of Immunity Therapy Center in Tijuana Mexico.",
            metadata={
                "chunk_id": "page_1_chunk_5",
                "page_id": 1,
                "document_title": "ITC Immunity Therapy Center",
                "source_url": "https://www.placidway.com/profile/5/",
                "page_type": "Clinic Profile",
                "section_path": "Medical Leadership",
                "is_table": False,
                "raw_table": None,
                "key_figures": {},
            },
        ),
    ]

    indexed_count = service.index_documents(sample_docs)
    assert indexed_count == 2

    # Verify debug chunks file was created
    all_chunks_debug = settings.DEBUG_DIR / "chunks" / "all_chunks.json"
    assert all_chunks_debug.exists(), ".debug/chunks/all_chunks.json must exist"

    debug_data = json.loads(all_chunks_debug.read_text(encoding="utf-8"))
    assert len(debug_data) == 2
    assert debug_data[0]["chunk_id"] == "page_2_table_1"
    assert debug_data[0]["key_figures"] == {"out-patient": 18995}


def test_native_rrf_hybrid_search_and_debug_retrieval(in_memory_embedding_service):
    service = in_memory_embedding_service

    docs = [
        Document(
            page_content="[Document: Adenocarcinoma Package | Section: Cost]\n"
                         "Out-Patient Adenocarcinoma Program costs $18,995 USD for 3 weeks at ITC.",
            metadata={"chunk_id": "c1", "source_url": "https://placidway.com/p1", "document_title": "Adeno", "is_table": True},
        ),
        Document(
            page_content="[Document: Adrenal Package | Section: Cost]\n"
                         "Adrenal Cancer Treatment In-Patient Program costs $30,000 USD for 3 weeks at ITC.",
            metadata={"chunk_id": "c2", "source_url": "https://placidway.com/p2", "document_title": "Adrenal", "is_table": True},
        ),
        Document(
            page_content="[Document: ITC Profile | Section: Doctors]\n"
                         "Dr. Carlos Bautista and Dr. David Alvarez treat cancer patients at ITC in Tijuana.",
            metadata={"chunk_id": "c3", "source_url": "https://placidway.com/p3", "document_title": "Doctors", "is_table": False},
        ),
    ]
    service.index_documents(docs)

    # 1. Test hybrid search with RRF
    results = service.search(query="How much does adenocarcinoma cost at ITC?", k=2)
    assert len(results) > 0
    top_doc = results[0]
    assert "Adenocarcinoma" in top_doc.page_content or "18,995" in top_doc.page_content

    # 2. Verify debug retrieval log was created
    last_retrieval_file = settings.DEBUG_DIR / "retrievals" / "last_retrieval.json"
    assert last_retrieval_file.exists(), ".debug/retrievals/last_retrieval.json must exist"

    retrieval_data = json.loads(last_retrieval_file.read_text(encoding="utf-8"))
    assert retrieval_data["query"] == "How much does adenocarcinoma cost at ITC?"
    assert len(retrieval_data["chunks"]) > 0
    assert retrieval_data["chunks"][0]["rank"] == 1


def test_hybrid_retriever_service_wrapper(in_memory_embedding_service):
    hybrid = HybridRetrieverService(embedding_service=in_memory_embedding_service)
    docs = [
        Document(
            page_content="Hyperthermia and biomagnetic therapy at Immunity Therapy Center.",
            metadata={"chunk_id": "c_hyp", "document_title": "Therapies"},
        )
    ]
    hybrid.refresh_index(docs)

    retrieved = hybrid.retrieve(query="biomagnetic therapy", k=1)
    assert len(retrieved) == 1
    assert "biomagnetic" in retrieved[0].page_content
