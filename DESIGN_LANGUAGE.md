# SageMate Core — 设计语言与产品哲学

> **Version**: 1.0  
> **Date**: 2026-04-22  
> **Designer**: UI/UX Redesign Initiative

---

## 1. 产品哲学：生长界面 (Growth Interface)

SageMate 不是传统的"文档管理工具"，而是一个**与 AI 共生的知识生命体**。

它的核心信念是：**知识是有机生长的，不是静态堆砌的。**

每一次摄入、每一次查询、每一次链接，都是这个知识网络的神经元在建立新的突触连接。因此，界面不应是冰冷的文件柜，而应是一座**可以被观察、触摸、与之对话的数字花园**。

### 1.1 设计五律

| 律则 | 含义 | 界面表现 |
|------|------|---------|
| **有机秩序** | 知识像神经网络一样自组织 | 节点有连接感，关系可视化，布局响应内容密度 |
| **渐进揭示** | 信息深度随用户意图展开 | 搜索是入口，hover 是窥视，点击是沉浸，编辑是共创 |
| **温度感知** | 知识有"新鲜度"和"活跃度" | 时间、关联度、引用频率通过微光、色彩饱和度传达 |
| **深度宁静** | 知识工作者需要长时间专注 | 深色基调，低饱和配色，无视觉噪音，内容为王 |
| **AI 共生** | AI 不是按钮，而是氛围 | 处理状态如呼吸，建议如低语，生成如流淌 |

---

## 2. 色彩系统：深海与神经元

### 2.1 主色板 (深色主题 — 默认)

```css
/* 背景层 — 从深空到近地 */
--bg-void:        #050508;   /* 纯黑底色，极少使用 */
--bg-deep:        #0c0c12;   /* 页面主背景 */
--bg-surface:     #13131f;   /* 卡片、面板 */
--bg-elevated:    #1c1c2e;   /* 浮层、下拉、hover */
--bg-input:       #161624;   /* 输入框背景 */

/* 边框层 — 几乎不可见的结构 */
--border-subtle:  rgba(255, 255, 255, 0.05);
--border-medium:  rgba(255, 255, 255, 0.08);
--border-strong:  rgba(255, 255, 255, 0.12);

/* 文字层 — 层级由透明度控制 */
--text-primary:   rgba(243, 244, 246, 0.95);  /* 标题、正文 */
--text-secondary: rgba(156, 163, 175, 0.85);  /* 摘要、标签 */
--text-tertiary:  rgba(107, 114, 128, 0.85);  /* 时间、元数据 — WCAG AA ≥4.5:1 */
--text-muted:     rgba(75, 85, 99, 0.75);     /* 禁用、水印 — WCAG AA ≥3:1 */

/* 强调色 — 神经元脉冲 */
--accent-neural:  #818cf8;   /* 靛蓝紫 — 主交互、链接、AI */
--accent-growth:  #fbbf24;   /* 琥珀金 — 新生成、更新、highlight */
--accent-living:  #34d399;   /* 翡翠绿 — 健康、成功、活跃 */
--accent-warm:    #f472b6;   /* 玫瑰粉 — 关联、引用、出链 */
--accent-caution: #fb923c;   /* 橙黄 — 警告、注意 */
--accent-danger:  #f87171;   /* 珊瑚红 — 错误、删除 */

/* 渐变 — 极光与深海 */
--gradient-hero:  linear-gradient(135deg, #1e1b4b 0%, #0c0c12 50%, #1a1025 100%);
--gradient-card:  linear-gradient(180deg, rgba(129,140,248,0.08) 0%, rgba(12,12,18,0) 100%);
--gradient-glow:  radial-gradient(circle at 50% 0%, rgba(129,140,248,0.15) 0%, transparent 60%);
```

### 2.2 语义色彩

| 语义 | 色值 | 使用场景 |
|------|------|---------|
| Entity (实体) | `#60a5fa` (蓝) | 人、组织、产品页面 |
| Concept (概念) | `#fbbf24` (琥珀) | 理论、框架、方法论 |
| Analysis (分析) | `#c084fc` (紫) | 对比、综合、深度分析 |
| Source (来源) | `#34d399` (绿) | 原始文档、来源页 |

### 2.3 主题切换

系统支持 `data-theme="light"` 属性切换。浅色主题在需要打印或户外场景使用，非默认。

---

## 3. 字体系统：清晰与温度

### 3.1 字体栈

```css
/* 中文正文 — 跨平台最优回退 */
--font-sans: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif;

/* 英文与标题 */
--font-display: "Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont, sans-serif;

/* 代码与元数据 */
--font-mono: "JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", monospace;
```

### 3.2 字号层级

| 层级 | 大小 | 字重 | 行高 | 字间距 | 用途 |
|------|------|------|------|--------|------|
| Display | 2.5rem (40px) | 700 | 1.2 | -0.02em | 页面大标题 |
| H1 | 1.75rem (28px) | 600 | 1.3 | -0.01em | 卡片标题、章节 |
| H2 | 1.25rem (20px) | 600 | 1.4 | 0 | 子标题 |
| H3 | 1.125rem (18px) | 500 | 1.5 | 0 | 小节标题 |
| Body | 0.9375rem (15px) | 500 | 1.65 | 0.01em | 正文阅读（中文 500 字重更清晰） |
| Small | 0.875rem (14px) | 400 | 1.6 | 0 | 辅助说明 |
| Caption | 0.8125rem (13px) | 500 | 1.5 | 0.02em | 标签、时间、元数据（12px 为可访问性下限） |
| Mono | 0.8125rem (13px) | 400 | 1.5 | 0 | 代码、slug、路径 |
```

---

## 4. 间距系统：呼吸感

基于 **6px 网格**（而非 4px），让中文排版更从容。

| Token | 值 | 用途 |
|-------|-----|------|
| space-1 | 6px | 图标与文字间隙 |
| space-2 | 12px | 紧凑内边距 |
| space-3 | 18px | 标准组件内边距 |
| space-4 | 24px | 卡片内边距 |
| space-5 | 36px | 区块间距 |
| space-6 | 48px | 大区块分隔 |
| space-7 | 72px | 页面级间距 |

---

## 5. 组件风格

### 5.1 卡片 (Knowledge Node)

- 圆角：`16px` (1rem)
- 背景：`bg-surface` + `gradient-card`
- 边框：`1px solid border-subtle`
- Hover：`border-medium` + 顶部微光 `gradient-glow` + `translateY(-2px)`
- 阴影：无阴影（深色主题靠边框和渐变区分层次）

### 5.2 按钮

| 类型 | 样式 |
|------|------|
| Primary | `bg-elevated` + `border-medium` + `text-primary`，hover 时 `accent-neural` 光晕扩散 |
| Accent | 渐变背景 `linear-gradient(135deg, #6366f1, #8b5cf6)` + 白色文字 |
| Ghost | 透明背景 + `text-secondary`，hover `bg-elevated` |
| Danger | 透明 + `text-danger`，hover `bg-danger/10` |

所有按钮圆角：`10px`（稍圆润但非药丸）

### 5.3 输入框

- 背景：`bg-input`
- 边框：`1px solid border-subtle`，focus 时 `border-accent-neural/50` + 外发光
- 圆角：`12px`
- Placeholder：`text-muted`

### 5.4 标签 (Badge)

- 圆角：`6px`（小圆角，信息密度高）
- 背景：语义色 15% 透明度
- 文字：语义色 90% 亮度

### 5.5 链接与 WikiLink

- 外部链接：`accent-neural`，下划线 hover 出现
- 内部 WikiLink `[[slug]]`：`bg-accent-neural/10` + `accent-neural` 文字 + `border-accent-neural/20` + 圆角 `6px` + hover 时背景加深

---

## 6. 动效系统：生命的节律

### 6.1 缓动函数

```css
--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
--ease-in-out-sine: cubic-bezier(0.37, 0, 0.63, 1);
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
```

### 6.2 关键动画

| 动画 | 时长 | 缓动 | 场景 |
|------|------|------|------|
| Fade Up | 0.4s | ease-out-expo | 页面入场、卡片加载 |
| Scale In | 0.3s | ease-spring | 弹窗、下拉菜单 |
| Glow Pulse | 2s infinite | ease-in-out-sine | AI 处理中、加载态 |
| Border Flow | 3s infinite | linear | 活跃节点边框流光 |
| Number Tick | 0.6s | ease-out-expo | 统计数字变化 |

### 6.3 滚动行为

- 全局：`scroll-behavior: smooth`
- 内容区：自定义滚动条 `6px` 宽，`border-radius: 3px`，`bg-elevated` 轨道

---

## 7. 页面级设计策略

### 7.1 Dashboard — 知识宇宙的概览

- **隐喻**：从太空俯瞰知识星球
- **布局**：顶部 Hero 区（渐变深空）+ 统计星座（4 颗核心星球）+ 双栏（最近活动流 + 快捷入口）
- **亮点**：统计数字有呼吸微动，健康状态用行星环颜色表示

### 7.2 知识库列表 — 神经元网络

- **隐喻**：在神经网络中导航
- **布局**：顶部统一搜索框（最大的视觉重心）+ 分类筛选胶囊 + 卡片网格
- **亮点**：卡片 hover 时顶部出现微光，表示这个知识节点"被激活"

### 7.3 页面详情 — 思维宫殿

- **隐喻**：进入一个完整的思维房间
- **布局**：宽屏阅读区（70%）+ 侧边栏元数据（30%，sticky）
- **亮点**：编辑模式切换无缝（高度不变，内容交叉淡入淡出），WikiLink 有独特视觉标识

### 7.4 摄入 — 知识炼金术

- **隐喻**：将原料投入炼金炉，AI 进行转化
- **布局**：左侧三栏输入区（文件/URL/文本）+ 右侧状态面板
- **亮点**：处理过程中有流动的进度可视化，成功时结果卡片生长出现

### 7.5 状态 — 系统生命体征

- **隐喻**：知识星球的健康监测站
- **布局**：Tab 导航 + 数据密集型面板
- **亮点**：健康检查用雷达图/热力图思维，成本用条形图，日志用时间轴

---

## 8. 交互原则

1. **减少跳转** — 尽量在同一页内完成操作，用模态层、抽屉、折叠面板
2. **即时反馈** — 每个操作在 100ms 内有视觉响应
3. **容错设计** — 删除需要二次确认，编辑自动保存草稿
4. **键盘优先** — `/` 聚焦搜索，`Esc` 关闭弹窗，`Cmd+Enter` 提交
5. **AI 存在感** — AI 处理时界面有微妙的脉冲，不是死板的 loading spinner

---

## 9. 实现约束

- 无构建工具，纯 Tailwind CDN + 自定义 CSS
- 深色主题为默认，浅色主题通过 `data-theme` 属性切换
- 所有图标使用内联 SVG，无外部图标库
- 字体使用系统字体栈，不引入外部字体文件（避免网络延迟）
- 兼容现代浏览器（Chrome, Safari, Firefox, Edge）

---

*Growth Interface — 让知识可见，让生长可感。*
