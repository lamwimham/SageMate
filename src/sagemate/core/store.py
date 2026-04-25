"""
SQLite FTS5 Storage Engine for the Wiki Layer.

Handles persistence, search, and metadata indexing for LLM-generated wiki pages.
Files are the source of truth; this store is a read-optimized index.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiosqlite
import jieba
import logging

logger = logging.getLogger(__name__)

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
    """Compute a content hash for deduplication.
    
    NOTE: We use MD5 (not SHA-256) because it is sufficient for content
    deduplication and keeps backward compatibility with existing DB records.
    Changing the algorithm would break dedup for all previously ingested sources.
    """
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _word_count(text: str) -> int:
    """Count words in a language-aware way.
    For CJK text, counts individual characters as words.
    For English/Latin text, counts space-separated tokens.
    """
    if not text:
        return 0
    # Simple heuristic: if text contains CJK characters, count chars
    # Otherwise count space-separated words
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in text)
    if has_cjk:
        return len(text.replace(" ", "").replace("\n", ""))
    return len(text.split())


def _safe_json_loads(value, default=None):
    """Safely deserialize a JSON string, returning default on failure."""
    try:
        return json.loads(value or "[]")
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def _category_value(category):
    """Normalize a WikiCategory enum or string to its string value."""
    return category.value if isinstance(category, WikiCategory) else category


def _generate_summary(content: str, max_chars: int = 150) -> str:
    """
    Generate a summary from page content.
    Strategy: take the first meaningful paragraph (skip frontmatter, headings).
    """
    # Strip YAML frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].lstrip()

    # Strip markdown headings and blank lines at the start
    lines = content.split("\n")
    text_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        text_lines.append(stripped)
        if len(text_lines) >= 3:  # Take first 3 non-heading lines
            break

    summary = " ".join(text_lines)
    # Truncate by character count (language-aware)
    if len(summary) > max_chars:
        summary = summary[:max_chars] + "..."
    return summary


def _tokenize(text: str) -> str:
    """
    Tokenize text using Jieba for FTS5 indexing.
    Handles Chinese and English seamlessly:
    - Chinese characters are segmented into words.
    - English words are kept intact.
    - Returns space-separated tokens.
    """
    # jieba.lcut handles mixed Chinese/English well.
    # It splits Chinese into words, keeps English words intact.
    tokens = jieba.lcut(text)
    # Filter out very short tokens (punctuation, single chars) to reduce noise
    filtered = [t for t in tokens if len(t.strip()) > 1]
    return " ".join(filtered)


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
                summary TEXT DEFAULT '',
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
            await db.execute("ALTER TABLE pages ADD COLUMN source_pages TEXT DEFAULT '[]'")
            await db.commit()

        try:
            await db.execute("SELECT summary FROM pages LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE pages ADD COLUMN summary TEXT DEFAULT ''")
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
                error TEXT,
                content_hash,
                source_url
            )
        """)

        # Migration: add content_hash and source_url columns if missing
        try:
            await db.execute("ALTER TABLE sources ADD COLUMN content_hash")
        except Exception:
            pass  # Column already exists
        try:
            await db.execute("ALTER TABLE sources ADD COLUMN source_url")
        except Exception:
            pass  # Column already exists

        # Compile pipeline tasks (persistent, survives app restarts)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS compile_tasks (
                task_id TEXT PRIMARY KEY,
                source_slug TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                step INTEGER DEFAULT 0,
                total_steps INTEGER DEFAULT 6,
                message TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT,
                result_json TEXT,
                error TEXT,
                FOREIGN KEY (source_slug) REFERENCES sources(slug)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_compile_tasks_status ON compile_tasks(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_compile_tasks_source ON compile_tasks(source_slug)")

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

        # App settings table (key-value store for persistent configuration)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)

        # Projects table (multi-project support)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                root_path TEXT,
                wiki_dir_name TEXT,
                assets_dir_name TEXT,
                status TEXT DEFAULT 'inactive',
                created_at TEXT,
                updated_at TEXT
            )
        """)

    # ── Wiki Page CRUD ─────────────────────────────────────────

    async def upsert_page(self, page: WikiPage, content: str, searchable_content: str = "", commit: bool = True):
        """Insert or update a wiki page and its search index.
        
        Args:
            searchable_content: Optional pre-processed content for FTS indexing.
                If provided, used instead of full content for search index.
            commit: If True (default), commits the transaction immediately.
                Set to False when calling from a batch operation to commit once at the end.
        """
        db = self._db
        assert db is not None

        chash = _content_hash(content)
        wc = await asyncio.to_thread(_word_count, content)

        # Auto-generate summary if not provided
        summary = page.summary
        if not summary and content:
            summary = await asyncio.to_thread(_generate_summary, content)

        await db.execute("""
            INSERT INTO pages (slug, title, category, file_path, created_at, updated_at,
                               word_count, content_hash, summary, inbound_links, outbound_links, tags, sources, source_pages)
            VALUES (:slug, :title, :category, :file_path, :created_at, :updated_at,
                    :word_count, :content_hash, :summary, :inbound_links, :outbound_links, :tags, :sources, :source_pages)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                category = excluded.category,
                file_path = excluded.file_path,
                updated_at = excluded.updated_at,
                word_count = excluded.word_count,
                content_hash = excluded.content_hash,
                summary = excluded.summary,
                inbound_links = excluded.inbound_links,
                outbound_links = excluded.outbound_links,
                tags = excluded.tags,
                sources = excluded.sources,
                source_pages = excluded.source_pages
        """, {
            "slug": page.slug,
            "title": page.title,
            "category": _category_value(page.category),
            "file_path": str(page.file_path),
            "created_at": page.created_at.isoformat(),
            "updated_at": page.updated_at.isoformat(),
            "word_count": wc,
            "content_hash": chash,
            "summary": summary,
            "inbound_links": json.dumps(page.inbound_links),
            "outbound_links": json.dumps(page.outbound_links),
            "tags": json.dumps(page.tags),
            "sources": json.dumps(page.sources),
            "source_pages": json.dumps(page.source_pages),
        })

        # Update FTS: FTS5 tables use an implicit rowid. Without explicit rowid management,
        # INSERT OR REPLACE acts like an append. We must DELETE old entries first to avoid duplicates.
        await db.execute("DELETE FROM search_idx WHERE slug = ?", [page.slug])
        
        # Tokenize content for Chinese search support.
        # Use searchable_content if provided (e.g. frontmatter-stripped), otherwise full content.
        fts_source = searchable_content if searchable_content else content
        tokenized_content = await asyncio.to_thread(_tokenize, fts_source)
        
        await db.execute("""
            INSERT INTO search_idx (slug, title, content, category)
            VALUES (:slug, :title, :content, :category)
        """, {
            "slug": page.slug,
            "title": page.title,
            "content": tokenized_content,
            "category": _category_value(page.category),
        })

        if commit:
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
            await self.upsert_page(page, content, commit=False)
        db = self._db
        assert db is not None
        await db.commit()

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

        cursor = await db.execute("SELECT * FROM pages WHERE slug = ?", (slug,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        for json_field in ["inbound_links", "outbound_links", "tags", "sources", "source_pages"]:
            d[json_field] = _safe_json_loads(d.get(json_field))
        return WikiPage(**d)


    async def list_pages(self, category: Optional[WikiCategory] = None) -> List[WikiPage]:
        db = self._db
        assert db is not None

        query = "SELECT * FROM pages ORDER BY updated_at DESC"
        params: list = []
        if category:
            query = "SELECT * FROM pages WHERE category = ? ORDER BY updated_at DESC"
            params = [_category_value(category)]

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for json_field in ["inbound_links", "outbound_links", "tags", "sources", "source_pages"]:
                d[json_field] = _safe_json_loads(d.get(json_field))
            result.append(WikiPage(**d))

        return result

    # ── Search ─────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 10, category: Optional[WikiCategory] = None) -> List[SearchResult]:
        db = self._db
        assert db is not None

        # Detect Chinese characters
        has_chinese = bool(re.search(r'[\u4e00-\u9fa5]', query))
        
        # FTS5 query formatting: sanitize slightly to avoid parser crashes on weird input
        safe_query = query.replace('"', '').replace(':', '').replace('(', '').replace(')', '').strip()
        if not safe_query:
            return []

        # For Chinese queries, use Jieba tokenization for FTS5
        if has_chinese:
            return await self._search_fts5_jieba(safe_query, limit, category)

        try:
            if category:
                cat_val = _category_value(category)
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
            return await self._search_like(safe_query, limit, category)

    async def _search_fts5_jieba(self, query: str, limit: int = 10, category: Optional[WikiCategory] = None) -> List[SearchResult]:
        """
        FTS5 search with Jieba tokenization for Chinese text.
        Tokenizes query into keywords and joins with OR logic.
        """
        db = self._db
        assert db is not None
        
        # Tokenize query (offload to thread to avoid blocking event loop)
        tokens = await asyncio.to_thread(jieba.lcut, query)
        # Filter out noise and build FTS5 OR query
        keywords = [t for t in tokens if len(t.strip()) > 1]
        if not keywords:
            return []
            
        # Build FTS5 MATCH expression: "word1 OR word2 OR word3"
        fts_query = " OR ".join(keywords)
        
        try:
            if category:
                cat_val = _category_value(category)
                sql = """
                    SELECT slug, title, category,
                           snippet(search_idx, 2, '<b>', '</b>', '...', 20) as snippet,
                           rank
                    FROM search_idx
                    WHERE search_idx MATCH ? AND category = ?
                    ORDER BY rank
                    LIMIT ?
                """
                params = (fts_query, cat_val, limit)
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
                params = (fts_query, limit)

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
            logger.warning(f"[Store] Jieba FTS5 search failed for '{query}': {e}")
            return await self._search_like(query, limit, category)

    async def _search_like(self, query: str, limit: int = 10, category: Optional[WikiCategory] = None) -> List[SearchResult]:
        """Fallback search using LIKE for Chinese or FTS5 failures."""
        db = self._db
        assert db is not None
        
        like_query = f"%{query}%"
        if category:
            cat_val = _category_value(category)
            sql = """SELECT slug, title, category, content_hash FROM pages 
                     WHERE (title LIKE ? OR slug LIKE ?) AND category = ? LIMIT ?"""
            cursor = await db.execute(sql, (like_query, like_query, cat_val, limit))
        else:
            sql = """SELECT slug, title, category, content_hash FROM pages 
                     WHERE title LIKE ? OR slug LIKE ? LIMIT ?"""
            cursor = await db.execute(sql, (like_query, like_query, limit))
        
        rows = await cursor.fetchall()
        return [
            SearchResult(
                slug=r["slug"],
                title=r["title"],
                category=WikiCategory(r["category"]) if r["category"] in [c.value for c in WikiCategory] else WikiCategory.CONCEPT,
                snippet=f"(匹配关键词: {query})",
                score=0.0,
            )
            for r in rows
        ]

    # ── Source Tracking ────────────────────────────────────────

    async def upsert_source(self, slug: str, title: str, file_path: str,
                            source_type: str = "unknown", status: str = "pending",
                            wiki_pages: list[str] | None = None, error: str | None = None,
                            content_hash: str | None = None, source_url: str | None = None):

        db = self._db
        assert db is not None
        await db.execute("""
            INSERT INTO sources (slug, title, file_path, source_type, ingested_at, wiki_pages, status, error, content_hash, source_url)
            VALUES (:slug, :title, :file_path, :source_type, :ingested_at, :wiki_pages, :status, :error, :content_hash, :source_url)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                file_path = excluded.file_path,
                source_type = excluded.source_type,
                ingested_at = excluded.ingested_at,
                wiki_pages = excluded.wiki_pages,
                status = excluded.status,
                error = excluded.error,
                content_hash = excluded.content_hash,
                source_url = excluded.source_url
        """, {
            "slug": slug,
            "title": title,
            "file_path": file_path,
            "source_type": source_type,
            "ingested_at": datetime.now().isoformat(),
            "wiki_pages": json.dumps(wiki_pages or []),
            "status": status,
            "error": error,
            "content_hash": content_hash,
            "source_url": source_url,
        })
        await db.commit()

    async def update_source_status(self, slug: str, status: str):
        """Update only the status field of a source (for ingest progress tracking)."""
        db = self._db
        assert db is not None
        await db.execute(
            "UPDATE sources SET status = ?, ingested_at = ? WHERE slug = ?",
            (status, datetime.now().isoformat(), slug)
        )
        await db.commit()

    async def get_source_by_hash(self, content_hash: str) -> Optional[dict]:
        """Check if a source with the same content hash already exists."""

        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT * FROM sources WHERE content_hash = ?", (content_hash,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["wiki_pages"] = _safe_json_loads(d.get("wiki_pages"))


        return d

    async def get_source_by_url(self, url: str) -> Optional[dict]:
        """Check if a source from the same URL already exists."""

        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT * FROM sources WHERE source_url = ?", (url,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["wiki_pages"] = _safe_json_loads(d.get("wiki_pages"))


        return d

    async def get_source(self, slug: str) -> Optional[dict]:

        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT * FROM sources WHERE slug = ?", (slug,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["wiki_pages"] = _safe_json_loads(d.get("wiki_pages"))


        return d

    async def list_sources(self) -> list[dict]:
        """List all source documents."""

        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT * FROM sources ORDER BY ingested_at DESC")
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["wiki_pages"] = _safe_json_loads(d.get("wiki_pages"))

            results.append(d)
        return results

    # ── Compile Task CRUD (persistent pipeline tasks) ──────────

    async def create_compile_task(self, task_id: str, source_slug: str) -> None:
        """Create a new compile task record."""

        db = self._db
        assert db is not None
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT INTO compile_tasks (task_id, source_slug, status, step, total_steps, message, created_at, updated_at)
            VALUES (:task_id, :source_slug, 'queued', 0, 6, '任务已创建，等待处理', :created_at, :updated_at)
        """, {"task_id": task_id, "source_slug": source_slug, "created_at": now, "updated_at": now})
        await db.commit()

    async def update_compile_task_status(self, task_id: str, status: str, step: int, message: str) -> None:
        """Update compile task status and progress."""
        db = self._db
        assert db is not None
        await db.execute("""
            UPDATE compile_tasks
            SET status = :status, step = :step, message = :message, updated_at = :updated_at
            WHERE task_id = :task_id
        """, {"task_id": task_id, "status": status, "step": step, "message": message, "updated_at": datetime.now().isoformat()})
        await db.commit()

    async def set_compile_task_result(self, task_id: str, result: dict) -> None:
        """Mark compile task as completed with result."""

        db = self._db
        assert db is not None
        await db.execute("""
            UPDATE compile_tasks
            SET status = 'completed', step = total_steps, result_json = :result_json, updated_at = :updated_at
            WHERE task_id = :task_id
        """, {"task_id": task_id, "result_json": json.dumps(result), "updated_at": datetime.now().isoformat()})
        await db.commit()

    async def set_compile_task_error(self, task_id: str, error: str) -> None:
        """Mark compile task as failed."""
        db = self._db
        assert db is not None
        await db.execute("""
            UPDATE compile_tasks
            SET status = 'failed', error = :error, updated_at = :updated_at
            WHERE task_id = :task_id
        """, {"task_id": task_id, "error": error, "updated_at": datetime.now().isoformat()})
        await db.commit()

    async def get_compile_task(self, task_id: str) -> Optional[dict]:
        """Get a compile task by id."""

        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT * FROM compile_tasks WHERE task_id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("result_json"):
            d["result"] = _safe_json_loads(d["result_json"])
        return d


    async def list_unfinished_compile_tasks(self) -> list[dict]:
        """List all compile tasks that are not completed or failed."""

        db = self._db
        assert db is not None
        cursor = await db.execute("""
            SELECT t.*, s.title as source_title
            FROM compile_tasks t
            JOIN sources s ON t.source_slug = s.slug
            WHERE t.status NOT IN ('completed', 'failed')
            ORDER BY t.created_at DESC
        """)
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("result_json"):
                d["result"] = _safe_json_loads(d["result_json"])
            results.append(d)

        return results

    async def list_compile_tasks(self, limit: int = 50) -> list[dict]:
        """List recent compile tasks (all statuses)."""

        db = self._db
        assert db is not None
        cursor = await db.execute("""
            SELECT t.*, s.title as source_title
            FROM compile_tasks t
            JOIN sources s ON t.source_slug = s.slug
            ORDER BY t.created_at DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("result_json"):
                d["result"] = _safe_json_loads(d["result_json"])
            results.append(d)

        return results

    # ── Index.md and Log.md helpers ────────────────────────────

    async def build_index_entries(self) -> list[IndexEntry]:
        """Build index entries from all wiki pages."""
        pages = await self.list_pages()

        entries = []
        for p in pages:
            inbound_links = _safe_json_loads(p.inbound_links) if isinstance(p.inbound_links, str) else (p.inbound_links or [])
            inbound = len(inbound_links)
            entries.append(IndexEntry(
                slug=p.slug,
                title=p.title,
                category=_category_value(p.category) if isinstance(p.category, (WikiCategory, str)) else WikiCategory(p.category),
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

    # ── Settings (Key-Value Store) ─────────────────────────────

    async def set_setting(self, key: str, value: str):
        """Upsert a setting in app_settings table."""
        db = self._db
        assert db is not None
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (:key, :value, :updated_at)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, {"key": key, "value": value, "updated_at": now})
        await db.commit()

    async def get_setting(self, key: str) -> Optional[str]:
        """Get a single setting value."""
        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def get_all_settings(self) -> dict[str, str]:
        """Get all settings as a dict."""
        db = self._db
        assert db is not None
        cursor = await db.execute("SELECT key, value FROM app_settings")
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}

    async def delete_setting(self, key: str):
        """Delete a single setting."""
        db = self._db
        assert db is not None
        await db.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        await db.commit()

    # ── Projects ───────────────────────────────────────────────

    async def create_project(self, project):
        """Create a new project."""
        db = self._db
        assert db is not None
        await db.execute("""
            INSERT INTO projects (id, name, root_path, wiki_dir_name, assets_dir_name, status, created_at, updated_at)
            VALUES (:id, :name, :root_path, :wiki_dir_name, :assets_dir_name, :status, :created_at, :updated_at)
        """, {
            "id": project.id,
            "name": project.name,
            "root_path": project.root_path,
            "wiki_dir_name": project.wiki_dir_name,
            "assets_dir_name": project.assets_dir_name,
            "status": project.status.value if hasattr(project.status, 'value') else str(project.status),
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        })
        await db.commit()

    async def get_project(self, project_id: str):
        """Get a project by ID."""
        db = self._db
        assert db is not None
        from ..models import Project, ProjectStatus
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        return Project(**d)

    async def list_projects(self):
        """List all projects."""
        db = self._db
        assert db is not None
        from ..models import Project, ProjectStatus
        cursor = await db.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [Project(**dict(r)) for r in rows]

    async def update_project(self, project_id: str, **kwargs):
        """Update project fields. Returns updated project or None."""
        db = self._db
        assert db is not None
        from ..models import Project
        # Build SET clause
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self.get_project(project_id)
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        await db.execute(f"UPDATE projects SET {set_clause} WHERE id = :id",
                         {"id": project_id, **updates})
        await db.commit()
        return await self.get_project(project_id)

    async def activate_project(self, project_id: str):
        """Set a project as active (deactivate all others)."""
        db = self._db
        assert db is not None
        await db.execute("UPDATE projects SET status = 'inactive'")
        await db.execute("UPDATE projects SET status = 'active', updated_at = ? WHERE id = ?",
                         (datetime.now().isoformat(), project_id))
        await db.commit()
        return await self.get_project(project_id)

    async def delete_project(self, project_id: str):
        """Delete a project."""
        db = self._db
        assert db is not None
        await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()

    async def get_active_project(self):
        """Get the currently active project."""
        db = self._db
        assert db is not None
        from ..models import Project
        cursor = await db.execute("SELECT * FROM projects WHERE status = 'active' LIMIT 1")
        row = await cursor.fetchone()
        if not row:
            return None
        return Project(**dict(row))

    # ── Schema Introspection ───────────────────────────────────

    async def get_schema(self) -> dict:
        """Return full database schema (tables + DDL) for display in Settings."""
        db = self._db
        assert db is not None
        # Get all tables
        cursor = await db.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name"
        )
        rows = await cursor.fetchall()
        tables = {}
        for row in rows:
            tables[row["name"]] = {
                "type": row["type"],
                "ddl": row["sql"],
            }

        # Get column details for each table
        for table_name in tables:
            cursor = await db.execute(f"PRAGMA table_info({table_name})")
            cols = await cursor.fetchall()
            tables[table_name]["columns"] = [
                {
                    "cid": c["cid"],
                    "name": c["name"],
                    "type": c["type"],
                    "notnull": bool(c["notnull"]),
                    "default": c["dflt_value"],
                    "pk": bool(c["pk"]),
                }
                for c in cols
            ]

        # Get row counts
        for table_name in tables:
            cursor = await db.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
            row = await cursor.fetchone()
            tables[table_name]["row_count"] = row["cnt"]

        return tables

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


