# Ingest 摄入流程梳理与优化方案

> 针对 `/web/ingest` 接口的文档摄入功能，梳理当前任务流程、识别阻塞点，并提出分阶段迭代优化方案。  
> **现阶段只出方案，不改代码。**

---

## 一、当前任务流程全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  前端 (ingest.html)                                                          │
│  ├── 文本编辑  → POST /ingest (form: text, title, auto_compile)             │
│  ├── 文件上传  → POST /ingest (form: file, auto_compile)                    │
│  └── 粘贴 URL  → POST /ingest (form: url, auto_compile)                     │
│                    ↓ 立即返回 {task_id}                                       │
│                    ↓ SSE /ingest/progress/{task_id} 实时进度                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  API 层: POST /ingest  (app.py:1312)                                        │
│  1. task_id = ingest_tasks.create_task()  → 状态 QUEUED                     │
│  2. 按输入类型分支处理:                                                       │
│     ├─ 文件: 读文件 → 写临时文件 → DeterministicParser.parse()              │
│     │              → 复制到 data/raw/papers/originals/                       │
│     ├─ URL:  URLCollector.collect() (Tier1.5 → fallback Tier2)              │
│     │              → 写入 data/raw/papers/originals/{slug}.md               │
│     └─ 文本: 直接生成 markdown → 写入 data/raw/notes/{slug}.md              │
│  3. 若 auto_compile=true 且 llm_api_key 存在:                               │
│     asyncio.create_task(ingest_tasks.run_compile(...))  ← 后台任务          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  编译阶段: IngestTaskManager.run_compile() (app.py:226)                     │
│  ⚠️ 全程持有全局锁: async with self._compiler_lock:                          │
│                                                                             │
│  Step 1: reading_context                                                    │
│    └─ store.build_index_entries() → SELECT * FROM pages (全表扫描)          │
│       → 遍历所有页面，JSON parse inbound_links → 构建 index_context         │
│                                                                             │
│  Step 2: calling_llm                                                        │
│    └─ compiler.compile() → llm.generate_structured()                        │
│       → 一次大模型调用，prompt = system_prompt + source_content + index_ctx │
│       → timeout=300s, max_tokens=8000                                       │
│       → 返回 JSON: {source_archive, new_pages[], contradictions[]}          │
│                                                                             │
│  Step 3: writing_pages                                                      │
│    └─ _write_pages() → 写 Source Archive .md                                │
│       → 逐页写 Knowledge Page .md (循环内每次 store.upsert_page())          │
│                                                                             │
│  Step 4: updating_index                                                     │
│    └─ _update_index() → 再次 SELECT * FROM pages → 全量重建 index.md        │
│                                                                             │
│  Step 5: append_log                                                         │
│    └─ 追加写入 log.md                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 前端感知的 7 个步骤

| 步骤 | key | 对应后端实际阶段 | 典型耗时 |
|------|-----|------------------|----------|
| 1 | queued | 任务创建 | 瞬时 |
| 2 | parsing | 文件解析/URL采集 | 1s ~ 15s |
| 3 | reading_context | build_index_entries | 100ms ~ 2s |
| 4 | calling_llm | LLM generate_structured | **10s ~ 180s** |
| 5 | writing_pages | _write_pages | 100ms ~ 1s |
| 6 | updating_index | _update_index | 100ms ~ 1s |
| 7 | completed | set_result | 瞬时 |

---

## 二、阻塞点详细分析

### 🔴 P0 — 全局编译锁 `_compiler_lock`（最严重）

**现状:**
- `IngestTaskManager` 维护一个 `asyncio.Lock()`，所有 `run_compile()` 必须串行执行
- 即使用户连续上传 3 个文件，第 2、3 个任务会在锁外等待，前端一直显示 "LLM 分析中" 或 "等待调度"

**影响:**
- 多文件摄入体验极差，任务排队时间线性叠加
- 如果某个 LLM 调用卡住 5 分钟（timeout 设置），后续所有任务都被阻塞

**根因:**
- 锁的设计意图是防止并发写 wiki 目录冲突，但实现过度保守
- 不同 source_slug 之间理论上无冲突，完全可以并行

---

### 🔴 P0 — LLM 单调用瓶颈

**现状:**
- 整个编译过程只发生 **1 次** LLM API 调用（`generate_structured`）
- Prompt 包含：system_prompt + 完整 source_content（截断至 12k 字符）+ wiki_index_context
- 输出 max_tokens=8000，需要一次性生成 source_archive + 所有 knowledge pages

**影响:**
- 长文档时 prompt 很长，LLM 处理时间显著增加
- 8000 token 输出限制可能不足以生成大量知识页，导致内容截断
- 每次调用都 **新建 AsyncOpenAI client**，有 TCP/TLS 连接开销

**根因:**
- 架构上是 "单步编译"，没有分 chunk 或流式生成
- `compiler_max_wiki_context_chars = 8000` 配置项在代码中**从未被使用**，index context 无截断

---

### 🟡 P1 — 上下文读取低效

**现状:**
```python
# store.build_index_entries()
await db.execute("SELECT * FROM pages ORDER BY updated_at DESC")
```
- 每次编译都 **全表扫描**，读取 pages 表所有字段（包括 content）
- 对每个页面 JSON parse `inbound_links`，但 index context 里根本不用这个信息
- `_format_index_context` 简单拼接所有页面，随着 wiki 增长线性膨胀

**影响:**
- wiki 页面越多，reading_context 步骤越慢
- prompt 中无用的 index context 浪费 LLM token 和处理时间

---

### 🟡 P1 — 写页面与索引全量重建

**现状:**
- `_write_pages()` 中逐页写入磁盘，**逐页调用** `store.upsert_page()`（每次独立 SQL）
- `_update_index()` 每次编译都 **全量重建** `index.md`
- `_append_log()` 每次读取整个 `log.md` 再写回

**影响:**
- 生成 20 个页面就要执行 20+ 次 INSERT/UPDATE + FTS5 索引更新
- index.md 和 log.md 的 I/O 随着 wiki 增长而变慢

---

### 🟡 P1 — PDF 解析阻塞 Event Loop

**现状:**
```python
# parser.py:85
result = subprocess.run(['pdftotext', '-layout', str(file_path), '-'],
                        capture_output=True, text=True, timeout=60)
```
- 在 async 函数里直接调用 **同步** `subprocess.run`
- 大 PDF（几十 MB、几百页）可能阻塞 event loop 数秒

---

### 🟢 P2 — URL 采集 Tier 2 启动开销

**现状:**
- `URLCollector` 的 `BrowserPool` 首次初始化 Playwright 需要 2~3 秒
- Tier 1.5 (curl_cffi) 失败后 fallback 到 Tier 2，用户感知为明显停顿
- 虽然有 cache，但首次采集新 URL 仍可能触发冷启动

---

### 🟢 P2 — 任务状态内存存储

**现状:**
- `IngestTaskManager._tasks` 是纯内存 dict，进程重启即丢失
- 没有持久化队列，无法做任务恢复、重试、并发控制

**影响:**
- 服务端重启后，正在进行的任务前端无法追踪
- 无法支持限流（当前用全局锁变相限流到 1）

---

## 三、迭代优化方案

### Phase 1: 移除全局锁 + 细粒度并发控制（最大收益，优先做）

**目标:** 让多个文档的编译可以并行执行，消除排队阻塞。

**方案:**
1. **将 `_compiler_lock` 改为按 `source_slug` 的细粒度锁**
   - 使用 `dict[str, asyncio.Lock]`，只有相同 slug 的任务才串行
   - 不同文件天然不同 slug，实现真正并行

2. **如果担心并发写同一目录的冲突，可将写阶段也纳入 slug 锁保护**
   - 读取上下文（build_index_entries）→ 无锁，只读
   - LLM 调用 → 无锁，纯网络 I/O
   - 写 pages + 更新索引 → 持有 slug 锁

3. **增加并发上限控制**
   - 用 `asyncio.Semaphore(N)` 限制同时进行的 LLM 调用数（建议 N=3~5）
   - 避免瞬间打爆 LLM API 配额

**预期收益:**
- 3 个文件同时上传时，总耗时从 `T1+T2+T3` 降到 `max(T1,T2,T3)`
- 消除单点阻塞故障（一个任务卡住不影响其他任务）

---

### Phase 2: LLM 调用优化

**目标:** 减少单次 LLM 调用的延迟和连接开销。

**方案:**
1. **复用 AsyncOpenAI client**
   - `LLMClient` 初始化时创建 client，不要每次 `generate_*` 都新建
   - 减少 TCP/TLS 握手开销

2. **启用流式响应感知（可选）**
   - 如果 LLM 支持，可用 `stream=True` 让前端更早看到 "calling_llm" 有动静
   - 但结构化 JSON 输出不易流式解析，可作为体验优化而非核心优化

3. **实现 index_context 截断**
   - 实际使用 `compiler_max_wiki_context_chars` 配置
   - 只取最近/最相关的 N 个页面，或按 category 采样
   - 大幅减少 prompt token 数

4. **超长文档分 Chunk 并行编译**
   - 当 source_content > 12k（已达截断线）时，按语义 chunk 拆分
   - 每 chunk 独立调用 LLM 生成 wiki pages，最后合并去重
   - 需要引入"合并编译结果"的子流程

**预期收益:**
- 连接复用节省 200ms ~ 1s
- index context 截断可节省 20%~50% 的 prompt token，降低 LLM 处理时间
- 分 Chunk 编译可将超长文档的处理时间从 180s 降到 30~60s

---

### Phase 3: 数据库与 I/O 优化

**目标:** 减少不必要的全量操作和逐行写入。

**方案:**
1. **`build_index_entries` 轻量化**
   - SQL 改为 `SELECT slug, title, category, summary FROM pages`（不读 content）
   - 移除 inbound_links 的 JSON parse（index context 不需要）
   - 增加内存缓存：带 30s TTL 的 `lru_cache` 或 `async_lru`

2. **Batch Upsert Pages**
   - `_write_pages` 中将所有 pages 收集到一个 list
   - 一次性 `executemany` 插入，或至少用事务包裹 (`BEGIN ... COMMIT`)
   - FTS5 索引也随事务一起更新

3. **增量更新 index.md**
   - 不再每次全量重建，而是基于新增/更新的页面做增量 append
   - 或者将 index.md 重建改为**异步后台任务**（编译完成后触发，不阻塞前端）

4. **log.md 追加优化**
   - 使用 `a` 模式（append mode）打开文件，避免读取整个文件

**预期收益:**
- reading_context 从 O(n) 降到 O(1)（有缓存时）
- 写 20 个页面的 SQL 从 20 次独立事务降到 1 次
- index.md 重建不再阻塞 compile 完成时间

---

### Phase 4: 解析层非阻塞化

**目标:** 避免文件解析阻塞主 event loop。

**方案:**
1. **PDF 解析放入线程池**
   ```python
   loop = asyncio.get_event_loop()
   result = await loop.run_in_executor(None, subprocess.run, [...])
   ```

2. **DOCX / HTML 解析同理**
   - `python-docx` 和 `trafilatura` 都是 CPU/IO 密集型，建议用 `run_in_executor`

3. **URL 采集 BrowserPool 预热**
   - 应用启动时预初始化 `BrowserPool`（调用 `pool.initialize()`）
   - 避免第一个 URL 摄入时的 2~3 秒冷启动

**预期收益:**
- 大文件上传时 API 仍能响应其他请求
- URL 采集首次体验更流畅

---

### Phase 5: 任务队列持久化（中长期）

**目标:** 提升系统可靠性，支持任务恢复和更精细的调度。

**方案:**
1. **将任务状态存入 SQLite（而非内存 dict）**
   - 表结构：`ingest_tasks(task_id, status, source_slug, created_at, updated_at, error, result_json)`
   - SSE 订阅者从内存通知，但状态持久化到 DB

2. **引入真正的 Worker 模型**
   - 从 `asyncio.create_task` 改为从 DB 队列取任务执行
   - 支持并发数限制、优先级、失败重试（最多 3 次）
   - 支持进程重启后恢复未完成任务

3. **前台交互优化**
   - 页面刷新后，可根据 task_id 从 DB 恢复进度展示
   - 支持"正在排队的任务数"显示

**预期收益:**
- 服务重启不丢任务
- 可支持更复杂的调度策略（如夜间批量编译）

---

## 四、优化优先级总览

| 优先级 | 优化项 | 预估工作量 | 预期收益 |
|--------|--------|-----------|----------|
| **P0** | 移除全局编译锁，改为 slug 级细粒度锁 + Semaphore 并发控制 | 小 (1~2h) | **极高** — 多任务并行，消除排队 |
| **P0** | LLMClient 复用 AsyncOpenAI 连接 | 小 (30min) | 中 — 减少连接开销 |
| **P1** | `build_index_entries` 字段裁剪 + 内存缓存 | 小 (1h) | 中 — 加速 reading_context |
| **P1** | `_write_pages` batch upsert + 事务包裹 | 中 (2h) | 中 — 减少 DB I/O |
| **P1** | `_update_index` / `_append_log` 异步化或增量化 | 中 (2~3h) | 中 — 缩短 compile 结束时间 |
| **P1** | PDF/DOCX/HTML 解析放入线程池 | 小 (1h) | 中 — 避免 event loop 阻塞 |
| **P2** | 启用 `compiler_max_wiki_context_chars` 截断 | 小 (30min) | 中 — 减少 LLM token 消耗 |
| **P2** | URL BrowserPool 启动预热 | 小 (30min) | 低 — 首次体验优化 |
| **P3** | 任务队列持久化到 SQLite | 中 (4~6h) | 中 — 可靠性、可恢复 |
| **P3** | 超长文档分 Chunk 并行编译 | 大 (1~2d) | 高 — 突破单文档长度限制 |

---

## 五、关键代码位置索引

| 模块 | 文件路径 | 关键函数/类 |
|------|----------|-------------|
| API 入口 | `src/sagemate/api/app.py:1312` | `ingest_file()` |
| 任务管理 | `src/sagemate/api/app.py:90` | `IngestTaskManager` |
| 编译锁 | `src/sagemate/api/app.py:96` | `_compiler_lock` |
| 编译器 | `src/sagemate/pipeline/compiler.py:257` | `IncrementalCompiler.compile()` |
| LLM 客户端 | `src/sagemate/pipeline/compiler.py:31` | `LLMClient.generate_structured()` |
| 解析器 | `src/sagemate/pipeline/parser.py:17` | `DeterministicParser.parse()` |
| URL 采集 | `src/sagemate/pipeline/url_collector.py:654` | `URLCollector.collect()` |
| 数据存储 | `src/sagemate/core/store.py` | `Store.build_index_entries()`, `upsert_page()` |
| 配置项 | `src/sagemate/core/config.py:133` | `compiler_max_source_chars`, `compiler_max_wiki_context_chars` |

---

## 六、不改代码的验证建议

在正式改动前，可通过以下方式验证阻塞点：

1. **确认全局锁的影响**
   - 连续上传 3 个中等大小 PDF，观察 SSE 进度
   - 如果第 2、3 个任务的 "calling_llm" 在第一个完成后才开始，说明锁在排队

2. **测量各阶段耗时**
   - 在 `run_compile` 各步骤打 `time.monotonic()` 日志
   - 确认 LLM 调用占总时间的比例（通常 >80%）

3. **观察 index context 膨胀**
   - 打印 `len(index_context)` 和 `len(prompt)` 到日志
   - 确认随着 wiki 页面增加，prompt 是否线性增长

4. **确认 `_compiler_lock` 外的并行度**
   - 在 `run_compile` 进入锁前后分别打印日志
   - 观察是否有任务在锁外堆积等待
