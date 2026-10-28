"""
In-memory Conversation History Session Manager.
Maintains conversational turns per session_id with zero-overhead 0ms latency.
"""

import logging
from typing import Dict, List, Optional
from src.orchestration.schemas import ChatMessage

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages in-memory chat histories for multi-turn conversational reasoning.
    """

    def __init__(self, max_history_turns: int = 10):
        self._sessions: Dict[str, List[ChatMessage]] = {}
        self.max_history_turns = max_history_turns

    def get_history(self, session_id: str) -> List[ChatMessage]:
        """Retrieve recent conversation turns for a session."""
        return self._sessions.get(session_id, [])

    def add_user_message(self, session_id: str, content: str) -> None:
        """Record user message in session history."""
        self._sessions.setdefault(session_id, []).append(
            ChatMessage(role="user", content=content)
        )
        self._trim(session_id)

    def add_assistant_message(self, session_id: str, content: str) -> None:
        """Record assistant reply in session history."""
        self._sessions.setdefault(session_id, []).append(
            ChatMessage(role="assistant", content=content)
        )
        self._trim(session_id)

    def add_turn(self, session_id: str, user_content: str, assistant_content: str) -> None:
        """Record a completed conversation turn."""
        self.add_user_message(session_id, user_content)
        self.add_assistant_message(session_id, assistant_content)

    def format_history_for_prompt(self, session_id: str) -> str:
        """Format history into clean dialogue text for prompt injection."""
        history = self.get_history(session_id)
        if not history:
            return "No previous conversation history."
        lines = []
        for msg in history:
            prefix = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)

    def _trim(self, session_id: str) -> None:
        """Ensure history doesn't exceed maximum turns."""
        turns = self._sessions.get(session_id, [])
        max_messages = self.max_history_turns * 2
        if len(turns) > max_messages:
            self._sessions[session_id] = turns[-max_messages:]

    def clear(self, session_id: Optional[str] = None) -> None:
        """Clear a specific session or all sessions."""
        if session_id:
            self._sessions.pop(session_id, None)
        else:
            self._sessions.clear()


# Global singleton session manager
session_manager = SessionManager()
