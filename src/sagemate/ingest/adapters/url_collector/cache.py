"""TTL Cache with LRU eviction."""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional

from ....core.config import url_collector_settings, URLCollectorSettings
import dataclasses

from .models import CacheEntry, URLResult
from .validator import URLValidator

logger = logging.getLogger(__name__)


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

            # Return a copy with cached=True so we don't mutate the stored object
            return dataclasses.replace(entry.result, cached=True)

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
