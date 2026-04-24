# -*- coding: utf-8 -*-
"""ChatBox Content Types — Discriminated Union for all message content forms.

Design Principle:
  Every message in the ChatBox has a `content_type` discriminator.
  Frontends (Web, WeChat, future channels) pattern-match on this field
  to render the appropriate UI component.

  This is a Tagged Union (Algebraic Data Type) — type-safe by construction.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Content Type Discriminator ───────────────────────────────────────────

class ContentType(str, Enum):
    """All possible content types in the ChatBox."""

    TEXT = "text"                          # Plain text / Markdown
    IMAGE = "image"                        # Image with optional caption
    VOICE = "voice"                        # Voice message (transcribed)
    FILE = "file"                          # Generic file attachment
    URL = "url"                            # URL preview card
    INTENT_CLARIFICATION = "intent_clarification"   # "What do you want to do?"
    INTENT_CONFIRMATION = "intent_confirmation"       # "Confirm before action"
    PROGRESS = "progress"                  # Async task progress
    ERROR = "error"                        # Error message
    SYSTEM = "system"                      # System event (login, etc.)


# ── Option Models ────────────────────────────────────────────────────────

class IntentOption(BaseModel):
    """A single option in an intent clarification card."""

    id: str                                # Machine-readable ID: "ingest", "ocr", "describe", "ignore"
    label: str                             # Human-readable: "归档入库"
    description: str = ""                  # Optional subtitle
    icon: str = ""                         # Optional icon name/emoji
    primary: bool = False                  # Highlight as recommended


class ConfirmAction(BaseModel):
    """Action descriptor for intent confirmation."""

    action_type: str                       # "ingest", "delete", "overwrite", "compile"
    target_id: str = ""                    # Slug, file_path, etc.
    preview: str = ""                    # Human-readable preview of what will happen
    estimated_cost: str = ""             # Optional: "~3 tokens", "~2 min"


# ── Content Union Members ────────────────────────────────────────────────

class TextContent(BaseModel):
    """Plain text or Markdown message."""

    content_type: Literal[ContentType.TEXT] = ContentType.TEXT
    text: str
    markdown: bool = True                  # If True, render with MD support
    code_blocks: list[dict] = Field(default_factory=list)  # Extracted code blocks


class ImageContent(BaseModel):
    """Image message — from user upload or system-generated."""

    content_type: Literal[ContentType.IMAGE] = ContentType.IMAGE
    image_path: str                      # Absolute path or URL
    caption: str = ""                    # Optional caption / OCR text
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: int = 0                   # Bytes
    mime_type: str = "image/png"


class VoiceContent(BaseModel):
    """Voice message — always transcribed before display."""

    content_type: Literal[ContentType.VOICE] = ContentType.VOICE
    audio_path: str = ""                 # Original audio file (if kept)
    transcription: str                   # Transcribed text (required)
    duration_seconds: int = 0
    language: str = "zh"


class FileContent(BaseModel):
    """Generic file attachment."""

    content_type: Literal[ContentType.FILE] = ContentType.FILE
    file_name: str
    file_path: str
    mime_type: str = "application/octet-stream"
    file_size: int = 0
    preview_text: str = ""               # First N chars for text files


class URLContent(BaseModel):
    """URL preview card."""

    content_type: Literal[ContentType.URL] = ContentType.URL
    url: str
    title: str = ""
    description: str = ""
    image_url: str = ""
    site_name: str = ""


class IntentClarificationContent(BaseModel):
    """Multi-choice card: "I received an image. What do you want to do?"

    Rendered as a card with buttons/options in the ChatBox.
    User selection produces a follow-up message with the chosen intent.
    """

    content_type: Literal[ContentType.INTENT_CLARIFICATION] = ContentType.INTENT_CLARIFICATION
    question: str                        # "我收到了一张图片，你想让我做什么？"
    options: list[IntentOption]          # 2-4 options
    timeout_seconds: int = 300           # Auto-cancel after N seconds
    context_data: dict = Field(default_factory=dict)  # Pass-through: image_path, etc.


class IntentConfirmationContent(BaseModel):
    """Single-action confirmation: "Archive this file? [Confirm] [Cancel]"

    For high-impact operations that need explicit user confirmation.
    """

    content_type: Literal[ContentType.INTENT_CONFIRMATION] = ContentType.INTENT_CONFIRMATION
    message: str                         # "确认将文件归档到知识库？"
    action: ConfirmAction                # What will happen if confirmed
    confirm_label: str = "确认"           # Button text
    cancel_label: str = "取消"            # Button text


class ProgressContent(BaseModel):
    """Async task progress indicator."""

    content_type: Literal[ContentType.PROGRESS] = ContentType.PROGRESS
    task_id: str
    task_name: str                       # "编译 Wiki", "OCR 识别"
    step: int = 0
    total_steps: int = 5
    step_name: str = ""                  # "正在读取上下文..."
    percent: int = 0                     # 0-100
    message: str = ""                    # Human-readable status
    is_done: bool = False
    result_preview: str = ""             # Brief result summary when done


class ErrorContent(BaseModel):
    """Structured error message for the ChatBox."""

    content_type: Literal[ContentType.ERROR] = ContentType.ERROR
    error_code: str = "UNKNOWN"            # "NETWORK_ERROR", "LLM_TIMEOUT", etc.
    message: str                           # Human-readable
    suggestion: str = ""                   # "请检查网络连接后重试"
    retryable: bool = False              # Can user retry?


class SystemContent(BaseModel):
    """System event — not a user message, but a system notification.

    Examples: "WeChat connected", "Auto-compile completed", "Token expired".
    """

    content_type: Literal[ContentType.SYSTEM] = ContentType.SYSTEM
    event_type: str                      # "channel_connected", "task_completed", "auth_expired"
    message: str
    metadata: dict = Field(default_factory=dict)
    actionable: bool = False             # Has a CTA button?
    action_label: str = ""               # Button text if actionable
    action_payload: dict = Field(default_factory=dict)


# ── Discriminated Union ──────────────────────────────────────────────────

ChatContent = (
    TextContent
    | ImageContent
    | VoiceContent
    | FileContent
    | URLContent
    | IntentClarificationContent
    | IntentConfirmationContent
    | ProgressContent
    | ErrorContent
    | SystemContent
)
"""Tagged union of all possible message contents.

Use pattern matching (Python 3.10+) or isinstance checks:

    match msg.content:
        case TextContent(text=t):
            render_markdown(t)
        case IntentClarificationContent(options=opts):
            render_option_card(opts)
        case _:
            render_fallback(msg.content)
"""
