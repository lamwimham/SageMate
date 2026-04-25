"""Site-specific extraction handlers (Strategy Pattern)."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

import trafilatura
from playwright.async_api import BrowserContext, Page

from ....core.config import URLCollectorSettings
from .models import URLResult
from .table_extractor import HybridTableExtractor, TableExtractor

logger = logging.getLogger(__name__)

# Anti-bot / verification page keywords (Chinese & English)
ANTI_BOT_KEYWORDS = [
    "环境异常",
    "完成验证",
    "去验证",
    "请在微信客户端打开",
    "访问频繁",
    "操作过于频繁",
    "验证",
    "安全验证",
    "点击验证",
    "滑动验证",
    "captcha",
    "robot",
    "automated",
    "blocked",
    "access denied",
    "forbidden",
    "unusual traffic",
]


def _is_anti_bot_page(content: str) -> bool:
    """Check if the page content indicates anti-bot interception."""
    lower = content.lower()
    return any(kw.lower() in lower for kw in ANTI_BOT_KEYWORDS)


class SiteHandler(ABC):
    """
    Abstract base class for site-specific extraction handlers.

    Responsible for:
    - URL pattern matching
    - Context preparation (headers, cookies)
    - Content extraction
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Handler name for logging and metadata."""
        pass

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this handler can handle the URL."""
        pass

    @abstractmethod
    async def prepare_context(self, context: BrowserContext, url: str) -> None:
        """Prepare browser context (set headers, cookies, etc.)."""
        pass

    @abstractmethod
    async def extract(
        self,
        page: Page,
        url: str,
        settings: URLCollectorSettings,
    ) -> URLResult:
        """Extract content from the page."""
        pass


class WeChatHandler(SiteHandler):
    """Handler for WeChat public account articles (mp.weixin.qq.com)."""

    name = "wechat"

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return "mp.weixin.qq.com" in url

    async def prepare_context(self, context: BrowserContext, url: str) -> None:
        """Set WeChat-specific headers."""
        await context.set_extra_http_headers({
            "Referer": "https://mp.weixin.qq.com",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        })

    async def _attempt_direct_extract(
        self, page: Page, url: str, settings: URLCollectorSettings
    ) -> URLResult | None:
        """Attempt 1: WeChat-specific selectors."""
        try:
            await page.wait_for_selector(
                "#js_content",
                timeout=settings.tier2_wait_selector_timeout * 1000,
            )
            await page.wait_for_timeout(2000)  # Wait for images

            title_el = await page.query_selector("#activity-name")
            title = ""
            if title_el:
                title = (await title_el.inner_text()).strip()

            content_el = await page.query_selector("#js_content")
            if not content_el:
                return None

            content_html = await content_el.inner_html()
            extracted = trafilatura.extract(
                content_html,
                include_comments=False,
                output_format="markdown",
            )
            content = extracted if extracted else await content_el.inner_text()

            if len(content) < 50:
                return None

            return URLResult(
                url=url,
                title=title,
                content=content,
                success=True,
                metadata={"extraction_method": "wechat_direct"},
            )
        except Exception as e:
            logger.warning(f"[WeChatHandler] Direct extraction failed: {e}")
            return None

    async def _attempt_generic_extract(
        self, page: Page, url: str
    ) -> URLResult | None:
        """Attempt 2: Generic full-page extraction."""
        try:
            html = await page.content()

            # Anti-bot check before extraction
            if _is_anti_bot_page(html):
                logger.warning("[WeChatHandler] Anti-bot page detected in fallback")
                return URLResult(
                    url=url,
                    title="",
                    content="",
                    success=False,
                    error="BLOCKED_BY_WAF: WeChat anti-bot verification page detected",
                )

            extracted = trafilatura.extract(
                html,
                include_comments=False,
                output_format="markdown",
            )
            if extracted and len(extracted) >= 50:
                # Try to grab title
                title_el = await page.query_selector("#activity-name, h1, h2, .rich_media_title")
                title = ""
                if title_el:
                    title = (await title_el.inner_text()).strip()
                return URLResult(
                    url=url,
                    title=title,
                    content=extracted,
                    success=True,
                    metadata={"extraction_method": "wechat_fallback"},
                )
        except Exception as e:
            logger.warning(f"[WeChatHandler] Fallback extraction failed: {e}")
        return None

    async def _attempt_scroll_extract(
        self, page: Page, url: str
    ) -> URLResult | None:
        """Attempt 3: Scroll down to trigger lazy loading, then extract."""
        try:
            # Simulate human scrolling
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await page.wait_for_timeout(800)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3 * 2)")
            await page.wait_for_timeout(800)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1200)

            html = await page.content()
            if _is_anti_bot_page(html):
                return None

            extracted = trafilatura.extract(
                html,
                include_comments=False,
                output_format="markdown",
            )
            if extracted and len(extracted) >= 50:
                title_el = await page.query_selector("#activity-name, h1, h2, .rich_media_title")
                title = ""
                if title_el:
                    title = (await title_el.inner_text()).strip()
                return URLResult(
                    url=url,
                    title=title,
                    content=extracted,
                    success=True,
                    metadata={"extraction_method": "wechat_scroll"},
                )
        except Exception as e:
            logger.warning(f"[WeChatHandler] Scroll extraction failed: {e}")
        return None

    async def extract(
        self,
        page: Page,
        url: str,
        settings: URLCollectorSettings,
    ) -> URLResult:
        """
        Extract WeChat article with multi-attempt strategy.

        Attempt order:
        1. WeChat-specific selectors (#js_content)
        2. Generic full-page extraction (anti-bot check)
        3. Scroll-triggered lazy loading extraction
        """
        # ── Attempt 1: Direct selectors ─────────────────────────
        result = await self._attempt_direct_extract(page, url, settings)
        if result is not None and result.success:
            return result

        # ── Attempt 2: Generic fallback ─────────────────────────
        logger.info("[WeChatHandler] Falling back to generic extraction")
        result = await self._attempt_generic_extract(page, url)
        if result is not None and result.success:
            return result
        if result is not None and not result.success:
            # Anti-bot detected — don't waste time on scroll attempt
            return result

        # ── Attempt 3: Scroll trigger ───────────────────────────
        logger.info("[WeChatHandler] Falling back to scroll extraction")
        result = await self._attempt_scroll_extract(page, url)
        if result is not None and result.success:
            return result

        # ── All attempts failed ─────────────────────────────────
        return URLResult(
            url=url,
            title="",
            content="",
            success=False,
            error="WeChat content extraction failed (direct + fallback + scroll)",
        )


class GenericHandler(SiteHandler):
    """Generic handler for most websites."""

    name = "generic"

    def __init__(self, table_extractor: TableExtractor | None = None):
        self._table_extractor = table_extractor or HybridTableExtractor()

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return True  # Fallback for all URLs

    async def prepare_context(self, context: BrowserContext, url: str) -> None:
        """No special preparation needed."""
        pass

    async def extract(
        self,
        page: Page,
        url: str,
        settings: URLCollectorSettings,
    ) -> URLResult:
        """Generic extraction: scroll, wait, trafilatura."""
        # Scroll to load lazy content
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass
        await page.wait_for_timeout(settings.tier2_network_idle_timeout * 1000)

        # Anti-bot check
        html = await page.content()
        if _is_anti_bot_page(html):
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error="BLOCKED_BY_WAF: Anti-bot verification page detected",
            )

        # Try trafilatura via strategy
        return self._table_extractor.extract(html, url)


class SiteHandlerRegistry:
    """Registry for site handlers (instance-level, not global)."""

    def __init__(self):
        self._handlers: list[SiteHandler] = []
        self.register_defaults()

    def register(self, handler: SiteHandler) -> None:
        self._handlers.append(handler)

    def get_handler(self, url: str) -> SiteHandler:
        """Get handler for URL, returns first matching handler."""
        for handler in self._handlers:
            if handler.can_handle(url):
                return handler
        return GenericHandler()  # Fallback

    def register_defaults(self) -> None:
        """Register default handlers."""
        self._handlers.clear()
        self.register(WeChatHandler())
        self.register(GenericHandler())
