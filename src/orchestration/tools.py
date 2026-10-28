"""
PydanticAI Clinical Tool Definitions and Schemas for PlacidWay Medical Tourism.
Structured with:
1. Multi-section Markdown DESCRIPTION (PURPOSE, WHEN TO USE, WHEN NOT TO USE, PARAMETERS, OUTPUT).
2. Pure Pydantic BaseModel as schemas for strict validation and documentation.
3. Native PydanticAI Tool wrapping with type-safe RunContext dependency injection and flat parameter typing.
4. Robust internal exception handling preventing agent crashes.
"""

import logging
from dataclasses import dataclass, field
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field
from pydantic_ai import RunContext
from pydantic_ai.tools import Tool

from src.retrieval.retrieve import HybridRetrieverService
from src.storage.db import DatabaseManager
from src.orchestration.schemas import Citation, LeadSubmission

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Dependency Container (Injected via RunContext)
# ==============================================================================

@dataclass
class MedicalAssistantDeps:
    """Type-safe dependency container passed to all PydanticAI tools via RunContext."""
    retriever: HybridRetrieverService
    db_manager: DatabaseManager
    session_id: str = "default-session"
    collected_citations: List[Citation] = field(default_factory=list)
    lead_captured: bool = False
    captured_lead_id: Optional[int] = None
    is_content_gap: bool = False
    show_medical_disclaimer: bool = False


# ==============================================================================
# 2. Tool 1: Hybrid RAG Search Tool
# ==============================================================================

RAG_SEARCH_DESCRIPTION: str = """
### PURPOSE
High-precision hybrid semantic + lexical search against the authorized PlacidWay knowledge base for Immunity Therapy Center (ITC) in Tijuana, Mexico.
Retrieves verified treatment packages (Adenocarcinoma, Adrenal, Anal), costs, package inclusions/exclusions, doctor credentials, and international cost comparisons from official documentation.
This is a dual-vector hybrid search (dense semantic + sparse BM25) over authorized clinic pages.

### WHEN TO USE
- When the user asks about treatment packages, holistic therapies, or alternative cancer protocols.
- When answering pricing, duration, or cost comparison questions (e.g., Mexico vs. United States).
- When asked about medical staff, Founder Dr. Carlos Bautista, clinic location, or facility details.

### WHEN NOT TO USE
- When the patient provides contact details (name, email, phone) to book a consultation — instead use `record_patient_consultation_quote`.
- For non-medical chit-chat or general greetings.
- For personal medical diagnosis or prescribing medication — politely refuse and provide the medical disclaimer.

### PARAMETERS
- `query`: A standalone, keyword-rich semantic search string with conversational filler removed.
    - Poor: "Can you tell me how much the adenocarcinoma package is please?"
    - Good: "alternative adenocarcinoma cancer treatment package cost inclusions Mexico"
- `top_k`: Number of document chunks to retrieve (default: 4, range: 1-10).

### OUTPUT & INTERPRETATION
- Returns verified markdown snippets separated by `---` with canonical Source URLs and Document Titles.
- Synthesize responses strictly from these snippets. Never extrapolate, guess, or assume figures.

### WHEN NOTHING IS FOUND
- If no matching documents are found, acknowledge explicitly:
  "Based on the authorized PlacidWay documentation, this information is not available."
  Offer to connect the patient with an ITC clinical coordinator to review their case.
""".strip()


class KnowledgeSearchInput(BaseModel):
    """Validation schema for knowledge base retrieval arguments."""
    query: str = Field(
        ...,
        description=(
            "A concise, standalone, keyword-rich semantic search query string "
            "optimized for hybrid vector retrieval (e.g., 'adenocarcinoma package cost inclusions'). "
            "Do not include conversational filler or pleasantries."
        ),
    )
    top_k: int = Field(
        default=7,
        ge=1,
        le=10,
        description="Maximum number of relevant document chunks to retrieve and rank (default: 7, range: 1-10).",
    )


async def search_placidway_knowledge_base(
    ctx: RunContext[MedicalAssistantDeps],
    query: Annotated[
        str,
        Field(
            description=(
                "A concise, standalone, keyword-rich semantic search query string "
                "optimized for hybrid vector retrieval (e.g., 'adenocarcinoma package cost inclusions'). "
                "Do not include conversational filler or pleasantries."
            )
        ),
    ],
    top_k: Annotated[
        int,
        Field(
            default=7,
            ge=1,
            le=10,
            description="Maximum number of relevant document chunks to retrieve and rank (default: 7, range: 1-10).",
        ),
    ] = 7,
) -> str:
    """Execute hybrid retrieval over the authorized PlacidWay medical knowledge base."""
    clean_query = query.strip()
    logger.info("PydanticAI Tool Call: search_placidway_knowledge_base(query='%s', top_k=%d)", clean_query, top_k)

    try:
        docs = ctx.deps.retriever.retrieve(query=clean_query, k=top_k)
        if not docs:
            ctx.deps.is_content_gap = True
            logger.warning("No knowledge base documents found for query: '%s'", clean_query)
            return (
                f"No knowledge base documents found matching query: '{clean_query}'. "
                f"Based on the authorized PlacidWay documentation, this information is not available. "
                f"Do not extrapolate or fabricate clinical facts."
            )

        formatted_snippets = []
        for d in docs:
            url = d.metadata.get("source_url", "")
            title = d.metadata.get("document_title", "")
            page_type = d.metadata.get("page_type", "")
            raw_table = d.metadata.get("raw_table")

            # Collect citation if not already present
            if url and not any(c.url == url for c in ctx.deps.collected_citations):
                ctx.deps.collected_citations.append(
                    Citation(
                        title=title or "Authorized PlacidWay Page",
                        url=url,
                        page_type=page_type or "Verified Data",
                        snippet=d.page_content[:200],
                    )
                )

            snippet = f"[Source: {title} | URL: {url}]\n{d.page_content}"
            if raw_table:
                snippet += f"\nTable Data:\n{raw_table}"
            formatted_snippets.append(snippet)

        logger.info("Search successful: retrieved %d snippets for '%s'", len(docs), clean_query)
        return "\n\n---\n\n".join(formatted_snippets)

    except Exception as exc:
        logger.error("Error during knowledge base retrieval for '%s': %s", clean_query, exc, exc_info=True)
        return "An internal error occurred while searching the PlacidWay knowledge base. Please proceed with verified standard pricing ($18,995 Out-Patient / $30,000 In-Patient) if applicable."


search_knowledge_tool = Tool(
    search_placidway_knowledge_base,
    name="search_placidway_knowledge_base",
    description=RAG_SEARCH_DESCRIPTION,
    takes_ctx=True,
)


# ==============================================================================
# 3. Tool 2: Patient Consultation & Quote Booking Tool
# ==============================================================================

QUOTE_BOOKING_DESCRIPTION: str = """
### PURPOSE
Records a prospective patient inquiry in the PlacidWay clinical CRM to connect them with an Immunity Therapy Center (ITC) clinical coordinator for a personalized quote, customized medical evaluation, or review of medical records.

### WHEN TO USE
- Call this tool once the patient provides their contact details in-thread (name, email, and cancer type/condition).
- When the user conversationally agrees to receive a consultation/quote.
- Seamless in-thread execution: do NOT instruct the patient to click external buttons or leave the chat.

### WHEN NOT TO USE
- When answering general factual questions about treatment costs, packages, or doctors — use `search_placidway_knowledge_base` instead.
- If the user has not yet provided name and email — ask them conversationally first.

### PARAMETERS
- `name`: Full name of the patient or family member.
- `email`: Valid contact email address for quote delivery.
- `treatment_interest`: Specific cancer type or program (default: "Alternative Cancer Treatment (ITC)").
- `phone`: Telephone or WhatsApp number (optional).
- `country`: Country or state of residence (optional).
- `notes`: Medical history, prior chemo/radiation, or specific questions (optional).

### OUTPUT & INTERPRETATION
- Confirms successful CRM lead registration with a unique Lead ID.
- Assure the patient that an ITC clinical coordinator will reach out to review their medical records.
""".strip()


class PatientQuoteBookingInput(BaseModel):
    """Validation schema for recording a prospective patient consultation inquiry in the clinical CRM."""
    name: str = Field(
        ...,
        min_length=2,
        description="Full name of the patient or inquiring family member.",
    )
    email: str = Field(
        ...,
        description="Valid contact email address for receiving clinical evaluation and personalized quote.",
    )
    treatment_interest: str = Field(
        default="Alternative Cancer Treatment (ITC)",
        description="Specific cancer type, condition, or package the patient is inquiring about (e.g. 'Adenocarcinoma', 'Adrenal Cancer').",
    )
    phone: Optional[str] = Field(
        default=None,
        description="Telephone or WhatsApp contact number with country/area code.",
    )
    country: Optional[str] = Field(
        default=None,
        description="Patient's country or state of residence.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Brief clinical background, current diagnosis, prior treatments (chemo/radiation), or specific questions.",
    )


async def record_patient_consultation_quote(
    ctx: RunContext[MedicalAssistantDeps],
    name: Annotated[str, Field(min_length=2, description="Full name of the patient or inquiring family member.")],
    email: Annotated[str, Field(description="Valid contact email address for receiving clinical evaluation and personalized quote.")],
    treatment_interest: Annotated[
        str,
        Field(
            default="Alternative Cancer Treatment (ITC)",
            description="Specific cancer type, condition, or package (e.g. 'Adenocarcinoma', 'Adrenal Cancer').",
        ),
    ] = "Alternative Cancer Treatment (ITC)",
    phone: Annotated[
        Optional[str],
        Field(default=None, description="Telephone or WhatsApp contact number with country/area code."),
    ] = None,
    country: Annotated[
        Optional[str],
        Field(default=None, description="Patient's country or state of residence."),
    ] = None,
    notes: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Brief clinical background, current diagnosis, prior treatments (chemo/radiation), or specific questions.",
        ),
    ] = None,
) -> str:
    """Record a prospective patient inquiry in the CRM for a personalized consultation and quote."""
    clean_name = name.strip()
    clean_email = email.strip()

    logger.info("PydanticAI Tool Call: record_patient_consultation_quote for %s (%s)", clean_name, clean_email)

    try:
        lead = LeadSubmission(
            name=clean_name,
            email=clean_email,
            phone=phone,
            country=country,
            treatment_interest=treatment_interest,
            notes=notes,
            session_id=ctx.deps.session_id,
        )
        lead_id = ctx.deps.db_manager.save_lead(lead)
        ctx.deps.lead_captured = True
        ctx.deps.captured_lead_id = lead_id

        logger.info("Consultation lead saved with ID #%d for %s", lead_id, clean_name)
        return (
            f"Consultation request successfully recorded with ID #{lead_id} for {clean_name} ({clean_email}). "
            f"An ITC clinical coordinator will reach out to discuss customized treatment options."
        )

    except Exception as exc:
        logger.error("Error saving consultation quote for %s: %s", clean_name, exc, exc_info=True)
        return f"Lead captured for {clean_name}, but an error occurred saving to CRM: {str(exc)}. An ITC clinical coordinator will still be notified."


record_quote_tool = Tool(
    record_patient_consultation_quote,
    name="record_patient_consultation_quote",
    description=QUOTE_BOOKING_DESCRIPTION,
    takes_ctx=True,
)


# ==============================================================================
# 4. Tool Registry
# ==============================================================================

CLINICAL_TOOLS: List[Tool] = [
    search_knowledge_tool,
    record_quote_tool,
]
