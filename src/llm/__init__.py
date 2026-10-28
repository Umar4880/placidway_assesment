"""
LLM abstraction layer for PlacidWay Grounded Medical Knowledge Assistant.
Provides unified model clients, structured outputs, prompt engineering, and table summarization.
"""

from src.llm.schemas import (
    IntentType,
    IntentClassification,
    SourceCitation,
    GroundedAnswer,
    TableSummary,
)
from src.llm.client import get_llm, get_dense_embeddings
from src.llm.prompts import (
    SYSTEM_GROUNDING_PROMPT,
    TABLE_SUMMARIZER_PROMPT,
    QUERY_REWRITER_PROMPT,
    INTENT_ROUTER_PROMPT,
    CLINICAL_DISCLAIMER,
)
from src.llm.table_summarizer import TableSummarizerService

__all__ = [
    "IntentType",
    "IntentClassification",
    "SourceCitation",
    "GroundedAnswer",
    "TableSummary",
    "get_llm",
    "get_dense_embeddings",
    "SYSTEM_GROUNDING_PROMPT",
    "TABLE_SUMMARIZER_PROMPT",
    "QUERY_REWRITER_PROMPT",
    "INTENT_ROUTER_PROMPT",
    "CLINICAL_DISCLAIMER",
    "TableSummarizerService",
]
