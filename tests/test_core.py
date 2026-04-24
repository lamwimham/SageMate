"""
Comprehensive tests for SageMate Core v0.2.

Tests cover:
- Store: CRUD, search, source tracking, stats
- Parser: Markdown, slug generation, frontmatter
- LintEngine: orphans, broken links, stale pages
- Watcher: file sync, category inference, wikilink extraction
- Compiler: LLM mock integration, page writing, index/log updates
"""

import json
import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import os

from src.sagemate.core.store import Store
from src.sagemate.core.watcher import WikiFileHandler
from src.sagemate.ingest.adapters.file_parser import DeterministicParser
from src.sagemate.pipeline.lint import LintEngine
from src.sagemate.pipeline.compiler import IncrementalCompiler
from src.sagemate.core.config import Settings
from src.sagemate.core.config import Settings
from src.sagemate.models import (
    LintIssue,
    LintIssueSeverity,
    LintIssueType,
    LintReport,
    LogEntry,
    LogEntryType,
    SearchResult,
    WikiCategory,
    WikiPage,
    WikiPageCreate,
    WikiPageUpdate,
)


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def db_path(temp_dir):
    return str(temp_dir / "test.db")


@pytest_asyncio.fixture
async def store(db_path):
    s = Store(db_path)
    await s.connect()
    yield s
    await s.close()


@pytest.fixture
def wiki_dir(temp_dir):
    d = temp_dir / "wiki"
    d.mkdir()
    (d / "entities").mkdir()
    (d / "concepts").mkdir()
    (d / "analyses").mkdir()
    (d / "sources").mkdir()
    return d


@pytest.fixture
def raw_dir(temp_dir):
    d = temp_dir / "raw"
    d.mkdir()
    (d / "articles").mkdir()
    (d / "papers").mkdir()
    (d / "notes").mkdir()
    return d


# ── Store Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_upsert_and_get(store):
    page = WikiPage(
        slug="test-page",
        title="Test Page",
        category=WikiCategory.CONCEPT,
        file_path="/wiki/concepts/test-page.md",
    )
    content = "# Test\n\nThis is a test page."
    await store.upsert_page(page, content)

    retrieved = await store.get_page("test-page")
    assert retrieved is not None
    assert retrieved.title == "Test Page"
    assert retrieved.category == WikiCategory.CONCEPT


@pytest.mark.asyncio
async def test_store_update_existing(store):
    page = WikiPage(
        slug="update-test",
        title="Original",
        category=WikiCategory.CONCEPT,
        file_path="/wiki/concepts/update-test.md",
    )
    await store.upsert_page(page, "Original content")

    # Update
    page.title = "Updated"
    await store.upsert_page(page, "Updated content")

    retrieved = await store.get_page("update-test")
    assert retrieved.title == "Updated"


@pytest.mark.asyncio
async def test_store_delete(store):
    page = WikiPage(
        slug="delete-me",
        title="Delete Me",
        category=WikiCategory.CONCEPT,
        file_path="/wiki/concepts/delete-me.md",
    )
    await store.upsert_page(page, "Delete me content")
    await store.delete_page("delete-me")

    retrieved = await store.get_page("delete-me")
    assert retrieved is None


@pytest.mark.asyncio
async def test_store_search(store):
    pages = [
        ("python-basics", "Python Basics", "Python is a programming language."),
        ("python-async", "Python Async", "Async programming in Python uses asyncio."),
        ("javascript-intro", "JavaScript Intro", "JavaScript is a web programming language."),
    ]
    for slug, title, content in pages:
        p = WikiPage(slug=slug, title=title, category=WikiCategory.CONCEPT,
                     file_path=f"/wiki/concepts/{slug}.md")
        await store.upsert_page(p, content)

    results = await store.search("Python")
    assert len(results) >= 2
    assert all("python" in r.slug for r in results)

    results = await store.search("web")
    assert len(results) >= 1
    assert results[0].slug == "javascript-intro"


@pytest.mark.asyncio
async def test_store_search_with_category(store):
    entity = WikiPage(slug="john-doe", title="John Doe", category=WikiCategory.ENTITY,
                      file_path="/wiki/entities/john-doe.md")
    await store.upsert_page(entity, "John Doe is a person.")

    concept = WikiPage(slug="python", title="Python", category=WikiCategory.CONCEPT,
                       file_path="/wiki/concepts/python.md")
    await store.upsert_page(concept, "Python is a language.")

    results = await store.search("person", category=WikiCategory.ENTITY)
    assert len(results) == 1
    assert results[0].slug == "john-doe"

    results = await store.search("person", category=WikiCategory.CONCEPT)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_store_list_pages(store):
    for i in range(3):
        p = WikiPage(
            slug=f"page-{i}",
            title=f"Page {i}",
            category=WikiCategory.CONCEPT,
            file_path=f"/wiki/concepts/page-{i}.md",
        )
        await store.upsert_page(p, f"Content {i}")

    all_pages = await store.list_pages()
    assert len(all_pages) == 3

    entity_pages = await store.list_pages(WikiCategory.ENTITY)
    assert len(entity_pages) == 0


@pytest.mark.asyncio
async def test_store_source_tracking(store):
    await store.upsert_source(
        slug="source-1",
        title="Test Article",
        file_path="/raw/articles/test-article.md",
        source_type="markdown",
        status="completed",
        wiki_pages=["concept-a", "entity-b"],
    )

    source = await store.get_source("source-1")
    assert source is not None
    assert source["title"] == "Test Article"
    assert source["status"] == "completed"
    assert "concept-a" in source["wiki_pages"]


@pytest.mark.asyncio
async def test_store_stats(store):
    for i in range(5):
        cat = WikiCategory.ENTITY if i < 2 else WikiCategory.CONCEPT
        p = WikiPage(slug=f"page-{i}", title=f"Page {i}", category=cat,
                     file_path=f"/wiki/{'entities' if i < 2 else 'concepts'}/page-{i}.md")
        await store.upsert_page(p, f"Content {i}")

    await store.upsert_source("src-1", "Source 1", "/raw/test.md", "markdown", "completed")

    stats = await store.stats()
    assert stats["wiki_pages"] == 5
    assert stats["sources"] == 1
    assert stats["by_category"]["entity"] == 2
    assert stats["by_category"]["concept"] == 3


@pytest.mark.asyncio
async def test_store_batch_create(store):
    pages = [
        WikiPageCreate(slug="page-a", title="Page A", category=WikiCategory.CONCEPT, content="Content A"),
        WikiPageCreate(slug="page-b", title="Page B", category=WikiCategory.ENTITY, content="Content B"),
    ]
    contents = {"page-a": "Content A", "page-b": "Content B"}

    for pc in pages:
        page = WikiPage(
            slug=pc.slug,
            title=pc.title,
            category=pc.category,
            file_path=f"/wiki/{'concepts' if pc.category == WikiCategory.CONCEPT else 'entities'}/{pc.slug}.md",
        )
        await store.upsert_page(page, contents[pc.slug])

    assert await store.get_page("page-a") is not None
    assert await store.get_page("page-b") is not None


# ── Parser Tests ───────────────────────────────────────────────

def test_slug_generation():
    assert DeterministicParser.generate_slug("Hello World") == "hello-world"
    assert DeterministicParser.generate_slug("My_Test_Title") == "my-test-title"
    assert DeterministicParser.generate_slug("  spaced  out  ") == "spaced-out"
    assert DeterministicParser.generate_slug("Special!@#Chars") == "specialchars"


def test_slug_generation_chinese():
    slug = DeterministicParser.generate_slug("人工智能")
    assert "人工智能" in slug


def test_slug_generation_empty():
    slug = DeterministicParser.generate_slug("")
    assert slug.startswith("untitled-")


def test_slug_generation_with_prefix():
    slug = DeterministicParser.generate_slug("Test Page", prefix="raw")
    assert slug.startswith("raw-")
    assert "test-page" in slug


@pytest.mark.asyncio
async def test_parse_markdown(temp_dir):
    md_content = """# Raw Document

This is some raw content about AI.
"""
    input_path = temp_dir / "input.md"
    input_path.write_text(md_content)

    target_dir = temp_dir / "kb"
    slug, content = await DeterministicParser.parse_markdown(input_path, target_dir)

    assert "raw" in slug
    # parse_markdown is a pure function — writing is caller's responsibility
    assert not target_dir.exists() or not any(target_dir.iterdir())
    assert "---" in content
    assert "title:" in content


@pytest.mark.asyncio
async def test_parse_markdown_with_frontmatter(temp_dir):
    md_content = """---
title: 'Custom Title'
slug: custom-slug
---

Content here.
"""
    input_path = temp_dir / "input.md"
    input_path.write_text(md_content)

    target_dir = temp_dir / "kb"
    slug, content = await DeterministicParser.parse_markdown(input_path, target_dir)

    assert "custom-title" in slug
    assert "Custom Title" in content


# ── Watcher Tests ──────────────────────────────────────────────

def test_parse_frontmatter():
    handler = WikiFileHandler.__new__(WikiFileHandler)
    handler.store = None
    handler.wiki_dir = Path("/tmp")
    handler._debounce_timers = {}
    handler._debounce_ms = 500

    content = """---
title: 'Test Page'
slug: test-page
category: concept
tags: ["test", "demo"]
---

Body content here.
"""
    meta = handler._parse_frontmatter(content)
    assert meta["title"] == "Test Page"
    assert meta["slug"] == "test-page"
    assert meta["category"] == "concept"


def test_extract_wikilinks():
    handler = WikiFileHandler.__new__(WikiFileHandler)
    handler.store = None
    handler.wiki_dir = Path("/tmp")
    handler._debounce_timers = {}
    handler._debounce_ms = 500

    content = "This links to [[python]] and also [[async-programming]]."
    links = handler._extract_wikilinks(content)
    assert links == ["python", "async-programming"]


def test_infer_category():
    handler = WikiFileHandler.__new__(WikiFileHandler)
    handler.store = None
    handler.wiki_dir = Path("/tmp")
    handler._debounce_timers = {}
    handler._debounce_ms = 500

    assert handler._infer_category(Path("/wiki/entities/test.md"), "concept") == WikiCategory.ENTITY
    assert handler._infer_category(Path("/wiki/concepts/test.md"), "concept") == WikiCategory.CONCEPT
    assert handler._infer_category(Path("/wiki/analyses/test.md"), "concept") == WikiCategory.ANALYSIS
    assert handler._infer_category(Path("/wiki/sources/test.md"), "concept") == WikiCategory.SOURCE
    assert handler._infer_category(Path("/wiki/concepts/test.md"), "entity") == WikiCategory.ENTITY


def test_parse_list():
    handler = WikiFileHandler.__new__(WikiFileHandler)
    handler.store = None
    handler.wiki_dir = Path("/tmp")
    handler._debounce_timers = {}
    handler._debounce_ms = 500

    assert handler._parse_list('["a", "b"]') == ["a", "b"]
    assert handler._parse_list("[]") == []
    assert handler._parse_list("invalid") == []


# ── LintEngine Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_lint_orphan_pages(store, wiki_dir):
    # Create a page with no inbound links
    page = WikiPage(
        slug="orphan-page",
        title="Orphan Page",
        category=WikiCategory.CONCEPT,
        file_path=str(wiki_dir / "concepts" / "orphan-page.md"),
        inbound_links=[],
        outbound_links=[],
    )
    await store.upsert_page(page, "# Orphan\n\nNo links here.")

    engine = LintEngine(store, wiki_dir)
    report = await engine.run()

    orphan_issues = [i for i in report.issues if i.issue_type == LintIssueType.ORPHAN_PAGE]
    assert len(orphan_issues) >= 1
    assert orphan_issues[0].page_slug == "orphan-page"


@pytest.mark.asyncio
async def test_lint_broken_links(store, wiki_dir):
    page = WikiPage(
        slug="page-with-broken-link",
        title="Broken Link Page",
        category=WikiCategory.CONCEPT,
        file_path=str(wiki_dir / "concepts" / "page-with-broken-link.md"),
        outbound_links=["non-existent-page"],
    )
    await store.upsert_page(page, "This links to [[non-existent-page]].")

    engine = LintEngine(store, wiki_dir)
    report = await engine.run()

    broken_issues = [i for i in report.issues if i.issue_type == LintIssueType.BROKEN_LINK]
    assert len(broken_issues) >= 1
    assert broken_issues[0].page_slug == "page-with-broken-link"


@pytest.mark.asyncio
async def test_lint_stale_pages(store, wiki_dir):
    stale_date = datetime.now() - timedelta(days=60)
    page = WikiPage(
        slug="stale-page",
        title="Stale Page",
        category=WikiCategory.CONCEPT,
        file_path=str(wiki_dir / "concepts" / "stale-page.md"),
        updated_at=stale_date,
    )
    await store.upsert_page(page, "# Old content")

    engine = LintEngine(store, wiki_dir)
    report = await engine.run()

    stale_issues = [i for i in report.issues if i.issue_type == LintIssueType.STALE_CLAIM]
    assert len(stale_issues) >= 1
    assert stale_issues[0].page_slug == "stale-page"


@pytest.mark.asyncio
async def test_lint_no_issues(store, wiki_dir):
    """Test that a healthy wiki has no issues."""
    page = WikiPage(
        slug="healthy-page",
        title="Healthy Page",
        category=WikiCategory.CONCEPT,
        file_path=str(wiki_dir / "concepts" / "healthy-page.md"),
        inbound_links=["other-page"],
        outbound_links=["other-page"],
        updated_at=datetime.now(),
    )
    await store.upsert_page(page, "# Healthy\n\nLinks to [[other-page]].")

    other = WikiPage(
        slug="other-page",
        title="Other Page",
        category=WikiCategory.CONCEPT,
        file_path=str(wiki_dir / "concepts" / "other-page.md"),
        inbound_links=["healthy-page"],
    )
    await store.upsert_page(other, "# Other\n\nReferenced by healthy page.")

    engine = LintEngine(store, wiki_dir)
    report = await engine.run()

    # May have contradiction issues from slug similarity
    broken = [i for i in report.issues if i.issue_type in (
        LintIssueType.BROKEN_LINK, LintIssueType.ORPHAN_PAGE, LintIssueType.STALE_CLAIM
    )]
    assert len(broken) == 0


@pytest.mark.asyncio
async def test_lint_report_md(store, wiki_dir):
    engine = LintEngine(store, wiki_dir)
    report = LintReport()
    report.total_pages_scanned = 5
    report.issues.append(LintIssue(
        issue_type=LintIssueType.ORPHAN_PAGE,
        severity=LintIssueSeverity.LOW,
        page_slug="test",
        description="Orphan page",
        suggestion="Add links",
    ))

    md = await engine.generate_report_md(report)
    assert "Orphan" in md
    assert "LOW" in md
    assert "test" in md


# ── LogEntry Tests ─────────────────────────────────────────────

def test_log_entry_format():
    entry = LogEntry(
        entry_type=LogEntryType.INGEST,
        title="Test Article",
        details="Ingested successfully.",
        affected_pages=["page-a", "page-b"],
    )
    md = entry.format_md()
    assert "[ingest]" in md.lower() or "ingest" in md.lower()
    assert "Test Article" in md
    assert "`page-a`" in md
    assert "`page-b`" in md


# ── Model Tests ────────────────────────────────────────────────

def test_wiki_page_model():
    page = WikiPage(
        slug="test",
        title="Test",
        category=WikiCategory.CONCEPT,
        file_path="/wiki/concepts/test.md",
    )
    assert page.slug == "test"
    assert page.word_count == 0
    assert page.inbound_links == []


def test_wiki_page_create_model():
    pc = WikiPageCreate(
        slug="new-page",
        title="New Page",
        category=WikiCategory.ENTITY,
        content="Content",
        tags=["tag1"],
        sources=["source-1"],
        outbound_links=["related-page"],
    )
    assert pc.category == WikiCategory.ENTITY
    assert pc.tags == ["tag1"]


def test_search_result_model():
    r = SearchResult(slug="test", title="Test", category=WikiCategory.CONCEPT,
                     snippet="result", score=0.5)
    assert r.slug == "test"
    assert r.score == 0.5


def test_wiki_category_enum():
    assert WikiCategory.ENTITY.value == "entity"
    assert WikiCategory.CONCEPT.value == "concept"
    assert WikiCategory.ANALYSIS.value == "analysis"
    assert WikiCategory.SOURCE.value == "source"


# ── Compiler Tests ─────────────────────────────────────────────

def test_compiler_parsing():
    """Test that _parse_compile_result correctly extracts Source Archive and Wiki Pages."""
    from src.sagemate.pipeline.compiler import IncrementalCompiler
    
    # Mock LLM response data matching the new schema
    mock_llm_response = {
        "source_archive": {
            "slug": "test-paper",
            "title": "Test Paper",
            "summary": "This is a test paper about AI.",
            "key_takeaways": ["Takeaway 1", "Takeaway 2"],
            "extracted_concepts": ["concept-a", "concept-b"]
        },
        "new_pages": [
            {
                "slug": "concept-a",
                "title": "Concept A",
                "category": "concept",
                "content": "Content for A",
                "source_pages": [1, 2]
            }
        ]
    }
    
    compiler = IncrementalCompiler.__new__(IncrementalCompiler)
    result = compiler._parse_compile_result(mock_llm_response, source_slug="test-paper")
    
    # Verify Source Archive
    assert result.source_archive is not None
    assert result.source_archive.title == "Test Paper"
    assert "Takeaway 1" in result.source_archive.key_takeaways
    
    # Verify Wiki Pages
    assert len(result.new_pages) == 1
    assert result.new_pages[0].slug == "concept-a"
    assert result.new_pages[0].source_pages == [1, 2]

@pytest.mark.asyncio
async def test_compiler_writing(store, wiki_dir):
    """Test that _write_pages creates both Source Archive and Wiki Pages on disk."""
    from src.sagemate.pipeline.compiler import IncrementalCompiler
    from src.sagemate.models import CompileResult, SourceArchive, WikiPageCreate
    
    # Mock a compile result
    result = CompileResult(
        source_archive=SourceArchive(
            slug="mock-paper",
            title="Mock Paper",
            summary="A summary",
            key_takeaways=["Point 1"],
            extracted_concepts=["page-1"]
        ),
        new_pages=[
            WikiPageCreate(
                slug="page-1",
                title="Page 1",
                category=WikiCategory.CONCEPT,
                content="Content 1"
            )
        ]
    )
    
    # Create mock settings for the compiler
    settings = Settings(data_dir=wiki_dir.parent)
    settings.ensure_dirs()
    
    compiler = IncrementalCompiler(store=store, wiki_dir=wiki_dir, settings_obj=settings)
    
    # Write pages
    await compiler._write_pages(result)
    
    # Verify Source Archive was written
    archive_path = wiki_dir / "sources" / "mock-paper.md"
    assert archive_path.exists()
    content = archive_path.read_text()
    assert "# 📄 Mock Paper" in content
    assert "[[page-1]]" in content
    
    # Verify Wiki Page was written
    page_path = wiki_dir / "concepts" / "page-1.md"
    assert page_path.exists()
    assert "slug: page-1" in page_path.read_text()

