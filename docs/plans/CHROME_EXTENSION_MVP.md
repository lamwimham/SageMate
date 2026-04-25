# SageMate Clipper — Chrome 插件 MVP 设计文档

> 桌面端主力内容采集入口。用户在浏览器中阅读时，一键将页面内容发送到 SageMate。

---

## 一、产品定位

```
Chrome 插件 = SageMate 的"剪贴板"

用户在浏览器阅读文章
    │
    ▼ 点击 SageMate 图标
提取当前页面正文
    │
    ▼ 一键发送
保存到 SageMate 素材库（raw/）
    │
    ▼ 可选：触发 AI 编译
生成结构化 Wiki 页面
```

**核心价值**：比"复制 URL → 粘贴 → 等待爬取"快 10 倍，成功率 100%。

---

## 二、功能规格（MVP）

### 2.1 用户流程

```
┌─────────────────────────────────────────┐
│  用户在微信公众平台阅读文章              │
│  （已登录，页面已完全渲染）              │
└─────────────────────────────────────────┘
                │
                ▼ 点击 Chrome 工具栏图标
┌─────────────────────────────────────────┐
│  🌿 SageMate Clipper                    │
│                                         │
│  📄 AI 时代的知识管理方法论              │
│  🔗 mp.weixin.qq.com                    │
│  📝 约 3,200 字                         │
│                                         │
│  [✓] 自动编译为知识卡片                 │
│                                         │
│     [🚀 发送到 SageMate]                │
│                                         │
│  状态：✅ 已连接 localhost:8000         │
└─────────────────────────────────────────┘
                │
                ▼
        内容保存到 raw/
        如果勾选编译 → 触发 LLM 编译
                │
                ▼
        弹出通知："《AI 时代...》已保存"
```

### 2.2 功能清单

| # | 功能 | MVP | 说明 |
|---|------|-----|------|
| 1 | 提取页面标题 | ✅ | `document.title` |
| 2 | 提取页面 URL | ✅ | `window.location.href` |
| 3 | 提取正文内容 | ✅ | 基于 Readability.js 提取 |
| 4 | 发送到 sagemate | ✅ | POST localhost:8000/api/v1/clip |
| 5 | 显示连接状态 | ✅ | 检查 sagemate 是否运行 |
| 6 | 自动编译开关 | ✅ | 复选框控制 auto_compile |
| 7 | 成功/失败通知 | ✅ | Chrome notification |
| 8 | 右键菜单发送 | ❌ | Phase 2 |
| 9 | 快捷键支持 | ❌ | Phase 2 |
| 10 | 选中文字发送 | ❌ | Phase 2 |

---

## 三、技术架构

```
Chrome Extension (Manifest V3)
├── manifest.json          # 权限声明、入口配置
├── popup.html             # 点击图标弹出的 UI
├── popup.js               # 弹窗逻辑：提取 → 发送
├── content.js             # Content Script：注入页面提取正文
├── background.js          # Service Worker：跨域请求、通知
└── icons/                 # 16x16, 48x48, 128x128 图标

通信流程：
popup.js ──chrome.tabs.executeScript──► content.js（提取正文）
    │                                          │
    │◄─────────返回 {title, url, content}──────┘
    │
    ▼ fetch
background.js ──POST──► sagemate-core:8000/api/v1/clip
    │
    ▼ Chrome notification
显示成功/失败通知
```

### 3.1 为什么用 Content Script 提取？

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| **Content Script** | 能访问页面 DOM、已渲染内容 | 需要注入权限 | ✅ MVP |
| Background fetch URL | 不注入页面 | 从头渲染、可能失败、拿不到登录态 | ❌ |
| Readability.js 在 background | 干净 | 拿不到当前 DOM | ❌ |

**Content Script 能拿到什么：**
- 已渲染完成的 DOM（包括懒加载、JS 动态插入的内容）
- 用户已登录的页面状态（Cookie、LocalStorage）
- 用户展开/折叠的内容（当前可见状态）

### 3.2 正文提取算法（MVP 版）

不使用 Readability.js（减少依赖），用简单的启发式提取：

```javascript
function extractContent() {
  // 1. 尝试找到文章主体（常见 CMS 的 article/main 标签）
  const candidates = [
    document.querySelector('article'),
    document.querySelector('main'),
    document.querySelector('[role="main"]'),
    document.querySelector('.post-content'),
    document.querySelector('.entry-content'),
    document.querySelector('#content'),
  ];
  
  let content = candidates.find(el => el && el.innerText.length > 500);
  
  // 2. 如果没找到，用段落密度算法
  if (!content) {
    content = findLargestTextBlock();
  }
  
  // 3. 清理：移除脚本、样式、导航、广告
  const cleaned = cleanHTML(content);
  
  // 4. 转为 Markdown（简化版）
  return htmlToMarkdown(cleaned);
}
```

---

## 四、后端接口设计

### 4.1 新增 API：`POST /api/v1/clip`

**用途**：接收 Chrome 插件发送的页面内容，保存到 raw/，可选触发编译。

**Request**：
```json
POST /api/v1/clip
Content-Type: application/json

{
  "title": "AI 时代的知识管理方法论",
  "url": "https://mp.weixin.qq.com/s/xxx",
  "content": "提取后的正文 Markdown...",
  "html": "<原始 HTML（可选）>",
  "auto_compile": true,
  "source_type": "browser_clipper"
}
```

**Response**：
```json
{
  "success": true,
  "source_slug": "ai-era-knowledge-management",
  "task_id": "abc123",
  "message": "已保存，正在编译中..."
}
```

**实现逻辑**：
1. 将 content 保存为 `data/raw/articles/{slug}.md`
2. 如果 `auto_compile=true` 且 LLM 已配置 → 触发编译任务
3. 如果 `auto_compile=true` 但 LLM 未配置 → 保存成功，但提示"请配置 LLM 以启用编译"
4. 如果 `auto_compile=false` → 仅保存到 raw/

### 4.2 CORS 配置

Chrome 插件向 `localhost:8000` 发送请求，需要在 sagemate 后端允许 `chrome-extension://*` 来源。

```python
# app.py CORS 配置新增
origins = [
    "http://localhost:5173",  # Vite dev
    "http://localhost:8000",
    "chrome-extension://*",   # Chrome 插件
]
```

---

## 五、文件结构

```
sagemate-core/
├── ...
├── browser-extension/              # ← 新增
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.css
│   ├── popup.js
│   ├── content.js
│   ├── background.js
│   └── icons/
│       ├── icon16.png
│       ├── icon48.png
│       └── icon128.png
```

---

## 六、实施计划

| # | 任务 | 文件 | 预估时间 |
|---|------|------|---------|
| 1 | 后端新增 `/api/v1/clip` | `api/app.py` | 30 min |
| 2 | CORS 允许 chrome-extension | `api/app.py` | 5 min |
| 3 | 创建插件目录结构 | `browser-extension/` | 10 min |
| 4 | manifest.json | `browser-extension/manifest.json` | 10 min |
| 5 | content.js（正文提取） | `browser-extension/content.js` | 30 min |
| 6 | popup.html + css | `browser-extension/popup.html` | 20 min |
| 7 | popup.js（UI 逻辑） | `browser-extension/popup.js` | 30 min |
| 8 | background.js（通知） | `browser-extension/background.js` | 15 min |
| 9 | 测试端到端 | — | 20 min |

**总计：约 3 小时**

---

## 七、Phase 2 扩展（未来）

| 功能 | 说明 |
|------|------|
| 右键菜单 | 右键页面任意位置 → "发送到 SageMate" |
| 快捷键 | Cmd+Shift+S 一键发送 |
| 选中文字 | 选中一段文字 → 右键 → "Ask SageMate" |
| 多页面批量 | 选中多个 Tab → 批量发送 |
| 图片提取 | 提取页面中的图片一并发送 |
| Firefox 支持 | 迁移到 WebExtension API |

---

> **文档版本**: v1.0  
> **编写日期**: 2026-04-25  
> **目标**: MVP 可用，支持 Chrome/Edge（Manifest V3）
