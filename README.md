# SageMate Core

> **Local-First LLM Wiki — A persistent, compounding second brain.**
>
> Inspired by [Karpathy's llm-wiki pattern](https://karpathy.ai/), SageMate incrementally builds and maintains a structured, interlinked knowledge base from your raw sources. Knowledge is compiled once and kept current — not re-derived on every query.

---

## Table of Contents

- [Why SageMate?](#why-sagemate)
- [Core Features](#core-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Components](#components)
- [Browser Extension](#browser-extension)
- [Desktop App](#desktop-app)
- [Development](#development)
- [Roadmap](#roadmap)
- [License](#license)

---

## Why SageMate?

Traditional note-taking tools are **libraries** — you file things away and hope to find them later. SageMate is a **radar** — it actively surfaces connections, detects contradictions, and reminds you of what you've forgotten.

| Traditional (Obsidian/Notion) | SageMate (AI-Native) |
| :--- | :--- |
| Library / Warehouse | **Personal Advisor / Radar** |
| Search & Browse | **Context-Aware Injection & Review** |
| Storage Efficiency | **Recall Efficiency** |

**The Wiki is a persistent, compounding artifact.** Every new source you ingest doesn't just get stored — it gets *integrated*. A single article can update 10–15 wiki pages, forge new cross-references, and flag contradictions with existing knowledge.

---

## Core Features

### 🧠 Incremental Knowledge Compilation
- Drop a file, paste a URL, or type text — the LLM reads it and **incrementally updates** your wiki.
- New entities, concepts, and analyses are created or merged automatically.

### 🔗 Interlinked Wiki Pages
- **Entities** — people, organizations, products.
- **Concepts** — ideas, frameworks, theories.
- **Analyses** — comparison tables, deep-dives, synthesized answers.
- **Sources** — per-source summary pages with backlinks.
- Native `[[wikilink]]` support for bidirectional linking.

### 🔍 Full-Text Search + LLM Q&A
- **SQLite FTS5** powers blazing-fast full-text search across all wiki pages.
- **Streaming LLM queries** synthesize answers with citations from your knowledge base.

### 🛡️ Self-Health (LintEngine)
Periodic automated checks detect:
- **Contradictions** — conflicting claims across pages.
- **Stale claims** — pages outdated by newer sources.
- **Orphan pages** — pages with zero inbound links.
- **Missing cross-references** — concepts mentioned but not yet documented.
- **Broken links** — internal `[[wikilinks]]` pointing to non-existent pages.

### 🌐 Browser Extension (Chrome)
One-click clipper: extract article content from any webpage and send it directly to your SageMate knowledge base.

### 💬 WeChat Integration
Sync messages and articles from WeChat into your knowledge pipeline.

### 🖥️ Desktop Application
Cross-platform desktop app built with **Tauri v2** (Rust + Web frontend).

### 📁 Multi-Project Support
Organize knowledge into isolated projects, each with its own `raw/`, `wiki/`, and `assets/` directories.

---

## Architecture

SageMate follows a **local-first, file-centric** philosophy:

> **Files are Truth.** All data resides in Markdown files. SQLite is a **Read-Optimized Index** (search & metadata). If the DB is corrupted, rebuild it 100% from files.

### Three Data Layers

```
data/
├── raw/                    # Immutable source documents (PDF, DOCX, HTML, MD)
│   ├── articles/
│   ├── papers/
│   └── notes/
├── wiki/                   # LLM-generated, structured, interlinked markdown
│   ├── index.md            # Content catalog
│   ├── log.md              # Append-only timeline
│   ├── entities/           # Entity pages
│   ├── concepts/           # Concept pages
│   ├── analyses/           # Synthesized analyses
│   └── sources/            # Per-source summaries
├── schema/
│   └── conventions.md      # Wiki conventions & LLM operating manual
└── sagemate.db             # SQLite FTS5 index (rebuilt from files)
```

### Ingest Flow

```
User drops file → Parser normalizes to Markdown
    → IncrementalCompiler reads source + existing wiki
    → LLM creates/updates wiki pages
    → Updates index.md + log.md
    → Watcher syncs to SQLite FTS5 index
```

### Query Flow

```
User asks question → FTS5 searches wiki pages
    → LLM reads relevant pages
    → Synthesizes answer with citations
    → Optionally saves analysis to wiki/analyses/
```

---

## Quick Start

### Prerequisites
- Python **3.12+**
- Node.js **20+** (for frontend development)
- Rust **1.75+** (for desktop app)

### 1. Clone & Install Backend

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install with all extras
pip install -e ".[dev,parse,desktop]"
```

### 2. Configure Environment

```bash
cp .env.example .env  # or edit .env directly
```

Key variables:
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o
DATA_DIR=./data
```

### 3. Run the Server

```bash
# CLI entry point
sagemate

# Or directly
python -m sagemate.api.app

# Server starts at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 4. Run the Web Frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Run the Desktop App

```bash
cd src-tauri
cargo tauri dev
```

---

## Project Structure

```
sagemate-core/
├── src/sagemate/              # Python backend core
│   ├── api/                   # FastAPI app, routers, templates
│   ├── core/                  # Store (SQLite), Watcher, Config, EventBus
│   ├── ingest/                # Parser, Compiler, Task Manager
│   ├── pipeline/              # Processing pipelines
│   ├── plugins/               # WeChat channel integration
│   ├── system/                # LintEngine, Doctor
│   └── models.py              # Pydantic data models
├── frontend/                  # React + Vite + TanStack Router frontend
│   ├── src/
│   │   ├── api/               # API clients
│   │   ├── components/        # UI components
│   │   ├── views/             # Page views
│   │   └── stores/            # Zustand state stores
│   └── package.json
├── src-tauri/                 # Tauri v2 desktop shell (Rust)
│   ├── src/
│   └── Cargo.toml
├── browser-extension/         # Chrome Extension (Manifest V3)
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   └── popup.js
├── docs/                      # Design docs, API reference, roadmaps
├── data/                      # Runtime data (DB, raw, wiki, projects)
├── tests/                     # pytest suite
└── scripts/                   # Build & migration utilities
```

---

## Components

| Component | Role | Tech |
|-----------|------|------|
| **Store** | SQLite FTS5 index + metadata cache | `aiosqlite`, FTS5 |
| **Watcher** | Dual file watcher (raw/ + wiki/) | `watchdog` |
| **Parser** | Deterministic file normalization | `pypdf`, `python-docx`, `trafilatura` |
| **IncrementalCompiler** | LLM-assisted wiki updater | OpenAI-compatible API |
| **LintEngine** | Self-health checker | Periodic cron + LLM |
| **Task Manager** | Async ingest queue with SSE progress | `asyncio` |
| **WeChat Plugin** | Message/article sync | `agentscope` |

### API Highlights

| Endpoint | Description |
|----------|-------------|
| `POST /ingest` | Submit file, URL, or text for ingestion |
| `GET /ingest/progress/{id}` | SSE stream for real-time task progress |
| `GET /pages` | List all wiki pages |
| `GET /search?q=...` | Full-text search (FTS5) |
| `POST /query` | LLM Q&A with citations |
| `POST /query/stream` | Streaming LLM Q&A (SSE) |
| `POST /lint` | Run wiki health check |
| `GET /health` | System health & stats |

> See [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) for the complete API specification.

---

## Browser Extension

The **SageMate Clipper** (Chrome Extension) lets you capture any web page in one click:

1. Open the extension popup on any page.
2. Preview extracted title, URL, and content.
3. Click **Send to SageMate** — the page is queued for ingestion and auto-compilation.
4. Optional keyboard shortcut: `Ctrl+Shift+S` / `Cmd+Shift+S`.

**Install:**
```bash
cd browser-extension
# Load " unpacked extension" in chrome://extensions/
```

---

## Desktop App

SageMate ships as a cross-platform desktop application powered by **Tauri v2**:

- Lightweight Rust-based shell.
- System tray integration.
- Native notifications.
- Bundled web frontend.

**Build:**
```bash
cd src-tauri
cargo tauri build
```

---

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
ruff check src/
ruff format src/
```

### Useful Scripts

```bash
# Reset local data
python scripts/reset_data.py

# Migrate to new project structure
python scripts/migrate_to_project_structure.py

# Build desktop sidecar
bash scripts/build-sidecar.sh
```

---

## Roadmap

### Phase 1: Passive Radar ✅
- [x] Auto-entity extraction
- [x] Link suggestions
- [x] Conflict detection

### Phase 2: Active Radar 🚧
- [ ] Editor Radar — sidebar shows related notes based on draft context
- [ ] Smart Paste — detect duplicates and suggest merges

### Phase 3: Knowledge Graph Visualization
- [ ] Interactive graph view
- [ ] Orphan detection & visualization

See [`docs/PRODUCT_ROADMAP.md`](docs/PRODUCT_ROADMAP.md) for the full roadmap.

---

## License

This project is licensed under the **Apache License 2.0**.

See [LICENSE](LICENSE) for details.

---

<p align="center">
  <i>Built for thinkers who want their knowledge to compound — not just accumulate.</i>
</p>
