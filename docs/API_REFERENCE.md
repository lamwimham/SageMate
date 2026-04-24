# SageMate Core — API Documentation & Frontend Architecture

> **Version**: 0.4.0
> **Architecture**: Server-side rendered (SSR) with Jinja2 templates + vanilla JavaScript PJAX router
> **Styling**: Tailwind CSS (local CDN) + custom design tokens (dark/light theme)
> **Last Updated**: 2026-04-23

---

## Table of Contents

1. [Frontend Architecture Overview](#1-frontend-architecture-overview)
2. [API Endpoints Reference](#2-api-endpoints-reference)
3. [Page Routes](#3-page-routes)
4. [Data Models](#4-data-models)
5. [WebSocket / SSE Endpoints](#5-websocket--sse-endpoints)
6. [Frontend Layout Components](#6-frontend-layout-components)
7. [VSCode-Style Multi-Column Layout Plan](#7-vscode-style-multi-column-layout-plan)

---

## 1. Frontend Architecture Overview

### 1.1 Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI (async) |
| Templating | Jinja2 (server-side rendered) |
| CSS | Tailwind CSS (local `tailwind.js`) + custom CSS variables |
| JavaScript | Vanilla JS (no framework) |
| Navigation | Custom PJAX router (SPA-like, swaps `<main>` only) |
| Markdown | `marked.js` (local asset) |
| Theme | CSS custom properties (dark default, light toggle) |

### 1.2 Current Layout Pattern

```
┌─────────────────────────────────────────────────────┐
│                    Top Header (sticky)               │
│  Logo | Nav Links (6) | API | Theme Toggle | Menu   │
├─────────────────────────────────────────────────────┤
│                                                     │
│                  Main Content Area                  │
│              ({% block content %})                   │
│           Max-width 7xl, centered                    │
│                                                     │
├─────────────────────────────────────────────────────┤
│                    Footer                            │
│         Version · Tagline · Links                    │
└─────────────────────────────────────────────────────┘
```

### 1.3 Target Layout: VSCode-Style Multi-Column

```
┌──────────┬──────────────┬────────────────────────────┬─────────────┐
│ Activity │   Sidebar    │      Main Content          │   Detail    │
│   Bar    │  (Explorer)  │     (Editor/View)          │   Panel     │
│  (Icons) │  (Tree/List) │                            │  (Optional) │
│          │              │                            │             │
│ 📊 Dash  │  📁 Files    │  ┌──────────────────┐     │  Metadata   │
│ 📚 Wiki  │  📄 Pages    │  │  Tab Bar         │     │  Links      │
│ ⚡ Ingest│  📊 Stats    │  ├──────────────────┤     │  Graph      │
│ 📂 Raw   │  🔗 Links    │  │  Content Area    │     │  Preview    │
│ 🔍 Status│  ⚙️ Settings │  │                  │     │             │
│ ⚙️ Config│              │  │                  │     │             │
│          │              │  └──────────────────┘     │             │
├──────────┴──────────────┴────────────────────────────┴─────────────┤
│                      Bottom Panel (Optional)                       │
│              Terminal | Output | Problems | Search                 │
└────────────────────────────────────────────────────────────────────┘
```

### 1.4 Design Patterns to Apply

| Pattern | Purpose | Where |
|---------|---------|-------|
| **Layout Shell** | Centralized multi-column container | `base.html` |
| **Component Slots** | `{% block %}` for each panel | `base.html` |
| **State Management** | `window.__sagemate__` global state | JS runtime |
| **Event Bus** | `CustomEvent` for cross-panel communication | JS runtime |
| **PJAX Router** | Enhanced to handle multi-panel swaps | `base.html` script |
| **Lazy Loading** | Fetch panel content on demand | Per-page scripts |
| **Keyboard Shortcuts** | `Ctrl/Cmd+` shortcuts like VSCode | Global handler |
| **Command Palette** | `Ctrl/Cmd+Shift+P` quick actions | New component |

---

## 2. API Endpoints Reference

### 2.1 Health & System

#### `GET /health`
Health check endpoint.

**Response**:
```json
{
  "status": "ok",
  "version": "0.4.0",
  "data_dir": "/path/to/data",
  "wiki_pages": 42,
  "sources": 15
}
```

---

### 2.2 Settings API

#### `GET /api/settings`
Get all current application settings.

**Response**:
```json
{
  "llm_base_url": "https://api.example.com/v1",
  "llm_api_key": "***",
  "llm_model": "Qwen/Qwen3-Coder-480B",
  "vision_base_url": "https://api.example.com/v1",
  "vision_api_key": "***",
  "vision_model": "gpt-4-vision",
  "wechat_base_url": "https://open.bigmodel.cn/api/paas/v4",
  "wechat_api_key": "",
  "wechat_model": "GLM-5",
  "compiler_max_source_chars": 50000,
  "compiler_max_wiki_context_chars": 30000,
  "lint_stale_days": 30,
  "cron_auto_compile_enabled": true,
  "cron_auto_compile_interval": 300,
  "cron_lint_enabled": true,
  "cron_lint_interval": 1800,
  "url_tier1_timeout": 30,
  "url_tier2_timeout": 60,
  "url_cache_enabled": true,
  "url_max_concurrent": 5,
  "url_retry_attempts": 3,
  "url_proxy_enabled": false,
  "url_proxy_url": "",
  "watcher_debounce_ms": 500,
  "raw_dir_path": "/path/to/data/raw",
  "overrides": ["llm_base_url", "llm_model"]
}
```

#### `PATCH /api/settings`
Update application settings. Saves to DB and applies immediately.

**Request Body** (`SettingsUpdate`):
```json
{
  "llm_base_url": "https://new-api.example.com/v1",
  "llm_api_key": "sk-xxx",
  "llm_model": "Qwen/Qwen3-Coder-480B",
  "vision_base_url": "...",
  "vision_api_key": "...",
  "vision_model": "...",
  "wechat_base_url": "...",
  "wechat_api_key": "...",
  "wechat_model": "...",
  "compiler_max_source_chars": 50000,
  "compiler_max_wiki_context_chars": 30000,
  "lint_stale_days": 30,
  "cron_auto_compile_enabled": true,
  "cron_auto_compile_interval": 300,
  "cron_lint_enabled": true,
  "cron_lint_interval": 1800,
  "url_tier1_timeout": 30,
  "url_tier2_timeout": 60,
  "url_cache_enabled": true,
  "url_max_concurrent": 5,
  "url_retry_attempts": 3,
  "url_proxy_enabled": false,
  "url_proxy_url": "",
  "watcher_debounce_ms": 500,
  "raw_dir_path": "/path/to/data/raw"
}
```

**Response**:
```json
{
  "success": true,
  "updated": ["llm_base_url", "llm_model"]
}
```

#### `POST /api/settings/reset`
Reset all runtime setting overrides (clear DB table).

**Response**:
```json
{
  "success": true
}
```

---

### 2.3 WeChat QR Login API

#### `POST /api/wechat/qr`
Fetch WeChat login QR code via service layer.

**Response**:
```json
{
  "success": true,
  "qr_code": "data:image/png;base64,...",
  "qr_id": "uuid-string"
}
```

#### `POST /api/wechat/qr/poll`
Poll WeChat QR login status.

**Request Body** (optional):
```json
{
  "qr_id": "uuid-string"
}
```

**Response**:
```json
{
  "status": "scanned" | "confirmed" | "expired" | "waiting",
  "account": {
    "nickname": "UserNickname",
    "avatar": "https://..."
  }
}
```

#### `POST /api/wechat/logout`
Log out of WeChat.

**Response**:
```json
{
  "success": true
}
```

#### `GET /api/wechat/account`
Get current WeChat account status.

**Response**:
```json
{
  "logged_in": true,
  "nickname": "UserNickname",
  "avatar": "https://..."
}
```

---

### 2.4 Wiki Pages API

#### `GET /pages`
List all wiki pages, optionally filtered by category.

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | No | Filter by category: `entity`, `concept`, `analysis`, `source` |

**Response** (`WikiPage[]`):
```json
[
  {
    "slug": "my-page",
    "title": "My Page",
    "category": "concept",
    "file_path": "/path/to/data/wiki/concepts/my-page.md",
    "created_at": "2026-04-20T10:00:00",
    "updated_at": "2026-04-23T15:30:00",
    "word_count": 1234,
    "tags": ["tag1", "tag2"],
    "sources": ["source-1"],
    "source_pages": ["P1", "P2"],
    "inbound_links": ["other-page"],
    "outbound_links": ["linked-page"],
    "summary": "Auto-generated summary..."
  }
]
```

#### `GET /pages/{slug}`
Get a wiki page with content.

**Response**:
```json
{
  "page": { /* WikiPage object */ },
  "content": "# Page Content\n\n..."
}
```

#### `PUT /pages/{slug}`
Update a wiki page by saving new content.

**Request Body**:
```json
{
  "content": "# Updated Content\n\n..."
}
```

**Response**:
```json
{
  "success": true,
  "slug": "my-page",
  "message": "Page updated"
}
```

#### `DELETE /pages/{slug}`
Delete a wiki page.

**Response**:
```json
{
  "success": true,
  "slug": "my-page",
  "message": "Page deleted"
}
```

---

### 2.5 Search & Query API

#### `GET /search`
Full-text search across wiki pages.

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | string | Yes | Search query |
| `category` | string | No | Filter by category |
| `limit` | int | No | Max results (default: 50) |

**Response** (`SearchResult[]`):
```json
[
  {
    "slug": "my-page",
    "title": "My Page",
    "category": "concept",
    "score": 0.95,
    "snippet": "...matching text...",
    "word_count": 1234,
    "updated_at": "2026-04-23T15:30:00"
  }
]
```

#### `POST /query`
LLM-based Q&A (non-streaming).

**Request Body** (`QueryRequest`):
```json
{
  "question": "What is the knowledge base about?",
  "save_analysis": false
}
```

**Response** (`QueryResponse`):
```json
{
  "answer": "The knowledge base is about...",
  "sources": ["page-1", "page-2"],
  "related_pages": [/* WikiPage[] */]
}
```

#### `POST /query/stream`
Streaming LLM Q&A (Server-Sent Events).

**Request Body** (`QueryRequest`):
```json
{
  "question": "What is the knowledge base about?",
  "save_analysis": false
}
```

**Response**: SSE stream
```
event: chunk
data: {"chunk": "The knowledge base..."}

event: chunk
data: {"chunk": "is about..."}

event: done
data: {"sources": ["page-1"], "related_pages": [...]}
```

---

### 2.6 Ingest API

#### `POST /ingest`
Submit data for ingestion (file, URL, or text).

**Request** (multipart form or JSON):
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | No | Upload file (PDF, MD, TXT, DOCX, HTML) |
| `url` | string | No | URL to ingest |
| `text` | string | No | Raw text to ingest |
| `title` | string | No | Optional title for the source |

**Response**:
```json
{
  "task_id": "abc123def456",
  "status": "queued",
  "message": "Task created, waiting for processing"
}
```

#### `GET /ingest/progress/{task_id}`
SSE stream for task progress.

**Response**: SSE stream
```
event: progress
data: {"type": "progress", "task_id": "abc123", "status": "reading_context", "step": 2, "total_steps": 5, "message": "Reading context..."}

event: progress
data: {"type": "progress", "task_id": "abc123", "status": "calling_llm", "step": 3, "total_steps": 5, "message": "LLM analyzing..."}

event: completed
data: {"type": "completed", "task_id": "abc123", "result": {"success": true, "wiki_pages_created": 3, ...}}
```

---

### 2.7 Lint API

#### `POST /lint`
Run lint check on the wiki.

**Response**:
```json
{
  "success": true,
  "report": {
    "total_pages_scanned": 42,
    "issue_count": 5,
    "high_severity_count": 2,
    "medium_severity_count": 3,
    "low_severity_count": 0,
    "timestamp": "2026-04-23T15:30:00",
    "issues": [
      {
        "page_slug": "my-page",
        "issue_type": "broken_link",
        "severity": "high",
        "description": "Link to [[non-existent]] is broken",
        "suggestion": "Create the page or remove the link"
      }
    ]
  }
}
```

---

### 2.8 Raw Files API

#### `GET /web/raw/view`
Preview a single raw file.

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | Yes | Relative path within raw_dir |
| `embed` | string | No | Set to `1` for embed mode (iframe) |

**Response**: HTML template with appropriate viewer (PDF iframe, image, markdown, etc.)

#### `GET /data/raw/{path}`
Direct file access (mounted static directory).

---

## 3. Page Routes

### 3.1 HTML Routes

| Route | Template | Active Nav | Description |
|-------|----------|------------|-------------|
| `/` | (redirect) | — | Redirects to `/web` |
| `/web` | `index.html` | `dashboard` | Dashboard — stats, recent pages, activity log |
| `/web/pages` | `pages.html` | `wiki` | Wiki Pages list — search, category filters, card grid |
| `/web/pages/{slug}` | `page_detail.html` | `wiki` | Single Wiki page — view/edit markdown, metadata sidebar |
| `/web/sources` | `sources.html` | `wiki` | Sources list — table of archived source files |
| `/web/sources/{slug}` | `source_detail.html` | `wiki` | Source detail — file info, preview, linked wiki pages |
| `/web/ingest` | `ingest.html` | `ingest` | Ingest data — file upload, URL input, text input, SSE progress |
| `/web/raw` | `raw.html` | `raw` | Raw files — file timeline sidebar + preview panel |
| `/web/status` | `status.html` | `status` | System status — tabbed: health, log, cost, cron |
| `/web/settings` | `settings.html` | `settings` | Settings — collapsible sections for all config |
| `/docs` | — | — | FastAPI auto-generated Swagger API docs |

### 3.2 Redirects

| Old Route | New Route | Status |
|-----------|-----------|--------|
| `/web/query` | `/web/pages` | 301 |
| `/sources/{slug}` | `/web/sources/{slug}` | 301 |

---

## 4. Data Models

### 4.1 WikiPage
```python
class WikiPage(BaseModel):
    slug: str
    title: str
    category: WikiCategory  # entity, concept, analysis, source
    file_path: str
    created_at: datetime
    updated_at: datetime
    word_count: int
    tags: list[str] = []
    sources: list[str] = []
    source_pages: list[str] = []
    inbound_links: list[str] = []
    outbound_links: list[str] = []
    summary: str = ""
```

### 4.2 SearchResult
```python
class SearchResult(BaseModel):
    slug: str
    title: str
    category: WikiCategory
    score: float
    snippet: str = ""
    word_count: int = 0
    updated_at: datetime
```

### 4.3 QueryRequest
```python
class QueryRequest(BaseModel):
    question: str
    save_analysis: bool = False
```

### 4.4 QueryResponse
```python
class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = []
    related_pages: list[WikiPage] = []
```

### 4.5 IngestResult
```python
class IngestResult(BaseModel):
    success: bool
    source_slug: str | None = None
    wiki_pages_created: int = 0
    wiki_pages_updated: int = 0
    wiki_pages: list[dict] = []
    error: str | None = None
```

### 4.6 IngestTaskState
```python
class IngestTaskState(BaseModel):
    task_id: str
    status: IngestTaskStatus  # queued, reading_context, calling_llm, writing_pages, updating_index, completed, failed
    step: int
    total_steps: int = 5
    step_name: str
    message: str
    created_at: str
    updated_at: str
    result: IngestResult | None = None
    error: str | None = None
```

### 4.7 LintReport
```python
class LintReport(BaseModel):
    total_pages_scanned: int
    issue_count: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    timestamp: datetime
    issues: list[LintIssue]
```

### 4.8 LintIssue
```python
class LintIssue(BaseModel):
    page_slug: str
    issue_type: LintIssueType  # broken_link, orphan_page, stale_claim, contradiction, missing_cross_ref
    severity: str  # high, medium, low
    description: str
    suggestion: str | None = None
```

### 4.9 SettingsUpdate
```python
class SettingsUpdate(BaseModel):
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    vision_base_url: str | None = None
    vision_api_key: str | None = None
    vision_model: str | None = None
    wechat_base_url: str | None = None
    wechat_api_key: str | None = None
    wechat_model: str | None = None
    compiler_max_source_chars: int | None = None
    compiler_max_wiki_context_chars: int | None = None
    lint_stale_days: int | None = None
    cron_auto_compile_enabled: bool | None = None
    cron_auto_compile_interval: int | None = None
    cron_lint_enabled: bool | None = None
    cron_lint_interval: int | None = None
    url_tier1_timeout: int | None = None
    url_tier2_timeout: int | None = None
    url_cache_enabled: bool | None = None
    url_max_concurrent: int | None = None
    url_retry_attempts: int | None = None
    url_proxy_enabled: bool | None = None
    url_proxy_url: str | None = None
    watcher_debounce_ms: int | None = None
    raw_dir_path: str | None = None
```

---

## 5. WebSocket / SSE Endpoints

### 5.1 Ingest Progress Stream
**Endpoint**: `GET /ingest/progress/{task_id}`
**Protocol**: Server-Sent Events (SSE)
**Events**:
- `progress`: Step progress update
- `completed`: Task finished successfully
- `failed`: Task failed with error

### 5.2 Query Stream
**Endpoint**: `POST /query/stream`
**Protocol**: Server-Sent Events (SSE)
**Events**:
- `chunk`: Streaming text chunk
- `done`: Final result with sources and related pages

---

## 6. Frontend Layout Components

### 6.1 Current Template Structure

```
base.html
├── index.html          (Dashboard)
├── pages.html          (Pages List)
├── page_detail.html    (Page Detail)
├── page_missing.html   (Missing Page)
├── sources.html        (Sources List)
├── source_detail.html  (Source Detail)
├── ingest.html         (Ingest)
├── raw.html            (Raw Files)
├── status.html         (Status)
├── settings.html       (Settings)
├── raw_view.html       (Raw File View - standalone)
└── raw_view_embed.html (Raw File Embed - iframe)
```

### 6.2 PJAX Router

The current PJAX router in `base.html`:
1. Intercepts clicks on internal links
2. Fetches new page HTML via `fetch()`
3. Extracts `<main>` content
4. Swaps content into `#main-content`
5. Updates URL via `history.pushState()`
6. Re-executes page-specific `<script>` blocks

**Limitations**:
- Only swaps a single `<main>` block
- Cannot handle multi-panel updates
- No state persistence across navigation
- No keyboard shortcuts
- No command palette

### 6.3 Enhanced PJAX Router (Target)

The enhanced router will:
1. Support **named panel targets**: `sidebar`, `main`, `detail`, `bottom`
2. Use `data-panel` attributes on links to specify target
3. Maintain **panel state** (which page is open in each panel)
4. Support **tab management** (open/close/switch tabs in main panel)
5. Expose **event bus** for cross-panel communication
6. Support **keyboard shortcuts** (`Ctrl+P` command palette, `Ctrl+B` toggle sidebar, etc.)

---

## 7. VSCode-Style Multi-Column Layout Plan

### 7.1 Layout Regions

| Region | ID | Default Width | Collapsible | Content |
|--------|----|---------------|-------------|---------|
| **Activity Bar** | `activity-bar` | 48px | No | Icon navigation (Dashboard, Wiki, Ingest, Raw, Status, Settings) |
| **Side Bar** | `side-bar` | 260px | Yes (Ctrl+B) | Explorer tree, search, outline, etc. |
| **Main Content** | `main-content` | Flexible | No | Tabbed editor/view area |
| **Detail Panel** | `detail-panel` | 300px | Yes (Ctrl+J) | Metadata, links, preview, context |
| **Bottom Panel** | `bottom-panel` | 200px | Yes (Ctrl+`) | Output, terminal, problems, search results |

### 7.2 Panel-to-Page Mapping

| Page | Activity Bar Icon | Side Bar | Main Content | Detail Panel | Bottom Panel |
|------|-------------------|----------|--------------|--------------|--------------|
| Dashboard | 📊 | Quick Links + Activity | Stats + Recent Pages | — | — |
| Pages List | 📚 | Category Tree + Search | Page Cards Grid | — | — |
| Page Detail | 📚 | Outline + Link Tree | Markdown Content | Metadata + Links | — |
| Ingest | ⚡ | Task History | Input Forms + Progress | — | Task Log |
| Raw Files | 📂 | File Tree | Preview | File Meta + Links | — |
| Status | 🔍 | Log Filters | Health/Log/Cost/Cron | — | — |
| Settings | ⚙️ | Section Nav | Config Forms | — | — |

### 7.3 Component Architecture

```
base.html (Layout Shell)
├── ActivityBar (left icon rail)
│   ├── ActivityBarItem (per icon)
│   └── Theme Toggle
│
├── SideBar (collapsible)
│   ├── SideBarHeader (title + actions)
│   └── SideBarContent (tree/list)
│
├── MainContent (tabbed)
│   ├── TabBar (open tabs)
│   └── TabContent (active view)
│
├── DetailPanel (collapsible, right)
│   └── Dynamic content per page
│
└── BottomPanel (collapsible)
    └── Dynamic content per page
```

### 7.4 CSS Layout Strategy

Using CSS Grid for the main shell:

```css
.layout-shell {
  display: grid;
  grid-template-columns: 48px 1fr;
  grid-template-rows: 1fr auto;
  height: 100vh;
}

.layout-shell.sidebar-open {
  grid-template-columns: 48px 260px 1fr;
}

.layout-shell.detail-open {
  grid-template-columns: 48px 260px 1fr 300px;
}

.layout-shell.bottom-open {
  grid-template-rows: 1fr 200px;
}
```

### 7.5 State Management

```javascript
window.__sagemate__ = {
  // Layout state
  layout: {
    sidebarOpen: true,
    detailPanelOpen: false,
    bottomPanelOpen: false,
    sidebarWidth: 260,
    detailPanelWidth: 300,
    bottomPanelHeight: 200,
  },

  // Panel content state
  panels: {
    sidebar: { view: 'explorer', data: {} },
    main: { tabs: [], activeTab: null },
    detail: { view: null, data: {} },
    bottom: { view: null, data: {} },
  },

  // Navigation state
  nav: {
    activeActivity: 'dashboard',
    history: [],
    breadcrumbs: [],
  },

  // Event bus
  events: new EventTarget(),
}
```

### 7.6 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + B` | Toggle Side Bar |
| `Ctrl/Cmd + J` | Toggle Bottom Panel |
| `Ctrl/Cmd + Shift + P` | Open Command Palette |
| `Ctrl/Cmd + P` | Quick Open (search pages) |
| `Ctrl/Cmd + K` | Focus Search |
| `Ctrl/Cmd + W` | Close Tab |
| `Ctrl/Cmd + \` | Toggle Detail Panel |
| `Ctrl/Cmd + 1-6` | Switch Activity Bar section |
| `Ctrl/Cmd + Shift + F` | Global Search |
| `Escape` | Close modal/palette |

### 7.7 Implementation Phases

**Phase 1: Layout Shell** (base.html refactor)
- Create CSS Grid layout
- Add Activity Bar
- Add collapsible Side Bar
- Add Main Content area
- Add collapsible Detail Panel
- Add collapsible Bottom Panel
- Update PJAX router for multi-panel

**Phase 2: Page Migration** (one page at a time)
- Migrate Dashboard (simplest)
- Migrate Pages List
- Migrate Page Detail (complex: editor + metadata)
- Migrate Ingest (complex: SSE + forms)
- Migrate Raw Files (already close to target)
- Migrate Status (tabs)
- Migrate Settings (accordion)

**Phase 3: Enhanced Features**
- Command Palette
- Keyboard Shortcuts
- Tab Management
- Resizable Panels
- Panel State Persistence

---

## 8. Refactoring Strategy

### 8.1 Design Patterns

| Pattern | Application |
|---------|-------------|
| **Composite Layout** | `base.html` as shell with named slots |
| **Template Inheritance** | Pages extend `base.html`, fill blocks |
| **Event-Driven** | `CustomEvent` for cross-panel communication |
| **State Machine** | Panel visibility and tab management |
| **Observer** | Theme changes, layout state changes |
| **Strategy** | Different side bar views per page type |
| **Mediator** | PJAX router coordinates panel updates |

### 8.2 Backward Compatibility

- Keep existing page templates working during migration
- Use feature flag `data-layout="vscode"` on `<body>` to switch layouts
- Migrate one page at a time, test each before moving to next
- Provide fallback to old layout if needed

### 8.3 Risk Mitigation

- **CSS conflicts**: Use specific selectors, avoid global styles
- **JS errors**: Wrap new code in try/catch, log to console
- **Mobile**: Keep responsive design, collapse panels on small screens
- **Performance**: Lazy load panel content, don't render everything upfront

---

*End of Document*
