# [feat] Markdown 编辑器 — 技术选型与架构设计

> **Issue**: 待定 (需配置 git remote)
> **类型**: Feature Discussion
> **优先级**: 待定
> **创建时间**: 2026-04-24

---

## 1. 背景

当前 SageMate Core 的 Wiki 页面详情面板 (`PageDetailPanel`) 只支持**只读渲染**（通过 `MarkdownRenderer`），缺少编辑能力。

用户编辑 Wiki 页面的工作流目前只能通过以下方式：
- 直接修改本地 Markdown 文件（手动/外部编辑器）
- 依赖 File Watcher 自动同步到数据库

这违背了产品"本地优先但界面统一"的原则——用户应该能在 Web UI 中直接编辑、预览、保存 Wiki 页面。

---

## 2. 需求定义

### 2.1 核心需求

| 需求 | 描述 | 优先级 |
|------|------|--------|
| 实时预览 | 编辑区和预览区同步渲染，支持 Markdown 渲染 | P0 |
| 保存/草稿 | 显式保存按钮，自动保存草稿 | P0 |
| 语法高亮 | 代码块、表格、列表等语法高亮 | P0 |
| Wikilink 支持 | `[[page-slug]]` 格式的快捷插入和跳转 | P0 |
| 图片上传 | 拖拽/粘贴图片，自动上传到 `wiki/assets/` | P1 |
| 工具栏 | Bold/Italic/Heading/List/Code/Link 等常用操作 | P1 |
| 全屏编辑 | 沉浸式编辑模式 | P2 |
| 版本历史 | 查看页面修改历史 | P3 |

### 2.2 现有 API 复用

后端已有 `PUT /pages/{slug}` 接口：

```python
@app.put("/pages/{slug}")
async def update_page(slug: str, request: Request):
    """Update a wiki page by saving new content to its markdown file."""
    # 接收 { content: string }
    # 写入文件 + 更新数据库 + 触发 watcher
```

前端可以直接对接，无需后端新增接口。

---

## 3. 技术选型对比

### 3.1 候选方案

| 方案 | 类型 | 体积 | Wikilink 支持 | 社区活跃度 | 评估 |
|------|------|------|---------------|-----------|------|
| **Monaco Editor** | 代码编辑器 | ~3MB | 需自定义扩展 | ⭐⭐⭐⭐⭐ | 功能强大但过重，适合"代码+Markdown"混编场景 |
| **CodeMirror 6** | 代码编辑器 | ~500KB | 需自定义扩展 | ⭐⭐⭐⭐⭐ | 轻量模块化，扩展灵活 |
| **Milkdown** | Markdown WYSIWYG | ~300KB | 插件化支持 | ⭐⭐⭐⭐ | 专为 Markdown 设计，插件系统完善 |
| **Toast UI Editor** | WYSIWYG + Markdown | ~400KB | 需自定义 | ⭐⭐⭐⭐ | 双栏编辑+工具栏开箱即用 |
| **react-markdown + textarea** | 自研组合 | ~100KB | 完全自定义 | ⭐⭐⭐⭐⭐ | 最灵活，但需要自己实现工具栏和快捷键 |
| **md-editor-v3** | Vue 系组件 | ~200KB | 需适配 | ⭐⭐⭐ | Vue 专用，不适合 React 项目 |

### 3.2 推荐方案

**首选: CodeMirror 6 + react-markdown 预览**

理由：
1. SageMate 前端是 **React + Vite**，CodeMirror 6 有官方 `@codemirror/lang-markdown` 和 `@uiw/react-codemirror` 包装
2. 体积仅 ~500KB（Monaco 的 1/6）
3. 插件架构灵活，可以自定义 Wikilink 补全、快捷键、主题
4. 预览侧直接用现有的 `MarkdownRenderer`（已集成 `markdown-it`），零新增依赖
5. 与现有 `PageDetailPanel` 集成最简单——只需加一个编辑/预览切换按钮

---

## 4. 架构设计

### 4.1 组件结构

```
PageDetailPanel (现有)
  ├── PageHeaderView          ← 标题 + 元数据
  ├── PageContentView         ← 现有只读渲染
  └── PageEditorView (新增)    ← 新增编辑器
       ├── EditorToolbar      ← 工具栏 (Bold/Italic/Heading/Link/Wikilink/Save)
       ├── CodeMirrorEditor   ← 编辑区 (CodeMirror 6)
       ├── MarkdownPreview    ← 预览区 (复用 MarkdownRenderer)
       └── EditorStatus       ← 保存状态 (已保存/编辑中/保存失败)
```

### 4.2 状态机

```
          ┌──────────┐
          │   VIEW   │ ← 默认状态：只读显示
          └────┬─────┘
               │ [点击"编辑"]
               ▼
          ┌──────────┐
          │  EDITING │ ← 编辑模式，从文件加载内容到 CodeMirror
          └────┬─────┘
         ┌─────┴──────┐
         │             │
  [Ctrl+S/点击保存]   [点击"取消"]
         │             │
         ▼             ▼
    ┌─────────┐   ┌──────────┐
    │ SAVING  │   │   VIEW   │
    └────┬────┘   └──────────┘
         │
    ┌────┴─────┐
    │ 成功/失败 │
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │   VIEW   │ ← 回到只读，刷新内容
    └──────────┘
```

### 4.3 数据流

```
用户点击"编辑"
  ↓
fetch(`/pages/${slug}`)  ← 获取当前页面内容
  ↓
CodeMirror 初始化，加载内容
  ↓
用户编辑（自动标记 dirty）
  ↓
用户 Ctrl+S 或点击保存
  ↓
PUT /pages/{slug} { content: newContent }
  ↓
成功 → 刷新 PageDetailView + 显示"已保存"
失败 → 显示错误，保留编辑状态
```

---

## 5. 待讨论问题

1. **双栏 vs 切换模式**: CodeMirror + 预览并排（双栏）还是编辑/预览切换？
   - 双栏: 实时预览，体验好，但移动端空间受限
   - 切换: 简单，节省空间，但需要手动切换

2. **Wikilink 补全**: 是否需要 `[[` 触发自动补全（列出所有 wiki 页面 slug）？
   - 需要额外调用 `GET /pages` 获取 slug 列表
   - CodeMirror 6 的 autocompletion 插件支持自定义补全源

3. **图片处理**: 拖拽图片上传是直接走 `POST /ingest` 还是本地保存到 `wiki/assets/`？

4. **权限/锁定**: 多用户同时编辑同一页面时是否需要文件锁？（当前 MVP 可能不需要）

---

## 6. 下一步

- [ ] 确定技术选型（投票/决策）
- [ ] 确认交互模式（双栏 vs 切换）
- [ ] 编写详细实现计划
- [ ] 创建 feature 分支实现

---

*本文档待讨论，欢迎补充。*
