"""
PydanticAI-powered Clinical Grounded Agent Orchestrator.
Native PydanticAI agent architecture for PlacidWay Medical Tourism.

Features:
1. Type-safe dependency injection via RunContext[MedicalAssistantDeps].
2. Tools and input schemas loaded from src.orchestration.tools.
3. System prompt instructions loaded from prompt.md.
4. XML-structured multi-turn context formatting for pronoun resolution.
5. Factual grounding, conversational 1-by-1 lead intake, and citation tracking.
6. Native system event capture and streaming via run_stream_events.
7. Model resilience via native FallbackModel.
"""

import os
os.environ["PYDANTIC_AI_NO_BANNER"] = "1"

import time
import logging
from pathlib import Path
from typing import AsyncIterator, List, Optional

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartStartEvent,
    PartDeltaEvent,
    PartEndEvent,
    ThinkingPart,
    ThinkingPartDelta,
    TextPart,
    TextPartDelta,
)

from src.orchestration.base import BaseOrchestrator
from src.orchestration.schemas import (
    ChatMessage,
    ChatResponse,
)
from src.orchestration.tools import (
    MedicalAssistantDeps,
    CLINICAL_TOOLS,
)

from src.retrieval.retrieve import HybridRetrieverService
from src.storage.db import DatabaseManager
from src.utils.config import settings

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "prompt.md"


def load_system_prompt() -> str:
    """Load the XML-structured prompt instructions from prompt.md."""
    try:
        content = PROMPT_FILE.read_text(encoding="utf-8")
        if "<conversation_history>" in content:
            return content.split("<conversation_history>")[0].strip()
        return content.strip()
    except Exception as e:
        logger.warning("Could not read prompt.md (%s), falling back to default prompt", e)
        return "You are the official PlacidWay Medical Tourism Knowledge Assistant for Immunity Therapy Center in Tijuana, Mexico."


def create_pydantic_ai_agent() -> Agent[MedicalAssistantDeps, str]:
    """Factory creating and configuring the PydanticAI agent with NVIDIA as primary and Google Gemini as fallback."""
    models_chain = []

    # 1. Primary Model: NVIDIA NIM
    nvidia_key = getattr(settings, "NVIDIA_API_KEY", "") or os.environ.get("NVIDIA_API_KEY", "")
    nvidia_base_url = getattr(settings, "NVIDIA_BASE_URL", "") or "https://integrate.api.nvidia.com/v1"
    primary_model_name = getattr(settings, "PRIMARY_LLM_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")

    if nvidia_key:
        try:
            models_chain.append(
                OpenAIChatModel(
                    model_name=primary_model_name,
                    provider=OpenAIProvider(
                        base_url=nvidia_base_url,
                        api_key=nvidia_key,
                    ),
                )
            )
        except Exception as e:
            logger.warning("Failed to initialize NVIDIA primary model: %s", e)

    # 2. Fallback Model: Google Gemini
    google_key = settings.get_google_api_key() or os.environ.get("GEMINI_API_KEY", "")
    fallback_model_name = getattr(settings, "FALLBACK_LLM_MODEL", "gemini-3.1-flash-lite")

    if google_key and google_key != "your_gemini_api_key_here":
        os.environ["GEMINI_API_KEY"] = google_key
        try:
            models_chain.append(GoogleModel(fallback_model_name))
        except Exception as e:
            logger.warning("Failed to initialize Google fallback model: %s", e)

    if not models_chain:
        model_instance = "test"
    else:
        # FallbackModel seamlessly routes to fallback when primary encounters error or rate limit
        model_instance = FallbackModel(*models_chain) if len(models_chain) > 1 else models_chain[0]

    agent = Agent(
        model=model_instance,
        deps_type=MedicalAssistantDeps,
        system_prompt=load_system_prompt(),
        tools=CLINICAL_TOOLS,
        retries=3,
    )
    return agent


class PydanticAIAgentOrchestrator(BaseOrchestrator):
    """
    Linear, Type-Safe Agentic Orchestration using PydanticAI.
    Combines hybrid RAG retrieval and conversational consultation quote booking.
    """

    @property
    def pattern_name(self) -> str:
        return "pydantic_ai"

    def __init__(
        self,
        retriever: HybridRetrieverService,
        db_manager: Optional[DatabaseManager] = None,
    ):
        super().__init__(retriever)
        self.db_manager = db_manager or DatabaseManager()
        self.agent = create_pydantic_ai_agent()

    def _format_history_prompt(self, history: List[ChatMessage], current_query: str) -> str:
        """Build multi-turn context string in XML format for pronoun and follow-up resolution."""
        if not history:
            return f"<patient_query>\n{current_query}\n</patient_query>"

        history_lines = ["<conversation_history>"]
        for msg in history[-6:]:
            speaker = "patient" if msg.role == "user" else "assistant"
            history_lines.append(f"<{speaker}>{msg.content}</{speaker}>")
        history_lines.append("</conversation_history>")

        history_lines.append(f"\n<patient_query>\n{current_query}\n</patient_query>")
        return "\n".join(history_lines)

    async def process_turn(
        self,
        user_message: str,
        history: List[ChatMessage],
        session_id: str = "default-session",
    ) -> ChatResponse:
        """
        Execute synchronous conversation turn with the PydanticAI agent.
        """
        start_time = time.perf_counter()
        deps = MedicalAssistantDeps(
            retriever=self.retriever,
            db_manager=self.db_manager,
            session_id=session_id,
        )

        full_prompt = self._format_history_prompt(history, user_message)

        result = await self.agent.run(full_prompt, deps=deps)
        answer_text = str(result.output)
        elapsed = round(time.perf_counter() - start_time, 3)

        # Extract thinking/reasoning content if present in ModelResponse parts
        thought_parts = []
        for msg in result.all_messages():
            parts = getattr(msg, "parts", [])
            for p in parts:
                if getattr(p, "part_kind", None) == "thinking" or type(p).__name__ == "ThinkingPart":
                    c = getattr(p, "content", "")
                    if c:
                        thought_parts.append(str(c))
        thought_text = "\n\n".join(thought_parts) if thought_parts else None

        # Fallback: extract inline <think>...</think> if present in answer_text
        if not thought_text and "<think>" in answer_text and "</think>" in answer_text:
            s_idx = answer_text.find("<think>") + len("<think>")
            e_idx = answer_text.find("</think>")
            thought_text = answer_text[s_idx:e_idx].strip()
            answer_text = (answer_text[:answer_text.find("<think>")] + answer_text[e_idx + len("</think>"):].strip()).strip()

        return ChatResponse(
            answer=answer_text,
            pattern_used=self.pattern_name,
            citations=deps.collected_citations,
            show_medical_disclaimer=deps.show_medical_disclaimer,
            is_content_gap=deps.is_content_gap,
            trigger_lead_capture=deps.lead_captured,
            latency_seconds=elapsed,
            thought=thought_text,
            thought_duration=None,
        )

    async def process_turn_stream(
        self,
        user_message: str,
        history: List[ChatMessage],
        session_id: str = "default-session",
    ) -> AsyncIterator[dict]:
        """
        Stream the agent response tokens and reasoning traces natively using PydanticAI run_stream_events.
        Separates model reasoning/thinking tokens (Claude/ChatGPT style) from final answer markdown deltas.
        Yields trace events, thought events, delta events, and a final 'done' event with metadata & citations.
        """
        start_time = time.perf_counter()
        deps = MedicalAssistantDeps(
            retriever=self.retriever,
            db_manager=self.db_manager,
            session_id=session_id,
        )

        full_prompt = self._format_history_prompt(history, user_message)

        thought_chunks: List[str] = []
        thought_start: Optional[float] = None
        thought_done_emitted: bool = False
        thought_duration: Optional[float] = None

        answer_chunks: List[str] = []

        # Native PydanticAI event stream: traces, thoughts, and text deltas
        async with self.agent.run_stream_events(full_prompt, deps=deps) as stream:
            async for event in stream:
                # 1. Agent tool invocation dispatched
                if isinstance(event, FunctionToolCallEvent):
                    tool_name = event.part.tool_name
                    if tool_name == "search_placidway_knowledge_base":
                        query_arg = ""
                        if isinstance(event.part.args, dict):
                            query_arg = event.part.args.get("query", "")
                        elif isinstance(event.part.args, str):
                            query_arg = event.part.args
                        step_msg = f"Checking knowledge base for '{query_arg}'..." if query_arg else "Checking knowledge base..."
                        yield {
                            "event": "trace",
                            "data": {
                                "step": "rag_search",
                                "status": "running",
                                "message": step_msg,
                            },
                        }
                    elif tool_name == "record_patient_consultation_quote":
                        yield {
                            "event": "trace",
                            "data": {
                                "step": "crm",
                                "status": "running",
                                "message": "Recording patient consultation quote inquiry...",
                            },
                        }
                    else:
                        yield {
                            "event": "trace",
                            "data": {
                                "step": "tool_call",
                                "status": "running",
                                "message": f"Calling tool {tool_name}...",
                            },
                        }

                # 2. Agent tool execution completed
                elif isinstance(event, FunctionToolResultEvent):
                    tool_name = event.part.tool_name
                    if tool_name == "search_placidway_knowledge_base":
                        chunk_count = len(deps.collected_citations)
                        doc_word = "document chunks" if chunk_count != 1 else "document chunk"
                        yield {
                            "event": "trace",
                            "data": {
                                "step": "rag_retrieved",
                                "status": "done",
                                "message": f"Retrieved {chunk_count} verified {doc_word} from PlacidWay",
                            },
                        }
                    elif tool_name == "record_patient_consultation_quote":
                        yield {
                            "event": "trace",
                            "data": {
                                "step": "crm_saved",
                                "status": "done",
                                "message": "Consultation inquiry registered in clinical CRM",
                            },
                        }

                # 3. Model part start (either ThinkingPart or TextPart)
                elif isinstance(event, PartStartEvent):
                    part = event.part
                    part_kind = getattr(part, "part_kind", None)
                    is_thinking = part_kind == "thinking" or isinstance(part, ThinkingPart)
                    part_content = getattr(part, "content", None)

                    if is_thinking:
                        if thought_start is None:
                            thought_start = time.perf_counter()
                        if isinstance(part_content, str) and part_content:
                            thought_chunks.append(part_content)
                            yield {
                                "event": "thought",
                                "data": {"text": part_content},
                            }
                    else:
                        # Transition from thinking to final answer
                        if thought_chunks and not thought_done_emitted:
                            thought_done_emitted = True
                            thought_duration = round(time.perf_counter() - (thought_start or start_time), 1)
                            yield {
                                "event": "thought_done",
                                "data": {
                                    "duration": thought_duration,
                                    "text": "".join(thought_chunks),
                                },
                            }
                        if isinstance(part_content, str) and part_content:
                            answer_chunks.append(part_content)
                            yield {
                                "event": "delta",
                                "data": {"text": part_content},
                            }

                # 4. Model token deltas streamed incrementally
                elif isinstance(event, PartDeltaEvent):
                    delta = event.delta
                    delta_kind = getattr(delta, "part_delta_kind", None)
                    is_thinking = delta_kind == "thinking" or isinstance(delta, ThinkingPartDelta)
                    content_delta = getattr(delta, "content_delta", None)

                    if is_thinking:
                        if thought_start is None:
                            thought_start = time.perf_counter()
                        if content_delta:
                            thought_chunks.append(content_delta)
                            yield {
                                "event": "thought",
                                "data": {"text": content_delta},
                            }
                    else:
                        # Transition from thinking to final answer
                        if thought_chunks and not thought_done_emitted:
                            thought_done_emitted = True
                            thought_duration = round(time.perf_counter() - (thought_start or start_time), 1)
                            yield {
                                "event": "thought_done",
                                "data": {
                                    "duration": thought_duration,
                                    "text": "".join(thought_chunks),
                                },
                            }
                        if content_delta:
                            answer_chunks.append(content_delta)
                            yield {
                                "event": "delta",
                                "data": {"text": content_delta},
                            }

                # 5. Model part end
                elif isinstance(event, PartEndEvent):
                    part = event.part
                    part_kind = getattr(part, "part_kind", None)
                    if (part_kind == "thinking" or isinstance(part, ThinkingPart)) and not thought_done_emitted:
                        thought_done_emitted = True
                        thought_duration = round(time.perf_counter() - (thought_start or start_time), 1)
                        yield {
                            "event": "thought_done",
                            "data": {
                                "duration": thought_duration,
                                "text": "".join(thought_chunks),
                            },
                        }

        # 6. Stream termination & finalize thinking
        if thought_chunks and not thought_done_emitted:
            thought_done_emitted = True
            thought_duration = round(time.perf_counter() - (thought_start or start_time), 1)
            yield {
                "event": "thought_done",
                "data": {
                    "duration": thought_duration,
                    "text": "".join(thought_chunks),
                },
            }

        final_output = stream.result.output if (stream.result and stream.result.output) else "".join(answer_chunks)
        answer_text = str(final_output)

        # Fallback check for inline <think>...</think> in answer_text
        extracted_thought = "".join(thought_chunks) if thought_chunks else None
        if not extracted_thought and "<think>" in answer_text and "</think>" in answer_text:
            s_idx = answer_text.find("<think>") + len("<think>")
            e_idx = answer_text.find("</think>")
            extracted_thought = answer_text[s_idx:e_idx].strip()
            answer_text = (answer_text[:answer_text.find("<think>")] + answer_text[e_idx + len("</think>"):].strip()).strip()

        elapsed = round(time.perf_counter() - start_time, 3)

        final_response = ChatResponse(
            answer=answer_text,
            pattern_used=self.pattern_name,
            citations=deps.collected_citations,
            show_medical_disclaimer=deps.show_medical_disclaimer,
            is_content_gap=deps.is_content_gap,
            trigger_lead_capture=deps.lead_captured,
            latency_seconds=elapsed,
            thought=extracted_thought,
            thought_duration=thought_duration,
        )

        yield {
            "event": "done",
            "data": final_response.model_dump(),
        }
