"""
SQLite FTS5 Storage Engine for the Wiki Layer.

Handles persistence, search, and metadata indexing for LLM-generated wiki pages.
Files are the source of truth; this store is a read-optimized index.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiosqlite

from ..models import (
    IndexEntry,
    LogEntry,
    LogEntryType,
    SearchResult,
    WikiCategory,
    WikiPage,
    WikiPageCreate,
    WikiPageUpdate,
)


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _word_count(text: str) -> int:
    return len(text.split())


class Store:
    """
    Wrapper around SQLite for wiki metadata and FTS5 search.
    Designed for Local First: Files are the source of truth,
    this store is a read-optimized index.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._db: Optional[aiosqlite.Connection] = None

    # ── Lifecycle ──────────────────────────────────────────────

    async def connect(self):
        """Initialize DB and create tables if not exists."""
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.execute("PRAGMA journal_mode=WAL;")
            await self._db.execute("PRAGMA foreign_keys=ON;")
            await self.init_schema()
            await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    async def init_schema(self):
        """Create tables and FTS5 index. Idempotent."""
        db = self._db
        assert db is not None

        # Wiki pages metadata table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'concept',
                file_path TEXT UNIQUE NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                word_count INTEGER DEFAULT 0,
                content_hash TEXT,
                inbound_links TEXT DEFAULT '[]',
                outbound_links TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                sources TEXT DEFAULT '[]'
            )
        """)
        
        # ── Auto-Migration ───────────────────────────────────────
        # Automatically add new columns if they are missing
        try:
            await db.execute("SELECT source_pages FROM pages LIMIT 1")
        except Exception:
            # Column missing, add it
            await db.execute("ALTER TABLE pages ADD COLUMN source_pages TEXT DEFAULT '[]'")
            await db.commit()

        # Source documents table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                file_path TEXT UNIQUE NOT NULL,
                source_type TEXT DEFAULT 'unknown',
                ingested_at TEXT,
                wiki_pages TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending',
                error TEXT
            )
        """)

        # FTS5 Virtual Table for full-text search across wiki pages
        # Standalone (not external content) to avoid rowid mapping issues
        await db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_idx USING fts5(
                slug,
                title,
                content,
                category,
                tokenize='porter unicode61 remove_diacritics 2'
            )
        """)

    # ── Wiki Page CRUD ─────────────────────────────────────────

    async def upsert_page(self, page: WikiPage, content: str):
        """Insert or update a wiki page and its search index."""
        db = self._db
        assert db is not None

        import json

        chash = _content_hash(content)
        wc = _word_count(content)

        await db.execute("""
            INSERT INTO pages (slug, title, category, file_path, created_at, updated_at,
                               word_count, content_hash, inbound_links, outbound_links, tags, sources, source_pages)
            VALUES (:slug, :title, :category, :file_path, :created_at, :updated_at,
                    :word_count, :content_hash, :inbound_links, :outbound_links, :tags, :sources, :source_pages)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                category = excluded.category,
                file_path = excluded.file_path,
                updated_at = excluded.updated_at,
                word_count = excluded.word_count,
                content_hash = excluded.content_hash,
                inbound_links = excluded.inbound_links,
                outbound_links = excluded.outbound_links,
                tags = excluded.tags,
                sources = excluded.sources,
                source_pages = excluded.source_pages
        """, {
            "slug": page.slug,
            "title": page.title,
            "category": page.category.value if isinstance(page.category, WikiCategory) else page.category,
            "file_path": str(page.file_path),
            "created_at": page.created_at.isoformat(),
            "updated_at": page.updated_at.isoformat(),
            "word_count": wc,
            "content_hash": chash,
            "inbound_links": json.dumps(page.inbound_links),
            "outbound_links": json.dumps(page.outbound_links),
            "tags": json.dumps(page.tags),
            "sources": json.dumps(page.sources),
            "source_pages": json.dumps(page.source_pages),
        })

        # Update FTS: FTS5 tables use an implicit rowid. Without explicit rowid management,
        # INSERT OR REPLACE acts like an append. We must DELETE old entries first to avoid duplicates.
        await db.execute("DELETE FROM search_idx WHERE slug = ?", [page.slug])
        await db.execute("""
            INSERT INTO search_idx (slug, title, content, category)
            VALUES (:slug, :title, :content, :category)
        """, {
            "slug": page.slug,
            "title": page.title,
            "content": content,
            "category": page.category.value if isinstance(page.category, WikiCategory) else page.category,
        })

        await db.commit()

    async def create_pages_batch(self, pages: list[WikiPageCreate], contents: dict[str, str]):
        """Create multiple wiki pages in a single transaction."""
        for pc in pages:
            content = contents.get(pc.slug, pc.content)
            file_path = str(pc.file_path) if hasattr(pc, 'file_path') and pc.file_path else ""
            page = WikiPage(
                slug=pc.slug,
                title=pc.title,
                category=pc.category,
                file_path=file_path,
                content=content,
                tags=pc.tags,
                sources=pc.sources,
                outbound_links=pc.outbound_links,
            )
            await self.upsert_page(page, content)

    async def update_page(self, update: WikiPageUpdate, content: str):
        """Apply an incremental update to a wiki page."""
        existing = await self.get_page(update.slug)
        if not existing:
            raise ValueError(f"Page not found: {update.slug}")

        if update.title:
            existing.title = update.title

        await self.upsert_page(existing, content)

    async def delete_page(self, slug: str):
        db = self._db
        assert db is not None
        await db.execute("DELETE FROM pages WHERE slug = ?", (slug,))
        await db.execute("DELETE FROM search_idx WHERE slug = ?", (slug,))
        await db.commit()

    async def get_page(self, slug: str) -> Optional[WikiPage]:
        db = self._db
        assert db is not None
        import json
        cursor = await db.execute("SELECT * FROM pages WHERE slug = ?", (slug,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        for json_field in ["inbound_links", "outbound_links", "tags", "sources", "source_pages"]:
            try:
                d[json_field] = json.loads(d.get(json_field) or "[]")
            except (json.JSONDecodeError, TypeError):
                d[json_field] = []
        return WikiPage(**d)

    async def list_pages(self, category: Optional[WikiCategory] = None) -> List[WikiPage]:
        db = self._db
        assert db is not None
        import json

        query = "SELECT * FROM pages ORDER BY updated_at DESC"
        params: list = []
        if category:
            query = "SELECT * FROM pages WHERE category = ? ORDER BY updated_at DESC"
            params = [category.value if isinstance(category, WikiCategory) else category]

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for json_field in ["inbound_links", "outbound_links", "tags", "sources", "source_pages"]:
                try:
                    d[json_field] = json.loads(d.get(json_field) or "[]")
                except (json.JSONDecodeError, TypeError):
                    d[json_field] = []
            result.append(WikiPage(**d))
        return result

    # ── Search ─────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 10, category: Optional[WikiCategory] = None) -> List[SearchResult]:
        db = self._db
        assert db is not None

        # FTS5 query formatting: sanitize slightly to avoid parser crashes on weird input
        # Remove FTS5 special chars that might cause "no such column" errors
        safe_query = query.replace('"', '').replace(':', '').replace('(', '').replace(')', '').strip()
        if not safe_query:
            return []

        try:
            if category:
                cat_val = category.value if isinstance(category, WikiCategory) else category
                sql = """
                    SELECT slug, title, category,
                           snippet(search_idx, 2, '<b>', '</b>', '...', 20) as snippet,
                           rank
                    FROM search_idx
                    WHERE search_idx MATCH ? AND category = ?
                    ORDER BY rank
                    LIMIT ?
                """
                params = (safe_query, cat_val, limit)
            else:
                sql = """
                    SELECT slug, title, category,
                           snippet(search_idx, 2, '<b>', '</b>', '...', 20) as snippet,
                           rank
                    FROM search_idx
                    WHERE search_idx MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """
                params = (safe_query, limit)

            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            return [
                SearchResult(
                    slug=r["slug"],
                    title=r["title"],
                    category=WikiCategory(r["category"]) if r["category"] in [c.value for c in WikiCategory] else WikiCategory.CONCEPT,
                    snippet=r["snippet"],
                    score=r["rank"],
                )
                for r in rows
            ]
        except Exception as e:
            print(f"[Store] FTS5 search failed for '{query}': {e}")
            # Fallback to simple LIKE search if FTS5 fails
            like_query = f"%{safe_query}%"
            # The `pages` table doesn't store content, so we match on title and return a generic snippet.
            # If category filter is provided:
            if category:
                cat_val = category.value if isinstance(category, WikiCategory) else category
                sql = "SELECT slug, title, category FROM pages WHERE title LIKE ? AND category = ? LIMIT ?"
                cursor = await db.execute(sql, (like_query, cat_val, limit))
            else:
                sql = "SELECT slug, title, category FROM pages WHERE title LIKE ? LIMIT ?"
                cursor = await db.execute(sql, (like_query, limit))
            
            rows = await cursor.fetchall()
            return [
                SearchResult(
                    slug=r["slug"],
                    title=r["title"],
                    category=WikiCategory(r["category"]) if r["category"] in [c.value for c in WikiCategory] else WikiCategory.CONCEPT,
                    snippet=r["content"][:100] + "...",
                    score=0.0,
                )
                for r in rows
            ]

    # ── Source Tracking ────────────────────────────────────────

    async def upsert_source(self, slug: str, title: str, file_path: str,
                            source_type: str = "unknown", status: str = "pending",
                            wiki_pages: list[str] | None = None, error: str | None = None):
        import json
        db = self._db
        assert db is not None
        await db.execute("""
            INSERT INTO sources (slug, title, file_path, source_type, ingested_at, wiki_pages, status, error)
            VALUES (:slug, :title, :file_path, :source_type, :ingested_at, :wiki_pages, :status, :error)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                ingested_at = excluded.ingested_at,
                wiki_pages = excluded.wiki_pages,
                status = excluded.status,
                error = excluded.error
        """, {
            "slug": slug,
            "title": title,
            "file_path": file_path,
            "source_type": source_type,
            "ingested_at": datetime.now().isoformat(),
            "wiki_pages": json.dumps(wiki_pages or []),
            "status": status,
            "error": error,
        })
        await db.commit()

    async def get_source(self, slug: str) -> Optional[dict]:
        import json
        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT * FROM sources WHERE slug = ?", (slug,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["wiki_pages"] = json.loads(d.get("wiki_pages") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["wiki_pages"] = []
        return d

    # ── Index.md and Log.md helpers ────────────────────────────

    async def build_index_entries(self) -> list[IndexEntry]:
        """Build index entries from all wiki pages."""
        pages = await self.list_pages()
        import json
        entries = []
        for p in pages:
            try:
                inbound = len(json.loads(p.inbound_links) if isinstance(p.inbound_links, str) else (p.inbound_links or []))
            except (json.JSONDecodeError, TypeError):
                inbound = 0
            entries.append(IndexEntry(
                slug=p.slug,
                title=p.title,
                category=p.category if isinstance(p.category, WikiCategory) else WikiCategory(p.category),
                last_updated=p.updated_at,
                source_count=len(p.sources) if isinstance(p.sources, list) else 0,
                inbound_count=inbound,
            ))
        return entries

    async def append_log(self, entry: LogEntry):
        """Append a log entry to the log.md file and track in DB."""
        # We don't store log entries in SQLite (they're in log.md),
        # but this method provides a hook for the Watcher to sync if needed.
        pass

    # ── Stats ──────────────────────────────────────────────────

    async def stats(self) -> dict:
        """Return wiki statistics."""
        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM pages")
        row = await cursor.fetchone()
        page_count = row["cnt"]

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM sources")
        row = await cursor.fetchone()
        source_count = row["cnt"]

        cursor = await db.execute("SELECT category, COUNT(*) as cnt FROM pages GROUP BY category")
        rows = await cursor.fetchall()
        by_category = {r["category"]: r["cnt"] for r in rows}

        return {
            "wiki_pages": page_count,
            "sources": source_count,
            "by_category": by_category,
        }
