# ChatBox 数据格式规范

## 设计目标

1. **类型安全**: 所有消息内容用 discriminated union，前端可 pattern-match
2. **不可变性**: ChatMessage 不可变，更新 = 创建新实例
3. **状态机**: SessionState 显式定义，非法转换在代码层面被拒绝
4. **可追踪**: 每条消息有完整元数据（处理时间、token消耗、原始数据）

## 核心类型

### ChatMessage — 统一消息

```python
class ChatMessage(BaseModel):
    id: str                    # UUID
    session_id: str            # "wechat:{user_id}" 或 "web:{session_id}"
    channel: str               # "wechat", "web", "api"
    direction: MessageDirection  # INBOUND | OUTBOUND | SYSTEM
    status: MessageStatus        # PENDING → SENT → DELIVERED → READ | FAILED
    content: ChatContent         # 见下方 Union
    created_at: str              # ISO-8601
    reply_to_id: Optional[str]   # 线程回复
    correlation_id: Optional[str]  # 请求-响应关联
    metadata: MessageMetadata    # 处理痕迹、原始数据、成本
```

### ChatContent — 内容 Union

| 类型 | content_type | 用途 |
|------|-------------|------|
| TextContent | "text" | 普通文本/Markdown |
| ImageContent | "image" | 图片（带路径、尺寸、caption） |
| VoiceContent | "voice" | 语音（转录后） |
| FileContent | "file" | 文件附件 |
| URLContent | "url" | URL 预览卡片 |
| IntentClarificationContent | "intent_clarification" | **意图澄清卡片** |
| IntentConfirmationContent | "intent_confirmation" | **二次确认卡片** |
| ProgressContent | "progress" | 异步任务进度 |
| ErrorContent | "error" | 错误消息 |
| SystemContent | "system" | 系统事件 |

### 意图澄清 (IntentClarificationContent)

```python
class IntentClarificationContent(BaseModel):
    content_type: Literal["intent_clarification"]
    question: str                    # "我收到了一张图片，你想让我做什么？"
    options: list[IntentOption]      # 选项列表
    timeout_seconds: int = 300       # 超时自动取消
    context_data: dict               # 透传数据（如 image_path）

class IntentOption(BaseModel):
    id: str                          # "ingest", "ocr", "describe", "ignore"
    label: str                       # "归档入库"
    description: str = ""            # 副标题
    icon: str = ""                   # 图标/emoji
    primary: bool = False            # 是否推荐选项
```

### 会话状态机 (SessionState)

```
IDLE ──[收到图片]──▶ AWAITING_INTENT
  │                      │
  │                      ├──[用户选择]──▶ PROCESSING ──[完成]──▶ IDLE
  │                      │
  │                      └──[超时/取消]──▶ IDLE
  │
  └──[普通消息]──▶ PROCESSING ──[完成]──▶ IDLE
```

## 使用示例

### 创建意图澄清消息

```python
from sagemate.core.chat import ChatMessage, IntentClarificationContent, IntentOption, MessageDirection

msg = ChatMessage(
    id="msg-001",
    session_id="wechat:user_123",
    channel="wechat",
    direction=MessageDirection.OUTBOUND,
    content=IntentClarificationContent(
        question="我收到了一张图片，你想让我做什么？",
        options=[
            IntentOption(id="ingest", label="归档入库", description="提取文字并编译为 Wiki", primary=True),
            IntentOption(id="ocr", label="识别文字", description="只提取文字内容"),
            IntentOption(id="describe", label="描述图片", description="描述图片内容"),
            IntentOption(id="ignore", label="忽略", description="不处理这张图片"),
        ],
        context_data={"image_path": "/data/raw/images/img_123.png"},
    ),
)
```

### Pattern Matching (Python 3.10+)

```python
match msg.content:
    case TextContent(text=t):
        render_markdown(t)
    case IntentClarificationContent(question=q, options=opts):
        render_option_card(question, opts)
    case ImageContent(image_path=path, caption=caption):
        render_image(path, caption)
    case _:
        render_fallback(msg.content)
```

## 前端渲染指南

| Content Type | Web 渲染 | WeChat 渲染 |
|-------------|---------|------------|
| text | Markdown + 代码高亮 | 纯文本 |
| image | `<img>` 标签 | 图片消息 |
| intent_clarification | 卡片 + 按钮组 | 文本 + 编号选项 |
| intent_confirmation | 确认弹窗/卡片 | 文本 + 确认/取消 |
| progress | 进度条 | 文本状态更新 |
| error | 错误提示卡片 | 文本 + 重试提示 |
| system | 系统通知横幅 | 灰色小字 |
