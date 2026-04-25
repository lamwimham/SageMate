# SageMate 生产级优化方案

## 现状诊断

### 内存占用分析（900MB 浏览器）

| 组件 | 问题 | 内存估算 |
|------|------|---------|
| **CodeMirror 实例** | 每个标签页独立创建，切换不销毁 | ~30MB × N |
| **Zustand 持久化** | wikiTabs 持久化到 localStorage，大对象序列化 | ~50MB |
| **React Query 缓存** | 默认 gcTime=5min，页面内容长期驻留 | ~100MB+ |
| **WikiPagesStore** | 独立 fetch，与 React Query 重复缓存 | ~20MB |
| **MarkdownRenderer** | 预览态渲染全部内容，无虚拟滚动 | ~50MB |
| **事件监听** | 全局 keydown 未清理，闭包引用 | 泄漏 |
| **后端 app.py** | 1614行单体文件，启动慢 | 影响冷启动 |

### 关键发现

1. **CodeMirror 无生命周期管理**：切换标签页时编辑器实例不销毁，语法树、decorations、历史栈持续累积
2. **双重缓存**：`useWikiPagesStore` 和 `useQuery` 同时缓存页面列表，数据重复
3. **Zustand 持久化滥用**：`wikiTabs` 持久化到 localStorage，包含完整标签状态，每次变更全量序列化
4. **全局事件泄漏**：`useKeyboardShortcuts` 在多个组件中重复注册，未正确清理
5. **后端单体**：`app.py` 1614行，违反单一职责原则

## 优化方案

### Phase 1: 前端内存治理（立即实施）

#### 1.1 CodeMirror 实例池化
- 活跃池最多 3 个实例，冻结池 5 个
- 非活跃标签页自动冻结（保留内容，销毁编辑器）
- 组件卸载时 `view.destroy()` 强制释放

#### 1.2 React Query 缓存分层
| 数据类型 | gcTime | staleTime | 策略 |
|---------|--------|-----------|------|
| 页面内容 | 0 | 30s | 标签关闭即清除 |
| 页面列表 | 10min | 5min | 全局共享 |
| 搜索结果 | 1min | 30s | 用完即弃 |

#### 1.3 Zustand 持久化精简
- `wikiTabs` 只持久化 `tabs` 和 `activeKey`，不持久化 `dirtyKeys`/`saveHandlers`
- `noteContent` 不持久化（已是 session-only）

#### 1.4 事件监听治理
- `useKeyboardShortcuts` 改为单例模式（Layout 级别注册一次）
- 所有 `addEventListener` 必须配对 `removeEventListener`

#### 1.5 MarkdownRenderer 虚拟化
- 长文档使用虚拟滚动（react-window 或 @tanstack/react-virtual）
- 预览态只渲染可视区域

### Phase 2: 后端架构优化

#### 2.1 app.py 拆分
```
src/sagemate/api/
├── app.py              # 入口 + 生命周期（<200行）
├── routers/
│   ├── wiki.py         # Wiki CRUD
│   ├── ingest.py       # 采集/编译
│   ├── settings.py     # 设置管理
│   ├── wechat.py       # 微信插件
│   └── projects.py     # 项目管理
├── dependencies.py     # 共享依赖注入
└── middleware.py       # CORS/日志/异常处理
```

#### 2.2 SQLite 连接池
- 当前 `Store` 类单连接，高并发阻塞
- 改为连接池（aiosqlite + 连接池）

#### 2.3 编译器内存优化
- `compiler_max_source_chars` 默认 50k，超限截断
- 增量编译避免全量加载

### Phase 3: 构建优化

#### 3.1 Bundle 拆分
- CodeMirror 动态导入（`import()`）
- 路由级别 code splitting
- 目标：初始 bundle < 500KB

#### 3.2 Tree Shaking
- 检查 `@codemirror` 主题和语言包是否全量引入
- 检查 `lucide-react` 是否只导入使用的图标

## 实施优先级

| 优先级 | 任务 | 预期内存节省 | 实施时间 |
|-------|------|------------|---------|
| P0 | CodeMirror 生命周期管理 | ~200MB | 2h |
| P0 | React Query gcTime=0 | ~150MB | 30min |
| P1 | 事件监听单例化 | ~50MB | 1h |
| P1 | Markdown 虚拟滚动 | ~100MB | 2h |
| P2 | app.py 拆分 | 启动加速 | 4h |
| P2 | SQLite 连接池 | 并发提升 | 3h |
| P3 | Bundle 动态加载 | 初始加载加速 | 4h |

## 验证指标

- 浏览器内存占用：< 300MB（目标）
- 初始 bundle：< 500KB
- 冷启动时间：< 3s
- ESLint 错误：0
- 超大文件：0（>500行）
