"""Table extraction strategies for trafilatura output improvement.

Design: Strategy Pattern
- TableExtractor: abstract base
- TrafilaturaTableExtractor: delegate to trafilatura directly
- HybridTableExtractor: custom BeautifulSoup-based table handling
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

import trafilatura

from .models import URLResult

logger = logging.getLogger(__name__)


class TableExtractor(ABC):
    """Abstract strategy for extracting markdown from HTML with table support."""

    @abstractmethod
    def extract(self, html: str, url: str) -> URLResult:
        """
        Extract markdown content from HTML.

        Returns:
            URLResult with extracted content (success=True) or error (success=False).
        """
        ...


class TrafilaturaTableExtractor(TableExtractor):
    """
    Default strategy: let trafilatura handle tables natively.
    Simple, fast, but trafilatura's table→markdown output can be broken
    for complex tables (columns split across lines).
    """

    def extract(self, html: str, url: str) -> URLResult:
        md = trafilatura.extract(
            html,
            include_tables=True,
            include_comments=False,
            output_format="markdown",
        )

        if not md or len(md.strip()) < 50:
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error="Content extraction failed or too short",
            )

        metadata = trafilatura.metadata.extract_metadata(html)
        title = ""
        if metadata:
            title = getattr(metadata, "title", None) or metadata.get("title", "")

        clean_content = re.sub(r"\n\s*\n", "\n\n", md).strip()

        return URLResult(
            url=url,
            title=title or md.split("\n")[0][:50],
            content=clean_content,
            success=True,
            metadata=metadata,
        )


class HybridTableExtractor(TableExtractor):
    """
    Custom strategy: extract tables as clean HTML separately and embed them
    at their correct positions in the markdown content.

    Workaround for trafilatura's broken table→markdown output.
    """

    def extract(self, html: str, url: str) -> URLResult:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")

            # Collect and clean tables
            tables_info = []
            for table in soup.find_all("table"):
                for caption in table.find_all("caption"):
                    caption.decompose()
                for link in table.find_all("a"):
                    link.unwrap()
                for cell in table.find_all(["th", "td"]):
                    if "class" in cell.attrs:
                        del cell.attrs["class"]
                    for p in cell.find_all("p"):
                        p.unwrap()

                # Find unique code-like term for position matching
                all_text = table.get_text()
                code_terms = re.findall(
                    r"[A-Z][a-zA-Z]+(?:[A-Z][a-zA-Z]*)*", all_text
                )
                code_terms = [t for t in code_terms if len(t) > 8]
                unique_term = code_terms[0] if code_terms else None

                tables_info.append({
                    "html": str(table),
                    "unique_term": unique_term,
                })
                table.decompose()

            # Extract markdown without tables
            md = trafilatura.extract(
                str(soup),
                include_tables=False,
                include_comments=False,
                output_format="markdown",
            )
            if not md:
                md = ""

            # Insert tables at their positions
            for table_info in tables_info:
                term = table_info["unique_term"]
                if term and term in md:
                    pos = md.find(term)
                    next_para = md.find("\n\n", pos)
                    if next_para == -1:
                        next_para = len(md)
                    md = (
                        md[:next_para]
                        + "\n\n"
                        + table_info["html"]
                        + "\n\n"
                        + md[next_para:]
                    )
                else:
                    # Fallback: append at end
                    md += "\n\n" + table_info["html"] + "\n\n"

        except Exception:
            # Fallback: standard trafilatura with tables
            md = trafilatura.extract(
                html,
                include_tables=True,
                include_comments=False,
                output_format="markdown",
            )

        if not md or len(md.strip()) < 50:
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error="Content extraction failed or too short",
            )

        metadata = trafilatura.metadata.extract_metadata(html)
        title = ""
        if metadata:
            title = getattr(metadata, "title", None) or metadata.get("title", "")

        clean_content = re.sub(r"\n\s*\n", "\n\n", md).strip()

        return URLResult(
            url=url,
            title=title or md.split("\n")[0][:50],
            content=clean_content,
            success=True,
            metadata=metadata,
        )
