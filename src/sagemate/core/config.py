"""SageMate Configuration"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Load .env file before Settings class reads env vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars


def _default_data_dir() -> Path:
    """Return the default data directory.

    Priority:
    1. SAGEMATE_DATA_DIR env var
    2. PyInstaller bundle directory (for desktop app)
    3. platformdirs user data directory (production default)
    """
    # 1. Env var override
    env_dir = os.getenv("SAGEMATE_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    # 2. PyInstaller bundled environment
    if hasattr(sys, '_MEIPASS'):
        # In PyInstaller, use a writable location outside the temp bundle
        from platformdirs import user_data_dir
        return Path(user_data_dir("SageMate", "SageMate"))

    # 3. Default: platform-specific user data directory
    try:
        from platformdirs import user_data_dir
        return Path(user_data_dir("SageMate", "SageMate"))
    except ImportError:
        # Fallback for environments without platformdirs
        return Path("./data")


class Settings(BaseModel):
    """Application settings, loaded from env vars with defaults."""

    # Paths
    data_dir: Path = Field(default_factory=_default_data_dir)
    obsidian_vault_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("SAGEMATE_OBSIDIAN_VAULT_PATH", "")
    )

    # LLM
    llm_base_url: str = Field(
        default_factory=lambda: os.getenv("SAGEMATE_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    )
    llm_api_key: str = Field(default_factory=lambda: os.getenv("SAGEMATE_LLM_API_KEY", ""))
    llm_model: str = Field(default_factory=lambda: os.getenv("SAGEMATE_LLM_MODEL", "qwen-plus"))

    # Vision LLM (for PDF parsing)
    # Default to standard DashScope endpoint for Qwen-VL
    vision_base_url: str = Field(
        default_factory=lambda: os.getenv("SAGEMATE_VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    )
    vision_api_key: str = Field(default_factory=lambda: os.getenv("SAGEMATE_VISION_API_KEY", ""))
    vision_model: str = Field(default_factory=lambda: os.getenv("SAGEMATE_VISION_MODEL", "qwen-vl-max"))

    # Watcher
    watcher_debounce_ms: int = Field(default=500)

    # Compiler
    compiler_max_source_chars: int = Field(default=40000)
    compiler_max_wiki_context_chars: int = Field(default=16000)

    # Lint
    lint_stale_days: int = Field(default=30)

    # Cron
    cron_auto_compile_enabled: bool = Field(default=True)
    cron_auto_compile_interval: int = Field(default=300)  # seconds
    cron_lint_enabled: bool = Field(default=True)
    cron_lint_interval: int = Field(default=1800)  # seconds

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def wiki_dir(self) -> Path:
        return self.data_dir / "wiki"

    @property
    def schema_dir(self) -> Path:
        return self.data_dir / "schema"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sagemate.db"

    @property
    def wiki_categories(self) -> list[Path]:
        return [
            self.wiki_dir / "entities",
            self.wiki_dir / "concepts",
            self.wiki_dir / "analyses",
            self.wiki_dir / "sources",
            self.wiki_dir / "notes",
        ]

    def ensure_dirs(self):
        """Create all required directories."""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        (self.raw_dir / "articles").mkdir(exist_ok=True)
        (self.raw_dir / "papers").mkdir(exist_ok=True)
        (self.raw_dir / "notes").mkdir(exist_ok=True)

        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        for cat_dir in self.wiki_categories:
            cat_dir.mkdir(exist_ok=True)

        self.schema_dir.mkdir(parents=True, exist_ok=True)

    def wiki_dir_for_category(self, category: str) -> Path:
        """Get the wiki subdirectory for a given category."""
        mapping = {
            "entity": "entities",
            "concept": "concepts",
            "analysis": "analyses",
            "source": "sources",
            "note": "notes",
        }
        subdir = mapping.get(category, "concepts")
        return self.wiki_dir / subdir


class URLCollectorSettings(BaseModel):
    """URL Collector specific settings."""
    tier1_timeout: int = Field(default=30)
    tier2_timeout: int = Field(default=30)
    tier2_network_idle_timeout: int = Field(default=5)
    tier2_wait_selector_timeout: int = Field(default=10)
    cache_enabled: bool = Field(default=True)
    cache_ttl_seconds: int = Field(default=3600)
    cache_max_entries: int = Field(default=1000)
    max_concurrent_requests: int = Field(default=5)
    retry_max_attempts: int = Field(default=3)
    retry_min_wait_seconds: int = Field(default=1)
    retry_max_wait_seconds: int = Field(default=10)
    browser_pool_max_age_minutes: int = Field(default=30)
    min_content_length: int = Field(default=50)
    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    proxy_enabled: bool = Field(default=False)
    proxy_url: str = Field(default="")


url_collector_settings = URLCollectorSettings()

settings = Settings()
