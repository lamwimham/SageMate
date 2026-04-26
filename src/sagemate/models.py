"""SageMate Core Domain Models"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Wiki Layer
# ============================================================

class ProjectStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Project(BaseModel):
    """A project represents an isolated knowledge workspace."""
    id: str
    name: str
    root_path: str  # Absolute knowledge-base root path
    wiki_dir_name: str = "wiki"
    assets_dir_name: str = "assets"
    status: ProjectStatus = ProjectStatus.INACTIVE
    created_at: str = ""
    updated_at: str = ""


class ProjectCreate(BaseModel):
    """Create a new project, optionally using a custom local directory."""
    name: str
    root_path: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None


class WikiCategory(str, Enum):
    """Wiki page categories."""
    ENTITY = "entity"       # People, orgs, products, places
    CONCEPT = "concept"     # Ideas, frameworks, theories
    ANALYSIS = "analysis"   # Comparisons, deep-dives, synthesized answers
    SOURCE = "source"       # Per-source summary pages
    NOTE = "note"           # User-authored notes / personal knowledge


class WikiPage(BaseModel):
    """A single page in the LLM-maintained wiki."""
    slug: str
    title: str
    category: WikiCategory
    file_path: str
    content: str = ""
    summary: str = ""           # First ~150 chars, used for index and query context
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    word_count: int = 0
    content_hash: Optional[str] = None
    inbound_links: list[str] = Field(default_factory=list)
    outbound_links: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)  # slugs of source pages that contributed
    source_pages: list[int] = Field(default_factory=list)  # page numbers from source PDF

    @property
    def path(self) -> Path:
        return Path(self.file_path)


class WikiPageUpdate(BaseModel):
    """Represents an incremental update to an existing wiki page."""
    slug: str
    title: Optional[str] = None
    content_patch: str = ""       # The new content (full replacement for MVP)
    reason: str = ""              # Why this page is being updated
    new_links: list[str] = Field(default_factory=list)
    removed_links: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


class WikiPageCreate(BaseModel):
    """Request to create a new wiki page."""
    slug: str
    title: str
    category: WikiCategory
    content: str
    tags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    outbound_links: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)  # List of page numbers from the source PDF


# ============================================================
# Source Layer
# ============================================================

class SourceStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceDocument(BaseModel):
    """A raw source document."""
    file_path: str
    title: str
    slug: str
    source_type: str = "unknown"  # pdf, md, html, docx, txt
    ingested_at: Optional[datetime] = None
    wiki_pages_created: list[str] = Field(default_factory=list)
    status: SourceStatus = SourceStatus.PENDING
    error: Optional[str] = None


# ============================================================
# Log Layer
# ============================================================

class LogEntryType(str, Enum):
    INGEST = "ingest"
    QUERY = "query"
    LINT = "lint"
    MANUAL_EDIT = "manual_edit"
    REPAIR = "repair"


class LogEntry(BaseModel):
    """A single entry in the append-only log."""
    timestamp: datetime = Field(default_factory=datetime.now)
    entry_type: LogEntryType
    title: str
    details: str = ""
    affected_pages: list[str] = Field(default_factory=list)

    def format_md(self) -> str:
        """Format as a parseable markdown log entry."""
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M")
        pages = ", ".join(f"`{p}`" for p in self.affected_pages) if self.affected_pages else "none"
        lines = [
            f"## [{ts}] {self.entry_type.value} | {self.title}",
            f"",
            f"{self.details}",
            f"",
            f"- **Affected pages**: {pages}",
            f"",
        ]
        return "\n".join(lines)


# ============================================================
# Index Layer
# ============================================================

class IndexEntry(BaseModel):
    """A catalog entry in index.md."""
    slug: str
    title: str
    category: WikiCategory
    summary: str = ""
    last_updated: Optional[datetime] = None
    source_count: int = 0
    inbound_count: int = 0


# ============================================================
# Compiler Output (LLM response schema)
# ============================================================

class SourceArchive(BaseModel):
    """The 'One-Pager' summary for an ingested document."""
    slug: str
    title: str
    summary: str              # The core summary/abstract
    key_takeaways: list[str]  # List of key arguments or conclusions
    extracted_concepts: list[str] = [] # Slugs of concepts found in this doc

class CompileResult(BaseModel):
    """Output of the IncrementalCompiler after processing a source."""
    # 1. The "One-Pager" Archive
    source_archive: Optional[SourceArchive] = None
    # 2. The Atomic Knowledge Pages
    new_pages: list[WikiPageCreate] = Field(default_factory=list)
    updated_pages: list[WikiPageUpdate] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    summary: str = ""


# ============================================================
# Lint Results
# ============================================================

class LintIssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LintIssueType(str, Enum):
    CONTRADICTION = "contradiction"
    STALE_CLAIM = "stale_claim"
    ORPHAN_PAGE = "orphan_page"
    BROKEN_LINK = "broken_link"
    MISSING_CROSS_REF = "missing_cross_ref"
    NO_SUMMARY = "no_summary"


class LintIssue(BaseModel):
    """A single issue detected by the LintEngine."""
    issue_type: LintIssueType
    severity: LintIssueSeverity
    page_slug: str
    description: str
    suggestion: str = ""
    related_pages: list[str] = Field(default_factory=list)


class LintReport(BaseModel):
    """Full lint report for the wiki."""
    timestamp: datetime = Field(default_factory=datetime.now)
    total_pages_scanned: int = 0
    issues: list[LintIssue] = Field(default_factory=list)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def high_severity_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == LintIssueSeverity.HIGH)


# ============================================================
# Search Results
# ============================================================

class SearchResult(BaseModel):
    slug: str
    title: str
    category: WikiCategory
    snippet: str
    score: float


# ============================================================
# API Request/Response Models
# ============================================================

class IngestRequest(BaseModel):
    """API request to ingest a source file."""
    source_type: Optional[str] = None  # pdf, md, html, docx, txt
    auto_compile: bool = True          # Whether to run IncrementalCompiler after parsing


class IngestResult(BaseModel):
    success: bool
    source_slug: Optional[str] = None
    wiki_pages_created: int = 0
    wiki_pages_updated: int = 0
    wiki_pages: list[dict] = Field(default_factory=list)
    error: Optional[str] = None


class IngestTaskStatus(str, Enum):
    QUEUED = "queued"
    PARSING = "parsing"
    READING_CONTEXT = "reading_context"
    CALLING_LLM = "calling_llm"
    WRITING_PAGES = "writing_pages"
    UPDATING_INDEX = "updating_index"
    COMPLETED = "completed"
    FAILED = "failed"


class CompileTaskStatus(str, Enum):
    """Persistent compile pipeline task status."""
    QUEUED = "queued"
    PARSING = "parsing"
    READING_CONTEXT = "reading_context"
    CALLING_LLM = "calling_llm"
    WRITING_PAGES = "writing_pages"
    UPDATING_INDEX = "updating_index"
    COMPLETED = "completed"
    FAILED = "failed"


class CompileTaskResult(BaseModel):
    """Result of a compile task."""
    success: bool
    source_slug: str
    wiki_pages_created: int = 0
    wiki_pages_updated: int = 0
    wiki_pages: list[dict] = Field(default_factory=list)


class CompileTask(BaseModel):
    """Persistent compile pipeline task, stored in SQLite.
    
    Unlike IngestTaskState (in-memory only), CompileTask survives
    application restarts and supports historical querying.
    """
    task_id: str
    source_slug: str
    source_title: str = ""  # Enriched via JOIN with sources table
    status: CompileTaskStatus = CompileTaskStatus.QUEUED
    step: int = 0
    total_steps: int = 6
    message: str = "任务已创建，等待处理"
    created_at: str = ""
    updated_at: str = ""
    result: Optional[CompileTaskResult] = None
    error: Optional[str] = None


class IngestTaskState(BaseModel):
    """In-memory state for an async ingest task."""
    task_id: str
    status: IngestTaskStatus = IngestTaskStatus.QUEUED
    step: int = 0
    total_steps: int = 6
    step_name: str = "排队中"
    message: str = "任务已创建，等待处理"
    result: Optional[IngestResult] = None
    error: Optional[str] = None
    failed_step: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class QueryRequest(BaseModel):
    question: str
    save_analysis: bool = False  # Whether to save the answer as a wiki analysis page


class AppSettings(BaseModel):
    """All user-configurable application settings."""

    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    vision_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    vision_api_key: str = ""
    vision_model: str = "qwen-vl-max"
    wechat_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    wechat_api_key: str = ""
    compiler_max_source_chars: int = Field(default=40000, ge=1000, le=50000)
    compiler_max_wiki_context_chars: int = Field(default=16000, ge=1000, le=30000)
    lint_stale_days: int = Field(default=30, ge=1, le=365)
    cron_auto_compile_enabled: bool = True
    cron_auto_compile_interval: int = Field(default=300, ge=60, le=86400)
    cron_lint_enabled: bool = True
    cron_lint_interval: int = Field(default=1800, ge=60, le=86400)
    watcher_debounce_ms: int = Field(default=500, ge=100, le=5000)
    raw_dir_path: str = ""
    url_tier1_timeout: int = Field(default=30, ge=5, le=120)
    url_tier2_timeout: int = Field(default=30, ge=5, le=120)
    url_cache_enabled: bool = True
    url_max_concurrent: int = Field(default=5, ge=1, le=20)
    url_retry_attempts: int = Field(default=3, ge=1, le=5)
    url_proxy_enabled: bool = False
    url_proxy_url: str = ""


class SettingsUpdate(BaseModel):
    """Partial update for application settings."""
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    vision_base_url: Optional[str] = None
    vision_api_key: Optional[str] = None
    vision_model: Optional[str] = None
    wechat_base_url: Optional[str] = None
    wechat_api_key: Optional[str] = None
    compiler_max_source_chars: Optional[int] = None
    compiler_max_wiki_context_chars: Optional[int] = None
    lint_stale_days: Optional[int] = None
    cron_auto_compile_enabled: Optional[bool] = None
    cron_auto_compile_interval: Optional[int] = None
    cron_lint_enabled: Optional[bool] = None
    cron_lint_interval: Optional[int] = None
    watcher_debounce_ms: Optional[int] = None
    raw_dir_path: Optional[str] = None
    url_tier1_timeout: Optional[int] = None
    url_tier2_timeout: Optional[int] = None
    url_cache_enabled: Optional[bool] = None
    url_max_concurrent: Optional[int] = None
    url_retry_attempts: Optional[int] = None
    url_proxy_enabled: Optional[bool] = None
    url_proxy_url: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)  # wiki page slugs used
    citations: list[dict] = Field(default_factory=list)
    related_pages: list[str] = Field(default_factory=list)  # wiki page slugs related to the question


class LintTrigger(BaseModel):
    auto_fix: bool = False
    categories: Optional[list[LintIssueType]] = None  # None = all


# ============================================================
# Swagger / OpenAPI Response Models
# ============================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    data_dir: str
    wiki_pages: int
    sources: int


class GenericResponse(BaseModel):
    """Generic success/failure response."""
    success: bool = True
    message: str = ""
    slug: Optional[str] = None

class PageDetailResponse(BaseModel):
    """Wiki page detail response including file content."""
    page: WikiPage
    content: str
