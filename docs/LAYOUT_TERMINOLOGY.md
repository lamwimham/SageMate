# SageMate 前端布局术语规范

> 本文档定义 SageMate 前端全局布局中各区域的统一名称，用于团队沟通、代码注释和文档撰写。
>
> 代码中已存在对应组件的文件名/导出名，沟通时优先使用本文档定义的中文名称，必要时附注英文组件名。

---

## 布局总览

```
┌─────────────────────────────────────────────────────────────┐
│  TopBar（顶部栏）                                            │
├──────────┬───────────────────────────────────┬──────────────┤
│          │                                   │              │
│ Activity │              Main                 │   Detail     │
│  Bar     │         （主内容区）               │   Panel      │
│（活动栏） │                                   │ （详情面板）  │
│  48px    │                                   │   300px      │
│          │                                   │              │
├──────────┴───────────────────────────────────┴──────────────┤
│  BottomPanel（底部面板）— 默认隐藏                            │
└─────────────────────────────────────────────────────────────┘
```

全局布局由 `PageShell` 组件实现，采用两层 CSS Grid：

- **外层 Grid**：3 行 × 2 列
  - Row 1: TopBar（跨 2 列）
  - Row 2: ActivityBar（Col 1）+ Inner Workspace（Col 2）
  - Row 3: BottomPanel（跨 2 列，可选）

- **内层 Grid**（Inner Workspace）：1 行 × 2–3 列
  - `sidebarOpen && detailOpen` → `260px | 1fr | 300px`
  - `sidebarOpen && !detailOpen` → `260px | 1fr`
  - `!sidebarOpen && detailOpen` → `1fr | 300px`
  - `!sidebarOpen && !detailOpen` → `1fr`

---

## 区域术语表

| 中文名称 | 英文组件名 | 文件路径 | 位置 / 尺寸 | 职责 | 内容来源 |
|---|---|---|---|---|---|
| **顶部栏** | `TopBar` | `components/layout/TopBar.tsx` | 最顶部，高 `36px`，通栏 | 项目切换器、布局控制按钮（显隐 Sidebar / DetailPanel） | 全局固定 |
| **活动栏** | `ActivityBar` | `components/layout/ActivityBar.tsx` | 最左侧，宽 `48px`，垂直 | 一级导航图标（Wiki / Ingest / Raw / Status / Settings） | 全局固定 |
| **侧边栏** | `Sidebar` | `components/layout/Sidebar.tsx` | ActivityBar 右侧，宽 `260px` | 页面级辅助内容容器（导航 / 筛选 / 列表） | 各页面通过 `usePageLayout({ sidebar: ... })` 注册 |
| **主内容区** | `Main` | `PageShell` 内 `<main>` | 中间，自适应宽度 | 路由页面主体内容渲染区 | React Router |
| **详情面板** | `DetailPanel` | `components/layout/DetailPanel.tsx` | 最右侧，宽 `300px` | 页面级详情 / 监控 / 操作面板 | 各页面通过 `usePageLayout({ detailPanel: ... })` 注册 |
| **底部面板** | `BottomPanel` | `components/layout/BottomPanel.tsx` | 最底部，高 `200px`，通栏 | 扩展面板（默认隐藏，可放日志、终端等） | 全局，通过 `layoutStore.bottomOpen` 控制 |

---

## Sidebar 内部结构

Sidebar 是**容器组件**，内容由当前页面通过 `usePageLayout` 注册。内部固定分为两个区域：

```
┌─────────────────────┐
│                     │
│   页面边栏内容       │  ← flex: 1，页面专属
│   (IngestSidebar     │     随路由切换自动替换
│    / WikiSidebar     │
│    / SettingsSidebar)│
│                     │
├─────────────────────┤
│                     │
│  CompileTaskSidebar │  ← shrink: 0，全局常驻
│  (编译任务边栏)      │     有任务时显示，无任务时隐藏
│                     │
└─────────────────────┘
```

| 中文名称 | 英文组件名 | 文件路径 | 位置 | 说明 |
|---|---|---|---|---|
| **页面边栏内容** | `IngestSidebar` / `WikiSidebar` / `SettingsSidebar` / `StatusSidebar` | `components/layout/sidebars/` | Sidebar 上半部（`flex-1`） | 页面专属，随路由切换 |
| **编译任务边栏** | `CompileTaskSidebar` | `components/layout/CompileTaskSidebar.tsx` | Sidebar 底部（`border-t`） | 全局编译任务微型监控器，所有页面可见；轮询 `/api/v1/ingest/tasks` + SSE 实时更新 |

---

## DetailPanel 内部结构

DetailPanel 同样是**容器组件**，内容由当前页面通过 `usePageLayout` 注册。不同页面会挂载不同的面板：

| 中文名称 | 英文组件名 | 文件路径 | 所属页面 | 说明 |
|---|---|---|---|---|
| **处理进度面板** | `IngestProgressPanel` | `components/layout/detail-panels/IngestProgressPanel.tsx` | Ingest（存在 `activeTaskId` 时） | 单任务步骤时间线 + 进度条 + 成功结果卡片 + 失败诊断卡片 |
| **编译任务面板** | `CompileTaskPanel` | `components/layout/detail-panels/CompileTaskPanel.tsx` | Ingest（无活跃任务时） | 全局编译任务列表，任务卡片可展开查看结果 / 诊断信息 |
| **AI 侧边面板** | `AISidebar` | `components/layout/detail-panels/AISidebar.tsx` | Wiki 页面 | AI 对话、问答、分析 |
| **元数据栏** | `MetadataBar` | `components/layout/detail-panels/MetadataBar.tsx` | Wiki 编辑模式 | 页面属性（标题、分类、标签等）编辑 |
| **页面编辑器视图** | `PageEditorView` | `components/layout/detail-panels/PageEditorView.tsx` | Wiki 编辑模式 | Markdown 编辑器容器 |
| **默认空面板** | `PageDetailPanel` | `components/layout/detail-panels/PageDetailPanel.tsx` | 未注册页面 | 占位提示「此页面无详情面板内容」 |

> **动态切换规则（Ingest 页面）**：
> - 用户提交编译任务后 → `activeTaskId` 被设置 → DetailPanel 自动切换为 `IngestProgressPanel`
> - 无活跃任务时 → DetailPanel 显示 `CompileTaskPanel`

---

## 布局控制机制

### 1. 页面级布局注册

```tsx
// 在页面组件顶层调用
usePageLayout({
  sidebar: <IngestSidebar />,        // 注册到 Sidebar 容器
  detailPanel: <CompileTaskPanel />,  // 注册到 DetailPanel 容器
})
```

- 页面挂载时自动注册，卸载时自动清理
- `usePageLayout` 现已支持**动态更新**（依赖数组包含 `config`），可根据状态切换面板

### 2. 全局显隐控制

由 `layoutStore`（Zustand）统一管理：

| 状态 | 控制方法 | 说明 |
|---|---|---|
| `sidebarOpen` | `toggleSidebar()` | 控制 Sidebar 显隐 |
| `detailOpen` | `toggleDetail()` | 控制 DetailPanel 显隐 |
| `bottomOpen` | `toggleBottom()` | 控制 BottomPanel 显隐 |

TopBar 上的布局控制按钮直接操作这些状态。

### 3. LayoutContext

`LayoutContext`（React Context）在 `LayoutProvider` 中维护：
- `sidebarContent` — 当前页面注册的 Sidebar 内容
- `detailPanelContent` — 当前页面注册的 DetailPanel 内容

`Sidebar` 和 `DetailPanel` 容器组件从 Context 读取内容并渲染。

---

## 沟通示例

| 场景 | ❌ 避免这样说 | ✅ 正确说法 |
|---|---|---|
| 最左侧的图标导航 | "左边栏" / "顶部导航" | **ActivityBar（活动栏）** |
| 260px 宽的辅助面板 | "左边的栏" / "侧边栏" | **Sidebar（侧边栏）** |
| 最右侧的 300px 面板 | "右边显示任务进度的地方" | **DetailPanel（详情面板）** |
| Sidebar 底部的任务列表 | "底部那个任务列表" | **CompileTaskSidebar（编译任务边栏）** |
| Ingest 页面右侧的进度 | "上传后右边的面板" | **IngestProgressPanel（处理进度面板）** |
| Ingest 页面右侧的任务列表 | "全局任务监控" | **CompileTaskPanel（编译任务面板）** |
| 中间的主体内容 | "中间的内容" | **Main（主内容区）** |
| 最顶部的横条 | "顶部导航" | **TopBar（顶部栏）** |

---

## 相关文件速查

```
frontend/src/
├── components/layout/
│   ├── PageShell.tsx              # 全局布局壳（Grid 定义）
│   ├── TopBar.tsx                 # 顶部栏
│   ├── ActivityBar.tsx            # 活动栏
│   ├── Sidebar.tsx                # 侧边栏容器
│   ├── DetailPanel.tsx            # 详情面板容器
│   ├── BottomPanel.tsx            # 底部面板
│   ├── CompileTaskSidebar.tsx     # 编译任务边栏
│   ├── sidebars/                  # 页面级 Sidebar 内容
│   │   ├── IngestSidebar.tsx
│   │   ├── SettingsSidebar.tsx
│   │   └── ...
│   └── detail-panels/             # 页面级 DetailPanel 内容
│       ├── IngestProgressPanel.tsx
│       ├── CompileTaskPanel.tsx
│       ├── AISidebar.tsx
│       └── ...
├── layout/
│   └── LayoutContext.tsx          # React Context（sidebarContent / detailPanelContent）
├── hooks/
│   └── usePageLayout.ts           # 页面级布局注册 Hook
└── stores/
    └── layout.ts                  # Zustand store（sidebarOpen / detailOpen / bottomOpen）
```

---

*最后更新：2026-04-25*
