"""URL content collector with tiered scraping strategy."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import trafilatura
from curl_cffi import AsyncSession

from ....core.config import url_collector_settings, URLCollectorSettings
from .models import URLResult
from .cache import TTLCache
from .browser_pool import BrowserPool
from .handlers import SiteHandlerRegistry
from .table_extractor import HybridTableExtractor
from .validator import URLValidator

logger = logging.getLogger(__name__)


class URLCollector:
    """
    URL content collector with tiered scraping strategy.

    Features:
    - Tier 1.5 (curl_cffi + trafilatura): Fast, low cost
    - Tier 2 (Playwright + stealth): JS rendering, WAF bypass
    - Anti-bot detection & classification
    - Retry with strategy rotation
    - Cache: TTL caching for duplicate URLs
    - Batch: Concurrent collection with semaphore
    """

    def __init__(
        self,
        settings: URLCollectorSettings,
        cache: TTLCache,
        browser_pool: BrowserPool,
        handler_registry: SiteHandlerRegistry,
        semaphore: asyncio.Semaphore,
    ):
        self._settings = settings
        self._cache = cache
        self._browser_pool = browser_pool
        self._handler_registry = handler_registry
        self._semaphore = semaphore

    @staticmethod
    def is_url(text: str) -> bool:
        """Check if text is a valid URL (static method for compatibility)."""
        return URLValidator.validate(text)

    async def collect(self, url: str, timeout: Optional[int] = None) -> URLResult:
        """
        Collect content from a single URL.

        Flow:
        1. Validate URL
        2. Check cache
        3. Try Tier 1.5 (curl_cffi + trafilatura)
        4. Fallback to Tier 2 (Playwright + stealth)
        5. Update cache
        """
        settings = self._settings
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
        if settings.cache_enabled:
            cached = await self._cache.get(url)
            if cached:
                logger.info(f"[URLCollector] Cache hit for {url}")
                return cached

        # Tier 1.5: curl_cffi + trafilatura
        logger.info(f"[URLCollector] Tier 1.5 attempt: {url}")
        result = await self._tier1_fetch(url, effective_timeout)

        if result.success and len(result.content) >= settings.min_content_length:
            result.extraction_tier = "tier1"
            await self._cache.set(url, result)
            return result

        # Tier 2: Playwright + stealth
        logger.info(
            f"[URLCollector] Tier 1 failed ({result.error}), "
            f"falling back to Tier 2: {url}"
        )
        result = await self._tier2_fetch(url)

        result.extraction_tier = "tier2"
        await self._cache.set(url, result)
        return result

    async def _tier1_fetch(self, url: str, timeout: int) -> URLResult:
        """Tier 1.5: Fast fetch with curl_cffi."""
        settings = self._settings

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

                extractor = HybridTableExtractor()
                return extractor.extract(resp.text, url)

        except Exception as e:
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error=str(e),
            )

    async def _tier2_fetch(self, url: str) -> URLResult:
        """Tier 2: Playwright browser fetch with anti-detection."""
        settings = self._settings
        pool = self._browser_pool
        handler = self._handler_registry.get_handler(url)

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

    async def collect_batch(
        self,
        urls: list[str],
        fail_fast: bool = False,
    ) -> list[URLResult]:
        """
        Collect multiple URLs concurrently.

        Args:
            urls: List of URLs to collect
            fail_fast: If True, raises the first exception after returning all results

        Returns:
            List of URLResults (order matches input)
        """
        semaphore = self._semaphore

        async def collect_with_semaphore(url: str) -> URLResult:
            async with semaphore:
                return await self.collect(url)

        tasks = [collect_with_semaphore(url) for url in urls]

        # Always collect all results; fail_fast controls whether we raise afterward
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results: list[URLResult] = []
        first_error: Optional[Exception] = None
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
                if first_error is None:
                    first_error = result
            else:
                processed_results.append(result)

        if fail_fast and first_error is not None:
            raise first_error

        return processed_results

    async def close(self) -> None:
        """Close all resources (browser pool, cache, semaphore)."""
        await self._browser_pool.close()
        await self._cache.clear()
        self._semaphore = None


class URLCollectorFactory:
    """Factory for creating URLCollector instances with injected dependencies."""

    @staticmethod
    def create(
        settings: Optional[URLCollectorSettings] = None,
    ) -> URLCollector:
        """Create a URLCollector with all dependencies injected."""
        effective_settings = settings or url_collector_settings
        cache = TTLCache(effective_settings)
        browser_pool = BrowserPool(effective_settings)
        handler_registry = SiteHandlerRegistry()
        semaphore = asyncio.Semaphore(effective_settings.max_concurrent_requests)
        return URLCollector(
            settings=effective_settings,
            cache=cache,
            browser_pool=browser_pool,
            handler_registry=handler_registry,
            semaphore=semaphore,
        )


# Module-level default instance (lazy-loaded for backward compatibility)
_default_collector: Optional[URLCollector] = None


def get_default_collector() -> URLCollector:
    """Get the module-level default URLCollector instance."""
    global _default_collector
    if _default_collector is None:
        _default_collector = URLCollectorFactory.create()
    return _default_collector
