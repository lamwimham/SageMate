"""
Ingest Adapter Base Types.

Defines the contract for input adapters that convert raw sources
(PDF, DOCX, HTML, URL, etc.) into normalized markdown content.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ParseResult:
    """Result of parsing a raw file into normalized markdown."""

    slug: str
    title: str
    content: str          # Full markdown with frontmatter
    source_type: str      # "pdf", "markdown", "docx", "html", "text"
    metadata: dict = None # Optional extra info (page count, url, etc.)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
