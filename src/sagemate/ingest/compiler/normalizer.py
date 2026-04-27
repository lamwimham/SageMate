"""
Compile result normalization.

LLM strategies are allowed to vary in how they extract knowledge, but the
canonical source identity and page bookkeeping must remain deterministic.
This module is the seam that keeps prompt/chunk artifacts out of persisted
wiki pages and prepares the compiler for future CompilePlan/Evidence stages.
"""

from __future__ import annotations

from ...models import CompileResult, SourceArchive, WikiCategory, WikiPageCreate


class CompileResultNormalizer:
    """Normalize compiler output before any file or DB write happens."""

    def normalize(
        self,
        result: CompileResult,
        *,
        source_slug: str,
        source_title: str,
    ) -> CompileResult:
        normalized = result.model_copy(deep=True)
        normalized.new_pages = self._dedupe_pages(normalized.new_pages, source_slug)
        normalized.source_archive = self._canonical_archive(
            archive=normalized.source_archive,
            source_slug=source_slug,
            source_title=source_title,
            pages=normalized.new_pages,
        )
        return normalized

    def _dedupe_pages(
        self,
        pages: list[WikiPageCreate],
        source_slug: str,
    ) -> list[WikiPageCreate]:
        seen: set[str] = set()
        deduped: list[WikiPageCreate] = []
        for page in pages:
            if page.category == WikiCategory.SOURCE:
                continue
            if page.slug in seen:
                continue
            seen.add(page.slug)
            if source_slug not in page.sources:
                page.sources = [*page.sources, source_slug]
            page.source_pages = list(dict.fromkeys(page.source_pages))
            page.outbound_links = list(dict.fromkeys(page.outbound_links))
            page.tags = list(dict.fromkeys(page.tags))
            deduped.append(page)
        return deduped

    def _canonical_archive(
        self,
        *,
        archive: SourceArchive | None,
        source_slug: str,
        source_title: str,
        pages: list[WikiPageCreate],
    ) -> SourceArchive:
        page_slugs = [p.slug for p in pages]
        if archive is None:
            return SourceArchive(
                slug=source_slug,
                title=source_title,
                summary="Compiled source archive.",
                key_takeaways=[],
                extracted_concepts=page_slugs,
            )

        archive.slug = source_slug
        archive.title = source_title
        archive.extracted_concepts = list(dict.fromkeys(
            [*archive.extracted_concepts, *page_slugs]
        ))
        return archive
