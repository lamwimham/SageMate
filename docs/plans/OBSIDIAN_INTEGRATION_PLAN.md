# Obsidian Vault 赋能方案：SageMate as AI Engine

> 针对 Obsidian 重度用户场景，设计 SageMate 与现有 Vault 的最小侵入式整合方案。  
> 核心目标：**不迁移、不替代，让 SageMate 成为 Vault 的 AI 后台引擎。**

---

## 一、背景与用户画像

### 1.1 用户画像

| 维度 | 描述 |
|------|------|
| **工具惯性强** | 已有成熟的文件夹体系、Daily Notes 工作流、Canvas、Dataview 查询模板 |
| **笔记量级大** | 通常 500~5000 篇笔记，跨度数年，涵盖阅读、项目、灵感、会议等多种类型 |
| **手动维护疲劳** | 双向链接靠手动打，标签体系随时间膨胀，找不到"三个月前关于某概念的笔记" |
| **对 AI 有预期** | 希望 AI 帮他做"发现关联"、"归纳整理"、"跨文档问答"，但**绝不接受把笔记搬到新平台** |

### 1.2 Obsidian 的固有局限

1. **搜索是关键词匹配**：无法问"我所有关于 Rust 内存管理的笔记里，哪些观点相互矛盾"
2. **Graph View 是静态的**：只能看已有链接，不能发现"隐式关联"
3. **无自动归纳能力**：100 篇 Daily Notes 不会自动变成 1 篇概念综述
4. **无内容校验机制**：笔记里的过时效信息、自相矛盾不会主动提醒

### 1.3 SageMate 能补位的价值

| Obsidian 缺什么 | SageMate 能提供 |
|----------------|----------------|
| 语义级搜索与问答 | FTS5 + LLM 综合回答，带 `[[笔记名]]` 引用 |
| 自动发现隐式关联 | LLM 分析全文，推荐"这篇笔记和已有 3 篇相关" |
| 碎片自动归纳 | 将 Daily Notes / fleeting notes 编译为概念页/MOC |
| 知识库健康检查 | 孤立笔记检测、矛盾观点标记、过期内容提醒 |
| 新内容智能链接 | 读一篇 PDF/URL，自动链接回 Vault 中的相关笔记 |

---

## 二、核心设计原则

```
┌─────────────────────────────────────────────────────────────────┐
│                     设计原则：Vault First                        │
├─────────────────────────────────────────────────────────────────┤
│  1. Vault 目录结构 = 唯一真相源，SageMate 不修改用户文件夹布局    │
│  2. AI 生成内容输出到 Vault 内的指定子目录，用户拥有完全编辑权     │
│  3. 用户现有笔记被当作"已存在的知识页"索引，而非 raw source 重编译 │
│  4. Obsidian 继续是"写作与阅读界面"，SageMate 是"后台引擎"       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、赋能模式设计

### 模式 A：Vault 外挂索引 + 智能问答（Phase 1）

**定位**：最小可行产品（MVP）。零迁移成本，5 分钟配置完成。

```
用户操作流：

  Obsidian Vault 目录
        │
        ▼
┌─────────────────────┐
│ 1. 添加为 Project   │  ← 用户在 SageMate UI 选择 Vault 路径
│    wiki_dir_name="."│     或 config 里直接配置
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ 2. Watcher 递归索引  │  ← 监控整个 Vault 的 .md 变化
│    所有笔记入 SQLite │     解析 frontmatter + [[wikilink]] + #tag
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ 3. 用户提问         │  ← 在 SageMate UI 或 Obsidian 插件面板
│    "Rust 内存安全    │     SageMate 搜索 Vault 笔记 → LLM 综合回答
│     有哪些笔记提到"  │     回答中附带 [[笔记名]] 引用
└─────────────────────┘
```

**关键行为**：
- Vault 里的 `.md` 文件被识别为 `source_type: obsidian_note`
- 不触发 `compile` 流程（避免把用户的永久笔记重新编译成 source archive）
- 直接索引进 `pages` 表，FTS5 可搜，LLM 回答可引用

### 模式 B：AI 辅助整理 + 回写 Vault（Phase 2）

**定位**：把 SageMate 的编译能力输出到 Vault。

```
输入（来自 SageMate）                    输出（回到 Vault）

PDF / URL / 文本  ──compile──►  Source Archive + 概念页
                                      │
                                      ▼
                          ┌──────────────────────────┐
                          │ 写入 Vault/AI-Synthesis/ │  ← 可配置路径
                          │ - source-{slug}.md       │
                          │ - concept-{slug}.md      │
                          │ - analysis-{slug}.md     │
                          └──────────────────────────┘
                                      │
                                      ▼
                          页面内自动包含 [[用户已有笔记]] 的 backlink
                          Obsidian Graph View 中可见 AI 生成的关联
```

**关键行为**：
- 编译输出目录可配置（默认 `AI-Synthesis/`，用户可改）
- AI 生成的页面使用标准 Markdown + frontmatter，Obsidian 完全兼容
- 生成页面中的 `[[wikilink]]` 指向 Vault 中的已有笔记，形成双向链接

### 模式 C：Vault 健康巡检 + 关联推荐（Phase 3）

**定位**：主动式知识库维护。

| 巡检类型 | 触发方式 | 输出 |
|---------|---------|------|
| **孤立笔记检测** | 定时任务 / 手动触发 | 列出 Vault 中 0 入链 + 0 出链的笔记，建议合并或删除 |
| **关联推荐** | 打开单篇笔记时 | "这篇笔记提到了'熵增'， Vault 中有 3 篇相关笔记未链接，是否添加 [[链接]]？" |
| **矛盾检测** | 新笔记编译完成后 | "新笔记对'Rust 所有权'的描述与 '2024-03-rust-notes.md' 冲突，请 review" |
| **概念归纳** | 用户手动选择 N 篇笔记 | 生成一篇 MOC（Map of Content）页面，汇总相关笔记 |

---

## 四、技术实现路径

### 4.1 架构变更总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         当前架构（Single Wiki）                              │
│                                                                             │
│   Project root_path                                                         │
│        └── wiki/                 ← Watcher 只监控这里                        │
│            ├── entities/                                                    │
│            ├── concepts/                                                    │
│            └── ...                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ 变更
┌─────────────────────────────────────────────────────────────────────────────┐
│                      目标架构（Vault-Aware Project）                         │
│                                                                             │
│   Project root_path (Obsidian Vault)                                        │
│        ├── 01-Inbox/                                                        │
│        ├── 02-Projects/          ← Watcher 递归监控整个 Vault               │
│        ├── 03-Concepts/          ← 用户现有笔记 = WikiPage (category: note) │
│        ├── Daily Notes/                                                     │
│        ├── AI-Synthesis/         ← 编译输出目录（可配置）                    │
│        │   ├── sources/                                                     │
│        │   ├── concepts/                                                    │
│        │   └── analyses/                                                    │
│        └── .obsidian/            ← 忽略（隐藏目录过滤）                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 需改动的模块清单

#### 4.2.1 Project 模型扩展

**文件**：`src/sagemate/models.py`

```python
class Project(BaseModel):
    id: str
    name: str
    root_path: str
    wiki_dir_name: str = "wiki"
    assets_dir_name: str = "assets"
    
    # 新增字段
    project_type: ProjectType = ProjectType.SAGEMATE  # sagemate | obsidian
    output_dir_name: str = "AI-Synthesis"             # 编译输出子目录
    ignored_patterns: list[str] = [".obsidian", ".git", "_templates"]
    status: ProjectStatus = ProjectStatus.INACTIVE
    created_at: str = ""
    updated_at: str = ""
```

新增 `ProjectType` 枚举：
- `SAGEMATE`：默认模式，root_path 下创建 `wiki/` 子目录
- `OBSIDIAN`：Vault 模式，root_path 即 wiki 根，输出到 `output_dir_name`

#### 4.2.2 Watcher 增强

**文件**：`src/sagemate/core/watcher.py`

当前问题：
- `WikiFileHandler` 的 `_infer_category` 只认 `/entities`、`/concepts` 等固定路径
- `WatcherManager` 只监控 `wiki_dir`

改动点：
1. **监控范围**：`OBSIDIAN` 类型 project，watcher 监控 `root_path`，递归所有子目录
2. **过滤规则**：跳过 `ignored_patterns`（`.obsidian`、`.git` 等）
3. **Category 推断**：Vault 中的笔记默认 category = `note`，除非 frontmatter 显式指定
4. **去重机制**：同一 Vault 中的笔记通过相对路径作为 `slug`，避免与用户手动创建的 `wiki/` 内容冲突

```python
class VaultFileHandler(FileSystemEventHandler):
    """Obsidian Vault 专用 handler。"""
    
    def _should_ignore(self, path: Path) -> bool:
        """检查路径是否在忽略列表中。"""
        for pattern in self.ignored_patterns:
            if pattern in path.parts:
                return True
        return False
    
    def _relative_slug(self, path: Path) -> str:
        """用相对于 Vault 根的路径作为 slug，保证唯一性。"""
        rel = path.relative_to(self.vault_root)
        return str(rel.with_suffix("")).replace("/", "--")
```

#### 4.2.3 Store 层适配

**文件**：`src/sagemate/core/store.py`

改动点：
1. `pages` 表已有 `source_pages` 字段，复用它来标记"这篇 wiki page 来源于 Vault 中的哪些笔记"
2. 新增索引优化：Vault 笔记量大（5000+），需要确保 FTS5 查询性能
3. `upsert_page` 需要支持"来自 Vault 的笔记不覆盖现有记录，只更新 hash 变化"

#### 4.2.4 Ingest Pipeline 适配

**文件**：`src/sagemate/ingest/` 相关

改动点：
1. **文件类型识别**：`DeterministicParser.parse_markdown` 遇到 Vault 中的 `.md`，**不**把它当作 raw source 重新编译，而是直接索引
2. **编译输出路径**：`compiler.py` 中的 `_write_pages` 需要支持把输出写到 project 指定的 `output_dir_name`
3. **Source Archive 渲染器**：生成的 source archive 页面需要包含 `related_vault_notes` 字段，列出 Vault 中相关的已有笔记

#### 4.2.5 API 层新增端点

**文件**：`src/sagemate/api/app.py`

新增端点：

```
# 基于 Vault 内容的智能问答
POST /api/v1/projects/{project_id}/obsidian/query
Body: { "query": "string", "context_note_paths": ["string"] }
Response: { "answer": "string", "citations": [{"slug": "...", "title": "...", "excerpt": "..."}] }

# 为指定笔记推荐关联
POST /api/v1/projects/{project_id}/obsidian/suggest-links
Body: { "note_path": "string" }
Response: { "suggestions": [{"target_slug": "...", "target_title": "...", "reason": "..."}] }

# Vault 健康巡检
GET /api/v1/projects/{project_id}/obsidian/health
Response: { "orphans": [...], "contradictions": [...], "stale_notes": [...] }

# 批量归纳（MOC 生成）
POST /api/v1/projects/{project_id}/obsidian/synthesize-moc
Body: { "note_paths": ["string"], "moc_title": "string" }
Response: { "moc_path": "string", "content": "string" }
```

---

## 五、数据流详细设计

### 5.1 Vault 笔记索引流

```
用户保存笔记  Daily Notes/2026-04-25.md
        │
        ▼
┌──────────────────────────────┐
│ VaultFileHandler.on_modified │  ← watchdog 触发
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ sync_file()                  │
│ 1. 读取文件内容               │
│ 2. 解析 YAML frontmatter      │
│ 3. 提取 #tag（Obsidian 行内标签）│
│ 4. 提取 [[wikilink]]          │
│ 5. 计算 content_hash          │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ Store.upsert_page()          │
│ slug = "Daily Notes--2026-04-25"
│ category = "note"
│ file_path = "/abs/path/to/Vault/Daily Notes/2026-04-25.md"
│ source_type = "obsidian_note"  ← 新增标识
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ FTS5 search_idx 同步         │
│ 内容经过 Jieba 分词后索引     │
└──────────────────────────────┘
```

### 5.2 新内容编译 + 回写 Vault 流

```
用户上传 URL / PDF
        │
        ▼
┌──────────────────────────────┐
│ IngestTaskManager            │
│ 1. URLCollector / PDFParser  │
│ 2. 生成 source_content       │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ IncrementalCompiler.compile()│
│ Prompt 中包含：               │
│ - source_content              │
│ - 当前 Vault 的 index_context │
│ - conventions.md             │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ LLM 返回 CompileResult       │
│ {                             │
│   source_archive: {...},      │
│   new_pages: [                │
│     {slug, title, category,   │
│      content, related_notes:  │
│        ["Concepts/Rust",      │
│         "Daily Notes/2026..."]│
│     }                         │
│   ]                           │
│ }                             │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ _write_pages()               │
│ 输出路径：                    │
│ {vault_root}/AI-Synthesis/   │
│   concepts/rust-memory.md    │
│   sources/url-slug.md        │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ VaultFileHandler.on_created  │  ← 新文件触发 watcher
│ 新页面被索引，obsidian 中     │
│ Graph View 立即显示新节点和链接│
└──────────────────────────────┘
```

---

## 六、Obsidian 兼容层设计

### 6.1 语法映射

| Obsidian 语法 | SageMate 处理策略 |
|-------------|------------------|
| `[[Note Name]]` | 已支持，提取为 outbound_links |
| `[[Note Name\|Alias]]` | 需要扩展 regex，提取 link target + display text |
| `![[Embed Note]]` | 索引进内容时，把 embed 内容内联展开 |
| `#tag` 行内标签 | 新增提取逻辑，纳入 `tags` 字段 |
| `tags: [a, b]` frontmatter | 已支持 |
| `aliases: ["x", "y"]` | 新增提取，用于搜索别名匹配 |
| `cssclasses: [...]` | 忽略 |
| Callouts (`> [!NOTE]`) | 保留原样，索引时当作普通文本 |
| Dataview 查询块 | 保留原样，索引进代码块文本 |
| Excalidraw / Canvas | 忽略（非 `.md` 文件） |

### 6.2 Frontmatter 规范

SageMate 输出到 Vault 的页面，frontmatter 采用 Obsidian 兼容格式：

```yaml
---
title: "Rust 内存安全模型"
slug: "rust-memory-safety"
category: "concept"
created: "2026-04-25T10:30:00"
source: "https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html"
tags: ["rust", "memory-safety", "ownership"]
related_vault_notes:
  - "Concepts/Rust"
  - "Daily Notes/2026-04-20"
sagemate_generated: true
sagemate_version: "0.5.0"
---
```

`related_vault_notes` 中的路径会被渲染为 `[[Concepts/Rust]]` 形式，Obsidian 自动识别为双向链接。

---

## 七、分阶段路线图

### Phase 1：Vault 索引 + 基础问答（2 周）

**目标**：用户能把 Obsidian Vault 添加为 project，在 SageMate UI 里基于 Vault 内容提问。

**任务清单**：

| # | 任务 | 文件 | 优先级 |
|---|------|------|--------|
| 1.1 | Project 模型新增 `project_type` 和 `output_dir_name` | `models.py` | P0 |
| 1.2 | `create_project` API 支持创建 OBSIDIAN 类型 project | `app.py` | P0 |
| 1.3 | Watcher 支持递归监控整个 Vault 根目录 | `watcher.py` | P0 |
| 1.4 | Watcher 添加忽略规则（`.obsidian`, `.git`） | `watcher.py` | P0 |
| 1.5 | 解析 Obsidian 特有语法：`[[alias]]`、`#tag`、`aliases` | `watcher.py` | P1 |
| 1.6 | 标记 Vault 笔记的 `source_type`，避免被 compile 流程误处理 | `store.py`, `ingest/` | P0 |
| 1.7 | Query Handler 支持只搜索 Vault 笔记（project 作用域过滤） | `agent/pipeline.py` | P0 |
| 1.8 | 前端 Project 选择器支持切换 Vault project | `frontend/` | P1 |

**验收标准**：
- 能把一个 1000 篇笔记的 Vault 添加为 project，5 分钟内完成初始索引
- 在 SageMate 搜索框输入问题，返回的答案中正确引用 Vault 中的笔记
- 在 Vault 中新增/修改/删除笔记，SQLite 索引在 1 秒内同步

### Phase 2：编译回写 + 关联推荐（2 周）

**目标**：新 ingest 的内容编译后输出到 Vault；系统能推荐笔记间关联。

**任务清单**：

| # | 任务 | 文件 | 优先级 |
|---|------|------|--------|
| 2.1 | Compiler 输出路径支持 project 级配置 | `compiler.py` | P0 |
| 2.2 | Source Archive / Knowledge Page 渲染器生成 Obsidian 兼容 frontmatter | `source_archive.py` | P0 |
| 2.3 | CompileResult 新增 `related_vault_notes` 字段 | `models.py`, `prompts.py` | P1 |
| 2.4 | 新增 `/obsidian/suggest-links` API | `app.py` | P1 |
| 2.5 | 新增 `/obsidian/synthesize-moc` API | `app.py` | P2 |
| 2.6 | 前端支持"一键接受关联推荐"交互 | `frontend/` | P2 |

**验收标准**：
- 上传一篇 PDF，编译完成后在 Vault 的 `AI-Synthesis/` 目录下出现新 `.md` 文件
- 新文件中的 `[[wikilink]]` 在 Obsidian 中被正确识别为双向链接
- 调用 suggest-links API，返回的推荐相关度人工评估 > 70% 准确率

### Phase 3：健康巡检 + Obsidian 插件（3 周）

**目标**：提供主动式知识库维护能力；Obsidian 端有原生插件体验。

**任务清单**：

| # | 任务 | 文件 | 优先级 |
|---|------|------|--------|
| 3.1 | 孤立笔记检测算法 | `app.py` 或新模块 | P1 |
| 3.2 | 矛盾检测（基于 LLM 对比两篇笔记摘要） | 新模块 | P2 |
| 3.3 | 新增 `/obsidian/health` API | `app.py` | P1 |
| 3.4 | 定时巡检任务（Cron 触发） | `task_manager.py` | P2 |
| 3.5 | Obsidian 社区插件原型（Local REST API 桥接） | 新仓库 `sagemate-obsidian-plugin` | P1 |
| 3.6 | 插件支持：侧边栏显示"相关笔记" | 插件仓库 | P2 |
| 3.7 | 插件支持：右键"Ask SageMate" | 插件仓库 | P2 |

**验收标准**：
- 运行 health check，能正确找出 Vault 中 10 篇以上的孤立笔记
- Obsidian 插件安装后，侧边栏实时显示当前编辑笔记的相关推荐
- 插件能通过 Local REST API 与 SageMate 后端通信（支持自定义端口）

---

## 八、Obsidian 插件架构（预览）

由于 Obsidian 插件需要独立仓库和 TypeScript 开发，本计划书只定义接口契约，具体实现放到 Phase 3。

### 插件 ↔ SageMate 通信协议

```typescript
// 插件设置界面
interface SageMatePluginSettings {
  apiBaseUrl: string;        // 默认 "http://localhost:8000"
  apiToken?: string;         // 如需鉴权
  projectId: string;         // 绑定的 Vault project ID
  outputDir: string;         // 默认 "AI-Synthesis"
  autoSuggestLinks: boolean; // 是否自动显示关联推荐
}

// 插件调用的核心接口
interface SageMateClient {
  // 基于当前笔记内容提问
  ask(query: string, currentNotePath?: string): Promise<AnswerResponse>;
  
  // 获取当前笔记的关联推荐
  getSuggestions(notePath: string): Promise<LinkSuggestion[]>;
  
  // 手动触发 MOC 生成（选中多篇笔记）
  synthesizeMoc(notePaths: string[], title: string): Promise<{mocPath: string}>;
  
  // 获取 Vault 健康报告
  getHealth(): Promise<HealthReport>;
}
```

---

## 九、风险与边界

### 9.1 已知风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **Vault 笔记量过大**（>10,000 篇）导致初始索引慢 | 用户体验差 | 增加后台批量索引任务 + 进度条；首次索引用批量 INSERT 而非逐页 |
| **Watcher 性能瓶颈** | 大量文件同时修改时 debounce 失效 | 限制并发 sync 数；大 batch 改为异步队列 |
| **Obsidian 与 SageMate 同时写同一文件** | 数据冲突 | AI 输出目录与用户写作目录分离；输出文件用 `sagemate_generated: true` 标记 |
| **FTS5 中文分词质量影响搜索** | 搜不到想要的内容 | 持续调优 Jieba 词典；必要时fallback到 LIKE |
| **LLM 幻觉导致关联推荐不准** | 用户不信任推荐 | 推荐结果必须附带来源引用；允许用户一键忽略 |

### 9.2 明确不做（Out of Scope）

1. **不实现 Obsidian 插件的离线模式**：插件必须能连接到运行中的 SageMate 后端
2. **不替代 Obsidian Sync / Git**：文件同步仍由用户自行解决
3. **不解析 Excalidraw / Canvas 文件**：只处理 `.md`
4. **不修改用户 Vault 中的原有笔记**：SageMate 只读索引 + 在子目录中写新内容
5. **不实现实时协同编辑**：Obsidian 负责写，SageMate 负责读和生成

---

## 十、验收标准汇总

### Phase 1 验收

- [ ] 创建 OBSIDIAN 类型 project，指定 Vault 路径，wiki_dir_name = "." 生效
- [ ] Watcher 正确索引 Vault 中所有 `.md` 文件（排除 `.obsidian`）
- [ ] Vault 笔记的 frontmatter、`[[wikilink]]`、`#tag` 被正确解析
- [ ] 在 SageMate UI 提问，返回结果包含 Vault 笔记的 `[[slug]]` 引用
- [ ] Vault 中新建笔记后，SageMate 搜索能在 1 秒内找到

### Phase 2 验收

- [ ] 编译 PDF/URL 后，输出文件出现在 Vault 的 `AI-Synthesis/` 目录
- [ ] 输出文件的 frontmatter 被 Obsidian 正确识别
- [ ] 输出文件中的 `[[wikilink]]` 在 Obsidian Graph View 中显示为链接
- [ ] `suggest-links` API 对 20 篇测试笔记的推荐准确率达 70%+

### Phase 3 验收

- [ ] `health` API 返回的孤立笔记清单人工验证准确
- [ ] Obsidian 插件能通过 HTTP 与 SageMate 通信
- [ ] 插件侧边栏显示当前笔记的"相关笔记"推荐
- [ ] 端到端测试通过：用户从 Obsidian 选中笔记 → 请求 MOC → MOC 文件回写到 Vault → Obsidian 中可见

---

## 十一、附录：快速配置示例

### 11.1 通过 API 创建 Obsidian Project

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "root_path": "/Users/alice/Documents/Obsidian Vault",
    "name": "My Obsidian Vault",
    "project_type": "obsidian",
    "wiki_dir_name": ".",
    "output_dir_name": "AI-Synthesis"
  }'
```

### 11.2 期望的 Vault 目录结构（配置后）

```
Obsidian Vault/
├── 01-Inbox/
├── 02-Projects/
├── 03-Concepts/
│   └── Rust.md
├── Daily Notes/
│   └── 2026-04-25.md
├── AI-Synthesis/           # SageMate 输出目录
│   ├── sources/
│   │   └── rust-book-ch04.md
│   └── concepts/
│       └── rust-ownership-model.md
├── .obsidian/              # 被 watcher 忽略
└── index.md                # Vault 的 MOC（用户维护）
```

---

> **文档版本**: v1.0  
> **编写日期**: 2026-04-25  
> **对应代码版本**: sagemate 0.4.0  
> **下一阶段动作**: 进入 Phase 1 开发，优先实现 Project 模型扩展 + Watcher 增强
