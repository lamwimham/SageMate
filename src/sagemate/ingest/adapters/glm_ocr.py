"""GLM-OCR Client — Zhipu native document parsing API.

Endpoint: POST /layout_parsing
Model: glm-ocr
Supports: PDF, JPG, PNG (url or base64)
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class GLMOCRClient:
    """Wrapper for Zhipu GLM-OCR API (non-OpenAI-compatible endpoint)."""

    def __init__(self, api_key: str, base_url: str = "https://open.bigmodel.cn/api/paas/v4"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    async def parse_pdf(self, pdf_bytes: bytes) -> str:
        """Parse PDF bytes → Markdown via glm-ocr."""
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        return await self._call_layout_parsing(
            file=f"data:application/pdf;base64,{b64}"
        )

    async def parse_pdf_file(self, file_path: Path) -> str:
        """Parse a PDF file → Markdown via glm-ocr."""
        return await self.parse_pdf(file_path.read_bytes())

    async def parse_image(self, image_bytes: bytes, mime: str = "image/png") -> str:
        """Parse image bytes → Markdown via glm-ocr."""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return await self._call_layout_parsing(
            file=f"data:{mime};base64,{b64}"
        )

    async def _call_layout_parsing(self, file: str) -> str:
        """Call the layout_parsing endpoint and extract markdown text."""
        url = f"{self.base_url}/layout_parsing"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "glm-ocr",
            "file": file,
        }

        logger.info(f"📝 Calling GLM-OCR: {url}")

        resp = await self._client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Defensive: try multiple possible response shapes
        text = (
            data.get("content")
            or data.get("text")
            or data.get("result")
            or data.get("data", {}).get("content")
            or ""
        )

        if not text:
            logger.warning(f"GLM-OCR returned empty text. Raw: {data}")

        logger.info(f"✅ GLM-OCR success: {len(text)} chars")
        return text
