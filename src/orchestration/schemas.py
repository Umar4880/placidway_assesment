"""
Pydantic schemas and data contracts for orchestration, chat API, citations, leads, and content gaps.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class Citation(BaseModel):
    title: str = Field(description="Page title of the source citation")
    url: str = Field(description="Exact source URL from the 7 authorized pages")
    page_type: Optional[str] = Field(default=None, description="Type of page: Clinic Profile, Treatment Package, etc.")
    snippet: Optional[str] = Field(default=None, description="Relevant excerpt or supporting text from the source")


class GroundedResponseSchema(BaseModel):
    intent: Literal["greeting", "out_of_scope", "medical_advice_refusal", "booking_or_quote", "knowledge_query"] = Field(
        description="Classified user query intent"
    )
    answer: str = Field(
        description="The strictly grounded answer text, or polite refusal/clarification"
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Exact citations from retrieved authorized documents (empty for greetings/refusals)"
    )
    show_medical_disclaimer: bool = Field(
        default=False,
        description="True if query or answer touches upon treatments, procedures, or medical conditions"
    )
    is_content_gap: bool = Field(
        default=False,
        description="True if the user asked a valid medical travel question that cannot be answered from the 7 pages"
    )
    trigger_lead_capture: bool = Field(
        default=False,
        description="True if user asked to book, requested a custom quote, or hit a content gap"
    )
    detected_language: str = Field(
        default="en",
        description="ISO 639-1 code of the user query language (e.g., 'en', 'es', 'fr', 'ar')"
    )


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="Current user message")
    session_id: Optional[str] = Field(default="default-session", description="Session ID for conversation history")
    pattern: Optional[str] = Field(
        default="pydantic_ai",
        description="Orchestrator engine identifier (defaults to pydantic_ai)"
    )
    history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="Previous turns in the conversation"
    )


class ChatResponse(BaseModel):
    answer: str
    pattern_used: str = "pydantic_ai"
    citations: List[Citation] = Field(default_factory=list)
    show_medical_disclaimer: bool = False
    is_content_gap: bool = False
    trigger_lead_capture: bool = False
    detected_language: str = "en"
    latency_seconds: Optional[float] = None
    thought: Optional[str] = None
    thought_duration: Optional[float] = None


class LeadSubmission(BaseModel):
    name: str = Field(..., min_length=2, description="Patient / User full name")
    email: str = Field(..., description="Contact email address")
    treatment_interest: Optional[str] = Field(default="Alternative Cancer Treatment (ITC)", description="Target procedure or clinic of interest")
    phone: Optional[str] = Field(default=None, description="Contact phone number")
    country: Optional[str] = Field(default=None, description="Country of residence")
    notes: Optional[str] = Field(default=None, description="Optional patient notes or questions")
    session_id: Optional[str] = Field(default=None, description="Associated chat session ID")


class ContentGapItem(BaseModel):
    id: Optional[int] = None
    query: str
    standalone_query: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
