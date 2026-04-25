"""FastAPI Application Entry Point — SageMate Core v0.2"""

from __future__ import annotations

import os
import asyncio
import tempfile
import logging
from typing import Optional
from pathlib import Path
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import uuid
import json

from ..core.config import settings, url_collector_settings
from ..core.store import Store
from ..core.watcher import WatcherManager
from ..core.agent import AgentPipeline, AgentMessage, AgentResponse
from ..models import (
    AppSettings,
    GenericResponse,
    HealthResponse,
    IngestResult,
    IngestTaskState,
    IngestTaskStatus,
    LintReport,
    LintTrigger,
    PageDetailResponse,
    Project,
    ProjectCreate,
    ProjectStatus,
    ProjectUpdate,
    QueryRequest,
    QueryResponse,
    SearchResult,
    SettingsUpdate,
    WikiCategory,
    WikiPage,
    WikiPageCreate,
)
from ..ingest.compiler.compiler import IncrementalCompiler, LLMClient
from ..system.lint import LintEngine
from ..ingest.adapters.file_parser import DeterministicParser
from ..ingest.adapters.archive_helper import ArchiveHelper
from ..ingest.adapters.file_validator import FileTypeValidator, FileValidationError
from ..core.slug import SlugGenerator
from ..core.event_bus import EventBus
from ..ingest.task_manager import IngestTaskManager
from ..doctor import Doctor
from ..plugins.wechat.channel import WechatChannel
from ..plugins.wechat.service import WeChatService
from .dependencies import register_components
from .routers import wechat as wechat_router
import httpx

# ── Service Instances ────────────────────────────────────────
wechat_service: Optional[WeChatService] = None

# ── Runtime Path Overrides ───────────────────────────────────
_runtime_raw_dir: Optional[Path] = None  # Overrides settings.raw_dir when set via Settings UI


async def get_project_context() -> dict:
    """Return raw_dir and wiki_dir based on the active project.
    Falls back to global settings if no project is active.
    """
    active = await store.get_active_project()
    if active:
        root = Path(active.root_path)
        wiki_dir = root / active.wiki_dir_name
        assets_dir = wiki_dir / active.assets_dir_name
        return {
            "project": active,
            "raw_dir": root,
            "wiki_dir": wiki_dir,
            "assets_dir": assets_dir,
        }
    return {
        "project": None,
        "raw_dir": _runtime_raw_dir or settings.raw_dir,
        "wiki_dir": settings.wiki_dir,
        "assets_dir": settings.wiki_dir / "assets",
    }


def get_effective_raw_dir() -> Path:
    """Return the effective raw directory, respecting runtime overrides."""
    return _runtime_raw_dir or settings.raw_dir

# ── Startup Doctor Check ───────────────────────────────────────
if not Doctor.run():
    import sys
    sys.exit(1)

settings.ensure_dirs()

# ── Global Components ───────────────────────────────────────────
store = Store(str(settings.db_path))
watcher = WatcherManager(store, settings.raw_dir, settings.wiki_dir, settings)
compiler = IncrementalCompiler(store, settings.wiki_dir, LLMClient(), settings)
lint_engine = LintEngine(store, settings.wiki_dir, settings)

# Cron & Cost Monitor (optional — may not be configured)
try:
    from ..system.cron_scheduler import CronScheduler
    from ..system.cost_monitor import CostMonitor
    cron = CronScheduler(compiler, lint_engine, settings)
    cost_monitor = CostMonitor()
except Exception:
    cron = None
    cost_monitor = None

# ── Event Bus (pub-sub for decoupled progress notifications) ─
event_bus = EventBus()

# ── Ingest Task Manager (Async + SSE via EventBus) ───────────
ingest_tasks = IngestTaskManager(event_bus=event_bus, store=store)

# ── Core Agent Pipeline (shared by all channels) ─────────────
agent_pipeline = AgentPipeline(store, settings, ingest_service=ingest_tasks)

# ── WeChat Channel (initialized after AgentPipeline) ───────────
wechat_channel = WechatChannel(agent_pipeline=agent_pipeline)
wechat_service = WeChatService(wechat_channel.client, wechat_channel.auth)

# ── Settings Snapshots (for reset) ─────────────────────────────
_initial_settings = settings.model_copy()
_initial_url_settings = url_collector_settings.model_copy()

# ── Templates Setup ─────────────────────────────────────────────
# Locate templates directory relative to this file
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "api" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    os.makedirs(settings.raw_dir, exist_ok=True)
    os.makedirs(settings.wiki_dir, exist_ok=True)
    await store.connect()
    watcher.start()
    await _initial_sync()

    # WeChat Channel is a plugin — started on-demand via UI login, not at boot.

    # Load runtime settings overrides from DB
    await reload_settings_from_db()

    # Register components for dependency injection
    register_components(
        store=store,
        watcher=watcher,
        compiler=compiler,
        lint_engine=lint_engine,
        event_bus=event_bus,
        ingest_tasks=ingest_tasks,
        agent_pipeline=agent_pipeline,
        wechat_channel=wechat_channel,
        wechat_service=wechat_service,
    )
    
    yield
    
    # Shutdown
    if cron:
        cron.stop()
    watcher.stop()
    await store.close()


# ── Settings reload helper ───────────────────────────────────

async def reload_settings_from_db():
    """Load runtime setting overrides from SQLite and apply to global config.

    Also re-reads .env file so changes on disk take effect without restart.
    """
    global _initial_settings, _initial_url_settings

    # Re-read .env so changes on disk take effect without restart
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass

    # Refresh snapshots with latest env vars (so "reset to default" uses current .env)
    from ..core.config import Settings, URLCollectorSettings
    _initial_settings = Settings().model_copy()
    _initial_url_settings = URLCollectorSettings().model_copy()

    try:
        overrides = await store.get_all_settings()
    except Exception:
        return  # DB not ready yet

    import json

    def _apply(model, snapshot, prefix: str, mapping: dict):
        for field, target_attr in mapping.items():
            key = f"{prefix}{field}" if prefix else field
            if key in overrides:
                raw = overrides[key]
                # Try JSON parse first, then plain string
                try:
                    val = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    val = raw
                # Convert bool strings
                if isinstance(val, str) and val.lower() in ("true", "false"):
                    val = val.lower() == "true"
                setattr(model, target_attr, val)
            else:
                # Reset to initial default (now reflects latest .env)
                setattr(model, target_attr, getattr(snapshot, target_attr))

    # Main settings
    _apply(settings, _initial_settings, "", {
        "llm_base_url": "llm_base_url",
        "llm_api_key": "llm_api_key",
        "llm_model": "llm_model",
        "vision_base_url": "vision_base_url",
        "vision_api_key": "vision_api_key",
        "vision_model": "vision_model",
        "compiler_max_source_chars": "compiler_max_source_chars",
        "compiler_max_wiki_context_chars": "compiler_max_wiki_context_chars",
        "lint_stale_days": "lint_stale_days",
        "cron_auto_compile_enabled": "cron_auto_compile_enabled",
        "cron_auto_compile_interval": "cron_auto_compile_interval",
        "cron_lint_enabled": "cron_lint_enabled",
        "cron_lint_interval": "cron_lint_interval",
        "watcher_debounce_ms": "watcher_debounce_ms",
    })

    # WeChat plugin settings (stored in DB but not in Settings model — handled separately by WeChatChannel)
    # Removed: WeChat settings are managed by wechat_channel.agent.reinit() below,
    # not by the Settings model which has no wechat_* fields.

    # URL collector settings
    _apply(url_collector_settings, _initial_url_settings, "", {
        "url_tier1_timeout": "tier1_timeout",
        "url_tier2_timeout": "tier2_timeout",
        "url_tier2_network_idle_timeout": "tier2_network_idle_timeout",
        "url_tier2_wait_selector_timeout": "tier2_wait_selector_timeout",
        "url_cache_enabled": "cache_enabled",
        "url_cache_ttl_seconds": "cache_ttl_seconds",
        "url_cache_max_entries": "cache_max_entries",
        "url_max_concurrent": "max_concurrent_requests",
        "url_retry_attempts": "retry_max_attempts",
        "url_browser_pool_max_age_minutes": "browser_pool_max_age_minutes",
        "url_min_content_length": "min_content_length",
        "url_user_agent": "user_agent",
        "url_proxy_enabled": "proxy_enabled",
        "url_proxy_url": "proxy_url",
    })

    # Re-init WeChat Agent so it picks up new model/key settings
    try:
        wechat_channel.agent.reinit()
    except Exception:
        pass

    # Handle raw_dir_path override (not a Settings model field)
    global _runtime_raw_dir
    if "raw_dir_path" in overrides:
        raw_path = overrides["raw_dir_path"]
        try:
            _runtime_raw_dir = Path(raw_path)
            _runtime_raw_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"raw_dir override applied: {_runtime_raw_dir}")
        except Exception as e:
            logger.error(f"Invalid raw_dir_path: {raw_path} — {e}")
            _runtime_raw_dir = None
    else:
        _runtime_raw_dir = None


app = FastAPI(title="SageMate Core", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(wechat_router.router)

# ── Static Files ────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles
# Mount local JS/CSS assets (replaces CDN)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# Mount data/ directory so browsers can load PDFs directly
if settings.data_dir.exists():
    app.mount("/data", StaticFiles(directory=str(settings.data_dir)), name="data")


# ============================================================
# Web Dashboard Routes (HTML)
# ============================================================

@app.get("/", response_class=HTMLResponse, tags=["SPA"])
async def root_spa():
    """Serve the React SPA root."""
    dist = STATIC_DIR / "dist" / "index.html"
    if dist.exists():
        return FileResponse(dist)
    return HTMLResponse("<h1>Frontend not built. Run <code>cd frontend && npm run build</code></h1>")


@app.get("/api/v1/sources", tags=["Sources"], response_model=dict)
async def list_sources_json(status: str | None = None, source_type: str | None = None, q: str | None = None):
    """Return all sources as JSON (for React SPA)."""
    import json
    db = store._db
    sources = []
    all_types = set()
    if db:
        cursor = await db.execute("SELECT * FROM sources ORDER BY ingested_at DESC")
        rows = await cursor.fetchall()
        for r in rows:
            d = dict(r)
            try:
                d['wiki_pages'] = json.loads(d.get('wiki_pages') or '[]')
            except Exception:
                d['wiki_pages'] = []
            all_types.add(d.get('source_type', 'unknown'))
            sources.append(d)
    if status:
        sources = [s for s in sources if s.get('status') == status]
    if source_type:
        sources = [s for s in sources if s.get('source_type') == source_type]
    if q:
        q_lower = q.lower()
        sources = [s for s in sources if q_lower in s.get('title', '').lower() or q_lower in s.get('slug', '').lower()]
    return {"sources": sources, "source_types": sorted(all_types)}


@app.get("/api/v1/ingest/tasks", tags=["Ingest"], response_model=dict)
async def ingest_task_list():
    """Return recent ingest task history (JSON API)."""
    return {"tasks": ingest_tasks.list_tasks(limit=50)}


@app.get("/api/v1/raw/files", tags=["Sources"], response_model=dict)
async def list_raw_files_json():
    """Return all raw files as JSON (for React SPA)."""
    import mimetypes, json
    files = []
    if settings.raw_dir.exists():
        for f in sorted(settings.raw_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(settings.raw_dir)
                parent = str(rel.parent) if rel.parent != Path(".") else "root"
                ext = f.suffix.lower()
                mime, _ = mimetypes.guess_type(str(f))
                size = f.stat().st_size
                is_text = ext in (".md", ".txt", ".html", ".json", ".csv", ".yaml", ".yml", ".py", ".js", ".css") or (mime and mime.startswith("text/"))
                file_info = {
                    "name": f.name,
                    "rel_path": str(rel),
                    "parent": parent,
                    "ext": ext,
                    "size": size,
                    "size_human": _human_size(size),
                    "mime": mime or "application/octet-stream",
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "is_text": is_text,
                    "is_markdown": ext in (".md", ".markdown"),
                    "is_pdf": ext == ".pdf",
                    "is_docx": ext == ".docx",
                    "is_image": mime and mime.startswith("image/"),
                    "file_url": "/data/raw/" + str(rel),
                }
                if is_text and size < 100_000:
                    try:
                        file_info["content"] = f.read_text(encoding="utf-8")
                    except Exception:
                        file_info["content"] = "无法读取文件内容"
                files.append(file_info)

    # Lookup linked sources & wiki pages from DB
    db = store._db
    for f in files:
        f["linked_source"] = None
        f["linked_wiki_pages"] = []
        if db:
            try:
                candidates = [
                    str(settings.raw_dir / f["rel_path"]),
                    f"data/raw/{f['rel_path']}",
                    f["rel_path"],
                ]
                for cand in candidates:
                    cursor = await db.execute("SELECT slug, title, wiki_pages, status, error FROM sources WHERE file_path = ?", (cand,))
                    row = await cursor.fetchone()
                    if row:
                        d = dict(row)
                        try:
                            d["wiki_pages"] = json.loads(d.get("wiki_pages") or "[]")
                        except Exception:
                            d["wiki_pages"] = []
                        f["linked_source"] = d
                        # Batch fetch wiki pages to avoid N+1 queries
                        wp_slugs = d.get("wiki_pages", [])
                        if wp_slugs:
                            pages_map = await store.get_pages_batch(wp_slugs)
                            for wp_slug in wp_slugs:
                                wp = pages_map.get(wp_slug)
                                if wp:
                                    f["linked_wiki_pages"].append({"slug": wp.slug, "title": wp.title, "category": wp.category.value})
                        break
            except Exception:
                pass

    files.sort(key=lambda x: x["modified"], reverse=True)
    return {"files": files, "raw_dir": str(settings.raw_dir)}


@app.get("/api/v1/raw/view", tags=["Sources"])
async def raw_file_view(request: Request, path: str):
    """DOCX embed preview for React SPA iframe. Returns standalone HTML without nav/footer."""
    import mimetypes
    target = settings.raw_dir / path
    try:
        target.resolve().relative_to(settings.raw_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    ext = target.suffix.lower()
    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"
    file_url = "/data/raw/" + path

    return templates.TemplateResponse(
        request, "raw_view_embed.html", {
            "path": path,
            "name": target.name,
            "ext": ext,
            "mime": mime,
            "file_url": file_url,
        }
    )


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


async def _initial_sync():
    """Scan existing wiki files into the database on boot.
    
    Parses YAML frontmatter to preserve sources, tags, source_pages, etc.
    This is critical — without frontmatter parsing, restarts would overwrite
    these fields with empty defaults.
    """
    import re, json
    
    def _parse_frontmatter(content: str) -> dict:
        """Extract YAML frontmatter as a dict."""
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not m:
            return {}
        result = {}
        for line in m.group(1).split("\n"):
            line = line.strip()
            if ':' in line:
                key, _, val = line.partition(':')
                key = key.strip()
                val = val.strip()
                # Parse lists: ["a", "b"] -> list
                if val.startswith('[') and val.endswith(']'):
                    inner = val[1:-1].strip()
                    if not inner:
                        result[key] = []
                    else:
                        items = []
                        for item in re.findall(r'"([^"]*)"', inner):
                            items.append(item)
                        if not items:
                            for item in re.findall(r"'([^']*)'", inner):
                                items.append(item)
                        result[key] = items
                else:
                    # Strip quotes
                    result[key] = val.strip("'\"")
        return result
    
    for cat_dir in settings.wiki_categories:
        if not cat_dir.exists():
            continue
        for md_file in cat_dir.glob("*.md"):
            if md_file.name in ("index.md", "log.md"):
                continue
            try:
                content = md_file.read_text(encoding='utf-8')
                fm = _parse_frontmatter(content)
                
                page = WikiPage(
                    slug=md_file.stem,
                    title=fm.get('title', md_file.stem.replace('-', ' ').title()),
                    category=_category_from_dir(cat_dir),
                    file_path=str(md_file),
                    tags=fm.get('tags', []),
                    sources=fm.get('sources', []),
                    source_pages=fm.get('source_pages', []),
                    outbound_links=fm.get('outbound_links', []),
                    summary="",  # Will be auto-generated by store
                )
                await store.upsert_page(page, content)
            except Exception as e:
                print(f"[InitialSync] Error scanning {md_file}: {e}")


def _category_from_dir(dir_path: Path) -> WikiCategory:
    name = dir_path.name.lower()
    mapping = {
        "entities": WikiCategory.ENTITY,
        "concepts": WikiCategory.CONCEPT,
        "analyses": WikiCategory.ANALYSIS,
        "sources": WikiCategory.SOURCE,
        "notes": WikiCategory.NOTE,
    }
    return mapping.get(name, WikiCategory.CONCEPT)


# ============================================================
# API Endpoints
# ============================================================

@app.get("/health", tags=["System"], response_model=HealthResponse)
async def health():
    stats = await store.stats()
    return {
        "status": "ok",
        "version": "0.4.0",
        "data_dir": str(settings.data_dir),
        "wiki_pages": stats["wiki_pages"],
        "sources": stats["sources"],
    }


@app.get("/api/v1/settings", tags=["Settings"], response_model=dict)
async def get_settings():
    """Get all current application settings."""
    overrides = await store.get_all_settings()
    # Build current effective settings from globals + overrides
    import json

    def _get(key: str, default):
        if key in overrides:
            raw = overrides[key]
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                if isinstance(default, bool) and isinstance(raw, str):
                    return raw.lower() == "true"
                if isinstance(default, int) and raw.isdigit():
                    return int(raw)
                return raw
        return default

    return {
        # LLM
        "llm_base_url": _get("llm_base_url", settings.llm_base_url),
        "llm_api_key": _get("llm_api_key", settings.llm_api_key),
        "llm_model": _get("llm_model", settings.llm_model),
        # Vision
        "vision_base_url": _get("vision_base_url", settings.vision_base_url),
        "vision_api_key": _get("vision_api_key", settings.vision_api_key),
        "vision_model": _get("vision_model", settings.vision_model),
        # WeChat
        "wechat_base_url": _get("wechat_base_url", getattr(settings, "wechat_base_url", "https://open.bigmodel.cn/api/paas/v4")),
        "wechat_api_key": _get("wechat_api_key", getattr(settings, "wechat_api_key", "")),
        # Compiler
        "compiler_max_source_chars": _get("compiler_max_source_chars", settings.compiler_max_source_chars),
        "compiler_max_wiki_context_chars": _get("compiler_max_wiki_context_chars", settings.compiler_max_wiki_context_chars),
        # Lint
        "lint_stale_days": _get("lint_stale_days", settings.lint_stale_days),
        # Cron
        "cron_auto_compile_enabled": _get("cron_auto_compile_enabled", settings.cron_auto_compile_enabled),
        "cron_auto_compile_interval": _get("cron_auto_compile_interval", settings.cron_auto_compile_interval),
        "cron_lint_enabled": _get("cron_lint_enabled", settings.cron_lint_enabled),
        "cron_lint_interval": _get("cron_lint_interval", settings.cron_lint_interval),
        # URL Collector
        "url_tier1_timeout": _get("url_tier1_timeout", url_collector_settings.tier1_timeout),
        "url_tier2_timeout": _get("url_tier2_timeout", url_collector_settings.tier2_timeout),
        "url_tier2_network_idle_timeout": _get("url_tier2_network_idle_timeout", url_collector_settings.tier2_network_idle_timeout),
        "url_tier2_wait_selector_timeout": _get("url_tier2_wait_selector_timeout", url_collector_settings.tier2_wait_selector_timeout),
        "url_cache_enabled": _get("url_cache_enabled", url_collector_settings.cache_enabled),
        "url_cache_ttl_seconds": _get("url_cache_ttl_seconds", url_collector_settings.cache_ttl_seconds),
        "url_cache_max_entries": _get("url_cache_max_entries", url_collector_settings.cache_max_entries),
        "url_max_concurrent": _get("url_max_concurrent", url_collector_settings.max_concurrent_requests),
        "url_retry_attempts": _get("url_retry_attempts", url_collector_settings.retry_max_attempts),
        "url_browser_pool_max_age_minutes": _get("url_browser_pool_max_age_minutes", url_collector_settings.browser_pool_max_age_minutes),
        "url_min_content_length": _get("url_min_content_length", url_collector_settings.min_content_length),
        "url_user_agent": _get("url_user_agent", url_collector_settings.user_agent),
        "url_proxy_enabled": _get("url_proxy_enabled", url_collector_settings.proxy_enabled),
        "url_proxy_url": _get("url_proxy_url", url_collector_settings.proxy_url or ""),
        # Watcher
        "watcher_debounce_ms": _get("watcher_debounce_ms", settings.watcher_debounce_ms),
        # Storage (project-aware)
        "raw_dir_path": _get("raw_dir_path", str(settings.raw_dir)),
        # Metadata
        "overrides": list(overrides.keys()),
    }


@app.post("/api/v1/settings/reset", tags=["Settings"], response_model=GenericResponse)
async def reset_settings():
    """Reset all runtime setting overrides (clear DB table)."""
    db = store._db
    if db:
        await db.execute("DELETE FROM app_settings")
        await db.commit()
    await reload_settings_from_db()
    return {"success": True}


@app.patch("/api/v1/settings", tags=["Settings"], response_model=AppSettings)
async def update_settings(payload: SettingsUpdate):
    """Update application settings. Saves to DB and applies immediately."""
    import json

    # Map update fields to DB keys
    field_map = {
        "llm_base_url": payload.llm_base_url,
        "llm_api_key": payload.llm_api_key,
        "llm_model": payload.llm_model,
        "vision_base_url": payload.vision_base_url,
        "vision_api_key": payload.vision_api_key,
        "vision_model": payload.vision_model,
        "wechat_base_url": payload.wechat_base_url,
        "wechat_api_key": payload.wechat_api_key,
        "compiler_max_source_chars": payload.compiler_max_source_chars,
        "compiler_max_wiki_context_chars": payload.compiler_max_wiki_context_chars,
        "lint_stale_days": payload.lint_stale_days,
        "cron_auto_compile_enabled": payload.cron_auto_compile_enabled,
        "cron_auto_compile_interval": payload.cron_auto_compile_interval,
        "cron_lint_enabled": payload.cron_lint_enabled,
        "cron_lint_interval": payload.cron_lint_interval,
        "url_tier1_timeout": payload.url_tier1_timeout,
        "url_tier2_timeout": payload.url_tier2_timeout,
        "url_cache_enabled": payload.url_cache_enabled,
        "url_max_concurrent": payload.url_max_concurrent,
        "url_retry_attempts": payload.url_retry_attempts,
        "url_proxy_enabled": payload.url_proxy_enabled,
        "url_proxy_url": payload.url_proxy_url,
        "watcher_debounce_ms": payload.watcher_debounce_ms,
        # Storage
        "raw_dir_path": payload.raw_dir_path,
    }

    for key, value in field_map.items():
        if value is not None:
            await store.set_setting(key, json.dumps(value))

    await reload_settings_from_db()
    return {"success": True, "updated": [k for k, v in field_map.items() if v is not None]}


# ── Projects API ─────────────────────────────────────────────

@app.get("/api/v1/projects", tags=["Projects"], response_model=dict)
async def list_projects():
    """List all projects."""
    projects = await store.list_projects()
    return {
        "projects": [p.model_dump() for p in projects],
        "count": len(projects),
    }


@app.post("/api/v1/projects", tags=["Projects"], response_model=dict)
async def create_project(payload: ProjectCreate):
    """Create a new project from a directory path."""
    import uuid
    import os

    root_path = os.path.abspath(payload.root_path)
    if not os.path.isdir(root_path):
        raise HTTPException(status_code=400, detail=f"目录不存在: {root_path}")

    # Check for duplicate path
    existing = await store.list_projects()
    if any(p.root_path == root_path for p in existing):
        raise HTTPException(status_code=409, detail="该目录已添加为项目")

    name = payload.name or os.path.basename(root_path)
    now = datetime.now().isoformat()
    project = Project(
        id=str(uuid.uuid4())[:8],
        name=name,
        root_path=root_path,
        created_at=now,
        updated_at=now,
    )

    # Ensure wiki/ and wiki/assets/ subdirs exist
    wiki_dir = Path(root_path) / project.wiki_dir_name
    assets_dir = wiki_dir / project.assets_dir_name
    os.makedirs(wiki_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    await store.create_project(project)
    return {"success": True, "project": project.model_dump()}


@app.get("/api/v1/projects/{project_id}", tags=["Projects"], response_model=dict)
async def get_project(project_id: str):
    """Get a single project by ID."""
    project = await store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": project.model_dump()}


@app.patch("/api/v1/projects/{project_id}", tags=["Projects"], response_model=dict)
async def update_project(project_id: str, payload: ProjectUpdate):
    """Update project metadata."""
    project = await store.update_project(project_id, name=payload.name)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "project": project.model_dump()}


@app.post("/api/v1/projects/{project_id}/activate", tags=["Projects"], response_model=GenericResponse)
async def activate_project(project_id: str):
    """Set a project as the active project."""
    project = await store.activate_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "project": project.model_dump()}


@app.delete("/api/v1/projects/{project_id}", tags=["Projects"], response_model=GenericResponse)
async def delete_project(project_id: str):
    """Delete a project (metadata only, does NOT delete files)."""
    project = await store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status == ProjectStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="无法删除当前激活的项目，请先切换到其他项目")
    await store.delete_project(project_id)
    return {"success": True}


@app.get("/api/v1/projects/active", tags=["Projects"], response_model=dict)
async def get_active_project():
    """Get the currently active project."""
    project = await store.get_active_project()
    return {"project": project.model_dump() if project else None}


@app.get("/api/v1/schema", tags=["Settings"], response_model=dict)
async def get_schema():
    """Return database schema (tables, DDL, columns) for display in Settings."""
    schema = await store.get_schema()
    return {"tables": schema}


@app.post("/api/v1/projects/{project_id}/scan", tags=["Projects"], response_model=dict)
async def scan_project_files(project_id: str):
    """Scan a project directory and return discovered raw files.
    Excludes the wiki/ output directory.
    """
    import os
    from pathlib import Path

    project = await store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    root = Path(project.root_path)
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"目录不存在: {root}")

    wiki_subdir = root / project.wiki_dir_name
    supported_exts = {'.pdf', '.md', '.markdown', '.txt', '.docx', '.html', '.htm',
                      '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}

    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip wiki output directory
        dirpath_obj = Path(dirpath)
        if dirpath_obj == wiki_subdir or wiki_subdir in dirpath_obj.parents:
            dirnames.clear()
            continue

        for fn in filenames:
            ext = Path(fn).suffix.lower()
            if ext in supported_exts:
                fp = dirpath_obj / fn
                stat = fp.stat()
                files.append({
                    "path": str(fp),
                    "rel_path": str(fp.relative_to(root)),
                    "name": fn,
                    "ext": ext,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

    return {"project_id": project_id, "files": files, "count": len(files)}


# ── WeChat QR Login API ─────────────────────────────────────
# 已迁移到 routers/wechat.py


@app.post("/api/v1/pages", status_code=201, tags=["Wiki"], response_model=dict)
async def create_page(payload: WikiPageCreate):
    """Create a new wiki page (e.g. a user-authored Note).

    Strategy:
    1. Generate file path based on category
    2. Write markdown file with frontmatter
    3. Insert into database + FTS5 index

    Returns: { success: bool, slug: str }
    """
    wiki_dir = settings.wiki_dir_for_category(payload.category.value if isinstance(payload.category, WikiCategory) else payload.category)
    slug = payload.slug.lower().replace(" ", "-")

    # De-dup slug: if exists, append a counter
    original_slug = slug
    counter = 1
    while await store.get_page(slug):
        slug = f"{original_slug}-{counter}"
        counter += 1

    file_path = wiki_dir / f"{slug}.md"

    # Build full content: if payload already contains frontmatter, use as-is
    import json
    if payload.content.strip().startswith("---"):
        full_content = payload.content
    else:
        fm_lines = [
            "---",
            f"title: \"{payload.title}\"",
            f"category: {payload.category.value if isinstance(payload.category, WikiCategory) else payload.category}",
            f"tags: {json.dumps(payload.tags)}",
            f"outbound_links: {json.dumps(payload.outbound_links)}",
            f"sources: {json.dumps(payload.sources)}",
            "---",
            "",
        ]
        full_content = "\n".join(fm_lines) + payload.content

    # Write file
    try:
        file_path.write_text(full_content, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write page: {e}")

    # Insert into DB
    now = datetime.now()
    page = WikiPage(
        slug=slug,
        title=payload.title,
        category=payload.category,
        file_path=str(file_path),
        content=payload.content,
        summary="",
        tags=payload.tags,
        outbound_links=payload.outbound_links,
        sources=payload.sources,
        created_at=now,
        updated_at=now,
    )
    await store.upsert_page(page, full_content)

    return {"success": True, "slug": slug}


@app.get("/api/v1/pages", response_model=list[WikiPage], tags=["Wiki"])
async def list_pages(category: str | None = None):
    """List all wiki pages, optionally filtered by category."""
    cat = WikiCategory(category) if category else None
    return await store.list_pages(cat)


@app.get("/api/v1/pages/{slug}", tags=["Wiki"], response_model=PageDetailResponse)
async def get_page(slug: str):
    """Get a wiki page."""
    page = await store.get_page(slug)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page not found: {slug}")
    # Also read the file content
    try:
        file_content = Path(page.file_path).read_text(encoding='utf-8')
    except Exception:
        file_content = page.content if hasattr(page, 'content') else ""
    return {"page": page, "content": file_content}


@app.put("/api/v1/pages/{slug}", tags=["Wiki"], response_model=GenericResponse)
async def update_page(slug: str, request: Request):
    """Update a wiki page by saving new content to its markdown file."""
    import json
    page = await store.get_page(slug)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page not found: {slug}")

    try:
        body = await request.json()
        new_content = body.get("content", "")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        file_path = Path(page.file_path)
        file_path.write_text(new_content, encoding='utf-8')

        # Update database entry directly (watcher will also pick it up)
        # Re-parse frontmatter to update metadata
        import re
        fm = {}
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n', new_content, re.DOTALL)
        if m:
            for line in m.group(1).split("\n"):
                line = line.strip()
                if ':' in line:
                    key, _, val = line.partition(':')
                    key = key.strip()
                    val = val.strip()
                    if val.startswith('[') and val.endswith(']'):
                        inner = val[1:-1].strip()
                        if not inner:
                            fm[key] = []
                        else:
                            items = re.findall(r'"([^"]*)"', inner)
                            if not items:
                                items = re.findall(r"'([^']*)'", inner)
                            fm[key] = items
                    else:
                        fm[key] = val.strip("'\"")

        # Extract outbound wikilinks
        outbound = re.findall(r'\[\[([^\]]+)\]\]', new_content)

        page.title = fm.get('title', page.title)
        page.tags = fm.get('tags', page.tags) if isinstance(fm.get('tags'), list) else page.tags
        page.sources = fm.get('sources', page.sources) if isinstance(fm.get('sources'), list) else page.sources
        page.source_pages = fm.get('source_pages', page.source_pages) if isinstance(fm.get('source_pages'), list) else page.source_pages
        page.outbound_links = list(set(outbound))
        page.updated_at = datetime.now()

        await store.upsert_page(page, new_content)

        return {"success": True, "slug": slug, "message": "Page updated"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save page: {e}")


@app.delete("/api/v1/pages/{slug}", tags=["Wiki"], response_model=GenericResponse)
async def delete_page(slug: str):
    """Delete a wiki page (both file and database entry)."""
    page = await store.get_page(slug)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page not found: {slug}")

    try:
        file_path = Path(page.file_path)
        if file_path.exists():
            file_path.unlink()

        await store.delete_page(slug)

        return {"success": True, "slug": slug, "message": "Page deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete page: {e}")


@app.get("/api/v1/search", response_model=list[SearchResult], tags=["Wiki"])
async def search(q: str, category: str | None = None):
    """Full-text search across wiki pages."""
    cat = WikiCategory(category) if category else None
    return await store.search(q, category=cat)


# ── Async Ingest with SSE Progress ─────────────────────────────

@app.post("/api/v1/ingest", tags=["Ingest"], response_model=dict)
async def ingest_file(
    file: UploadFile | None = File(None),
    auto_compile: bool = Form(True),
    url: str | None = Form(None),
    text: str | None = Form(None),
    title: str | None = Form(None),
):
    """Upload and ingest a file, URL, or text. Returns task_id immediately; process runs async."""
    import re, shutil
    
    task_id = ingest_tasks.create_task()
    
    try:
        # ── Mode 1: File Upload ──
        if file and file.filename:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)
            
            # Validate file header against extension
            ext = Path(file.filename).suffix.lower()
            try:
                FileTypeValidator.validate(content, ext.lstrip("."))
            except FileValidationError as fv_err:
                os.unlink(tmp_path)
                raise HTTPException(status_code=400, detail=str(fv_err))

            # Unified slug generation
            source_title = file.filename
            source_slug = SlugGenerator.generate(
                source_title.rsplit(".", 1)[0] if "." in source_title else source_title,
                prefix="raw",
            )

            await ingest_tasks.update_progress(task_id, IngestTaskStatus.PARSING, 1, "正在解析文件内容...")
            try:
                _, source_content = await DeterministicParser.parse(tmp_path, settings.raw_dir)
            except Exception as parse_err:
                await ingest_tasks.set_error(task_id, f"解析失败: {parse_err}", failed_step="parsing")
                os.unlink(tmp_path)
                raise HTTPException(status_code=422, detail=f"文件解析失败: {parse_err}")
            source_content = re.sub(r'slug:.*$', f'slug: {source_slug}', source_content, flags=re.MULTILINE)

            # Archive to canonical location
            archive_dir = ArchiveHelper.files_dir(settings.raw_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / file.filename
            shutil.copy2(tmp_path, archive_path)
            os.unlink(tmp_path)

            source_type = {".pdf": "pdf", ".md": "markdown", ".docx": "docx", ".html": "html", ".htm": "html", ".txt": "text"}.get(ext, "unknown")
            
        # ── Mode 2: URL Ingestion ──
        elif url:
            from ..ingest.adapters.url_collector import get_default_collector
            collected = await get_default_collector().collect(url)
            if not collected.success:
                raise RuntimeError(f"URL collection failed: {collected.error}")
            
            safe_name = re.sub(r'[^\w\u4e00-\u9fa5-]', '-', url)[:80]
            safe_name = re.sub(r'-{2,}', '-', safe_name).strip('-').lower()
            source_slug = f"url-{safe_name}"
            source_title = collected.title or url
            source_content = collected.content
            source_type = "url"
            
            archive_dir = ArchiveHelper.papers_dir(settings.raw_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / f"{source_slug}.md"
            md_content = f"""---
title: '{source_title}'
source_url: '{url}'
collected_at: '{datetime.now().isoformat()}'
---

{collected.content}
"""
            archive_path.write_text(md_content, encoding='utf-8')
            
        # ── Mode 3: Text Ingestion ──
        elif text:
            import time
            safe_title = (title or "Untitled Note").strip()
            safe_name = re.sub(r'[^\w\u4e00-\u9fa5-]', '-', safe_title)[:60]
            safe_name = re.sub(r'-{2,}', '-', safe_name).strip('-').lower() or f"note-{int(time.time())}"
            source_slug = safe_name
            source_title = safe_title
            source_content = text
            source_type = "text"
            
            archive_dir = ArchiveHelper.notes_dir(settings.raw_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / f"{source_slug}.md"
            md_content = f"""---
title: '{source_title}'
created_at: '{datetime.now().isoformat()}'
---

{text}
"""
            archive_path.write_text(md_content, encoding='utf-8')
        
        else:
            await ingest_tasks.set_error(task_id, "No input provided.", failed_step="queued")
            raise HTTPException(400, "No input provided.")
        
        # ── Async Compile ──
        if auto_compile and settings.llm_api_key:
            # Start background task
            asyncio.create_task(
                ingest_tasks.run_compile(
                    task_id=task_id,
                    source_slug=source_slug,
                    source_content=source_content,
                    source_title=source_title,
                    archive_path=archive_path,
                    source_type=source_type,
                )
            )
            return {
                "task_id": task_id,
                "status": "processing",
                "message": "文件已接收，正在后台编译中",
            }
        else:
            # No compile needed, just archive
            await store.upsert_source(
                slug=source_slug,
                title=source_title,
                file_path=str(archive_path),
                source_type=source_type,
                status="completed",
            )
            await ingest_tasks.set_result(task_id, IngestResult(
                success=True,
                source_slug=source_slug,
                wiki_pages_created=0,
                wiki_pages_updated=0,
            ))
            return {
                "task_id": task_id,
                "status": "completed",
                "message": "已归档（未启用自动编译）",
                "result": {"source_slug": source_slug, "wiki_pages_created": 0},
            }
        
    except HTTPException:
        await ingest_tasks.set_error(task_id, "Invalid request", failed_step="queued")
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        await ingest_tasks.set_error(task_id, str(e), failed_step="queued")
        return {
            "task_id": task_id,
            "status": "failed",
            "message": f"处理失败: {str(e)}",
        }


# ── Chrome Extension Clip API ─────────────────────────────────

@app.post("/api/v1/clip", tags=["Ingest"], response_model=dict)
async def clip(payload: dict):
    """
    Receive content from Chrome Extension (SageMate Clipper).
    Saves to raw/ and optionally triggers compilation.
    """
    title = payload.get("title", "Untitled").strip()
    url = payload.get("url", "")
    content = payload.get("content", "")
    hostname = payload.get("hostname", "")
    auto_compile = payload.get("auto_compile", True)
    source_type = payload.get("source_type", "browser_clipper")

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    # Generate slug
    source_slug = SlugGenerator.generate(title, prefix="raw")
    safe_name = source_slug

    # Save to raw/papers/originals/
    archive_dir = ArchiveHelper.papers_dir(settings.raw_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{safe_name}.md"

    # Build markdown with frontmatter
    md_content = f"""---
title: '{title.replace("'", "'")}'
slug: {source_slug}
source: '{url}'
source_type: '{source_type}'
hostname: '{hostname}'
clipped_at: '{datetime.now().isoformat()}'
---

{content.strip()}
"""
    archive_path.write_text(md_content, encoding="utf-8")

    # Create task
    task_id = ingest_tasks.create_task()

    # Upsert source
    await store.upsert_source(
        slug=source_slug,
        title=title,
        file_path=str(archive_path),
        source_type=source_type,
        status="pending" if auto_compile else "completed",
    )

    if auto_compile and settings.llm_api_key:
        asyncio.create_task(
            ingest_tasks.run_compile(
                task_id=task_id,
                source_slug=source_slug,
                source_content=md_content,
                source_title=title,
                archive_path=archive_path,
                source_type=source_type,
            )
        )
        return {
            "success": True,
            "task_id": task_id,
            "source_slug": source_slug,
            "status": "processing",
            "message": "已保存，正在编译中...",
        }
    else:
        await ingest_tasks.set_result(task_id, IngestResult(
            success=True,
            source_slug=source_slug,
            wiki_pages_created=0,
            wiki_pages_updated=0,
        ))
        msg = "已保存到素材库"
        if auto_compile and not settings.llm_api_key:
            msg += "（未配置 LLM，跳过编译）"
        return {
            "success": True,
            "task_id": task_id,
            "source_slug": source_slug,
            "status": "completed",
            "message": msg,
        }


@app.get("/api/v1/ingest/progress/{task_id}", tags=["Ingest"])
async def ingest_progress(task_id: str):
    """SSE endpoint for real-time ingest progress via EventBus."""
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        queue = asyncio.Queue(maxsize=100)
        
        async def handler(payload: dict):
            if payload.get("task_id") == task_id:
                await queue.put(payload)
        
        await event_bus.subscribe("ingest.progress", handler)
        try:
            task = ingest_tasks.get_task(task_id)
            if not task:
                yield f"data: {json.dumps({'type': 'failed', 'status': 'failed', 'message': 'Task not found'})}\n\n"
                return

            # If task already finished before subscription, emit final event immediately
            if task.status.value in ("completed", "failed"):
                yield f"data: {json.dumps({'type': task.status.value, 'status': task.status.value, 'message': task.message, 'step': task.step, 'total_steps': task.total_steps})}\n\n"
                return

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            await event_bus.unsubscribe("ingest.progress", handler)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/ingest/result/{task_id}", tags=["Ingest"], response_model=dict)
async def ingest_result(task_id: str):
    """Get the final result of an ingest task."""
    task = ingest_tasks.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # Flatten result for frontend convenience
    payload = {
        "status": task.status.value,
        "message": task.message,
        "task_id": task.task_id,
        "step": task.step,
        "total_steps": task.total_steps,
    }
    if task.result:
        payload.update({
            "success": task.result.success,
            "source_slug": task.result.source_slug,
            "wiki_pages_created": task.result.wiki_pages_created,
            "wiki_pages_updated": task.result.wiki_pages_updated,
            "wiki_pages": task.result.wiki_pages,
            "error": task.result.error,
        })
    if task.error:
        payload["error"] = task.error
    return payload


def _build_fallback_answer(question: str, results: list) -> str:
    """Build a structured fallback answer when LLM is unavailable."""
    import re
    lines = [f"基于知识库中的 {len(results)} 个相关页面，以下是简要整理：\n"]
    for r in results:
        snippet = (r.snippet or "暂无摘要")[:300]
        # Strip frontmatter from snippet if present
        snippet = re.sub(r'^---\s*\n[\s\S]*?\n---\s*\n', '', snippet)
        lines.append(f"### [{r.title}](/web/pages/{r.slug})")
        lines.append(f"{snippet}\n")
    lines.append("---")
    lines.append("💡 *提示：配置 LLM API Key 后可获得 AI 综合深度回答。*")
    return "\n".join(lines)


@app.post("/api/v1/query", response_model=QueryResponse, tags=["Query"])
async def query(request: QueryRequest):
    """
    Query the wiki. Searches wiki pages, then synthesizes an answer.
    Delegates to the shared AgentPipeline.query() to avoid duplication.
    """
    answer, sources, related_pages, citations = await agent_pipeline.query(request.question)
    return QueryResponse(
        answer=answer,
        sources=sources,
        citations=citations,
        related_pages=related_pages,
    )


@app.post("/api/v1/query/stream", tags=["Query"])
async def query_stream(request: QueryRequest, req: Request):
    """
    Streaming query endpoint. Returns SSE (Server-Sent Events) with token-by-token
    LLM output, followed by a final 'done' event containing the formatted answer
    and paper-style references.
    """
    from fastapi.responses import StreamingResponse

    async def event_generator():
        async for event in agent_pipeline.query_stream(request.question):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/v1/agent/chat", response_model=AgentResponse, tags=["Query"])
async def agent_chat(request: Request):
    """Unified intelligence endpoint for all channels (WeChat, Web, etc.)."""
    import json
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    msg = AgentMessage(
        channel=body.get("channel", "unknown"),
        user_id=body.get("user_id", ""),
        content_type=body.get("content_type", "text"),
        text=body.get("text", ""),
        raw_data=body.get("raw_data", {}),
    )
    return await agent_pipeline.process(msg)


@app.post("/api/v1/lint", response_model=LintReport, tags=["Lint"])
async def lint(trigger: LintTrigger | None = None):
    """Run a lint check on the wiki."""
    if trigger is None:
        trigger = LintTrigger()
    report = await lint_engine.run()
    return report


@app.get("/api/v1/lint/report", tags=["Lint"], response_model=dict)
async def lint_report_md():
    """Get the latest lint report as markdown."""
    report = await lint_engine.run()
    return await lint_engine.generate_report_md(report)


@app.get("/api/v1/index", tags=["Wiki"], response_model=dict)
async def get_index():
    """Get the wiki index."""
    index_path = settings.wiki_dir / "index.md"
    if not index_path.exists():
        return {"content": "", "entries": []}
    content = index_path.read_text(encoding='utf-8')
    entries = await store.build_index_entries()
    return {"content": content, "entries": [e.model_dump() for e in entries]}


@app.get("/api/v1/log", tags=["System"], response_model=dict)
async def get_log():
    """Get the wiki activity log."""
    log_path = settings.wiki_dir / "log.md"
    if not log_path.exists():
        return {"content": ""}
    return {"content": log_path.read_text(encoding='utf-8')}


@app.get("/api/v1/stats", tags=["System"], response_model=dict)
async def stats():
    """Get wiki statistics."""
    return await store.stats()


@app.get("/api/v1/cost", tags=["System"], response_model=dict)
async def cost_summary(days: int = 30, recent: int = 20):
    """Get LLM token usage and cost summary."""
    if not cost_monitor:
        return {"summary": None, "recent": []}
    summary = cost_monitor.get_summary(days=days)
    recent_entries = cost_monitor.get_recent_entries(limit=recent)
    return {"summary": summary, "recent": recent_entries}


@app.get("/api/v1/cron/status", tags=["System"], response_model=dict)
async def cron_status_endpoint():
    """Get cron scheduler status."""
    return {
        "running": getattr(cron, '_running', False) if cron else False,
        "auto_compile": {
            "enabled": getattr(settings, "cron_auto_compile_enabled", True),
            "interval_seconds": getattr(settings, "cron_auto_compile_interval", 300),
        },
        "lint_check": {
            "enabled": getattr(settings, "cron_lint_enabled", True),
            "interval_seconds": getattr(settings, "cron_lint_interval", 1800),
        },
        "active_tasks": len(getattr(cron, '_tasks', [])) if cron else 0,
    }


@app.get("/api/v1/export", tags=["Export"])
async def export_wiki():
    """
    Export entire wiki as ZIP archive.
    Includes: wiki markdown files, source archive, index, log, and schema.
    """
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Wiki markdown files
        if settings.wiki_dir.exists():
            for md_file in settings.wiki_dir.rglob("*.md"):
                arc_name = f"wiki/{md_file.relative_to(settings.wiki_dir)}"
                zf.write(md_file, arc_name)
        
        # 2. Source documents (archived originals)
        originals_dir = settings.raw_dir / "papers" / "originals"
        if originals_dir.exists():
            for src_file in originals_dir.iterdir():
                if src_file.is_file():
                    arc_name = f"sources/{src_file.name}"
                    zf.write(src_file, arc_name)
        
        # 3. Raw articles/notes
        for subdir in ["articles", "notes"]:
            raw_subdir = settings.raw_dir / subdir
            if raw_subdir.exists():
                for f in raw_subdir.iterdir():
                    if f.is_file():
                        arc_name = f"raw/{subdir}/{f.name}"
                        zf.write(f, arc_name)
        
        # 4. Schema conventions
        if settings.schema_dir.exists():
            for f in settings.schema_dir.iterdir():
                if f.is_file():
                    zf.write(f, f"schema/{f.name}")
    
    zip_buffer.seek(0)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sagemate_export_{timestamp}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/v1/export/json", tags=["Export"], response_model=dict)
async def export_wiki_json():
    """
    Export wiki data as JSON (structured, no binaries).
    Includes: pages, sources, index entries.
    """
    pages = await store.list_pages()
    sources = await store.list_sources()
    index_entries = await store.build_index_entries()
    
    return {
        "exported_at": datetime.now().isoformat(),
        "page_count": len(pages),
        "source_count": len(sources),
        "pages": [p.model_dump() for p in pages],
        "sources": sources,
        "index": [e.model_dump() for e in index_entries],
    }


@app.post("/api/v1/recompile", tags=["Ingest"], response_model=GenericResponse)
async def recompile_all(force_language: str = "zh"):
    """
    Batch recompile all wiki pages from their source documents.
    Useful for converting old English wiki pages to Chinese.
    """
    import logging
    logger = logging.getLogger(__name__)

    # 1. Get all source documents
    sources = await store.list_sources()
    if not sources:
        return {"status": "no_sources", "message": "No source documents found."}

    results = []
    for source in sources:
        slug = source.get("slug", "")
        title = source.get("title", "")
        file_path = source.get("file_path", "")

        if not file_path or not Path(file_path).exists():
            results.append({"slug": slug, "status": "skipped", "reason": "file not found"})
            continue

        # 2. Parse source to markdown
        try:
            parser = DeterministicParser()
            _, source_content = await parser.parse(Path(file_path), settings.raw_dir)
        except Exception as e:
            results.append({"slug": slug, "status": "error", "reason": f"parse failed: {e}"})
            continue

        # 3. Create a recompile-specific LLM client with Chinese language instruction
        recompile_llm = LLMClient(
            purpose="recompile",
            cost_monitor=cost_monitor,
        )

        # 4. Build recompile prompt with language enforcement
        index_entries = await store.build_index_entries()
        index_context = compiler._format_index_context(index_entries)
        source_text = source_content[:settings.compiler_max_source_chars]
        conventions = compiler._load_conventions()

        language_instruction = (
            f"CRITICAL: ALL output MUST be written in {force_language}.\n"
            f"If force_language is 'zh', write everything in Chinese.\n"
        )

        system_prompt = f"""You are re-compiling wiki pages for a personal knowledge base.

{language_instruction}

Rules:
1. Extract key entities and concepts from the source.
2. Create concise, self-contained wiki pages.
3. Use wikilinks [[like-this]] for cross-references.
4. Keep one concept per page.
5. Use lowercase-kebab-case slugs.

{conventions}"""

        prompt = f"""Re-analyze this source document and produce updated wiki pages.

## Source: {title} (slug: {slug})

{source_text}

## Current Wiki Index

{index_context}

## Task

Produce wiki pages in {force_language}. Return JSON with:
- source_archive: summary of the document
- new_pages: wiki pages to create (with slug, title, category, content, source_pages)
- contradictions: any contradictions found"""

        try:
            result_data = await recompile_llm.generate_structured(
                prompt=prompt,
                system_prompt=system_prompt,
                response_format={"type": "json_schema", "json_schema": __import__("sagemate.ingest.compiler.compiler", fromlist=["COMPILE_RESPONSE_SCHEMA"]).COMPILE_RESPONSE_SCHEMA},
            )

            # Parse and write
            compile_result = compiler._parse_compile_result(result_data, slug)
            await compiler._write_pages(compile_result)
            await compiler._update_index()

            results.append({
                "slug": slug,
                "status": "ok",
                "pages_created": len(compile_result.new_pages),
            })
        except Exception as e:
            results.append({"slug": slug, "status": "error", "reason": str(e)})

    return {
        "status": "completed",
        "total": len(sources),
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════
# SPA Catch-All — Serve React app for all non-API routes
# ═══════════════════════════════════════════════════════════════

API_PREFIXES = {
    "api/", "static/", "data/", "docs", "health", "pages", "search",
    "ingest", "query", "lint", "index", "log", "stats", "cost", "cron",
    "export", "recompile", "agent", "sources", "clip",
}

@app.get("/{full_path:path}", response_class=HTMLResponse, tags=["SPA"])
async def serve_spa(full_path: str):
    """Serve the React SPA for any unmatched route (enables client-side routing)."""
    # Don't intercept API or asset routes
    if any(full_path == p or full_path.startswith(p + "/") for p in API_PREFIXES):
        raise HTTPException(status_code=404, detail="Not found")
    dist = STATIC_DIR / "dist" / "index.html"
    if dist.exists():
        return FileResponse(dist)
    return HTMLResponse("<h1>Frontend not built</h1>")
