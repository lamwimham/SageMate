"""
Source Archive Rendering Strategies.

The Source Archive is the "hub page" for each ingested document.
Different renderers control how the source content and LLM-generated
metadata are combined into the final markdown file.

Design: Strategy Pattern
- SourceArchiveRenderer (ABC): defines the rendering contract
- FullContentRenderer:   preserves full source text in body, metadata in frontmatter
- SummaryRenderer:       (legacy) LLM-generated summary as body

Usage:
    renderer = FullContentRenderer()
    md = renderer.render(archive=source_archive, source_content=raw_text)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import SourceArchive


class SourceArchiveRenderer(ABC):
    """
    Strategy interface for rendering a source archive markdown page.

    A source archive page serves as the canonical hub for an ingested
    document. Renderers decide how to balance between:
    - Preserving original content (fidelity)
    - Presenting LLM-generated metadata (discoverability)
    """

    @abstractmethod
    def render(self, archive: SourceArchive, source_content: str) -> str:
        """
        Render the full markdown content for the source archive page.

        Args:
            archive: LLM-generated metadata (summary, takeaways, concepts).
            source_content: The original parsed text from the source document.

        Returns:
            Complete markdown string (including frontmatter) to write to disk.
        """
        ...


class FullContentRenderer(SourceArchiveRenderer):
    """
    Renders a source archive that preserves the full original content
    in the body, with LLM-generated metadata stored in YAML frontmatter.

    Philosophy: "The file is the truth". The original text is never lost;
    LLM annotations are machine-readable metadata, not a replacement.
    """

    # Fields that go into frontmatter (machine-readable, stable schema)
    SUMMARY_KEY: str = "sagemate_summary"
    TAKEAWAYS_KEY: str = "sagemate_key_takeaways"
    CONCEPTS_KEY: str = "sagemate_extracted_concepts"

    def render(self, archive: SourceArchive, source_content: str) -> str:
        frontmatter = self._build_frontmatter(archive)
        cleaned = self._clean_content(source_content)
        return frontmatter + cleaned

    def _clean_content(self, content: str) -> str:
        """Clean source content before archiving.

        Removes:
        - Empty list items ("- ", "* ", "+ ", "1. " with no content)
        - Excessive blank lines (3+ newlines → 2)
        - Trailing whitespace on each line
        """
        lines = content.split('\n')
        cleaned_lines = []
        prev_was_empty_list = False

        for line in lines:
            stripped = line.rstrip()
            # Detect empty list items: bullet or numbered, no actual content
            is_empty_list = bool(
                stripped and
                len(stripped) <= 4 and
                (
                    stripped in ('-', '*', '+') or
                    stripped.endswith(('-', '*', '+')) or
                    stripped in ('-', '*', '+', '- ', '* ', '+ ') or
                    (len(stripped) >= 2 and stripped[0].isdigit() and stripped[1:] == '. ')
                )
            )

            if is_empty_list:
                if not prev_was_empty_list:
                    prev_was_empty_list = True
                continue  # drop this line entirely

            prev_was_empty_list = False
            cleaned_lines.append(stripped)

        result = '\n'.join(cleaned_lines)
        # Collapse 3+ consecutive newlines to double newline
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()

    def _build_frontmatter(self, archive: SourceArchive) -> str:
        takeaways_yaml = "\n".join(
            f'  - "{self._escape_yaml(t)}"' for t in archive.key_takeaways
        )
        concepts_yaml = "\n".join(
            f'  - "[[{slug}]]"' for slug in archive.extracted_concepts
        )

        return f"""---
title: '{self._escape_yaml(archive.title)}'
slug: {archive.slug}
category: source
{self.SUMMARY_KEY}: "{self._escape_yaml(archive.summary)}"
{self.TAKEAWAYS_KEY}:
{takeaways_yaml}
{self.CONCEPTS_KEY}:
{concepts_yaml}
---

"""

    @staticmethod
    def _escape_yaml(value: str) -> str:
        """Escape quotes in inline YAML string values."""
        return value.replace('"', '\\"').replace("'", "\\'")


# NOTE: SummaryRenderer was removed. FullContentRenderer is the only active renderer.
# If you need a summary-only view, create a new renderer that strips the body.
