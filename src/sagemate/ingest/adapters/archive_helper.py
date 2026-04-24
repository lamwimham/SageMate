"""
Archive Path Helper — centralized raw-data directory management.

Eliminates hard-coded archive paths scattered across API endpoints,
AgentPipeline handlers, and WeChat channel code.
"""

from __future__ import annotations

from pathlib import Path


class ArchiveHelper:
    """Provides canonical archive directories under data/raw/."""

    @staticmethod
    def files_dir(raw_dir: Path) -> Path:
        """Original files: PDF, DOCX, images, voice, etc."""
        return raw_dir / "files"

    @staticmethod
    def notes_dir(raw_dir: Path) -> Path:
        """Plain-text notes / memos."""
        return raw_dir / "notes"

    @staticmethod
    def papers_dir(raw_dir: Path) -> Path:
        """URL-collected articles (already parsed to Markdown)."""
        return raw_dir / "papers" / "originals"

    @staticmethod
    def images_dir(raw_dir: Path) -> Path:
        """Raw image uploads."""
        return raw_dir / "images"

    @staticmethod
    def voice_dir(raw_dir: Path) -> Path:
        """Raw voice uploads."""
        return raw_dir / "voice"
