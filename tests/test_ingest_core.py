"""
Tests for refactored ingest core components.

Covers:
- EventBus: pub/sub, failure isolation, unsubscribe
- IngestTaskManager: lifecycle, event publishing, stale detection
- FileParser: pure-function behavior (no side effects)
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from src.sagemate.core.event_bus import EventBus
from src.sagemate.ingest.task_manager import IngestTaskManager
from src.sagemate.ingest.adapters.file_parser import DeterministicParser
from src.sagemate.ingest.compiler.unit_of_work import WikiWriteUnit
from src.sagemate.models import IngestResult, IngestTaskStatus


# ── EventBus Fixtures ──────────────────────────────────────────

@pytest_asyncio.fixture
async def event_bus():
    bus = EventBus()
    yield bus


# ── EventBus Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_bus_publish_no_subscribers(event_bus):
    """Publishing with no subscribers should not raise."""
    await event_bus.publish("test.event", {"msg": "hello"})


@pytest.mark.asyncio
async def test_event_bus_single_subscriber(event_bus):
    """A subscriber should receive published events."""
    received = []

    async def handler(payload):
        received.append(payload)

    await event_bus.subscribe("ingest.progress", handler)
    await event_bus.publish("ingest.progress", {"task_id": "abc", "step": 1})

    assert len(received) == 1
    assert received[0]["task_id"] == "abc"


@pytest.mark.asyncio
async def test_event_bus_multiple_subscribers(event_bus):
    """All subscribers should receive the event."""
    received_a = []
    received_b = []

    async def handler_a(payload):
        received_a.append(payload)

    async def handler_b(payload):
        received_b.append(payload)

    await event_bus.subscribe("ingest.progress", handler_a)
    await event_bus.subscribe("ingest.progress", handler_b)
    await event_bus.publish("ingest.progress", {"task_id": "xyz"})

    assert len(received_a) == 1
    assert len(received_b) == 1


@pytest.mark.asyncio
async def test_event_bus_unsubscribe(event_bus):
    """After unsubscribe, handler should not receive events."""
    received = []

    async def handler(payload):
        received.append(payload)

    await event_bus.subscribe("ingest.progress", handler)
    await event_bus.publish("ingest.progress", {"task_id": "1"})
    assert len(received) == 1

    await event_bus.unsubscribe("ingest.progress", handler)
    await event_bus.publish("ingest.progress", {"task_id": "2"})
    assert len(received) == 1  # Still 1 — second event ignored


@pytest.mark.asyncio
async def test_event_bus_handler_failure_isolation(event_bus):
    """One failing handler should not prevent others from running."""
    received_good = []

    async def bad_handler(payload):
        raise RuntimeError("I am bad")

    async def good_handler(payload):
        received_good.append(payload)

    await event_bus.subscribe("ingest.progress", bad_handler)
    await event_bus.subscribe("ingest.progress", good_handler)

    # Should not raise despite bad_handler failing
    await event_bus.publish("ingest.progress", {"task_id": "t1"})

    assert len(received_good) == 1


# ── IngestTaskManager Fixtures ─────────────────────────────────

@pytest_asyncio.fixture
async def task_manager(event_bus):
    mock_store = AsyncMock()
    tm = IngestTaskManager(event_bus=event_bus, store=mock_store)
    yield tm


# ── IngestTaskManager Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_task_manager_create_task(task_manager):
    """Creating a task should return a valid ID and store it."""
    task_id = task_manager.create_task()
    assert len(task_id) == 12

    task = task_manager.get_task(task_id)
    assert task is not None
    assert task.status == IngestTaskStatus.QUEUED
    assert task.step == 0


@pytest.mark.asyncio
async def test_task_manager_get_missing_task(task_manager):
    """Getting a non-existent task should return None."""
    assert task_manager.get_task("nonexistent") is None


@pytest.mark.asyncio
async def test_task_manager_list_tasks(task_manager):
    """list_tasks should return recent tasks sorted by created_at desc."""
    t1 = task_manager.create_task()
    t2 = task_manager.create_task()

    tasks = task_manager.list_tasks(limit=10)
    assert len(tasks) == 2
    # Most recent first
    assert tasks[0]["task_id"] == t2
    assert tasks[1]["task_id"] == t1


@pytest.mark.asyncio
async def test_task_manager_update_progress_publishes_event(task_manager, event_bus):
    """update_progress should publish an event to the bus."""
    received = []

    async def handler(payload):
        received.append(payload)

    await event_bus.subscribe("ingest.progress", handler)

    task_id = task_manager.create_task()
    await task_manager.update_progress(task_id, IngestTaskStatus.PARSING, 1, "parsing...")

    assert len(received) == 1
    assert received[0]["task_id"] == task_id
    assert received[0]["status"] == "parsing"
    assert received[0]["step"] == 1

    # Task state should also be updated
    task = task_manager.get_task(task_id)
    assert task.status == IngestTaskStatus.PARSING
    assert task.message == "parsing..."


@pytest.mark.asyncio
async def test_task_manager_set_result_publishes_event(task_manager, event_bus):
    """set_result should publish a 'completed' event."""
    received = []

    async def handler(payload):
        received.append(payload)

    await event_bus.subscribe("ingest.progress", handler)

    task_id = task_manager.create_task()
    result = IngestResult(
        success=True,
        source_slug="test-doc",
        wiki_pages_created=3,
        wiki_pages_updated=0,
    )
    await task_manager.set_result(task_id, result)

    assert len(received) == 1
    assert received[0]["type"] == "completed"
    assert received[0]["result"]["wiki_pages_created"] == 3

    task = task_manager.get_task(task_id)
    assert task.status == IngestTaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_task_manager_set_error_publishes_event(task_manager, event_bus):
    """set_error should publish a 'failed' event."""
    received = []

    async def handler(payload):
        received.append(payload)

    await event_bus.subscribe("ingest.progress", handler)

    task_id = task_manager.create_task()
    await task_manager.set_error(task_id, "something broke")

    assert len(received) == 1
    assert received[0]["type"] == "failed"
    assert "something broke" in received[0]["message"]

    task = task_manager.get_task(task_id)
    assert task.status == IngestTaskStatus.FAILED


@pytest.mark.asyncio
async def test_task_manager_stale_detection(task_manager):
    """Tasks stuck >10 min should be auto-marked as failed on get_task."""
    task_id = task_manager.create_task()
    task = task_manager.get_task(task_id)

    # Manually set updated_at to 11 minutes ago
    old_time = (datetime.now() - timedelta(seconds=660)).isoformat()
    task.updated_at = old_time

    # Re-fetch triggers stale detection
    task = task_manager.get_task(task_id)
    assert task.status == IngestTaskStatus.FAILED
    assert "超时" in task.message


@pytest.mark.asyncio
async def test_task_manager_update_progress_missing_task(task_manager):
    """Updating progress for a missing task should be a no-op."""
    # Should not raise
    await task_manager.update_progress("missing", IngestTaskStatus.PARSING, 1, "...")


@pytest.mark.asyncio
async def test_task_manager_submit_compile(task_manager, event_bus):
    """submit_compile should create a task and return its ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "test.md"
        archive_path.write_text("# Test")

        task_id = await task_manager.submit_compile(
            source_slug="test-slug",
            source_content="hello world",
            source_title="Test",
            archive_path=archive_path,
            source_type="text",
            auto_compile=False,  # Don't actually call LLM
        )

        assert len(task_id) == 12
        task = task_manager.get_task(task_id)
        assert task.status == IngestTaskStatus.COMPLETED
        assert task.result is not None
        assert task.result.wiki_pages_created == 0


# ── FileParser Tests (post-purification) ───────────────────────

@pytest.mark.asyncio
async def test_parse_markdown_no_side_effects():
    """After Phase 1 refactor, parse_markdown should NOT write files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.md"
        input_path.write_text("# Hello\n\nWorld.")
        target_dir = Path(tmpdir) / "kb"

        slug, content = await DeterministicParser.parse_markdown(input_path, target_dir)

        # Should return valid content
        assert "---" in content
        assert "title:" in content

        # Should NOT create files in target_dir
        assert not target_dir.exists() or not any(target_dir.iterdir())


@pytest.mark.asyncio
async def test_parse_pdf_no_side_effects():
    """parse_pdf should NOT write files and should raise on invalid PDF."""
    from src.sagemate.ingest.adapters.pdf_strategies import PDFParseError

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy PDF file (not a real PDF)
        input_path = Path(tmpdir) / "dummy.pdf"
        input_path.write_text("Not a real PDF")
        target_dir = Path(tmpdir) / "output"

        # Invalid PDF should raise PDFParseError (fail-fast)
        with pytest.raises(PDFParseError):
            await DeterministicParser.parse_pdf(input_path, target_dir)

        # Should NOT create files in target_dir
        assert not (target_dir / "papers").exists()


@pytest.mark.asyncio
async def test_parse_html_no_side_effects():
    """parse_html should NOT write files when target_dir is provided."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.html"
        input_path.write_text("<html><body><h1>Hello</h1><p>World</p></body></html>")
        target_dir = Path(tmpdir) / "output"

        slug, content = await DeterministicParser.parse_html(input_path, target_dir)

        # Should return markdown content
        assert "Hello" in content

        # Should NOT create files in target_dir
        assert not (target_dir / "articles").exists()


@pytest.mark.asyncio
async def test_parse_docx_no_side_effects():
    """parse_docx should NOT write files when target_dir is provided."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal docx-like zip (or just test that it tries to read)
        # Since we may not have python-docx installed, we test the ImportError path
        input_path = Path(tmpdir) / "test.docx"
        input_path.write_text("fake docx")
        target_dir = Path(tmpdir) / "output"

        try:
            slug, content = await DeterministicParser.parse_docx(input_path, target_dir)
            # If python-docx is installed, content should be returned
            assert isinstance(content, str)
        except (RuntimeError, Exception) as e:
            # Expected if python-docx is not installed or file is invalid
            pass

        # Should NOT create files in target_dir regardless
        assert not target_dir.exists() or not any(target_dir.iterdir())


# ── WikiWriteUnit Tests (Unit of Work) ─────────────────────────

@pytest.mark.asyncio
async def test_wiki_write_unit_commit_writes_files():
    """WikiWriteUnit should write all scheduled files on commit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = Path(tmpdir) / "wiki"
        uow = WikiWriteUnit(wiki_dir)

        uow.schedule_write(Path("sources/test.md"), "# Source")
        uow.schedule_write(Path("concepts/foo.md"), "# Foo")
        await uow.commit()

        assert (wiki_dir / "sources" / "test.md").exists()
        assert (wiki_dir / "concepts" / "foo.md").exists()
        assert (wiki_dir / "sources" / "test.md").read_text() == "# Source"


@pytest.mark.asyncio
async def test_wiki_write_unit_commit_runs_db_ops():
    """WikiWriteUnit should run DB operations after files are committed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = Path(tmpdir) / "wiki"
        uow = WikiWriteUnit(wiki_dir)

        db_calls = []
        async def db_op():
            db_calls.append(1)

        uow.schedule_write(Path("test.md"), "content")
        uow.schedule_db(db_op)
        await uow.commit()

        assert len(db_calls) == 1


@pytest.mark.asyncio
async def test_wiki_write_unit_rollback_on_failure():
    """If a DB op fails before file replace, targets should remain untouched."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = Path(tmpdir) / "wiki"
        uow = WikiWriteUnit(wiki_dir)

        uow.schedule_write(Path("test.md"), "content")

        async def failing_db():
            raise RuntimeError("DB failed!")

        uow.schedule_db(failing_db)

        with pytest.raises(RuntimeError, match="DB failed!"):
            await uow.commit()

        # Target file should NOT exist (replace never ran)
        assert not (wiki_dir / "test.md").exists()
        # No temp files left behind
        assert not any(wiki_dir.rglob(".tmp_*"))


@pytest.mark.asyncio
async def test_wiki_write_unit_overwrites_existing():
    """Commit should atomically overwrite existing files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = Path(tmpdir) / "wiki"
        (wiki_dir / "sources").mkdir(parents=True)
        (wiki_dir / "sources" / "old.md").write_text("old content")

        uow = WikiWriteUnit(wiki_dir)
        uow.schedule_write(Path("sources/old.md"), "new content")
        await uow.commit()

        assert (wiki_dir / "sources" / "old.md").read_text() == "new content"


@pytest.mark.asyncio
async def test_wiki_write_unit_empty_commit():
    """Commit with no scheduled operations should be a no-op."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = Path(tmpdir) / "wiki"
        uow = WikiWriteUnit(wiki_dir)
        await uow.commit()
        assert not wiki_dir.exists() or not any(wiki_dir.iterdir())


# ── CompileStrategy Tests ──────────────────────────────────────

from src.sagemate.ingest.compiler.strategies import (
    CompileStrategyFactory,
    SinglePassStrategy,
    ChunkedStrategy,
    DeepCompileStrategy,
)
from src.sagemate.models import CompileResult, SourceArchive, WikiPageCreate, WikiCategory


def test_strategy_factory_selects_single_pass():
    """Short documents (< 5K chars) should use SinglePassStrategy."""
    store = None
    with tempfile.TemporaryDirectory() as tmpdir:
        strategy = CompileStrategyFactory.create("x" * 1000, store, Path(tmpdir))
        assert isinstance(strategy, SinglePassStrategy)


def test_strategy_factory_selects_chunked():
    """Medium documents (5K ~ 50K chars) should use ChunkedStrategy."""
    store = None
    with tempfile.TemporaryDirectory() as tmpdir:
        strategy = CompileStrategyFactory.create("x" * 10000, store, Path(tmpdir))
        assert isinstance(strategy, ChunkedStrategy)


def test_strategy_factory_selects_deep_compile():
    """Long documents (> 50K chars) should use DeepCompileStrategy."""
    store = None
    with tempfile.TemporaryDirectory() as tmpdir:
        strategy = CompileStrategyFactory.create("x" * 60000, store, Path(tmpdir))
        assert isinstance(strategy, DeepCompileStrategy)


def test_chunked_strategy_split_by_headings():
    """Chunks should split by markdown headings when available."""
    strategy = ChunkedStrategy.__new__(ChunkedStrategy)
    content = "# Intro\nSome text.\n# Chapter 1\nMore text.\n# Chapter 2\nEven more."
    chunks = strategy._split_into_chunks(content, chunk_size=50)
    assert len(chunks) >= 2
    assert "# Intro" in chunks[0]


def test_chunked_strategy_split_by_paragraphs_fallback():
    """When no headings, fallback to paragraph-based splitting with overlap."""
    strategy = ChunkedStrategy.__new__(ChunkedStrategy)
    content = "Paragraph one.\n\nParagraph two.\n\nParagraph three.\n\n" + "word " * 5000
    chunks = strategy._split_into_chunks(content, chunk_size=1000)
    assert len(chunks) > 1
    total = sum(len(c) for c in chunks)
    # Due to overlap, total may exceed original, but each chunk should be <= chunk_size + overlap_margin
    for c in chunks:
        assert len(c) <= 1200  # chunk_size + some margin


def test_chunked_strategy_merge_dedupes_slugs():
    """Merging chunk results should deduplicate pages by slug."""
    strategy = ChunkedStrategy.__new__(ChunkedStrategy)

    r1 = CompileResult()
    r1.new_pages = [
        WikiPageCreate(slug="page-a", title="Page A", category=WikiCategory.CONCEPT, content="A1"),
        WikiPageCreate(slug="page-b", title="Page B", category=WikiCategory.CONCEPT, content="B1"),
    ]
    r2 = CompileResult()
    r2.new_pages = [
        WikiPageCreate(slug="page-a", title="Page A", category=WikiCategory.CONCEPT, content="A2"),
        WikiPageCreate(slug="page-c", title="Page C", category=WikiCategory.CONCEPT, content="C1"),
    ]

    merged = strategy._merge_results([r1, r2], source_slug="test")
    assert len(merged.new_pages) == 3
    slugs = {p.slug for p in merged.new_pages}
    assert slugs == {"page-a", "page-b", "page-c"}


@pytest.mark.asyncio
async def test_single_pass_strategy_execution():
    """SinglePassStrategy should call LLM and return parsed CompileResult."""

    class MockLLM:
        async def generate_structured(self, prompt, system_prompt, response_format):
            return {
                "source_archive": {
                    "slug": "test-doc",
                    "title": "Test Doc",
                    "summary": "A summary",
                    "key_takeaways": ["Point 1"],
                    "extracted_concepts": ["concept-x"],
                },
                "new_pages": [
                    {
                        "slug": "concept-x",
                        "title": "Concept X",
                        "category": "concept",
                        "content": "Content here",
                        "source_pages": [1],
                    }
                ],
            }

    class FakeStore:
        async def build_index_entries(self):
            return []

        async def upsert_page(self, page, content, searchable_content=None):
            pass

    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = Path(tmpdir) / "wiki"
        strategy = SinglePassStrategy(
            store=FakeStore(),
            wiki_dir=wiki_dir,
            llm_client=MockLLM(),
        )
        result = await strategy.compile(
            source_slug="test-doc",
            source_content="Short content",
            source_title="Test Doc",
        )

    assert result.source_archive is not None
    assert result.source_archive.title == "Test Doc"
    assert len(result.new_pages) == 1
    assert result.new_pages[0].slug == "concept-x"


@pytest.mark.asyncio
async def test_single_pass_strategy_progress_callback():
    """Progress callback should receive step updates."""

    class MockLLM:
        async def generate_structured(self, prompt, system_prompt, response_format):
            return {
                "source_archive": None,
                "new_pages": [],
            }

    class FakeStore:
        async def build_index_entries(self):
            return []

        async def upsert_page(self, page, content, searchable_content=None):
            pass

    steps = []

    async def track(step, msg):
        steps.append(step)

    with tempfile.TemporaryDirectory() as tmpdir:
        strategy = SinglePassStrategy(
            store=FakeStore(),
            wiki_dir=Path(tmpdir) / "wiki",
            llm_client=MockLLM(),
        )
        await strategy.compile(
            source_slug="s",
            source_content="c",
            source_title="t",
            progress_callback=track,
        )

    assert "reading_context" in steps
    assert "calling_llm" in steps
    assert "writing_pages" in steps
    assert "updating_index" in steps


# ── Per-Source Lock Tests ──────────────────────────────────────

from unittest.mock import AsyncMock, patch


def test_task_manager_has_semaphore_and_source_locks(event_bus):
    """Constructor should set up semaphore and per-source lock dict."""
    mock_store = AsyncMock()
    tm = IngestTaskManager(event_bus=event_bus, store=mock_store, max_concurrent_compiles=3)
    assert tm._compile_semaphore._value == 3
    assert tm._source_locks == {}


@pytest.mark.asyncio
async def test_same_source_slug_serializes(event_bus):
    """Two compiles with the same source_slug must not overlap."""
    mock_store = AsyncMock()
    tm = IngestTaskManager(event_bus=event_bus, store=mock_store, max_concurrent_compiles=3)

    first_entered = asyncio.Event()
    first_can_exit = asyncio.Event()
    second_entered = asyncio.Event()

    async def mock_compile(*args, **kwargs):
        source_slug = kwargs.get("source_slug")
        if source_slug == "same-source":
            # This mock is called for both tasks; use first_entered to distinguish
            if not first_entered.is_set():
                first_entered.set()
                await first_can_exit.wait()
            else:
                second_entered.set()
        return CompileResult()

    with patch("src.sagemate.ingest.compiler.compiler.IncrementalCompiler") as MockCompiler:
        MockCompiler.return_value.compile = mock_compile

        t1 = asyncio.create_task(
            tm.run_compile("t1", "same-source", "c", "title", Path("/tmp/a"), "text")
        )
        await asyncio.wait_for(first_entered.wait(), timeout=0.5)

        t2 = asyncio.create_task(
            tm.run_compile("t2", "same-source", "c", "title", Path("/tmp/b"), "text")
        )
        await asyncio.sleep(0.05)
        assert not second_entered.is_set(), "Second compile should be blocked by per-source lock"

        first_can_exit.set()
        await asyncio.gather(t1, t2)
        assert second_entered.is_set(), "Second compile should have run after first released lock"


@pytest.mark.asyncio
async def test_different_sources_run_concurrently(event_bus):
    """Two compiles with different source_slugs should overlap."""
    mock_store = AsyncMock()
    tm = IngestTaskManager(event_bus=event_bus, store=mock_store, max_concurrent_compiles=3)

    entered_count = 0
    gate = asyncio.Event()
    both_inside = asyncio.Event()

    async def mock_compile(*args, **kwargs):
        nonlocal entered_count
        entered_count += 1
        if entered_count == 2:
            both_inside.set()
        await gate.wait()
        return CompileResult()

    with patch("src.sagemate.ingest.compiler.compiler.IncrementalCompiler") as MockCompiler:
        MockCompiler.return_value.compile = mock_compile

        t1 = asyncio.create_task(
            tm.run_compile("t1", "source-a", "c", "title", Path("/tmp/a"), "text")
        )
        t2 = asyncio.create_task(
            tm.run_compile("t2", "source-b", "c", "title", Path("/tmp/b"), "text")
        )

        await asyncio.wait_for(both_inside.wait(), timeout=0.5)
        assert entered_count == 2, "Different sources should compile concurrently"

        gate.set()
        await asyncio.gather(t1, t2)


@pytest.mark.asyncio
async def test_global_semaphore_limits_concurrency(event_bus):
    """Semaphore should cap total concurrent compiles."""
    mock_store = AsyncMock()
    tm = IngestTaskManager(event_bus=event_bus, store=mock_store, max_concurrent_compiles=1)

    entered_count = 0
    gate = asyncio.Event()
    both_inside = asyncio.Event()

    async def mock_compile(*args, **kwargs):
        nonlocal entered_count
        entered_count += 1
        if entered_count == 2:
            both_inside.set()
        await gate.wait()
        return CompileResult()

    with patch("src.sagemate.ingest.compiler.compiler.IncrementalCompiler") as MockCompiler:
        MockCompiler.return_value.compile = mock_compile

        t1 = asyncio.create_task(
            tm.run_compile("t1", "source-a", "c", "title", Path("/tmp/a"), "text")
        )
        t2 = asyncio.create_task(
            tm.run_compile("t2", "source-b", "c", "title", Path("/tmp/b"), "text")
        )

        # With max_concurrent=1, both_inside should NEVER fire
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(both_inside.wait(), timeout=0.1)

        assert entered_count == 1, "Only one compile should be active at a time"
        gate.set()
        await asyncio.gather(t1, t2)
        assert entered_count == 2


def test_format_index_context_truncates():
    """_format_index_context should respect compiler_max_wiki_context_chars."""
    from src.sagemate.ingest.compiler.strategies import SinglePassStrategy
    from src.sagemate.models import IndexEntry, WikiCategory
    from datetime import datetime

    strategy = SinglePassStrategy.__new__(SinglePassStrategy)
    strategy.cfg = type("Cfg", (), {"compiler_max_wiki_context_chars": 80})()

    entries = [
        IndexEntry(slug=f"page-{i}", title=f"Title {i}", category=WikiCategory.CONCEPT,
                   summary="", last_updated=datetime.now(), source_count=0, inbound_count=0)
        for i in range(10)
    ]

    result = strategy._format_index_context(entries)
    assert "Existing wiki pages:" in result
    assert "omitted for brevity" in result
    assert len(result) <= 80 + 50  # some margin for the truncation note


def test_format_index_context_empty():
    """Empty wiki should return placeholder."""
    from src.sagemate.ingest.compiler.strategies import SinglePassStrategy

    strategy = SinglePassStrategy.__new__(SinglePassStrategy)
    strategy.cfg = type("Cfg", (), {"compiler_max_wiki_context_chars": 8000})()

    result = strategy._format_index_context([])
    assert "first source" in result
