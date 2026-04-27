"""
Plan-first compilation primitives.

Long documents should not let each chunk independently create final wiki
pages. This module separates the flow into:
1. local chunk scan -> lightweight knowledge candidates
2. deterministic global plan -> final page set
3. page assembly -> one stable wiki page per planned item
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from ...core.slug import SlugGenerator
from ...models import CompilePlanSummary, CompileResult, SourceArchive, WikiCategory, WikiPageCreate

ProgressCallback = Optional[Callable[[str, str], Awaitable[None]]]

PLANNABLE_CATEGORIES = {
    WikiCategory.ENTITY,
    WikiCategory.CONCEPT,
    WikiCategory.RELATIONSHIP,
    WikiCategory.ANALYSIS,
}


class EvidenceRef(BaseModel):
    """A small source-backed snippet that can justify a planned wiki page."""

    chunk_index: int
    quote: str = ""
    source_pages: list[int] = Field(default_factory=list)
    block_ids: list[str] = Field(default_factory=list)


class KnowledgeCandidate(BaseModel):
    """A local scan result; not yet a final wiki page decision."""

    slug: str
    title: str
    category: WikiCategory = WikiCategory.CONCEPT
    summary: str = ""
    aliases: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class LocalScanResult(BaseModel):
    """Candidates discovered from one document chunk."""

    chunk_index: int
    total_chunks: int
    candidates: list[KnowledgeCandidate] = Field(default_factory=list)


class PlannedWikiPage(BaseModel):
    """A final page selected by the global plan."""

    slug: str
    title: str
    category: WikiCategory
    reason: str = ""
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)

    @property
    def source_pages(self) -> list[int]:
        pages: list[int] = []
        for ref in self.evidence_refs:
            pages.extend(ref.source_pages)
        return list(dict.fromkeys(pages))


class CompilePlan(BaseModel):
    """The global decision about which wiki pages this source should produce."""

    source_slug: str
    source_title: str
    pages: list[PlannedWikiPage] = Field(default_factory=list)


class CandidatePlanBuilder:
    """Merge local candidates into a deterministic global compile plan."""

    def __init__(self, max_pages: int = 8, max_evidence_per_page: int = 8):
        self.max_pages = max_pages
        self.max_evidence_per_page = max_evidence_per_page

    def build(
        self,
        scans: list[LocalScanResult],
        *,
        source_slug: str,
        source_title: str,
    ) -> CompilePlan:
        merged: dict[str, KnowledgeCandidate] = {}
        for scan in scans:
            for candidate in scan.candidates:
                if candidate.category not in PLANNABLE_CATEGORIES:
                    continue
                key = candidate.slug or SlugGenerator.generate(candidate.title)
                if key not in merged:
                    candidate.slug = key
                    merged[key] = candidate
                    continue

                existing = merged[key]
                existing.aliases = list(dict.fromkeys([*existing.aliases, *candidate.aliases]))
                existing.evidence_refs = [*existing.evidence_refs, *candidate.evidence_refs]
                if len(candidate.summary) > len(existing.summary):
                    existing.summary = candidate.summary

        candidates = sorted(
            merged.values(),
            key=lambda c: (-len(c.evidence_refs), -self._category_rank(c.category), c.title.lower()),
        )
        pages = [
            PlannedWikiPage(
                slug=c.slug,
                title=c.title,
                category=c.category,
                reason=c.summary,
                evidence_refs=c.evidence_refs[: self.max_evidence_per_page],
            )
            for c in candidates[: self.max_pages]
        ]
        return CompilePlan(source_slug=source_slug, source_title=source_title, pages=pages)

    @staticmethod
    def _category_rank(category: WikiCategory) -> int:
        return {
            WikiCategory.CONCEPT: 4,
            WikiCategory.ENTITY: 3,
            WikiCategory.RELATIONSHIP: 2,
            WikiCategory.ANALYSIS: 1,
        }.get(category, 0)


@dataclass
class CompileBudgetPolicy:
    """Cost and quality boundaries for plan-first compilation."""

    max_scan_chunks: int = 12
    max_pages: int = 8
    max_evidence_per_page: int = 8
    max_evidence_quote_chars: int = 800

    @classmethod
    def from_settings(cls, cfg: object) -> "CompileBudgetPolicy":
        return cls(
            max_scan_chunks=max(1, int(getattr(cfg, "compiler_plan_first_max_scan_chunks", 12))),
            max_pages=max(1, int(getattr(cfg, "compiler_plan_first_max_pages", 8))),
            max_evidence_per_page=max(1, int(getattr(cfg, "compiler_plan_first_max_evidence_per_page", 8))),
            max_evidence_quote_chars=max(120, int(getattr(cfg, "compiler_plan_first_max_evidence_quote_chars", 800))),
        )

    def select_chunks(self, chunks: list[str]) -> list[tuple[int, str]]:
        """Pick a bounded, evenly distributed subset of chunks."""
        if not chunks:
            return []
        if len(chunks) <= self.max_scan_chunks:
            return list(enumerate(chunks))
        if self.max_scan_chunks == 1:
            return [(0, chunks[0])]

        last_index = len(chunks) - 1
        selected_indexes = {
            round(i * last_index / (self.max_scan_chunks - 1))
            for i in range(self.max_scan_chunks)
        }
        return [(index, chunks[index]) for index in sorted(selected_indexes)]

    def trim_quote(self, quote: object) -> str:
        text = str(quote).strip()
        if len(text) <= self.max_evidence_quote_chars:
            return text
        return text[: self.max_evidence_quote_chars].rstrip() + "..."


@dataclass
class PlanFirstCompileOrchestrator:
    """Coordinates scan -> plan -> assemble for chunked compilation."""

    llm: object
    max_concurrent: int = 3
    max_pages: int = 8
    budget: CompileBudgetPolicy | None = None

    def _budget(self) -> CompileBudgetPolicy:
        return self.budget or CompileBudgetPolicy(max_pages=self.max_pages)

    async def compile(
        self,
        *,
        source_slug: str,
        source_title: str,
        chunks: list[str],
        index_context: str,
        progress_callback: ProgressCallback = None,
    ) -> CompileResult:
        scans = await self.scan_chunks(
            source_slug=source_slug,
            source_title=source_title,
            chunks=chunks,
            progress_callback=progress_callback,
        )
        budget = self._budget()
        plan = CandidatePlanBuilder(
            max_pages=budget.max_pages,
            max_evidence_per_page=budget.max_evidence_per_page,
        ).build(
            scans,
            source_slug=source_slug,
            source_title=source_title,
        )
        plan_summary = self._build_summary(
            plan=plan,
            scans=scans,
            total_chunks=len(chunks),
            budget=budget,
        )
        if not plan.pages:
            return CompileResult(
                source_archive=self._source_archive(plan),
                plan_summary=plan_summary,
            )

        pages = await self.assemble_pages(
            plan=plan,
            index_context=index_context,
            progress_callback=progress_callback,
        )
        return CompileResult(
            source_archive=self._source_archive(plan),
            new_pages=pages,
            plan_summary=plan_summary,
        )

    async def scan_chunks(
        self,
        *,
        source_slug: str,
        source_title: str,
        chunks: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[LocalScanResult]:
        semaphore = asyncio.Semaphore(self.max_concurrent)
        selected_chunks = self._budget().select_chunks(chunks)
        total_chunks = len(chunks)

        async def scan_one(index: int, chunk: str) -> LocalScanResult:
            async with semaphore:
                if progress_callback:
                    await progress_callback(
                        "calling_llm",
                        f"正在扫描第 {index + 1}/{total_chunks} 段候选知识...",
                    )
                data = await self.llm.generate_structured(
                    prompt=self._build_scan_prompt(
                        source_slug=source_slug,
                        source_title=source_title,
                        chunk_index=index,
                        total_chunks=total_chunks,
                        chunk_text=chunk,
                    ),
                    system_prompt=LOCAL_SCAN_SYSTEM_PROMPT,
                    response_format=LOCAL_SCAN_RESPONSE_SCHEMA,
                )
                return self._parse_scan_result(data, index, total_chunks)

        return await asyncio.gather(*[scan_one(i, chunk) for i, chunk in selected_chunks])

    async def assemble_pages(
        self,
        *,
        plan: CompilePlan,
        index_context: str,
        progress_callback: ProgressCallback = None,
    ) -> list[WikiPageCreate]:
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def assemble_one(index: int, page: PlannedWikiPage) -> WikiPageCreate:
            async with semaphore:
                if progress_callback:
                    await progress_callback(
                        "calling_llm",
                        f"正在组装第 {index + 1}/{len(plan.pages)} 个 Wiki 页面...",
                    )
                data = await self.llm.generate_structured(
                    prompt=self._build_assemble_prompt(plan, page, index_context),
                    system_prompt=PAGE_ASSEMBLY_SYSTEM_PROMPT,
                    response_format=PAGE_ASSEMBLY_RESPONSE_SCHEMA,
                )
                return self._parse_assembled_page(data, page, plan.source_slug)

        return await asyncio.gather(*[
            assemble_one(index, page) for index, page in enumerate(plan.pages)
        ])

    def _source_archive(self, plan: CompilePlan) -> SourceArchive:
        titles = [page.title for page in plan.pages]
        return SourceArchive(
            slug=plan.source_slug,
            title=plan.source_title,
            summary=f"Plan-first compilation identified {len(plan.pages)} wiki pages.",
            key_takeaways=titles[:5],
            extracted_concepts=[page.slug for page in plan.pages],
        )

    def _build_summary(
        self,
        *,
        plan: CompilePlan,
        scans: list[LocalScanResult],
        total_chunks: int,
        budget: CompileBudgetPolicy,
    ) -> CompilePlanSummary:
        evidence_refs = [
            ref
            for page in plan.pages
            for ref in page.evidence_refs
        ]
        block_ids = {
            block_id
            for ref in evidence_refs
            for block_id in ref.block_ids
        }
        return CompilePlanSummary(
            mode="plan_first",
            total_chunks=total_chunks,
            scanned_chunks=len(scans),
            candidate_pages=sum(len(scan.candidates) for scan in scans),
            planned_pages=len(plan.pages),
            evidence_refs=len(evidence_refs),
            evidence_blocks=len(block_ids),
            page_slugs=[page.slug for page in plan.pages],
            budget={
                "max_scan_chunks": budget.max_scan_chunks,
                "max_pages": budget.max_pages,
                "max_evidence_per_page": budget.max_evidence_per_page,
                "max_evidence_quote_chars": budget.max_evidence_quote_chars,
            },
        )

    def _build_scan_prompt(
        self,
        *,
        source_slug: str,
        source_title: str,
        chunk_index: int,
        total_chunks: int,
        chunk_text: str,
    ) -> str:
        return f"""Scan this source chunk and identify candidate wiki pages.

Do NOT write final Wiki pages. Only return compact candidates with evidence.

Source: {source_title} (slug: {source_slug})
Chunk: {chunk_index + 1}/{total_chunks}

{chunk_text}

Return candidates for categories:
- concept: ideas, frameworks, methods, terms
- entity: people, organizations, products, papers, tools
- relationship: evidence-backed links between concepts/entities
- analysis: synthesized comparisons or high-level interpretations

The chunk may contain markers like `<!-- page=2 -->` and
`<!-- block=p2-b3 kind=paragraph -->`. Include both `source_pages` and
`evidence_block_ids` whenever available.

Prefer candidates that have explicit evidence in this chunk."""

    def _build_assemble_prompt(
        self,
        plan: CompilePlan,
        page: PlannedWikiPage,
        index_context: str,
    ) -> str:
        evidence = "\n\n".join(
            f"- chunk {ref.chunk_index + 1}, pages {ref.source_pages or 'unknown'}, blocks {ref.block_ids or 'unknown'}: {ref.quote}"
            for ref in page.evidence_refs
        )
        return f"""Assemble one SageMate wiki page from the selected evidence.

Source: {plan.source_title} (slug: {plan.source_slug})
Page slug: {page.slug}
Page title: {page.title}
Category: {page.category.value}
Reason selected: {page.reason}

Evidence snippets:
{evidence}

Current Wiki Index:
{index_context}

Write a stable, self-contained Markdown page. Use headings and [[wikilinks]] where useful.
Do not invent facts beyond the evidence snippets."""

    def _parse_scan_result(
        self,
        data: dict,
        chunk_index: int,
        total_chunks: int,
    ) -> LocalScanResult:
        candidates: list[KnowledgeCandidate] = []
        for raw in data.get("candidates", []):
            title = str(raw.get("title") or raw.get("name") or "").strip()
            if not title:
                continue
            slug = str(raw.get("slug") or SlugGenerator.generate(title)).strip()
            category = self._coerce_category(raw.get("category"))
            source_pages = self._coerce_pages(raw.get("source_pages", []))
            block_ids = self._coerce_block_ids(raw.get("evidence_block_ids", []))
            quotes = raw.get("evidence_quotes") or raw.get("evidence") or []
            if isinstance(quotes, str):
                quotes = [quotes]
            evidence_refs = []
            for quote in quotes:
                trimmed_quote = self._budget().trim_quote(quote)
                if not trimmed_quote:
                    continue
                evidence_refs.append(EvidenceRef(
                    chunk_index=chunk_index,
                    quote=trimmed_quote,
                    source_pages=source_pages,
                    block_ids=block_ids,
                ))
            candidates.append(KnowledgeCandidate(
                slug=slug,
                title=title,
                category=category,
                summary=str(raw.get("summary") or raw.get("reason") or ""),
                aliases=[str(a) for a in raw.get("aliases", []) if str(a).strip()],
                evidence_refs=evidence_refs,
            ))
        return LocalScanResult(
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            candidates=candidates,
        )

    def _parse_assembled_page(
        self,
        data: dict,
        planned: PlannedWikiPage,
        source_slug: str,
    ) -> WikiPageCreate:
        raw = data.get("page") or data
        content = raw.get("content") or self._fallback_content(planned)
        return WikiPageCreate(
            slug=raw.get("slug") or planned.slug,
            title=raw.get("title") or planned.title,
            category=self._coerce_category(raw.get("category") or planned.category.value),
            content=content,
            source_pages=self._coerce_pages(raw.get("source_pages") or planned.source_pages),
            tags=[str(tag) for tag in raw.get("tags", [])],
            sources=[source_slug],
            outbound_links=[str(link) for link in raw.get("outbound_links", [])],
        )

    @staticmethod
    def _coerce_category(value: object) -> WikiCategory:
        try:
            category = WikiCategory(str(value))
        except Exception:
            return WikiCategory.CONCEPT
        return category if category in PLANNABLE_CATEGORIES else WikiCategory.CONCEPT

    @staticmethod
    def _coerce_pages(value: object) -> list[int]:
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            value = re.findall(r"\d+", value)
        if not isinstance(value, list):
            return []
        pages: list[int] = []
        for item in value:
            try:
                pages.append(int(item))
            except (TypeError, ValueError):
                continue
        return list(dict.fromkeys(pages))

    @staticmethod
    def _coerce_block_ids(value: object) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        block_ids = [
            str(item).strip()
            for item in value
            if re.match(r"^p\d+-b\d+$", str(item).strip())
        ]
        return list(dict.fromkeys(block_ids))

    @staticmethod
    def _fallback_content(planned: PlannedWikiPage) -> str:
        evidence = "\n".join(f"- {ref.quote}" for ref in planned.evidence_refs if ref.quote)
        return f"{planned.reason}\n\n## Evidence\n\n{evidence}".strip()


LOCAL_SCAN_SYSTEM_PROMPT = (
    "You are a knowledge compiler. Your job is only to discover candidate "
    "wiki pages and cite evidence snippets. Do not write final articles."
)

LOCAL_SCAN_RESPONSE_SCHEMA = {
    "name": "local_scan_result",
    "schema": {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string"},
                        "title": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": ["entity", "concept", "relationship", "analysis"],
                        },
                        "summary": {"type": "string"},
                        "aliases": {"type": "array", "items": {"type": "string"}},
                        "source_pages": {"type": "array", "items": {"type": "integer"}},
                        "evidence_block_ids": {"type": "array", "items": {"type": "string"}},
                        "evidence_quotes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "category", "summary", "evidence_quotes"],
                },
            }
        },
        "required": ["candidates"],
    },
}

PAGE_ASSEMBLY_SYSTEM_PROMPT = (
    "You assemble stable SageMate wiki pages from provided evidence. "
    "Preserve source traceability and avoid unsupported claims."
)

PAGE_ASSEMBLY_RESPONSE_SCHEMA = {
    "name": "planned_page",
    "schema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["entity", "concept", "relationship", "analysis"],
                    },
                    "content": {"type": "string"},
                    "source_pages": {"type": "array", "items": {"type": "integer"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "outbound_links": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["slug", "title", "category", "content", "source_pages"],
            }
        },
        "required": ["page"],
    },
}
