# -*- coding: utf-8 -*-
"""SageMate WeChat Agent - Powered by AgentScope."""

from __future__ import annotations

import logging
import os

# AgentScope 1.0+ 正确导入路径
try:
    from agentscope.model import OpenAIChatModel
    from agentscope.message import Msg, TextBlock, ThinkingBlock
    from agentscope.formatter import OpenAIChatFormatter
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import AgentScope components: {e}")
    OpenAIChatModel = None
    Msg = None
    OpenAIChatFormatter = None

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "你是 SageMate，一个运行在微信上的个人智能助手（第二大脑）。"
    "你的任务是帮助用户整理思绪、回答关于知识库的问题。"
    "语气亲切、专业、简洁（中文为主）。"
    "当用户询问知识库内容时，你会先搜索知识库再回答。"
)


class SageMateAgent:
    """
    SageMate 核心智能体。
    使用 AgentScope 1.0+ 的 OpenAIChatModel + OpenAIChatFormatter。
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SageMateAgent, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 1. 获取配置
        api_key = os.getenv("SAGEMATE_WECHAT_API_KEY") or os.getenv("SAGEMATE_VISION_API_KEY")
        if not api_key:
            api_key = os.getenv("SAGEMATE_LLM_API_KEY")

        model_name = os.getenv("SAGEMATE_WECHAT_MODEL", "GLM-5")
        base_url = os.getenv("SAGEMATE_WECHAT_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

        if not api_key:
            logger.warning("⚠️ LLM API Key not found. Agent disabled.")
            self.enabled = False
            self.model = None
            self.formatter = None
            self._initialized = True
            return

        if OpenAIChatModel is None:
            logger.error("❌ AgentScope not installed correctly.")
            self.enabled = False
            self.model = None
            self.formatter = None
            self._initialized = True
            return

        self.enabled = True
        logger.info(f"🧠 Initializing SageMate Agent with {model_name} via AgentScope 1.0+...")

        # 2. 实例化模型 + 格式化器
        try:
            self.model = OpenAIChatModel(
                model_name=model_name,
                api_key=api_key,
                stream=False,
                client_kwargs={"base_url": base_url},
            )
            self.formatter = OpenAIChatFormatter()
            self._initialized = True
            logger.info(f"✅ SageMate Agent initialized (Model: {model_name})")
        except Exception as e:
            logger.error(f"❌ AgentScope Model Init failed: {e}")
            self.enabled = False
            self.model = None
            self.formatter = None

    def _extract_text(self, content: list) -> str:
        """从 ChatResponse.content (block list) 中提取纯文本。"""
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                # 跳过 thinking/tool_use 等非回复内容
            elif hasattr(block, "type"):
                if getattr(block, "type", None) == "text":
                    text_parts.append(getattr(block, "text", ""))
        return "".join(text_parts)

    async def chat(self, user_text: str, history: list[dict] | None = None) -> str:
        """
        接收用户文本和历史记录，异步返回 Agent 的回复。

        :param user_text: 当前用户的输入
        :param history: 历史记录列表，格式为 [{"role": "user/assistant", "content": "..."}]
        """
        if not self.enabled or not self.model or not self.formatter or Msg is None:
            return "SageMate: 系统未连接 LLM 或未正确初始化。"

        try:
            # Step 1: 构造消息列表
            # System Prompt
            msgs = [Msg(name="system", content=SYSTEM_PROMPT, role="system")]
            
            # 追加历史记录 (User 和 Assistant 交替)
            if history:
                for item in history:
                    msgs.append(Msg(name=item["role"], content=item["content"], role=item["role"]))
            
            # 追加当前用户输入
            msgs.append(Msg(name="user", content=user_text, role="user"))

            # Step 2: 格式化
            formatted_msgs = await self.formatter.format(msgs)

            # Step 3: 调用模型
            response = await self.model(formatted_msgs)

            # Step 4: 提取文本
            content = getattr(response, "content", [])
            if isinstance(content, list):
                text = self._extract_text(content)
                if text:
                    return text
            if isinstance(content, str):
                return content

            return "SageMate: 未收到有效回复。"

        except Exception as e:
            logger.error(f"❌ AgentScope Chat Error: {e}")
            return f"SageMate: 大脑暂时短路了 ({str(e)})。"
