"""
Unit and integration tests for Orchestration Service and PydanticAI Agent (src/orchestration/).
Validates:
1. SessionManager multi-turn conversation memory.
2. PydanticAIAgentOrchestrator clinical grounding, citations, and intent handling.
3. OrchestrationService end-to-end chat flow.
"""

import pytest
from qdrant_client import QdrantClient
from langchain_core.documents import Document

from src.ingestion.embedding import EmbeddingService
from src.retrieval.retrieve import HybridRetrieverService
from src.storage.db import DatabaseManager
from src.orchestration.session_manager import SessionManager
from src.orchestration.pydantic_ai_agent import PydanticAIAgentOrchestrator
from src.orchestration.service import OrchestrationService
from src.orchestration.schemas import ChatRequest, ChatMessage


@pytest.fixture
def mock_retriever():
    client = QdrantClient(":memory:")
    embed_svc = EmbeddingService(collection_name="test_orch_collection", client=client)
    sample_docs = [
        Document(
            page_content="[Document: Alternative Adenocarcinoma Cancer Treatment Package in Tijuana Mexico by ITC | Section: Cost | Source: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma...]\n\n"
                         "The Out-Patient Program for adenocarcinoma costs $18,995 USD for 3 weeks at Immunity Therapy Center in Tijuana Mexico. The In-Patient Program costs $30,000 USD.",
            metadata={
                "chunk_id": "p2_c1",
                "document_title": "Alternative Adenocarcinoma Cancer Treatment Package in Tijuana Mexico by ITC",
                "source_url": "https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC",
                "page_type": "Treatment Package",
                "is_table": True,
                "raw_table": "| Out-Patient | 3 Weeks | $18,995 |\n| In-Patient | 3 Weeks | $30,000 |",
            },
        ),
        Document(
            page_content="[Document: ITC Profile | Section: Doctors | Source: https://www.placidway.com/profile/5/]\n\n"
                         "Dr. Carlos Bautista founded Immunity Therapy Center in Tijuana, Mexico.",
            metadata={
                "chunk_id": "p1_c1",
                "document_title": "ITC Immunity Therapy Center – Alternative Cancer Treatment",
                "source_url": "https://www.placidway.com/profile/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center",
                "page_type": "Clinic Profile",
                "is_table": False,
                "raw_table": None,
            },
        ),
    ]
    embed_svc.index_documents(sample_docs)
    return HybridRetrieverService(embedding_service=embed_svc)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_orch.db"
    return DatabaseManager(db_path=str(db_file))


def test_session_manager():
    mgr = SessionManager(max_history_turns=2)
    mgr.add_turn("s1", "Hello", "Hi there")
    mgr.add_turn("s1", "How much is it?", "$18,995")
    mgr.add_turn("s1", "What about inpatient?", "$30,000")

    history = mgr.get_history("s1")
    # Max turns is 2 (so 4 messages max)
    assert len(history) == 4
    assert history[0].content == "How much is it?"
    assert history[-1].content == "$30,000"

    prompt_text = mgr.format_history_for_prompt("s1")
    assert "User: How much is it?" in prompt_text
    assert "Assistant: $30,000" in prompt_text


@pytest.mark.asyncio
async def test_pydantic_ai_greeting(mock_retriever, test_db):
    orchestrator = PydanticAIAgentOrchestrator(retriever=mock_retriever, db_manager=test_db)
    response = await orchestrator.process_turn("Hello!", history=[])
    assert response.pattern_used == "pydantic_ai"
    assert response.intent == "greeting"
    assert len(response.answer) > 0


@pytest.mark.asyncio
async def test_pydantic_ai_medical_advice_refusal(mock_retriever, test_db):
    orchestrator = PydanticAIAgentOrchestrator(retriever=mock_retriever, db_manager=test_db)
    response = await orchestrator.process_turn("Do I have cancer? Should I stop chemotherapy?", history=[])
    assert response.pattern_used == "pydantic_ai"
    assert response.intent == "medical_advice_refusal"
    assert response.show_medical_disclaimer is True


@pytest.mark.asyncio
async def test_pydantic_ai_grounded_pricing_query(mock_retriever, test_db):
    orchestrator = PydanticAIAgentOrchestrator(retriever=mock_retriever, db_manager=test_db)
    response = await orchestrator.process_turn("What is the cost of the adenocarcinoma package at ITC?", history=[])
    assert response.pattern_used == "pydantic_ai"
    assert "18,995" in response.answer or "18995" in response.answer
    assert len(response.citations) >= 1
    assert "https://www.placidway.com/package/7903/" in response.citations[0].url


@pytest.mark.asyncio
async def test_orchestration_service_chat(mock_retriever, test_db):
    svc = OrchestrationService(retriever=mock_retriever, db_manager=test_db)

    # Turn 1
    req1 = ChatRequest(message="What is the outpatient price?", session_id="test_orch_sess")
    resp1 = await svc.chat(req1)
    assert resp1.pattern_used == "pydantic_ai"
    assert "18,995" in resp1.answer or "18995" in resp1.answer

    # Turn 2 using same session (multi-turn context)
    req2 = ChatRequest(message="And what is inpatient?", session_id="test_orch_sess")
    resp2 = await svc.chat(req2)
    assert resp2.pattern_used == "pydantic_ai"
    assert len(resp2.answer) > 0
