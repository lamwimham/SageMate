"""
Language-aware slug generator for SageMate.

Design philosophy:
- A slug is a human-readable identifier used in [[wikilinks]].
- It must be natural to read and type.
- Language consistency: Chinese docs get Chinese slugs, English docs get English slugs.
- URL-safe and filesystem-safe.

Strategy Pattern:
- _ChineseSlugStrategy:  preserves CJK characters, removes spaces/punctuation.
- _EnglishSlugStrategy:  kebab-case, lowercase.
"""

from __future__ import annotations

import re
import uuid


class SlugGenerator:
    """
    Generates semantic, language-aware slugs from document titles.

    Usage:
        SlugGenerator.generate("Sora 技术报告")      → "Sora技术报告"
        SlugGenerator.generate("Sora Technical Report") → "sora-technical-report"
        SlugGenerator.generate("人工智能入门")         → "人工智能入门"
        SlugGenerator.generate("GPT-4 技术解析")       → "GPT-4技术解析"
    """

    # Characters we allow in slugs
    _CJK_RE = re.compile(r"[\u4e00-\u9fff]")
    _LATIN_RE = re.compile(r"[a-zA-Z]")

    @classmethod
    def _is_chinese_dominant(cls, text: str) -> bool:
        """
        Determine whether the text is predominantly Chinese.
        Tie goes to Chinese (more natural for mixed CJK-Latin titles
        common in Chinese technical writing).
        """
        cjk_count = len(cls._CJK_RE.findall(text))
        latin_count = len(cls._LATIN_RE.findall(text))
        return cjk_count >= latin_count

    @classmethod
    def generate(cls, title: str, prefix: str = "") -> str:
        """
        Generate a slug from a title.

        Args:
            title: The document / page title.
            prefix: Optional prefix (e.g. "raw"). Pass empty string
                    for semantic slugs without artificial prefixes.

        Returns:
            A filesystem-safe, URL-safe slug string.
        """
        title = title.strip()
        if not title:
            return f"untitled-{uuid.uuid4().hex[:6]}"

        if cls._is_chinese_dominant(title):
            slug = cls._generate_chinese_slug(title)
        else:
            slug = cls._generate_english_slug(title)

        if not slug:
            slug = f"untitled-{uuid.uuid4().hex[:6]}"

        if prefix:
            slug = f"{prefix}-{slug}"

        return slug

    @staticmethod
    def _generate_chinese_slug(title: str) -> str:
        """
        Chinese-mode slug generation.

        - Keep CJK characters, alphanumeric, and hyphens within Latin words.
        - Remove spaces (Chinese doesn't need them for readability).
        - Remove punctuation.

        Examples:
            "Sora 技术报告"      → "Sora技术报告"
            "人工智能入门指南"    → "人工智能入门指南"
            "GPT-4 技术解析"     → "GPT-4技术解析"
            "深度学习的 (2024)"   → "深度学习的2024"
        """
        # Keep: CJK, Latin letters, digits, hyphens (preserve things like GPT-4)
        slug = re.sub(r"[^\w\u4e00-\u9fff\-]", "", title)
        # Remove spaces (CJK text is readable without them)
        slug = slug.replace(" ", "")
        # Collapse consecutive hyphens
        slug = re.sub(r"\-{2,}", "-", slug)
        slug = slug.strip("-")
        return slug

    @staticmethod
    def _generate_english_slug(title: str) -> str:
        """
        English-mode slug generation (kebab-case).

        Examples:
            "Sora Technical Report" → "sora-technical-report"
            "Introduction to AI"    → "introduction-to-ai"
            "What's New in 2024?"   → "whats-new-in-2024"
        """
        slug = title.lower()
        slug = re.sub(r"[\s_]+", "-", slug)
        # Keep only lowercase letters, digits, hyphens
        slug = re.sub(r"[^a-z0-9\-]", "", slug)
        slug = re.sub(r"\-{2,}", "-", slug)
        slug = slug.strip("-")
        return slug
