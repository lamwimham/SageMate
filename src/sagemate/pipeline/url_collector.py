"""URL Collector Module - Tier 1.5 Scraping.

Fetches content from URLs using `curl_cffi` (Chrome impersonation) + `trafilatura` extraction.
Designed for high success rate on modern websites (blogs, news, docs).
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from curl_cffi import AsyncSession
import trafilatura

logger = logging.getLogger(__name__)


@dataclass
class URLResult:
    url: str
    title: str
    content: str
    success: bool
    error: str = ""
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class URLCollector:
    """
    Collects content from URLs using a tiered strategy.
    Currently implements Tier 1.5: curl_cffi (Chrome TLS fingerprint) + trafilatura.
    """

    # Patterns to detect if a string is a URL
    URL_PATTERN = re.compile(r'https?://[^\s/$.?#].[^\s]*')

    @staticmethod
    def is_url(text: str) -> bool:
        """Check if text looks like a URL."""
        return bool(URLCollector.URL_PATTERN.search(text))

    @classmethod
    async def collect(cls, url: str, timeout: int = 30) -> URLResult:
        """
        Collect content from a URL.
        
        Args:
            url: The URL to scrape.
            timeout: Request timeout in seconds.
            
        Returns:
            URLResult object containing content or error.
        """
        try:
            # Tier 1.5: curl_cffi with Chrome impersonation
            # trust_env=True uses system proxies (SOCKS/HTTP) if set, 
            # which helps bypass regional blocks.
            async with AsyncSession(impersonate="chrome110", timeout=timeout, trust_env=True) as session:
                logger.info(f"[URLCollector] Fetching {url} with Chrome impersonation...")
                
                # We set a reasonable User-Agent just in case, though impersonate handles it
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }
                
                resp = await session.get(url, headers=headers)
                
                # Check for common failure codes
                if resp.status_code != 200:
                    return URLResult(
                        url=url,
                        title="",
                        content="",
                        success=False,
                        error=f"HTTP Error: {resp.status_code}"
                    )

                # Extract text using trafilatura
                # include_comments=False keeps it clean
                # include_tables=True for data tables
                text = resp.text
                extracted = trafilatura.extract(
                    text, 
                    include_comments=False, 
                    include_tables=True,
                    output_format="markdown" # Markdown is better for LLM ingestion
                )

                if not extracted or len(extracted.strip()) < 50:
                    # Fallback check: maybe trafilatura failed but there's text?
                    # Sometimes JS-rendered content is missing in raw HTML.
                    # For MVP, we consider this a failure or partial success.
                    return URLResult(
                        url=url,
                        title="",
                        content=text[:1000], # Return raw snippet for debugging if needed
                        success=False,
                        error="Content extraction failed or too short (likely JS-heavy site)"
                    )

                # Extract metadata (Title, Author, Date)
                metadata = trafilatura.metadata.extract_metadata(text)
                title = metadata.get('title', '') if metadata else ''
                
                # Clean up content (remove excessive whitespace)
                clean_content = re.sub(r'\n\s*\n', '\n\n', extracted).strip()

                return URLResult(
                    url=url,
                    title=title or extracted.split('\n')[0][:50],
                    content=clean_content,
                    success=True,
                    metadata=metadata
                )

        except Exception as e:
            logger.error(f"[URLCollector] Failed to collect {url}: {e}")
            return URLResult(
                url=url,
                title="",
                content="",
                success=False,
                error=f"Collection exception: {str(e)}"
            )
