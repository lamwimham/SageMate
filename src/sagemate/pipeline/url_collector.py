"""URL Collector Module - Tiered Scraping Strategy.

Tier 1.5: `curl_cffi` (Chrome impersonation) + `trafilatura`.
Tier 2:   `playwright` (Headless Browser) for JS-heavy or strict WAF sites.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import trafilatura
from curl_cffi import AsyncSession
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


@dataclass
class URLResult:
    url: str
    title: str
    content: str
    success: bool
    error: str = ""
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class URLCollector:
    """
    Collects content from URLs using a tiered strategy.
    """

    URL_PATTERN = re.compile(r'https?://[^\s/$.?#].[^\s]*')

    @staticmethod
    def is_url(text: str) -> bool:
        return bool(URLCollector.URL_PATTERN.search(text))

    @classmethod
    async def collect(cls, url: str, timeout: int = 30) -> URLResult:
        """
        Main entry point. Tries Tier 1.5, then falls back to Tier 2.
        """
        # 1. Try Tier 1.5 (Fast, Low Cost)
        logger.info(f"[URLCollector] Attempting Tier 1.5: curl_cffi for {url}")
        result = await cls._tier_1_cffi(url, timeout)
        
        if result.success and len(result.content) > 100:
            return result

        # 2. Fallback to Tier 2 (Headless Browser)
        logger.info(f"[URLCollector] Tier 1 failed/incomplete ({result.error}), falling back to Tier 2: Playwright for {url}")
        try:
            result = await cls._tier_2_playwright(url, timeout)
            return result
        except Exception as e:
            logger.error(f"[URLCollector] Tier 2 failed: {e}")
            return URLResult(
                url=url, title="", content="", success=False, 
                error=f"All scraping tiers failed. Last error: {str(e)}"
            )

    @classmethod
    async def _tier_1_cffi(cls, url: str, timeout: int) -> URLResult:
        try:
            # WeChat articles need a Referer
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            if "mp.weixin.qq.com" in url:
                headers["Referer"] = "https://mp.weixin.qq.com"

            async with AsyncSession(impersonate="chrome110", timeout=timeout, trust_env=True) as session:
                resp = await session.get(url, headers=headers)
                
                if resp.status_code != 200:
                    return URLResult(url=url, title="", content="", success=False, error=f"HTTP Error: {resp.status_code}")

                return cls._extract_with_trafilatura(resp.text, url)
        except Exception as e:
            return URLResult(url=url, title="", content="", success=False, error=str(e))

    @classmethod
    async def _tier_2_playwright(cls, url: str, timeout: int) -> URLResult:
        """Uses Playwright Headless Browser to render JS and bypass WAFs."""
        is_wechat = "mp.weixin.qq.com" in url
        
        async with async_playwright() as p:
            # Launch with stealth args
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            
            # Inject stealth script to hide automation
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
            """)

            # Inject Referer for WeChat
            if is_wechat:
                await context.set_extra_http_headers({"Referer": "https://mp.weixin.qq.com"})
            
            page = await context.new_page()
            
            try:
                # 1. Navigate
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                
                # 2. Wait for network idle
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                # 3. Special handling for WeChat Articles
                if is_wechat:
                    try:
                        # Wait for the main content container
                        await page.wait_for_selector('#js_content', timeout=5000)
                        # Wait a bit more for images/lazy content
                        await page.wait_for_timeout(2000)
                        
                        # Extract title and content directly from specific selectors
                        title_el = await page.query_selector('#activity-name')
                        title = (await title_el.inner_text()).strip() if title_el else "Unknown Title"
                        
                        content_el = await page.query_selector('#js_content')
                        if content_el:
                            content_html = await content_el.inner_html()
                            # Try trafilatura on the inner HTML for markdown formatting
                            extracted = trafilatura.extract(content_html, include_comments=False, output_format="markdown")
                            content = extracted if extracted else await content_el.inner_text()
                        else:
                            content = ""
                        
                        if not content or len(content) < 50:
                            return URLResult(url=url, title=title, content="", success=False, error="WeChat content empty or blocked")
                            
                        return URLResult(
                            url=url, title=title, content=content, success=True,
                            metadata={"extraction_method": "wechat_direct"}
                        )
                    except Exception as e:
                        logger.warning(f"[URLCollector] WeChat specific extraction failed: {e}")
                        # Fallback to generic logic if specific extraction fails

                # 4. Generic handling (Scroll & Extract)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(3000) 

                html = await page.content()
                result = cls._extract_with_trafilatura(html, url)
                
                # If trafilatura failed, fallback to raw text
                if not result.success:
                    raw_text = await page.inner_text("body")
                    clean_text = re.sub(r'\n\s*\n', '\n\n', raw_text)
                    page_title = await page.title()
                    
                    return URLResult(
                        url=url,
                        title=page_title,
                        content=clean_text[:5000],
                        success=True,
                        metadata={"extraction_method": "playwright_raw_text"}
                    )
                
                return result
            finally:
                await browser.close()

    @staticmethod
    def _extract_with_trafilatura(html: str, url: str) -> URLResult:
        """Common extraction logic using trafilatura."""
        extracted = trafilatura.extract(
            html, 
            include_comments=False, 
            include_tables=True,
            output_format="markdown"
        )

        if not extracted or len(extracted.strip()) < 50:
            return URLResult(
                url=url, title="", content="", success=False,
                error="Content extraction failed or too short (empty page)"
            )

        metadata = trafilatura.metadata.extract_metadata(html)
        if metadata:
            title = getattr(metadata, 'title', None) or metadata.get('title', '')
        else:
            title = ''
            
        clean_content = re.sub(r'\n\s*\n', '\n\n', extracted).strip()

        return URLResult(
            url=url,
            title=title or extracted.split('\n')[0][:50],
            content=clean_content,
            success=True,
            metadata=metadata
        )
