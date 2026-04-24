# -*- coding: utf-8 -*-
"""SageMate WeChat Plugin - Communication Adapter.

Responsibilities:
  - Poll WeChat API for incoming messages
  - Download and decrypt media (images, voice, files)
  - Archive raw media to data/raw/
  - Construct standardized AgentMessage
  - Delegate ALL business logic to AgentPipeline
  - Render AgentResponse into WeChat-compatible text and send

Design Principle:
  This file knows NOTHING about:
    - Intent routing
    - OCR / voice transcription
    - Wiki queries
    - LLM chat logic
    - URL scraping
  It only knows the WeChat protocol.
"""

from __future__ import annotations

import asyncio
import logging
import json
import time
import os
from pathlib import Path

from .api import WechatApiClient
from .auth import WechatAuthenticator
from ...core.agent import AgentPipeline, AgentMessage
from ...core.config import settings
from ...ingest.adapters.file_validator import FileTypeValidator, FileValidationError
from ...ingest.adapters.archive_helper import ArchiveHelper

# Set default log level to DEBUG for this module so we see raw data
logging.getLogger("plugins.wechat").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# 系统指令前缀
COMMAND_PREFIX = "!"


class WechatChannel:
    """
    Pure communication adapter for WeChat.
    All intelligence lives in AgentPipeline (SageMate Core).
    """

    def __init__(self, agent_pipeline: AgentPipeline | None = None):
        self.client = WechatApiClient()
        self.auth = WechatAuthenticator(self.client)
        self.agent_pipeline = agent_pipeline

        # Lifecycle guard — prevent duplicate starts
        self._running = False

    async def start(self):
        """Start the channel polling loop.

        Idempotent: safe to call multiple times — returns immediately if already running.
        """
        if self._running:
            logger.debug("WeChat Channel already running, skipping start.")
            return
        self._running = True

        logger.info("🚀 Starting SageMate WeChat Channel...")

        # 1. Try saved token only — no QR prompt at startup
        logged_in = await self._ensure_login()
        if not logged_in:
            logger.info("ℹ️ WeChat not logged in. Login via Settings UI (⚙️ → 插件 → 微信插件).")
            return

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
                    if "token" in err_msg.lower() or "expired" in err_msg.lower() or "login" in err_msg.lower() or ret == -1:
                        logger.warning("🔐 Session expired/invalid. Attempting auto re-login...")
                        self.client.token = None
                        self.auth.invalidate_account()  # 删除本地失效 Token

                        # 进入重登流程
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
        """Restore a saved session/token only. Does NOT trigger QR login.

        Returns True if a valid saved token was restored, False otherwise.
        Full QR-based login must be initiated via the Settings UI.
        """
        try:
            account = self.auth.load_account()
            if account and account.token:
                logger.info(f"🔑 Restored saved token for user {account.user_id}")
                self.client.token = account.token
                self.client.base_url = account.base_url
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Token restore exception: {e}")
            return False

    # ── Message Handling ───────────────────────────────────────

    async def _handle_message(self, msg_data: dict):
        """Process a single raw message from WeChat.

        Steps:
          1. Download/decrypt media if needed
          2. Save raw media to data/raw/
          3. Construct AgentMessage
          4. Delegate to AgentPipeline
          5. Send reply back to user
        """
        logger.debug(f"📦 Raw Message Data: {json.dumps(msg_data, indent=2, ensure_ascii=False)}")

        from_user_id = msg_data.get("from_user_id")
        context_token = msg_data.get("context_token")
        if not isinstance(from_user_id, str) or not from_user_id:
            return

        if not self.agent_pipeline:
            logger.error("AgentPipeline not configured. Cannot process messages.")
            return

        item_list = msg_data.get("item_list", [])

        # 每条消息只处理第一个有效 item
        for item in item_list:
            item_type = item.get("type")

            if item_type == 1:  # Text
                text_content = item.get("text_item", {}).get("text", "")
                agent_msg = AgentMessage(
                    channel="wechat",
                    user_id=from_user_id,
                    content_type="text",
                    text=text_content,
                    raw_data={"context_token": context_token},
                )
                await self._dispatch_and_reply(agent_msg, from_user_id, context_token)
                return

            elif item_type == 2:  # Image
                await self.client.send_message(from_user_id, "👁️ 正在识别图片...", context_token=context_token)

                image_data = item.get("image_item", {}).get("media", {})
                encrypt_param = image_data.get("encrypt_query_param")
                aes_key = image_data.get("aes_key")

                if not encrypt_param:
                    await self.client.send_message(from_user_id, "[图片处理失败：缺少媒体参数]", context_token=context_token)
                    return

                image_bytes = await self.client.download_file(encrypt_param, aes_key)
                file_id = f"img_{int(time.time())}"
                image_path = self._save_media(image_bytes, "images", file_id, ".png")

                agent_msg = AgentMessage(
                    channel="wechat",
                    user_id=from_user_id,
                    content_type="image",
                    text="",
                    raw_data={
                        "file_path": str(image_path),
                        "context_token": context_token,
                    },
                )
                await self._dispatch_and_reply(agent_msg, from_user_id, context_token)
                return

            elif item_type == 3:  # Voice
                await self.client.send_message(from_user_id, "🎤 正在转写语音...", context_token=context_token)

                voice_data = item.get("voice_item", {})
                media = voice_data.get("media", {})
                aes_key = voice_data.get("aeskey") or media.get("aes_key")
                encrypt_param = media.get("encrypt_query_param")
                encode_type = voice_data.get("encode_type", 6)

                if not encrypt_param:
                    await self.client.send_message(from_user_id, "[语音处理失败：缺少媒体参数]", context_token=context_token)
                    return

                voice_bytes = await self.client.download_file(encrypt_param, aes_key)
                file_id = f"voice_{int(time.time())}"

                # Determine extension from encode_type
                type_map = {5: "amr", 6: "silk", 7: "mp3", 8: "ogg"}
                ext = type_map.get(encode_type, "silk")
                voice_path = self._save_media(voice_bytes, "voice", file_id, f".{ext}")

                agent_msg = AgentMessage(
                    channel="wechat",
                    user_id=from_user_id,
                    content_type="voice",
                    text="",
                    raw_data={
                        "file_path": str(voice_path),
                        "encode_type": encode_type,
                        "context_token": context_token,
                    },
                )
                await self._dispatch_and_reply(agent_msg, from_user_id, context_token)
                return

            elif item_type == 4:  # File
                await self._handle_file_message(item, msg_data, from_user_id, context_token)
                return

    async def _handle_file_message(self, item: dict, msg_data: dict, from_user_id: str, context_token: str):
        """Download and archive a file, then delegate to AgentPipeline."""
        import traceback

        file_item_data = item.get("file_item", {})
        file_name = file_item_data.get("file_name", "unknown_file")
        media = file_item_data.get("media", {})
        encrypt_query_param = media.get("encrypt_query_param")

        # Enhanced AES key extraction
        aes_key = (
            media.get("aes_key")
            or media.get("aeskey")
            or file_item_data.get("aes_key")
            or file_item_data.get("aeskey")
        )

        if not encrypt_query_param:
            await self.client.send_message(
                from_user_id,
                f"⚠️ 收到文件 [{file_name}]，但无法获取下载链接。",
                context_token=context_token
            )
            return

        logger.info(f"📥 Downloading file: {file_name}...")
        await self.client.send_message(
            from_user_id,
            f"✅ 已收到文件 [{file_name}]，正在处理...",
            context_token=context_token
        )

        try:
            file_bytes = await self.client.download_file(encrypt_query_param, aes_key=aes_key)

            # Validate file header
            detected = FileTypeValidator.detect(file_bytes)
            if not detected:
                raise FileValidationError(
                    f"文件头不是已知格式 (hex: {file_bytes[:8].hex()})"
                )
            logger.info(f"✅ 文件类型检测: {detected}")

            # Save raw file to canonical location
            file_id = f"file_{int(time.time())}"
            ext = Path(file_name).suffix or ".bin"
            file_path = self._save_media(
                file_bytes, ArchiveHelper.files_dir(settings.raw_dir).name, file_id, ext
            )

            # Delegate to Core
            agent_msg = AgentMessage(
                channel="wechat",
                user_id=from_user_id,
                content_type="file",
                text=file_name,
                raw_data={
                    "file_path": str(file_path),
                    "file_name": file_name,
                    "context_token": context_token,
                },
            )
            await self._dispatch_and_reply(agent_msg, from_user_id, context_token)

        except Exception as e:
            logger.error(f"File handling error:\n{traceback.format_exc()}")
            await self.client.send_message(
                from_user_id,
                f"❌ 处理文件 [{file_name}] 时出错: {str(e)}",
                context_token=context_token
            )

    async def _dispatch_and_reply(self, agent_msg: AgentMessage, user_id: str, context_token: str):
        """Send AgentMessage to AgentPipeline and deliver the response."""
        # 1. Commands (WeChat-specific, handled before Core)
        if agent_msg.content_type == "text" and agent_msg.text.startswith(COMMAND_PREFIX):
            reply_text = await self._handle_command(user_id, agent_msg.text)
            if reply_text:
                await self.client.send_message(user_id, reply_text, context_token=context_token)
                return

        # 2. Typing indicator (fire-and-forget)
        asyncio.create_task(self._show_typing(user_id, context_token))

        # 3. Delegate to Core AgentPipeline
        try:
            response = await self.agent_pipeline.process(agent_msg)
        except Exception as e:
            logger.error(f"AgentPipeline error: {e}")
            await self.client.send_message(
                user_id,
                f"SageMate: 处理消息时出错 ({str(e)})。",
                context_token=context_token
            )
            return

        # 4. Send reply (Core already formats the reply_text)
        reply_text = response.reply_text
        if not reply_text:
            return

        logger.info(f"📤 Sending Reply: {reply_text[:50]}...")
        await self.client.send_message(user_id, reply_text, context_token=context_token)

    # ── Helpers ────────────────────────────────────────────────

    def _save_media(self, data: bytes, subdir: str, file_id: str, ext: str) -> Path:
        """Save raw media bytes to data/raw/{subdir}/ and return the path."""
        media_dir = settings.raw_dir / subdir
        media_dir.mkdir(parents=True, exist_ok=True)
        path = media_dir / f"{file_id}{ext}"
        path.write_bytes(data)
        logger.info(f"📥 Saved raw media to: {path}")
        return path

    async def _show_typing(self, user_id: str, context_token: str):
        """Show typing indicator in background."""
        if not context_token:
            return

        try:
            config = await self.client.get_config(user_id, context_token)
            ticket = config.get("typing_ticket")
            if ticket:
                await self.client.send_typing(user_id, ticket, status=1)
        except Exception as e:
            logger.debug(f"Typing indicator failed: {e}")

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
            self.client.token = None
            self.auth.invalidate_account()

            success = await self._ensure_login()
            if success:
                return "✅ 重新登录成功！会话已清空，我满血复活了。"
            else:
                return "❌ 重新登录失败，请检查日志。"

        return None
