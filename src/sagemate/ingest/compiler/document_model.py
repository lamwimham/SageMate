"""
Document model for evidence-aware compilation.

The compiler works best when source text is not treated as an opaque blob.
This module converts normalized markdown with page markers into stable pages,
blocks, and evidence references. It is intentionally deterministic so later
LLM stages can cite `p3-b2` style block ids without inventing structure.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field


BlockKind = Literal["heading", "paragraph", "table", "code", "formula"]


class DocumentBlock(BaseModel):
    """A stable, citable unit of source content."""

    block_id: str
    page_number: int
    kind: BlockKind
    text: str
    section_path: list[str] = Field(default_factory=list)


class DocumentPage(BaseModel):
    """One source page with its parsed blocks."""

    page_number: int
    blocks: list[DocumentBlock] = Field(default_factory=list)


class EvidenceBlock(BaseModel):
    """A flattened evidence view for planning and future persistence."""

    ref_id: str
    source_slug: str
    page_number: int
    block_id: str
    kind: BlockKind
    text: str
    section_path: list[str] = Field(default_factory=list)


class DocumentModel(BaseModel):
    """A structured representation of a source document."""

    source_slug: str
    source_title: str
    source_type: str = "unknown"
    pages: list[DocumentPage] = Field(default_factory=list)

    @classmethod
    def from_markdown(
        cls,
        *,
        source_slug: str,
        source_title: str,
        source_type: str,
        content: str,
    ) -> "DocumentModel":
        body = _strip_frontmatter(content)
        pages = [
            DocumentPage(page_number=page_number, blocks=_parse_blocks(page_number, page_text))
            for page_number, page_text in _split_pages(body)
        ]
        return cls(
            source_slug=source_slug,
            source_title=source_title,
            source_type=source_type,
            pages=pages,
        )

    @property
    def blocks(self) -> list[DocumentBlock]:
        return [block for page in self.pages for block in page.blocks]

    def evidence_blocks(self) -> list[EvidenceBlock]:
        return [
            EvidenceBlock(
                ref_id=f"{self.source_slug}:{block.block_id}",
                source_slug=self.source_slug,
                page_number=block.page_number,
                block_id=block.block_id,
                kind=block.kind,
                text=block.text,
                section_path=block.section_path,
            )
            for block in self.blocks
        ]

    def to_markdown_chunks(self, max_chars: int) -> list[str]:
        """Render page/block-marked chunks without splitting individual blocks."""
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        current_page: int | None = None

        def flush() -> None:
            nonlocal current, current_len, current_page
            if current:
                chunks.append("\n\n".join(current).strip())
            current = []
            current_len = 0
            current_page = None

        for page in self.pages:
            for block in page.blocks:
                rendered_parts = []
                if current_page != page.page_number:
                    rendered_parts.append(f"<!-- page={page.page_number} -->")
                rendered_parts.append(f"<!-- block={block.block_id} kind={block.kind} -->")
                rendered_parts.append(block.text)
                rendered = "\n".join(rendered_parts)

                if current and current_len + len(rendered) + 2 > max_chars:
                    flush()
                    rendered = "\n".join([
                        f"<!-- page={page.page_number} -->",
                        f"<!-- block={block.block_id} kind={block.kind} -->",
                        block.text,
                    ])

                current.append(rendered)
                current_len += len(rendered) + 2
                current_page = page.page_number

        flush()
        return chunks or [""]


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    end = content.find("---", 3)
    if end == -1:
        return content
    return content[end + 3:].lstrip("\n")


def _split_pages(content: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"<!--\s*page=(\d+)\s*-->", re.IGNORECASE)
    matches = list(pattern.finditer(content))
    if not matches:
        return [(1, content.strip())]

    pages: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        page_text = content[start:end].strip()
        if page_text:
            pages.append((int(match.group(1)), page_text))
    return pages or [(1, content.strip())]


def _parse_blocks(page_number: int, page_text: str) -> list[DocumentBlock]:
    raw_blocks = _split_markdown_blocks(page_text)
    blocks: list[DocumentBlock] = []
    section_path: list[str] = []

    for raw in raw_blocks:
        text = raw.strip()
        if not text:
            continue
        kind = _classify_block(text)
        if kind == "heading":
            heading = re.sub(r"^#{1,6}\s+", "", text.splitlines()[0]).strip()
            section_path = [heading]
        block_id = f"p{page_number}-b{len(blocks) + 1}"
        blocks.append(DocumentBlock(
            block_id=block_id,
            page_number=page_number,
            kind=kind,
            text=text,
            section_path=list(section_path),
        ))
    return blocks


def _split_markdown_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_code = False

    for line in text.splitlines():
        if line.strip().startswith("```"):
            current.append(line)
            in_code = not in_code
            continue
        if not in_code and not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)

    if current:
        blocks.append("\n".join(current))
    return blocks


def _classify_block(text: str) -> BlockKind:
    stripped = text.strip()
    if stripped.startswith("```"):
        return "code"
    if re.match(r"^#{1,6}\s+", stripped):
        return "heading"
    if stripped.startswith("$$") or stripped.endswith("$$"):
        return "formula"
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) >= 2 and all(line.startswith("|") and line.endswith("|") for line in lines[:2]):
        return "table"
    return "paragraph"
