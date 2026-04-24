"""
Migration Script: Translate existing Wiki pages to Chinese.
"""
import asyncio
import logging
import sys
import os
import re
from pathlib import Path
from openai import AsyncOpenAI

# Add src to path to import SageMate modules
sys.path.insert(0, 'src')
from sagemate.core.store import Store
from sagemate.core.config import settings
from sagemate.models import WikiPage, WikiCategory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MigrateTranslate")

# LLM Client setup
# Use the configured DashScope/Qwen settings
api_key = os.getenv("SAGEMATE_LLM_API_KEY") or os.getenv("SAGEMATE_VISION_API_KEY")
base_url = os.getenv("SAGEMATE_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
model_name = os.getenv("SAGEMATE_LLM_MODEL", "qwen-plus")

if not api_key:
    logger.error("❌ Missing SAGEMATE_LLM_API_KEY. Please set it in .env")
    sys.exit(1)

client = AsyncOpenAI(api_key=api_key, base_url=base_url)

# Regex to split Frontmatter and Content
FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)', re.DOTALL)

# Simple heuristic: if text contains > 20% CJK chars, consider it Chinese
def is_chinese(text: str, threshold: float = 0.2) -> bool:
    # Remove code blocks to avoid false positives
    clean_text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    clean_text = re.sub(r'`[^`]+`', '', clean_text)
    
    total_chars = len(clean_text)
    if total_chars < 50:
        return True # Short files might be ambiguous, skip or treat as translated
        
    # Count CJK characters
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff]', clean_text))
    ratio = cjk_chars / total_chars
    return ratio > threshold

async def translate_content(content: str, slug: str) -> str:
    """Send content to LLM for translation."""
    prompt = f"""
    请将以下 Markdown 文档翻译为简体中文。
    
    **重要规则**：
    1. 保留 Markdown 格式（标题、列表、代码块、粗体等）。
    2. 不要翻译代码块内部的内容。
    3. 严格保留 Wiki 链接格式：`[[slug]]` 或 `[[slug|显示文本]]`。如果是 `[[slug]]` 这种形式，**不要翻译 slug 部分**。
    4. 直接输出翻译后的 Markdown，不要包含任何解释或前言后语。
    
    **待翻译内容**：
    {content}
    """
    
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一个专业的知识库翻译助手，擅长技术文档的中文本地化。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error translating {slug}: {e}")
        return content

async def process_file(md_path: Path, store: Store):
    """Process a single markdown file."""
    try:
        text = md_path.read_text(encoding='utf-8')
        
        # Parse Frontmatter
        match = FRONTMATTER_RE.match(text)
        if not match:
            logger.warning(f"Skipping {md_path}: No valid Frontmatter found.")
            return

        frontmatter_str = match.group(1)
        content = match.group(2)

        # Check if already Chinese
        if is_chinese(content):
            logger.info(f"Skipping {md_path.name}: Already Chinese.")
            return

        logger.info(f"🔄 Translating: {md_path.name} ...")
        
        # Translate
        translated_content = await translate_content(content, md_path.stem)
        
        # Reassemble
        new_text = f"---\n{frontmatter_str}\n---\n\n{translated_content}"
        
        # Write back to file
        md_path.write_text(new_text, encoding='utf-8')
        
        # Update Store (FTS index)
        # We need to parse the file again to update the DB
        # To save tokens/time, we can just read the content we just wrote
        # But Store.upsert_page expects a WikiPage object
        
        # Minimal parsing to get metadata
        # Minimal parsing to get metadata
        import yaml
        metadata = yaml.safe_load(frontmatter_str) or {}
        
        slug = metadata.get('slug', md_path.stem)
        title = metadata.get('title', md_path.stem.replace('-', ' ').title())
        category_str = metadata.get('category', 'concept')
        category = WikiCategory(category_str) if category_str in [c.value for c in WikiCategory] else WikiCategory.CONCEPT
        
        tags = metadata.get('tags', [])
        sources = metadata.get('sources', [])
        source_pages = metadata.get('source_pages', [])
        
        page = WikiPage(
            slug=slug,
            title=title,
            category=category,
            file_path=str(md_path),
            tags=tags,
            sources=sources,
            source_pages=source_pages
        )
        
        # We don't need to send full content to upsert_page if the file is already updated?
        # Actually, Store.upsert_page updates the FTS index with the `content` argument.
        # So we must pass the full content.
        # We have `translated_content` ready.
        
        await store.upsert_page(page, translated_content)
        logger.info(f"✅ Translated and Indexed: {md_path.name}")

    except Exception as e:
        logger.error(f"Failed to process {md_path}: {e}")

async def main():
    wiki_dir = settings.wiki_dir
    if not wiki_dir.exists():
        logger.error(f"Wiki directory not found: {wiki_dir}")
        return

    logger.info(f"🚀 Starting migration for Wiki at: {wiki_dir}")
    
    store = Store(settings.db_path)
    await store.connect()

    tasks = []
    
    # Find all .md files in wiki subdirectories
    for md_file in wiki_dir.rglob("*.md"):
        # Skip index and log
        if md_file.name in ["index.md", "log.md"]:
            continue
            
        # Check if it's inside a category directory (not root wiki dir)
        if md_file.parent == wiki_dir:
            continue
            
        tasks.append(process_file(md_file, store))

    # Run concurrently (limit concurrency to avoid API rate limits)
    # Using a simple semaphore or just asyncio.gather with limit
    semaphore = asyncio.Semaphore(3) # 3 concurrent requests
    
    async def bounded_task(task):
        async with semaphore:
            await task
            
    await asyncio.gather(*[bounded_task(t) for t in tasks])
    
    await store.close()
    logger.info("🎉 Migration complete!")

if __name__ == "__main__":
    asyncio.run(main())
