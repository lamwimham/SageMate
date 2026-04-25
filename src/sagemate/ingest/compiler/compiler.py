"""
Knowledge Compilation Pipeline — Incremental.

The heart of the Karpathy llm-wiki pattern: reads a new source and incrementally
updates the existing wiki — creating new pages, updating existing ones, flagging
contradictions, and maintaining cross-references.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

from ...core.config import Settings, settings
from ...core.store import Store
from ...models import CompileResult
from .source_archive import FullContentRenderer, SourceArchiveRenderer
from .strategies import CompileStrategyFactory


class LLMClient:
    """
    Minimal LLM client interface. Wraps OpenAI-compatible APIs (DashScope/Qwen).
    Reads settings lazily so .env / DB changes take effect without recreating the instance.
    """

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        purpose: str = "compile",
        cost_monitor=None,
    ):
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._purpose = purpose
        self._cost_monitor = cost_monitor
        safe_key = self.api_key[:8] + "..." if self.api_key and len(self.api_key) > 8 else self.api_key
        logger.info(f"[LLMClient] initialized purpose={purpose} base_url={self.base_url} api_key={safe_key} model={self.model}")

    @property
    def base_url(self) -> str:
        return self._base_url or settings.llm_base_url

    @property
    def api_key(self) -> str:
        return self._api_key or settings.llm_api_key

    @property
    def model(self) -> str:
        return self._model or settings.llm_model

    # ── Private helpers ───────────────────────────────────────────

    def _ensure_deps(self):
        """Lazy-import openai + httpx to avoid hard dependency at import time."""
        try:
            from openai import AsyncOpenAI
            import httpx
            return AsyncOpenAI, httpx
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

    def _build_client(self):
        """Create an AsyncOpenAI client with current settings."""
        AsyncOpenAI, httpx = self._ensure_deps()
        timeout = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

    @staticmethod
    def _build_messages(prompt: str, system_prompt: str = "") -> list[dict]:
        """Assemble the OpenAI message list."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _record_cost(self, input_tokens: int, output_tokens: int, duration_ms: float):
        """Delegate cost tracking to the monitor if one is attached."""
        if self._cost_monitor:
            self._cost_monitor.record(
                model=self.model,
                purpose=self._purpose,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
            )

    # ── Public API ────────────────────────────────────────────────

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: Optional[dict] = None,
        max_tokens: int = 32000,
    ) -> dict:
        """Call LLM with structured JSON output."""
        client = self._build_client()
        messages = self._build_messages(prompt, system_prompt)

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if response_format:
            # OpenAI supports json_schema; most compat APIs (DeepSeek, DashScope) only support json_object
            if "openai.com" in self.base_url:
                kwargs["response_format"] = {"type": "json_schema", "json_schema": response_format}
            else:
                kwargs["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        response = await client.chat.completions.create(**kwargs)
        duration_ms = (time.monotonic() - start) * 1000

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        self._record_cost(input_tokens, output_tokens, duration_ms)

        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"LLM returned non-JSON response: {content[:200]}")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2000,
    ) -> str:
        """Call LLM for plain text output."""
        client = self._build_client()
        messages = self._build_messages(prompt, system_prompt)

        start = time.monotonic()
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        duration_ms = (time.monotonic() - start) * 1000

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        self._record_cost(input_tokens, output_tokens, duration_ms)

        return response.choices[0].message.content

    async def generate_text_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2000,
    ):
        """Call LLM for streaming plain text output. Yields token strings."""
        client = self._build_client()
        messages = self._build_messages(prompt, system_prompt)

        start = time.monotonic()
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )

        full_content = ""
        output_tokens = 0
        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                full_content += content
                output_tokens += 1
                yield content

        duration_ms = (time.monotonic() - start) * 1000

        # Streaming responses don't include usage; estimate tokens from content length
        # Rough estimate: 1 token ≈ 4 chars
        CHARS_PER_TOKEN = 4
        estimated_input = (len(prompt) + len(system_prompt)) // CHARS_PER_TOKEN
        estimated_output = len(full_content) // CHARS_PER_TOKEN
        self._record_cost(estimated_input, estimated_output, duration_ms)


# ── JSON Schema for Compiler Output (single source of truth in prompts.py) ──

from .prompts import COMPILE_RESPONSE_SCHEMA  # noqa: F401


class IncrementalCompiler:
    """
    Orchestrates the LLM to incrementally compile raw sources into the wiki.
    Reads a new source, understands the existing wiki context, and produces
    new/updated wiki pages.
    """

    def __init__(
        self,
        store: Store,
        wiki_dir: Path,
        llm_client: Optional[LLMClient] = None,
        settings_obj: Optional[Settings] = None,
        cost_monitor=None,
        source_renderer: Optional[SourceArchiveRenderer] = None,
    ):
        self.store = store
        self.wiki_dir = wiki_dir
        self.cfg = settings_obj or settings
        self.cost_monitor = cost_monitor
        self.source_renderer = source_renderer or FullContentRenderer()
        if llm_client:
            self.llm = llm_client
        else:
            self.llm = LLMClient(
                purpose="compile",
                cost_monitor=cost_monitor,
            )

    async def compile(
        self,
        source_slug: str,
        source_content: str,
        source_title: str,
        progress_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> CompileResult:
        """
        Main compilation flow — delegates to a CompileStrategy selected
        by the CompileStrategyFactory based on document length.
        """
        strategy = CompileStrategyFactory.create(
            source_content=source_content,
            store=self.store,
            wiki_dir=self.wiki_dir,
            llm_client=self.llm,
            settings_obj=self.cfg,
            cost_monitor=self.cost_monitor,
        )
        return await strategy.compile(
            source_slug=source_slug,
            source_content=source_content,
            source_title=source_title,
            progress_callback=progress_callback,
        )

    # Dead-code private methods removed.
    # CompileStrategy (in strategies.py) now owns _write_pages, _update_index, _append_log,
    # _parse_compile_result, _build_system_prompt, _build_compile_prompt.
    # This IncrementalCompiler is a thin delegator to CompileStrategyFactory.
