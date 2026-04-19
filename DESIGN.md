# SageMate Core: Local-First LLM Wiki (Second Brain)

> **Design Philosophy**: Inspired by Karpathy's llm-wiki pattern.
> The LLM **incrementally builds and maintains a persistent wiki** — a structured, interlinked collection of markdown files. Knowledge is compiled once and kept current, not re-derived on every query.
> **The wiki is a persistent, compounding artifact.**

## 1. Architecture Principles

1.  **Files are Truth**: All data resides in Markdown files. SQLite is a **Read-Optimized Index** (Search & Metadata). If the DB is corrupted, we can rebuild it 100% from files.
2.  **Three Layers**:
    - **Raw Sources** (`data/raw/`): Immutable source documents. LLM reads, never modifies.
    - **Wiki** (`data/wiki/`): LLM-generated, structured, interlinked markdown. The LLM owns this layer.
    - **Schema** (`data/schema/`): Conventions and instructions that tell the LLM how to maintain the wiki.
3.  **Incremental & Compounding**: When a new source arrives, the LLM reads it, integrates it into the *existing* wiki — updating entity pages, revising topic summaries, flagging contradictions, noting cross-references. A single source may touch 10-15 wiki pages.
4.  **Deterministic + LLM Hybrid**: File parsing, slug generation, and metadata extraction are Python (deterministic). Semantic structuring, cross-referencing, and synthesis are LLM (probabilistic, wrapped in retry/backoff).
5.  **Event-Driven**: `Watchdog` listens to file changes and syncs to SQLite automatically.
6.  **Self-Maintaining**: A LintEngine periodically health-checks the wiki — contradictions, stale claims, orphan pages, missing cross-refs.

## 2. Directory Structure

```
data/
├── raw/                    # Immutable source documents
│   ├── articles/
│   ├── papers/
│   └── notes/
├── wiki/                   # LLM-generated knowledge
│   ├── index.md            # Content catalog (page list, summaries, categories)
│   ├── log.md              # Append-only timeline (ingests, queries, lints)
│   ├── entities/           # Entity pages (people, orgs, products)
│   ├── concepts/           # Concept pages (ideas, frameworks, theories)
│   ├── analyses/           # Comparison tables, deep-dives, synthesized answers
│   └── sources/            # Per-source summary pages
├── schema/
│   └── conventions.md      # Wiki conventions, page formats, workflows
└── sagemate.db             # SQLite FTS5 index (rebuilt from files)
```

## 3. Component Design

### 3.1 Core: `Store` (SQLite FTS5)
- **Role**: High-performance search and metadata cache for the **wiki layer**.
- **Tables**:
  - `pages`: `slug`, `title`, `category` (entity/concept/analysis/source), `file_path`, `created_at`, `updated_at`, `word_count`, `content_hash`, `inbound_links`, `outbound_links`
  - `search_idx`: FTS5 virtual table for full-text search across wiki pages
  - `sources`: `file_path`, `title`, `ingested_at`, `wiki_pages_created`, `status`
- **Special**: Maintains `index.md` and `log.md` sync state.

### 3.2 Core: `Watcher` (Dual Watcher)
- **Role**: Watches both `raw/` and `wiki/` directories.
- **Raw watcher**: Triggers ingestion pipeline when new sources arrive.
- **Wiki watcher**: Re-indexes wiki pages when LLM or user edits them directly.

### 3.3 Pipeline: `Parser` (Deterministic)
- **Role**: Convert raw inputs (PDF, Docx, HTML) to Markdown in `data/raw/`.
- **Logic**: Use `pypdf` / `python-docx` / `trafilatura`. Generate deterministic slugs. Add YAML frontmatter.
- **Output**: Clean Markdown file in `data/raw/`. Watcher triggers ingestion.

### 3.4 Pipeline: `IncrementalCompiler` (LLM-Assisted)
- **Role**: The heart of the system. Reads a new source and incrementally updates the wiki.
- **Flow**:
  1. Read new source from `data/raw/`.
  2. Read `index.md` to understand current wiki scope.
  3. Read relevant existing wiki pages (based on topic overlap).
  4. Call LLM with strict JSON Schema to produce:
     - New pages to create (entities, concepts, analyses)
     - Existing pages to update (with diffs)
     - Contradictions to flag
     - Cross-references to add
  5. Write generated/updated pages to `data/wiki/`.
  6. Append entry to `log.md`.
  7. Update `index.md`.
  8. Watcher picks up changes and updates Search Index.

### 3.5 Pipeline: `LintEngine` (Self-Maintenance)
- **Role**: Periodic health-check of the wiki.
- **Checks**:
  - **Contradictions**: Pages with conflicting claims (LLM-assisted comparison).
  - **Stale claims**: Pages that haven't been updated in N days but newer sources exist on the topic.
  - **Orphan pages**: Pages with zero inbound links.
  - **Missing cross-refs**: Concepts mentioned in pages but lacking their own wiki page.
  - **Broken links**: Internal `[[wikilinks]]` pointing to non-existent pages.
- **Output**: Lint report (markdown), auto-fix suggestions, optional auto-repair.

### 3.6 Schema: `conventions.md`
- **Role**: The "operating manual" for the LLM. Co-evolved with the user.
- **Contents**:
  - Page format conventions (frontmatter, heading structure, link style)
  - Category definitions and when to use each
  - Ingest workflow steps
  - Query response format
  - Lint priorities

## 4. Operations

### Ingest
```
User drops file → Parser normalizes → IncrementalCompiler reads source + existing wiki
→ Creates/updates wiki pages → Updates index.md + log.md → Store syncs to SQLite
```

### Query
```
User asks question → Store searches wiki pages (FTS5) → LLM reads relevant pages
→ Synthesizes answer with citations → Optionally saves analysis to data/wiki/analyses/
```

### Lint
```
User triggers lint → LintEngine scans wiki → Detects issues → Generates report
→ User reviews → LLM auto-fixes approved issues → Updates index.md + log.md
```

## 5. Tech Stack
- **Runtime**: Python 3.12+
- **Web**: FastAPI + `aiosqlite`
- **DB**: SQLite (FTS5)
- **Parsing**: `pypdf`, `python-docx`, `trafilatura`
- **Sync**: `watchdog`
- **LLM**: OpenAI-compatible API (DashScope/Qwen)
- **Frontmatter**: `pyyaml`
