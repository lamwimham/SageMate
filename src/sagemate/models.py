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

class WikiCategory(str, Enum):
    """Wiki page categories."""
    ENTITY = "entity"       # People, orgs, products, places
    CONCEPT = "concept"     # Ideas, frameworks, theories
    ANALYSIS = "analysis"   # Comparisons, deep-dives, synthesized answers
    SOURCE = "source"       # Per-source summary pages


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
    error: Optional[str] = None


class QueryRequest(BaseModel):
    question: str
    save_analysis: bool = False  # Whether to save the answer as a wiki analysis page


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)  # wiki page slugs used
    citations: list[dict] = Field(default_factory=list)


class LintTrigger(BaseModel):
    auto_fix: bool = False
    categories: Optional[list[LintIssueType]] = None  # None = all
