# -*- coding: utf-8 -*-
"""ChatBox Core Types — Messages, Sessions, and State Machine.

Architecture:
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │   Channel   │────▶│ ChatMessage │────▶│  ChatSession │
  │ (WeChat/Web)│     │  (immutable)│     │  (stateful)  │
  └─────────────┘     └─────────────┘     └─────────────┘
                             │
                             ▼
                       ┌─────────────┐
                       │ ChatContent │
                       │  (union)    │
                       └─────────────┘

Design Decisions:
  - ChatMessage is immutable (no setter mutation — create new instances)
  - SessionState is a finite state machine (explicit transitions only)
  - All timestamps are ISO-8601 strings (JSON-serializable, timezone-aware)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .content import ChatContent


# ── Direction ────────────────────────────────────────────────────────────

class MessageDirection(str, Enum):
    """Who sent the message."""

    INBOUND = "inbound"        # User → System
    OUTBOUND = "outbound"      # System → User
    SYSTEM = "system"          # System event (not a conversational turn)


# ── Status ───────────────────────────────────────────────────────────────

class MessageStatus(str, Enum):
    """Delivery lifecycle of a message."""

    PENDING = "pending"        # Queued, not yet sent
    SENT = "sent"              # Sent to channel API
    DELIVERED = "delivered"    # Channel API acknowledged
    READ = "read"              # User seen (if channel supports read receipts)
    FAILED = "failed"          # Delivery failed, may retry
    CANCELLED = "cancelled"    # Intent clarification timed out / user dismissed


# ── Session State (Finite State Machine) ─────────────────────────────────

class SessionState(str, Enum):
    """Conversation state machine states.

    Transitions:
      IDLE ──[user sends image]──▶ AWAITING_INTENT
      AWAITING_INTENT ──[user selects option]──▶ PROCESSING
      AWAITING_INTENT ──[timeout]──▶ IDLE
      PROCESSING ──[task done]──▶ IDLE
      IDLE ──[user sends text]──▶ PROCESSING ──[done]──▶ IDLE
    """

    IDLE = "idle"                          # Ready for new input
    AWAITING_INTENT = "awaiting_intent"    # Waiting for user to clarify intent (e.g., image options)
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Waiting for yes/no confirmation
    PROCESSING = "processing"              # Async task running (compile, OCR, etc.)
    ERROR = "error"                        # Stuck in error, needs user action


class StateTransition(BaseModel):
    """A valid FSM transition rule."""

    from_state: SessionState
    to_state: SessionState
    trigger: str                           # "user_message", "intent_selected", "timeout", "task_done", "error"
    description: str = ""


# ── Core Message Model ───────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in the ChatBox conversation.

    Immutable — to "edit" a message, create a new instance with updated fields.
    This ensures audit trail integrity and simplifies caching.
    """

    # Identity
    id: str                                # UUID v4
    session_id: str                        # "wechat:{user_id}" or "web:{session_id}"
    channel: str = "unknown"               # "wechat", "web", "api"

    # Direction & Status
    direction: MessageDirection = MessageDirection.INBOUND
    status: MessageStatus = MessageStatus.PENDING

    # Content (the discriminated union)
    content: ChatContent

    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Optional[str] = None     # Last status change
    read_at: Optional[str] = None        # When user read it (if tracked)

    # Metadata
    reply_to_id: Optional[str] = None    # For threaded replies
    correlation_id: Optional[str] = None   # Links a request to its response
    metadata: MessageMetadata = Field(default_factory=lambda: MessageMetadata())

    def with_status(self, new_status: MessageStatus) -> "ChatMessage":
        """Return a copy with updated status (immutable update)."""
        return self.model_copy(update={
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def with_content(self, new_content: ChatContent) -> "ChatMessage":
        """Return a copy with updated content (for progressive updates)."""
        return self.model_copy(update={
            "content": new_content,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })


class MessageMetadata(BaseModel):
    """Extra metadata attached to a message."""

    # Source / Provenance
    source_ip: Optional[str] = None        # For web clients
    user_agent: Optional[str] = None       # Browser / client info

    # Processing trace
    intent_detected: Optional[str] = None  # "query", "ingest", "chat"
    intent_confidence: float = 0.0
    processing_time_ms: Optional[int] = None  # End-to-end latency

    # Raw data (channel-specific, for debugging / audit)
    raw_data: dict = Field(default_factory=dict)

    # Cost / Performance
    tokens_used: int = 0
    model_name: str = ""
    cost_estimate: str = ""                # "~$0.002" or "local"


# ── Session Model ────────────────────────────────────────────────────────

class ChatSession(BaseModel):
    """A conversation session — holds messages and state.

    One session per user per channel. Sessions are persistent
    (stored in SQLite) so conversations survive restarts.
    """

    id: str                                # session_id: "wechat:{user_id}"
    channel: str
    user_id: str
    state: SessionState = SessionState.IDLE

    # Messages (ordered chronologically)
    messages: list[ChatMessage] = Field(default_factory=list)

    # State machine context
    pending_intent_data: dict = Field(default_factory=dict)  # Data waiting for intent clarification
    pending_confirmation: Optional[IntentConfirmationRecord] = None

    # Lifecycle
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None       # Auto-cleanup after inactivity

    def add_message(self, msg: ChatMessage) -> "ChatSession":
        """Return a copy with the new message appended."""
        new_messages = self.messages + [msg]
        return self.model_copy(update={
            "messages": new_messages,
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
        })

    def transition_to(self, new_state: SessionState, context: dict | None = None) -> "ChatSession":
        """Return a copy with updated state (validates transition)."""
        # TODO: Validate against ALLOWED_TRANSITIONS
        update = {"state": new_state, "last_activity_at": datetime.now(timezone.utc).isoformat()}
        if context:
            if new_state == SessionState.AWAITING_INTENT:
                update["pending_intent_data"] = context
            elif new_state == SessionState.AWAITING_CONFIRMATION:
                update["pending_confirmation"] = context
        return self.model_copy(update=update)


class IntentConfirmationRecord(BaseModel):
    """Record of a pending confirmation (stored in session)."""

    message_id: str                        # The confirmation message ID
    action_type: str                       # "ingest", "delete", etc.
    action_payload: dict = Field(default_factory=dict)  # Parameters needed to execute
    expires_at: str                        # ISO timestamp


# ── FSM Transition Rules ─────────────────────────────────────────────────

ALLOWED_TRANSITIONS: list[StateTransition] = [
    StateTransition(from_state=SessionState.IDLE, to_state=SessionState.AWAITING_INTENT, trigger="image_received", description="User sent image, need intent clarification"),
    StateTransition(from_state=SessionState.IDLE, to_state=SessionState.AWAITING_CONFIRMATION, trigger="high_impact_action", description="Action needs confirmation"),
    StateTransition(from_state=SessionState.IDLE, to_state=SessionState.PROCESSING, trigger="user_message", description="Normal message processing"),
    StateTransition(from_state=SessionState.AWAITING_INTENT, to_state=SessionState.PROCESSING, trigger="intent_selected", description="User chose an intent option"),
    StateTransition(from_state=SessionState.AWAITING_INTENT, to_state=SessionState.IDLE, trigger="timeout", description="Intent clarification timed out"),
    StateTransition(from_state=SessionState.AWAITING_INTENT, to_state=SessionState.IDLE, trigger="user_cancelled", description="User dismissed the clarification"),
    StateTransition(from_state=SessionState.AWAITING_CONFIRMATION, to_state=SessionState.PROCESSING, trigger="confirmed", description="User confirmed the action"),
    StateTransition(from_state=SessionState.AWAITING_CONFIRMATION, to_state=SessionState.IDLE, trigger="cancelled", description="User cancelled the action"),
    StateTransition(from_state=SessionState.PROCESSING, to_state=SessionState.IDLE, trigger="task_done", description="Async task completed"),
    StateTransition(from_state=SessionState.PROCESSING, to_state=SessionState.ERROR, trigger="task_failed", description="Async task failed"),
    StateTransition(from_state=SessionState.ERROR, to_state=SessionState.IDLE, trigger="user_acknowledged", description="User acknowledged error"),
    StateTransition(from_state=SessionState.ERROR, to_state=SessionState.PROCESSING, trigger="retry", description="User requested retry"),
]
