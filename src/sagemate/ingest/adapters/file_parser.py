"""
Deterministic Ingestion Pipeline.
Converts raw files (PDF, Docx, HTML, TXT) to normalized Markdown with frontmatter.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from ...core.config import Settings, settings
from ...core.slug import SlugGenerator

logger = logging.getLogger(__name__)


class DeterministicParser:
    """
    Pure Python file parser. No LLM involved.
    Handles structure extraction, frontmatter normalization, and slug generation.
    """

    @staticmethod
    def generate_slug(title: str, prefix: str = "") -> str:
        """Convert title to a URL-friendly, language-aware slug."""
        return SlugGenerator.generate(title, prefix=prefix)

    @staticmethod
    async def parse_markdown(file_path: Path, target_dir: Path | None = None) -> tuple[str, str]:
        """
        Parse a markdown file, normalize frontmatter.
        Returns (slug, normalized_content).
        Note: target_dir is deprecated and no longer used (writing is caller's responsibility).
        """
        content = file_path.read_text(encoding='utf-8')

        # Extract title from frontmatter or filename
        title = file_path.stem.replace('-', ' ').replace('_', ' ').title()
        frontmatter_meta = {}

        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 2:
                yaml_block = parts[1].strip()
                for line in yaml_block.split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        frontmatter_meta[k.strip()] = v.strip().strip("'\"")
                if 'title' in frontmatter_meta:
                    title = frontmatter_meta['title']
                content = parts[2].lstrip()

        slug = DeterministicParser.generate_slug(title, prefix="raw")

        # Build normalized frontmatter
        frontmatter = f"""---
title: '{title}'
slug: {slug}
source: '{file_path.name}'
source_type: 'markdown'
---

"""
        normalized = frontmatter + content

        return slug, normalized

    @staticmethod
    async def parse_pdf(file_path: Path, target_dir: Path | None = None) -> tuple[str, str]:
        """
        Extract text from PDF via strategy pattern.
        Auto-selects GLM-OCR (Zhipu) if configured, otherwise falls back to Poppler.
        If the primary strategy fails, attempts the alternative as a fallback.
        Note: target_dir is deprecated and no longer used.

        Raises:
            PDFParseError: if all strategies fail.
        """
        from .pdf_strategies import (
            PDFParserFactory,
            PDFParseError,
            GLMOCRPDFStrategy,
            PopplerPDFStrategy,
        )

        primary = PDFParserFactory.create(settings)
        try:
            return await primary.parse(file_path, settings)
        except PDFParseError as exc:
            logger.warning(f"Primary PDF strategy {primary.__class__.__name__} failed: {exc}")

            # Fallback: if primary was Poppler but OCR is configured, try GLM-OCR
            if isinstance(primary, PopplerPDFStrategy):
                if settings.vision_api_key and "bigmodel" in (settings.vision_base_url or "").lower():
                    logger.info("Falling back to GLMOCRPDFStrategy")
                    fallback = GLMOCRPDFStrategy(
                        api_key=settings.vision_api_key,
                        base_url=settings.vision_base_url,
                    )
                    try:
                        return await fallback.parse(file_path, settings)
                    except PDFParseError as exc2:
                        logger.warning(f"Fallback GLM-OCR also failed: {exc2}")
                elif settings.llm_api_key and "bigmodel" in (settings.llm_base_url or "").lower():
                    logger.info("Falling back to GLMOCRPDFStrategy (legacy config)")
                    fallback = GLMOCRPDFStrategy(
                        api_key=settings.llm_api_key,
                        base_url=settings.llm_base_url,
                    )
                    try:
                        return await fallback.parse(file_path, settings)
                    except PDFParseError as exc2:
                        logger.warning(f"Fallback GLM-OCR also failed: {exc2}")

            # Fallback: if primary was GLM-OCR, try Poppler as local fallback
            elif isinstance(primary, GLMOCRPDFStrategy):
                logger.info("Falling back to PopplerPDFStrategy")
                fallback = PopplerPDFStrategy()
                try:
                    return await fallback.parse(file_path, settings)
                except PDFParseError as exc2:
                    logger.warning(f"Fallback Poppler also failed: {exc2}")

            raise

    @staticmethod
    async def parse_docx(file_path: Path, target_dir: Path | None = None) -> tuple[str, str]:
        """Extract text from DOCX using python-docx and return Markdown.
        Note: target_dir is deprecated and no longer used.
        """
        try:
            from docx import Document
        except ImportError:
            raise RuntimeError("python-docx not installed. Run: pip install python-docx")

        doc = Document(str(file_path))
        text = ""
        for para in doc.paragraphs:
            if para.style.name.startswith('Heading'):
                level = min(int(para.style.name.replace('Heading ', '')), 6)
                text += f"{'#' * level} {para.text}\n\n"
            else:
                text += f"{para.text}\n\n"

        title = file_path.stem.replace('-', ' ').replace('_', ' ').title()
        slug = DeterministicParser.generate_slug(title, prefix="raw")

        frontmatter = f"""---
title: '{title}'
slug: {slug}
source: '{file_path.name}'
source_type: 'docx'
---

"""
        final_md = frontmatter + text

        return slug, final_md

    @staticmethod
    async def parse_html(file_path: Path, target_dir: Path | None = None) -> tuple[str, str]:
        """Extract text from HTML using trafilatura and return Markdown.
        Note: target_dir is deprecated and no longer used.
        """
        try:
            import trafilatura
        except ImportError:
            raise RuntimeError("trafilatura not installed. Run: pip install trafilatura")

        html_content = file_path.read_text(encoding='utf-8')
        text = trafilatura.extract(html_content, include_links=True, output_format='markdown') or ""

        title = file_path.stem.replace('-', ' ').replace('_', ' ').title()
        slug = DeterministicParser.generate_slug(title, prefix="raw")

        frontmatter = f"""---
title: '{title}'
slug: {slug}
source: '{file_path.name}'
source_type: 'html'
---

"""
        final_md = frontmatter + text

        return slug, final_md

    @staticmethod
    async def parse(file_path: Path, target_dir: Optional[Path] = None) -> tuple[str, str]:
        """Auto-detect file type and parse accordingly.
        Note: target_dir is deprecated and no longer used.
        """
        ext = file_path.suffix.lower()
        parsers = {
            '.md': DeterministicParser.parse_markdown,
            '.markdown': DeterministicParser.parse_markdown,
            '.pdf': DeterministicParser.parse_pdf,
            '.docx': DeterministicParser.parse_docx,
            '.html': DeterministicParser.parse_html,
            '.htm': DeterministicParser.parse_html,
            '.txt': DeterministicParser.parse_markdown,  # Treat TXT as MD
        }

        parser_fn = parsers.get(ext)
        if parser_fn is None:
            raise ValueError(f"Unsupported file type: {ext}")

        return await parser_fn(file_path, target_dir)
