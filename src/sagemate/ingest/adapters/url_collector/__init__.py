"""URL Collector Package — Tiered scraping with cache, browser pool, and site handlers.

Backward-compatible imports:
    from ...ingest.adapters.url_collector import URLCollector, URLResult, get_default_collector
"""

from .models import URLResult, CacheEntry
from .validator import URLValidator
from .cache import TTLCache
from .browser_pool import BrowserInstance, BrowserPool
from .table_extractor import TableExtractor, TrafilaturaTableExtractor, HybridTableExtractor
from .handlers import SiteHandler, WeChatHandler, GenericHandler, SiteHandlerRegistry
from .collector import URLCollector, URLCollectorFactory, get_default_collector

__all__ = [
    "URLResult",
    "CacheEntry",
    "URLValidator",
    "TTLCache",
    "BrowserInstance",
    "BrowserPool",
    "TableExtractor",
    "TrafilaturaTableExtractor",
    "HybridTableExtractor",
    "SiteHandler",
    "WeChatHandler",
    "GenericHandler",
    "SiteHandlerRegistry",
    "URLCollector",
    "URLCollectorFactory",
    "get_default_collector",
]
