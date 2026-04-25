"""
Compile Pipeline — Two-phase ingest architecture.

Phase 1 (Archive): store raw source → returns immediately
Phase 2 (Compile): create CompileTask → async pipeline execution

Design Patterns:
- Pipeline: stages are explicit, each with its own progress step
- Repository: CompileTaskRepository isolates SQL from business logic
- Observer: EventBus for decoupled SSE progress streaming
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
import uuid
from datetime import datetime
from typing import Optional

from ...core.event_bus import EventBus
from ...core.store import Store
from ...models import CompileTask, CompileTaskResult, CompileTaskStatus

logger = logging.getLogger(__name__)


class CompileTaskRepository:
    """Repository for compile_tasks table. Isolates SQL from business logic."""

    def __init__(self, store: Store):
        self._store = store

    async def create(self, task_id: str, source_slug: str) -> None:
        await self._store.create_compile_task(task_id, source_slug)

    async def update_status(self, task_id: str, status: CompileTaskStatus, step: int, message: str) -> None:
        await self._store.update_compile_task_status(task_id, status.value, step, message)

    async def set_result(self, task_id: str, result: CompileTaskResult) -> None:
        await self._store.set_compile_task_result(task_id, result.model_dump())

    async def set_error(self, task_id: str, error: str) -> None:
        await self._store.set_compile_task_error(task_id, error)

    async def get(self, task_id: str) -> Optional[CompileTask]:
        row = await self._store.get_compile_task(task_id)
        if not row:
            return None
        return self._row_to_model(row)

    async def list_unfinished(self) -> list[CompileTask]:
        rows = await self._store.list_unfinished_compile_tasks()
        return [self._row_to_model(r) for r in rows]

    async def list_recent(self, limit: int = 50) -> list[CompileTask]:
        rows = await self._store.list_compile_tasks(limit)
        return [self._row_to_model(r) for r in rows]

    @staticmethod
    def _row_to_model(row: dict) -> CompileTask:
        result = None
        if row.get("result"):
            try:
                result = CompileTaskResult(**row["result"])
            except Exception:
                result = None
        return CompileTask(
            task_id=row["task_id"],
            source_slug=row["source_slug"],
            source_title=row.get("source_title") or row["source_slug"],
            status=CompileTaskStatus(row["status"]),
            step=row.get("step", 0),
            total_steps=row.get("total_steps", 6),
            message=row.get("message", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            result=result,
            error=row.get("error"),
        )


class CompilePipeline:
    """
    Compile pipeline that transforms a raw source into wiki pages.

    Responsibilities:
    - Create persistent CompileTask records
    - Orchestrate compilation via IncrementalCompiler
    - Publish progress events to EventBus (for SSE streaming)
    - Persist task status after each phase

    Does NOT handle:
    - Source archiving (done by IngestTaskManager / ingest_file)
    - HTTP or SSE transport (handled by FastAPI endpoint)
    """

    STEP_MAP = {
        "reading_context": (CompileTaskStatus.READING_CONTEXT, 2),
        "calling_llm": (CompileTaskStatus.CALLING_LLM, 3),
        "writing_pages": (CompileTaskStatus.WRITING_PAGES, 4),
        "updating_index": (CompileTaskStatus.UPDATING_INDEX, 5),
    }
    COMPILE_TIMEOUT_SECONDS = 300
    TASK_ID_LENGTH = 12
    MAX_CONCURRENT_COMPILES = 3

    def __init__(self, store: Store, compiler, event_bus: EventBus):
        self._repo = CompileTaskRepository(store)
        self._compiler = compiler
        self._event_bus = event_bus
        self._source_locks: dict[str, asyncio.Lock] = {}
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_COMPILES)
        self._running_tasks: set[asyncio.Task] = set()

    async def submit(self, source_slug: str, source_content: str, source_title: str) -> str:
        """Submit a source for compilation. Returns compile_task_id immediately."""
        task_id = uuid.uuid4().hex[:self.TASK_ID_LENGTH]
        await self._repo.create(task_id, source_slug)
        task = asyncio.create_task(
            self._run(task_id, source_slug, source_content, source_title)
        )
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)
        return task_id

    async def _run(self, task_id: str, source_slug: str, source_content: str, source_title: str):
        """Execute the compile pipeline under lock."""
        logger.info(f"[CompilePipeline] Starting compile for {source_slug}, content length={len(source_content)}")

        source_lock = self._source_locks.setdefault(source_slug, asyncio.Lock())
        async with self._semaphore:
            async with source_lock:
                try:
                    # Phase 1-2: parsing + reading_context (pre-compile)
                    await self._progress(task_id, CompileTaskStatus.PARSING, 1, "正在准备编译...")
                    await self._progress(task_id, CompileTaskStatus.READING_CONTEXT, 2, "正在读取知识库上下文...")

                    # Phase 3-5: compile with progress callback
                    logger.info(f"[CompilePipeline] Calling compiler.compile for {source_slug}")
                    result = await asyncio.wait_for(
                        self._compiler.compile(
                            source_slug=source_slug,
                            source_content=source_content,
                            source_title=source_title,
                            progress_callback=self._make_progress_callback(task_id),
                        ),
                        timeout=self.COMPILE_TIMEOUT_SECONDS,
                    )
                    logger.info(f"[CompilePipeline] compile returned: new_pages={len(result.new_pages)}, source_archive={result.source_archive is not None}")

                    wiki_pages = [{"slug": p.slug, "title": p.title} for p in result.new_pages]
                    await self._repo.set_result(
                        task_id,
                        CompileTaskResult(
                            success=True,
                            source_slug=source_slug,
                            wiki_pages_created=len(result.new_pages),
                            wiki_pages_updated=0,
                            wiki_pages=wiki_pages,
                        ),
                    )
                    await self._publish(task_id, "completed", CompileTaskStatus.COMPLETED, 6,
                                        f"完成: 创建 {len(result.new_pages)} 页")
                    await self._update_source_status(source_slug, "compiled", wiki_pages=[p["slug"] for p in wiki_pages])
                    logger.info(f"[CompilePipeline] Compile completed for {source_slug}: {len(result.new_pages)} pages created")

                except asyncio.TimeoutError:
                    err_msg = f"编译超时（{self.COMPILE_TIMEOUT_SECONDS // 60}分钟）。LLM 响应过慢或任务被阻塞，请稍后重试。"
                    logger.error(f"[CompilePipeline] Timeout for {source_slug}")
                    await self._fail_task(task_id, source_slug, err_msg)

                except Exception as e:
                    logger.error(f"[CompilePipeline] Exception for {source_slug}: {e}")
                    traceback.print_exc()
                    await self._fail_task(task_id, source_slug, str(e))

                finally:
                    # Clean up source lock to prevent unbounded memory growth
                    if source_slug in self._source_locks and not source_lock.locked():
                        self._source_locks.pop(source_slug, None)

    async def _fail_task(self, task_id: str, source_slug: str, error_msg: str):
        """Mark a compile task as failed and update source status."""
        await self._repo.set_error(task_id, error_msg)
        await self._publish(task_id, "failed", CompileTaskStatus.FAILED, 0, error_msg)
        await self._update_source_status(source_slug, "failed")

    async def _update_source_status(self, source_slug: str, status: str, wiki_pages: list[str] | None = None):
        """Update source record status after compile completes or fails."""
        store = self._repo._store
        source = await store.get_source(source_slug)
        if source:
            await store.upsert_source(
                slug=source_slug,
                title=source.get("title", source_slug),
                file_path=source.get("file_path", ""),
                source_type=source.get("source_type", "unknown"),
                status=status,
                wiki_pages=wiki_pages or [],
            )

    def _make_progress_callback(self, task_id: str):
        """Create a progress callback for IncrementalCompiler."""
        async def callback(step: str, message: str):
            mapped = self.STEP_MAP.get(step)
            if mapped is None:
                raise ValueError(f"Unknown compile step: {step!r}")
            status, step_num = mapped
            await self._progress(task_id, status, step_num, message)

        return callback

    async def _progress(self, task_id: str, status: CompileTaskStatus, step: int, message: str):
        """Persist status and publish event."""
        await self._repo.update_status(task_id, status, step, message)
        await self._publish(task_id, "progress", status, step, message)

    async def _publish(self, task_id: str, event_type: str, status: CompileTaskStatus, step: int, message: str):
        """Publish progress event to EventBus."""
        await self._event_bus.publish("compile.progress", {
            "type": event_type,
            "task_id": task_id,
            "status": status.value,
            "step": step,
            "total_steps": 6,
            "message": message,
        })
