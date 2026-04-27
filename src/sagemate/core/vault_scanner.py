"""
Obsidian Vault Scanner — indexes all Markdown files into the wiki store.

Features:
- Traverses any Obsidian vault directory
- Parses YAML frontmatter
- Extracts wiki links [[...]] and tags #tag
- Upserts into SQLite FTS5 for AI search
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import WikiCategory, WikiPage

logger = logging.getLogger(__name__)

# Regex patterns
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
TAG_RE = re.compile(r"(?<![a-zA-Z0-9])#([a-zA-Z0-9_\-/\u4e00-\u9fff]+)")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class ScanResult:
    """Result of scanning a vault."""
    total_files: int = 0
    indexed_files: int = 0
    skipped_files: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and return (metadata_dict, body_without_frontmatter)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fm_text = match.group(1)
    body = text[match.end():]
    try:
        # Simple YAML parsing — handles basic key: value structures
        metadata = {}
        for line in fm_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Handle list syntax: [a, b, c]
                if val.startswith("[") and val.endswith("]"):
                    val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
                metadata[key] = val
        return metadata, body
    except Exception:
        return {}, text


def _extract_wikilinks(text: str) -> list[str]:
    """Extract [[slug]] or [[slug|display]] links."""
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]


def _extract_tags(text: str) -> list[str]:
    """Extract #tags, excluding heading anchors like #heading."""
    tags = []
    for m in TAG_RE.finditer(text):
        tag = m.group(1)
        # Skip pure numeric tags (usually heading anchors)
        if tag.isdigit():
            continue
        tags.append(tag)
    return tags


def _slug_from_path(file_path: Path, vault_root: Path) -> str:
    """Generate a unique slug from file path relative to vault root."""
    rel = file_path.relative_to(vault_root)
    # Remove .md extension, replace slashes and spaces
    stem = str(rel.with_suffix(""))
    slug = stem.replace("/", "-").replace("\\", "-").replace(" ", "-").lower()
    # Deduplicate dashes
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled"


def _category_from_frontmatter(meta: dict) -> WikiCategory:
    """Infer category from frontmatter or defaults to NOTE."""
    cat = meta.get("category", "")
    cat_map = {
        "entity": WikiCategory.ENTITY,
        "concept": WikiCategory.CONCEPT,
        "relationship": WikiCategory.RELATIONSHIP,
        "analysis": WikiCategory.ANALYSIS,
        "source": WikiCategory.SOURCE,
        "note": WikiCategory.NOTE,
        "person": WikiCategory.ENTITY,
        "book": WikiCategory.SOURCE,
        "paper": WikiCategory.SOURCE,
        "meeting": WikiCategory.NOTE,
        "project": WikiCategory.NOTE,
        "moc": WikiCategory.CONCEPT,
    }
    return cat_map.get(str(cat).lower().strip(), WikiCategory.NOTE)


class VaultScanner:
    """Scans an Obsidian vault and indexes Markdown files into the wiki store."""

    def __init__(self, store, vault_path: Path | str):
        self.store = store
        self.vault_path = Path(vault_path).expanduser().resolve()
        self._inbound_index: dict[str, set[str]] = {}  # slug -> set of inbound link slugs

    async def scan(self, progress_callback=None) -> ScanResult:
        """
        Scan the vault and index all Markdown files.

        Args:
            progress_callback: Optional async callable(total, current, filename)
        """
        result = ScanResult()
        md_files = list(self.vault_path.rglob("*.md"))
        result.total_files = len(md_files)

        # Skip template and attachment directories
        skip_dirs = {".git", ".obsidian", "09-Templates", "Attachments", "attachments", "99-Archive"}
        md_files = [
            f for f in md_files
            if not any(part in skip_dirs for part in f.relative_to(self.vault_path).parts)
        ]
        result.total_files = len(md_files)

        logger.info(f"[VaultScanner] Found {len(md_files)} markdown files in {self.vault_path}")

        # First pass: extract outbound links and build inbound link index
        pages_data: list[tuple[Path, dict, str, str, str, list[str], list[str]]] = []
        for i, file_path in enumerate(md_files):
            try:
                text = file_path.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(text)
                slug = _slug_from_path(file_path, self.vault_path)
                title = meta.get("title", file_path.stem)
                outbound = _extract_wikilinks(text)
                tags = _extract_tags(text)
                pages_data.append((file_path, meta, title, text, body, outbound, tags))

                # Build inbound link index
                for target in outbound:
                    target_slug = target.lower().replace(" ", "-")
                    self._inbound_index.setdefault(target_slug, set()).add(slug)
            except Exception as e:
                result.errors.append(f"{file_path}: {e}")
                result.skipped_files += 1
                if progress_callback:
                    await progress_callback(len(md_files), i + 1, file_path.name)

        # Second pass: upsert into store
        for i, (file_path, meta, title, text, body, outbound, tags) in enumerate(pages_data):
            slug = _slug_from_path(file_path, self.vault_path)
            inbound = list(self._inbound_index.get(slug, set()))

            page = WikiPage(
                slug=slug,
                title=title,
                category=_category_from_frontmatter(meta),
                file_path=str(file_path),
                outbound_links=outbound,
                inbound_links=inbound,
                tags=tags,
                sources=[],
            )

            try:
                # searchable_content is body without frontmatter for better FTS
                await self.store.upsert_page(page, text, searchable_content=body, commit=False)
                result.indexed_files += 1
            except Exception as e:
                result.errors.append(f"Upsert {file_path}: {e}")
                result.skipped_files += 1

            if progress_callback:
                await progress_callback(len(md_files), i + 1, file_path.name)

        # Commit batch
        db = self.store._db
        if db:
            await db.commit()

        logger.info(
            f"[VaultScanner] Done: {result.indexed_files} indexed, "
            f"{result.skipped_files} skipped, {len(result.errors)} errors"
        )
        return result
