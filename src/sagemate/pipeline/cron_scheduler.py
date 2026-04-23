"""Cron Job Scheduler for SageMate Core.

Manages periodic tasks:
- Auto-compile pending sources
- Periodic lint checks
- Wiki health monitoring
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CronScheduler:
    """Manages periodic background tasks."""

    def __init__(
        self,
        store=None,
        compiler=None,
        lint_engine=None,
        settings=None,
    ):
        self.store = store
        self.compiler = compiler
        self.lint_engine = lint_engine
        self.settings = settings
        self._tasks: list[asyncio.Task] = []
        self._running = False

    def start(self):
        """Start all scheduled tasks."""
        if self._running:
            return
        
        self._running = True
        logger.info("🕐 Cron scheduler started")

        # Auto-compile: check every N minutes (if enabled)
        if getattr(self.settings, "cron_auto_compile_enabled", True):
            auto_compile_interval = getattr(self.settings, "cron_auto_compile_interval", 300)
            task1 = asyncio.create_task(self._auto_compile_loop(auto_compile_interval))
            self._tasks.append(task1)
            logger.info(f"  ⏰ Auto-compile: every {auto_compile_interval}s")
        else:
            logger.info("  ⏰ Auto-compile: disabled")

        # Lint check: every N minutes (if enabled)
        if getattr(self.settings, "cron_lint_enabled", True):
            lint_interval = getattr(self.settings, "cron_lint_interval", 1800)
            task2 = asyncio.create_task(self._lint_loop(lint_interval))
            self._tasks.append(task2)
            logger.info(f"  ⏰ Lint check: every {lint_interval}s")
        else:
            logger.info("  ⏰ Lint check: disabled")

    def stop(self):
        """Stop all scheduled tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("🕐 Cron scheduler stopped")

    async def _auto_compile_loop(self, interval: int):
        """Periodically check for pending sources and compile them."""
        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break
                    
                await self._auto_compile_pending()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-compile loop error: {e}")
                await asyncio.sleep(60)  # Back off on error

    async def _auto_compile_pending(self):
        """Compile any sources that are in 'pending' status."""
        if not self.store or not self.compiler:
            return

        try:
            sources = await self.store.list_sources()
            pending = [s for s in sources if s.get("status") == "pending"]
            
            if not pending:
                return

            logger.info(f"🔨 Auto-compiling {len(pending)} pending source(s)...")
            
            for source in pending:
                slug = source.get("slug", "")
                title = source.get("title", "")
                file_path = source.get("file_path", "")

                if not file_path or not Path(file_path).exists():
                    await self.store.upsert_source(
                        slug=slug,
                        title=title,
                        file_path=file_path,
                        status="failed",
                        error="File not found",
                    )
                    continue

                try:
                    from .pipeline.parser import DeterministicParser
                    parser = DeterministicParser()
                    _, source_content = await parser.parse(Path(file_path), self.settings.raw_dir)

                    result = await self.compiler.compile(
                        source_slug=slug,
                        source_content=source_content,
                        source_title=title,
                    )

                    await self.store.upsert_source(
                        slug=slug,
                        title=title,
                        file_path=file_path,
                        status="completed",
                        wiki_pages=[p.slug for p in result.new_pages],
                    )

                    logger.info(f"✅ Auto-compiled: {slug} ({len(result.new_pages)} pages)")

                except Exception as e:
                    logger.error(f"❌ Auto-compile failed for {slug}: {e}")
                    await self.store.upsert_source(
                        slug=slug,
                        title=title,
                        file_path=file_path,
                        status="failed",
                        error=str(e),
                    )

        except Exception as e:
            logger.error(f"Auto-compile error: {e}")

    async def _lint_loop(self, interval: int):
        """Periodically run lint checks on the wiki."""
        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break
                    
                await self._run_lint_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Lint loop error: {e}")
                await asyncio.sleep(120)  # Back off on error

    async def _run_lint_check(self):
        """Run a lint check and log any issues."""
        if not self.lint_engine:
            return

        try:
            report = await self.lint_engine.run()
            
            if report.issue_count == 0:
                logger.info("✅ Lint check passed — no issues found")
                return

            # Log issues
            for issue in report.issues:
                severity = issue.severity.value.upper()
                logger.warning(
                    f"⚠️ Lint [{severity}] {issue.issue_type.value}: "
                    f"{issue.page_slug} — {issue.description}"
                )

            logger.info(
                f"📊 Lint complete: {report.issue_count} issues "
                f"({report.high_severity_count} high severity)"
            )

        except Exception as e:
            logger.error(f"Lint check error: {e}")
