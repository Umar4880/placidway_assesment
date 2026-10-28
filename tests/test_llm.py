"""
Unit tests for the LLM module (src/llm/).
Tests schemas, prompt formatting, client factory fallbacks, and table summarization.
"""

import pytest
from src.llm.schemas import (
    IntentType,
    IntentClassification,
    SourceCitation,
    GroundedAnswer,
    TableSummary,
)
from src.llm.prompts import (
    SYSTEM_GROUNDING_PROMPT,
    TABLE_SUMMARIZER_PROMPT,
    QUERY_REWRITER_PROMPT,
    INTENT_ROUTER_PROMPT,
    CLINICAL_DISCLAIMER,
)
from src.llm.client import get_llm, get_dense_embeddings, get_sparse_embeddings
from src.llm.table_summarizer import TableSummarizerService


def test_intent_classification_schema():
    classification = IntentClassification(
        intent=IntentType.PRICING_PACKAGE,
        confidence=0.98,
        rewritten_query="What is the price of the adenocarcinoma package at ITC Tijuana?",
        requires_retrieval=True,
        rationale="User asking about package pricing.",
    )
    assert classification.intent == IntentType.PRICING_PACKAGE
    assert classification.confidence == 0.98
    assert classification.requires_retrieval is True


def test_grounded_answer_schema():
    citation = SourceCitation(
        title="Alternative Adenocarcinoma Cancer Treatment Package",
        url="https://www.placidway.com/package/7903/...",
        snippet="Out-Patient Program is $18,995 for 3 weeks.",
    )
    answer = GroundedAnswer(
        answer="The outpatient adenocarcinoma treatment package at ITC is $18,995 for 3 weeks.",
        citations=[citation],
        confidence=1.0,
        disclaimer=CLINICAL_DISCLAIMER,
        suggested_follow_ups=["What is included in the outpatient program?", "What are the inpatient costs?"],
        is_refusal=False,
    )
    assert len(answer.citations) == 1
    assert "18,995" in answer.answer
    assert "Disclaimer:" in answer.disclaimer


def test_prompts_formatting():
    grounding = SYSTEM_GROUNDING_PROMPT.format(
        context="[Doc 1] Test Context", query="How much does it cost?"
    )
    assert "Test Context" in grounding
    assert "How much does it cost?" in grounding

    table_p = TABLE_SUMMARIZER_PROMPT.format(
        document_title="ITC Profile",
        section_title="Pricing",
        source_url="https://placidway.com",
        intro_text="Understanding cancer treatment costs abroad.",
        table_notes="Inpatient care includes 24/7 supervision.",
        table_markdown="| A | B |\n|---|---|\n| 1 | 2 |",
    )
    assert "ITC Profile" in table_p
    assert "Understanding cancer treatment" in table_p

    router_p = INTENT_ROUTER_PROMPT.format(
        chat_history="User: Hello\nAssistant: Hi", user_query="What about chemo?"
    )
    assert "What about chemo?" in router_p


def test_llm_and_embeddings_factory():
    llm = get_llm()
    assert llm is not None

    dense = get_dense_embeddings()
    assert dense is not None
    vec = dense.embed_query("Immunity Therapy Center Tijuana")
    assert len(vec) > 0
    assert isinstance(vec[0], float)

    sparse = get_sparse_embeddings()
    assert sparse is not None
    sparse_res = list(sparse.embed(["Out-Patient Program $18,995"]))
    assert len(sparse_res) == 1
    assert len(sparse_res[0].indices) > 0


def test_table_summarizer_extracts_figures():
    raw_table = """
| Program Type | Duration | Total Cost (USD) |
| --- | --- | --- |
| Out-Patient Program | 3 Weeks | $18,995 |
| In-Patient Program | 3 Weeks | $30,000 |
    """.strip()

    summarizer = TableSummarizerService()
    result = summarizer.summarize(
        table_markdown=raw_table,
        document_title="Alternative Adenocarcinoma Cancer Treatment Package",
        section_title="Alternative Cancer Treatment Cost and Packages",
        source_url="https://www.placidway.com/package/7903/Alternative-Adenocarcinoma...",
    )

    assert isinstance(result, TableSummary)
    assert "18,995" in result.summary or "18995" in result.summary
    assert "30,000" in result.summary or "30000" in result.summary
    assert result.key_figures.get("out-patient_program") == 18995
    assert result.key_figures.get("in-patient_program") == 30000
    assert result.raw_table == raw_table
