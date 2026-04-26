#!/usr/bin/env python3
"""
Migrate legacy data into the new project-based directory structure.

Before projects:
  ~/Library/Application Support/SageMate/raw/
  ~/Library/Application Support/SageMate/wiki/

After projects:
  ~/Library/Application Support/SageMate/projects/default/raw/
  ~/Library/Application Support/SageMate/projects/default/wiki/

This script:
1. Moves files from old raw/ and wiki/ into projects/default/
2. Updates file_path references in the database
"""

import shutil
import sqlite3
from pathlib import Path
import sys


def migrate():
    # Determine data directory (same logic as config.py)
    import os
    env_dir = os.getenv("SAGEMATE_DATA_DIR")
    if env_dir:
        data_dir = Path(env_dir)
    else:
        try:
            from platformdirs import user_data_dir
            data_dir = Path(user_data_dir("SageMate", "SageMate"))
        except ImportError:
            data_dir = Path("./data")

    print(f"Data directory: {data_dir}")

    old_raw = data_dir / "raw"
    old_wiki = data_dir / "wiki"
    project_raw = data_dir / "projects" / "default" / "raw"
    project_wiki = data_dir / "projects" / "default" / "wiki"
    db_path = data_dir / "sagemate.db"

    # Ensure target directories exist
    project_raw.mkdir(parents=True, exist_ok=True)
    project_wiki.mkdir(parents=True, exist_ok=True)

    moved_files = []

    # ── Migrate raw files ──
    if old_raw.exists():
        for src in old_raw.rglob("*"):
            if src.is_file():
                rel = src.relative_to(old_raw)
                dst = project_raw / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                # Avoid overwriting if already exists in target
                if dst.exists():
                    print(f"  Skip (already exists): {rel}")
                    continue
                shutil.move(str(src), str(dst))
                moved_files.append((str(src), str(dst)))
                print(f"  Moved raw: {rel}")
        # Remove empty old directories
        for subdir in sorted(old_raw.rglob("*"), reverse=True):
            if subdir.is_dir() and not any(subdir.iterdir()):
                subdir.rmdir()
        if old_raw.exists() and not any(old_raw.iterdir()):
            old_raw.rmdir()
            print("  Removed empty old raw/ directory")

    # ── Migrate wiki files ──
    if old_wiki.exists():
        for src in old_wiki.rglob("*"):
            if src.is_file():
                rel = src.relative_to(old_wiki)
                dst = project_wiki / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    print(f"  Skip (already exists): {rel}")
                    continue
                shutil.move(str(src), str(dst))
                moved_files.append((str(src), str(dst)))
                print(f"  Moved wiki: {rel}")
        for subdir in sorted(old_wiki.rglob("*"), reverse=True):
            if subdir.is_dir() and not any(subdir.iterdir()):
                subdir.rmdir()
        if old_wiki.exists() and not any(old_wiki.iterdir()):
            old_wiki.rmdir()
            print("  Removed empty old wiki/ directory")

    # ── Update database file_path references ──
    if db_path.exists() and moved_files:
        print(f"\nUpdating database: {db_path}")
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        for old_path, new_path in moved_files:
            cursor.execute(
                "UPDATE sources SET file_path = ? WHERE file_path = ?",
                (new_path, old_path),
            )
            if cursor.rowcount > 0:
                print(f"  Updated DB: {old_path} -> {new_path}")

        conn.commit()
        conn.close()

    print("\nMigration complete.")
    print(f"Total files moved: {len(moved_files)}")
    return 0


if __name__ == "__main__":
    sys.exit(migrate())
