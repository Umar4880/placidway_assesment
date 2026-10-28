"""
Unified Orchestrator Service powered by PydanticAI.
Manages clinical conversation turns with hybrid RAG retrieval and conversational quote booking.
"""

import json
import logging
from typing import AsyncIterator, Optional
from src.retrieval.retrieve import HybridRetrieverService
from src.storage.db import DatabaseManager
from src.orchestration.pydantic_ai_agent import PydanticAIAgentOrchestrator
from src.orchestration.session_manager import session_manager
from src.orchestration.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class OrchestrationService:
    """
    Clinical Knowledge Orchestrator powered exclusively by PydanticAI.
    Provides strictly grounded RAG search and conversational consultation booking tools.
    """

    def __init__(
        self,
        retriever: Optional[HybridRetrieverService] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.retriever = retriever or HybridRetrieverService()
        self.db_manager = db_manager or DatabaseManager()
        self.agent = PydanticAIAgentOrchestrator(self.retriever, self.db_manager)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Execute conversation turn using PydanticAI agent and manage in-memory session.
        """
        session_id = request.session_id or "default-session"

        # 1. Fetch in-memory history (or use passed history if provided)
        history = request.history or session_manager.get_history(session_id)

        logger.info(
            "Processing turn with PydanticAI agent for session '%s': '%s'",
            session_id,
            request.message[:60],
        )

        # 2. Process turn through PydanticAI agent
        response = await self.agent.process_turn(
            user_message=request.message,
            history=history,
            session_id=session_id,
        )

        # 3. Update in-memory session history
        session_manager.add_turn(
            session_id=session_id,
            user_content=request.message,
            assistant_content=response.answer,
        )

        return response

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        Execute conversation turn using PydanticAI streaming and yield SSE events.
        """
        session_id = request.session_id or "default-session"
        history = request.history or session_manager.get_history(session_id)

        logger.info(
            "Processing streaming turn with PydanticAI agent for session '%s': '%s'",
            session_id,
            request.message[:60],
        )

        async for item in self.agent.process_turn_stream(
            user_message=request.message,
            history=history,
            session_id=session_id,
        ):
            event_name = item.get("event", "message")
            event_data = item.get("data", {})

            if event_name == "done":
                # Save completed turn in history
                assistant_answer = event_data.get("answer", "")
                if assistant_answer:
                    session_manager.add_turn(
                        session_id=session_id,
                        user_content=request.message,
                        assistant_content=assistant_answer,
                    )

            payload = json.dumps(event_data)
            yield f"event: {event_name}\ndata: {payload}\n\n"


# Lazy-loaded global orchestrator service instance to prevent duplicate QdrantClient file lock collisions
_orchestration_service: Optional[OrchestrationService] = None


def get_orchestration_service() -> OrchestrationService:
    global _orchestration_service
    if _orchestration_service is None:
        _orchestration_service = OrchestrationService()
    return _orchestration_service


def __getattr__(name: str):
    if name == "orchestration_service":
        return get_orchestration_service()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
