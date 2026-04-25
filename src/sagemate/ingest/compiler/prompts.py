"""
Compile Prompts — Centralized prompt templates and JSON schema for knowledge compilation.

Design Patterns:
- Builder: CompilePromptBuilder constructs prompts and schema based on detail_level.
- Single Source of Truth: All prompt text and schema definitions live here,
  eliminating duplication between IncrementalCompiler (pipeline) and CompileStrategy.

Usage:
    from .prompts import CompilePromptBuilder, COMPILE_RESPONSE_SCHEMA

    builder = CompilePromptBuilder(conventions=conventions, detail_level="comprehensive")
    system_prompt = builder.build_system_prompt()
    compile_prompt  = builder.build_compile_prompt(title, slug, content, index_ctx)
    schema          = builder.build_response_schema()
"""

from __future__ import annotations


class CompilePromptBuilder:
    """
    Builds system prompts, compile prompts, and response schemas for LLM compilation.

    detail_level controls information density:
        concise       — Summaries only, minimal detail.
        comprehensive — Full detail with examples and reasoning preserved (default).
        exhaustive    — Maximum detail, every data point preserved.
    """

    _DETAIL_CONFIGS: dict[str, dict[str, str]] = {
        "concise": {
            "system_rule": (
                "Use concise, informative markdown. Each page should be self-contained."
            ),
            "summary_desc": (
                "A concise abstract (3-5 sentences) explaining what this document is about."
            ),
            "content_desc": (
                "Concise markdown content for this wiki page. Focus on key points only."
            ),
            "page_focus": "Keep pages focused — one concept per page.",
        },
        "comprehensive": {
            "system_rule": (
                "Use detailed, comprehensive markdown. Preserve key details, examples, data points, "
                "and reasoning from the source. Do NOT omit information for brevity. "
                "Each page should be self-contained and thorough."
            ),
            "summary_desc": (
                "A comprehensive abstract explaining what this document is about. "
                "Include the document's scope, methodology, key findings, and implications."
            ),
            "content_desc": (
                "Detailed markdown content for this wiki page. "
                "Preserve important details, examples, data points, and reasoning from the source. "
                "Do NOT summarize or compress for brevity. "
                "Use headings (##, ###) for structure. "
                "Include a clear definition in the first paragraph, "
                "detailed explanation with examples in the body, "
                "and a '## Related' section at the end with wikilinks."
            ),
            "page_focus": (
                "Keep pages focused — one concept per page, but be thorough within each page. "
                "Include specific examples, data, and reasoning from the source."
            ),
        },
        "exhaustive": {
            "system_rule": (
                "Use exhaustive, highly detailed markdown. Preserve ALL information from the source: "
                "every example, every data point, every argument, every caveat. "
                "Do NOT summarize, condense, or omit anything. "
                "If a concept is complex, use multiple sections with detailed explanations. "
                "Each page should be a complete reference on its topic."
            ),
            "summary_desc": (
                "An exhaustive abstract covering all major sections, methodologies, findings, "
                "and implications of the document. Leave nothing out."
            ),
            "content_desc": (
                "Exhaustive markdown content for this wiki page. "
                "Preserve ALL details, examples, data points, edge cases, and reasoning from the source. "
                "Do NOT summarize or condense. Use extensive headings (##, ###, ####) for structure. "
                "Include: (1) precise definition, (2) full explanation with all examples, "
                "(3) data and evidence, (4) edge cases and caveats, "
                "(5) step-by-step breakdowns where applicable, "
                "(6) a '## Related' section with comprehensive wikilinks."
            ),
            "page_focus": (
                "Be exhaustive. If a concept has many facets, cover them all in detail. "
                "Use multiple subsections. Never say 'etc.' or 'and so on' — write it all out."
            ),
        },
    }

    def __init__(self, conventions: str = "", detail_level: str = "comprehensive"):
        if detail_level not in self._DETAIL_CONFIGS:
            raise ValueError(
                f"detail_level must be one of {list(self._DETAIL_CONFIGS.keys())}, "
                f"got {detail_level!r}"
            )
        self._conventions = conventions
        self._detail = self._DETAIL_CONFIGS[detail_level]

    # ── Prompts ───────────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        """Return the system prompt injected into every LLM compile call."""
        return f"""You are a Knowledge Compiler for a personal wiki (Second Brain).
Your job is to read new source documents and incrementally update the wiki.

CRITICAL LANGUAGE RULE: You MUST write the wiki pages in the EXACT SAME LANGUAGE as the source document.
- If the source is in Chinese, write ALL wiki content in Chinese.
- If the source is in English, write in English.
- NEVER translate the source content. Preserve all original terminology.

SLUG RULE (critical for wikilinks):
- The slug is the identifier inside [[wikilinks]]. It MUST be human-readable.
- For Chinese pages: use Chinese slugs (e.g. [[扩散模型]], [[Sora技术报告]]).
  Remove spaces between Chinese characters. Keep Latin acronyms as-is.
- For English pages: use lowercase-kebab-case (e.g. [[diffusion-model]], [[sora-technical-report]]).
- Match the language of the page title. Do NOT romanize Chinese titles into pinyin.

Rules:
1. Extract key entities (people, orgs, products) and concepts from the source.
2. Create new wiki pages for important entities and concepts.
3. {self._detail['system_rule']}
4. Include wikilinks [[slug]] to reference other wiki pages.
5. Flag any claims that seem to contradict existing wiki content.
6. {self._detail['page_focus']}
7. Categories: 'entity' for people/orgs/products, 'concept' for ideas/frameworks, 'analysis' for comparisons.

Page format:
- Start with a clear definition/summary in the first paragraph.
- Use headings for structure.
- End with a "Related" section linking to other wiki pages.
- Use YAML frontmatter with: title, slug, category, tags.

FORMATTING RULES (preserve formulas and code):
- If the source contains mathematical formulas (e.g. $E=mc^2$, Greek letters, summations, integrals), 
  wrap them in LaTeX: inline formulas in $...$, block formulas in $$...$$.
- If the source contains code-like expressions, pseudocode, or formulaic alphas 
  (e.g. rank(Ts_ArgMax(...)), (close - open) / open, correlation(x, y, 10)),
  wrap them in Markdown code blocks (```language ... ```) or inline code (`...`).
- Preserve ALL original formulas and expressions exactly — do NOT simplify, rephrase, or omit them.

{self._conventions}"""

    def build_compile_prompt(
        self,
        source_title: str,
        source_slug: str,
        source_content: str,
        index_context: str,
    ) -> str:
        """Return the user prompt that carries the document + wiki context."""
        return f"""Analyze the following source document and integrate its knowledge into the wiki.

## Source: {source_title} (slug: {source_slug})

{source_content}

## Current Wiki Index

{index_context}

## Task

Read the source document and perform two actions:

### Action 1: Create a "Source Archive"
Generate a high-level summary of this document to serve as the "Hub Page" for this file.
- **summary**: {self._detail['summary_desc']}
- **key_takeaways**: 3-5 bullet points of the most important arguments or conclusions.
- **extracted_concepts**: List the slugs of the specific knowledge pages you are about to create.

### Action 2: Extract Knowledge Pages
Create new wiki pages for key entities and concepts found in the source.
- **IMPORTANT**: Identify the source page numbers. The input text contains markers like `<!-- page=1 -->`, `<!-- page=2 -->`.
  - For each wiki page you create, you MUST extract the list of page numbers (integers) that contributed to that content and put them in the `source_pages` field.

Return a JSON object with:
- source_archive: The summary object (slug, title, summary, key_takeaways, extracted_concepts).
- new_pages: array of wiki pages to create (each with slug, title, category, content, source_pages, tags, outbound_links).
- contradictions: array of any contradictions found (empty if none)."""

    # ── Schema ────────────────────────────────────────────────────

    def build_response_schema(self) -> dict:
        """Return the JSON schema with detail-level-aware field descriptions."""
        return {
            "name": "compile_result",
            "schema": {
                "type": "object",
                "properties": {
                    "source_archive": {
                        "type": "object",
                        "description": (
                            "A high-level summary of the entire document. "
                            "Use this to create a 'Source Page' that acts as the hub for this document."
                        ),
                        "properties": {
                            "slug": {"type": "string"},
                            "title": {"type": "string"},
                            "summary": {
                                "type": "string",
                                "description": self._detail["summary_desc"],
                            },
                            "key_takeaways": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "3-5 core arguments or conclusions from the document.",
                            },
                            "extracted_concepts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of slugs for the knowledge pages you are creating from this doc.",
                            },
                        },
                        "required": [
                            "slug",
                            "title",
                            "summary",
                            "key_takeaways",
                            "extracted_concepts",
                        ],
                    },
                    "new_pages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "slug": {"type": "string"},
                                "title": {"type": "string"},
                                "category": {
                                    "type": "string",
                                    "enum": ["entity", "concept", "analysis", "source"],
                                },
                                "content": {
                                    "type": "string",
                                    "description": self._detail["content_desc"],
                                },
                                "source_pages": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": (
                                        "List of page numbers (integers) found in the source document "
                                        "corresponding to this content."
                                    ),
                                },
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "sources": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "outbound_links": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "slug",
                                "title",
                                "category",
                                "content",
                                "source_pages",
                            ],
                        },
                    },
                    "contradictions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["source_archive", "new_pages"],
            },
        }


# ── Backward-compatible constant (default detail level) ─────────

COMPILE_RESPONSE_SCHEMA = CompilePromptBuilder().build_response_schema()
