"""
Knowledge Compilation Pipeline — Incremental.

The heart of the Karpathy llm-wiki pattern: reads a new source and incrementally
updates the existing wiki — creating new pages, updating existing ones, flagging
contradictions, and maintaining cross-references.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from ..core.config import Settings, settings
from ..core.store import Store
from ..models import (
    CompileResult,
    IndexEntry,
    LogEntry,
    LogEntryType,
    WikiCategory,
    WikiPageCreate,
)


class LLMClient:
    """
    Minimal LLM client interface. Wraps OpenAI-compatible APIs (DashScope/Qwen).
    """

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
    ):
        self.base_url = base_url or settings.llm_base_url
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: Optional[dict] = None,
        max_tokens: int = 4000,
    ) -> dict:
        """Call LLM with structured JSON output."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

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

        response = await client.chat.completions.create(**kwargs)
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
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


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
    ):
        self.store = store
        self.wiki_dir = wiki_dir
        self.llm = llm_client or LLMClient()
        self.cfg = settings_obj or settings

    async def compile(
        self,
        source_slug: str,
        source_content: str,
        source_title: str,
    ) -> CompileResult:
        """
        Main compilation flow:
        1. Read existing wiki index to understand scope
        2. Read relevant existing pages for context
        3. Call LLM to analyze source and produce wiki updates
        4. Write new pages to disk
        5. Update index.md and log.md
        """
        # Step 1: Get wiki index context
        index_entries = await self.store.build_index_entries()
        index_context = self._format_index_context(index_entries)

        # Step 2: Truncate source if too long
        source_text = source_content[:self.cfg.compiler_max_source_chars]

        # Step 3: Load schema conventions if available
        conventions = self._load_conventions()

        # Step 4: Build LLM prompt
        system_prompt = self._build_system_prompt(conventions)
        prompt = self._build_compile_prompt(
            source_title=source_title,
            source_slug=source_slug,
            source_content=source_text,
            index_context=index_context,
        )

        # Step 5: Call LLM
        result_data = await self.llm.generate_structured(
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=COMPILE_RESPONSE_SCHEMA,
        )

        # Step 6: Parse and validate result
        compile_result = self._parse_compile_result(result_data, source_slug)

        # Step 7: Write new pages to disk
        await self._write_pages(compile_result)

        # Step 8: Update index.md
        await self._update_index()

        # Step 9: Append to log.md
        await self._append_log(source_title, source_slug, compile_result)

        return compile_result

    def _build_system_prompt(self, conventions: str) -> str:
        return f"""You are a Knowledge Compiler for a personal wiki (Second Brain).
Your job is to read new source documents and incrementally update the wiki.

CRITICAL LANGUAGE RULE: You MUST write the wiki pages in the EXACT SAME LANGUAGE as the source document.
- If the source is in Chinese, write ALL wiki content in Chinese.
- If the source is in English, write in English.
- NEVER translate the source content. Preserve all original terminology.

Rules:
1. Extract key entities (people, orgs, products) and concepts from the source.
2. Create new wiki pages for important entities and concepts.
3. Use concise, informative markdown. Each page should be self-contained.
4. Include wikilinks [[like-this]] to reference other wiki pages.
5. Flag any claims that seem to contradict existing wiki content.
6. Keep pages focused — one concept per page.
7. Use the slug format: lowercase-kebab-case, no special characters.
8. Categories: 'entity' for people/orgs/products, 'concept' for ideas/frameworks, 'analysis' for comparisons.

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
        from ..models import SourceArchive
        
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

    async def _write_pages(self, result: CompileResult):
        """Write new wiki pages and the Source Archive to disk."""
        
        # 1. Write Source Archive (The "Hub")
        if result.source_archive:
            archive = result.source_archive
            # Create links to extracted concepts
            links = "\n".join(f"- [[{slug}]]" for slug in archive.extracted_concepts)
            takeaways = "\n".join(f"- {t}" for t in archive.key_takeaways)
            
            content = f"""# 📄 {archive.title}

> **Summary**
{archive.summary}

## 🔑 Key Takeaways
{takeaways}

## 🔗 Extracted Concepts
{links}

---
*Archived automatically by SageMate.*
"""
            # Write to wiki/sources/
            archive_path = self.cfg.wiki_dir / "sources" / f"{archive.slug}.md"
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            archive_path.write_text(content, encoding='utf-8')
            print(f"[Compiler] Created Source Archive: {archive.slug}")

        # 2. Write Knowledge Wiki Pages (The "Leaves")
        for page in result.new_pages:
            cat_dir = self.cfg.wiki_dir_for_category(page.category.value)

            # Build full markdown with frontmatter
            tags_str = ", ".join(f'"{t}"' for t in page.tags) if page.tags else ""
            sources_str = ", ".join(f'"{s}"' for s in page.sources) if page.sources else ""
            
            # Add source_pages if available
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
            
            # ⚠️ Fix: Strip existing YAML frontmatter from LLM output if it included it
            content = page.content
            if content.startswith("---"):
                # Find the closing '---'
                end_index = content.find("---", 3)
                if end_index != -1:
                    # Remove the header block (--- ... ---)
                    content = content[end_index + 3:].lstrip("\n")
            
            full_content = frontmatter + content

            file_path = cat_dir / f"{page.slug}.md"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(full_content, encoding='utf-8')

            # Also upsert to Store
            from ..models import WikiPage
            wiki_page = WikiPage(
                slug=page.slug,
                title=page.title,
                category=page.category,
                file_path=str(file_path),
                content=page.content,
                tags=page.tags,
                sources=page.sources,
                outbound_links=page.outbound_links,
            )
            await self.store.upsert_page(wiki_page, page.content)

    async def _update_index(self):
        """Rebuild index.md from current wiki state."""
        entries = await self.store.build_index_entries()
        index_md = self._render_index_md(entries)

        index_path = self.wiki_dir / "index.md"
        index_path.write_text(index_md, encoding='utf-8')

    async def _append_log(self, source_title: str, source_slug: str, result: CompileResult):
        """Append an ingest entry to log.md."""
        log_path = self.wiki_dir / "log.md"

        entry = LogEntry(
            entry_type=LogEntryType.INGEST,
            title=source_title,
            details=f"Ingested source `{source_slug}`. Created {len(result.new_pages)} new wiki pages. "
                    f"Contradictions flagged: {len(result.contradictions)}.",
            affected_pages=[p.slug for p in result.new_pages],
        )

        if log_path.exists():
            existing = log_path.read_text(encoding='utf-8')
            new_content = existing + "\n---\n\n" + entry.format_md() + "\n"
        else:
            new_content = "# SageMate Activity Log\n\n" + entry.format_md() + "\n"

        log_path.write_text(new_content, encoding='utf-8')

    def _format_index_context(self, entries: list[IndexEntry]) -> str:
        if not entries:
            return "(Wiki is empty — this is the first source.)"
        lines = ["Existing wiki pages:"]
        for e in entries:
            lines.append(f"- `{e.slug}` ({e.category.value}): {e.title}")
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
