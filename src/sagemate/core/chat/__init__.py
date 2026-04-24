# -*- coding: utf-8 -*-
"""ChatBox Package — Unified messaging protocol for SageMate Core.

Exports:
  - Content types: TextContent, ImageContent, IntentClarificationContent, etc.
  - Message types: ChatMessage, ChatSession, MessageMetadata
  - State machine: SessionState, StateTransition, ALLOWED_TRANSITIONS
  - Enums: ContentType, MessageDirection, MessageStatus

Usage:
    from sagemate.core.chat import ChatMessage, TextContent, SessionState

    msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id="wechat:user_123",
        direction=MessageDirection.OUTBOUND,
        content=TextContent(text="Hello!"),
    )
"""

from __future__ import annotations

from .content import (
    ChatContent,
    ContentType,
    ConfirmAction,
    ErrorContent,
    FileContent,
    ImageContent,
    IntentClarificationContent,
    IntentConfirmationContent,
    IntentOption,
    ProgressContent,
    SystemContent,
    TextContent,
    URLContent,
    VoiceContent,
)
from .types import (
    ALLOWED_TRANSITIONS,
    ChatMessage,
    ChatSession,
    IntentConfirmationRecord,
    MessageDirection,
    MessageMetadata,
    MessageStatus,
    SessionState,
    StateTransition,
)

__all__ = [
    # Content types
    "ChatContent",
    "ContentType",
    "TextContent",
    "ImageContent",
    "VoiceContent",
    "FileContent",
    "URLContent",
    "IntentClarificationContent",
    "IntentConfirmationContent",
    "ProgressContent",
    "ErrorContent",
    "SystemContent",
    "IntentOption",
    "ConfirmAction",
    # Message types
    "ChatMessage",
    "ChatSession",
    "MessageMetadata",
    "MessageDirection",
    "MessageStatus",
    # State machine
    "SessionState",
    "StateTransition",
    "ALLOWED_TRANSITIONS",
    "IntentConfirmationRecord",
]
