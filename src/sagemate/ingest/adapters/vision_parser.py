"""Vision / Image OCR Module.

Provides two capabilities:
1. VisionClassifier — determines whether an image is a document screenshot,
   chart, or casual photo (Strategy: classify first, act second).
2. VisionParser — extracts text from document images via OCR.
"""

import logging
from pathlib import Path
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class VisionClassifier:
    """
    Uses a Vision LLM to classify the semantic type of an image.

    This prevents "noisy photo descriptions" from being ingested as wiki
    content. We only OCR images that are likely to contain meaningful text.
    """

    CLASSIFY_PROMPT = (
        "请判断这张图片的类型。只输出以下类别之一，不要解释，不要多余文字：\n"
        "- document: 包含大量可读文字的文档、文章截图、PDF扫描件、代码截图、书本页面\n"
        "- chart: 图表、数据可视化、流程图、思维导图、表格截图\n"
        "- photo: 照片、风景、人物、动物、食物、表情包、无文字的纯图像\n"
        "- other: 无法明确归类\n"
        "\n"
        "输出格式：仅一个单词，如 'document'"
    )

    def __init__(self, api_key: str, base_url: str, model: str = "glm-4v-plus"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def classify(self, image_bytes: bytes) -> str:
        """
        Classify image type.

        Returns one of: "document", "chart", "photo", "other".
        """
        try:
            import base64
            b64_image = base64.b64encode(image_bytes).decode("utf-8")

            logger.info("🖼️  Calling Vision LLM for image classification...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                            },
                            {"type": "text", "text": self.CLASSIFY_PROMPT},
                        ],
                    }
                ],
                temperature=0.0,
                max_tokens=10,
            )

            raw = response.choices[0].message.content.strip().lower()
            # Normalize possible variations
            if "document" in raw:
                result = "document"
            elif "chart" in raw or "diagram" in raw or "table" in raw:
                result = "chart"
            elif "photo" in raw or "image" in raw or "picture" in raw:
                result = "photo"
            else:
                result = "other"

            logger.info(f"🖼️  Image classified as: {result}")
            return result

        except Exception as e:
            logger.error(f"❌ Vision classification failed: {e}")
            # Fail-safe: treat as photo so we don't accidentally ingest garbage
            return "photo"


class VisionParser:
    """
    Extracts text from document images via Vision LLM OCR.

    This should ONLY be called after VisionClassifier has identified the
    image as a 'document' or 'chart'. Calling it on casual photos will
    produce meaningless noise.
    """

    OCR_PROMPT = (
        "请提取这张图片中的所有文字内容。\n"
        "- 如果是文档/文章截图：逐字提取所有可见文字，保持原有段落格式。\n"
        "- 如果是图表/表格：用文字描述其结构和关键数据。\n"
        "- 如果图片中几乎没有文字：只回复 '__NO_TEXT__'。\n"
        "请直接输出提取的内容，不要包含多余的寒暄。"
    )

    def __init__(self, api_key: str, base_url: str, model: str = "glm-4v-plus"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def parse_image(
        self,
        image_bytes: bytes,
        file_id: str,
        raw_dir: Path | None = None,
        save_raw: bool = True,
    ) -> str:
        """
        Process image bytes and return extracted text.

        Args:
            image_bytes: Raw image data.
            file_id: Unique identifier for the filename.
            raw_dir: Directory to save the original image (if save_raw=True).
            save_raw: Whether to persist the original image to disk.
                      Set to False if the caller has already saved it.

        Returns:
            Extracted text or an error marker.
        """
        # 1. Optionally save original image
        if save_raw and raw_dir is not None:
            image_dir = raw_dir / "images"
            image_dir.mkdir(parents=True, exist_ok=True)
            image_path = image_dir / f"{file_id}.png"
            image_path.write_bytes(image_bytes)
            logger.info(f"📸 Saved original image to: {image_path}")

        # 2. Call Vision LLM for OCR
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
                                },
                            },
                            {"type": "text", "text": self.OCR_PROMPT},
                        ],
                    }
                ],
                temperature=0.1,
            )

            text = response.choices[0].message.content.strip()
            logger.info(f"✅ Vision OCR successful: {text[:50]}...")
            return text

        except Exception as e:
            logger.error(f"❌ Vision LLM OCR failed: {e}")
            return f"[Image OCR Error: {e}]"
