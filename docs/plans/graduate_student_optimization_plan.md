# SageMate 研究生场景优化 — 技术实现规划

> **目标**：在现有架构基础上，以可维护的方式实现学术 PDF 意图识别、元数据提取、批量导入、学术引用输出四个能力。
> **原则**：不破坏现有设计模式，新增组件通过接口注入，保持向后兼容。

---

## 1. 当前架构梳理

### 1.1 摄取数据流

```
文件/URL/文本
  ↓
[API 层]     app.py: ingest_file() — 接收输入，归档到 raw/
  ↓
[适配层]     DeterministicParser.parse() — PDF→Markdown（纯规则，无 LLM）
  ↓
[服务层]     IngestTaskManager.run_compile() — 异步任务编排（EventBus 进度通知）
  ↓
[编译层]     IncrementalCompiler.compile()
              ↓
            CompileStrategyFactory.create() — 按文档长度选策略
              ↓
            ├─ SinglePassStrategy   (< 5K chars)
            ├─ ChunkedStrategy      (5K ~ 50K)
            └─ DeepCompileStrategy  (> 50K)
              ↓
            LLMClient.generate_structured()
              ↓
            CompileStrategy._write_pages()
              ↓
[存储层]     WikiWriteUnit — 原子写入（temp → os.replace → DB）
              ↓
            Store.upsert_page() — SQLite + FTS5
```

### 1.2 前端摄取数据流

```
Ingest.tsx — 单文件上传/拖拽（input[type=file]，无 multiple）
  ↓
ingest.ts — API 仓库（ingestFile 接受单个 File）
  ↓
/api/ingest — 单文件/URL/文本提交
  ↓
/api/ingest/progress/{task_id} — SSE 进度
  ↓
IngestProgressPanel — 单任务进度展示
```

### 1.3 现有设计模式

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **Strategy** | `CompileStrategy` / `SourceArchiveRenderer` | 不同文档长度用不同编译策略；不同渲染方式 |
| **Factory** | `CompileStrategyFactory` | 按长度阈值创建策略实例 |
| **Unit of Work** | `WikiWriteUnit` | 文件+DB 原子提交，失败回滚 |
| **Observer/Pub-Sub** | `EventBus` | 摄取进度与 SSE 端点解耦 |
| **Template Method** | `CompileStrategy.compile()` | 骨架固定，`_execute_compile()` 可变 |
| **Facade** | `IngestService` | 编译提交的稳定接口，隐藏任务管理细节 |

### 1.4 关键约束

- **Local-First**：文件是真理，SQLite 是只读优化的索引
- **零外部依赖（运行时）**：不依赖 GROBID、Elasticsearch 等外部服务
- **异步编译**：LLM 调用在后台，通过 SSE 推送进度
- **向后兼容**：现有 `/api/ingest` 接口和行为不能破坏

---

## 2. 设计原则（本次优化遵循）

1. **职责分离**：检测、提取、编译、渲染是不同职责，不揉在一个类里
2. **开闭原则**：新增功能通过"新增子类/实现"完成，不改现有类的核心逻辑
3. **前端薄、后端厚**：复杂判断和格式化逻辑放在后端，前端只做展示层适配
4. **渐进增强**：所有新功能是 opt-in，未触发时不影响现有行为
5. **数据一致性**：frontmatter（文件）和 SQLite（索引）始终保持同步

---

## 3. 需求一：意图识别（学术 PDF 检测）

### 3.1 现状

- `DeterministicParser.parse_pdf()` 只提取纯文本，不做内容分析
- `CompileStrategyFactory` 仅按文档长度选择策略，不考虑内容类型
- `CompileStrategy._build_system_prompt()` 是通用 prompt，无学术特化

### 3.2 变动点

#### 新增组件

```python
# src/sagemate/ingest/classifier/
class DocumentClassifier(ABC):
    @abstractmethod
    async def classify(self, text: str, file_path: Path) -> DocumentType:
        ...

class HeuristicDocumentClassifier(DocumentClassifier):
    """基于启发式规则检测学术论文。零 LLM 调用，毫秒级。"""
    # 检测 Abstract/References/DOI/作者单位等指标
    # 命中 2+ 个指标 → ACADEMIC_PAPER

class DocumentType(str, Enum):
    ACADEMIC_PAPER = "academic_paper"
    GENERAL_DOCUMENT = "general_document"
    UNKNOWN = "unknown"
```

#### 修改点

| 文件 | 修改内容 | 影响范围 |
|------|---------|---------|
| `DeterministicParser.parse_pdf()` | 返回三元组 `(slug, content, text_sample)`，供分类器使用 | 解析层 |
| `CompileStrategyFactory.create()` | 增加 `document_type` 参数 | 工厂方法签名 |
| `CompileStrategy.__init__()` | 注入 `DocumentClassifier`（可选，默认 None） | 策略基类 |
| `CompileStrategy._build_system_prompt()` | 根据 `document_type` 选择不同的 prompt 模板 | 编译输出 |
| `SourceArchiveRenderer._build_frontmatter()` | 增加 `document_type` frontmatter 字段 | 渲染输出 |
| `models.py` — `SourceArchive` | 增加 `document_type: str = "unknown"` | 数据模型 |

### 3.3 架构决策

**Q: 检测放在解析层还是编译层？**

- 解析层职责是"提取文本"，不应该"理解内容"
- 编译层职责是"知识重组"，不应该"类型判断"
- **决策**：新增独立的 **DocumentClassifier** 组件，位于"解析层"和"编译层"之间。这符合 Single Responsibility Principle，未来可扩展 `BookClassifier`, `LegalDocumentClassifier`。

**Q: Prompt 怎么切换？**

- 方案 A：在 `_build_system_prompt()` 里加 if-else（简单但违反开闭原则）
- 方案 B：新增 `AcademicCompileStrategy` 子类（过度设计，论文和通用文档的编译策略差异只在 prompt，不在分块/深度逻辑）
- **决策**：引入 **SystemPromptBuilder** 策略（轻量级），现有 Strategy 子类不变，通过注入不同的 PromptBuilder 来切换学术/通用编译风格。

```python
class SystemPromptBuilder(ABC):
    @abstractmethod
    def build(self, conventions: str, document_type: DocumentType) -> str: ...

class DefaultPromptBuilder(SystemPromptBuilder): ...
class AcademicPromptBuilder(SystemPromptBuilder):
    # 强调提取：研究问题、方法、实验、数据集、结论、局限性
```

### 3.4 影响范围

- **后端**：编译链路（3 个 Strategy 子类 + Factory + 渲染器）
- **前端**：Source 页面需显示文档类型标签（`🏷️ 学术论文`）
- **数据**：Source Archive frontmatter 增加 `document_type` 字段

---

## 4. 需求二：学术元数据提取

### 4.1 现状

- `SourceArchive` 只有：`slug, title, summary, key_takeaways, extracted_concepts`
- `WikiPage` 无 `authors, year, venue, doi`
- `pages` 表无学术元数据列
- `FullContentRenderer` frontmatter 无学术字段
- `AgentPipeline._format_citations()` 只使用 `number, slug, title`

### 4.2 变动点

#### 数据模型层

```python
# models.py — SourceArchive
class SourceArchive(BaseModel):
    slug: str
    title: str
    summary: str
    key_takeaways: list[str]
    extracted_concepts: list[str]
    # 新增
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str = ""
    document_type: str = "unknown"

# models.py — WikiPage
class WikiPage(BaseModel):
    ... # 现有字段
    # 新增
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str = ""
```

#### 存储层

```python
# store.py — init_schema() — Auto-Migration
# 新增列（复用现有 try/except ALTER TABLE 模式）
- authors TEXT DEFAULT '[]'
- year INTEGER
- venue TEXT DEFAULT ''
- doi TEXT DEFAULT ''
- document_type TEXT DEFAULT 'unknown'
```

#### 编译层

- `COMPILE_RESPONSE_SCHEMA` — `source_archive` 增加 `authors, year, venue, doi, document_type`
- `CompileStrategy._parse_compile_result()` — 解析并传递元数据到 `SourceArchive` 和 `WikiPageCreate`
- `FullContentRenderer._build_frontmatter()` — 输出学术元数据：

```yaml
---
title: '...'
slug: ...
category: source
authors: ["Smith, J.", "Lee, K."]
year: 2024
venue: "Nature"
doi: "10.1038/..."
document_type: academic_paper
sagemate_summary: "..."
---
```

#### 问答层

```python
# AgentPipeline._format_citations()
# 当前：只转换 [[slug]] → [1]
# 变更：对每个 slug 调用 store.get_page() 获取 authors/year
# citations 数组扩展：
# {number, slug, title, authors, year}
```

#### 前端类型层

```typescript
// types/wiki.ts — WikiPage
export interface WikiPage {
  ... // 现有字段
  authors: string[]
  year: number | null
  venue: string
  doi: string
  document_type: string
}

// types/chat.ts — Citation
export interface Citation {
  number: number
  slug: string
  title: string
  authors?: string[]
  year?: number
}
```

### 4.3 架构决策

**Q: 元数据提取放在编译前还是编译中？**

- 编译前独立提取：职责分离；元数据可被其他模块独立使用；编译失败时元数据仍可保留。缺点是多一次 LLM 调用。
- 编译中一起提取：复用一次 LLM 调用。缺点是 prompt 更复杂，编译失败时元数据也丢失。
- **决策**：放在**编译中**（复用 LLM 调用），在 `COMPILE_RESPONSE_SCHEMA` 的 `source_archive` 中增加元数据字段。
  - 理由：学术元数据和 source archive 天然绑定（都是"这篇文档是什么"的信息）；减少一次 LLM 调用对用户体验很重要；如果后续需要独立提取（如批量导入时只提取元数据不编译），可以再拆出 `MetadataExtractor`。

**Q: 元数据存储在哪？**

- 方案 A：只在 Source Archive frontmatter 中存储（文件是真理）
- 方案 B：同时存入 SQLite（为了快速查询和搜索）
- **决策**：**两者都存**。frontmatter 是持久化存储，SQLite 是索引。两者保持一致，符合现有架构（`WikiWriteUnit` 同时写文件和 DB）。

### 4.4 影响范围

- **全链路**：解析 → 编译 → 存储 → 问答 → 前端展示
- **数据迁移**：SQLite 表增加列（使用现有 auto-migration 模式，无破坏性变更）
- **前端**：WikiPage / Citation 类型扩展；Source 页面展示元数据卡片

---

## 5. 需求三：批量导入

### 5.1 现状

- `app.py` `/api/ingest` 只接受单文件（`file: UploadFile | None`）
- 前端 `<input type="file">` 无 `multiple` 属性
- `handleDrop` 只取 `files[0]`
- `ingest.ts` `ingestFile` 只接受单个 `File`
- 后端无目录扫描能力

### 5.2 变动点

#### API 层

**方案选择**：不改 `/api/ingest` 接口，前端并发调用。理由：
- 保持接口简单和向后兼容
- 每个文件仍是独立的摄取流程，复用现有任务管理
- 前端聚合多个任务的进度即可

新增接口（目录扫描）：
```python
@app.post("/api/ingest/scan")
async def scan_and_import(directory: str | None = None):
    """扫描指定目录（默认 raw/papers/），返回未处理的 PDF 列表并自动提交摄取。"""
    # 扫描目录，过滤已存在于 sources 表的文件
    # 为每个新文件调用 ingest_tasks.submit_compile()
    # 返回 task_id 列表
```

#### 前端层

```typescript
// ingest.ts
export const ingestRepo = {
  // 现有方法保持不变
  ingestFile: (file: File, opts?: IngestRequest) => ...,
  
  // 新增：批量上传
  ingestFiles: (files: File[], opts?: IngestRequest) => {
    return Promise.all(files.map(f => ingestRepo.ingestFile(f, opts)))
  },
}
```

```tsx
// Ingest.tsx
// <input type="file" multiple accept="..." />
// handleDrop: 取 e.dataTransfer.files（全部，不是 files[0]）
// 显示文件列表（多选时）
// 提交时并发调用 ingestFiles
```

### 5.3 架构决策

**Q: 后端是否需要真正的批量接口？**

- 前端并发调用现有接口：后端零改动，但前端需要管理 N 个 task_id 和进度
- 后端新增 `/api/ingest/batch`：统一任务管理，但增加复杂度，multipart 传大文件列表可能不稳定
- **决策**：**前端并发调用 + 后端目录扫描接口**。
  - 前端多文件上传：并发调用 `/api/ingest`，前端聚合进度（显示总进度条 + 每个文件的子进度）
  - 目录扫描：后端做（`POST /api/ingest/scan`），因为需要文件系统访问权限
  - 这样分离最符合现有架构：上传是用户主动行为（前端驱动），扫描是系统行为（后端驱动）

### 5.4 影响范围

- **前端**：Ingest.tsx（拖拽区域、文件列表、批量进度展示）、ingest.ts、useIngest.ts
- **后端**：新增 `/api/ingest/scan` 端点（约 50 行）
- **无破坏性变更**：现有单文件上传行为完全保留

---

## 6. 需求四：学术引用格式输出

### 6.1 现状

- `AgentPipeline._format_citations()` 把 `[[slug]]` → `[1]`
- `AgentResponse.citations` 只有 `number, slug, title`
- 前端直接渲染 `[1]` 为链接

### 6.2 变动点

#### 后端

```python
# AgentPipeline._format_citations()
# 当前：
#   title_lookup = {rp["slug"]: rp.get("title", rp["slug"]) for rp in related_pages}
# 变更：
#   查询 store.get_page(slug) 获取 authors 和 year
#   citation = {
#       "number": i,
#       "slug": slug,
#       "title": title_lookup.get(slug, slug),
#       "authors": page.authors if page else [],
#       "year": page.year if page else None,
#   }
```

#### 前端

```typescript
// 后端输出结构化元数据，前端负责格式渲染

// 渲染策略（可切换）
function formatCitation(
  c: Citation,
  style: 'apa' | 'gb7714' | 'inline'
): string {
  switch (style) {
    case 'apa':
      return `${c.authors?.[0] || 'Unknown'} et al. (${c.year || 'n.d.'})`
    case 'gb7714':
      return `[${c.number}] ${c.authors?.join(', ')}. ${c.title}[J]. ${c.venue}, ${c.year}.`
    case 'inline':
      return `[${c.number}]`
  }
}
```

### 6.3 架构决策

**Q: 格式化放在后端还是前端？**

- 后端格式化：统一、简单，但增加后端复杂度，新增格式需要改后端
- 前端格式化：灵活，用户可实时切换格式，减少后端改动
- **决策**：**后端输出结构化元数据，前端负责格式渲染**。
  - 理由：引用格式是展示层 concern，不是业务逻辑；流式输出场景下前端可以动态渲染；未来支持用户切换 APA/GB/T 7714/MLA 不需要改后端。

### 6.4 影响范围

- **后端**：`AgentPipeline._format_citations()`（约 20 行改动）
- **前端**：`types/chat.ts`（类型扩展）、`WikiQAPanel.tsx` / `MarkdownRenderer.tsx`（渲染逻辑）
- **最小影响**：仅问答链路，不影响摄取和编译

---

## 7. 组件关系图（优化后）

```
┌─────────────────────────────────────────────────────────────┐
│                        解析层                                │
│  DeterministicParser.parse_pdf()                            │
│    → (slug, content, text_sample)                           │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                     分类层（新增）                            │
│  DocumentClassifier.classify(text_sample)                   │
│    → DocumentType.ACADEMIC_PAPER / GENERAL_DOCUMENT         │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                        编译层                                │
│  CompileStrategyFactory.create(..., document_type)          │
│    → SinglePassStrategy / ChunkedStrategy / DeepCompile     │
│      → SystemPromptBuilder.build(document_type)             │
│        → AcademicPromptBuilder（论文特化 prompt）            │
│        → DefaultPromptBuilder（通用 prompt）                 │
│      → LLMClient.generate_structured()                      │
│        → COMPILE_RESPONSE_SCHEMA（扩展元数据字段）            │
│      → CompileStrategy._write_pages()                       │
│        → FullContentRenderer.render()                       │
│          → frontmatter 包含 authors/year/venue/doi          │
│        → WikiWriteUnit.commit()                             │
│          → 文件 + DB 原子写入                                │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                        问答层                                │
│  AgentPipeline.query()                                      │
│    → store.search() → store.get_page()                      │
│    → _format_citations()                                    │
│      → 查询 authors/year（新增 DB 字段）                     │
│    → AgentResponse.citations（扩展字段）                     │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                        前端层                                │
│  Ingest.tsx — 多文件上传 + 批量进度                          │
│  Source Page — 显示学术元数据卡片 + 文档类型标签               │
│  WikiChatPanel — 学术引用格式渲染（APA/GB/T 7714）           │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 开发计划

按**依赖关系**排序，不是按优先级。每个 Phase 内部可并行。

### Phase A：基础设施扩展（无用户可见功能，纯架构准备）

| 任务 | 文件 | 说明 | 预估 |
|------|------|------|------|
| A1 | `models.py` | `SourceArchive` / `WikiPage` 增加学术元数据字段 | 30min |
| A2 | `store.py` | `pages` 表 auto-migration（authors/year/venue/doi/document_type） | 30min |
| A3 | `store.py` | `upsert_page` / `get_page` / `list_pages` 支持新字段 | 30min |
| A4 | `types/wiki.ts` | 前端 `WikiPage` 接口扩展 | 15min |
| A5 | `types/chat.ts` | 前端 `Citation` 接口扩展 | 10min |

**验收标准**：TypeScript 0 errors；后端单元测试通过；DB migration 无异常。

### Phase B：意图识别 + 编译特化（核心引擎改造）

| 任务 | 文件 | 说明 | 预估 |
|------|------|------|------|
| B1 | 新增 `ingest/classifier/` | `DocumentClassifier` ABC + `HeuristicDocumentClassifier` | 1h |
| B2 | 新增 `ingest/prompts/` | `SystemPromptBuilder` ABC + `DefaultPromptBuilder` + `AcademicPromptBuilder` | 1h |
| B3 | `strategies.py` | `CompileStrategy` 注入 `SystemPromptBuilder`；`CompileStrategyFactory` 传 `document_type` | 30min |
| B4 | `compiler.py` | `COMPILE_RESPONSE_SCHEMA` 扩展元数据字段；`_parse_compile_result` 解析元数据 | 30min |
| B5 | `source_archive.py` | `FullContentRenderer` frontmatter 输出学术元数据 | 30min |
| B6 | `file_parser.py` | `parse_pdf` 返回 `text_sample`（前 2000 字供分类器使用） | 15min |
| B7 | `app.py` | `ingest_file` 中集成分类器，传递 `document_type` 到编译流程 | 30min |

**验收标准**：上传论文和通用文档，编译 prompt 不同；Source Archive frontmatter 包含 `document_type`。

### Phase C：元数据打通（全链路贯通）

| 任务 | 文件 | 说明 | 预估 |
|------|------|------|------|
| C1 | `agent/pipeline.py` | `_format_citations` 查询 DB 获取 authors/year | 30min |
| C2 | `models.py` | `AgentResponse.citations` 扩展字段 | 15min |
| C3 | 前端渲染层 | 引用卡片/气泡支持学术格式显示 | 1h |
| C4 | `core/watcher.py` | `sync_file` 解析 frontmatter 中的学术元数据，同步到 DB | 30min |

**验收标准**：问答时引用显示作者和年份；外部修改 frontmatter 后 watcher 正确同步元数据到 DB。

### Phase D：批量导入（用户可见功能）

| 任务 | 文件 | 说明 | 预估 |
|------|------|------|------|
| D1 | `app.py` | 新增 `POST /api/ingest/scan` 目录扫描接口 | 30min |
| D2 | `ingest.ts` | 新增 `ingestFiles` 批量方法 | 15min |
| D3 | `Ingest.tsx` | `<input multiple>`、多文件拖拽、文件列表展示 | 1h |
| D4 | `useIngest.ts` / store | 批量任务进度聚合（总进度条 + 子任务状态） | 1h |

**验收标准**：拖拽 5 个 PDF 同时上传，前端显示每个文件的独立进度和总进度；目录扫描接口能发现 raw/papers/ 下的未处理文件。

---

## 9. 风险与回退方案

| 风险 | 影响 | 回退方案 |
|------|------|---------|
| 启发式分类误判率高 | 论文被当作普通文档编译，输出质量下降 | 在 Source 页面提供"重新分类为学术论文"按钮，手动触发重新编译 |
| LLM 元数据提取不准 | authors/year 错误，引用格式混乱 | 前端元数据面板（已完成 Phase 2）允许用户手动编辑并保存 |
| DB migration 失败 | 新列无法创建，upsert 报错 | 使用 `try/except` 包裹 ALTER TABLE（已有模式），失败时优雅降级（元数据不存 DB，仅存 frontmatter） |
| 批量上传前端并发过多 | 后端同时编译 10+ 个文档，LLM 限流 | IngestTaskManager 已有 `max_concurrent_compiles=3` 的 Semaphore，天然限流 |

---

## 10. 可维护性检查清单

- [ ] 新增组件都有 ABC / 接口，不直接依赖具体实现
- [ ] 现有 `SinglePassStrategy` / `ChunkedStrategy` / `DeepCompileStrategy` 无需修改核心逻辑
- [ ] `/api/ingest` 接口签名不变，向后兼容
- [ ] 所有新 DB 列都有默认值，不破坏现有查询
- [ ] frontmatter 新增字段不影响现有 frontmatter 解析（`_parse_frontmatter` 是宽松解析）
- [ ] 前端类型扩展使用 `?` 可选标记，不破坏现有组件
