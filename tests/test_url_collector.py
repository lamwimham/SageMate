"""
Tests for URL Collector Module.

Coverage:
- URLValidator: valid/invalid URL validation
- TTLCache: set/get, expiration, max entries, cleanup
- BrowserPool: initialization, acquire/release, get_page
- SiteHandler: WeChat match, Generic fallback
- URLCollector: Tier1/Tier2, cache hit, batch, invalid URL
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.sagemate.ingest.adapters.url_collector import (
    URLCollector,
    URLCollectorFactory,
    URLResult,
    URLValidator,
    TTLCache,
    BrowserPool,
    BrowserInstance,
    SiteHandlerRegistry,
    WeChatHandler,
    GenericHandler,
)
from src.sagemate.core.config import URLCollectorSettings


# ── Helper ────────────────────────────────────────────────────────────────────


def _make_collector(settings, cache, browser_pool=None, registry=None):
    """Factory helper to create a URLCollector with injected test dependencies."""
    from unittest.mock import AsyncMock
    return URLCollector(
        settings=settings,
        cache=cache,
        browser_pool=browser_pool or AsyncMock(),
        handler_registry=registry or SiteHandlerRegistry(),
        semaphore=asyncio.Semaphore(settings.max_concurrent_requests),
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def url_settings():
    """Test settings with smaller values."""
    return URLCollectorSettings(
        tier1_timeout=10,
        tier2_timeout=10,
        tier2_network_idle_timeout=2,
        tier2_wait_selector_timeout=3,
        cache_enabled=True,
        cache_ttl_seconds=60,
        cache_max_entries=10,
        max_concurrent_requests=3,
        retry_max_attempts=2,
        browser_pool_max_age_minutes=30,
        min_content_length=50,
    )


@pytest_asyncio.fixture
async def cache(url_settings):
    """Cache fixture."""
    cache = TTLCache(url_settings)
    yield cache
    await cache.clear()


@pytest_asyncio.fixture
async def browser_pool(url_settings):
    """Browser pool fixture with cleanup."""
    pool = BrowserPool(url_settings)
    yield pool
    await pool.close()


# ── URLValidator Tests ───────────────────────────────────────────────────────


def test_url_validator_valid_urls():
    """Test valid URLs are accepted."""
    assert URLValidator.validate("https://example.com")
    assert URLValidator.validate("https://example.com/path")
    assert URLValidator.validate("https://example.com/path?query=1")
    assert URLValidator.validate("http://localhost:8080")
    assert URLValidator.validate("https://mp.weixin.qq.com/s/abc123")
    assert URLValidator.validate("http://192.168.1.1:3000")


def test_url_validator_invalid_urls():
    """Test invalid URLs are rejected."""
    assert not URLValidator.validate("")
    assert not URLValidator.validate("not a url")
    assert not URLValidator.validate("ftp://invalid.protocol")
    assert not URLValidator.validate("http://")
    assert not URLValidator.validate("https://")


def test_url_validator_edge_cases():
    """Test edge cases."""
    assert URLValidator.validate("https://example.com/path?query=1&a=b#anchor")
    assert URLValidator.validate("http://example.com/")
    assert URLValidator.validate("https://sub.domain.example.com")


def test_url_validator_normalize():
    """Test URL normalization."""
    assert URLValidator.normalize("  https://example.com  ") == "https://example.com"
    assert URLValidator.normalize("https://example.com") == "https://example.com"


# ── TTLCache Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_set_and_get(cache):
    """Test cache set and get."""
    result = URLResult(
        url="https://example.com",
        title="Test Title",
        content="Test content here with enough length",
        success=True,
    )
    await cache.set(result.url, result)

    cached = await cache.get(result.url)
    assert cached is not None
    assert cached.title == "Test Title"
    assert cached.cached is True


@pytest.mark.asyncio
async def test_cache_miss(cache):
    """Test cache miss returns None."""
    cached = await cache.get("https://nonexistent.com")
    assert cached is None


@pytest.mark.asyncio
async def test_cache_expiration(cache, url_settings):
    """Test expired entries are not returned."""
    result = URLResult(
        url="https://expiring.com",
        title="Expiring",
        content="Content",
        success=True,
    )
    await cache.set(result.url, result)

    # Manually expire the entry
    async with cache._lock:
        entry = cache._cache.get(result.url)
        if entry:
            entry.expires_at = datetime.now() - timedelta(seconds=1)

    cached = await cache.get(result.url)
    assert cached is None  # Should be expired


@pytest.mark.asyncio
async def test_cache_max_entries(cache):
    """Test cache evicts oldest when over limit."""
    small_settings = URLCollectorSettings(cache_max_entries=3, cache_ttl_seconds=60)
    small_cache = TTLCache(small_settings)

    # Add more entries than limit
    for i in range(5):
        result = URLResult(
            url=f"https://site{i}.com",
            title=f"Site {i}",
            content="Content",
            success=True,
        )
        await small_cache.set(result.url, result)

    assert small_cache.size == 3
    # First entries should be evicted
    assert await small_cache.get("https://site0.com") is None
    assert await small_cache.get("https://site1.com") is None
    # Recent entries should exist
    assert await small_cache.get("https://site3.com") is not None
    assert await small_cache.get("https://site4.com") is not None

    await small_cache.clear()


@pytest.mark.asyncio
async def test_cache_cleanup_expired(cache, url_settings):
    """Test cleanup_expired removes old entries."""
    # Add entries
    for i in range(5):
        result = URLResult(
            url=f"https://site{i}.com",
            title=f"Site {i}",
            content="Content",
            success=True,
        )
        await cache.set(result.url, result)

    # Manually expire first 2 entries
    async with cache._lock:
        for i in range(2):
            entry = cache._cache.get(f"https://site{i}.com")
            if entry:
                entry.expires_at = datetime.now() - timedelta(seconds=1)

    cleaned = await cache.cleanup_expired()
    assert cleaned == 2
    assert cache.size == 3


@pytest.mark.asyncio
async def test_cache_clear(cache):
    """Test cache clear removes all entries."""
    for i in range(5):
        result = URLResult(
            url=f"https://site{i}.com",
            title=f"Site {i}",
            content="Content",
            success=True,
        )
        await cache.set(result.url, result)

    assert cache.size == 5
    await cache.clear()
    assert cache.size == 0


@pytest.mark.asyncio
async def test_cache_hit_count(cache):
    """Test hit count increments on access."""
    result = URLResult(
        url="https://example.com",
        title="Test",
        content="Content",
        success=True,
    )
    await cache.set(result.url, result)

    # Access multiple times
    await cache.get(result.url)
    await cache.get(result.url)
    await cache.get(result.url)

    async with cache._lock:
        entry = cache._cache.get(result.url)
        assert entry.hit_count == 3


# ── BrowserPool Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_pool_initialize(browser_pool):
    """Test browser pool initializes correctly."""
    await browser_pool.initialize()
    assert browser_pool._initialized
    assert browser_pool._playwright is not None
    assert len(browser_pool._pool) > 0


@pytest.mark.asyncio
async def test_browser_pool_acquire(browser_pool):
    """Test acquiring browser instance."""
    await browser_pool.initialize()
    instance = await browser_pool.acquire()
    assert instance.browser is not None
    assert instance.context is not None
    assert instance.usage_count >= 1


@pytest.mark.asyncio
async def test_browser_pool_release(browser_pool):
    """Test releasing browser instance."""
    await browser_pool.initialize()
    instance = await browser_pool.acquire()
    await browser_pool.release(instance)
    # Instance should still be in pool
    assert instance in browser_pool._pool


@pytest.mark.asyncio
async def test_browser_pool_get_page(browser_pool):
    """Test get_page context manager."""
    await browser_pool.initialize()

    async with browser_pool.get_page("https://example.com") as page:
        assert page is not None


@pytest.mark.asyncio
async def test_browser_pool_double_initialize(browser_pool):
    """Test double initialize doesn't create duplicates."""
    await browser_pool.initialize()
    initial_size = len(browser_pool._pool)
    await browser_pool.initialize()
    assert len(browser_pool._pool) == initial_size


@pytest.mark.asyncio
async def test_browser_pool_close(browser_pool):
    """Test browser pool closes properly."""
    await browser_pool.initialize()
    await browser_pool.close()
    assert not browser_pool._initialized
    assert len(browser_pool._pool) == 0


@pytest.mark.asyncio
async def test_browser_pool_recycling(url_settings):
    """Test old instances are recycled."""
    short_settings = URLCollectorSettings(
        browser_pool_max_age_minutes=1,
    )
    pool = BrowserPool(short_settings)
    await pool.initialize()

    instance = await pool.acquire()
    # Fake old creation time
    instance.created_at = datetime.now() - timedelta(minutes=2)
    await pool.release(instance)

    # Next acquire should get new instance
    new_instance = await pool.acquire()
    assert (datetime.now() - new_instance.created_at).total_seconds() < 60

    await pool.close()


# ── SiteHandler Tests ─────────────────────────────────────────────────────────


def test_site_handler_registry_defaults():
    """Test default handlers are registered."""
    registry = SiteHandlerRegistry()
    assert len(registry._handlers) >= 2


def test_site_handler_wechat_match():
    """Test WeChat handler matches WeChat URLs."""
    assert WeChatHandler.can_handle("https://mp.weixin.qq.com/s/abc123")
    assert WeChatHandler.can_handle("http://mp.weixin.qq.com/s/test")
    assert not WeChatHandler.can_handle("https://example.com")


def test_site_handler_generic_matches_all():
    """Test Generic handler matches all URLs."""
    assert GenericHandler.can_handle("https://example.com")
    assert GenericHandler.can_handle("https://any-site.com/path")


def test_site_handler_registry_get_handler():
    """Test registry returns correct handler."""
    registry = SiteHandlerRegistry()

    wechat_url = "https://mp.weixin.qq.com/s/test"
    handler = registry.get_handler(wechat_url)
    assert handler.name == "wechat"

    generic_url = "https://example.com"
    handler = registry.get_handler(generic_url)
    assert handler.name == "generic"


# ── URLCollector Static Tests ─────────────────────────────────────────────────


def test_url_collector_is_url_valid():
    """Test is_url static method with valid URLs."""
    assert URLCollector.is_url("https://example.com")
    assert URLCollector.is_url("http://localhost:8080")


def test_url_collector_is_url_invalid():
    """Test is_url static method with invalid URLs."""
    assert not URLCollector.is_url("plain text")
    assert not URLCollector.is_url("")
    assert not URLCollector.is_url("not-a-url")


# ── URLCollector Tier1 Mock Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collector_tier1_success_mock(url_settings, cache):
    """Test Tier 1 success with mocked fetch."""
    collector = _make_collector(url_settings, cache)

    # Mock the tier1 fetch to return success
    with patch.object(
        collector,
        "_tier1_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = URLResult(
            url="https://example.com",
            title="Example Title",
            content="This is example content with enough length for validation",
            success=True,
            extraction_tier="tier1",
        )

        result = await collector.collect("https://example.com")
        assert result.success
        assert result.extraction_tier == "tier1"
        assert "Example Title" in result.title


@pytest.mark.asyncio
async def test_collector_invalid_url(url_settings, cache):
    """Test invalid URL returns error."""
    collector = _make_collector(url_settings, cache)

    result = await collector.collect("not-a-valid-url")
    assert not result.success
    assert "Invalid URL" in result.error


@pytest.mark.asyncio
async def test_collector_cache_hit(url_settings, cache):
    """Test cache hit returns cached result."""
    # Pre-populate cache
    cached_result = URLResult(
        url="https://cached.com",
        title="Cached Title",
        content="Cached content",
        success=True,
        cached=False,  # Will be set to True on retrieval
    )
    await cache.set(cached_result.url, cached_result)

    collector = _make_collector(url_settings, cache)

    result = await collector.collect("https://cached.com")
    assert result.cached
    assert result.title == "Cached Title"


@pytest.mark.asyncio
async def test_collector_tier2_fallback_mock(url_settings, cache):
    """Test Tier 2 fallback when Tier 1 fails."""
    collector = _make_collector(url_settings, cache)

    with patch.object(
        collector,
        "_tier1_fetch",
        new_callable=AsyncMock,
    ) as mock_tier1:
        mock_tier1.return_value = URLResult(
            url="https://complex-site.com",
            title="",
            content="",  # Empty content triggers fallback
            success=False,
            error="Content too short",
        )

        with patch.object(
            collector,
            "_tier2_fetch",
            new_callable=AsyncMock,
        ) as mock_tier2:
            mock_tier2.return_value = URLResult(
                url="https://complex-site.com",
                title="Tier2 Title",
                content="Full content from Playwright",
                success=True,
                extraction_tier="tier2",
                site_handler="generic",
            )

            result = await collector.collect("https://complex-site.com")
            assert result.success
            assert result.extraction_tier == "tier2"


# ── URLCollector Batch Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collector_batch_success(url_settings, cache):
    """Test batch collection returns all results."""
    urls = [
        "https://site1.com",
        "https://site2.com",
        "https://site3.com",
    ]

    # Mock collect to return success for each
    async def mock_collect(url, timeout=None):
        return URLResult(
            url=url,
            title=f"Title for {url}",
            content="Content",
            success=True,
        )

    collector = _make_collector(url_settings, cache)

    with patch.object(
        collector,
        "collect",
        side_effect=mock_collect,
    ):
        results = await collector.collect_batch(urls)
        assert len(results) == 3
        assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_collector_batch_with_errors(url_settings, cache):
    """Test batch collection handles errors gracefully."""
    urls = [
        "https://success.com",
        "https://error.com",
        "https://another.com",
    ]

    results_map = {
        "https://success.com": URLResult(url="https://success.com", title="Title", content="Content", success=True),
        "https://error.com": URLResult(url="https://error.com", title="", content="", success=False, error="Failed"),
        "https://another.com": URLResult(url="https://another.com", title="Title", content="Content", success=True),
    }

    async def mock_collect(url, timeout=None):
        return results_map.get(url, URLResult(url=url, title="", content="", success=False, error="Unknown URL"))

    collector = _make_collector(url_settings, cache)

    with patch.object(
        collector,
        "collect",
        side_effect=mock_collect,
    ):
        results = await collector.collect_batch(urls)
        assert len(results) == 3
        # Check error result is included
        error_results = [r for r in results if not r.success]
        assert len(error_results) == 1


@pytest.mark.asyncio
async def test_collector_batch_concurrent_limit(url_settings, cache):
    """Test batch respects concurrency limit."""
    # Settings with low concurrency
    low_settings = URLCollectorSettings(max_concurrent_requests=2)
    collector = _make_collector(low_settings, cache)

    concurrent_count = [0]  # Use list to allow modification in closure
    max_concurrent = [0]

    async def tracked_collect(url, timeout=None):
        concurrent_count[0] += 1
        max_concurrent[0] = max(max_concurrent[0], concurrent_count[0])
        await asyncio.sleep(0.05)  # Small delay to ensure overlap
        concurrent_count[0] -= 1
        return URLResult(url=url, title="", content="", success=True)

    with patch.object(collector, "collect", side_effect=tracked_collect):
        urls = [f"https://site{i}.com" for i in range(6)]
        await collector.collect_batch(urls)

        assert max_concurrent[0] <= 2


# ── URLCollector Close Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collector_close():
    """Test close cleans up resources."""
    mock_pool = AsyncMock()
    mock_cache = AsyncMock()
    settings = URLCollectorSettings()
    registry = SiteHandlerRegistry()
    semaphore = asyncio.Semaphore(3)

    collector = URLCollector(
        settings=settings,
        cache=mock_cache,
        browser_pool=mock_pool,
        handler_registry=registry,
        semaphore=semaphore,
    )

    await collector.close()

    mock_pool.close.assert_called_once()
    mock_cache.clear.assert_called_once()
    assert collector._semaphore is None


# ── URLResult Tests ───────────────────────────────────────────────────────────


def test_url_result_creation():
    """Test URLResult creation."""
    result = URLResult(
        url="https://example.com",
        title="Test",
        content="Content",
        success=True,
    )
    assert result.url == "https://example.com"
    assert result.success
    assert result.metadata == {}


def test_url_result_with_metadata():
    """Test URLResult with metadata."""
    result = URLResult(
        url="https://example.com",
        title="Test",
        content="Content",
        success=True,
        metadata={"author": "John"},
        extraction_tier="tier1",
        site_handler="wechat",
    )
    assert result.metadata["author"] == "John"
    assert result.extraction_tier == "tier1"
    assert result.site_handler == "wechat"


def test_url_result_post_init():
    """Test URLResult post_init sets default metadata."""
    result = URLResult(
        url="https://example.com",
        title="Test",
        content="Content",
        success=True,
        metadata=None,
    )
    assert result.metadata == {}


# ── WeChatHandler Mock Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wechat_handler_prepare_context(url_settings):
    """Test WeChat handler prepares context correctly."""
    handler = WeChatHandler()
    mock_context = AsyncMock()

    await handler.prepare_context(mock_context, "https://mp.weixin.qq.com/s/test")

    mock_context.set_extra_http_headers.assert_called_once()
    call_args = mock_context.set_extra_http_headers.call_args[0][0]
    assert "Referer" in call_args
    assert "mp.weixin.qq.com" in call_args["Referer"]


@pytest.mark.asyncio
async def test_generic_handler_extract_success(url_settings):
    """Test GenericHandler extract with mocked page."""
    handler = GenericHandler()
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body><p>Test content</p></body></html>")

    result = await handler.extract(mock_page, "https://example.com", url_settings)

    # Note: actual trafilatura extraction may vary
    # This test verifies the method runs without errors
    assert result.url == "https://example.com"


# ── Integration: Full Flow Mock ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_flow_mock(url_settings, cache, browser_pool):
    """Test full collection flow with all mocks."""
    collector = _make_collector(url_settings, cache, browser_pool=browser_pool)

    # Mock tier1 success
    with patch.object(
        collector,
        "_tier1_fetch",
        new_callable=AsyncMock,
    ) as mock_tier1:
        mock_tier1.return_value = URLResult(
            url="https://test.com",
            title="Test Page",
            content="This is the full content of the test page with sufficient length",
            success=True,
        )

        result = await collector.collect("https://test.com")

        assert result.success
        assert result.title == "Test Page"
        assert not result.cached  # First call, not cached

        # Second call should be cached
        result2 = await collector.collect("https://test.com")
        assert result2.cached

    await collector.close()