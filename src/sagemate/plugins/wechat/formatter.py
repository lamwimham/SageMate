"""Rich Text Formatter for WeChat Messages.

Converts structured responses into well-formatted WeChat-compatible text.
Supports: query responses with source attribution, structured summaries, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceRef:
    """A reference to a wiki page or source document."""
    title: str
    slug: str
    category: str = ""
    relevance: float = 1.0  # 0-1 confidence score


@dataclass
class RichReply:
    """A structured reply that can be rendered as formatted WeChat text."""
    title: str = ""
    sections: list[str] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    footer: str = ""
    is_from_knowledge: bool = False
    is_from_general: bool = False
    raw_text: str = ""  # Fallback plain text

    def render(self) -> str:
        """Render as WeChat-compatible formatted text."""
        if self.raw_text:
            return self.raw_text

        lines = []

        # Title
        if self.title:
            emoji = "📚" if self.is_from_knowledge else "💡"
            lines.append(f"{emoji} {self.title}")
            lines.append("")

        # Sections
        for i, section in enumerate(self.sections):
            if i > 0:
                lines.append("— " + "─" * 20)
                lines.append("")
            lines.append(section)

        # Source attribution
        if self.sources:
            lines.append("")
            lines.append("📎 来源:")
            for src in self.sources:
                cat = f" [{src.category}]" if src.category else ""
                lines.append(f"  • {src.title}{cat}")

        # Confidence badge
        if self.is_from_knowledge:
            lines.append("")
            lines.append("✅ 以上内容基于知识库")
        elif self.is_from_general:
            lines.append("")
            lines.append("💡 以上内容来自通用知识，请注意核实")

        # Footer
        if self.footer:
            lines.append("")
            lines.append(self.footer)

        return "\n".join(lines)


class ReplyFormatter:
    """Formats different response types into RichReply."""

    @staticmethod
    def query_response(
        question: str,
        answer: str,
        sources: list[dict] | None = None,
        confidence: float = 1.0,
    ) -> RichReply:
        """Format a knowledge base query response."""
        reply = RichReply(
            title=f"关于「{question}」",
            sections=[answer],
            is_from_knowledge=True,
        )

        if sources:
            for src in sources[:5]:  # Max 5 sources
                reply.sources.append(SourceRef(
                    title=src.get("title", "Unknown"),
                    slug=src.get("slug", ""),
                    category=src.get("category", ""),
                ))

        if confidence < 0.5:
            reply.footer = "⚠️ 知识库相关内容较少，答案可能不够完整。"

        return reply

    @staticmethod
    def not_found(question: str) -> RichReply:
        """Format a 'not found in knowledge base' response."""
        return RichReply(
            title=f"关于「{question}」",
            sections=[
                "知识库暂时没有收录相关信息。",
                "",
                "你可以：",
                "1. 发送相关文章/文档让我归档",
                "2. 换一个问题试试",
                "3. 直接和我闲聊 😊"
            ],
            footer="💡 提示：发送 PDF/文章/URL 可自动归档到知识库"
        )

    @staticmethod
    def general_knowledge(answer: str, question: str = "") -> RichReply:
        """Format a general knowledge response (not from wiki)."""
        title = f"关于「{question}」" if question else "通用知识回答"
        return RichReply(
            title=title,
            sections=[answer],
            is_from_general=True,
            footer="⚠️ 此答案来自通用知识，非知识库内容"
        )

    @staticmethod
    def ingest_success(filename: str, slug: str, pages_created: int = 0) -> RichReply:
        """Format a successful ingestion response."""
        return RichReply(
            title="归档成功",
            sections=[
                f"📄 文件: {filename}",
                f"🆔 编号: {slug}",
                f"📚 新增页面: {pages_created}",
            ],
            footer="✅ 文档已归档，可随时查询相关内容"
        )

    @staticmethod
    def url_ingest_success(title: str, slug: str) -> RichReply:
        """Format a successful URL ingestion response."""
        return RichReply(
            title="链接归档成功",
            sections=[
                f"🔗 标题: {title}",
                f"🆔 编号: {slug}",
            ],
            footer="✅ 文章已归档到知识库"
        )

    @staticmethod
    def voice_transcript(text: str, duration_hint: str = "") -> RichReply:
        """Format a voice transcription result."""
        sections = [f"🎤 转写结果:\n{text}"]
        if duration_hint:
            sections.append(f"⏱️ 时长: {duration_hint}")
        return RichReply(
            title="语音已转写",
            sections=sections,
            footer="✅ 语音内容已归档到知识库"
        )
