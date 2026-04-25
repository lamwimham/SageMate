#!/usr/bin/env python3
"""Reset all SageMate process data, preserving only directory structure and DB schema.

Clears:
  - data/raw/ (all archived source files)
  - data/wiki/ (all generated .md pages)
  - data/sagemate.db (all table rows, keeps schema)

Preserves:
  - data/schema/ (unchanged)
  - All directory structures
  - DB table definitions (pages, sources, search_idx)

Note: If the backend is running, it will be stopped before reset.
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sagemate.core.config import settings
from sagemate.core.store import Store


def clear_directory(dir_path: Path, keep_git: bool = True):
    """Remove all files in a directory but keep the directory tree."""
    if not dir_path.exists():
        print(f"  [skip] {dir_path} does not exist")
        return
    for item in dir_path.rglob("*"):
        if item.is_file():
            if keep_git and item.name == ".gitkeep":
                continue
            item.unlink()
            print(f"  [del] {item.relative_to(settings.data_dir)}")
    print(f"  [ok] {dir_path.relative_to(settings.data_dir)} cleared (dirs preserved)")


def kill_db_holders():
    """Kill any process holding a lock on the database file."""
    db_path = settings.db_path
    if not db_path.exists():
        return

    try:
        result = subprocess.run(
            ["lsof", "-t", str(db_path)],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            my_pid = str(os.getpid())
            for pid in pids:
                if pid != my_pid:
                    print(f"  [kill] Process {pid} holding DB lock — terminating")
                    subprocess.run(["kill", pid], capture_output=True, timeout=3)
            # Wait for locks to release
            import time
            time.sleep(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


async def clear_db_tables(db_path: Path):
    """Delete all rows from DB tables, keeping schema intact."""
    if not db_path.exists():
        print(f"  [skip] {db_path} does not exist")
        return

    # Kill processes holding the lock
    kill_db_holders()

    store = Store(db_path)
    await store.connect()

    db = store._db
    # Temporarily disable foreign keys to avoid constraint violations during reset
    await db.execute("PRAGMA foreign_keys=OFF")

    # Delete FTS5 entries first (they reference page slugs)
    await db.execute("DELETE FROM search_idx")
    await db.execute("DELETE FROM pages")
    await db.execute("DELETE FROM sources")
    await db.commit()

    # Vacuum to reclaim space
    await db.execute("VACUUM")
    await db.commit()

    # Re-enable foreign keys
    await db.execute("PRAGMA foreign_keys=ON")
    await db.commit()

    await store.close()
    print(f"  [ok] {db_path.relative_to(settings.data_dir)} tables cleared, schema preserved")


async def main():
    print("=" * 60)
    print("SageMate Data Reset")
    print("=" * 60)
    print(f"Data directory: {settings.data_dir.absolute()}")
    print()

    # 1. Clear raw files
    print("[1/3] Clearing raw files...")
    clear_directory(settings.raw_dir)
    print()

    # 2. Clear wiki markdown files
    print("[2/3] Clearing wiki pages...")
    clear_directory(settings.wiki_dir)
    print()

    # 3. Clear DB table data (keep schema)
    print("[3/3] Clearing database tables...")
    await clear_db_tables(settings.db_path)
    print()

    # Re-create directory structure
    settings.ensure_dirs()

    print("=" * 60)
    print("Reset complete. All process data cleared.")
    print("Schema files and directory structure preserved.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
