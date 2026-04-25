"""Playwright browser instance pool for reuse with anti-detection."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright_stealth import Stealth

from ....core.config import url_collector_settings, URLCollectorSettings

logger = logging.getLogger(__name__)


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
    - Anti-detection via playwright-stealth (evades WAF/bot detection)
    """

    def __init__(self, settings: Optional[URLCollectorSettings] = None, max_pool_size: int = 1):
        self._settings = settings or url_collector_settings
        self._max_pool_size = max_pool_size
        self._pool: list[BrowserInstance] = []
        self._playwright: Optional[Playwright] = None
        self._lock = asyncio.Lock()
        self._initialized = False
        self._stealth = Stealth(
            navigator_languages_override=("zh-CN", "zh", "en"),
            navigator_platform_override="MacIntel",
            navigator_user_agent_override=self._settings.user_agent,
            navigator_vendor_override="Google Inc.",
            webgl_vendor_override="Apple Inc.",
            webgl_renderer_override="Apple M1",
            chrome_runtime=True,
        )

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
        """Create a new browser instance with anti-detection."""
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--hide-scrollbars",
            "--disable-extensions",
            "--disable-features=IsolateOrigins,site-per-process",
            "--window-size=1280,800",
            "--force-color-profile=srgb",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
        ]

        browser = await self._playwright.chromium.launch(
            headless=True,
            args=launch_args,
        )

        # Create context with proxy if enabled
        # NOTE: Do NOT manually set Sec-Ch-Ua* headers here — they conflict with
        # playwright-stealth and trigger WAF (e.g. WeChat anti-bot). Let the
        # browser auto-send client hints or let stealth patch them.
        context_options: dict[str, Any] = {
            "user_agent": self._settings.user_agent,
            "viewport": {"width": 1280, "height": 800},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
        }

        if self._settings.proxy_enabled and self._settings.proxy_url:
            context_options["proxy"] = {"server": self._settings.proxy_url}

        context = await browser.new_context(**context_options)

        # Apply playwright-stealth anti-detection at context level
        # (injected into every new page automatically)
        await self._stealth.apply_stealth_async(context)

        return BrowserInstance(
            browser=browser,
            context=context,
            created_at=datetime.now(),
        )

    async def acquire(self) -> BrowserInstance:
        """Acquire a browser instance from pool."""
        await self.initialize()

        async with self._lock:
            max_age = timedelta(minutes=self._settings.browser_pool_max_age_minutes)
            now = datetime.now()

            expired_idx = None
            for i, instance in enumerate(self._pool):
                if now - instance.created_at > max_age:
                    expired_idx = i
                    break

            if expired_idx is None:
                if self._pool:
                    instance = min(self._pool, key=lambda x: x.usage_count)
                    instance.usage_count += 1
                    instance.last_used = now
                    return instance
                # Pool empty, will create below
                expired = None
            else:
                expired = self._pool.pop(expired_idx)

        # Outside lock: recycle and create (heavy IO, 2-3s per instance)
        if expired:
            try:
                await self._recycle_instance(expired)
            except Exception as e:
                logger.warning(f"[BrowserPool] Error recycling instance: {e}")

        new_instance = await self._create_instance()

        async with self._lock:
            # Guard against pool inflation when multiple coroutines race to recreate
            if len(self._pool) < self._max_pool_size:
                self._pool.append(new_instance)
            else:
                # Pool already has an instance from another coroutine; close the spare
                try:
                    await self._recycle_instance(new_instance)
                except Exception:
                    pass
                new_instance = self._pool[0]
            new_instance.usage_count += 1
            new_instance.last_used = now
            return new_instance

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
