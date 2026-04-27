#!/usr/bin/env python3
"""Bump version across all SageMate project files.

Single source of truth: pyproject.toml
This script syncs the version to all other modules (Rust, Node, Python).

Usage:
    python scripts/bump_version.py 0.6.0
"""

import argparse
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# (relative_path, regex_pattern, replacement_template)
FILES = [
    # Python core
    ("pyproject.toml", r'^version = "[^"]+"', 'version = "{version}"'),
    ("src/sagemate/__init__.py", r'__version__ = "[^"]+"', '__version__ = "{version}"'),
    # FastAPI app version
    ("src/sagemate/api/app.py", r'version="[^"]+"', 'version="{version}"'),
    ("src/sagemate/api/app.py", r'"version": "[^"]+"', '"version": "{version}"'),
    # Rust / Tauri
    ("src-tauri/Cargo.toml", r'^version = "[^"]+"', 'version = "{version}"'),
    ("src-tauri/tauri.conf.json", r'"version": "[^"]+"', '"version": "{version}"'),
    # Frontend
    ("frontend/package.json", r'"version": "[^"]+"', '"version": "{version}"'),
]


def bump(version: str) -> None:
    for rel_path, pattern, template in FILES:
        path = PROJECT_ROOT / rel_path
        if not path.exists():
            print(f"⚠️  跳过: {rel_path} (不存在)")
            continue

        content = path.read_text(encoding="utf-8")
        new_content = re.sub(
            pattern,
            template.format(version=version),
            content,
            count=1,
            flags=re.MULTILINE,
        )

        if new_content == content:
            print(f"⚠️  未改动: {rel_path}")
        else:
            path.write_text(new_content, encoding="utf-8")
            print(f"✅ 已更新: {rel_path} -> {version}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bump SageMate version across Python, Rust, and Node modules"
    )
    parser.add_argument("version", help="New version, e.g. 0.6.0")
    args = parser.parse_args()

    bump(args.version)
    print(f"\n🎉 已同步到 {args.version}")
    print(
        f"下一步:\n"
        f"  git add -A\n"
        f"  git commit -m 'release: bump version to {args.version}'\n"
        f"  git tag v{args.version}\n"
        f"  git push origin main --tags"
    )
