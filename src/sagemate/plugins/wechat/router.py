# -*- coding: utf-8 -*-
"""SageMate WeChat Plugin - Intent Router.

Token-optimized intent routing with keyword + heuristic fast paths.
LLM is only called for ambiguous long texts that can't be classified otherwise.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    INGEST = "INGEST"   # Save to Knowledge Base
    QUERY = "QUERY"     # Ask the Knowledge Base
    CHAT = "CHAT"       # Just chat, do not save
    IGNORE = "IGNORE"   # Noise/System message


class RouterResult:
    def __init__(self, intent: Intent, content: str, reply_hint: Optional[str] = None):
        self.intent = intent
        self.content = content
        self.reply_hint = reply_hint

    def __repr__(self):
        return f"<RouterResult: {self.intent} | {self.content[:20]}...>"


# ---------------------------------------------------------------------------
# Fast-path keyword sets (no LLM needed)
# ---------------------------------------------------------------------------

# Words that strongly indicate the user wants to QUERY existing knowledge
QUERY_KEYWORDS = [
    "知识库", "有哪些", "什么内容", "搜索", "查找", "笔记", "说过", "记得",
    "查一下", "查询", "wiki", "knowledge", "总结", "汇总", "概况",
    "帮我找", "帮我查", "有没有", "知不知道", "介绍一下",
    "what", "search", "find", "tell me about", "do you know",
]

# Words that strongly indicate the user is just CHATTING
CHAT_KEYWORDS = [
    "你好", "你好啊", "早上好", "晚上好", "下午好", "早安", "晚安",
    "谢谢", "感谢", "哈哈", "哈哈哈", "嗯嗯", "好的", "收到",
    "在吗", "在不在", "hello", "hi ", "hey", "thanks", "thank you",
    "bye", "再见", "拜拜", "ok", "okok",
]

# Words that strongly indicate the user wants to INGEST
INGEST_KEYWORDS = [
    "记录", "保存", "记一下", "备忘", "收藏", "归档", "存一下",
    "笔记：", "想法：", "想法:", "灵感", "想法 ", "我觉得", "我认为",
    "我认为", "建议", "TODO", "todo",
]


class IntentRouter:
    """Routes incoming WeChat messages to the correct handler.

    Routing pipeline (fast → slow):
    1. Empty / whitespace → IGNORE
    2. Prefix ! → INGEST, prefix ? → QUERY
    3. Keyword match → corresponding intent
    4. Heuristic rules (length, punctuation, question marks)
    5. LLM classification (only for ambiguous texts > 30 chars)
    6. Safe fallback → CHAT (don't waste tokens on uncertain ingestion)
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def route(self, text: str, is_voice: bool = False) -> RouterResult:
        """Determine the intent of the message."""
        if not text or text.isspace():
            return RouterResult(Intent.IGNORE, "")

        # Strip leading/trailing whitespace for analysis
        stripped = text.strip()

        # ── Step 1: Prefix override ──────────────────────────────
        if stripped.startswith("!"):
            return RouterResult(Intent.INGEST, stripped[1:].strip())
        if stripped.startswith("?"):
            return RouterResult(Intent.QUERY, stripped[1:].strip())

        # ── Step 2: Keyword fast paths ───────────────────────────
        if any(kw in stripped for kw in QUERY_KEYWORDS):
            return RouterResult(Intent.QUERY, text)
        if any(kw in stripped for kw in INGEST_KEYWORDS):
            return RouterResult(Intent.INGEST, text)
        if any(kw in stripped for kw in CHAT_KEYWORDS):
            return RouterResult(Intent.CHAT, text)

        # ── Step 3: Heuristic rules ──────────────────────────────
        result = self._heuristic_route(stripped, is_voice)
        if result is not None:
            return result

        # ── Step 4: LLM for ambiguous cases ──────────────────────
        # Only call LLM for texts long enough to be ambiguous (> 30 chars)
        if len(stripped) > 30 and self.llm_client:
            try:
                result = await self._call_llm(stripped)
                return result
            except Exception as e:
                logger.warning(f"Router LLM fallback failed: {e}")

        # ── Step 5: Safe fallback ────────────────────────────────
        # Short unknown text → CHAT (safer than wasting tokens ingesting noise)
        return RouterResult(Intent.CHAT, text)

    @staticmethod
    def _heuristic_route(text: str, is_voice: bool) -> RouterResult | None:
        """
        Fast heuristic classification. Returns None if uncertain.

        Rules of thumb:
        - Questions (ending with ？ or ?) → QUERY
        - Very short (< 8 chars, no keywords) → CHAT
        - Long substantive text (> 50 chars) → INGEST
        - Voice messages → INGEST (user speaking notes)
        """
        # Voice → usually the user dictating notes
        if is_voice and len(text) > 5:
            return RouterResult(Intent.INGEST, text)

        # Contains question marks and is a reasonable length → QUERY
        if ("？" in text or "?" in text) and len(text) > 5:
            # But only if it's not obviously a rhetorical/exclamatory question
            if not text.endswith("！") and not text.endswith("!"):
                return RouterResult(Intent.QUERY, text)

        # Very short text without keywords → likely CHAT
        if len(text) < 8:
            return RouterResult(Intent.CHAT, text)

        # Medium text (8-30 chars) without keywords → uncertain, let LLM decide
        if len(text) <= 30:
            return None  # Let pipeline proceed to LLM or fallback

        # Long text (> 30 chars) without any keywords → likely INGEST (user writing notes)
        # But be conservative: only if it looks substantive (contains nouns/verbs, not just "......")
        if len(text) > 30:
            # Filter out noise patterns
            noise_patterns = [r'^[.。…~～\s]+$', r'^[0-9]+$', r'^[a-zA-Z]+$']
            for pattern in noise_patterns:
                if re.match(pattern, text):
                    return RouterResult(Intent.CHAT, text)
            return RouterResult(Intent.INGEST, text)

        return None

    async def _call_llm(self, text: str) -> RouterResult:
        """Call LLM for intent classification. Uses a cheap model."""
        if not self.llm_client:
            # No LLM available → safe heuristic fallback
            return RouterResult(Intent.INGEST, text) if len(text) > 30 else RouterResult(Intent.CHAT, text)

        # Minimal prompt to save tokens
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify the user message into exactly one intent: "
                    "INGEST (save note/idea), QUERY (ask about existing knowledge), "
                    "CHAT (casual conversation), IGNORE (noise). "
                    "Reply with JSON only: {\"intent\": \"...\"}"
                ),
            },
            {"role": "user", "content": text},
        ]

        response = await self.llm_client.chat.completions.create(
            model="qwen-turbo",
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=30,  # We only need a tiny JSON response
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        intent_str = data.get("intent", "CHAT")
        summary = data.get("summary", "")

        intent = Intent(intent_str)
        content_to_process = text if intent == Intent.INGEST else summary
        return RouterResult(intent, content_to_process, reply_hint=summary)
