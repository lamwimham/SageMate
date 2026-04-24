# PRD: 渐进式知识编辑器 (Progressive Knowledge Editor)

> **Issue**: #2
> **类型**: Feature
> **优先级**: P0
> **状态**: ✅ **COMPLETED** (All 3 Phases Merged)
> **创建时间**: 2026-04-24
> **完成时间**: 2026-04-24

---

## 1. 产品目标

为 SageMate Core 打造**标杆级 Wiki 页面编辑体验**，核心原则：

- **静默支持**: 编辑器像空气，存在但不被感知
- **不打断**: 不弹窗、不确认、不跳转思路
- **知识连接优先**: Wikilink 是核心交互，不是附属功能

---

## 2. 数据模型

### 2.1 编辑状态

```typescript
interface EditorState {
  mode: 'view' | 'edit'              // 当前模式
  content: string                    // 当前编辑器内容
  originalContent: string            // 进入编辑时的原始内容（用于 diff/取消）
  isDirty: boolean                   // 是否有未保存的修改
  isSaving: boolean                  // 是否正在保存
  saveError: string | null           // 保存错误信息
  draft: string | null               // localStorage 草稿
}

interface PageMetadata {
  slug: string
  title: string
  category: WikiCategory
  tags: string[]
  sources: string[]                  // source slugs
  created_at: string
  updated_at: string
}
```

### 2.2 API 接口（复用现有）

| 方法 | 路径 | 用途 | 请求体 |
|------|------|------|--------|
| GET | `/pages/{slug}` | 获取页面内容+元数据 | - |
| PUT | `/pages/{slug}` | 保存页面内容 | `{ content: string }` |
| GET | `/pages` | 获取所有页面列表（Wikilink 补全） | - |

---

## 3. 交互规范

### 3.1 模式切换

```
视图态 (默认)                    编辑态 (点击"编辑")
┌──────────────────────┐        ┌──────────────────────┐
│ 页面标题      [编辑] │        │ 页面标题  [保存][取消]│
│                      │  -->   │                      │
│ 渲染后的内容...      │        │ CodeMirror 编辑区...  │
│ [[wikilink]] 可点击  │        │                      │
└──────────────────────┘        └──────────────────────┘
```

- 视图态: 纯只读渲染，`[[wikilink]]` 可点击跳转
- 编辑态: CodeMirror 6 WYSIWYG 模式，渲染+编辑一体
- 切换是瞬时完成的，无过渡动画

### 3.2 Wikilink 补全

```
输入触发: 键入 [[
弹出补全: 光标下方，固定 5 项高度
```

补全数据结构:
```typescript
interface WikilinkCompletion {
  slug: string           // 页面 slug
  title: string          // 页面标题
  category: string       // 页面分类
  summary: string        // 前 80 字摘要
  isLinked: boolean      // 当前页面是否已链接此页面
}
```

交互细节:
- 输入 `[[` 后 100ms 内弹出（已预加载页面列表，无网络延迟）
- 支持模糊搜索（title → slug → tags 优先级）
- `Enter` 确认插入 `[[slug]]`
- `Esc` 关闭，继续输入
- 不选任何项继续打字，面板自动关闭
- 已存在的链接显示 `✓` 标记

### 3.3 保存机制

```
自动保存: 每 30s 静默写入 localStorage
显式保存: ⌘+S / Ctrl+S 发送 PUT /pages/{slug}
保存成功: 无提示
保存失败: 底部显示 "保存失败，草稿已保留"（3s 后淡出）
```

### 3.4 外部文件变更

```
Watcher 检测到外部修改 → 底部固定条显示:
┌──────────────────────────────────────┐
│ ⚠️ 此文件在外部被修改 [重新加载][忽略]│
└──────────────────────────────────────┘
```

- 不弹窗、不打断、不自动覆盖
- 用户手动选择处理

### 3.5 元数据面板

```
默认折叠: 📋 属性 · concept · AI, 架构    [展开]
展开后:
┌──────────────────────────────────────┐
│ 标题  [可编辑输入框]                  │
│ 分类  concept              [下拉切换] │
│ 标签  [AI ×] [架构 ×] [+ 添加]       │
│ 来源  [source-slug ×]                │
│ 创建  2026-04-24 11:42    只读       │
│ 更新  2026-04-24 14:15    只读       │
└──────────────────────────────────────┘
```

- 修改属性标记 isDirty，与正文一起保存
- 保存时调用 PUT 接口（后端已支持 frontmatter 解析）

---

## 4. 组件架构

```
PageDetailPanel (改造)
├── PageHeaderView          ← 标题 + 编辑/保存/取消按钮
├── MetadataBar             ← 新增：可折叠元数据面板
├── PageContentView         ← 现有：只读渲染 (保留)
├── PageEditorView          ← 新增：编辑器容器
│   ├── CodeMirrorEditor    ← CodeMirror 6 实例
│   ├── WikilinkAutocomplete ← 补全面板组件
│   └── EditorStatus        ← 保存状态指示 (仅失败时)
├── ExternalChangeBanner    ← 新增：外部变更提示条
└── AISidebar (Phase 3)     ← 未来：AI 助手侧边栏
```

---

## 5. 状态机

```
┌─────────┐    点击"编辑"     ┌─────────┐
│  VIEW   │ ──────────────▶  │  EDIT   │
│ (只读)  │                  │ (编辑)  │
└─────────┘                  └────┬────┘
                                  │
                          ┌───────┴───────┐
                          │               │
                   ⌘+S/点击保存      点击"取消"
                          │               │
                    ┌─────┴─────┐    ┌────┴────┐
                    │  SAVING   │    │  VIEW   │
                    └─────┬─────┘    │ (丢弃)  │
                          │         └─────────┘
                    ┌─────┴─────┐
                    │ 成功/失败 │
                    └─────┬─────┘
                          │
                    ┌─────┴─────┐
                    │   VIEW    │
                    │ (刷新)    │
                    └───────────┘
```

---

## 6. 视觉规范

### 6.1 配色

| 元素 | 颜色 | 用途 |
|------|------|------|
| 编辑器背景 | `#1a1a2e` | 深靛蓝，暗色主题 |
| 编辑区文字 | `#e2e8f0` | 浅灰白，高对比度 |
| Wikilink | `#60a5fa` | 蓝色，可识别 |
| 断链 | `#ef4444` | 红色虚线下划线 |
| 补全面板背景 | `#1e1e3f` | 比编辑器稍深 |
| 补全选中项 | `#3b3b6b` | 深紫灰，高亮 |

### 6.2 字体

- 编辑区: `JetBrains Mono, SF Mono, Consolas, monospace`
- 渲染区: `Inter, SF Pro, -apple-system, sans-serif`
- 字号: 14px (编辑器), 15px (渲染)
- 行高: 1.7

### 6.3 动效

| 动效 | 时长 | 缓动 | 场景 |
|------|------|------|------|
| 补全面板出现 | 120ms | ease-out | Wikilink 弹出 |
| 补全面板消失 | 100ms | ease-in | 关闭补全 |
| 模式切换 | 0ms | - | 视图/编辑切换 (瞬时) |
| 错误提示淡入 | 200ms | ease-out | 保存失败 |
| 错误提示淡出 | 300ms | ease-in | 3s 后消失 |

---

## 7. 实施计划

### Phase 1: 基础编辑器 (PR #1)

**范围**: CodeMirror 6 集成 + 读写切换 + 保存 + 脏状态

**改动**:
- 安装 `@uiw/react-codemirror`, `@codemirror/lang-markdown`, `@codemirror/theme-one-dark`
- 新建 `PageEditorView` 组件
- 改造 `PageDetailPanel` 支持 mode 切换
- 实现 `⌘+S` 保存快捷键
- 实现 localStorage 草稿自动保存 (30s)
### Phase 1: 基础编辑器 (PR #3 ✅ Merged)

**范围**: CodeMirror 6 集成 + 读写切换 + 保存 + 脏状态
**状态**: ✅ 已完成

### Phase 2: 知识连接 (PR #4 ✅ Merged)

**范围**: Wikilink 补全 + 断链视觉 + 元数据面板
**状态**: ✅ 已完成

### Phase 3: AI 助手 (PR #5 ✅ Merged)

**范围**: AI 浮动工具栏 + 建议关联
**状态**: ✅ 已完成
- 预加载 `GET /pages` 列表
- 断链检测（解析内容中的 `[[...]]` 与页面列表比对）
- 新建 `MetadataBar` 组件
- 元数据修改与保存集成

**预期代码量**: ~600 行

### Phase 3: AI 助手 (PR #3)

**范围**: AI 浮动工具栏 + 建议关联

**改动**:
- 新建 `AISidebar` 组件
- 对接 `/agent/chat` 接口
- 选中文本后显示 AI 操作按钮
- AI 生成建议以灰色显示在原段落下方

**预期代码量**: ~500 行

---

## 8. 测试策略

| 测试类型 | 内容 | 工具 |
|---------|------|------|
| 单元测试 | EditorState 状态机、保存逻辑 | Vitest |
| 组件测试 | PageEditorView 渲染、切换 | Testing Library |
| 集成测试 | 完整编辑→保存→刷新流程 | Playwright |
| 手动测试 | Wikilink 补全流畅度、断链提示 | 浏览器 |

---

## 9. 验收标准

- [ ] 从视图切换到编辑 < 100ms
- [ ] 输入 `[[` 到补全弹出 < 150ms
- [ ] 万行文档滚动 60fps
- [ ] ⌘+S 保存到显示结果 < 1s
- [ ] 保存失败时草稿不丢失
- [ ] 外部文件变更不自动覆盖
- [ ] TypeScript 0 errors
- [ ] 所有交互不弹窗、不打断

---

*PRD v1.0 — 待开发*
