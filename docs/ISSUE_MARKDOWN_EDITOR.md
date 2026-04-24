# [feat] Markdown 编辑器 — 架构演进与终极目标：超越 Obsidian 的体验

> **Issue**: #13
> **类型**: Feature / Epic
> **优先级**: P0 (Core Value)
> **状态**: 阶段一完成 / 阶段二规划中
> **创建时间**: 2026-04-24
> **最后更新**: 2026-04-24

---

## 1. 愿景

打造 SageMate 的核心交互体验：**比肩甚至超越 Obsidian 的 Markdown 编辑体验**，同时保持 Web 应用的轻量级优势。

我们的路线是：
1.  **稳健起步**：基于 CodeMirror 6 构建高性能源码编辑器 + 实时分屏预览。
2.  **平滑进阶**：通过 Live Preview 插件实现源码与渲染的无缝融合。
3.  **超越经典**：结合 SageMate 的 AI 能力，提供智能补全、双向链接推荐、知识图谱联动。

---

## 2. 阶段性成果与计划

### ✅ 阶段一：架构重构与 MVP (已完成)

- [x] **技术选型**: CodeMirror 6 + React 组件化架构。
- [x] **实时预览**: 实现 `ViewToggle` (编辑/分屏/预览) + `useDeferredValue` 性能优化（左侧打字丝滑，右侧异步渲染）。
- [x] **自动配对引擎 (Auto-Pair)**: 采用策略模式重构 `autopair.ts`，支持：
  - [x] 智能补全 `**`, `*`, `` ` ``, `~~` 等 Markdown 符号。
  - [x] 智能识别行首 `#`, `-`, `>` 并自动补全空格或升级标题级别。
- [x] **双向链接支持**: 实现 `wikilink-autocomplete.ts`，输入 `[[` 触发全库页面补全。
- [x] **Note 编辑器**: 独立的 `NoteEditor` 组件，支持新建笔记时自动保存并升级为 Page Tab。
- [x] **状态管理**: WikiTabsStore 支持多 Tab 切换、标签持久化 (localStorage)、以及 Tab 类型 (overview/note/page) 统一管理。

### 🚀 阶段二：Live Preview (实时渲染/内联预览) (进行中)

*目标：用户输入 Markdown 语法时，源码自动隐藏并渲染为最终样式（类 Obsidian 模式）。*

- [ ] **CodeMirror View Plugin**: 开发自定义插件，实时拦截源码并渲染为 Widget。
- [ ] **语法隐藏逻辑**:
  - [ ] `# 标题` → 隐藏 `#`，渲染为大号标题。
  - [ ] `**粗体**` → 隐藏 `**`，渲染为粗体。
  - [ ] `[[链接]]` → 渲染为可点击的 Link Widget。
- [ ] **光标智能行为**: 点击渲染后的区域自动展开为源码编辑，失焦后恢复渲染。

### 🔮 阶段三：AI 增强与深度集成 (规划中)

- [ ] **AI 辅助续写**: 在光标处按 `Cmd+I` 唤起 AI 补全建议 (Ghost Text)。
- [ ] **智能引用**: 选中一段文字，自动搜索 Wiki 库并推荐相关页面插入 `[[链接]]`。
- [ ] **知识图谱联动**: 编辑器侧边栏实时显示当前编辑页面的关联图谱 (Local Graph View)。
- [ ] **块级引用**: 支持 `[[Page#BlockID]]` 级别的细粒度链接。

---

## 3. 核心架构设计

### 3.1 自动配对引擎 (Strategy Pattern)

```typescript
// 策略接口
interface PairStrategy {
  trigger: string
  pair: string
  customHandler?: (view: EditorView) => boolean | null
}

// 工厂函数
createAutoPairExtension() -> [Extension, ...]
```

### 3.2 性能优化模型

*   **Deferred Rendering**: `content` (高频更新) -> `useDeferredValue` -> `deferredContent` (渲染)。
    *   *效果*：即使在低端设备上渲染千字长文，输入端延迟 < 16ms。

---

## 4. 技术栈

*   **Editor Core**: `@codemirror/lang-markdown`, `@codemirror/view`, `@codemirror/state`
*   **UI**: React 18, TailwindCSS
*   **Icons**: Inline SVG (Heroicons style)
*   **State**: Zustand (WikiTabsStore, EditorStore)

---

*本文档长期有效，随项目演进而持续更新。*
