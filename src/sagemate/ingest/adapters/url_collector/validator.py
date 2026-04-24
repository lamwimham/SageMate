"""URL validation utilities."""

from __future__ import annotations

import re
from urllib.parse import urlparse


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
