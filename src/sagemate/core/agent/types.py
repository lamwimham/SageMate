"""Standardized message protocol for Channel ↔ Core Agent communication."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class Intent(str, Enum):
    QUERY = "query"     # Ask the knowledge base
    INGEST = "ingest"   # Save content to wiki
    CHAT = "chat"       # General conversation
    IGNORE = "ignore"   # Noise / system message


class AgentMessage(BaseModel):
    """A standardized message from any channel (WeChat, Web, etc.)."""

    channel: str = "unknown"           # "wechat", "web", etc.
    user_id: str
    session_id: str = ""               # Format: "{channel}:{user_id}"
    content_type: str = "text"         # "text", "image", "voice", "file", "url"
    text: str = ""                     # Extracted text (after OCR, transcription, etc.)
    raw_data: dict = Field(default_factory=dict)  # Raw channel-specific data

    def model_post_init(self, __context):
        if not self.session_id:
            self.session_id = f"{self.channel}:{self.user_id}"


class AgentResponse(BaseModel):
    """Structured response from Core Agent to the channel."""

    reply_text: str
    reply_type: str = "markdown"       # "markdown" | "simple"
    action_taken: str = ""             # "queried" | "ingested" | "chatted"
    sources: list[dict] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)  # [{number, slug, title}]
    related_pages: list[dict] = Field(default_factory=list)  # [{slug, title, category, summary, ...}]
    conversation_id: str = ""          # Session ID for multi-turn context
    suggested_followups: list[str] = Field(default_factory=list)
