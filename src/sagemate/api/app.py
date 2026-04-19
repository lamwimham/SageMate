"""FastAPI Application Entry Point — SageMate Core v0.2"""

from __future__ import annotations

import os
import asyncio
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import settings
from ..core.store import Store
from ..core.watcher import WatcherManager
from ..models import (
    IngestResult,
    LintReport,
    LintTrigger,
    QueryRequest,
    QueryResponse,
    SearchResult,
    WikiCategory,
    WikiPage,
)
from ..pipeline.compiler import IncrementalCompiler, LLMClient
from ..pipeline.lint import LintEngine
from ..pipeline.parser import DeterministicParser
from ..pipeline.cost_monitor import CostMonitor
from ..doctor import Doctor
from ..plugins.wechat.channel import WechatChannel

# ── Startup Doctor Check ───────────────────────────────────────
if not Doctor.run():
    import sys
    sys.exit(1)

settings.ensure_dirs()

# ── Global Components ───────────────────────────────────────────
store = Store(str(settings.db_path))
cost_monitor = CostMonitor()
watcher = WatcherManager(store, settings.raw_dir, settings.wiki_dir, settings)
compiler = IncrementalCompiler(
    store, settings.wiki_dir, LLMClient(purpose="compile", cost_monitor=cost_monitor),
    settings, cost_monitor=cost_monitor,
)
lint_engine = LintEngine(store, settings.wiki_dir, settings)
wechat_channel = WechatChannel()  # Initialize WeChat Channel


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    os.makedirs(settings.raw_dir, exist_ok=True)
    os.makedirs(settings.wiki_dir, exist_ok=True)
    await store.connect()
    watcher.start()
    await _initial_sync()
    
    # Start WeChat Channel in background
    asyncio.create_task(wechat_channel.start())
    
    yield
    
    # Shutdown
    watcher.stop()
    await store.close()


app = FastAPI(title="SageMate Core", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _initial_sync():
    """Scan existing wiki files into the database on boot."""
    for cat_dir in settings.wiki_categories:
        if not cat_dir.exists():
            continue
        for md_file in cat_dir.glob("*.md"):
            if md_file.name in ("index.md", "log.md"):
                continue
            try:
                content = md_file.read_text(encoding='utf-8')
                # Minimal frontmatter parse
                title = md_file.stem.replace('-', ' ').title()
                import json
                page = WikiPage(
                    slug=md_file.stem,
                    title=title,
                    category=_category_from_dir(cat_dir),
                    file_path=str(md_file),
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
    }
    return mapping.get(name, WikiCategory.CONCEPT)


# ============================================================
# API Endpoints
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.4.0",
        "data_dir": str(settings.data_dir),
        "wiki_pages": (await store.stats())["wiki_pages"],
        "sources": (await store.stats())["sources"],
    }


@app.get("/pages", response_model=list[WikiPage])
async def list_pages(category: str | None = None):
    """List all wiki pages, optionally filtered by category."""
    cat = WikiCategory(category) if category else None
    return await store.list_pages(cat)


@app.get("/pages/{slug}")
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


@app.get("/search", response_model=list[SearchResult])
async def search(q: str, category: str | None = None):
    """Full-text search across wiki pages."""
    cat = WikiCategory(category) if category else None
    return await store.search(q, category=cat)


@app.post("/ingest", response_model=IngestResult)
async def ingest_file(file: UploadFile = File(...), auto_compile: bool = True):
    """Upload and ingest a file. Parses to raw/, then compiles to wiki/."""
    if not file.filename:
        raise HTTPException(400, "No filename")

    # 1. Save to temp file for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    # 2. Define Archive Directory
    archive_dir = settings.raw_dir / "papers" / "originals"
    archive_dir.mkdir(parents=True, exist_ok=True)
    # Use original filename, but fallback to slug if needed
    archive_path = archive_dir / file.filename

    try:
        # Generate a meaningful Source Slug based on the ORIGINAL filename
        # This ensures the Wiki references a human-readable ID like "2507.22887v1"
        import re
        safe_name = re.sub(r'[^\w\u4e00-\u9fa5-]', '-', file.filename) # Keep Chinese/Alphanumeric
        safe_name = re.sub(r'-{2,}', '-', safe_name).strip('-').lower()
        # Remove extension if present
        if '.' in safe_name:
            safe_name = safe_name.rsplit('.', 1)[0]
        
        source_slug = safe_name
        print(f"[Ingest] Assigned Source Slug: {source_slug}")

        # Parse to raw/ (Parser returns a temp slug, which we will override)
        _, source_content = await DeterministicParser.parse(tmp_path, settings.raw_dir)
        
        # Override the slug in the Markdown content frontmatter to match our meaningful slug
        # This aligns the content ID with the file ID
        source_content = re.sub(r'slug:.*$', f'slug: {source_slug}', source_content, flags=re.MULTILINE)

        # Step 2: Archive the original PDF
        # Copy the processed temp file to the permanent archive location
        import shutil
        shutil.copy2(tmp_path, archive_path)
        print(f"[Ingest] Archived original file to: {archive_path}")

        # Step 3: Track source in DB
        ext = Path(file.filename).suffix.lower()
        source_type = {"pdf": "pdf", ".md": "markdown", ".docx": "docx", ".html": "html", ".txt": "text"}.get(ext, "unknown")
        
        wiki_created = 0
        wiki_updated = 0

        # Step 4: Compile to wiki (if auto_compile)
        if auto_compile and settings.llm_api_key:
            try:
                result = await compiler.compile(
                    source_slug=source_slug,
                    source_content=source_content,
                    source_title=file.filename,
                )
                wiki_created = len(result.new_pages)
                wiki_updated = len(result.updated_pages)

                # Update source record with wiki links and archive path
                await store.upsert_source(
                    slug=source_slug,
                    title=file.filename,
                    file_path=str(archive_path), # Point to the archived file
                    source_type=source_type,
                    status="completed",
                    wiki_pages=[p.slug for p in result.new_pages],
                )
            except Exception as e:
                print(f"[Ingest] Compilation failed: {e}")
                await store.upsert_source(
                    slug=source_slug,
                    title=file.filename,
                    file_path=str(archive_path),
                    source_type=source_type,
                    status="completed",
                    error=f"Compilation failed: {str(e)}",
                )
        else:
             # Just track it even if no compilation
             await store.upsert_source(
                    slug=source_slug,
                    title=file.filename,
                    file_path=str(archive_path),
                    source_type=source_type,
                    status="completed", # No compilation, but parsing success
                )

        return IngestResult(
            success=True,
            source_slug=source_slug,
            wiki_pages_created=wiki_created,
            wiki_pages_updated=wiki_updated,
        )

    except Exception as e:
        return IngestResult(success=False, error=str(e))
    finally:
        # Clean up the temporary file, keep the archive
        if tmp_path.exists():
            tmp_path.unlink()


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Query the wiki. Searches wiki pages, then synthesizes an answer.
    If save_analysis is True, saves the answer as a wiki analysis page.
    """
    # Step 1: Search wiki (extract keywords for better FTS5 matching)
    import re
    # Find words with 3+ chars, remove duplicates
    search_terms = list(set(re.findall(r'\b\w{3,}\b', request.question)))
    
    if not search_terms:
        return QueryResponse(
            answer="Your question didn't contain significant keywords to search for.",
            sources=[],
        )

    # Use OR logic for FTS5 to match any of the keywords
    search_query = " OR ".join(search_terms)
    results = await store.search(search_query, limit=5)

    if not results:
        return QueryResponse(
            answer="No relevant wiki pages found for this query.",
            sources=[],
        )

    # Step 2: Read relevant pages
    page_contents = []
    sources = []
    for r in results:
        page = await store.get_page(r.slug)
        if page:
            try:
                content = Path(page.file_path).read_text(encoding='utf-8')
            except Exception:
                content = ""
            page_contents.append(f"## {r.title}\n\n{content}")
            sources.append(r.slug)

    # Step 3: LLM synthesis (if API key available)
    if settings.llm_api_key:
        llm = LLMClient()
        prompt = f"""Answer the following question based ONLY on the wiki pages provided below.
Cite your sources using [[slug]] format.

Question: {request.question}

## Wiki Pages:

{chr(10).join(page_contents)}

Provide a clear, well-structured answer with citations."""

        try:
            answer = await llm.generate_text(
                prompt=prompt,
                system_prompt="You are a knowledge assistant. Answer based on the provided wiki pages only. Cite sources with [[slug]] format.",
            )
        except Exception:
            answer = f"Found {len(results)} relevant pages:\n\n" + "\n".join(
                f"- **{r.title}** (`{r.slug}`): {r.snippet}" for r in results
            )
    else:
        answer = f"Found {len(results)} relevant pages:\n\n" + "\n".join(
            f"- **{r.title}** (`{r.slug}`): {r.snippet}" for r in results
        )

    return QueryResponse(
        answer=answer,
        sources=sources,
    )


@app.post("/lint", response_model=LintReport)
async def lint(trigger: LintTrigger | None = None):
    """Run a lint check on the wiki."""
    if trigger is None:
        trigger = LintTrigger()
    report = await lint_engine.run()
    return report


@app.get("/lint/report")
async def lint_report_md():
    """Get the latest lint report as markdown."""
    report = await lint_engine.run()
    return await lint_engine.generate_report_md(report)


@app.get("/index")
async def get_index():
    """Get the wiki index."""
    index_path = settings.wiki_dir / "index.md"
    if not index_path.exists():
        return {"content": "", "entries": []}
    content = index_path.read_text(encoding='utf-8')
    entries = await store.build_index_entries()
    return {"content": content, "entries": [e.model_dump() for e in entries]}


@app.get("/log")
async def get_log():
    """Get the wiki activity log."""
    log_path = settings.wiki_dir / "log.md"
    if not log_path.exists():
        return {"content": ""}
    return {"content": log_path.read_text(encoding='utf-8')}


@app.get("/stats")
async def stats():
    """Get wiki statistics."""
    return await store.stats()


@app.get("/cost")
async def cost_summary(days: int = 30, recent: int = 20):
    """Get LLM token usage and cost summary."""
    summary = cost_monitor.get_summary(days=days)
    recent_entries = cost_monitor.get_recent_entries(limit=recent)
    return {"summary": summary, "recent": recent_entries}


@app.post("/recompile")
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
                response_format={"type": "json_schema", "json_schema": __import__("sagemate.pipeline.compiler", fromlist=["COMPILE_RESPONSE_SCHEMA"]).COMPILE_RESPONSE_SCHEMA},
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
