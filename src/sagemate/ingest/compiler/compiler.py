"""
Knowledge Compilation Pipeline — Incremental.

The heart of the Karpathy llm-wiki pattern: reads a new source and incrementally
updates the existing wiki — creating new pages, updating existing ones, flagging
contradictions, and maintaining cross-references.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

from ...core.config import Settings, settings
from ...core.store import Store
from ...models import (
    CompileResult,
    IndexEntry,
    LogEntry,
    LogEntryType,
    WikiCategory,
    WikiPage,
    WikiPageCreate,
)
from .source_archive import FullContentRenderer, SourceArchiveRenderer
from .strategies import CompileStrategyFactory
from .unit_of_work import WikiWriteUnit


class LLMClient:
    """
    Minimal LLM client interface. Wraps OpenAI-compatible APIs (DashScope/Qwen).
    """

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        purpose: str = "compile",
        cost_monitor=None,
    ):
        self.base_url = base_url or settings.llm_base_url
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self._purpose = purpose
        self._cost_monitor = cost_monitor

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: Optional[dict] = None,
        max_tokens: int = 8000,
    ) -> dict:
        """Call LLM with structured JSON output."""
        try:
            from openai import AsyncOpenAI
            import httpx
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        timeout = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = {"type": "json_schema", "json_schema": response_format}

        start = time.monotonic()
        response = await client.chat.completions.create(**kwargs)
        duration_ms = (time.monotonic() - start) * 1000

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        # Record cost
        if self._cost_monitor:
            self._cost_monitor.record(
                model=self.model,
                purpose=self._purpose,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
            )

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
        try:
            from openai import AsyncOpenAI
            import httpx
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        timeout = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

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

        if self._cost_monitor:
            self._cost_monitor.record(
                model=self.model,
                purpose=self._purpose,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
            )

        return response.choices[0].message.content

    async def generate_text_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2000,
    ):
        """
        Call LLM for streaming plain text output.
        Yields individual token strings as they arrive.
        """
        try:
            from openai import AsyncOpenAI
            import httpx
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        timeout = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

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
        # This is approximate but sufficient for cost monitoring
        if self._cost_monitor:
            # Rough estimate: 1 token ≈ 3-4 chars for CJK, 4 chars for English
            estimated_input = len(prompt) // 4 + len(system_prompt) // 4
            estimated_output = len(full_content) // 4
            self._cost_monitor.record(
                model=self.model,
                purpose=self._purpose,
                input_tokens=estimated_input,
                output_tokens=estimated_output,
                duration_ms=duration_ms,
            )


# ── JSON Schema for Compiler Output ─────────────────────────────

COMPILE_RESPONSE_SCHEMA = {
    "name": "compile_result",
    "schema": {
        "type": "object",
        "properties": {
            "source_archive": {
                "type": "object",
                "description": "A high-level summary of the entire document. Use this to create a 'Source Page' that acts as the hub for this document.",
                "properties": {
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string", "description": "A concise abstract of the document (3-5 sentences)."},
                    "key_takeaways": {"type": "array", "items": {"type": "string"}, "description": "3-5 core arguments or conclusions from the document."},
                    "extracted_concepts": {"type": "array", "items": {"type": "string"}, "description": "List of slugs for the knowledge pages you are creating from this doc."}
                },
                "required": ["slug", "title", "summary", "key_takeaways", "extracted_concepts"]
            },
            "new_pages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string"},
                        "title": {"type": "string"},
                        "category": {"type": "string", "enum": ["entity", "concept", "analysis", "source"]},
                        "content": {"type": "string"},
                        "source_pages": {
                            "type": "array", 
                            "items": {"type": "integer"},
                            "description": "List of page numbers (integers) found in the source document corresponding to this content."
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "sources": {"type": "array", "items": {"type": "string"}},
                        "outbound_links": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["slug", "title", "category", "content", "source_pages"],
                },
            },
            "contradictions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["source_archive", "new_pages"],
    },
}


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

    def _build_system_prompt(self, conventions: str) -> str:
        return f"""You are a Knowledge Compiler for a personal wiki (Second Brain).
Your job is to read new source documents and incrementally update the wiki.

CRITICAL LANGUAGE RULE: You MUST write the wiki pages in the EXACT SAME LANGUAGE as the source document.
- If the source is in Chinese, write ALL wiki content in Chinese.
- If the source is in English, write in English.
- NEVER translate the source content. Preserve all original terminology.

SLUG RULE (critical for wikilinks):
- The slug is the identifier inside [[wikilinks]]. It MUST be human-readable.
- For Chinese pages: use Chinese slugs (e.g. [[扩散模型]], [[Sora技术报告]]).
  Remove spaces between Chinese characters. Keep Latin acronyms as-is.
- For English pages: use lowercase-kebab-case (e.g. [[diffusion-model]], [[sora-technical-report]]).
- Match the language of the page title. Do NOT romanize Chinese titles into pinyin.

Rules:
1. Extract key entities (people, orgs, products) and concepts from the source.
2. Create new wiki pages for important entities and concepts.
3. Use concise, informative markdown. Each page should be self-contained.
4. Include wikilinks [[slug]] to reference other wiki pages.
5. Flag any claims that seem to contradict existing wiki content.
6. Keep pages focused — one concept per page.
7. Categories: 'entity' for people/orgs/products, 'concept' for ideas/frameworks, 'analysis' for comparisons.

Page format:
- Start with a clear definition/summary in the first paragraph.
- Use headings for structure.
- End with a "Related" section linking to other wiki pages.
- Use YAML frontmatter with: title, slug, category, tags.

{conventions}"""

    def _build_compile_prompt(
        self,
        source_title: str,
        source_slug: str,
        source_content: str,
        index_context: str,
    ) -> str:
        return f"""Analyze the following source document and integrate its knowledge into the wiki.

## Source: {source_title} (slug: {source_slug})

{source_content}

## Current Wiki Index

{index_context}

## Task

Read the source document and perform two actions:

### Action 1: Create a "Source Archive"
Generate a high-level summary of this document to serve as the "Hub Page" for this file.
- **summary**: A concise abstract (3-5 sentences) explaining what this document is about.
- **key_takeaways**: 3-5 bullet points of the most important arguments or conclusions.
- **extracted_concepts**: List the slugs of the specific knowledge pages you are about to create.

### Action 2: Extract Knowledge Pages
Create new wiki pages for key entities and concepts found in the source.
- **IMPORTANT**: Identify the source page numbers. The input text contains markers like `<!-- page=1 -->`, `<!-- page=2 -->`.
  - For each wiki page you create, you MUST extract the list of page numbers (integers) that contributed to that content and put them in the `source_pages` field.

Return a JSON object with:
- source_archive: The summary object (slug, title, summary, key_takeaways, extracted_concepts).
- new_pages: array of wiki pages to create (each with slug, title, category, content, source_pages, tags, outbound_links).
- contradictions: array of any contradictions found (empty if none)."""

    def _parse_compile_result(self, data: dict, source_slug: str) -> CompileResult:
        from ...models import SourceArchive
        
        result = CompileResult()
        
        # Parse Source Archive (The "One-Pager")
        archive_data = data.get("source_archive")
        if archive_data:
            result.source_archive = SourceArchive(**archive_data)
        
        # Parse Knowledge Pages
        for page_data in data.get("new_pages", []):
            page = WikiPageCreate(
                slug=page_data["slug"],
                title=page_data["title"],
                category=WikiCategory(page_data.get("category", "concept")),
                content=page_data["content"],
                source_pages=page_data.get("source_pages", []),
                tags=page_data.get("tags", []),
                sources=[source_slug],
                outbound_links=page_data.get("outbound_links", []),
            )
            result.new_pages.append(page)

        return result

    async def _write_pages(self, result: CompileResult, source_content: str = ""):
        """Write new wiki pages and the Source Archive to disk atomically."""
        uow = WikiWriteUnit(self.cfg.wiki_dir)

        # 1. Source Archive (The "Hub")
        if result.source_archive:
            archive = result.source_archive
            content = self.source_renderer.render(archive, source_content)

            archive_rel = Path("sources") / f"{archive.slug}.md"
            uow.schedule_write(archive_rel, content)
            print(f"[Compiler] Created Source Archive: {archive.slug}")

            frontmatter_end = content.find("---", 3) if content.startswith("---") else -1
            searchable = content[:frontmatter_end + 3] if frontmatter_end != -1 else ""

            source_page = WikiPage(
                slug=archive.slug,
                title=archive.title,
                category=WikiCategory.SOURCE,
                file_path=str(self.cfg.wiki_dir / archive_rel),
                content=content,
                summary=archive.summary,
                sources=[],
            )
            uow.schedule_db(lambda: self.store.upsert_page(source_page, content, searchable_content=searchable))

        # 2. Knowledge Wiki Pages (The "Leaves")
        for page in result.new_pages:
            tags_str = ", ".join(f'"{t}"' for t in page.tags) if page.tags else ""
            sources_str = ", ".join(f'"{s}"' for s in page.sources) if page.sources else ""
            source_pages_str = ", ".join(str(p) for p in page.source_pages) if page.source_pages else ""
            pages_field = f"source_pages: [{source_pages_str}]\n" if source_pages_str else ""

            frontmatter = f"""---
title: '{page.title}'
slug: {page.slug}
category: {page.category.value}
tags: [{tags_str}]
sources: [{sources_str}]
{pages_field}---

"""
            content = page.content
            if content.startswith("---"):
                end_index = content.find("---", 3)
                if end_index != -1:
                    content = content[end_index + 3:].lstrip("\n")
            full_content = frontmatter + content

            cat_subdir = {
                "entity": "entities",
                "concept": "concepts",
                "analysis": "analyses",
                "source": "sources",
            }.get(page.category.value, "concepts")
            page_rel = Path(cat_subdir) / f"{page.slug}.md"
            uow.schedule_write(page_rel, full_content)

            wiki_page = WikiPage(
                slug=page.slug,
                title=page.title,
                category=page.category,
                file_path=str(self.cfg.wiki_dir / page_rel),
                content=page.content,
                tags=page.tags,
                sources=page.sources,
                outbound_links=page.outbound_links,
            )
            uow.schedule_db(lambda p=wiki_page, c=page.content: self.store.upsert_page(p, c))

        # 3. Atomic commit
        await uow.commit()

    async def _update_index(self):
        """Rebuild index.md from current wiki state atomically."""
        entries = await self.store.build_index_entries()
        index_md = self._render_index_md(entries)

        uow = WikiWriteUnit(self.wiki_dir)
        uow.schedule_write(Path("index.md"), index_md)
        await uow.commit()

    async def _append_log(self, source_title: str, source_slug: str, result: CompileResult):
        """Append an ingest entry to log.md using append-only mode."""
        log_path = self.wiki_dir / "log.md"

        entry = LogEntry(
            entry_type=LogEntryType.INGEST,
            title=source_title,
            details=f"Ingested source `{source_slug}`. Created {len(result.new_pages)} new wiki pages. "
                    f"Contradictions flagged: {len(result.contradictions)}.",
            affected_pages=[p.slug for p in result.new_pages],
        )

        entry_text = "\n---\n\n" + entry.format_md() + "\n"

        if not log_path.exists():
            # First write: create file with header
            log_path.write_text("# SageMate Activity Log\n\n" + entry_text.lstrip("\n"), encoding='utf-8')
        else:
            # Append mode ('a') is safe for concurrent writers at OS level
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(entry_text)

    def _format_index_context(self, entries: list[IndexEntry]) -> str:
        if not entries:
            return "(Wiki is empty — this is the first source.)"
        max_chars = getattr(self.cfg, "compiler_max_wiki_context_chars", 8000)
        lines = ["Existing wiki pages:"]
        current_len = len(lines[0]) + 1
        truncated = False
        for e in entries:
            line = f"- `{e.slug}` ({e.category.value}): {e.title}"
            if current_len + len(line) + 1 > max_chars:
                truncated = True
                break
            lines.append(line)
            current_len += len(line) + 1
        if truncated:
            lines.append(f"... ({len(entries) - len(lines) + 1} more pages omitted for brevity)")
        return "\n".join(lines)

    def _render_index_md(self, entries: list[IndexEntry]) -> str:
        from collections import defaultdict
        by_cat: dict[str, list[IndexEntry]] = defaultdict(list)
        for e in entries:
            by_cat[e.category.value].append(e)

        lines = [
            "# Wiki Index",
            "",
            f"*Last updated: {entries[0].last_updated.strftime('%Y-%m-%d %H:%M') if entries else 'never'}*",
            f"*Total pages: {len(entries)}*",
            "",
        ]

        for cat_name in ["entity", "concept", "analysis", "source"]:
            cat_entries = by_cat.get(cat_name, [])
            if not cat_entries:
                continue
            lines.append(f"## {cat_name.capitalize()}s")
            lines.append("")
            for e in cat_entries:
                summary = e.summary if e.summary else "(no summary)"
                lines.append(f"- [[{e.slug}]] — {e.title}: {summary}")
            lines.append("")

        return "\n".join(lines)

    def _load_conventions(self) -> str:
        schema_path = self.cfg.schema_dir / "conventions.md"
        if schema_path.exists():
            return f"## Wiki Conventions (from conventions.md)\n\n{schema_path.read_text(encoding='utf-8')}"
        return ""
