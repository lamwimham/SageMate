"""API Dependencies — 共享依赖注入

提供全局组件的依赖工厂，供路由模块使用。
遵循 FastAPI 依赖注入模式，避免全局变量直接访问。
"""

from typing import Annotated
from fastapi import Depends

from ..core.config import settings, url_collector_settings
from ..core.store import Store
from ..core.watcher import WatcherManager
from ..core.agent import AgentPipeline
from ..ingest.compiler.compiler import IncrementalCompiler, LLMClient
from ..system.lint import LintEngine
from ..core.event_bus import EventBus
from ..ingest.task_manager import IngestTaskManager
from ..plugins.wechat.channel import WechatChannel
from ..plugins.wechat.service import WeChatService

# ── Global Component Registry ────────────────────────────────
# 这些在 app.py 的 lifespan 中初始化，这里提供访问接口

_store: Store | None = None
_watcher: WatcherManager | None = None
_compiler: IncrementalCompiler | None = None
_lint_engine: LintEngine | None = None
_event_bus: EventBus | None = None
_ingest_tasks: IngestTaskManager | None = None
_agent_pipeline: AgentPipeline | None = None
_wechat_channel: WechatChannel | None = None
_wechat_service: WeChatService | None = None


def register_components(
    store: Store,
    watcher: WatcherManager,
    compiler: IncrementalCompiler,
    lint_engine: LintEngine,
    event_bus: EventBus,
    ingest_tasks: IngestTaskManager,
    agent_pipeline: AgentPipeline,
    wechat_channel: WechatChannel,
    wechat_service: WeChatService,
):
    """Register global components (called once during app startup)."""
    global _store, _watcher, _compiler, _lint_engine
    global _event_bus, _ingest_tasks, _agent_pipeline
    global _wechat_channel, _wechat_service
    _store = store
    _watcher = watcher
    _compiler = compiler
    _lint_engine = lint_engine
    _event_bus = event_bus
    _ingest_tasks = ingest_tasks
    _agent_pipeline = agent_pipeline
    _wechat_channel = wechat_channel
    _wechat_service = wechat_service


def get_store() -> Store:
    if _store is None:
        raise RuntimeError("Store not initialized")
    return _store


def get_watcher() -> WatcherManager:
    if _watcher is None:
        raise RuntimeError("Watcher not initialized")
    return _watcher


def get_compiler() -> IncrementalCompiler:
    if _compiler is None:
        raise RuntimeError("Compiler not initialized")
    return _compiler


def get_lint_engine() -> LintEngine:
    if _lint_engine is None:
        raise RuntimeError("LintEngine not initialized")
    return _lint_engine


def get_event_bus() -> EventBus:
    if _event_bus is None:
        raise RuntimeError("EventBus not initialized")
    return _event_bus


def get_ingest_tasks() -> IngestTaskManager:
    if _ingest_tasks is None:
        raise RuntimeError("IngestTaskManager not initialized")
    return _ingest_tasks


def get_agent_pipeline() -> AgentPipeline:
    if _agent_pipeline is None:
        raise RuntimeError("AgentPipeline not initialized")
    return _agent_pipeline


def get_wechat_channel() -> WechatChannel:
    if _wechat_channel is None:
        raise RuntimeError("WechatChannel not initialized")
    return _wechat_channel


def get_wechat_service() -> WeChatService:
    if _wechat_service is None:
        raise RuntimeError("WeChatService not initialized")
    return _wechat_service


# FastAPI Depends shortcuts
StoreDep = Annotated[Store, Depends(get_store)]
WatcherDep = Annotated[WatcherManager, Depends(get_watcher)]
CompilerDep = Annotated[IncrementalCompiler, Depends(get_compiler)]
LintEngineDep = Annotated[LintEngine, Depends(get_lint_engine)]
EventBusDep = Annotated[EventBus, Depends(get_event_bus)]
IngestTasksDep = Annotated[IngestTaskManager, Depends(get_ingest_tasks)]
AgentPipelineDep = Annotated[AgentPipeline, Depends(get_agent_pipeline)]
WechatChannelDep = Annotated[WechatChannel, Depends(get_wechat_channel)]
WechatServiceDep = Annotated[WeChatService, Depends(get_wechat_service)]
