# -*- coding: utf-8 -*-
"""SageMate WeChat Plugin - Intent Router."""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Optional

# We assume we have access to an LLM client. 
# In SageMate Core, this is usually passed in or imported from a common util.
# For now, we define the interface.

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
# Prompt Template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are the "Intent Router" for a personal Second Brain assistant.
Analyze the user's input and classify it into ONE of the following intents:

1. **INGEST**: The user wants to save a new idea, thought, note, or file.
   - Examples: "I think AI is changing fast", "Meeting notes: 10am...", "Record this link..."
   - *Action*: Archive this content.

2. **QUERY**: The user is asking a question about existing knowledge or asking to search.
   - Examples: "What did I say about React last week?", "Who is the CEO of OpenAI?", "? Find my notes on Docker"
   - *Action*: Search the wiki and answer.

3. **CHAT**: Casual conversation, greetings, or emotional expressions. No new knowledge.
   - Examples: "Hi", "Good morning", "Haha", "Thanks!", "Are you there?"
   - *Action*: Reply politely but do NOT save to wiki.

4. **IGNORE**: Garbage text, system errors, or empty content.
   - Examples: "..." (dots), system notifications.

**Special Rules**:
- If input starts with `!`, force **INGEST**.
- If input starts with `?`, force **QUERY**.
- Voice messages usually imply **INGEST** (unless they ask a question).

Output JSON ONLY:
{"intent": "INGEST", "summary": "Short summary of the content"}
"""


class IntentRouter:
    """Routes incoming WeChat messages to the correct handler."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def route(self, text: str, is_voice: bool = False) -> RouterResult:
        """
        Determine the intent of the message.
        """
        if not text or text.isspace():
            return RouterResult(Intent.IGNORE, "")

        # 1. Prefix Check (Fast path)
        if text.startswith("!"):
            return RouterResult(Intent.INGEST, text.lstrip("!").strip())
        if text.startswith("?"):
            return RouterResult(Intent.QUERY, text.lstrip("?").strip())

        # 2. Keyword-based QUERY detection (fast path for common patterns)
        query_keywords = ["知识库", "有哪些", "什么内容", "搜索", "查找", "笔记", "说过", "记得", "查一下", "查询", "wiki", "knowledge"]
        if any(kw in text for kw in query_keywords):
            return RouterResult(Intent.QUERY, text)

        # 3. LLM Classification (Slow path)
        try:
            result = await self._call_llm(text)
            return result
        except Exception as e:
            logger.error(f"Router LLM error: {e}")
            # Fallback: If LLM fails, treat as INGEST to be safe (don't lose data)
            # Or CHAT if you prefer safety against spam. 
            # Let's default to INGEST for text/voice to be helpful.
            return RouterResult(Intent.INGEST, text)

    async def _call_llm(self, text: str) -> RouterResult:
        if not self.llm_client:
            # If no LLM is provided, we can't do smart routing.
            # Default logic: Long text = INGEST, Short text = CHAT?
            # This is a very dumb heuristic.
            if len(text) > 15:
                return RouterResult(Intent.INGEST, text)
            else:
                return RouterResult(Intent.CHAT, text)

        # Call LLM
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ]
        
        # Assuming standard OpenAI-compatible interface
        response = await self.llm_client.chat.completions.create(
            model="qwen-turbo", # Cheap model is enough for routing
            messages=messages,
            response_format={"type": "json_object"} # Force JSON
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        intent_str = data.get("intent", "CHAT")
        summary = data.get("summary", "")

        intent = Intent(intent_str)
        
        # If it's INGEST, we pass the original text (or summary if text is huge)
        # But usually we want the full text for ingestion.
        content_to_process = text if intent == Intent.INGEST else summary

        return RouterResult(intent, content_to_process, reply_hint=summary)
