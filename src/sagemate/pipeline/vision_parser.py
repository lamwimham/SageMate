"""
Vision-Backed PDF Parser (v0.9) - GLM-OCR via Base64 Image Slicing.

Architecture:
1. Local: PDF -> Images (using Poppler).
2. API: Send images one by one to GLM-OCR layout_parsing endpoint.
3. Cost: Extremely low (~0.2 RMB/M Tokens). High accuracy for tables/formulas.

This avoids the expensive 'files/parser' managed service while keeping the 
precision of the dedicated OCR model.
"""

from __future__ import annotations

import base64
import httpx
import io
from pathlib import Path
from typing import Optional

from pdf2image import convert_from_path
from PIL import Image

from ..core.config import settings


class VisionParser:
    """
    Parses PDFs using Zhipu GLM-OCR with local image slicing.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or settings.vision_base_url).rstrip("/")
        self.api_key = api_key or settings.vision_api_key
        
        if not self.api_key:
            raise RuntimeError("No API key provided for VisionParser. Set SAGEMATE_VISION_API_KEY.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

    async def parse_pdf(self, file_path: Path) -> tuple[str, str]:
        """
        Main entry point.
        1. Convert PDF pages to images.
        2. Send each image to GLM-OCR.
        3. Aggregate Markdown results.
        """
        print(f"[VisionParser] Slicing {file_path.name} for GLM-OCR...")
        
        # 1. Get page count without loading all images
        from pdf2image.pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(str(file_path))
        total_pages = info["Pages"]
        
        print(f"[VisionParser] Found {total_pages} pages. Starting stream parsing...")

        full_markdown = ""
        
        # 2. Process page by page (Streaming to save RAM)
        for i in range(1, total_pages + 1):
            print(f"[VisionParser] Processing page {i}/{total_pages}...")
            
            # Load single page
            try:
                # 150 DPI is the sweet spot for OCR: clear text, low token cost
                images = convert_from_path(
                    str(file_path), 
                    dpi=150, 
                    first_page=i, 
                    last_page=i
                )
                image = images[0]
            except Exception as e:
                print(f"[VisionParser] Failed to slice page {i}: {e}")
                continue

            # Convert to Base64
            img_byte_arr = io.BytesIO()
            # Compress to JPEG to save bandwidth/tokens
            image.save(img_byte_arr, format='JPEG', quality=90)
            img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
            
            # Release memory
            del images
            del image

            # Send to GLM-OCR
            # We use layout_parsing for best Markdown quality
            page_md = await self._call_ocr(img_base64, i)
            
            # ⚠️ Inject Page Anchor for Data Lineage
            # This marker helps the LLM Compiler know which page this text came from
            page_md_with_anchor = f"<!-- page={i} -->\n\n{page_md}"
            
            full_markdown += page_md_with_anchor + "\n\n---\n\n"

        print(f"[VisionParser] Completed. Total Markdown length: {len(full_markdown)}")

        title = file_path.stem.replace('-', ' ').title()
        slug = f"raw-{file_path.stem.lower().replace(' ', '-')}"
        
        frontmatter = f"""---
title: '{title}'
slug: {slug}
source: '{file_path.name}'
source_type: 'pdf_glm_ocr_sliced'
---

"""
        return slug, frontmatter + full_markdown

    async def _call_ocr(self, img_base64: str, page_num: int) -> str:
        """Call GLM-OCR layout_parsing with Base64 image."""
        url = f"{self.base_url}/layout_parsing"
        
        # GLM-OCR layout_parsing accepts a file URL or base64 data URI.
        # We use the data URI scheme to send local image data as a string.
        payload = {
            "model": "glm-ocr",
            "file": f"data:image/jpeg;base64,{img_base64}"
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    url, 
                    headers={**self.headers, "Content-Type": "application/json"},
                    json=payload
                )
                
                if response.status_code != 200:
                    print(f"[VisionParser] API Error on page {page_num}: {response.status_code} - {response.text[:200]}")
                    return f"[OCR Error on page {page_num}]"
                
                result = response.json()
                md_results = result.get("md_results", "")
                
                if not md_results:
                    return f"[OCR Empty Result on page {page_num}]"
                    
                return md_results

            except Exception as e:
                print(f"[VisionParser] Exception on page {page_num}: {e}")
                return f"[OCR Exception on page {page_num}]"
