"""SageMate Configuration"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings, loaded from env vars with defaults."""

    # Paths
    data_dir: Path = Field(default=Path(os.getenv("SAGEMATE_DATA_DIR", "./data")))

    # LLM
    llm_base_url: str = Field(
        default=os.getenv("SAGEMATE_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    )
    llm_api_key: str = Field(default=os.getenv("SAGEMATE_LLM_API_KEY", ""))
    llm_model: str = Field(default=os.getenv("SAGEMATE_LLM_MODEL", "qwen-plus"))

    # Vision LLM (for PDF parsing)
    # Default to standard DashScope endpoint for Qwen-VL
    vision_base_url: str = Field(
        default=os.getenv("SAGEMATE_VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    )
    vision_api_key: str = Field(default=os.getenv("SAGEMATE_VISION_API_KEY", ""))
    vision_model: str = Field(default=os.getenv("SAGEMATE_VISION_MODEL", "qwen-vl-max"))

    # Watcher
    watcher_debounce_ms: int = Field(default=500)

    # Compiler
    compiler_max_source_chars: int = Field(default=12000)
    compiler_max_wiki_context_chars: int = Field(default=8000)

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
        }
        subdir = mapping.get(category, "concepts")
        return self.wiki_dir / subdir


settings = Settings()
