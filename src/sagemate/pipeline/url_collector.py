"""URL Collector Module - Tiered Scraping Strategy with Optimizations.

Features:
- Tier 1.5: curl_cffi (Chrome impersonation) + trafilatura (fast, low cost)
- Tier 2: Playwright (Headless Browser) for JS-heavy or strict WAF sites
- BrowserPool: Playwright instance reuse for performance
- TTLCache: URL result caching to avoid duplicate requests
- SiteHandler: Plugin pattern for site-specific extraction (WeChat, etc.)
- Batch collection: Concurrent URL collection with semaphore
- Retry mechanism: Tenacity retry with exponential backoff
- Proxy support: Optional proxy configuration
"""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Optional

import trafilatura
from curl_cffi import AsyncSession
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from urllib.parse import urlparse

from ..core.config import url_collector_settings, URLCollectorSettings

logger = logging.getLogger(__name__)


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class URLResult:
    url: str
    title: str
    content: str
    success: bool
    error: str = ""
    metadata: dict = field(default_factory=dict)
    extraction_tier: str = ""  # "tier1" or "tier2"
    site_handler: str = ""  # "wechat", "generic", etc.
    cached: bool = False
    collected_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CacheEntry:
    url: str
    result: URLResult
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


# ── URL Validator ─────────────────────────────────────────────────────────────


class URLValidator:
    """URL validation with strict regex patterns."""

    STRICT_URL_PATTERN = re.compile(
        r"^https?://"
        r"(?:"
        r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r")"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)?$",
        re.IGNORECASE,
    )

    @staticmethod
    def validate(text: str) -> bool:
        """Validate if text is a valid URL."""
        if not text:
            return False

        text = text.strip()

        # Basic regex match
        if not URLValidator.STRICT_URL_PATTERN.match(text):
            return False

        # Further validation with urlparse
        try:
            parsed = urlparse(text)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def normalize(url: str) -> str:
        """Normalize URL (strip whitespace)."""
        return url.strip()


# ── TTL Cache ─────────────────────────────────────────────────────────────────


class TTLCache:
    """
    Thread-safe TTL cache with LRU eviction.

    Features:
    - TTL expiration
    - Max entries limit (LRU eviction)
    - Async-safe with lock
    """

    def __init__(self, settings: Optional[URLCollectorSettings] = None):
        self._settings = settings or url_collector_settings
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, url: str) -> Optional[URLResult]:
        """Get cached result, returns None if not found or expired."""
        url = URLValidator.normalize(url)

        async with self._lock:
            entry = self._cache.get(url)

            if entry is None:
                return None

            if entry.is_expired:
                del self._cache[url]
                return None

            # Move to end (LRU refresh)
            self._cache.move_to_end(url)
            entry.hit_count += 1

            # Mark as cached
            result = entry.result
            result.cached = True
            return result

    async def set(self, url: str, result: URLResult) -> None:
        """Set cache entry, evict oldest if over limit."""
        url = URLValidator.normalize(url)

        async with self._lock:
            # Calculate expiration
            expires_at = datetime.now() + timedelta(
                seconds=self._settings.cache_ttl_seconds
            )

            entry = CacheEntry(
                url=url,
                result=result,
                created_at=datetime.now(),
                expires_at=expires_at,
            )

            # Remove old entry if exists
            if url in self._cache:
                del self._cache[url]

            # Add new entry
            self._cache[url] = entry

            # Evict oldest if over limit
            while len(self._cache) > self._settings.cache_max_entries:
                self._cache.popitem(last=False)

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> int:
        """Remove expired entries, return count of removed."""
        async with self._lock:
            expired_keys = [
                k for k, v in self._cache.items() if v.is_expired
            ]
            for k in expired_keys:
                del self._cache[k]
            return len(expired_keys)

    @property
    def size(self) -> int:
        """Current cache size."""
        return len(self._cache)


# ── Browser Pool ──────────────────────────────────────────────────────────────


@dataclass
class BrowserInstance:
    """Single browser instance wrapper."""
    browser: Browser
    context: BrowserContext
    created_at: datetime
    last_used: datetime = field(default_factory=datetime.now)
    usage_count: int = 0


class BrowserPool:
    """
    Playwright browser instance pool for reuse.

    Features:
    - Lazy initialization
    - Instance reuse (reduces startup overhead from 2-3s to ~0.1s)
    - Auto recycling based on max age
    - Proxy support
    """

    def __init__(self, settings: Optional[URLCollectorSettings] = None):
        self._settings = settings or url_collector_settings
        self._pool: list[BrowserInstance] = []
        self._playwright: Optional[Playwright] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Playwright and create initial browser instances."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            self._playwright = await async_playwright().start()

            # Create initial browser instances
            for _ in range(1):  # Start with 1 instance, scale as needed
                instance = await self._create_instance()
                self._pool.append(instance)

            self._initialized = True
            logger.info(f"[BrowserPool] Initialized with {len(self._pool)} instances")

    async def _create_instance(self) -> BrowserInstance:
        """Create a new browser instance."""
        launch_args = [
            "--disable-blink-features=AutomationControlled",
        ]

        browser = await self._playwright.chromium.launch(
            headless=True,
            args=launch_args,
        )

        # Create context with proxy if enabled
        context_options: dict[str, Any] = {
            "user_agent": self._settings.user_agent,
            "viewport": {"width": 1280, "height": 800},
        }

        if self._settings.proxy_enabled and self._settings.proxy_url:
            context_options["proxy"] = {"server": self._settings.proxy_url}

        context = await browser.new_context(**context_options)

        # Inject stealth script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """)

        return BrowserInstance(
            browser=browser,
            context=context,
            created_at=datetime.now(),
        )

    async def acquire(self) -> BrowserInstance:
        """Acquire a browser instance from pool."""
        await self.initialize()

        async with self._lock:
            # Check for expired instances
            max_age = timedelta(minutes=self._settings.browser_pool_max_age_minutes)
            now = datetime.now()

            for instance in self._pool:
                if now - instance.created_at > max_age:
                    # Recycle old instance
                    await self._recycle_instance(instance)
                    new_instance = await self._create_instance()
                    self._pool[self._pool.index(instance)] = new_instance
                    return new_instance

            # Find least used instance
            instance = min(self._pool, key=lambda x: x.usage_count)
            instance.usage_count += 1
            instance.last_used = now
            return instance

    async def _recycle_instance(self, instance: BrowserInstance) -> None:
        """Close and remove an instance."""
        try:
            await instance.context.close()
            await instance.browser.close()
        except Exception as e:
            logger.warning(f"[BrowserPool] Error recycling instance: {e}")

    async def release(self, instance: BrowserInstance) -> None:
        """Release instance back to pool (no action needed, it stays in pool)."""
        # Instance stays in pool for reuse
        pass

    async def close(self) -> None:
        """Close all browser instances and Playwright."""
        async with self._lock:
            for instance in self._pool:
                await self._recycle_instance(instance)

            self._pool.clear()

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            self._initialized = False
            logger.info("[BrowserPool] Closed")

    @asynccontextmanager
    async def get_page(self, url: str) -> AsyncGenerator[Page, None]:
        """Convenience method: get a page, auto-release."""
        instance = await self.acquire()

        # Create new page in existing context
        page = await instance.context.new_page()

        try:
            yield page
        finally:
            await page.close()
            await self.release(instance)


# ── Site Handlers ─────────────────────────────────────────────────────────────


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

        # Try trafilatura
        html = await page.content()
        return self._extract_with_trafilatura(html, url)

    @staticmethod
    def _extract_with_trafilatura(html: str, url: str) -> URLResult:
        """
        Extract content using trafilatura with hybrid table handling.

        trafilatura's markdown output for HTML tables is broken (columns split
        across lines). This method extracts tables as clean HTML separately and
        embeds them at their correct positions in the markdown content.
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")

            # Collect and clean tables
            tables_info = []
            for table in soup.find_all("table"):
                for caption in table.find_all("caption"):
                    caption.decompose()
                for link in table.find_all("a"):
                    link.unwrap()
                for cell in table.find_all(["th", "td"]):
                    if "class" in cell.attrs:
                        del cell.attrs["class"]
                    for p in cell.find_all("p"):
                        p.unwrap()

                # Find unique code-like term for position matching
                all_text = table.get_text()
                code_terms = re.findall(
                    r"[A-Z][a-zA-Z]+(?:[A-Z][a-zA-Z]*)*", all_text
                )
                code_terms = [t for t in code_terms if len(t) > 8]
                unique_term = code_terms[0] if code_terms else None

                tables_info.append({
                    "html": str(table),
                    "unique_term": unique_term,
                })
                table.decompose()

            # Extract markdown without tables
            md = trafilatura.extract(
                str(soup),
                include_tables=False,
                include_comments=False,
                output_format="markdown",
            )
            if not md:
                md = ""

            # Insert tables at their positions
            for table_info in tables_info:
                term = table_info["unique_term"]
                if term and term in md:
                    pos = md.find(term)
                    next_para = md.find("\n\n", pos)
                    if next_para == -1:
                        next_para = len(md)
                    md = (
                        md[:next_para]
                        + "\n\n"
                        + table_info["html"]
                        + "\n\n"
                        + md[next_para:]
                    )
                else:
                    # Fallback: append at end
                    md += "\n\n" + table_info["html"] + "\n\n"

        except Exception:
            # Fallback: standard trafilatura with tables
            md = trafilatura.extract(
                html,
                include_tables=True,
                include_comments=False,
                output_format="markdown",
            )

        if not md or len(md.strip()) < 50:
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error="Content extraction failed or too short",
            )

        # Get metadata
        metadata = trafilatura.metadata.extract_metadata(html)
        title = ""
        if metadata:
            title = getattr(metadata, "title", None) or metadata.get("title", "")

        clean_content = re.sub(r"\n\s*\n", "\n\n", md).strip()

        return URLResult(
            url=url,
            title=title or md.split("\n")[0][:50],
            content=clean_content,
            success=True,
            metadata=metadata,
        )


class SiteHandlerRegistry:
    """Registry for site handlers."""

    _handlers: list[SiteHandler] = []

    @classmethod
    def register(cls, handler: SiteHandler) -> None:
        cls._handlers.append(handler)

    @classmethod
    def get_handler(cls, url: str) -> SiteHandler:
        """Get handler for URL, returns first matching handler."""
        for handler in cls._handlers:
            if handler.can_handle(url):
                return handler
        return GenericHandler()  # Fallback

    @classmethod
    def register_defaults(cls) -> None:
        """Register default handlers."""
        cls._handlers.clear()
        cls.register(WeChatHandler())
        cls.register(GenericHandler())


# Auto-register defaults
SiteHandlerRegistry.register_defaults()


# ── URL Collector ─────────────────────────────────────────────────────────────


class URLCollector:
    """
    URL content collector with tiered scraping strategy.

    Features:
    - Tier 1.5 (curl_cffi + trafilatura): Fast, low cost
    - Tier 2 (Playwright): JS rendering, WAF bypass
    - Cache: TTL caching for duplicate URLs
    - Retry: Automatic retry with exponential backoff
    - Batch: Concurrent collection with semaphore
    """

    # Shared instances (lazy initialization)
    _browser_pool: Optional[BrowserPool] = None
    _cache: Optional[TTLCache] = None
    _semaphore: Optional[asyncio.Semaphore] = None
    _settings: Optional[URLCollectorSettings] = None

    @classmethod
    def _get_settings(cls) -> URLCollectorSettings:
        if cls._settings is None:
            cls._settings = url_collector_settings
        return cls._settings

    @classmethod
    def _get_cache(cls) -> TTLCache:
        if cls._cache is None:
            cls._cache = TTLCache(cls._get_settings())
        return cls._cache

    @classmethod
    def _get_browser_pool(cls) -> BrowserPool:
        if cls._browser_pool is None:
            cls._browser_pool = BrowserPool(cls._get_settings())
        return cls._browser_pool

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(cls._get_settings().max_concurrent_requests)
        return cls._semaphore

    @staticmethod
    def is_url(text: str) -> bool:
        """Check if text is a valid URL (static method for compatibility)."""
        return URLValidator.validate(text)

    @classmethod
    @retry(
        stop=stop_after_attempt(url_collector_settings.retry_max_attempts),
        wait=wait_exponential(
            min=url_collector_settings.retry_min_wait_seconds,
            max=url_collector_settings.retry_max_wait_seconds,
        ),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def collect(cls, url: str, timeout: Optional[int] = None) -> URLResult:
        """
        Collect content from a single URL.

        Flow:
        1. Validate URL
        2. Check cache
        3. Try Tier 1.5 (curl_cffi + trafilatura)
        4. Fallback to Tier 2 (Playwright)
        5. Update cache

        Args:
            url: URL to collect
            timeout: Optional timeout override (seconds)

        Returns:
            URLResult with extracted content
        """
        settings = cls._get_settings()
        effective_timeout = timeout or settings.tier1_timeout

        # Validate URL
        url = URLValidator.normalize(url)
        if not URLValidator.validate(url):
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error="Invalid URL format",
            )

        # Check cache
        cache = cls._get_cache()
        if settings.cache_enabled:
            cached = await cache.get(url)
            if cached:
                logger.info(f"[URLCollector] Cache hit for {url}")
                return cached

        # Tier 1.5: curl_cffi + trafilatura
        logger.info(f"[URLCollector] Tier 1.5 attempt: {url}")
        result = await cls._tier1_fetch(url, effective_timeout)

        if result.success and len(result.content) >= settings.min_content_length:
            result.extraction_tier = "tier1"
            await cache.set(url, result)
            return result

        # Tier 2: Playwright
        logger.info(
            f"[URLCollector] Tier 1 failed ({result.error}), "
            f"falling back to Tier 2: {url}"
        )
        result = await cls._tier2_fetch(url)

        result.extraction_tier = "tier2"
        await cache.set(url, result)
        return result

    @classmethod
    async def _tier1_fetch(cls, url: str, timeout: int) -> URLResult:
        """Tier 1.5: Fast fetch with curl_cffi."""
        settings = cls._get_settings()

        try:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            # WeChat needs Referer
            if "mp.weixin.qq.com" in url:
                headers["Referer"] = "https://mp.weixin.qq.com"

            proxy = None
            if settings.proxy_enabled and settings.proxy_url:
                proxy = settings.proxy_url

            async with AsyncSession(
                impersonate="chrome110",
                timeout=timeout,
                trust_env=True,
                proxy=proxy,
            ) as session:
                resp = await session.get(url, headers=headers)

                if resp.status_code != 200:
                    return URLResult(
                        url=url,
                        title="",
                        content="",
                        success=False,
                        error=f"HTTP Error: {resp.status_code}",
                    )

                return GenericHandler._extract_with_trafilatura(resp.text, url)

        except Exception as e:
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error=str(e),
            )

    @classmethod
    async def _tier2_fetch(cls, url: str) -> URLResult:
        """Tier 2: Playwright browser fetch."""
        settings = cls._get_settings()
        pool = cls._get_browser_pool()
        handler = SiteHandlerRegistry.get_handler(url)

        try:
            async with pool.get_page(url) as page:
                # Prepare context
                await handler.prepare_context(page.context, url)

                # Navigate
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=settings.tier2_timeout * 1000,
                )

                # Wait for network idle
                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=settings.tier2_network_idle_timeout * 1000,
                    )
                except Exception:
                    pass  # Continue even if networkidle fails

                # Extract with handler
                result = await handler.extract(page, url, settings)
                result.site_handler = handler.name
                return result

        except Exception as e:
            logger.error(f"[URLCollector] Tier 2 failed: {e}")
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error=f"Tier 2 failed: {str(e)}",
            )

    @classmethod
    async def collect_batch(
        cls,
        urls: list[str],
        fail_fast: bool = False,
    ) -> list[URLResult]:
        """
        Collect multiple URLs concurrently.

        Args:
            urls: List of URLs to collect
            fail_fast: If True, stop on first error

        Returns:
            List of URLResults (order matches input)
        """
        semaphore = cls._get_semaphore()

        async def collect_with_semaphore(url: str) -> URLResult:
            async with semaphore:
                return await cls.collect(url)

        tasks = [collect_with_semaphore(url) for url in urls]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=not fail_fast,
        )

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    URLResult(
                        url=urls[i],
                        title="",
                        content="",
                        success=False,
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    @classmethod
    async def close(cls) -> None:
        """Close shared resources (browser pool, etc.)."""
        if cls._browser_pool:
            await cls._browser_pool.close()
            cls._browser_pool = None

        if cls._cache:
            await cls._cache.clear()
            cls._cache = None