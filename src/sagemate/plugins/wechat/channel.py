# -*- coding: utf-8 -*-
"""SageMate WeChat Plugin - Main Channel Loop."""

from __future__ import annotations

import asyncio
import logging
import json
import time
import os

from .api import WechatApiClient
from .auth import WechatAuthenticator
from .router import IntentRouter, RouterResult, Intent
from .agent import SageMateAgent
from ...pipeline.url_collector import URLCollector
from ...pipeline.voice_parser import VoiceParser
from ...pipeline.vision_parser import VisionParser
from ...core.config import settings

# Set default log level to DEBUG for this module so we see raw data
logging.getLogger("plugins.wechat").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# 系统指令前缀
COMMAND_PREFIX = "!"

class WechatChannel:
    """
    The main bridge between WeChat and SageMate Core.
    It polls for messages, routes them, and sends replies.
    """

    def __init__(self):
        self.client = WechatApiClient()
        self.auth = WechatAuthenticator(self.client)
        
        # Intent Router
        self.router = IntentRouter()
        
        # SageMate Agent (The Brain)
        self.agent = SageMateAgent()

        # Session Store: { user_id: [ {role, content}, ... ] }
        self.sessions: dict[str, list] = {}

    async def start(self):
        """Start the channel loop."""
        logger.info("🚀 Starting SageMate WeChat Channel...")
        
        # 1. Login / Load Token
        await self._ensure_login()

        logger.info("👂 Listening for messages...")

        # 2. Start Polling
        self._get_updates_buf = ""
        
        while True:
            try:
                updates = await self.client.get_updates(self._get_updates_buf)
                
                # 1. 检查 API 业务级错误（如 Token 失效、会话过期）
                ret = updates.get("ret")
                if ret is not None and ret != 0:
                    err_msg = updates.get("errmsg", "Unknown error")
                    logger.error(f"❌ API Error: ret={ret} - {err_msg}")
                    
                    # 判定为会话失效，触发自动重连
                    # 通常 ret != 0 且包含 token/expired/login 等关键词
                    if "token" in err_msg.lower() or "expired" in err_msg.lower() or "login" in err_msg.lower() or ret == -1:
                        logger.warning("🔐 Session expired/invalid. Attempting auto re-login...")
                        self.client.token = None
                        self.auth.invalidate_account() # 删除本地失效 Token
                        self.sessions.clear()          # 清空内存会话
                        
                        # 进入重登流程（会阻塞直到扫码成功或获取新 Token）
                        await self._ensure_login()
                    
                    await asyncio.sleep(5)
                    continue

                if "msgs" in updates:
                    self._get_updates_buf = updates.get("get_updates_buf", updates.get("sync_buf", ""))
                    msgs = updates.get("msgs", [])
                    
                    for msg_data in msgs:
                        # 创建独立任务处理消息，避免阻塞主轮询循环
                        asyncio.create_task(self._handle_message(msg_data))
                        
            except Exception as e:
                logger.error(f"Polling loop error: {e}")
                await asyncio.sleep(5)

    async def _ensure_login(self):
        """Ensure we have a valid session/token."""
        try:
            account = await self.auth.login()
            if account:
                logger.info(f"✅ Logged in as {account.user_id}")
                return True
            else:
                logger.error("❌ Login failed.")
                return False
        except Exception as e:
            logger.error(f"❌ Login exception: {e}")
            return False

    async def _handle_file_message(self, msg_data: dict, context_token: str):
        """Handle incoming file messages (Type 4)."""
        import traceback
        item_list = msg_data.get("item_list", [])
        
        file_item_data = None
        for item in item_list:
            if item.get("type") == 4:
                file_item_data = item.get("file_item", {})
                break
        
        if not file_item_data:
            logger.error("Received file message type but no file_item data found.")
            return

        file_name = file_item_data.get("file_name", "unknown_file")
        media = file_item_data.get("media", {})
        encrypt_query_param = media.get("encrypt_query_param")
        
        # 🔑 增强密钥提取：尝试多个可能的路径
        aes_key = (media.get("aes_key") 
                   or media.get("aeskey") 
                   or file_item_data.get("aes_key")
                   or file_item_data.get("aeskey"))
        
        # 如果 media 里没有，尝试从 item 级别获取
        if not aes_key:
            for item in item_list:
                if item.get("type") == 4:
                    aes_key = item.get("aeskey") or item.get("aes_key")
                    break
        
        # Log the key details for debugging
        if aes_key:
            logger.warning(f"🔑 AES key found: len={len(aes_key)}, first 20 chars: {aes_key[:20]}")
        else:
            logger.warning("⚠️ 未找到 AES 密钥")
            if encrypt_query_param:
                 logger.error("❌ 无法解密：文件有下载链接但缺少密钥。")

        if not encrypt_query_param:
            logger.error(f"File {file_name} missing encrypt_query_param.")
            await self.client.send_message(
                msg_data.get("from_user_id"), 
                f"⚠️ 收到文件 [{file_name}]，但无法获取下载链接。",
                context_token=context_token
            )
            return

        logger.info(f"📥 Downloading file: {file_name}...")
        await self.client.send_message(
            msg_data.get("from_user_id"),
            f"✅ 已收到文件 [{file_name}]，正在下载并归档...",
            context_token=context_token
        )

        try:
            # 1. 下载并解密
            file_bytes = await self.client.download_file(encrypt_query_param, aes_key=aes_key)
            
            # 2. 检查文件头
            known_headers = {
                b'%PDF': 'PDF',
                b'PK\x03\x04': 'ZIP/DOCX/PPTX/XLSX',
                b'\xd0\xcf\x11\xe0': 'DOC (OLE)',
                b'\x89PNG': 'PNG',
                b'\xff\xd8\xff': 'JPEG',
            }
            detected_type = None
            for header, name in known_headers.items():
                if file_bytes[:len(header)] == header:
                    detected_type = name
                    break
            
            if not detected_type:
                print(f"❌ [HEADER CHECK] File header: {file_bytes[:8].hex()}")
                print(f"❌ [HEADER CHECK] Raw bytes: {file_bytes[:40]}")
                # 检查是否是因为缺少 pycryptodome
                try:
                    import Crypto
                except ImportError:
                    logger.error("❌ 致命错误: 未安装 pycryptodome！无法解密微信文件。")
                    raise RuntimeError("请运行: pip install pycryptodome")
                raise ValueError(f"文件解密失败，文件头不是已知格式 (hex: {file_bytes[:8].hex()})")
            else:
                logger.info(f"✅ 文件类型检测: {detected_type}")
            
            # 3. 归档
            import httpx
            ingest_url = "http://127.0.0.1:8001/ingest"
            files = {"file": (file_name, file_bytes, "application/octet-stream")}
            
            async with httpx.AsyncClient(trust_env=False, timeout=300.0) as client:
                resp = await client.post(ingest_url, files=files)
                
                # 增加详细错误日志
                if resp.status_code != 200:
                    logger.error(f"❌ Ingest API Error: {resp.status_code} - {resp.text[:200]}")
                    raise ValueError(f"SageMate Core 返回错误状态: {resp.status_code}")
                
                try:
                    result = resp.json()
                except Exception as json_err:
                    logger.error(f"❌ Ingest JSON 解析失败: {json_err}")
                    logger.error(f"Response Body: {resp.text[:500]}")
                    raise

                if result.get("success"):
                    slug = result.get("source_slug", "unknown")
                    wiki_created = result.get("wiki_pages_created", 0)
                    reply = f"🎉 归档成功！\n📄 来源: {file_name}\n🆔 编号: {slug}\n📚 新增页面: {wiki_created}"
                else:
                    reply = f"❌ 归档失败: {result.get('error', 'Unknown error')}"

        except Exception as e:
            # 打印完整堆栈以便调试
            logger.error(f"File ingest error:\n{traceback.format_exc()}")
            reply = f"❌ 处理文件 [{file_name}] 时出错: {str(e)}"

        await self.client.send_message(
            msg_data.get("from_user_id"),
            reply,
            context_token=context_token
        )

    async def _handle_url_ingestion(self, url: str, user_id: str, context_token: str, history: list) -> str:
        """Handle URL ingestion: Scrape -> Ingest -> Reply."""
        import httpx
        
        # 1. Notify user
        await self.client.send_message(
            user_id,
            f"🕸️ 正在抓取链接内容: {url[:40]}...",
            context_token=context_token
        )

        # 2. Scrape
        result = await URLCollector.collect(url)
        
        if not result.success:
            return f"❌ 抓取失败: {result.error}\n\n建议: 请复制文章正文直接发给我，或截图发送。"

        # 3. Ingest
        await self.client.send_message(
            user_id,
            f"📥 抓取成功: {result.title}\n正在归档...",
            context_token=context_token
        )

        try:
            # Send Markdown content to the ingest API
            # We create a "virtual file" in memory
            ingest_url = "http://127.0.0.1:8001/ingest"
            
            # Generate a slug-friendly filename from title
            import re
            safe_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '_', result.title or "url_content")
            filename = f"{safe_title}.md"
            
            # The content includes a YAML frontmatter for better parsing
            markdown_payload = f"""---
title: '{result.title}'
source_url: '{result.url}'
collected_at: '2026-04-19'
---

{result.content}
"""
            
            files = {
                "file": (filename, markdown_payload, "text/markdown")
            }

            async with httpx.AsyncClient(trust_env=False, timeout=300.0) as client:
                resp = await client.post(ingest_url, files=files)
                
                if resp.status_code == 200:
                    res_json = resp.json()
                    if res_json.get("success"):
                        slug = res_json.get("source_slug", "unknown")
                        return f"🎉 归档成功！\n🔗 来源: {result.title}\n🆔 编号: {slug}"
                    else:
                        return f"❌ 归档失败: {res_json.get('error', 'Unknown')}"
                else:
                    return f"❌ Ingest API 错误: {resp.status_code}"
        except Exception as e:
            logger.error(f"URL Ingest error: {e}")
            return f"❌ 归档出错: {str(e)}"

    async def _show_typing(self, user_id: str, context_token: str):
        """Show typing indicator in background."""
        if not context_token:
            return

        try:
            # 1. Get config to retrieve typing_ticket
            config = await self.client.get_config(user_id, context_token)
            ticket = config.get("typing_ticket")
            if ticket:
                # 2. Send typing status (1 = typing)
                await self.client.send_typing(user_id, ticket, status=1)
        except Exception as e:
            logger.debug(f"Typing indicator failed: {e}")

    async def _query_wiki(self, question: str) -> str | None:
        """
        Query the knowledge base and return formatted context.
        Token-optimized: uses summaries instead of full content.
        """
        import httpx
        import re
        
        # Extract keywords
        search_terms = list(set(re.findall(r'\b\w{2,}\b', question)))
        chinese_terms = re.findall(r'[\u4e00-\u9fa5]{2,}', question)
        search_terms.extend(chinese_terms)
        
        if not search_terms:
            return None
        
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=10.0) as client:
                # Try FTS5 search first (works well for English)
                search_query = " OR ".join(search_terms)
                resp = await client.get(
                    f"http://127.0.0.1:8001/search",
                    params={"q": search_query}
                )
                results = resp.json() if resp.status_code == 200 else []
                
                # If no results and we have Chinese terms, try listing all pages with summaries
                if not results and chinese_terms:
                    resp = await client.get(f"http://127.0.0.1:8001/pages")
                    if resp.status_code == 200:
                        all_pages = resp.json()
                        if all_pages:
                            pages = []
                            for p in all_pages[:5]:
                                slug = p.get("slug", "")
                                title = p.get("title", "")
                                cat = p.get("category", "")
                                summary = p.get("summary", "")
                                if summary:
                                    pages.append(f"## {title} ({cat})\n{summary}")
                                else:
                                    pages.append(f"## {title} ({cat})")
                            return f"知识库当前有 {len(all_pages)} 个页面:\n\n" + "\n\n".join(pages)
                
                if not results:
                    return None
                
                # Fetch pages using summary + small content excerpt (token-optimized)
                pages = []
                for r in results[:3]:
                    slug = r.get("slug", "")
                    title = r.get("title", "")
                    try:
                        page_resp = await client.get(f"http://127.0.0.1:8001/pages/{slug}")
                        if page_resp.status_code == 200:
                            page_data = page_resp.json()
                            summary = page_data.get("summary", "")
                            if summary:
                                # Summary is enough for context (~150 chars)
                                pages.append(f"## {title}\n{summary}")
                            else:
                                # Fallback: first 200 chars of content (was 800)
                                content = page_data.get("content", "")
                                pages.append(f"## {title}\n{content[:200]}")
                    except Exception:
                        pages.append(f"## {title}\n{r.get('snippet', '')}")
                
                return "\n\n".join(pages) if pages else None
        except Exception as e:
            logger.error(f"Wiki query failed: {e}")
            return None

    async def _handle_command(self, user_id: str, text: str) -> str | None:
        """
        Handle system commands (prefixed with '!').
        Returns reply text if handled, else None.
        """
        if not text.startswith(COMMAND_PREFIX):
            return None

        parts = text.split()
        cmd = parts[0].lower()

        if cmd == "!login" or cmd == "!relogin":
            logger.info(f"⚡ User {user_id} requested re-login...")
            self.sessions.clear()
            self.client.token = None
            self.auth.invalidate_account() # 强制删除本地 Token，确保触发二维码重扫
            
            success = await self._ensure_login()
            if success:
                return "✅ 重新登录成功！会话已清空，我满血复活了。"
            else:
                return "❌ 重新登录失败，请检查日志。"
        
        return None

    async def _handle_message(self, msg_data: dict):
        """Process a single raw message from WeChat."""
        logger.debug(f"📦 Raw Message Data: {json.dumps(msg_data, indent=2, ensure_ascii=False)}")

        from_user_id = msg_data.get("from_user_id")
        context_token = msg_data.get("context_token")
        if not isinstance(from_user_id, str) or not from_user_id:
            return

        item_list = msg_data.get("item_list", [])
        text_content = ""
        
        # 预初始化 Parsers (如果需要)
        vision_parser = None
        if self.agent and self.agent.enabled:
            # 复用 Agent 的配置来初始化 Vision Parser
            # 假设 Agent 的 model/base_url 可以用于 Vision，或者有独立的配置
            # 为了简单，我们这里直接尝试用 Agent 的模型，或者默认用 glm-4v-plus
            # 注意：如果 Agent 用的是纯文本模型，这里需要分开配置。
            # 暂时假设环境变量或默认配置可用
            vision_api_key = os.getenv("SAGEMATE_VISION_API_KEY") or os.getenv("SAGEMATE_LLM_API_KEY")
            vision_base_url = os.getenv("SAGEMATE_VISION_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
            if vision_api_key:
                vision_parser = VisionParser(api_key=vision_api_key, base_url=vision_base_url)

        for item in item_list:
            item_type = item.get("type")
            if item_type == 1:  # Text
                text_content = item.get("text_item", {}).get("text", "")
            
            elif item_type == 2:  # Image
                if vision_parser:
                    image_data = item.get("image_item", {}).get("media", {})
                    encrypt_param = image_data.get("encrypt_query_param")
                    aes_key = image_data.get("aes_key")
                    
                    if encrypt_param:
                        await self.client.send_message(from_user_id, "👁️ 正在识别图片...", context_token=context_token)
                        image_bytes = await self.client.download_file(encrypt_param, aes_key)
                        text_content = await vision_parser.parse_image(image_bytes, f"img_{int(time.time())}", settings.raw_dir)
                    else:
                        text_content = "[图片处理失败：缺少媒体参数]"
                else:
                    text_content = "[Vision 模型未配置，无法识别图片]"
                
            elif item_type == 3:  # Voice
                voice_data = item.get("voice_item", {})
                media = voice_data.get("media", {})
                encrypt_param = media.get("encrypt_query_param")
                aes_key = media.get("aes_key")
                
                if encrypt_param:
                    await self.client.send_message(from_user_id, "🎤 正在转写语音...", context_token=context_token)
                    voice_bytes = await self.client.download_file(encrypt_param, aes_key)
                    text_content = await VoiceParser.parse_voice(voice_bytes, f"voice_{int(time.time())}", settings.raw_dir)
                else:
                    text_content = "[语音处理失败：缺少媒体参数]"
                    
            elif item_type == 4:  # File
                # Handle File separately
                await self._handle_file_message(msg_data, context_token)
                return

        if not text_content:
            return

        # 1. Check Commands
        reply_text = await self._handle_command(from_user_id, text_content)
        if reply_text:
            await self.client.send_message(from_user_id, reply_text, context_token=context_token)
            return

        # 2. Intent Routing (if not a command)
        # Trigger typing indicator in background (fire-and-forget)
        if text_content and from_user_id:
            asyncio.create_task(self._show_typing(from_user_id, context_token))

        result: RouterResult = await self.router.route(text_content)
        
        # 3. Session Management
        # Get or create history
        history = self.sessions.get(from_user_id, [])
        
        # 4. Dispatch Actions & Generate Reply
        reply_text = ""
        
        if result.intent == Intent.IGNORE:
            return
            
        if result.intent == Intent.QUERY:
            # Query the knowledge base before answering
            wiki_context = await self._query_wiki(result.content)
            if wiki_context:
                # Prepend wiki context to the user query
                augmented_text = f"问题: {result.content}\n\n以下是知识库中的相关内容:\n{wiki_context}\n\n请基于以上内容回答。"
                reply_text = await self.agent.chat(augmented_text, history=history)
            else:
                # Wiki is empty or no match: tell agent to use general knowledge
                reply_text = await self.agent.chat(
                    f"问题: {result.content}\n\n知识库中暂无相关内容，请基于你的通用知识直接回答。回答后请说明此答案来自通用知识而非知识库。",
                    history=history
                )
        elif result.intent == Intent.INGEST:
            # Check if this is a URL ingestion
            if URLCollector.is_url(result.content):
                reply_text = await self._handle_url_ingestion(result.content, from_user_id, context_token, history)
            else:
                # For text ingestion, acknowledge and let the agent respond
                # Or ideally, save this text to the wiki (TODO for future)
                reply_text = await self.agent.chat(result.content, history=history)
        else:
            # CHAT or default
            reply_text = await self.agent.chat(result.content, history=history)

        # 5. Update Session History
        if reply_text:
            # Append User Message
            history.append({"role": "user", "content": result.content})
            # Append Assistant Message
            history.append({"role": "assistant", "content": reply_text})
            
            # Token-based truncation: keep within ~2000 tokens for history
            # Chinese ~1.5 chars/token, English ~4 chars/token → use 3 chars/token as safe estimate
            MAX_HISTORY_TOKENS = 2000
            CHARS_PER_TOKEN = 3
            max_chars = MAX_HISTORY_TOKENS * CHARS_PER_TOKEN
            
            # Remove oldest messages until under budget
            while history and sum(len(m.get("content", "")) for m in history) > max_chars:
                history.pop(0)
            
            # Always keep at least the last 2 messages (current turn)
            if len(history) < 2:
                pass  # keep as-is
            
            self.sessions[from_user_id] = history

            # 6. Send Reply
            logger.info(f"📤 Sending Reply: {reply_text[:50]}...")
            await self.client.send_message(from_user_id, reply_text, context_token=context_token)
