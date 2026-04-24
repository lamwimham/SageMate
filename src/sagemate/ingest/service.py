"""
Ingest Service Facade.

Design Pattern: Facade + Dependency Injection
- Provides a clean, stable contract for submitting compile tasks
- Hides the complexity of task management, event publishing, and scheduling
- Allows core/agent/pipeline.py to ingest content without knowing about
  FastAPI globals or SSE internals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..models import IngestTaskState


class IngestService(ABC):
    """
    Abstract facade for the ingest subsystem.

    Implementations handle:
    - Task creation and tracking
    - Async compile scheduling
    - Progress event publishing
    """

    @abstractmethod
    async def submit_compile(
        self,
        *,
        source_slug: str,
        source_content: str,
        source_title: str,
        archive_path: Path,
        source_type: str,
        auto_compile: bool = True,
    ) -> str:
        """
        Submit a source document for compilation.

        Returns:
            task_id: The unique identifier for tracking progress.
        """
        ...

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[IngestTaskState]:
        """Retrieve the current state of a task."""
        ...

    @abstractmethod
    def list_tasks(self, limit: int = 20) -> list[dict]:
        """Return recent task history."""
        ...
