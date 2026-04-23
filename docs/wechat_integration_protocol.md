# WeChat Integration Protocol for SageMate Core

## 1. 概述
本文档定义了 SageMate Core 与微信 (WeChat) 平台的对接协议，基于微信 **iLink Bot API**。该协议支持双向消息交互，允许 SageMate Core 作为一个“智能助手”接入用户的微信生态。

## 2. 架构概览
SageMate Core 通过 **插件 (Plugin)** 方式实现微信接入。核心引擎不直接处理网络请求，而是通过 **Channel Adapter** 模式将微信消息转换为 SageMate 内部的标准格式 (`IngestRequest`)。

```
[微信用户] <--> [微信 iLink API] <--> [SageMate WeChat Plugin] <--> [SageMate Core Engine]
```

## 3. 核心协议 (iLink API)
所有 API 均基于 HTTPS POST/GET 请求，默认 Base URL 为 `https://ilinkai.weixin.qq.com`。

### 3.1 鉴权机制
*   **Token**: 使用 Bearer Token 进行鉴权，Token 通过扫码登录获取。
*   **Header**: 
    *   `Authorization`: `Bearer {token}`
    *   `AuthorizationType`: `ilink_bot_token`
    *   `Content-Type`: `application/json`

### 3.2 登录流程
1.  **获取二维码**: `GET /ilink/bot/get_bot_qrcode?bot_type=3`
2.  **轮询状态**: `GET /ilink/bot/get_qrcode_status?qrcode={qrcode}`
    *   状态: `wait` (等待扫码) -> `scaned` (已扫码) -> `confirmed` (已登录)
3.  **成功**: 返回 `bot_token`, `ilink_user_id` 和 `base_url`。

### 3.3 消息接收 (长轮询)
*   **Endpoint**: `POST /ilink/bot/getupdates`
*   **机制**: 客户端发送包含上一次 `get_updates_buf` 的请求，服务端保持连接直到有新消息或超时 (默认 35s)。
*   **响应结构**:
    ```json
    {
      "ret": 0,
      "msgs": [
        {
          "message_id": 12345,
          "from_user_id": "wxid_xxx",
          "item_list": [
            { "type": 1, "text_item": { "text": "用户发送的内容" } },
            { "type": 3, "voice_item": { ... } }
          ]
        }
      ],
      "get_updates_buf": "next_buffer_string"
    }
    ```

### 3.4 消息发送
*   **Endpoint**: `POST /ilink/bot/sendmessage`
*   **请求结构**:
    ```json
    {
      "msg": {
        "to_user_id": "wxid_xxx",
        "item_list": [
          { "type": 1, "text_item": { "text": "SageMate 回复的内容" } }
        ]
      },
      "base_info": { "channel_version": "sagemate-wechat-1.0.0" }
    }
    ```

## 4. 数据类型映射
微信消息类型 (`type`) 与 SageMate 内部类型的映射关系：

| 微信 Type | 含义 | SageMate 处理逻辑 |
| :--- | :--- | :--- |
| `1` | **文本 (Text)** | 直接提取 `text_item.text` 作为用户输入。 |
| `3` | **语音 (Voice)** | 调用 CDN 接口下载语音文件 -> Whisper 本地转写 -> 提取文本输入 SageMate。 |
| `2` | **图片 (Image)** | 下载图片 -> 保存至 `data/raw/assets/` -> 生成引用 Markdown。 |
| `4` | **文件 (File)** | 下载文件 -> 根据后缀调用对应的 Parser (如 PDF, Docx) -> 送入编译器。 |

## 5. SageMate 集成方案 (Plugin 设计)

### 5.1 目录结构
```
sagemate-core/plugins/wechat/
├── __init__.py
├── channel.py          # 消息收发主循环 (Long-polling)
├── api.py              # WechatApiClient 封装
├── media_handler.py    # CDN 媒体下载 (图片/语音/文件)
└── parser_adapter.py   # 将微信消息转换为 SageMate Ingest 格式
```

### 5.2 消息流转流程
1.  **Listen**: `channel.py` 启动长轮询任务。
2.  **Receive**: 收到 `msgs` 列表，过滤非文本消息（如系统通知）。
3.  **Dispatch**:
    *   如果是 **文本**: 提取内容。
    *   如果是 **语音/文件/图片**: 调用 `media_handler.py` 异步下载。
4.  **Ingest**: 将内容封装为 Markdown 格式，调用 SageMate Core 的 `Compiler`。
    *   语音消息将被自动转写并标记为 `#voice_note`。
    *   文件消息将被解析为结构化知识。
5.  **Reply**: 获取编译器输出，通过 `sendmessage` 接口回复用户。

### 5.3 配置文件
```yaml
wechat:
  enabled: true
  account_id: "default"
  bot_prefix: "@"
  policies:
    dm_policy: "open"
    group_policy: "mention_only"
```

## 6. 安全与隐私
*   **本地化**: 所有媒体文件（语音、图片、文档）均在本地处理，不经过第三方。
*   **Token 管理**: `bot_token` 仅在本地 `data/wechat/tokens/` 目录下加密存储。
*   **白名单**: 支持通过 `WECHAT_ALLOW_FROM` 环境变量限制允许交互的用户 ID。

## 7. 下一步实施计划
1.  **API 封装**: 将 `Copaw` 中的 `api.py` 和 `types.py` 移植到 SageMate 插件目录。
2.  **登录 CLI**: 实现 `sagemate wechat login` 命令，支持终端展示二维码。
3.  **消息桥接**: 实现 `WechatChannel` 类，负责消息的收发与 SageMate Core 的 API 调用。
4.  **语音转写集成**: 将 Whisper 引擎接入语音消息处理流。
