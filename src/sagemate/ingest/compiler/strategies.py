"""
Compile Strategies — Pluggable compilation pipelines.

Design Patterns:
- Strategy: different algorithms for different document sizes
- Template Method: common skeleton (context → compile → write → index),
  with "compile" step overridden by each strategy.
"""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

from ...core.config import Settings, settings
from ...core.store import Store
from ...models import (
    CompileResult,
    IndexEntry,
    LogEntry,
    LogEntryType,
    SourceArchive,
    WikiCategory,
    WikiPage,
    WikiPageCreate,
)
from .normalizer import CompileResultNormalizer
from .planning import PlanFirstCompileOrchestrator
from .source_archive import FullContentRenderer, SourceArchiveRenderer
from .unit_of_work import WikiWriteUnit

ProgressCallback = Optional[Callable[[str, str], Awaitable[None]]]

# Maximum characters to scan when extracting document outline via LLM
OUTLINE_SCAN_MAX_CHARS = 15000


class CompileStrategy(ABC):
    """
    Abstract compilation strategy.

    Subclasses override `_execute_compile()` to implement different
    approaches (single-pass, chunked, deep-dive, etc.).
    The outer `compile()` method provides the common skeleton:
    reading_context → _execute_compile → writing_pages → updating_index → append_log.
    """

    def __init__(
        self,
        store: Store,
        wiki_dir: Path,
        llm_client: Optional[LLMClient] = None,
        settings_obj: Optional[Settings] = None,
        source_renderer: Optional[SourceArchiveRenderer] = None,
        cost_monitor=None,
    ):
        self.store = store
        self.wiki_dir = wiki_dir
        self.cfg = settings_obj or settings
        self.source_renderer = source_renderer or FullContentRenderer()
        self.normalizer = CompileResultNormalizer()
        if llm_client:
            self.llm = llm_client
        else:
            from .compiler import LLMClient
            self.llm = LLMClient(purpose="compile", cost_monitor=cost_monitor)

    # ── Template Method (skeleton) ───────────────────────────────

    async def compile(
        self,
        source_slug: str,
        source_content: str,
        source_title: str,
        progress_callback: ProgressCallback = None,
    ) -> CompileResult:
        async def _progress(step: str, message: str):
            if progress_callback:
                await progress_callback(step, message)

        # Step 1: Context
        await _progress("reading_context", "正在读取知识库索引...")
        index_context = await self._load_index_context()

        # Step 2: Strategy-specific compilation
        await _progress("calling_llm", "LLM 正在分析文档并提取知识...")
        compile_result = await self._execute_compile(
            source_slug=source_slug,
            source_content=source_content,
            source_title=source_title,
            index_context=index_context,
            progress_callback=progress_callback,
        )
        compile_result = self.normalizer.normalize(
            compile_result,
            source_slug=source_slug,
            source_title=source_title,
        )

        # Step 3: Write pages
        await _progress("writing_pages", f"正在生成 {len(compile_result.new_pages)} 个 Wiki 页面...")
        await self._write_pages(compile_result, source_content=source_content)

        # Step 4: Update index
        await _progress("updating_index", "正在更新知识库索引...")
        await self._update_index()

        # Step 5: Log
        await self._append_log(source_title, source_slug, compile_result)

        return compile_result

    # ── Abstract: override per strategy ──────────────────────────

    @abstractmethod
    async def _execute_compile(
        self,
        *,
        source_slug: str,
        source_content: str,
        source_title: str,
        index_context: str,
        progress_callback: ProgressCallback,
    ) -> CompileResult:
        """Core compilation logic — the part that varies per strategy."""
        ...

    # ── Shared helpers ───────────────────────────────────────────

    async def _load_index_context(self) -> str:
        entries = await self.store.build_index_entries()
        return self._format_index_context(entries)

    def _format_index_context(self, entries: list[IndexEntry]) -> str:
        if not entries:
            return "(Wiki is empty — this is the first source.)"
        max_chars = getattr(self.cfg, "compiler_max_wiki_context_chars", 8000)
        lines = ["Existing wiki pages:"]
        current_len = len(lines[0]) + 1  # +1 for newline
        truncated = False
        for entry in entries:
            line = f"- `{entry.slug}` ({entry.category.value}): {entry.title}"
            if current_len + len(line) + 1 > max_chars:
                truncated = True
                break
            lines.append(line)
            current_len += len(line) + 1
        if truncated:
            lines.append(f"... ({len(entries) - len(lines) + 1} more pages omitted for brevity)")
        return "\n".join(lines)

    def _build_system_prompt(self, conventions: str) -> str:
        from .prompts import CompilePromptBuilder
        return CompilePromptBuilder(
            conventions=conventions, detail_level="comprehensive"
        ).build_system_prompt()

    def _build_compile_prompt(
        self,
        source_title: str,
        source_slug: str,
        source_content: str,
        index_context: str,
    ) -> str:
        from .prompts import CompilePromptBuilder
        conventions = self._load_conventions()
        return CompilePromptBuilder(
            conventions=conventions, detail_level="comprehensive"
        ).build_compile_prompt(
            source_title=source_title,
            source_slug=source_slug,
            source_content=source_content,
            index_context=index_context,
        )

    def _parse_compile_result(self, data: dict, source_slug: str) -> CompileResult:
        result = CompileResult()

        archive_data = data.get("source_archive")
        if archive_data:
            result.source_archive = SourceArchive(**archive_data)

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

        result.contradictions = data.get("contradictions", [])
        return result

    def _load_conventions(self) -> str:
        schema_path = self.cfg.schema_dir / "conventions.md"
        if schema_path.exists():
            return f"## Wiki Conventions (from conventions.md)\n\n{schema_path.read_text(encoding='utf-8')}"
        return ""

    # ── Persistence helpers (shared) ─────────────────────────────

    async def _write_pages(self, result: CompileResult, source_content: str = ""):
        """Write new wiki pages and the Source Archive to disk atomically.

        Rules:
        - Only ONE source page per document (the source archive hub).
        - Compiled pages of category 'source' are dropped — they would duplicate the hub.
        - The source archive records all compiled pages as outbound links.
        """
        uow = WikiWriteUnit(self.wiki_dir)

        # Filter out source-category pages — the archive hub is the canonical source page
        non_source_pages = [p for p in result.new_pages if p.category != WikiCategory.SOURCE]

        if result.source_archive:
            archive = result.source_archive
            content = self.source_renderer.render(archive, source_content)

            # Append compiled-page links to the source archive body
            if non_source_pages:
                links_md = "\n\n## 相关页面\n\n" + "\n".join(
                    f"- [[{p.slug}]] — {p.title}" for p in non_source_pages
                ) + "\n"
                content += links_md
                # Also update the archive's concept list for frontmatter
                archive.extracted_concepts = list(dict.fromkeys(
                    archive.extracted_concepts + [p.slug for p in non_source_pages]
                ))

            archive_rel = Path("sources") / f"{archive.slug}.md"
            uow.schedule_write(archive_rel, content)
            logger.info(f"[Compiler] Created Source Archive: {archive.slug} with {len(non_source_pages)} compiled links")

            frontmatter_end = content.find("---", 3) if content.startswith("---") else -1
            searchable = content[:frontmatter_end + 3] if frontmatter_end != -1 else ""

            source_page = WikiPage(
                slug=archive.slug,
                title=archive.title,
                category=WikiCategory.SOURCE,
                file_path=str(self.wiki_dir / archive_rel),
                content=content,
                summary=archive.summary,
                sources=[],
                outbound_links=[p.slug for p in non_source_pages],
            )
            uow.schedule_db(lambda: self.store.upsert_page(source_page, content, searchable_content=searchable))

        for page in non_source_pages:
            tags_str = ", ".join(f'"{t}"' for t in page.tags) if page.tags else ""
            sources_str = ", ".join(f'"{s}"' for s in page.sources) if page.sources else ""
            source_pages_str = ", ".join(str(p) for p in page.source_pages) if page.source_pages else ""
            pages_field = f"source_pages: [{source_pages_str}]\n" if source_pages_str else ""

            # Auto-extract outbound wikilinks from content (reliable, not dependent on LLM)
            import re
            auto_outbound = re.findall(r'\[\[([^\]]+)\]\]', page.content)
            outbound_links = list(set(auto_outbound)) if auto_outbound else page.outbound_links

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
                "relationship": "relationships",
                "analysis": "analyses",
                "source": "sources",
            }.get(page.category.value, "concepts")
            page_rel = Path(cat_subdir) / f"{page.slug}.md"
            uow.schedule_write(page_rel, full_content)

            wiki_page = WikiPage(
                slug=page.slug,
                title=page.title,
                category=page.category,
                file_path=str(self.wiki_dir / page_rel),
                content=page.content,
                tags=page.tags,
                sources=page.sources,
                outbound_links=outbound_links,
            )
            uow.schedule_db(lambda p=wiki_page, c=page.content: self.store.upsert_page(p, c))

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
        import asyncio
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
            await asyncio.to_thread(
                log_path.write_text,
                "# SageMate Activity Log\n\n" + entry_text.lstrip("\n"),
                encoding='utf-8'
            )
        else:
            def _append():
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(entry_text)
            await asyncio.to_thread(_append)

    def _render_index_md(self, entries: list[IndexEntry]) -> str:
        by_cat: dict[str, list[IndexEntry]] = defaultdict(list)
        for entry in entries:
            by_cat[entry.category.value].append(entry)

        lines = [
            "# Wiki Index",
            "",
            f"*Last updated: {entries[0].last_updated.strftime('%Y-%m-%d %H:%M') if entries else 'never'}*",
            f"*Total pages: {len(entries)}*",
            "",
        ]
        for cat_name in ["entity", "concept", "relationship", "analysis", "source"]:
            cat_entries = by_cat.get(cat_name, [])
            if not cat_entries:
                continue
            lines.append(f"## {cat_name.capitalize()}s")
            lines.append("")
            for entry in cat_entries:
                summary = entry.summary if entry.summary else "(no summary)"
                lines.append(f"- [[{entry.slug}]] — {entry.title}: {summary}")
            lines.append("")
        return "\n".join(lines)


# ── Concrete Strategies ────────────────────────────────────────

class SinglePassStrategy(CompileStrategy):
    """
    Default strategy: one LLM call for the entire document.
    Best for short documents (< 5K chars).
    """

    async def _execute_compile(
        self,
        *,
        source_slug: str,
        source_content: str,
        source_title: str,
        index_context: str,
        progress_callback: ProgressCallback,
    ) -> CompileResult:
        source_text = source_content[:self.cfg.compiler_max_source_chars]
        conventions = self._load_conventions()
        system_prompt = self._build_system_prompt(conventions)
        prompt = self._build_compile_prompt(
            source_title=source_title,
            source_slug=source_slug,
            source_content=source_text,
            index_context=index_context,
        )

        from .prompts import COMPILE_RESPONSE_SCHEMA
        result_data = await self.llm.generate_structured(
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=COMPILE_RESPONSE_SCHEMA,
        )
        return self._parse_compile_result(result_data, source_slug)


class ChunkedStrategy(CompileStrategy):
    """
    Split long documents into chunks and compile each in parallel.
    Best for medium documents (5K ~ 50K chars).
    """

    DEFAULT_CHUNK_SIZE = 8000
    DEFAULT_MAX_CONCURRENT_CHUNKS = 3
    DEFAULT_CHUNK_OVERLAP = 200
    CHUNK_BOUNDARY_WINDOW = 200

    def __init__(self, *args, chunk_size: int = None, max_concurrent: int = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        self.max_concurrent = max_concurrent or self.DEFAULT_MAX_CONCURRENT_CHUNKS

    async def _execute_compile(
        self,
        *,
        source_slug: str,
        source_content: str,
        source_title: str,
        index_context: str,
        progress_callback: ProgressCallback,
    ) -> CompileResult:
        chunks = self._split_into_chunks(source_content, self.chunk_size)
        if getattr(self.cfg, "compiler_plan_first_enabled", True):
            try:
                planned = await PlanFirstCompileOrchestrator(
                    llm=self.llm,
                    max_concurrent=self.max_concurrent,
                    max_pages=getattr(self.cfg, "compiler_plan_first_max_pages", 8),
                ).compile(
                    source_slug=source_slug,
                    source_title=source_title,
                    chunks=chunks,
                    index_context=index_context,
                    progress_callback=progress_callback,
                )
                if planned.new_pages:
                    return planned
                logger.info(
                    "[Compiler] Plan-first compilation produced no pages for %s; falling back to legacy chunk compile.",
                    source_slug,
                )
            except Exception:
                logger.exception(
                    "[Compiler] Plan-first compilation failed for %s; falling back to legacy chunk compile.",
                    source_slug,
                )

        return await self._execute_legacy_chunk_compile(
            chunks=chunks,
            source_slug=source_slug,
            source_title=source_title,
            index_context=index_context,
            progress_callback=progress_callback,
        )

    async def _execute_legacy_chunk_compile(
        self,
        *,
        chunks: list[str],
        source_slug: str,
        source_title: str,
        index_context: str,
        progress_callback: ProgressCallback,
    ) -> CompileResult:
        semaphore = asyncio.Semaphore(self.max_concurrent)
        conventions = self._load_conventions()
        system_prompt = self._build_system_prompt(conventions)

        async def compile_one(idx: int, chunk_text: str) -> CompileResult:
            async with semaphore:
                if progress_callback:
                    await progress_callback(
                        "calling_llm",
                        f"LLM 正在分析第 {idx + 1}/{len(chunks)} 段...",
                    )
                prompt = self._build_compile_prompt(
                    source_title=source_title,
                    source_slug=source_slug,
                    source_content=(
                        f"<!-- chunk={idx + 1}/{len(chunks)} -->\n\n"
                        f"{chunk_text}"
                    ),
                    index_context=index_context,
                )
                from .prompts import COMPILE_RESPONSE_SCHEMA
                data = await self.llm.generate_structured(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_format=COMPILE_RESPONSE_SCHEMA,
                )
                return self._parse_compile_result(data, source_slug)

        results = await asyncio.gather(*[
            compile_one(i, chunk) for i, chunk in enumerate(chunks)
        ])

        return self._merge_results(results, source_slug)

    def _split_into_chunks(self, content: str, chunk_size: int) -> list[str]:
        """Split by semantic boundaries (headings, paragraphs) with overlap."""
        if len(content) <= chunk_size:
            return [content]

        chunks = []
        # Try to split by markdown headings first
        heading_pattern = re.compile(r'^(#{1,6}\s+.+)$', re.MULTILINE)
        headings = list(heading_pattern.finditer(content))

        if len(headings) > 1:
            # Split by headings
            boundaries = [0] + [m.start() for m in headings[1:]] + [len(content)]
            for i in range(len(boundaries) - 1):
                chunk = content[boundaries[i]:boundaries[i + 1]]
                if chunk.strip():
                    chunks.append(chunk)
        else:
            # Fallback: split by paragraphs with overlap
            overlap = 200
            start = 0
            while start < len(content):
                end = min(start + chunk_size, len(content))
                if end < len(content):
                    # Try to break at newline
                    nl_pos = content.rfind('\n', end - 200, end)
                    if nl_pos != -1:
                        end = nl_pos + 1
                chunks.append(content[start:end])
                start = end - overlap if end < len(content) else end

        return chunks or [content]

    def _merge_results(self, results: list[CompileResult], source_slug: str) -> CompileResult:
        """Merge chunk results, deduplicating by slug."""
        merged = CompileResult()
        seen_slugs: set[str] = set()

        # Use first chunk's source archive as the base
        for result in results:
            if result.source_archive and not merged.source_archive:
                merged.source_archive = result.source_archive
            merged.contradictions.extend(result.contradictions)

        # Merge pages, deduplicate by slug
        for result in results:
            for page in result.new_pages:
                if page.slug not in seen_slugs:
                    seen_slugs.add(page.slug)
                    merged.new_pages.append(page)

        # If no archive was produced, create a minimal one
        if not merged.source_archive:
            from ...models import SourceArchive
            merged.source_archive = SourceArchive(
                slug=source_slug,
                title=source_slug,
                summary="Compiled from multiple chunks.",
                key_takeaways=[],
                extracted_concepts=[p.slug for p in merged.new_pages],
            )

        return merged


class DeepCompileStrategy(CompileStrategy):
    """
    For very long documents (> 50K chars):
    1. Scan outline (light LLM call)
    2. Select high-importance chapters
    3. Compile selected chapters with ChunkedStrategy
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chunked = ChunkedStrategy(*args, **kwargs)

    async def _execute_compile(
        self,
        *,
        source_slug: str,
        source_content: str,
        source_title: str,
        index_context: str,
        progress_callback: ProgressCallback,
    ) -> CompileResult:
        # Step 1: Outline scan
        if progress_callback:
            await progress_callback("calling_llm", "正在扫描文档结构...")
        outline = await self._scan_outline(source_content)

        # Step 2: Select important chapters
        important = [c for c in outline.chapters if c.importance in ("high", "medium")]
        if not important:
            important = outline.chapters[:3]  # Fallback: first 3 chapters

        if progress_callback:
            await progress_callback(
                "calling_llm",
                f"精选 {len(important)} 个核心章节进行深度编译...",
            )

        # Step 3: Compile each selected chapter
        merged = CompileResult()
        merged.source_archive = outline.to_archive(source_slug, source_title)

        for chapter in important:
            chapter_result = await self._chunked._execute_compile(
                source_slug=source_slug,
                source_content=(
                    f"<!-- chapter={chapter.index}: {chapter.title} -->\n\n"
                    f"{chapter.content}"
                ),
                source_title=source_title,
                index_context=index_context,
                progress_callback=progress_callback,
            )
            # Merge pages
            seen = {p.slug for p in merged.new_pages}
            for page in chapter_result.new_pages:
                if page.slug not in seen:
                    merged.new_pages.append(page)
            merged.contradictions.extend(chapter_result.contradictions)

        # Update archive with final concept list
        if merged.source_archive:
            merged.source_archive.extracted_concepts = [p.slug for p in merged.new_pages]

        return merged

    async def _scan_outline(self, content: str) -> "DocumentOutline":
        """Lightweight LLM call to extract document structure."""
        scan_prompt = f"""Analyze this document and return a JSON outline.

Document (first {OUTLINE_SCAN_MAX_CHARS} chars):
{content[:OUTLINE_SCAN_MAX_CHARS]}

Return JSON with:
- title: document title
- chapters: array of {{index, title, summary, importance (high/medium/low), estimated_page_range}}
"""
        schema = {
            "name": "document_outline",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "chapters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "index": {"type": "integer"},
                                "title": {"type": "string"},
                                "summary": {"type": "string"},
                                "importance": {"type": "string", "enum": ["high", "medium", "low"]},
                                "estimated_page_range": {"type": "string"},
                            },
                            "required": ["index", "title", "summary", "importance"],
                        },
                    },
                },
                "required": ["title", "chapters"],
            },
        }

        data = await self.llm.generate_structured(
            prompt=scan_prompt,
            system_prompt="You are a document analyst. Extract the structure concisely.",
            response_format=schema,
        )
        return DocumentOutline.from_llm(data, content)


# ── Outline data structures ────────────────────────────────────

class ChapterInfo:
    def __init__(self, index: int, title: str, summary: str, importance: str,
                 content: str, page_range: str = ""):
        self.index = index
        self.title = title
        self.summary = summary
        self.importance = importance
        self.content = content
        self.page_range = page_range


class DocumentOutline:
    def __init__(self, title: str, chapters: list[ChapterInfo]):
        self.title = title
        self.chapters = chapters

    def to_archive(self, source_slug: str, source_title: str) -> SourceArchive:
        from ...models import SourceArchive
        return SourceArchive(
            slug=source_slug,
            title=source_title,
            summary=f"Document outline: {self.title}. {len(self.chapters)} chapters identified.",
            key_takeaways=[c.summary for c in self.chapters if c.importance == "high"],
            extracted_concepts=[],
        )

    @classmethod
    def from_llm(cls, data: dict, full_content: str) -> "DocumentOutline":
        raw_chapters = data.get("chapters", [])
        chapters = []
        for position, chapter in enumerate(raw_chapters):
            idx = chapter.get("index", len(chapters) + 1)
            title = chapter.get("title", f"Chapter {idx}")
            next_title = (
                raw_chapters[position + 1].get("title")
                if position + 1 < len(raw_chapters)
                else None
            )
            chapters.append(ChapterInfo(
                index=idx,
                title=title,
                summary=chapter.get("summary", ""),
                importance=chapter.get("importance", "medium"),
                content=cls._extract_chapter_content(
                    full_content,
                    title=title,
                    next_title=next_title,
                    page_range=chapter.get("estimated_page_range", ""),
                ),
                page_range=chapter.get("estimated_page_range", ""),
            ))
        return cls(title=data.get("title", "Untitled"), chapters=chapters)

    @staticmethod
    def _extract_chapter_content(
        full_content: str,
        *,
        title: str,
        next_title: str | None,
        page_range: str = "",
    ) -> str:
        by_pages = DocumentOutline._extract_by_page_range(full_content, page_range)
        if by_pages:
            return by_pages

        start = DocumentOutline._find_heading_start(full_content, title)
        if start is None:
            return full_content

        end = len(full_content)
        if next_title:
            next_start = DocumentOutline._find_heading_start(full_content, next_title, start + 1)
            if next_start is not None:
                end = next_start
        return full_content[start:end].strip()

    @staticmethod
    def _extract_by_page_range(full_content: str, page_range: str) -> str:
        pages = DocumentOutline._parse_page_range(page_range)
        if not pages or "<!-- page=" not in full_content:
            return ""

        pattern = re.compile(r"<!--\s*page=(\d+)\s*-->(.*?)(?=<!--\s*page=\d+\s*-->|$)", re.DOTALL)
        chunks = [
            match.group(0).strip()
            for match in pattern.finditer(full_content)
            if int(match.group(1)) in pages
        ]
        return "\n\n".join(chunks)

    @staticmethod
    def _parse_page_range(page_range: str) -> set[int]:
        pages: set[int] = set()
        for start, end in re.findall(r"(\d+)(?:\s*[-–]\s*(\d+))?", page_range or ""):
            start_num = int(start)
            end_num = int(end) if end else start_num
            pages.update(range(start_num, end_num + 1))
        return pages

    @staticmethod
    def _find_heading_start(content: str, title: str, offset: int = 0) -> int | None:
        escaped = re.escape(title.strip())
        heading = re.search(rf"(?im)^#{{1,6}}\s+{escaped}\s*$", content[offset:])
        if heading:
            return offset + heading.start()

        plain = re.search(rf"(?im)^{escaped}\s*$", content[offset:])
        if plain:
            return offset + plain.start()
        return None


# ── Strategy Factory ───────────────────────────────────────────

class CompileStrategyFactory:
    """Selects the appropriate strategy based on document length."""

    FASTLANE_THRESHOLD = 5000
    CHUNKED_THRESHOLD = 50000

    @classmethod
    def create(
        cls,
        source_content: str,
        store: Store,
        wiki_dir: Path,
        llm_client: Optional[LLMClient] = None,
        settings_obj: Optional[Settings] = None,
        cost_monitor=None,
    ) -> CompileStrategy:
        char_count = len(source_content)

        if char_count < cls.FASTLANE_THRESHOLD:
            return SinglePassStrategy(store, wiki_dir, llm_client, settings_obj, cost_monitor=cost_monitor)
        elif char_count < cls.CHUNKED_THRESHOLD:
            return ChunkedStrategy(store, wiki_dir, llm_client, settings_obj, cost_monitor=cost_monitor)
        else:
            return DeepCompileStrategy(store, wiki_dir, llm_client, settings_obj, cost_monitor=cost_monitor)
