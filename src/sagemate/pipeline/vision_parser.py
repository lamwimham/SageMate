"""Vision / Image OCR Module."""

import logging
import os
from pathlib import Path
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class VisionParser:
    """
    Handles image message ingestion:
    1. Download image data.
    2. Save original image to `data/raw/images/`.
    3. Use Vision LLM (GLM-4V) to extract text and descriptions.
    """

    def __init__(self, api_key: str, base_url: str, model: str = "glm-4v-plus"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def parse_image(self, image_bytes: bytes, file_id: str, raw_dir: Path) -> str:
        """
        Process image bytes and return extracted text/description.
        """
        # 1. Save original image
        image_dir = raw_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"{file_id}.png"
        image_path.write_bytes(image_bytes)
        logger.info(f"📸 Saved original image to: {image_path}")

        # 2. Call Vision LLM
        try:
            import base64
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            
            logger.info(f"👁️ Calling Vision LLM for OCR: {file_id}...")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64_image}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "请提取这张图片中的所有文字内容。如果是图表或照片，请详细描述其内容。请直接输出提取的文本，不要包含多余的寒暄。"
                            }
                        ]
                    }
                ],
                temperature=0.1,
            )
            
            text = response.choices[0].message.content
            logger.info(f"✅ Vision OCR successful: {text[:50]}...")
            return text
            
        except Exception as e:
            logger.error(f"❌ Vision LLM OCR failed: {e}")
            return f"[Image OCR Error: {e}]"
