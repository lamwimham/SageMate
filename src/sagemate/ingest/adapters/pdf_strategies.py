"""
PDF Parsing Strategies — Strategy Pattern.

Provides pluggable PDF text extraction strategies. The factory selects
the best available strategy based on runtime configuration.

Extending:
    1. Subclass PDFParseStrategy
    2. Implement _extract_text()
    3. Register in PDFParserFactory.create()
"""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from ...core.config import Settings
from ...core.slug import SlugGenerator

logger = logging.getLogger(__name__)


class PDFParseError(Exception):
    """Raised when PDF text extraction fails completely."""
    pass


class PDFParseStrategy(ABC):
    """Abstract strategy for PDF text extraction.

    Concrete strategies only need to implement _extract_text().
    Frontmatter, slug generation, and error wrapping are handled here.
    """

    async def parse(self, file_path: Path, settings: Settings) -> tuple[str, str]:
        """
        Parse a PDF file into (slug, markdown_with_frontmatter).

        Post-processes extracted text to normalize LaTeX formulas
        (Unicode superscripts/subscripts, Greek letters, etc.).

        Raises:
            PDFParseError: if text extraction fails.
        """
        from .formula_postprocessor import FormulaPostProcessor

        title = self._extract_title(file_path)
        slug = SlugGenerator.generate(title, prefix="raw")

        text = await self._extract_text(file_path, settings)
        if not text or not text.strip():
            raise PDFParseError(
                f"{self.__class__.__name__} returned empty content for {file_path.name}"
            )

        # Normalize LaTeX formulas extracted from PDF
        text = FormulaPostProcessor.process(text)

        frontmatter = (
            f"---\n"
            f"title: '{title}'\n"
            f"slug: {slug}\n"
            f"source: '{file_path.name}'\n"
            f"source_type: 'pdf'\n"
            f"---\n\n"
        )
        return slug, frontmatter + text.strip()

    @abstractmethod
    async def _extract_text(self, file_path: Path, settings: Settings) -> str:
        """Extract raw text/markdown from the PDF. Implement in subclass."""
        ...

    @staticmethod
    def _extract_title(file_path: Path) -> str:
        return file_path.stem.replace("-", " ").replace("_", " ").title()


class GLMOCRPDFStrategy(PDFParseStrategy):
    """PDF parsing via Zhipu GLM-OCR API (best quality, requires network)."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def _extract_text(self, file_path: Path, _settings: Settings) -> str:
        from ...ingest.adapters.glm_ocr import GLMOCRClient

        client = GLMOCRClient(api_key=self.api_key, base_url=self.base_url)
        try:
            return await client.parse_pdf_file(file_path)
        except Exception as exc:
            raise PDFParseError(f"GLM-OCR failed for {file_path.name}: {exc}") from exc


class PopplerPDFStrategy(PDFParseStrategy):
    """PDF parsing via local Poppler pdftotext (no API key, requires binary)."""

    TIMEOUT = 60  # seconds

    async def _extract_text(self, file_path: Path, _settings: Settings) -> str:
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(file_path), "-"],
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )
        except FileNotFoundError:
            raise PDFParseError(
                "pdftotext not found. Install Poppler: brew install poppler"
            )
        except subprocess.TimeoutExpired:
            raise PDFParseError(
                f"PDF extraction timed out after {self.TIMEOUT}s"
            )
        except Exception as exc:
            raise PDFParseError(f"pdftotext subprocess failed: {exc}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "(no stderr)"
            raise PDFParseError(
                f"pdftotext exited with code {result.returncode}: {stderr}"
            )

        text = result.stdout
        if not text.strip():
            raise PDFParseError(
                "pdftotext returned empty content (scanned PDF without text layer?)"
            )

        return text


class PDFParserFactory:
    """Factory: select the best available PDF parse strategy."""

    @staticmethod
    def create(settings: Settings) -> PDFParseStrategy:
        """
        Selection priority:
        1. GLM-OCR if Zhipu/BigModel key is configured via vision_* settings.
        2. GLM-OCR if Zhipu/BigModel key is configured via legacy llm_* settings.
        3. Poppler (pdftotext) as local fallback.
        """
        # Prefer dedicated vision/OCR config if available
        if settings.vision_api_key and "bigmodel" in (settings.vision_base_url or "").lower():
            logger.info("PDFParserFactory → GLMOCRPDFStrategy (vision config)")
            return GLMOCRPDFStrategy(
                api_key=settings.vision_api_key,
                base_url=settings.vision_base_url,
            )

        # Backward-compat: legacy llm config pointing at bigmodel
        if settings.llm_api_key and "bigmodel" in (settings.llm_base_url or "").lower():
            logger.info("PDFParserFactory → GLMOCRPDFStrategy (llm config)")
            return GLMOCRPDFStrategy(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )

        logger.info("PDFParserFactory → PopplerPDFStrategy")
        return PopplerPDFStrategy()
