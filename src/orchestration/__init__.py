"""
Orchestration module powered by PydanticAI.
"""

from src.orchestration.base import BaseOrchestrator
from src.orchestration.tools import (
    MedicalAssistantDeps,
    KnowledgeSearchInput,
    PatientQuoteBookingInput,
    RAG_SEARCH_DESCRIPTION,
    QUOTE_BOOKING_DESCRIPTION,
    search_placidway_knowledge_base,
    record_patient_consultation_quote,
    search_knowledge_tool,
    record_quote_tool,
    CLINICAL_TOOLS,
)
from src.orchestration.pydantic_ai_agent import (
    PydanticAIAgentOrchestrator,
    create_pydantic_ai_agent,
)
from src.orchestration.service import OrchestrationService, get_orchestration_service
from src.orchestration.session_manager import SessionManager, session_manager
from src.orchestration.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Citation,
    GroundedResponseSchema,
    LeadSubmission,
    ContentGapItem,
)


def __getattr__(name: str):
    if name == "orchestration_service":
        return get_orchestration_service()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "BaseOrchestrator",
    "PydanticAIAgentOrchestrator",
    "MedicalAssistantDeps",
    "KnowledgeSearchInput",
    "PatientQuoteBookingInput",
    "RAG_SEARCH_DESCRIPTION",
    "QUOTE_BOOKING_DESCRIPTION",
    "search_placidway_knowledge_base",
    "record_patient_consultation_quote",
    "search_knowledge_tool",
    "record_quote_tool",
    "CLINICAL_TOOLS",
    "create_pydantic_ai_agent",
    "OrchestrationService",
    "get_orchestration_service",
    "orchestration_service",
    "SessionManager",
    "session_manager",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Citation",
    "GroundedResponseSchema",
    "LeadSubmission",
    "ContentGapItem",
]
