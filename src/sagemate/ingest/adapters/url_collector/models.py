"""URL Collector data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


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
