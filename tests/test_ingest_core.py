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
    ChapterInfo,
    DocumentOutline,
)
from src.sagemate.ingest.compiler.normalizer import CompileResultNormalizer
from src.sagemate.ingest.compiler.document_model import DocumentModel
from src.sagemate.ingest.compiler.planning import (
    CandidatePlanBuilder,
    CompileBudgetPolicy,
    EvidenceRef,
    KnowledgeCandidate,
    LocalScanResult,
    PlanFirstCompileOrchestrator,
)
from src.sagemate.ingest.compiler.prompts import COMPILE_RESPONSE_SCHEMA
from src.sagemate.models import AppSettings, CompileResult, SourceArchive, WikiPageCreate, WikiCategory


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


def test_compile_result_normalizer_canonicalizes_source_archive():
    """Normalizer should keep chunk artifacts out of the canonical source page."""
    result = CompileResult(
        source_archive=SourceArchive(
            slug="raw-doc-part0",
            title="Research Doc (part 1/3)",
            summary="Summary",
            key_takeaways=["Takeaway"],
            extracted_concepts=["old"],
        ),
        new_pages=[
            WikiPageCreate(
                slug="concept-a",
                title="Concept A",
                category=WikiCategory.CONCEPT,
                content="A",
                sources=[],
                source_pages=[2, 2, 3],
                tags=["x", "x"],
            ),
            WikiPageCreate(
                slug="source-duplicate",
                title="Duplicate Source",
                category=WikiCategory.SOURCE,
                content="Should be dropped",
            ),
        ],
    )

    normalized = CompileResultNormalizer().normalize(
        result,
        source_slug="raw-doc",
        source_title="Research Doc",
    )

    assert normalized.source_archive.slug == "raw-doc"
    assert normalized.source_archive.title == "Research Doc"
    assert normalized.source_archive.extracted_concepts == ["old", "concept-a"]
    assert [p.slug for p in normalized.new_pages] == ["concept-a"]
    assert normalized.new_pages[0].sources == ["raw-doc"]
    assert normalized.new_pages[0].source_pages == [2, 3]


def test_prompt_schema_accepts_relationship_category():
    category_enum = COMPILE_RESPONSE_SCHEMA["schema"]["properties"]["new_pages"]["items"]["properties"]["category"]["enum"]
    assert "relationship" in category_enum


def test_poppler_pdf_strategy_injects_page_markers():
    from src.sagemate.ingest.adapters.pdf_strategies import PopplerPDFStrategy

    marked = PopplerPDFStrategy._inject_page_markers("first page\fsecond page\f")

    assert "<!-- page=1 -->" in marked
    assert "<!-- page=2 -->" in marked
    assert "first page" in marked
    assert "second page" in marked


def test_document_outline_from_llm_uses_chapter_slices():
    content = "# Alpha\nA body\n\n# Beta\nB body\n\n# Gamma\nG body"
    outline = DocumentOutline.from_llm(
        {
            "title": "Doc",
            "chapters": [
                {"index": 1, "title": "Alpha", "summary": "A", "importance": "high"},
                {"index": 2, "title": "Beta", "summary": "B", "importance": "medium"},
            ],
        },
        content,
    )

    assert len(outline.chapters) == 2
    assert "# Alpha" in outline.chapters[0].content
    assert "# Beta" not in outline.chapters[0].content
    assert "# Beta" in outline.chapters[1].content
    assert "# Gamma" in outline.chapters[1].content


def test_document_outline_prefers_page_range_when_markers_exist():
    content = "<!-- page=1 -->\nA\n\n<!-- page=2 -->\nB\n\n<!-- page=3 -->\nC"
    outline = DocumentOutline.from_llm(
        {
            "title": "Doc",
            "chapters": [
                {
                    "index": 1,
                    "title": "Missing Heading",
                    "summary": "B",
                    "importance": "high",
                    "estimated_page_range": "2-3",
                }
            ],
        },
        content,
    )

    assert "<!-- page=1 -->" not in outline.chapters[0].content
    assert "<!-- page=2 -->" in outline.chapters[0].content
    assert "<!-- page=3 -->" in outline.chapters[0].content


def test_document_model_parses_page_markers_into_evidence_blocks():
    model = DocumentModel.from_markdown(
        source_slug="raw-doc",
        source_title="Doc",
        source_type="pdf",
        content="""---
title: Doc
---

<!-- page=1 -->

# Intro

First paragraph.

<!-- page=2 -->

| A | B |
| - | - |
| 1 | 2 |
""",
    )

    assert [page.page_number for page in model.pages] == [1, 2]
    assert model.pages[0].blocks[0].block_id == "p1-b1"
    assert model.pages[0].blocks[0].kind == "heading"
    assert model.pages[0].blocks[1].section_path == ["Intro"]
    assert model.pages[1].blocks[0].kind == "table"

    evidence = model.evidence_blocks()
    assert evidence[0].ref_id == "raw-doc:p1-b1"
    assert evidence[0].page_number == 1


def test_document_model_renders_block_marked_chunks():
    model = DocumentModel.from_markdown(
        source_slug="raw-doc",
        source_title="Doc",
        source_type="pdf",
        content="<!-- page=1 -->\n\n# Intro\n\nAlpha\n\n<!-- page=2 -->\n\nBeta",
    )

    chunks = model.to_markdown_chunks(max_chars=80)

    assert chunks
    assert "<!-- page=1 -->" in chunks[0]
    assert "<!-- block=p1-b1 kind=heading -->" in "\n\n".join(chunks)
    assert "<!-- block=p2-b1 kind=paragraph -->" in "\n\n".join(chunks)


def test_candidate_plan_builder_merges_candidates():
    scans = [
        LocalScanResult(
            chunk_index=0,
            total_chunks=2,
            candidates=[
                KnowledgeCandidate(
                    slug="attention",
                    title="Attention",
                    category=WikiCategory.CONCEPT,
                    summary="Short",
                    aliases=["attn"],
                    evidence_refs=[EvidenceRef(chunk_index=0, quote="A", source_pages=[1])],
                )
            ],
        ),
        LocalScanResult(
            chunk_index=1,
            total_chunks=2,
            candidates=[
                KnowledgeCandidate(
                    slug="attention",
                    title="Attention",
                    category=WikiCategory.CONCEPT,
                    summary="Longer summary",
                    aliases=["attention mechanism"],
                    evidence_refs=[EvidenceRef(chunk_index=1, quote="B", source_pages=[2])],
                )
            ],
        ),
    ]

    plan = CandidatePlanBuilder(max_pages=3).build(
        scans,
        source_slug="raw-paper",
        source_title="Paper",
    )

    assert len(plan.pages) == 1
    assert plan.pages[0].slug == "attention"
    assert plan.pages[0].reason == "Longer summary"
    assert plan.pages[0].source_pages == [1, 2]


def test_compile_budget_policy_selects_evenly_distributed_chunks():
    chunks = [f"chunk-{i}" for i in range(10)]
    selected = CompileBudgetPolicy(max_scan_chunks=4).select_chunks(chunks)

    assert selected[0] == (0, "chunk-0")
    assert selected[-1] == (9, "chunk-9")
    assert len(selected) == 4
    assert [idx for idx, _ in selected] == sorted({idx for idx, _ in selected})
    assert CompileBudgetPolicy(max_scan_chunks=1).select_chunks(chunks) == [(0, "chunk-0")]
    assert CompileBudgetPolicy(max_scan_chunks=4).select_chunks([]) == []


def test_compile_budget_policy_trims_evidence_quotes():
    quote = "x" * 200
    trimmed = CompileBudgetPolicy(max_evidence_quote_chars=120).trim_quote(quote)

    assert len(trimmed) <= 123
    assert trimmed.endswith("...")


@pytest.mark.asyncio
async def test_plan_first_orchestrator_scans_plans_and_assembles():
    class MockLLM:
        def __init__(self):
            self.prompts = []

        async def generate_structured(self, prompt, system_prompt, response_format):
            self.prompts.append(prompt)
            if "Do NOT write final Wiki pages" in prompt:
                return {
                    "candidates": [
                        {
                            "slug": "attention",
                            "title": "Attention",
                            "category": "concept",
                            "summary": "Attention is important.",
                            "source_pages": [1],
                            "evidence_block_ids": ["p1-b2"],
                            "evidence_quotes": ["Attention lets the model focus."],
                        }
                    ]
                }
            return {
                "page": {
                    "slug": "attention",
                    "title": "Attention",
                    "category": "concept",
                    "content": "## Definition\n\nAttention lets the model focus.",
                    "source_pages": [1],
                    "tags": ["ml"],
                    "outbound_links": [],
                }
            }

    llm = MockLLM()
    result = await PlanFirstCompileOrchestrator(
        llm=llm,
        max_concurrent=1,
        max_pages=2,
    ).compile(
        source_slug="raw-paper",
        source_title="Paper",
        chunks=["<!-- page=1 -->\nAttention lets the model focus."],
        index_context="(empty)",
    )

    assert result.source_archive.slug == "raw-paper"
    assert [p.slug for p in result.new_pages] == ["attention"]
    assert result.new_pages[0].sources == ["raw-paper"]
    assert len(llm.prompts) == 2
    assert "blocks ['p1-b2']" in llm.prompts[1]


@pytest.mark.asyncio
async def test_plan_first_orchestrator_respects_scan_budget():
    class MockLLM:
        def __init__(self):
            self.scanned_chunks = []

        async def generate_structured(self, prompt, system_prompt, response_format):
            if "Do NOT write final Wiki pages" in prompt:
                self.scanned_chunks.append(prompt)
                return {"candidates": []}
            raise AssertionError("No page assembly should run without candidates")

    llm = MockLLM()
    result = await PlanFirstCompileOrchestrator(
        llm=llm,
        max_concurrent=1,
        budget=CompileBudgetPolicy(max_scan_chunks=3, max_pages=2),
    ).compile(
        source_slug="raw-paper",
        source_title="Paper",
        chunks=[f"chunk {i}" for i in range(10)],
        index_context="(empty)",
    )

    assert len(llm.scanned_chunks) == 3
    assert "Chunk: 1/10" in llm.scanned_chunks[0]
    assert "Chunk: 10/10" in llm.scanned_chunks[-1]
    assert result.new_pages == []


@pytest.mark.asyncio
async def test_chunked_strategy_uses_plan_first_before_legacy():
    class MockLLM:
        def __init__(self):
            self.scan_calls = 0
            self.assemble_calls = 0

        async def generate_structured(self, prompt, system_prompt, response_format):
            if "Do NOT write final Wiki pages" in prompt:
                self.scan_calls += 1
                return {
                    "candidates": [
                        {
                            "slug": "relationship-a-b",
                            "title": "A relates to B",
                            "category": "relationship",
                            "summary": "A is connected to B.",
                            "source_pages": [2],
                            "evidence_quotes": ["A depends on B."],
                        }
                    ]
                }
            self.assemble_calls += 1
            assert "Assemble one SageMate wiki page" in prompt
            return {
                "page": {
                    "slug": "relationship-a-b",
                    "title": "A relates to B",
                    "category": "relationship",
                    "content": "A depends on B.",
                    "source_pages": [2],
                    "tags": [],
                    "outbound_links": ["a", "b"],
                }
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLM()
        strategy = ChunkedStrategy(
            store=None,
            wiki_dir=Path(tmpdir),
            llm_client=llm,
            chunk_size=1000,
            max_concurrent=1,
        )
        strategy.cfg = type("Cfg", (), {
            "compiler_plan_first_enabled": True,
            "compiler_plan_first_max_pages": 3,
            "schema_dir": Path(tmpdir),
        })()
        result = await strategy._execute_compile(
            source_slug="raw-doc",
            source_content="<!-- page=2 -->\nA depends on B.",
            source_title="Doc",
            index_context="(empty)",
            progress_callback=None,
        )

    assert llm.scan_calls == 1
    assert llm.assemble_calls == 1
    assert result.new_pages[0].category == WikiCategory.RELATIONSHIP


@pytest.mark.asyncio
async def test_deep_compile_preserves_canonical_source_for_chapters():
    """DeepCompile should not leak chapter-specific slugs/titles into inner compiles."""

    class FakeChunked:
        def __init__(self):
            self.calls = []

        async def _execute_compile(self, **kwargs):
            self.calls.append(kwargs)
            return CompileResult(
                new_pages=[
                    WikiPageCreate(
                        slug="alpha",
                        title="Alpha",
                        category=WikiCategory.CONCEPT,
                        content="Alpha body",
                        sources=[kwargs["source_slug"]],
                    )
                ]
            )

    fake_chunked = FakeChunked()
    strategy = DeepCompileStrategy.__new__(DeepCompileStrategy)
    strategy._chunked = fake_chunked

    async def scan_outline(_content):
        return DocumentOutline(
            title="Doc",
            chapters=[
                ChapterInfo(
                    index=1,
                    title="Alpha Chapter",
                    summary="Alpha summary",
                    importance="high",
                    content="Alpha body",
                    page_range="1",
                )
            ],
        )

    strategy._scan_outline = scan_outline
    result = await DeepCompileStrategy._execute_compile(
        strategy,
        source_slug="raw-doc",
        source_content="full content",
        source_title="Doc",
        index_context="(empty)",
        progress_callback=None,
    )

    assert fake_chunked.calls[0]["source_slug"] == "raw-doc"
    assert fake_chunked.calls[0]["source_title"] == "Doc"
    assert "<!-- chapter=1: Alpha Chapter -->" in fake_chunked.calls[0]["source_content"]
    assert result.source_archive.slug == "raw-doc"
    assert result.source_archive.title == "Doc"
    assert result.new_pages[0].sources == ["raw-doc"]


def test_app_settings_exposes_plan_first_controls():
    settings = AppSettings()
    assert settings.compiler_plan_first_enabled is True
    assert settings.compiler_plan_first_max_pages == 8
    assert settings.compiler_plan_first_max_scan_chunks == 12
    assert settings.compiler_plan_first_max_evidence_per_page == 8
    assert settings.compiler_plan_first_max_evidence_quote_chars == 800


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
