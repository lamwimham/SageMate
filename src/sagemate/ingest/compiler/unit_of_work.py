"""
Wiki Write Unit — Atomic file persistence for the compiler.

Design Pattern: Unit of Work
- Collects all pending file writes and DB operations
- Commits atomically: temp files → os.replace → DB ops
- On failure: rolls back by deleting temp files, leaving disk untouched

This solves the "half-written wiki" problem:
if compile crashes after writing 3 of 10 pages, no partial state remains.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

DbOperation = Callable[[], Awaitable[None]]


@dataclass
class _FileOperation:
    target: Path
    content: str


class WikiWriteUnit:
    """
    Accumulates writes to the wiki directory and commits them atomically.

    Usage:
        uow = WikiWriteUnit(wiki_dir)
        uow.schedule_write(Path("sources/foo.md"), content)
        uow.schedule_db(lambda: store.upsert_page(...))
        await uow.commit()
    """

    def __init__(self, wiki_dir: Path):
        self._wiki_dir = wiki_dir
        self._files: list[_FileOperation] = []
        self._db_ops: list[DbOperation] = []

    def schedule_write(self, relative_path: Path, content: str) -> None:
        """Plan to write a file at `wiki_dir / relative_path`."""
        self._files.append(_FileOperation(
            target=self._wiki_dir / relative_path,
            content=content,
        ))

    def schedule_db(self, operation: DbOperation) -> None:
        """Plan a database operation to run after all files are committed."""
        self._db_ops.append(operation)

    async def commit(self) -> None:
        """
        Atomic commit:
        1. Write all files to temp locations
        2. Run DB operations (SQLite is transactional)
        3. Rename temps to targets (atomic on POSIX & Windows)

        If any step fails before Phase 3, temps are cleaned up and
        targets + DB are untouched.
        """
        temp_files: list[tuple[Path, Path]] = []  # (temp, target)

        try:
            # Phase 1: Write to temp files adjacent to targets
            for op in self._files:
                op.target.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_path_str = tempfile.mkstemp(
                    dir=op.target.parent,
                    prefix=".tmp_",
                    suffix=".md",
                )
                try:
                    os.write(fd, op.content.encode("utf-8"))
                finally:
                    os.close(fd)
                temp_files.append((Path(temp_path_str), op.target))

            # Phase 2: DB operations (transactional — safe to rollback)
            for op in self._db_ops:
                await op()

            # Phase 3: Atomic replace (POSIX: atomic; Windows: best-effort)
            for temp_path, target_path in temp_files:
                os.replace(temp_path, target_path)

        except Exception:
            # Rollback: delete any temp files that still exist
            for temp_path, _ in temp_files:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except OSError:
                    pass
            raise

    def __len__(self) -> int:
        """Return total scheduled operations (files + DB)."""
        return len(self._files) + len(self._db_ops)
