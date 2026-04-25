---
title: SageMate Core
category: project
status: active
priority: high
tags: [project, sagemate, pkm, ai]
created: 2025-12-01
updated: 2026-04-25
---

# SageMate Core

The main project: a personal knowledge management system with AI integration.

## Vision

Build a "Second Brain" that doesn't just store notes — it **thinks with you**.

Key differentiators from [[Obsidian]]:
1. Built-in AI Q&A with reasoning display
2. Automatic knowledge compilation from raw sources
3. Streaming everything — no waiting spinners

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Sources   │───→│   Compiler   │───→│  Wiki Pages │
│  (PDF/URL)  │    │   (LLM)      │    │ (Markdown)  │
└─────────────┘    └──────────────┘    └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │   Agent     │
                                       │  (Chat/QA)  │
                                       └─────────────┘
```

## Key Components

- [[playwright-stealth]] — anti-detection URL collection
- [[Streaming Response]] — real-time SSE for chat
- [[Formula Postprocessor]] — PDF LaTeX normalization
- [[MarkdownRenderer]] — KaTeX + wiki links

## Roadmap

### Q2 2026
- [x] Streaming chat with reasoning
- [x] WeChat article collection
- [x] KaTeX formula rendering
- [ ] Graph view for wiki links
- [ ] Mobile app (Tauri)

### Q3 2026
- [ ] Collaborative editing (CRDT)
- [ ] Plugin system
- [ ] Public API

## Related

- [[Personal-Website]] — shares design system
- [[PKM]] — parent concept
- [[Investment-Research]] — uses SageMate for research notes

---
#project #sagemate
