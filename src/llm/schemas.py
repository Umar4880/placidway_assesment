"""
Pydantic Schemas for Structured LLM Outputs and Retrieval Operations.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """Enumeration of user intent categories."""
    PRICING_PACKAGE = "PRICING_PACKAGE"           # Costs, package prices ($18,995, $30,000), inclusions, exclusions
    CLINICAL_FAQ = "CLINICAL_FAQ"                 # Therapies (hyperthermia, biomagnetic), conditions treated, process
    DOCTOR_FACILITY = "DOCTOR_FACILITY"           # Dr. Carlos Bautista, medical team, Tijuana location, credentials
    LEAD_SUBMISSION = "LEAD_SUBMISSION"           # Contact, quote request, booking, lead capture
    MEDICAL_ADVICE_REFUSAL = "MEDICAL_ADVICE_REFUSAL" # Personal diagnosis, prescription, emergency, stopping standard chemo
    OUT_OF_SCOPE = "OUT_OF_SCOPE"                 # General banter, unrelated questions, non-authorized clinics


class IntentClassification(BaseModel):
    """Structured output for two-stage intent routing and query rewriting."""
    intent: IntentType = Field(
        ...,
        description="The primary intent category for the user query."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the classified intent."
    )
    rewritten_query: str = Field(
        ...,
        description="Self-contained query resolved with conversational history, entities, and clinical terms."
    )
    requires_retrieval: bool = Field(
        True,
        description="Whether this query needs grounding via the Qdrant knowledge base."
    )
    rationale: Optional[str] = Field(
        None,
        description="Brief reasoning for the chosen intent and rewriting strategy."
    )


class SourceCitation(BaseModel):
    """Clinical source citation grounding an answer."""
    title: str = Field(..., description="Document or page title.")
    url: str = Field(..., description="Canonical source URL on PlacidWay.")
    snippet: Optional[str] = Field(None, description="Direct supporting quote or key fact from the source.")


class GroundedAnswer(BaseModel):
    """Structured clinical response strictly grounded in authorized documents."""
    answer: str = Field(
        ...,
        description="The clinical response strictly derived from retrieved evidence with zero hallucinations."
    )
    citations: List[SourceCitation] = Field(
        default_factory=list,
        description="Exact PlacidWay source URLs and document titles supporting the facts stated."
    )
    confidence: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Model confidence in factual grounding against retrieved documents."
    )
    disclaimer: str = Field(
        ...,
        description="Mandatory medical disclaimer informing user this is informational and not medical advice."
    )
    suggested_follow_ups: List[str] = Field(
        default_factory=list,
        description="2-3 relevant clinical or logistical follow-up questions."
    )
    is_refusal: bool = Field(
        False,
        description="True if the query was refused due to medical diagnosis safety or out-of-scope boundaries."
    )


class TableSummary(BaseModel):
    """Semantic table summary paired with raw markdown table."""
    title: str = Field(..., description="Title or section context of the table.")
    summary: str = Field(
        ...,
        description="Natural language summary detailing all procedures, costs, durations, and terms."
    )
    key_figures: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted key numbers, prices (e.g. {'outpatient': 18995, 'inpatient': 30000}), and durations."
    )
    raw_table: str = Field(..., description="Original raw GitHub-Flavored Markdown table representation.")
