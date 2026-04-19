# Wiki Conventions

This document defines the structure, formatting, and workflow conventions for this wiki.
Co-evolved by the human and the LLM. Update as needed.

## Page Format

All wiki pages use YAML frontmatter:

```yaml
---
title: 'Page Title'
slug: page-slug
category: concept  # entity | concept | analysis | source
tags: ["tag1", "tag2"]
sources: ["source-slug"]
---
```

## Content Structure

1. **First paragraph**: Clear, self-contained summary/definition.
2. **Body**: Structured with `##` headings. Facts, examples, context.
3. **Related**: End with a "## Related" section using wikilinks `[[like-this]]`.

## Linking

- Use `[[wikilinks]]` to reference other wiki pages by slug.
- Always link to the slug, not the title.
- When creating a new page, add a backlink from relevant existing pages.

## Categories

| Category | Directory | When to Use |
|----------|-----------|-------------|
| `entity` | `wiki/entities/` | People, organizations, products, places, tools |
| `concept` | `wiki/concepts/` | Ideas, frameworks, theories, methodologies |
| `analysis` | `wiki/analyses/` | Comparisons, deep-dives, synthesized answers to questions |
| `source` | `wiki/sources/` | Per-source summaries (one per ingested document) |

## Ingest Workflow

1. Read the new source document.
2. Read `index.md` to understand current wiki scope.
3. Identify key entities and concepts.
4. Check if pages already exist — update them if so, create new ones if not.
5. Flag contradictions with existing content.
6. Update `index.md` with new/changed pages.
7. Append entry to `log.md`.

## Query Workflow

1. Search wiki for relevant pages.
2. Read and synthesize an answer with citations.
3. If the answer is a valuable analysis, save it to `wiki/analyses/`.

## Lint Priorities

1. **High**: Contradictions between pages.
2. **Medium**: Broken links, stale claims (>30 days).
3. **Low**: Orphan pages, missing cross-refs.
