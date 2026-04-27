/**
 * Wiki 页面智能回答 — API 接口规范
 * 
 * 本文档定义前端 Wiki ChatBox 与后端交互的所有接口。
 * 所有接口基于 REST + SSE，返回 JSON。
 */

// ============================================================
// 1. 查询接口 (Query)
// ============================================================

/**
 * POST /query
 * 标准查询 — 同步返回完整答案
 * 
 * Request:
 *   {
 *     "question": "我们项目用了什么架构？",
 *     "save_analysis": false   // 是否将答案保存为 Wiki 分析页面
 *   }
 * 
 * Response (QueryResponse):
 *   {
 *     "answer": "基于知识库分析，项目采用...",
 *     "sources": ["architecture-overview", "tech-stack"],  // 引用的 Wiki 页面 slug 列表
 *     "citations": [                                       // 引用详情（可选）
 *       {"number": 1, "slug": "architecture-overview", "title": "架构概览"}
 *     ],
 *     "related_pages": [                                   // 相关页面元数据
 *       {
 *         "slug": "architecture-overview",
 *         "title": "架构概览",
 *         "category": "concept",
 *         "summary": "项目整体架构设计...",
 *         "updated_at": "2024-01-15T10:30:00",
 *         "word_count": 1200
 *       }
 *     ]
 *   }
 * 
 * Errors:
 *   400: Invalid request body
 *   500: LLM synthesis failed (returns fallback answer with raw search results)
 */

/**
 * POST /query/stream
 * 流式查询 — SSE 逐字返回 LLM 输出
 * 
 * Request: 同 POST /query
 * 
 * Response: Server-Sent Events (SSE)
 *   data: {"type": "sources", "sources": [...]}     // 首先返回搜索结果元数据
 *   data: {"type": "token", "token": "基于"}         // 然后逐 token 返回
 *   data: {"type": "token", "token": "知识库"}
 *   ...
 *   data: {"type": "done", "answer": "完整答案", "references": [...]}  // 最终答案 + 引用
 * 
 * Headers:
 *   Content-Type: text/event-stream
 *   Cache-Control: no-cache
 *   Connection: keep-alive
 *   X-Accel-Buffering: no
 */

// ============================================================
// 2. Agent 聊天接口 (Agent Chat)
// ============================================================

/**
 * POST /agent/chat
 * 统一智能入口 — 支持意图路由、多轮对话、意图澄清
 * 
 * Request:
 *   {
 *     "channel": "web",                    // "web" | "wechat" | "api"
 *     "user_id": "session_abc123",         // 前端会话 ID
 *     "content_type": "text",              // "text" | "image" | "voice" | "file"
 *     "text": "归档这篇文章",               // 用户输入文本
 *     "raw_data": {                       // 扩展数据（可选）
 *       "requires_intent_clarification": false,  // 是否需要意图澄清
 *       "image_path": "",                 // 图片路径（图片类型时）
 *       "file_path": ""                   // 文件路径（文件类型时）
 *     }
 *   }
 * 
 * Response (AgentResponse):
 *   {
 *     "reply_text": "📚 已收到归档请求，正在处理...",
 *     "reply_type": "markdown",            // "markdown" | "simple"
 *     "action_taken": "ingested",          // "queried" | "ingested" | "chatted" | "intent_clarification"
 *     "sources": [{"slug": "...", "title": "..."}],
 *     "suggested_followups": ["查看归档结果", "继续归档"]
 *   }
 * 
 * Special: 当 action_taken = "intent_clarification" 时，
 * reply_text 包含选项列表，前端需要渲染为选项卡片。
 */

// ============================================================
// 3. Wiki 页面接口 (Pages)
// ============================================================

/**
 * GET /pages
 * 列出所有 Wiki 页面
 * 
 * Query Params:
 *   ?category=concept    // 可选过滤: entity | concept | relationship | analysis | source
 * 
 * Response: WikiPage[]
 *   [
 *     {
 *       "slug": "architecture-overview",
 *       "title": "架构概览",
 *       "category": "concept",
 *       "file_path": "/data/wiki/architecture-overview.md",
 *       "summary": "项目整体架构设计...",
 *       "created_at": "2024-01-10T08:00:00",
 *       "updated_at": "2024-01-15T10:30:00",
 *       "word_count": 1200,
 *       "inbound_links": ["tech-stack", "deployment"],
 *       "outbound_links": ["microservices", "event-driven"],
 *       "tags": ["architecture", "design"],
 *       "sources": ["原始设计文档.pdf"]
 *     }
 *   ]
 */

/**
 * GET /pages/{slug}
 * 获取单个页面详情 + 内容
 * 
 * Response:
 *   {
 *     "page": WikiPage,           // 页面元数据
 *     "content": "# 架构概览\n\n..."  // 完整 Markdown 内容
 *   }
 */

/**
 * PUT /pages/{slug}
 * 更新页面内容
 * 
 * Request:
 *   {
 *     "content": "# 新内容\n\n..."   // 完整 Markdown
 *   }
 * 
 * Response:
 *   {
 *     "success": true,
 *     "slug": "architecture-overview",
 *     "message": "Page updated"
 *   }
 */

/**
 * DELETE /pages/{slug}
 * 删除页面
 * 
 * Response:
 *   {
 *     "success": true,
 *     "slug": "architecture-overview",
 *     "message": "Page deleted"
 *   }
 */

// ============================================================
// 4. 搜索接口 (Search)
// ============================================================

/**
 * GET /search?q={query}&category={category}
 * 全文搜索 Wiki 页面
 * 
 * Query Params:
 *   q: 搜索关键词（必填）
 *   category: 可选过滤类别
 * 
 * Response: SearchResult[]
 *   [
 *     {
 *       "slug": "architecture-overview",
 *       "title": "架构概览",
 *       "category": "concept",
 *       "snippet": "...匹配内容高亮片段...",
 *       "score": 0.95
 *     }
 *   ]
 */

// ============================================================
// 5. 索引接口 (Index)
// ============================================================

/**
 * GET /index
 * 获取 Wiki 索引页面
 * 
 * Response:
 *   {
 *     "content": "# 知识库索引\n\n...",   // 索引页面 Markdown
 *     "entries": [                       // 结构化条目列表
 *       {
 *         "slug": "architecture-overview",
 *         "title": "架构概览",
 *         "category": "concept",
 *         "summary": "...",
 *         "last_updated": "2024-01-15T10:30:00",
 *         "source_count": 3,
 *         "inbound_count": 2
 *       }
 *     ]
 *   }
 */

// ============================================================
// 6. 归档/入库接口 (Ingest)
// ============================================================

/**
 * POST /ingest
 * 上传文件/URL/文本进行归档
 * 
 * Request (multipart/form-data):
 *   file: File (可选)           // 上传文件
 *   url: string (可选)          // 网页链接
 *   text: string (可选)        // 纯文本
 *   title: string (可选)       // 自定义标题
 *   auto_compile: boolean = true  // 是否自动编译为 Wiki
 * 
 * Response:
 *   {
 *     "task_id": "ingest_abc123",
 *     "status": "processing",     // "processing" | "completed"
 *     "message": "文件已接收，正在后台编译中",
 *     "result": {                 // status=completed 时有
 *       "source_slug": "architecture-overview",
 *       "wiki_pages_created": 2
 *     }
 *   }
 */

/**
 * GET /ingest/progress/{task_id}
 * SSE 实时获取归档进度
 * 
 * Response: SSE stream
 *   data: {"type": "parsing", "status": "parsing", "step": 1, "total_steps": 5, "message": "正在解析..."}
 *   data: {"type": "calling_llm", "status": "calling_llm", "step": 3, "total_steps": 5, "message": "正在调用 LLM..."}
 *   data: {"type": "completed", "status": "completed", "step": 5, "total_steps": 5, "message": "编译完成"}
 */

/**
 * GET /ingest/result/{task_id}
 * 获取归档最终结果
 * 
 * Response:
 *   {
 *     "status": "completed",      // "completed" | "failed"
 *     "message": "编译完成",
 *     "task_id": "ingest_abc123",
 *     "step": 5,
 *     "total_steps": 5,
 *     "success": true,
 *     "source_slug": "architecture-overview",
 *     "wiki_pages_created": 2,
 *     "wiki_pages_updated": 0,
 *     "wiki_pages": [
 *       {"slug": "architecture-overview", "title": "架构概览"}
 *     ],
 *     "error": null
 *   }
 */

// ============================================================
// 7. 系统接口 (System)
// ============================================================

/**
 * GET /health
 * 健康检查
 * 
 * Response:
 *   {
 *     "status": "ok",
 *     "version": "0.2.0",
 *     "wiki_pages": 42,
 *     "sources": 15,
 *     "ingest_queue": 0
 *   }
 */

/**
 * GET /stats
 * Wiki 统计信息
 * 
 * Response:
 *   {
 *     "total_pages": 42,
 *     "total_sources": 15,
 *     "total_words": 45000,
 *     "categories": {
 *       "entity": 10,
 *       "concept": 20,
 *       "analysis": 8,
 *       "source": 4
 *     }
 *   }
 */

// ============================================================
// 8. 设置接口 (Settings)
// ============================================================

/**
 * GET /api/settings
 * 获取应用设置
 * 
 * Response: AppSettings (见 types/settings.ts)
 */

/**
 * PATCH /api/settings
 * 更新设置
 * 
 * Request: Partial<AppSettings>
 * Response: { "success": true }
 */

/**
 * POST /api/settings/reset
 * 重置设置为默认值
 * 
 * Response: { "success": true }
 */
