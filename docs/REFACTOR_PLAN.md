# 渐进重构方案：设计模式驱动的 Ingest 架构升级

> 不改代码，只出方案。每一步都有明确的完成标准、验证方法和回滚策略。

---

## 一、现状诊断：3 个架构债

### 债 1：分层污染 — `core` 依赖 `api`

```
core/agent/pipeline.py
    │
    ▼ 反向导入（致命）
api/app.py 的 ingest_tasks 全局实例
```

`core/` 是最底层，绝不应该知道 `api/`（FastAPI 层）的存在。

### 债 2：`pipeline/` 是大杂烩

```
pipeline/
├── compiler.py          ← 核心编译
├── source_archive.py    ← 渲染策略
├── parser.py            ← 文件解析
├── url_collector.py     ← 网页采集
├── voice_parser.py      ← 语音转录
├── vision_parser.py     ← 图片 OCR
├── cron_scheduler.py    ← 定时任务 ← 不该在这里
├── lint.py              ← 健康检查 ← 不该在这里
└── cost_monitor.py      ← 成本监控 ← 不该在这里
```

9 个文件，4 种完全不同的职责混在一个包里。

### 债 3：全局锁 + 副作用 + 无接口

| 问题 | 位置 | 影响 |
|------|------|------|
| `_compiler_lock` 全局锁 | `IngestTaskManager` | 所有编译串行 |
| `DeterministicParser.parse()` 内部写文件 | `parser.py` | 副作用不可控，测试困难 |
| `ingest_tasks` 全局实例无接口 | `api/app.py` | 无法 mock、无法替换实现 |
| `compiler.compile()` 签名僵化 | `compiler.py` | 无法支持 chunk 化而不改所有调用方 |

---

## 二、设计模式选型

| 设计模式 | 解决什么问题 | 应用位置 |
|----------|-------------|---------|
| **依赖注入 (DI)** | 打破反向导入，解耦模块 | `AgentPipeline` ↔ `TaskManager` |
| **策略模式 (Strategy)** | 不同文档长度走不同编译策略 | `FastlaneStrategy` / `ChunkedStrategy` / `DeepCompileStrategy` |
| **模板方法 (Template Method)** | 编译流程骨架固定，步骤可替换 | `AbstractCompilerStrategy` |
| **工作单元 (Unit of Work)** | 文件写入原子化，支持回滚 | `WikiWriteUnit` |
| **门面模式 (Facade)** | 简化外部调用接口 | `IngestService` |
| **命令模式 (Command)** | 任务可持久化、可重试 | `CompileCommand` |
| **观察者 / 事件总线** | 进度通知解耦 | `EventBus` |
| **适配器模式 (Adapter)** | Parser 纯化，无副作用 | `FileParser` → `(slug, content)` |

---

## 三、目标架构蓝图

```
src/sagemate/
│
├── api/                          ← FastAPI 层（只负责 HTTP）
│   ├── app.py                    ←   路由定义
│   └── routers/
│       └── ingest.py             ←   /ingest, /ingest/progress/*
│
├── core/                         ← 基础设施层
│   ├── config.py
│   ├── store.py                  ←   存储抽象
│   ├── event_bus.py              ←   【新增】事件总线
│   └── agent/
│       ├── pipeline.py           ←   通过 DI 获取 IngestService，不再反向导入
│       └── ...
│
├── ingest/                       ← 【重构】摄入核心（高内聚）
│   ├── __init__.py
│   ├── service.py                ←   【新增】IngestService 门面
│   ├── compiler/
│   │   ├── __init__.py
│   │   ├── strategies.py         ←   【新增】策略模式：编译策略接口 + 实现
│   │   ├── compiler.py           ←   现有 IncrementalCompiler（改名为 LLMCompiler）
│   │   ├── llm_client.py         ←   【新增】从 compiler.py 拆出的 LLMClient
│   │   └── source_archive.py     ←   渲染策略
│   ├── adapters/                 ←   【新增】输入适配器（高内聚）
│   │   ├── __init__.py
│   │   ├── base.py               ←   【新增】Parser 抽象接口
│   │   ├── file_parser.py        ←   原 parser.py（纯化后）
│   │   ├── url_collector.py      ←   原 url_collector.py
│   │   ├── voice_parser.py       ←   原 voice_parser.py
│   │   └── vision_parser.py      ←   原 vision_parser.py
│   └── task_manager.py           ←   【重构】IngestTaskManager（解耦 + 持久化）
│
├── system/                       ← 【新增】系统维护（原 pipeline 的杂物）
│   ├── cron_scheduler.py         ←   原 pipeline/cron_scheduler.py
│   ├── lint.py                   ←   原 pipeline/lint.py
│   └── cost_monitor.py           ←   原 pipeline/cost_monitor.py
│
└── plugins/
    └── wechat/
        └── channel.py            ←   仍通过 HTTP 调用 /ingest，不受影响
```

---

## 四、渐进重构路线图（6 个 Phase，每步可独立交付）

### Phase 0：目录重组 + Import 修正（1~2 天）

**目标**：零业务逻辑变化，只解决 `pipeline/` 大杂烩问题。

**动作**：
1. 新建目录 `ingest/`、`ingest/adapters/`、`ingest/compiler/`、`system/`
2. 将文件移动到对应目录
3. 修正所有 `from ...pipeline.xxx` import 路径
4. 删除旧的 `pipeline/` 目录（或保留 `__init__.py` 做兼容性转发）

**设计模式**：无（纯工程整理）

**完成标准**：
- `pytest tests/` 全部通过
- `python -m sagemate.api.app` 能正常启动
- 没有 `ImportError`

**回滚策略**：`git revert`

---

### Phase 1：Parser 纯化（适配器模式）（1 天）

**目标**：消除 `DeterministicParser` 的副作用，使其成为纯函数。

**当前问题**：
```python
# parser.py
@staticmethod
async def parse_pdf(file_path, target_dir):
    ...
    target = target_dir / "papers" / f"{slug}.md"
    target.write_text(frontmatter, encoding='utf-8')  # ← 副作用！
    return slug, frontmatter
```

**重构后**：
```python
# ingest/adapters/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Protocol

class ParseResult:
    slug: str
    title: str
    content: str          # 纯 markdown 内容
    source_type: str
    metadata: dict        # 可选的附加信息

class FileParser(ABC):
    """无副作用的输入适配器接口。"""
    
    @abstractmethod
    async def parse(self, file_path: Path) -> ParseResult:
        """将原始文件解析为结构化的 markdown 内容。"""
        ...

# ingest/adapters/file_parser.py
class PDFParser(FileParser):
    async def parse(self, file_path: Path) -> ParseResult:
        # pdftotext 提取文本...
        return ParseResult(
            slug=slug,
            title=title,
            content=frontmatter + text_content,
            source_type="pdf",
            metadata={"pages": estimated_pages},
        )

class MarkdownParser(FileParser):
    ...

class DocxParser(FileParser):
    ...

class ParserRegistry:
    """工厂 + 注册表。"""
    _parsers: dict[str, type[FileParser]] = {}
    
    @classmethod
    def register(cls, ext: str, parser: type[FileParser]):
        cls._parsers[ext] = parser
    
    @classmethod
    def get_parser(cls, ext: str) -> FileParser:
        parser_cls = cls._parsers.get(ext)
        if not parser_cls:
            raise ValueError(f"No parser registered for: {ext}")
        return parser_cls()

# 注册
ParserRegistry.register(".pdf", PDFParser)
ParserRegistry.register(".md", MarkdownParser)
ParserRegistry.register(".docx", DocxParser)
```

**调用方变化**：
```python
# 重构前（副作用内嵌）
slug, content = await DeterministicParser.parse(tmp_path, settings.raw_dir)

# 重构后（纯函数 + 调用方控制写入）
parser = ParserRegistry.get_parser(ext)
result = await parser.parse(tmp_path)
# 调用方决定是否写入、写入到哪里
archive_path = settings.raw_dir / "papers" / "originals" / file.filename
archive_path.write_text(result.content, encoding='utf-8')
```

**完成标准**：
- `pytest` 通过
- `file_parser.py` 的单元测试可以 mock 文件系统（因为 parser 不再直接写文件）

---

### Phase 2：事件总线 + 进度通知解耦（1~2 天）

**目标**：将 SSE 进度推送从 `IngestTaskManager` 的内部队列机制，解耦为事件总线。

**当前问题**：
```python
class IngestTaskManager:
    def __init__(self):
        self._listeners: dict[str, list[asyncio.Queue]] = {}  # 紧耦合
    
    async def _notify(self, task_id, event):
        for q in self._listeners[task_id]:
            q.put_nowait(event)  # 直接操作队列
```

**重构后**：
```python
# core/event_bus.py
class EventBus:
    """内存中的异步事件总线。可替换为 Redis/RabbitMQ 实现分布式。"""
    
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        self._subscribers.setdefault(event_type, []).append(handler)
    
    async def publish(self, event_type: str, payload: dict):
        for handler in self._subscribers.get(event_type, []):
            try:
                await handler(payload)
            except Exception:
                logger.exception(f"Event handler failed for {event_type}")

# ingest/task_manager.py
class IngestTaskManager:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        # 不再需要 self._listeners
    
    async def update_progress(self, task_id, status, step, message):
        ...
        await self._event_bus.publish("ingest.progress", {
            "task_id": task_id,
            "status": status.value,
            "step": step,
            "message": message,
        })

# api/routers/ingest.py — SSE 端点
@router.get("/ingest/progress/{task_id}")
async def ingest_progress(task_id: str, event_bus: EventBus = Depends(get_event_bus)):
    queue = asyncio.Queue()
    
    async def handler(payload):
        if payload["task_id"] == task_id:
            await queue.put(payload)
    
    event_bus.subscribe("ingest.progress", handler)
    try:
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["status"] in ("completed", "failed"):
                break
    finally:
        event_bus.unsubscribe("ingest.progress", handler)
```

**完成标准**：
- SSE 进度推送仍然正常工作
- `IngestTaskManager` 不再直接操作 `asyncio.Queue`
- 可以 mock `EventBus` 做单元测试

---

### Phase 3：依赖注入 — 打破反向导入（1~2 天）

**目标**：消除 `core/agent/pipeline.py → api/app.py` 的反向依赖。

**当前问题**：
```python
# core/agent/pipeline.py
from ...api.app import ingest_tasks  # ← 分层污染！

async def _ingest_url(self, url):
    ...
    task_id = ingest_tasks.create_task()  # 直接操作全局实例
    asyncio.create_task(ingest_tasks.run_compile(...))
```

**重构后**：
```python
# ingest/service.py — 门面模式
class IngestService(ABC):
    """摄入服务的抽象接口。"""
    
    @abstractmethod
    async def submit_compile(self, source_slug, source_content, source_title,
                             archive_path, source_type) -> str:
        """提交编译任务，返回 task_id。"""
        ...
    
    @abstractmethod
    async def get_task(self, task_id: str) -> IngestTaskState | None:
        ...

class DefaultIngestService(IngestService):
    """默认实现，组装所有组件。"""
    
    def __init__(self, task_manager: IngestTaskManager, event_bus: EventBus):
        self._task_manager = task_manager
        self._event_bus = event_bus
    
    async def submit_compile(self, source_slug, source_content, source_title,
                             archive_path, source_type) -> str:
        task_id = self._task_manager.create_task()
        asyncio.create_task(
            self._task_manager.run_compile(...)
        )
        return task_id

# api/app.py — 组装根对象（Composition Root）
from ingest.service import DefaultIngestService
from ingest.task_manager import IngestTaskManager
from core.event_bus import EventBus

event_bus = EventBus()
ingest_tasks = IngestTaskManager(event_bus=event_bus)
ingest_service = DefaultIngestService(task_manager=ingest_tasks, event_bus=event_bus)

# 注入到依赖容器
def get_ingest_service() -> IngestService:
    return ingest_service

# core/agent/pipeline.py — 通过构造函数注入
class AgentPipeline:
    def __init__(self, store, settings, ingest_service: IngestService):
        self.store = store
        self.settings = settings
        self._ingest_service = ingest_service  # ← 不再反向导入
    
    async def _ingest_url(self, url):
        ...
        task_id = await self._ingest_service.submit_compile(...)
```

**完成标准**：
- `core/agent/pipeline.py` 中没有任何 `from ...api` 的 import
- `pytest` 通过
- WeChat 文字/URL 摄入仍然正常工作

---

### Phase 4：工作单元 — 原子文件写入（1~2 天）

**目标**：解决移除全局锁后的文件并发写问题。

**当前问题**：
```python
# compiler.py
async def _write_pages(self, result):
    file_path.write_text(content, encoding='utf-8')  # 非原子！
    await self.store.upsert_page(...)  # DB 操作

async def _update_index(self):
    index_path.write_text(index_md, encoding='utf-8')  # 非原子！

async def _append_log(self, ...):
    log_path.write_text(new_content, encoding='utf-8')  # 非原子！
```

**重构后**：
```python
# ingest/compiler/unit_of_work.py
import tempfile
import os
from pathlib import Path

class WikiWriteUnit:
    """
    工作单元：收集所有待写入操作，最后原子提交。
    如果中途失败，可以回滚（不写入任何文件）。
    """
    
    def __init__(self, wiki_dir: Path):
        self._wiki_dir = wiki_dir
        self._operations: list[tuple[Path, str]] = []  # (target_path, content)
        self._db_operations: list[Callable] = []
    
    def schedule_write(self, relative_path: Path, content: str):
        """计划写入一个文件（此时不真正写入）。"""
        self._operations.append((self._wiki_dir / relative_path, content))
    
    def schedule_db(self, operation: Callable):
        """计划一个数据库操作。"""
        self._db_operations.append(operation)
    
    async def commit(self):
        """原子提交：先写临时文件，再 rename，最后写 DB。"""
        temp_files = []
        try:
            # Phase 1: 写入临时文件
            for target_path, content in self._operations:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
                temp_path.write_text(content, encoding='utf-8')
                temp_files.append((temp_path, target_path))
            
            # Phase 2: 原子 rename
            for temp_path, target_path in temp_files:
                os.replace(temp_path, target_path)  # 原子替换
            
            # Phase 3: DB 操作
            for op in self._db_operations:
                await op()
                
        except Exception:
            # 回滚：删除临时文件
            for temp_path, _ in temp_files:
                if temp_path.exists():
                    temp_path.unlink()
            raise
```

**Compiler 中的使用**：
```python
async def _write_pages(self, result, source_content):
    uow = WikiWriteUnit(self.cfg.wiki_dir)
    
    # 1. Source Archive
    if result.source_archive:
        content = self.source_renderer.render(result.source_archive, source_content)
        uow.schedule_write(Path("sources") / f"{archive.slug}.md", content)
        uow.schedule_db(lambda: self.store.upsert_page(source_page, content, ...))
    
    # 2. Knowledge Pages
    for page in result.new_pages:
        uow.schedule_write(
            self.cfg.wiki_dir_for_category(page.category) / f"{page.slug}.md",
            full_content
        )
        uow.schedule_db(lambda p=page: self.store.upsert_page(...))
    
    # 3. 原子提交
    await uow.commit()
```

**完成标准**：
- 并发编译两个不同 source 时，文件不会损坏
- 编译中途崩溃时，不会留下半 written 的文件

---

### Phase 5：编译策略抽象（策略模式 + 模板方法）（2~3 天）

**目标**：支持单文档编译、Chunk 化编译、深度编译，且对调用方透明。

**抽象设计**：
```python
# ingest/compiler/strategies.py
from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable

ProgressCallback = Callable[[str, str], Awaitable[None]]

class CompileStrategy(ABC):
    """
    编译策略接口。
    模板方法模式：骨架固定（读取上下文 → 编译 → 写入 → 更新索引），
    具体实现由子类决定。
    """
    
    def __init__(self, store: Store, wiki_dir: Path, llm_client: LLMClient):
        self.store = store
        self.wiki_dir = wiki_dir
        self.llm = llm_client
    
    # ── 模板方法（骨架）─────────────────────────
    async def compile(self, source_slug: str, source_content: str,
                      source_title: str,
                      progress_callback: Optional[ProgressCallback] = None) -> CompileResult:
        
        # Step 1: 读取上下文（公共）
        await self._on_progress(progress_callback, "reading_context", "读取知识库索引...")
        index_context = await self._load_index_context()
        
        # Step 2: 执行编译（由子类实现）
        await self._on_progress(progress_callback, "calling_llm", "LLM 分析中...")
        result = await self._execute_compile(
            source_slug=source_slug,
            source_content=source_content,
            source_title=source_title,
            index_context=index_context,
            progress_callback=progress_callback,
        )
        
        # Step 3: 写入（公共）
        await self._on_progress(progress_callback, "writing_pages", f"写入 {len(result.new_pages)} 页...")
        await self._persist_result(result, source_content)
        
        # Step 4: 更新索引（公共）
        await self._on_progress(progress_callback, "updating_index", "更新索引...")
        await self._update_index()
        
        return result
    
    # ── 抽象方法（子类必须实现）──────────────────
    @abstractmethod
    async def _execute_compile(self, *, source_slug, source_content, source_title,
                                index_context, progress_callback) -> CompileResult:
        """核心编译逻辑，由具体策略实现。"""
        ...
    
    # ── 公共方法（可被复用）──────────────────────
    async def _load_index_context(self) -> str:
        entries = await self.store.build_index_entries()
        return self._format_index_context(entries)
    
    async def _persist_result(self, result: CompileResult, source_content: str):
        uow = WikiWriteUnit(self.wiki_dir)
        # ... 写入逻辑
        await uow.commit()
    
    async def _update_index(self):
        # ... 重建 index.md
        pass
    
    async def _on_progress(self, cb, step, message):
        if cb:
            await cb(step, message)


# ── 具体策略实现 ──────────────────────────────

class SinglePassStrategy(CompileStrategy):
    """当前默认策略：单调用直接编译。适合 < 5K 字文档。"""
    
    async def _execute_compile(self, *, source_slug, source_content, source_title,
                                index_context, progress_callback) -> CompileResult:
        source_text = source_content[:settings.compiler_max_source_chars]
        prompt = self._build_compile_prompt(...)
        result_data = await self.llm.generate_structured(prompt=prompt, ...)
        return self._parse_compile_result(result_data, source_slug)


class ChunkedStrategy(CompileStrategy):
    """分片并行编译。适合 5K ~ 50K 字文档。"""
    
    def __init__(self, *args, chunk_size: int = 8000, max_concurrent: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        self.chunk_size = chunk_size
        self.max_concurrent = max_concurrent
    
    async def _execute_compile(self, *, source_slug, source_content, source_title,
                                index_context, progress_callback) -> CompileResult:
        # 1. 分片
        chunks = self._split_into_chunks(source_content, self.chunk_size)
        
        # 2. 并发编译（Semaphore 控制）
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def compile_one(chunk_idx, chunk_text):
            async with semaphore:
                await self._on_progress(progress_callback, "calling_llm",
                                        f"编译第 {chunk_idx + 1}/{len(chunks)} 段...")
                prompt = self._build_chunk_prompt(chunk_text, chunk_idx, ...)
                data = await self.llm.generate_structured(prompt=prompt, ...)
                return self._parse_compile_result(data, source_slug)
        
        results = await asyncio.gather(*[
            compile_one(i, chunk) for i, chunk in enumerate(chunks)
        ])
        
        # 3. 合并去重
        return self._merge_results(results)
    
    def _split_into_chunks(self, content: str, chunk_size: int) -> list[str]:
        """按语义边界（章节标题、段落）切分，保留 overlap。"""
        ...
    
    def _merge_results(self, results: list[CompileResult]) -> CompileResult:
        """合并多个 chunk 的结果，按 slug 去重。"""
        ...


class DeepCompileStrategy(CompileStrategy):
    """深度编译：先大纲扫描，再精选章节编译。适合 > 50K 字文档。"""
    
    async def _execute_compile(self, *, source_slug, source_content, source_title,
                                index_context, progress_callback) -> CompileResult:
        # Step 1: 大纲扫描（轻量调用）
        outline = await self._scan_outline(source_content)
        
        # Step 2: 精选高重要性章节
        important_chapters = [c for c in outline.chapters if c.importance == "high"]
        
        # Step 3: 对精选章节走 ChunkedStrategy
        sub_strategy = ChunkedStrategy(self.store, self.wiki_dir, self.llm)
        
        merged = CompileResult()
        for chapter in important_chapters:
            chapter_result = await sub_strategy._execute_compile(
                source_slug=f"{source_slug}-ch{chapter.index}",
                source_content=chapter.content,
                source_title=f"{source_title} — {chapter.title}",
                index_context=index_context,
                progress_callback=progress_callback,
            )
            merged = self._merge_results([merged, chapter_result])
        
        # Step 4: 生成全局 Source Archive
        merged.source_archive = await self._generate_global_archive(outline, merged)
        return merged
    
    async def _scan_outline(self, content: str) -> DocumentOutline:
        """轻量 LLM 调用，只读前 2 万字 + 提取目录。"""
        ...
```

**策略选择器（工厂模式）**：
```python
class CompileStrategyFactory:
    @staticmethod
    def create(source_content: str) -> CompileStrategy:
        char_count = len(source_content)
        
        if char_count < 5000:
            return SinglePassStrategy(...)
        elif char_count < 50000:
            return ChunkedStrategy(..., chunk_size=8000, max_concurrent=3)
        else:
            return DeepCompileStrategy(...)
```

**调用方（完全透明）**：
```python
# IngestTaskManager.run_compile()
strategy = CompileStrategyFactory.create(source_content)
result = await strategy.compile(
    source_slug=source_slug,
    source_content=source_content,
    source_title=source_title,
    progress_callback=progress_callback,
)
```

无论文档多长，调用方的代码**完全一样**。

**完成标准**：
- 短文仍走 `SinglePassStrategy`，行为和现在一致
- 长文自动走 `ChunkedStrategy`，SSE 进度显示 "第 3/5 段..."
- `cron_scheduler.py` 和 `recompile` 端点无需修改（因为 `compile()` 签名不变）

---

### Phase 6：任务持久化（命令模式）（3~5 天，可选）

**目标**：任务状态从内存 dict 迁移到 SQLite，支持重启恢复。

**当前问题**：
```python
class IngestTaskManager:
    def __init__(self):
        self._tasks: dict[str, IngestTaskState] = {}  # 进程重启即丢失
```

**重构后**：
```python
# ingest/task_manager.py
class IngestTaskRepository(ABC):
    @abstractmethod
    async def save(self, state: IngestTaskState) -> None: ...
    @abstractmethod
    async def get(self, task_id: str) -> IngestTaskState | None: ...

class InMemoryTaskRepository(IngestTaskRepository):
    """当前实现，零依赖。"""
    def __init__(self):
        self._tasks: dict[str, IngestTaskState] = {}
    
    async def save(self, state: IngestTaskState):
        self._tasks[state.task_id] = state
    
    async def get(self, task_id: str):
        return self._tasks.get(task_id)

class SQLiteTaskRepository(IngestTaskRepository):
    """持久化实现。"""
    def __init__(self, db):
        self._db = db
    
    async def save(self, state: IngestTaskState):
        await self._db.execute("""
            INSERT INTO ingest_tasks (task_id, status, step, message, result_json, created_at, updated_at)
            VALUES (:task_id, :status, :step, :message, :result_json, :created_at, :updated_at)
            ON CONFLICT(task_id) DO UPDATE SET ...
        """, {...})
    
    async def get(self, task_id: str):
        row = await self._db.execute("SELECT * FROM ingest_tasks WHERE task_id = ?", (task_id,))
        ...

class IngestTaskManager:
    def __init__(self, repository: IngestTaskRepository, event_bus: EventBus):
        self._repo = repository
        self._event_bus = event_bus
    
    async def update_progress(self, task_id, status, step, message):
        task = await self._repo.get(task_id)
        task.status = status
        task.step = step
        task.message = message
        await self._repo.save(task)
        await self._event_bus.publish("ingest.progress", {...})
```

**完成标准**：
- 服务重启后，通过 `/ingest/result/{task_id}` 仍能查到未完成的任务
- 可以安全地从 `InMemoryTaskRepository` 切换到 `SQLiteTaskRepository`

---

## 五、重构影响矩阵

| 重构 Phase | 修改的文件 | 影响的外部模块 | 风险等级 |
|-----------|-----------|--------------|---------|
| Phase 0 目录重组 | 仅 import 路径 | 所有 import `pipeline.xxx` 的地方 | 🟢 低（纯机械修改） |
| Phase 1 Parser 纯化 | `parser.py` + 调用方 | `api/app.py`, `cron_scheduler.py` | 🟢 低（签名简化） |
| Phase 2 事件总线 | `task_manager.py` + SSE 端点 | `api/app.py` | 🟢 低（内部解耦） |
| Phase 3 依赖注入 | `agent/pipeline.py` + `api/app.py` | `agent/pipeline.py`（正向影响） | 🟡 中（打破旧导入） |
| Phase 4 工作单元 | `compiler.py` | `cron_scheduler.py`（无影响，签名不变） | 🟡 中（文件写入逻辑变） |
| Phase 5 策略模式 | `compiler/` 目录 | `cron_scheduler.py`（无影响，签名不变） | 🟡 中（核心逻辑重构） |
| Phase 6 任务持久化 | `task_manager.py` | 前端 SSE（无影响） | 🔴 高（涉及 DB schema） |

---

## 六、推荐实施顺序

```
Week 1: Phase 0（目录重组）+ Phase 1（Parser 纯化）
        → 建立干净的目录结构，parser 可测试

Week 2: Phase 2（事件总线）+ Phase 3（依赖注入）
        → 架构层面的解耦完成

Week 3: Phase 4（工作单元）
        → 为移除全局锁做准备

Week 4: Phase 5（策略模式）
        → 支持 Chunk 化编译和超长文档

Week 5~6: Phase 6（任务持久化）— 可选
        → 如果不需要重启恢复，可以跳过
```

**Phase 0~3 是