"""
Abstract Base Orchestrator defining the contract for clinical agent orchestration.
"""

from abc import ABC, abstractmethod
from typing import List
from src.orchestration.schemas import ChatMessage, ChatResponse
from src.retrieval.retrieve import HybridRetrieverService


class BaseOrchestrator(ABC):
    """
    Abstract interface for orchestration engines.
    """

    def __init__(self, retriever: HybridRetrieverService):
        self.retriever = retriever

    @property
    @abstractmethod
    def pattern_name(self) -> str:
        """Name of the orchestrator engine (e.g. 'pydantic_ai')."""
        pass

    @abstractmethod
    async def process_turn(
        self,
        user_message: str,
        history: List[ChatMessage],
        session_id: str = "default-session"
    ) -> ChatResponse:
        """Process a conversation turn and return a structured GroundedResponse."""
        pass
