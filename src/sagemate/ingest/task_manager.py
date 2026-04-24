"""
Ingest Task Manager — Async task lifecycle + event-driven progress.

Design Pattern: Observer (via EventBus)
- No longer holds asyncio.Queue references directly
- Publishes progress events to the EventBus
- SSE endpoint subscribes to the bus independently
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.event_bus import EventBus
from ..models import IngestResult, IngestTaskState, IngestTaskStatus
from .service import IngestService


class IngestTaskManager(IngestService):
    """
    Manages async ingest tasks with event-driven progress streaming.

    Responsibilities:
    - Task lifecycle (create → update → complete/fail)
    - Compile scheduling and locking
    - Progress event publishing (via EventBus)

    Does NOT know about:
    - SSE queues, HTTP, or FastAPI
    """

    def __init__(self, event_bus: EventBus, store, max_concurrent_compiles: int = 3):
        self._tasks: dict[str, IngestTaskState] = {}
        self._event_bus = event_bus
        self._store = store
        self._source_locks: dict[str, asyncio.Lock] = {}
        self._compile_semaphore = asyncio.Semaphore(max_concurrent_compiles)

    # ── IngestService implementation ─────────────────────────────

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
        """Create a task and schedule background compilation."""
        task_id = self.create_task()

        if auto_compile:
            asyncio.create_task(
                self.run_compile(
                    task_id=task_id,
                    source_slug=source_slug,
                    source_content=source_content,
                    source_title=source_title,
                    archive_path=archive_path,
                    source_type=source_type,
                )
            )
        else:
            # No compile needed — mark as completed immediately
            await self.set_result(
                task_id,
                IngestResult(
                    success=True,
                    source_slug=source_slug,
                    wiki_pages_created=0,
                    wiki_pages_updated=0,
                ),
            )

        return task_id

    def create_task(self) -> str:
        task_id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        self._tasks[task_id] = IngestTaskState(
            task_id=task_id,
            status=IngestTaskStatus.QUEUED,
            step=0,
            total_steps=5,
            step_name="queued",
            message="任务已创建，等待处理",
            created_at=now,
            updated_at=now,
        )
        return task_id

    def get_task(self, task_id: str) -> Optional[IngestTaskState]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        # Lazy stale-task detection: auto-fail tasks stuck >10 min
        if task.status not in (IngestTaskStatus.COMPLETED, IngestTaskStatus.FAILED):
            try:
                last_update = datetime.fromisoformat(task.updated_at)
                if (datetime.now() - last_update).total_seconds() > 600:
                    task.status = IngestTaskStatus.FAILED
                    task.error = "任务处理超时（超过10分钟无响应），可能由于LLM服务不可用。请重试。"
                    task.message = task.error
                    task.updated_at = datetime.now().isoformat()
            except Exception:
                pass
        return task

    def list_tasks(self, limit: int = 20) -> list[dict]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        result = []
        for t in tasks[:limit]:
            result.append({
                "task_id": t.task_id,
                "status": t.status.value,
                "message": t.message,
                "source_slug": t.result.source_slug if t.result else None,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            })
        return result

    # ── Progress API (publishes to EventBus) ─────────────────────

    async def update_progress(self, task_id: str, status: IngestTaskStatus, step: int, message: str):
        task = self._tasks.get(task_id)
        if not task:
            return
        task.status = status
        task.step = step
        task.step_name = status.value
        task.message = message
        task.updated_at = datetime.now().isoformat()
        await self._event_bus.publish("ingest.progress", {
            "type": "progress",
            "task_id": task_id,
            "status": status.value,
            "step": step,
            "total_steps": task.total_steps,
            "message": message,
        })

    async def set_result(self, task_id: str, result: IngestResult):
        task = self._tasks.get(task_id)
        if not task:
            return
        task.result = result
        task.status = IngestTaskStatus.COMPLETED if result.success else IngestTaskStatus.FAILED
        task.message = f"完成: 创建 {result.wiki_pages_created} 页, 更新 {result.wiki_pages_updated} 页" if result.success else f"失败: {result.error}"
        task.step = task.total_steps
        task.updated_at = datetime.now().isoformat()
        await self._event_bus.publish("ingest.progress", {
            "type": "completed" if result.success else "failed",
            "task_id": task_id,
            "status": task.status.value,
            "step": task.total_steps,
            "message": task.message,
            "result": result.model_dump(),
        })

    async def set_error(self, task_id: str, error: str):
        task = self._tasks.get(task_id)
        if not task:
            return
        task.error = error
        task.status = IngestTaskStatus.FAILED
        task.message = f"失败: {error}"
        task.updated_at = datetime.now().isoformat()
        await self._event_bus.publish("ingest.progress", {
            "type": "failed",
            "task_id": task_id,
            "status": IngestTaskStatus.FAILED.value,
            "step": task.step,
            "total_steps": task.total_steps,
            "message": task.message,
            "error": error,
        })

    # ── Compile Orchestration ────────────────────────────────────

    async def run_compile(self, task_id: str, source_slug: str, source_content: str,
                          source_title: str, archive_path: Path, source_type: str):
        """Run the compiler under lock with progress callbacks."""
        # Avoid circular import at module load time
        from ..ingest.compiler.compiler import IncrementalCompiler
        from ..core.config import settings

        compiler = IncrementalCompiler(store=self._store, wiki_dir=settings.wiki_dir)

        async def progress_callback(step: str, message: str):
            step_map = {
                "reading_context": (IngestTaskStatus.READING_CONTEXT, 2),
                "calling_llm": (IngestTaskStatus.CALLING_LLM, 3),
                "writing_pages": (IngestTaskStatus.WRITING_PAGES, 4),
                "updating_index": (IngestTaskStatus.UPDATING_INDEX, 5),
            }
            status, step_num = step_map.get(step, (IngestTaskStatus.CALLING_LLM, 3))
            await self.update_progress(task_id, status, step_num, message)

        source_lock = self._source_locks.setdefault(source_slug, asyncio.Lock())
        async with self._compile_semaphore:
            async with source_lock:
                try:
                    await self.update_progress(task_id, IngestTaskStatus.CALLING_LLM, 3, "LLM 正在分析文档并提取知识...")
                    result = await asyncio.wait_for(
                        compiler.compile(
                            source_slug=source_slug,
                            source_content=source_content,
                            source_title=source_title,
                            progress_callback=progress_callback,
                        ),
                        timeout=300,
                    )
                    wiki_pages = [{"slug": p.slug, "title": p.title} for p in result.new_pages]
                    await self._store.upsert_source(
                        slug=source_slug,
                        title=source_title,
                        file_path=str(archive_path),
                        source_type=source_type,
                        status="completed",
                        wiki_pages=[p["slug"] for p in wiki_pages],
                    )
                    await self.set_result(task_id, IngestResult(
                        success=True,
                        source_slug=source_slug,
                        wiki_pages_created=len(result.new_pages),
                        wiki_pages_updated=0,
                        wiki_pages=wiki_pages,
                    ))
                except asyncio.TimeoutError:
                    err_msg = "编译超时（5分钟）。LLM 响应过慢或任务被阻塞，请稍后重试。"
                    await self._store.upsert_source(
                        slug=source_slug,
                        title=source_title,
                        file_path=str(archive_path),
                        source_type=source_type,
                        status="failed",
                        error=err_msg,
                    )
                    await self.set_error(task_id, err_msg)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    await self._store.upsert_source(
                        slug=source_slug,
                        title=source_title,
                        file_path=str(archive_path),
                        source_type=source_type,
                        status="failed",
                        error=str(e),
                    )
                    await self.set_error(task_id, str(e))
