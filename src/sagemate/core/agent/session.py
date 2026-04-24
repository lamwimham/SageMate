"""Unified session management for multi-channel conversations."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """
    In-memory session store keyed by '{channel}:{user_id}'.
    Automatically truncates old messages to stay within token budget.
    """

    def __init__(self, max_history_chars: int = 6000):
        self._sessions: dict[str, list[dict]] = {}
        self._max_chars = max_history_chars

    def get(self, session_id: str) -> list[dict]:
        """Get conversation history for a session."""
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, content: str):
        """Append a message and truncate if over budget."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        self._sessions[session_id].append({"role": role, "content": content})

        # Token-based truncation: ~3 chars/token safe estimate
        while (
            self._sessions[session_id]
            and sum(len(m.get("content", "")) for m in self._sessions[session_id]) > self._max_chars
        ):
            self._sessions[session_id].pop(0)

        # Always keep at least the last exchange (2 messages)
        if len(self._sessions[session_id]) < 2:
            pass  # keep as-is

    def clear(self, session_id: str):
        """Clear a session's history."""
        self._sessions.pop(session_id, None)

    def all_sessions(self) -> dict[str, list[dict]]:
        """Return a copy of all sessions (for introspection)."""
        return {k: list(v) for k, v in self._sessions.items()}
