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
            "Referer": "https://mp.weixin.qq.com"
        })

    async def extract(
        self,
        page: Page,
        url: str,
        settings: URLCollectorSettings,
    ) -> URLResult:
        """Extract WeChat article with special selectors."""
        try:
            # Wait for content container
            await page.wait_for_selector(
                "#js_content",
                timeout=settings.tier2_wait_selector_timeout * 1000,
            )
            await page.wait_for_timeout(2000)  # Wait for images

            # Extract title
            title_el = await page.query_selector("#activity-name")
            title = ""
            if title_el:
                title = (await title_el.inner_text()).strip()

            # Extract content
            content_el = await page.query_selector("#js_content")
            if not content_el:
                return URLResult(
                    url=url,
                    title=title,
                    content="",
                    success=False,
                    error="WeChat content element not found",
                )

            content_html = await content_el.inner_html()
            extracted = trafilatura.extract(
                content_html,
                include_comments=False,
                output_format="markdown",
            )
            content = extracted if extracted else await content_el.inner_text()

            if len(content) < 50:
                return URLResult(
                    url=url,
                    title=title,
                    content="",
                    success=False,
                    error="WeChat content empty or blocked",
                )

            return URLResult(
                url=url,
                title=title,
                content=content,
                success=True,
                metadata={"extraction_method": "wechat_direct"},
            )

        except Exception as e:
            logger.warning(f"[WeChatHandler] Extraction failed: {e}")
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error=str(e),
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
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(settings.tier2_network_idle_timeout * 1000)

        # Try trafilatura via strategy
        html = await page.content()
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
