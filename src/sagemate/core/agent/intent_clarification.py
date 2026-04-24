# -*- coding: utf-8 -*-
"""Intent Clarification Handler — Multi-turn intent resolution for ambiguous inputs.

Architecture:
  Strategy Pattern: All clarification logic is encapsulated here.
  The AgentPipeline delegates to this handler when:
    1. A new image arrives (requires_intent_clarification=True)
    2. User selects an option from a clarification card

State Machine Integration:
  IDLE ──[image]──▶ AWAITING_INTENT ──[selection]──▶ PROCESSING ──[done]──▶ IDLE

Design Principle:
  Separation of Concerns — The handler knows NOTHING about:
    - WeChat protocol
    - HTTP responses
    - Channel-specific formatting
  It only produces ChatMessage objects (pure data).
"""

from __future__ import annotations

import logging
from typing import Optional

from ..chat import (
    ChatMessage,
    ChatSession,
    ContentType,
    IntentClarificationContent,
    IntentConfirmationContent,
    IntentOption,
    MessageDirection,
    MessageStatus,
    SessionState,
    TextContent,
)
from .types import AgentMessage, AgentResponse

logger = logging.getLogger(__name__)


# ── Default Options for Image Intent Clarification ─────────────────────────

DEFAULT_IMAGE_OPTIONS = [
    IntentOption(
        id="ingest",
        label="归档入库",
        description="提取文字并编译为 Wiki 知识页面",
        icon="📚",
        primary=True,
    ),
    IntentOption(
        id="ocr",
        label="识别文字",
        description="只提取图片中的文字内容",
        icon="🔍",
    ),
    IntentOption(
        id="describe",
        label="描述图片",
        description="描述图片内容和场景",
        icon="🖼️",
    ),
    IntentOption(
        id="ignore",
        label="忽略",
        description="不处理，仅保存原始图片",
        icon="🗑️",
    ),
]

DEFAULT_FILE_OPTIONS = [
    IntentOption(
        id="ingest",
        label="归档入库",
        description="解析文件并编译为 Wiki 知识页面",
        icon="📚",
        primary=True,
    ),
    IntentOption(
        id="summarize",
        label="摘要总结",
        description="生成内容摘要，不入库",
        icon="📝",
    ),
    IntentOption(
        id="ignore",
        label="忽略",
        description="仅保存原始文件",
        icon="🗑️",
    ),
]


class IntentClarificationHandler:
    """Handles multi-turn intent clarification for ambiguous inputs.

    Responsibilities:
      - Generate clarification cards (options for user to choose)
      - Parse user selections (option ID → intent)
      - Manage session state transitions (AWAITING_INTENT ↔ IDLE)
      - Store context data (image_path, etc.) while waiting for user choice

    NOT responsible:
      - Executing the chosen intent (delegated back to AgentPipeline)
      - Channel-specific formatting
      - UI rendering
    """

    def __init__(self):
        # Option registry: content_type → list of IntentOption
        self._option_registry: dict[str, list[IntentOption]] = {
            "image": DEFAULT_IMAGE_OPTIONS,
            "file": DEFAULT_FILE_OPTIONS,
        }

    # ── Public API ──────────────────────────────────────────────────────────

    def create_clarification(
        self,
        session: ChatSession,
        content_type: str,
        context_data: dict,
        *,
        custom_options: Optional[list[IntentOption]] = None,
        question: Optional[str] = None,
    ) -> tuple[ChatSession, ChatMessage]:
        """Create an intent clarification card and update session state.

        Args:
            session: Current chat session (will be mutated to AWAITING_INTENT)
            content_type: "image", "file", etc.
            context_data: Raw data to pass through (image_path, file_path, etc.)
            custom_options: Override default options
            question: Override default question text

        Returns:
            (updated_session, clarification_message)
        """
        options = custom_options or self._option_registry.get(content_type, [])
        if not options:
            logger.warning(f"No clarification options for content_type={content_type}")
            options = [IntentOption(id="ignore", label="忽略", description="不处理")]

        default_questions = {
            "image": "我收到了一张图片，你想让我做什么？",
            "file": f"我收到了文件 [{context_data.get('file_name', '未知')}]，你想让我做什么？",
            "voice": "我收到了一条语音，已转写为文字。你想让我做什么？",
        }
        q = question or default_questions.get(content_type, "我收到了内容，你想让我做什么？")

        # Build clarification content
        clarification = IntentClarificationContent(
            question=q,
            options=options,
            timeout_seconds=300,
            context_data=context_data,
        )

        # Build message
        msg = ChatMessage(
            id=f"clarify-{session.id}-{len(session.messages)}",
            session_id=session.id,
            channel=session.channel,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.SENT,
            content=clarification,
        )

        # Update session state
        updated_session = session.transition_to(
            SessionState.AWAITING_INTENT,
            context={"content_type": content_type, **context_data},
        ).add_message(msg)

        logger.info(
            f"[IntentClarification] Created for session={session.id} "
            f"content_type={content_type} options={[o.id for o in options]}"
        )

        return updated_session, msg

    def resolve_selection(
        self,
        session: ChatSession,
        selected_option_id: str,
    ) -> tuple[ChatSession, Optional[AgentMessage]]:
        """Resolve a user's option selection from a clarification card.

        Args:
            session: Current session (must be in AWAITING_INTENT state)
            selected_option_id: The option chosen by user (e.g., "ingest", "ignore")

        Returns:
            (updated_session, resolved_agent_message or None)
            If None → selection was "ignore" or invalid, no further action needed.
        """
        if session.state != SessionState.AWAITING_INTENT:
            logger.warning(
                f"[IntentClarification] Session not in AWAITING_INTENT state "
                f"(current={session.state}), ignoring selection"
            )
            return session, None

        # Retrieve stored context from session
        context = session.pending_intent_data
        content_type = context.get("content_type", "unknown")
        raw_data = {k: v for k, v in context.items() if k != "content_type"}

        # Validate option
        valid_ids = {o.id for o in self._option_registry.get(content_type, [])}
        if selected_option_id not in valid_ids:
            logger.warning(f"[IntentClarification] Invalid option '{selected_option_id}'")
            # Return error message
            error_msg = ChatMessage(
                id=f"err-{session.id}",
                session_id=session.id,
                channel=session.channel,
                direction=MessageDirection.OUTBOUND,
                content=TextContent(text=f"无效选项: {selected_option_id}。请重新选择。"),
            )
            return session.add_message(error_msg), None

        logger.info(
            f"[IntentClarification] Resolved: session={session.id} "
            f"option={selected_option_id} content_type={content_type}"
        )

        # Build the resolved AgentMessage for pipeline processing
        # Map option → intent + text
        intent_text_map = {
            "ingest": ("请归档以下内容", Intent.INGEST),
            "ocr": ("请提取图片中的文字", Intent.QUERY),  # OCR treated as query
            "describe": ("请描述这张图片", Intent.QUERY),
            "summarize": ("请总结这份文件", Intent.QUERY),
            "ignore": (None, None),
        }

        text, intent = intent_text_map.get(selected_option_id, (None, None))

        if selected_option_id == "ignore":
            # User chose to ignore — return confirmation, no further processing
            confirm_msg = ChatMessage(
                id=f"confirm-{session.id}",
                session_id=session.id,
                channel=session.channel,
                direction=MessageDirection.OUTBOUND,
                content=TextContent(text="已忽略，图片已保存到原始资源。"),
            )
            updated_session = session.transition_to(SessionState.IDLE).add_message(confirm_msg)
            return updated_session, None

        # Build AgentMessage for the chosen intent
        # Combine the user's implicit intent with the raw data
        resolved_msg = AgentMessage(
            channel=session.channel,
            user_id=session.user_id,
            content_type=content_type,
            text=text or "",
            raw_data=raw_data,
        )
        # Tag the resolved intent so router can skip re-classification
        resolved_msg.raw_data["_resolved_intent"] = intent.value if intent else "chat"
        resolved_msg.raw_data["_from_clarification"] = True

        # Transition session back to IDLE (ready for processing)
        updated_session = session.transition_to(SessionState.IDLE)

        return updated_session, resolved_msg

    def is_clarification_response(
        self,
        session: ChatSession,
        msg: AgentMessage,
    ) -> bool:
        """Check if an incoming message is a response to a clarification card.

        Heuristics:
          1. Session is in AWAITING_INTENT state
          2. Message text matches one of the option IDs or labels
        """
        if session.state != SessionState.AWAITING_INTENT:
            return False

        # Check if text is a valid option ID
        valid_ids = {o.id for o in self._option_registry.get("image", [])}
        valid_ids.update({o.id for o in self._option_registry.get("file", [])})

        text = msg.text.strip().lower()
        return text in valid_ids or any(text == o.label.lower() for o in (
            self._option_registry.get("image", []) + self._option_registry.get("file", [])
        ))


# Import at bottom to avoid circular import
from .router import Intent