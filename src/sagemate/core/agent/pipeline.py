"""Agent Pipeline — Core intelligence hub for all channels.

Pipeline: AgentMessage → Intent Routing → Dispatch → AgentResponse
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from datetime import datetime

from .types import AgentMessage, AgentResponse, Intent
from .router import IntentRouter
from .session import SessionManager
from .intent_clarification import IntentClarificationHandler
from ...ingest.service import IngestService
from ...ingest.adapters.vision_parser import VisionClassifier, VisionParser
from ...ingest.adapters.file_parser import DeterministicParser
from ...ingest.adapters.archive_helper import ArchiveHelper
from ...core.chat import (
    ChatMessage,
    ChatSession,
    IntentClarificationContent,
    MessageDirection,
    MessageStatus,
    SessionState,
    TextContent,
)

logger = logging.getLogger(__name__)

# ── System Prompts ───────────────────────────────────────────

CHAT_SYSTEM_PROMPT = (
    "你是 SageMate，一个运行在用户个人设备上的智能助手（第二大脑）。\n"
    "你的任务是帮助用户回答关于知识库的问题。\n"
    "语气亲切、专业、简洁（中文为主）。\n\n"
    "【回答规则 — 必须遵守】\n"
    "1. 当提供了【知识库上下文】时，你必须 ONLY 基于该上下文回答。\n"
    "   - 不要引入外部知识，不要编造不在上下文中的事实。\n"
    "   - 如果上下文不足以回答问题，明确说：'知识库中暂无此问题的详细信息。'\n"
    "   - 引用来源时使用 [[slug]] 格式（如 [[concept-slug]]），自然地嵌入回答中。\n"
    "   - 禁止在回答末尾自行添加编号列表（如 [1]、[2] 等）。\n"
    "2. 当没有【知识库上下文】（仅有通用知识提示）时：\n"
    "   - 如果用户问的是具体事实、数据、人名、日期，回答：'这个问题我的知识库暂时没有收录，无法确认准确性。'\n"
    "   - 如果用户问的是通用建议、思路、方法，可以回答，但必须在开头标注 '💡 [通用知识]'。\n"
    "3. 永远不要编造具体数据、统计数字、人名、日期、产品名称。\n"
    "4. 如果不确定，诚实地说不知道，比编造答案更好。\n"
    "5. 回答要简洁，不要啰嗦。"
)


QUERY_SYSTEM_PROMPT = (
    "你是一位知识管理专家。你的任务是基于提供的 Wiki 页面内容，进行综合分析和深度回答。"
    "不要重复原文，要进行消化、关联和推理。用中文回答。"
)

QUERY_PROMPT_TEMPLATE = """基于下面提供的 Wiki 页面内容，回答用户的问题。

重要要求：
1. 不要简单罗列页面元数据（如 title、slug、tags 等），而是要**综合、消化、推理**页面中的实质知识内容
2. 回答应该是有机整合的，像一个知识专家在阐述观点，而非摘要列表
3. 使用 [[slug]] 格式引用来源，自然地嵌入到回答中
   - slug 是页面标识符，每个页面标题下方都标注了 (slug: xxx)
   - 禁止在回答末尾自行添加 [1]、[2] 等编号列表
   - 系统会自动处理引用编号和参考文献
4. 如果页面之间存在关联或矛盾，请指出并分析
5. 如果信息不足以完整回答，请明确说明"基于现有知识库..."

用户问题：{question}

## Wiki 页面内容：

{context}

请提供清晰、结构化、经过深度整合的回答。"""


def _build_fallback_answer(question: str, results: list) -> str:
    """Build a structured fallback answer when LLM is unavailable."""
    lines = [f"基于知识库中的 {len(results)} 个相关页面，以下是简要整理：\n"]
    for r in results:
        snippet = (r.snippet or "暂无摘要")[:300]
        snippet = re.sub(r'^---\s*\n[\s\S]*?\n---\s*\n', '', snippet)
        lines.append(f"### [{r.title}](/web/pages/{r.slug})")
        lines.append(f"{snippet}\n")
    lines.append("---")
    lines.append("💡 *提示：配置 LLM API Key 后可获得 AI 综合深度回答。*")
    return "\n".join(lines)


class AgentPipeline:
    """
    Main processing pipeline: standardized message -> intent routing -> dispatch -> response.
    
    v0.3: Added intent clarification flow for ambiguous inputs (images, files).
    """

    def __init__(self, store, settings, ingest_service: IngestService):
        self.store = store
        self.settings = settings
        self._ingest_service = ingest_service
        self.router = IntentRouter()
        self.sessions = SessionManager()
        self._clarification = IntentClarificationHandler()
        # ChatSession store: session_id → ChatSession
        self._chat_sessions: dict[str, ChatSession] = {}

    def _get_or_create_session(self, msg: AgentMessage) -> ChatSession:
        """Get existing ChatSession or create new one."""
        session_id = msg.session_id or f"{msg.channel}:{msg.user_id}"
        if session_id not in self._chat_sessions:
            self._chat_sessions[session_id] = ChatSession(
                id=session_id,
                channel=msg.channel,
                user_id=msg.user_id,
            )
        return self._chat_sessions[session_id]

    async def process(self, msg: AgentMessage) -> AgentResponse:
        """Process an incoming message and return a structured response."""
        logger.info(
            f"[AgentPipeline] channel={msg.channel} user={msg.user_id} "
            f"content_type={msg.content_type} text_len={len(msg.text)} "
            f"session={msg.session_id}"
        )

        session = self._get_or_create_session(msg)

        # ── Phase 1: Handle clarification responses ──────────────────
        if session.state == SessionState.AWAITING_INTENT:
            if self._clarification.is_clarification_response(session, msg):
                # User responded to a clarification card
                option_id = msg.text.strip().lower()
                updated_session, resolved_msg = self._clarification.resolve_selection(
                    session, option_id
                )
                self._chat_sessions[session.id] = updated_session
                if resolved_msg:
                    # Process the resolved intent
                    return await self._process_with_intent(resolved_msg, bypass_router=True)
                else:
                    # Ignore or error — return the confirmation message
                    last_msg = updated_session.messages[-1] if updated_session.messages else None
                    if last_msg and isinstance(last_msg.content, TextContent):
                        return AgentResponse(reply_text=last_msg.content.text, action_taken="clarified")
                    return AgentResponse(reply_text="已处理。", action_taken="clarified")
            else:
                # User sent something else while waiting — cancel clarification
                logger.info(f"[AgentPipeline] User sent non-clarification response, cancelling")
                self._chat_sessions[session.id] = session.transition_to(SessionState.IDLE)
                # Fall through to normal processing

        # ── Phase 2: Check for new intent clarification request ─────
        if msg.raw_data.get("requires_intent_clarification"):
            updated_session, clarify_msg = self._clarification.create_clarification(
                session,
                content_type=msg.content_type,
                context_data=msg.raw_data,
            )
            self._chat_sessions[session.id] = updated_session
            # Return the clarification card content as AgentResponse
            if isinstance(clarify_msg.content, IntentClarificationContent):
                options_text = "\n".join(
                    f"{i+1}. {opt.label} — {opt.description}"
                    for i, opt in enumerate(clarify_msg.content.options)
                )
                reply = f"{clarify_msg.content.question}\n\n{options_text}"
                return AgentResponse(
                    reply_text=reply,
                    action_taken="intent_clarification",
                    suggested_followups=[opt.id for opt in clarify_msg.content.options],
                )

        # ── Phase 2.5: Content-type preprocessing ─────────────────────
        if msg.content_type == "image":
            preprocessed = await self._preprocess_image(msg)
            if preprocessed is None:
                return AgentResponse(
                    reply_text="📸 收到图片，已保存到原始资源。",
                    action_taken="saved_photo",
                )
            msg = preprocessed
        elif msg.content_type == "voice":
            msg = await self._preprocess_voice(msg)
        elif msg.content_type == "file":
            return await self._handle_file_ingest(msg)

        # ── Phase 3: Normal intent routing ────────────────────────────
        return await self._process_with_intent(msg, bypass_router=False)

    async def _preprocess_image(self, msg: AgentMessage) -> AgentMessage | None:
        """Classify and OCR an image. Returns None if photo/other (no text)."""
        file_path = msg.raw_data.get("file_path")
        if not file_path:
            logger.warning("[AgentPipeline] Image message missing file_path")
            return msg

        image_bytes = Path(file_path).read_bytes()

        vision_key = self.settings.vision_api_key or self.settings.llm_api_key
        vision_url = self.settings.vision_base_url or self.settings.llm_base_url
        vision_model = self.settings.vision_model or "glm-4v-plus"

        if not vision_key:
            logger.warning("[AgentPipeline] No vision API key configured, skipping OCR")
            return None

        # ── Fast path: GLM-OCR for Zhipu platform ──────────────────────
        if "bigmodel" in vision_url:
            try:
                from ...ingest.adapters.glm_ocr import GLMOCRClient
                client = GLMOCRClient(api_key=vision_key, base_url=vision_url)
                text = await client.parse_image(image_bytes)
                if text and text.strip():
                    logger.info(f"[AgentPipeline] Image OCR via GLM-OCR: {len(text)} chars")
                    return msg.model_copy(update={"text": text.strip(), "content_type": "text"})
                return None
            except Exception as e:
                logger.warning(f"[AgentPipeline] GLM-OCR failed ({e}), falling back to VisionParser")

        # ── Standard path: VisionClassifier + VisionParser ─────────────
        try:
            classifier = VisionClassifier(
                api_key=vision_key, base_url=vision_url, model=vision_model
            )
            image_class = await classifier.classify(image_bytes)
            logger.info(f"[AgentPipeline] Image classified as: {image_class}")

            if image_class in ("photo", "other"):
                return None

            parser = VisionParser(
                api_key=vision_key, base_url=vision_url, model=vision_model
            )
            text = await parser.parse_image(
                image_bytes, file_id=Path(file_path).stem, save_raw=False
            )

            if text == "__NO_TEXT__":
                return None

            return msg.model_copy(update={"text": text, "content_type": "text"})

        except Exception as e:
            logger.error(f"[AgentPipeline] Image preprocessing failed: {e}")
            return msg.model_copy(update={"text": f"[图片识别失败: {e}]", "content_type": "text"})

    async def _preprocess_voice(self, msg: AgentMessage) -> AgentMessage:
        """Transcribe a voice message to text."""
        from ...ingest.adapters.voice_parser import VoiceParser

        file_path = msg.raw_data.get("file_path")
        encode_type = msg.raw_data.get("encode_type", 6)

        if not file_path:
            logger.warning("[AgentPipeline] Voice message missing file_path")
            return msg

        try:
            voice_bytes = Path(file_path).read_bytes()
            text = await VoiceParser.parse_voice(
                voice_bytes,
                file_id=Path(file_path).stem,
                raw_dir=Path(file_path).parent,
                encode_type=encode_type,
            )
            return msg.model_copy(update={"text": text, "content_type": "text"})
        except Exception as e:
            logger.error(f"[AgentPipeline] Voice preprocessing failed: {e}")
            return msg.model_copy(update={"text": f"[语音转写失败: {e}]", "content_type": "text"})

    async def _handle_file_ingest(self, msg: AgentMessage) -> AgentResponse:
        """Ingest a file directly into the knowledge base."""
        file_path = msg.raw_data.get("file_path")
        file_name = msg.raw_data.get("file_name", "unknown")

        if not file_path or not Path(file_path).exists():
            return AgentResponse(
                reply_text="❌ 文件处理失败：找不到文件。",
                action_taken="failed",
            )

        try:
            slug, source_content = await DeterministicParser.parse(
                Path(file_path), self.settings.raw_dir
            )

            if self.settings.llm_api_key:
                await self._ingest_service.submit_compile(
                    source_slug=slug,
                    source_content=source_content,
                    source_title=file_name,
                    archive_path=Path(file_path),
                    source_type="file",
                )
                return AgentResponse(
                    reply_text=f"✅ 文件已归档\n编号: {slug}\n正在后台编译为 Wiki 页面...",
                    action_taken="ingested",
                )
            else:
                return AgentResponse(
                    reply_text=f"✅ 文件已归档\n编号: {slug}\n（未启用自动编译）",
                    action_taken="ingested",
                )
        except Exception as e:
            logger.error(f"[AgentPipeline] File ingest failed: {e}")
            # Distinguish PDF parse errors for better UX
            err_msg = str(e)
            if "PDF" in err_msg or "pdftotext" in err_msg or "GLM-OCR" in err_msg:
                reply = f"❌ PDF 解析失败: {err_msg}\n\n建议: 若文件为扫描件，请确认已配置 GLM-OCR（智谱 API）或安装 Poppler。"
            else:
                reply = f"❌ 文件归档失败: {err_msg}"
            return AgentResponse(
                reply_text=reply,
                action_taken="failed",
            )

    async def _process_with_intent(self, msg: AgentMessage, bypass_router: bool = False) -> AgentResponse:
        """Process message with intent routing or bypass (for resolved clarifications)."""

        # ── Intent routing ─────────────────────────────────────────
        if bypass_router and msg.raw_data.get("_resolved_intent"):
            # Use pre-resolved intent from clarification
            intent_str = msg.raw_data["_resolved_intent"]
            from .router import RouterResult
            result = RouterResult(intent=Intent(intent_str), confidence=1.0)
            logger.info(f"[AgentPipeline] Using resolved intent={intent_str} (bypass router)")
        else:
            result = await self.router.route(msg.text)
            logger.info(f"[AgentPipeline] Intent={result.intent.value} confidence={result.confidence:.2f}")

        if result.intent == Intent.IGNORE:
            return AgentResponse(reply_text="", action_taken="ignored")

        if result.intent == Intent.QUERY:
            return await self._handle_query(msg)

        if result.intent == Intent.INGEST:
            return await self._handle_ingest(msg)

        return await self._handle_chat(msg)

    # ── Query Handler ──────────────────────────────────────────

    @staticmethod
    def _format_citations(answer: str, related_pages: list[dict]) -> tuple[str, list[dict]]:
        """
        Convert [[slug]] wikilink citations to [1], [2] paper-style citations.
        If LLM didn't use [[slug]] format, clean up self-generated [n] patterns
        and build a clean reference list from related_pages.
        Returns (formatted_answer, references_list).
        """
        import re

        slug_pattern = r'\[\[([^\]]+)\]\]'
        found_slugs = re.findall(slug_pattern, answer)

        title_lookup = {rp["slug"]: rp.get("title", rp["slug"]) for rp in related_pages}

        if found_slugs:
            # Normal path: LLM used [[slug]] format
            seen = []
            for slug in found_slugs:
                if slug not in seen:
                    seen.append(slug)

            formatted = answer
            for i, slug in enumerate(seen, 1):
                formatted = formatted.replace(f'[[{slug}]]', f'[{i}]')

            references = []
            for i, slug in enumerate(seen, 1):
                references.append({
                    "number": i,
                    "slug": slug,
                    "title": title_lookup.get(slug, slug),
                })
            return formatted, references

        # Fallback: LLM didn't use [[slug]] — clean up self-generated [n] garbage
        # Remove isolated [n] lines (e.g. "[1]" on its own line)
        answer = re.sub(r'^\s*\[\d+\]\s*$', '', answer, flags=re.MULTILINE)
        # Remove [n] prefix from lines that have actual content
        answer = re.sub(r'^\s*\[\d+\]\s+', '', answer, flags=re.MULTILINE)
        # Collapse excessive blank lines
        answer = re.sub(r'\n{3,}', '\n\n', answer).strip()

        # Build clean references from related_pages
        references = []
        for i, rp in enumerate(related_pages, 1):
            references.append({
                "number": i,
                "slug": rp["slug"],
                "title": title_lookup.get(rp["slug"], rp["slug"]),
            })

        # Append a clean reference section
        if related_pages:
            ref_lines = ["\n\n---\n\n**相关页面：**"]
            for i, rp in enumerate(related_pages, 1):
                title = title_lookup.get(rp["slug"], rp["slug"])
                ref_lines.append(f"{i}. [[{rp['slug']}]] — {title}")
            answer += "\n".join(ref_lines)

        return answer, references

    async def query(self, question: str) -> tuple[str, list[str], list[dict]]:
        """
        Query the knowledge base. Returns (answer, source_slugs, related_pages).
        This is the shared core logic used by both /query endpoint and Agent pipeline.
        """
        # Step 1: Pass the raw question to store.search()
        # store.search() handles jieba tokenization and FTS5 query building internally.
        # We do NOT pre-extract keywords or join with OR here — that causes
        # double-OR problems when _search_fts5_jieba tokenizes the query again.
        results = await self.store.search(question, limit=5)

        if not results:
            return "No relevant wiki pages found for this query.", [], [], []

        # Step 2: Read relevant pages & strip frontmatter
        page_contents = []
        sources = []
        for r in results:
            page = await self.store.get_page(r.slug)
            if page:
                try:
                    content = Path(page.file_path).read_text(encoding='utf-8')
                    content = re.sub(r'^---\s*\n[\s\S]*?\n---\s*\n', '', content)
                    content = content.strip()
                    if len(content) > 6000:
                        content = content[:6000] + "\n\n...[content truncated]"
                except Exception:
                    content = ""
                page_contents.append(f"### {r.title}\n\n{content}")
                sources.append(r.slug)

        # Step 3: LLM synthesis (if API key available)
        if self.settings.llm_api_key:
            try:
                from ...ingest.compiler.compiler import LLMClient
                llm = LLMClient(purpose="query")
                context = "\n\n---\n\n".join(page_contents)
                prompt = QUERY_PROMPT_TEMPLATE.format(question=question, context=context)
                answer = await llm.generate_text(
                    prompt=prompt,
                    system_prompt=QUERY_SYSTEM_PROMPT,
                    max_tokens=4000,
                )
            except Exception:
                logger.exception("LLM query synthesis failed, using fallback")
                answer = _build_fallback_answer(question, results)
        else:
            answer = _build_fallback_answer(question, results)

        # Step 4: Format citations [[slug]] → [1], [2]
        # Build related_pages metadata first (needed for title lookup)
        related_pages = []
        for r in results:
            page = await self.store.get_page(r.slug)
            if page:
                related_pages.append({
                    "slug": page.slug,
                    "title": page.title,
                    "category": page.category.value if page.category else "concept",
                    "summary": page.summary or r.snippet or "暂无摘要",
                    "updated_at": page.updated_at.isoformat() if page.updated_at else None,
                    "word_count": page.word_count,
                })

        answer, citations = self._format_citations(answer, related_pages)

        return answer, sources, related_pages, citations

    async def query_stream(self, question: str):
        """
        Stream a query response via AsyncGenerator.

        Yields event dicts:
          - {"type": "sources", "sources": [...]} — search results metadata
          - {"type": "token",   "token": "..."}   — LLM output token
          - {"type": "done",    "answer": "...", "references": [...]} — final formatted answer
        """
        # Step 1: Search
        results = await self.store.search(question, limit=5)

        if not results:
            yield {"type": "done", "answer": "No relevant wiki pages found for this query.", "references": []}
            return

        # Step 2: Read relevant pages
        page_contents = []
        sources = []
        related_pages = []
        for r in results:
            page = await self.store.get_page(r.slug)
            if page:
                try:
                    content = Path(page.file_path).read_text(encoding='utf-8')
                    content = re.sub(r'^---\s*\n[\s\S]*?\n---\s*\n', '', content)
                    content = content.strip()
                    if len(content) > 6000:
                        content = content[:6000] + "\n\n...[content truncated]"
                except Exception:
                    content = ""
                page_contents.append(f"### {r.title}\n\n{content}")
                sources.append(r.slug)
                related_pages.append({
                    "slug": page.slug,
                    "title": page.title,
                    "category": page.category.value if page.category else "concept",
                    "summary": page.summary or r.snippet or "暂无摘要",
                    "updated_at": page.updated_at.isoformat() if page.updated_at else None,
                    "word_count": page.word_count,
                })

        yield {"type": "sources", "sources": related_pages}

        # Step 3: LLM synthesis (streaming)
        if self.settings.llm_api_key:
            try:
                from ...ingest.compiler.compiler import LLMClient
                llm = LLMClient(purpose="query")
                context = "\n\n---\n\n".join(page_contents)
                prompt = QUERY_PROMPT_TEMPLATE.format(question=question, context=context)

                full_answer = ""
                full_thinking = ""
                async for chunk in llm.generate_text_stream(
                    prompt=prompt,
                    system_prompt=QUERY_SYSTEM_PROMPT,
                    max_tokens=4000,
                ):
                    if chunk.is_reasoning:
                        full_thinking += chunk.text
                        yield {"type": "thinking", "token": chunk.text}
                    else:
                        full_answer += chunk.text
                        yield {"type": "token", "token": chunk.text}

                # Format citations after full generation
                formatted_answer, references = self._format_citations(full_answer, related_pages)
                yield {"type": "done", "answer": formatted_answer, "references": references, "thinking": full_thinking or None}

            except Exception:
                logger.exception("LLM query synthesis failed, using fallback")
                answer = _build_fallback_answer(question, results)
                formatted_answer, references = self._format_citations(answer, related_pages)
                yield {"type": "done", "answer": formatted_answer, "references": references}
        else:
            answer = _build_fallback_answer(question, results)
            formatted_answer, references = self._format_citations(answer, related_pages)
            yield {"type": "done", "answer": formatted_answer, "references": references}

    async def _handle_query(self, msg: AgentMessage) -> AgentResponse:
        """Handle QUERY intent: search knowledge base and synthesize answer."""
        answer, sources, related_pages, citations = await self.query(msg.text)

        # Append to session history
        self.sessions.append(msg.session_id, "user", msg.text)
        self.sessions.append(msg.session_id, "assistant", answer)

        return AgentResponse(
            reply_text=answer,
            action_taken="queried",
            sources=[{"slug": s} for s in sources],
            citations=citations,
            related_pages=related_pages,
            conversation_id=msg.session_id,
        )

    # ── Chat Handler ───────────────────────────────────────────

    async def _handle_chat(self, msg: AgentMessage) -> AgentResponse:
        """Handle CHAT intent: general conversation via LLM.

        Even for CHAT intent, we first try to retrieve relevant KB context.
        If found, inject it so the LLM can answer from the knowledge base.
        """
        if not self.settings.llm_api_key:
            return AgentResponse(
                reply_text="SageMate: 系统未连接 LLM，无法进行闲聊。",
                action_taken="chatted",
            )

        try:
            from ...ingest.compiler.compiler import LLMClient
            llm = LLMClient(purpose="chat")

            # ── Step 1: Always try to retrieve KB context ──────────
            kb_context = ""
            related_pages = []
            search_results = await self.store.search(msg.text, limit=3)
            if search_results:
                page_contents = []
                for r in search_results:
                    page = await self.store.get_page(r.slug)
                    if page:
                        try:
                            content = Path(page.file_path).read_text(encoding='utf-8')
                            content = re.sub(r'^---\s*\n[\s\S]*?\n---\s*\n', '', content)
                            content = content.strip()
                            if len(content) > 3000:
                                content = content[:3000] + "\n\n...[content truncated]"
                        except Exception:
                            content = ""
                        page_contents.append(f"### {r.title} (slug: {r.slug})\n\n{content}")
                        related_pages.append({
                            "slug": page.slug,
                            "title": page.title,
                            "category": page.category.value if page.category else "concept",
                            "summary": page.summary or r.snippet or "暂无摘要",
                        })
                kb_context = "\n\n---\n\n".join(page_contents)

            # ── Step 2: Build prompt with optional KB context ──────
            history = self.sessions.get(msg.session_id)
            history_lines = []
            for item in history:
                role_label = "User" if item["role"] == "user" else "Assistant"
                history_lines.append(f"{role_label}: {item['content']}")

            if kb_context:
                # Inject KB context into the prompt
                kb_header = (
                    "以下是从你的知识库中检索到的相关页面内容。"
                    "请基于这些内容回答用户问题。\n\n"
                    f"{kb_context}\n\n"
                    "---\n\n"
                )
                prompt_parts = history_lines + [kb_header + f"User: {msg.text}", "Assistant:"]
            else:
                prompt_parts = history_lines + [f"User: {msg.text}", "Assistant:"]

            prompt = "\n\n".join(prompt_parts)

            answer = await llm.generate_text(
                prompt=prompt,
                system_prompt=CHAT_SYSTEM_PROMPT,
                max_tokens=2000,
            )

            # Update session
            self.sessions.append(msg.session_id, "user", msg.text)

            # Format citations for KB-backed answers
            if kb_context and related_pages:
                answer, citations = self._format_citations(answer, related_pages)
                action = "queried"
            else:
                citations = []
                action = "chatted"

            self.sessions.append(msg.session_id, "assistant", answer)

            return AgentResponse(
                reply_text=answer,
                action_taken=action,
                citations=citations,
                related_pages=related_pages if kb_context else [],
                conversation_id=msg.session_id,
            )

        except Exception as e:
            logger.error(f"Chat LLM error: {e}")
            return AgentResponse(
                reply_text=f"SageMate: 大脑暂时短路了 ({str(e)})。",
                action_taken="chatted",
                conversation_id=msg.session_id,
            )

    # ── Streaming Handlers ─────────────────────────────────────

    async def process_stream(self, msg: AgentMessage):
        """Stream-process an incoming message.

        Yields event dicts:
          - {"type": "status", "status": "retrieving"}
          - {"type": "sources", "sources": [...]}
          - {"type": "status", "status": "generating"}
          - {"type": "token", "token": "..."}
          - {"type": "done", "answer": "...", "citations": [...], "related_pages": [...], "action_taken": "..."}
          - {"type": "intent_clarification", "question": "...", "options": [...]}
          - {"type": "error", "message": "..."}
        """
        session = self._get_or_create_session(msg)

        # ── Phase 1: Handle clarification responses ──────────────────
        if session.state == SessionState.AWAITING_INTENT:
            if self._clarification.is_clarification_response(session, msg):
                option_id = msg.text.strip().lower()
                updated_session, resolved_msg = self._clarification.resolve_selection(
                    session, option_id
                )
                self._chat_sessions[session.id] = updated_session
                if resolved_msg:
                    async for event in self._process_with_intent_stream(resolved_msg, bypass_router=True):
                        yield event
                    return
                else:
                    last_msg = updated_session.messages[-1] if updated_session.messages else None
                    if last_msg and isinstance(last_msg.content, TextContent):
                        yield {"type": "done", "answer": last_msg.content.text, "action_taken": "clarified"}
                    else:
                        yield {"type": "done", "answer": "已处理。", "action_taken": "clarified"}
                    return
            else:
                self._chat_sessions[session.id] = session.transition_to(SessionState.IDLE)

        # ── Phase 2: Check for new intent clarification request ─────
        if msg.raw_data.get("requires_intent_clarification"):
            updated_session, clarify_msg = self._clarification.create_clarification(
                session, content_type=msg.content_type, context_data=msg.raw_data,
            )
            self._chat_sessions[session.id] = updated_session
            if isinstance(clarify_msg.content, IntentClarificationContent):
                options = [
                    {"id": opt.id, "label": opt.label, "description": opt.description, "primary": i == 0}
                    for i, opt in enumerate(clarify_msg.content.options)
                ]
                yield {
                    "type": "intent_clarification",
                    "question": clarify_msg.content.question,
                    "options": options,
                }
                return

        # ── Phase 2.5: Content-type preprocessing ─────────────────────
        if msg.content_type == "image":
            preprocessed = await self._preprocess_image(msg)
            if preprocessed is None:
                yield {"type": "done", "answer": "📸 收到图片，已保存到原始资源。", "action_taken": "saved_photo"}
                return
            msg = preprocessed
        elif msg.content_type == "voice":
            msg = await self._preprocess_voice(msg)
        elif msg.content_type == "file":
            res = await self._handle_file_ingest(msg)
            yield {"type": "done", "answer": res.reply_text, "action_taken": res.action_taken}
            return

        # ── Phase 3: Normal intent routing (streaming) ───────────────
        async for event in self._process_with_intent_stream(msg, bypass_router=False):
            yield event

    async def _process_with_intent_stream(self, msg: AgentMessage, bypass_router: bool = False):
        """Stream-process with intent routing."""
        if bypass_router and msg.raw_data.get("_resolved_intent"):
            intent_str = msg.raw_data["_resolved_intent"]
            from .router import RouterResult
            result = RouterResult(intent=Intent(intent_str), confidence=1.0)
        else:
            result = await self.router.route(msg.text)

        if result.intent == Intent.IGNORE:
            yield {"type": "done", "answer": "", "action_taken": "ignored"}
            return

        if result.intent == Intent.QUERY:
            async for event in self._handle_query_stream(msg):
                yield event
            return

        if result.intent == Intent.INGEST:
            res = await self._handle_ingest(msg)
            yield {"type": "done", "answer": res.reply_text, "action_taken": res.action_taken}
            return

        # CHAT
        async for event in self._handle_chat_stream(msg):
            yield event

    async def _handle_chat_stream(self, msg: AgentMessage):
        """Stream CHAT intent: retrieve KB context then stream LLM tokens."""
        if not self.settings.llm_api_key:
            yield {"type": "done", "answer": "SageMate: 系统未连接 LLM，无法进行闲聊。", "action_taken": "chatted"}
            return

        try:
            from ...ingest.compiler.compiler import LLMClient
            llm = LLMClient(purpose="chat")

            # ── Step 1: Retrieve KB context ────────────────────────
            yield {"type": "status", "status": "retrieving"}

            kb_context = ""
            related_pages = []
            search_results = await self.store.search(msg.text, limit=3)
            if search_results:
                page_contents = []
                for r in search_results:
                    page = await self.store.get_page(r.slug)
                    if page:
                        try:
                            content = Path(page.file_path).read_text(encoding='utf-8')
                            content = re.sub(r'^---\s*\n[\s\S]*?\n---\s*\n', '', content)
                            content = content.strip()
                            if len(content) > 3000:
                                content = content[:3000] + "\n\n...[content truncated]"
                        except Exception:
                            content = ""
                        page_contents.append(f"### {r.title} (slug: {r.slug})\n\n{content}")
                        related_pages.append({
                            "slug": page.slug,
                            "title": page.title,
                            "category": page.category.value if page.category else "concept",
                            "summary": page.summary or r.snippet or "暂无摘要",
                        })
                kb_context = "\n\n---\n\n".join(page_contents)
                yield {"type": "sources", "sources": related_pages}

            # ── Step 2: Build prompt ───────────────────────────────
            history = self.sessions.get(msg.session_id)
            history_lines = []
            for item in history:
                role_label = "User" if item["role"] == "user" else "Assistant"
                history_lines.append(f"{role_label}: {item['content']}")

            if kb_context:
                kb_header = (
                    "以下是从你的知识库中检索到的相关页面内容。"
                    "请基于这些内容回答用户问题。\n\n"
                    f"{kb_context}\n\n"
                    "---\n\n"
                )
                prompt_parts = history_lines + [kb_header + f"User: {msg.text}", "Assistant:"]
            else:
                prompt_parts = history_lines + [f"User: {msg.text}", "Assistant:"]

            prompt = "\n\n".join(prompt_parts)

            # ── Step 3: Stream LLM output ──────────────────────────
            yield {"type": "status", "status": "generating"}

            full_answer = ""
            full_thinking = ""
            async for chunk in llm.generate_text_stream(
                prompt=prompt,
                system_prompt=CHAT_SYSTEM_PROMPT,
                max_tokens=2000,
            ):
                if chunk.is_reasoning:
                    full_thinking += chunk.text
                    yield {"type": "thinking", "token": chunk.text}
                else:
                    full_answer += chunk.text
                    yield {"type": "token", "token": chunk.text}

            # Update session
            self.sessions.append(msg.session_id, "user", msg.text)

            # Format citations
            if kb_context and related_pages:
                answer, citations = self._format_citations(full_answer, related_pages)
                action = "queried"
            else:
                answer = full_answer
                citations = []
                action = "chatted"

            self.sessions.append(msg.session_id, "assistant", answer)

            yield {
                "type": "done",
                "answer": answer,
                "action_taken": action,
                "citations": citations,
                "related_pages": related_pages if kb_context else [],
                "conversation_id": msg.session_id,
                "thinking": full_thinking or None,
            }

        except Exception as e:
            import traceback
            logger.error(f"Chat stream error: {e}\n{traceback.format_exc()}")
            yield {"type": "done", "answer": f"SageMate: 大脑暂时短路了 ({str(e)})。", "action_taken": "chatted"}

    async def _handle_query_stream(self, msg: AgentMessage):
        """Stream QUERY intent: wraps query_stream with unified event format."""
        question = msg.text
        results = await self.store.search(question, limit=5)

        if not results:
            yield {"type": "done", "answer": "No relevant wiki pages found for this query.", "action_taken": "queried"}
            return

        yield {"type": "status", "status": "retrieving"}

        page_contents = []
        sources = []
        related_pages = []
        for r in results:
            page = await self.store.get_page(r.slug)
            if page:
                try:
                    content = Path(page.file_path).read_text(encoding='utf-8')
                    content = re.sub(r'^---\s*\n[\s\S]*?\n---\s*\n', '', content)
                    content = content.strip()
                    if len(content) > 6000:
                        content = content[:6000] + "\n\n...[content truncated]"
                except Exception:
                    content = ""
                page_contents.append(f"### {r.title}\n\n{content}")
                sources.append(r.slug)
                related_pages.append({
                    "slug": page.slug,
                    "title": page.title,
                    "category": page.category.value if page.category else "concept",
                    "summary": page.summary or r.snippet or "暂无摘要",
                    "updated_at": page.updated_at.isoformat() if page.updated_at else None,
                    "word_count": page.word_count,
                })

        yield {"type": "sources", "sources": related_pages}

        yield {"type": "status", "status": "generating"}

        if self.settings.llm_api_key:
            try:
                from ...ingest.compiler.compiler import LLMClient
                llm = LLMClient(purpose="query")
                context = "\n\n---\n\n".join(page_contents)
                prompt = QUERY_PROMPT_TEMPLATE.format(question=question, context=context)

                full_answer = ""
                async for token in llm.generate_text_stream(
                    prompt=prompt,
                    system_prompt=QUERY_SYSTEM_PROMPT,
                    max_tokens=4000,
                ):
                    full_answer += token
                    yield {"type": "token", "token": token}

                formatted_answer, references = self._format_citations(full_answer, related_pages)
                yield {
                    "type": "done",
                    "answer": formatted_answer,
                    "action_taken": "queried",
                    "citations": references,
                    "related_pages": related_pages,
                }

            except Exception:
                logger.exception("LLM query stream failed")
                answer = _build_fallback_answer(question, results)
                formatted_answer, references = self._format_citations(answer, related_pages)
                yield {
                    "type": "done",
                    "answer": formatted_answer,
                    "action_taken": "queried",
                    "citations": references,
                    "related_pages": related_pages,
                }
        else:
            answer = _build_fallback_answer(question, results)
            formatted_answer, references = self._format_citations(answer, related_pages)
            yield {
                "type": "done",
                "answer": formatted_answer,
                "action_taken": "queried",
                "citations": references,
                "related_pages": related_pages,
            }

    # ── Ingest Handler ─────────────────────────────────────────

    async def _handle_ingest(self, msg: AgentMessage) -> AgentResponse:
        """Handle INGEST intent: archive content to the knowledge base."""
        text = msg.text.strip()

        # Check if it's a URL
        from ...ingest.adapters.url_collector import URLCollector, get_default_collector
        if URLCollector.is_url(text):
            return await self._ingest_url(text)

        # Otherwise, treat as plain text note
        return await self._ingest_text(text)

    async def _ingest_url(self, url: str) -> AgentResponse:
        """Collect URL content and archive it."""
        from ...ingest.adapters.url_collector import get_default_collector

        result = await get_default_collector().collect(url)
        if not result.success:
            return AgentResponse(
                reply_text=f"❌ 抓取失败: {result.error}\n\n建议: 请复制文章正文直接发给我，或截图发送。",
                action_taken="ingested",
            )

        # Archive as markdown
        safe_name = re.sub(r'[^\w\u4e00-\u9fa5-]', '-', url)[:80]
        safe_name = re.sub(r'-{2,}', '-', safe_name).strip('-').lower()
        source_slug = f"url-{safe_name}"
        source_title = result.title or url

        archive_dir = ArchiveHelper.papers_dir(self.settings.raw_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{source_slug}.md"

        md_content = f"""---
title: '{source_title}'
source_url: '{url}'
collected_at: '{datetime.now().isoformat()}'
---

{result.content}
"""
        archive_path.write_text(md_content, encoding='utf-8')

        # Trigger async compile if enabled
        if self.settings.llm_api_key:
            await self._ingest_service.submit_compile(
                source_slug=source_slug,
                source_content=result.content,
                source_title=source_title,
                archive_path=archive_path,
                source_type="url",
            )
            reply = (
                f"🔗 链接归档成功\n"
                f"标题: {source_title}\n"
                f"编号: {source_slug}\n"
                f"✅ 文章已归档到知识库，正在后台编译为 Wiki 页面..."
            )
        else:
            reply = (
                f"🔗 链接归档成功\n"
                f"标题: {source_title}\n"
                f"编号: {source_slug}\n"
                f"✅ 文章已归档到知识库（未启用自动编译）"
            )

        return AgentResponse(reply_text=reply, action_taken="ingested")

    async def _ingest_text(self, text: str) -> AgentResponse:
        """Archive plain text as a note."""
        import time

        safe_title = text[:40].strip() or "Untitled Note"
        safe_name = re.sub(r'[^\w\u4e00-\u9fa5-]', '-', safe_title)[:60]
        safe_name = re.sub(r'-{2,}', '-', safe_name).strip('-').lower() or f"note-{int(time.time())}"
        source_slug = safe_name
        source_title = safe_title

        archive_dir = ArchiveHelper.notes_dir(self.settings.raw_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{source_slug}.md"

        md_content = f"""---
title: '{source_title}'
created_at: '{datetime.now().isoformat()}'
---

{text}
"""
        archive_path.write_text(md_content, encoding='utf-8')

        # Trigger async compile if enabled
        if self.settings.llm_api_key:
            await self._ingest_service.submit_compile(
                source_slug=source_slug,
                source_content=text,
                source_title=source_title,
                archive_path=archive_path,
                source_type="text",
            )
            reply = f"✅ 笔记已归档\n编号: {source_slug}\n正在后台编译为 Wiki 页面..."
        else:
            reply = f"✅ 笔记已归档\n编号: {source_slug}\n（未启用自动编译）"

        return AgentResponse(reply_text=reply, action_taken="ingested")
