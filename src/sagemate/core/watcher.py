"""
File System Watcher & Sync Engine.

Dual watcher: monitors both raw/ (for new sources) and wiki/ (for LLM edits).
Routes events to the appropriate handler and syncs to SQLite.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..core.config import Settings, settings
from ..core.store import Store
from ..models import WikiCategory, WikiPage


class WikiFileHandler(FileSystemEventHandler):
    """Handles wiki directory events and syncs to DB."""

    def __init__(self, store: Store, wiki_dir: Path, debounce_ms: int = 500):
        self.store = store
        self.wiki_dir = wiki_dir
        self._debounce_timers: dict[str, threading.Timer] = {}
        self._debounce_ms = debounce_ms
        # Capture the main event loop to schedule coroutines from watcher thread
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

    def _debounce(self, path: Path, callback: Callable):
        """Debounce to handle multiple rapid save events."""
        path_str = str(path)
        if path_str in self._debounce_timers:
            self._debounce_timers[path_str].cancel()

        def run_callback():
            """Scheduled in a timer thread; bridges to asyncio loop."""
            try:
                asyncio.run_coroutine_threadsafe(callback(path), self._loop)
            except Exception as e:
                print(f"[Watcher] Failed to schedule task: {e}")

        timer = threading.Timer(self._debounce_ms / 1000.0, run_callback)
        timer.daemon = True
        timer.start()
        self._debounce_timers[path_str] = timer

    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.md'):
            self._debounce(Path(event.src_path), self.sync_file)

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.md'):
            self._debounce(Path(event.src_path), self.sync_file)

    def on_deleted(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.md'):
            self._debounce(Path(event.src_path), self.sync_delete)

    async def sync_file(self, path: Path):
        """Read wiki file, parse metadata, upsert to DB."""
        try:
            if not path.exists():
                return

            content = path.read_text(encoding='utf-8')
            metadata = self._parse_frontmatter(content)

            # Determine category from path or frontmatter
            category = self._infer_category(path, metadata.get('category', 'concept'))

            slug = metadata.get('slug', path.stem)
            title = metadata.get('title', path.stem.replace('-', ' ').title())

            page = WikiPage(
                slug=slug,
                title=title,
                category=category,
                file_path=str(path),
                tags=self._parse_list(metadata.get('tags', '[]')),
                sources=self._parse_list(metadata.get('sources', '[]')),
                outbound_links=self._extract_wikilinks(content),
            )

            await self.store.upsert_page(page, content)

        except Exception as e:
            print(f"[WikiWatcher] Error processing {path}: {e}")

    async def sync_delete(self, path: Path):
        """Remove from DB."""
        try:
            # Try to get slug from frontmatter before deletion
            if path.exists():
                content = path.read_text(encoding='utf-8')
                metadata = self._parse_frontmatter(content)
                slug = metadata.get('slug', path.stem)
            else:
                slug = path.stem
            await self.store.delete_page(slug)
        except Exception as e:
            print(f"[WikiWatcher] Error deleting {path}: {e}")

    def _parse_frontmatter(self, content: str) -> dict:
        """Parse YAML frontmatter (simple key-value only)."""
        if not content.startswith('---'):
            return {}
        try:
            parts = content.split('---', 2)
            if len(parts) >= 2:
                yaml_str = parts[1].strip()
                meta = {}
                for line in yaml_str.split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        meta[k.strip()] = v.strip().strip("'\"")
                return meta
        except Exception:
            pass
        return {}

    def _parse_list(self, value: str) -> list:
        """Parse a JSON list string."""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []

    def _extract_wikilinks(self, content: str) -> list[str]:
        """Extract [[wikilinks]] from content."""
        import re
        return re.findall(r'\[\[([^\]]+)\]\]', content)

    def _infer_category(self, path: Path, frontmatter_cat: str) -> WikiCategory:
        """Infer category from directory structure or frontmatter."""
        cat_mapping = {
            'entity': WikiCategory.ENTITY,
            'concept': WikiCategory.CONCEPT,
            'analysis': WikiCategory.ANALYSIS,
            'source': WikiCategory.SOURCE,
        }
        # Only trust frontmatter if it's a non-default value
        if frontmatter_cat in cat_mapping and frontmatter_cat != 'concept':
            return cat_mapping[frontmatter_cat]

        # Fallback: infer from directory
        path_str = str(path).lower()
        if '/entities' in path_str:
            return WikiCategory.ENTITY
        elif '/concepts' in path_str:
            return WikiCategory.CONCEPT
        elif '/analyses' in path_str:
            return WikiCategory.ANALYSIS
        elif '/sources' in path_str:
            return WikiCategory.SOURCE
        return WikiCategory.CONCEPT


class WatcherManager:
    """Manages background Observer threads for raw/ and wiki/ directories."""

    def __init__(
        self,
        store: Store,
        raw_dir: Path,
        wiki_dir: Path,
        settings_obj: Optional[Settings] = None,
    ):
        self.store = store
        self.raw_dir = raw_dir
        self.wiki_dir = wiki_dir
        self.cfg = settings_obj or settings

        self.raw_observer = Observer()
        self.wiki_observer = Observer()

        self.wiki_handler = WikiFileHandler(
            store, wiki_dir, self.cfg.watcher_debounce_ms
        )

        # Wiki watcher: sync wiki pages to DB
        self.wiki_observer.schedule(
            self.wiki_handler, str(wiki_dir), recursive=True
        )

        # Raw watcher: we don't auto-process raw files, they trigger via API ingest
        # But we could add a handler here if needed in the future

    def start(self):
        self.wiki_observer.start()
        print(f"[Watcher] Started monitoring wiki: {self.wiki_dir}")

    def stop(self):
        self.wiki_observer.stop()
        self.wiki_observer.join()
        print("[Watcher] Stopped")
