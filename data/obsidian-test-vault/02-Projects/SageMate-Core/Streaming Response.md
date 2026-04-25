---
title: Streaming Response
category: concept
tags: [sagemate, sse, streaming, backend]
created: 2026-04-15
---

# Streaming Response

## Problem

Non-streaming LLM responses feel slow. TTFT (Time To First Token) can be 3-8 seconds. Users think the system is frozen.

## Solution

SSE (Server-Sent Events) with token-by-token delivery.

### Event Types

| Event | Description |
|-------|-------------|
| `status` | `retrieving` → `generating` |
| `thinking` | Reasoning content (DeepSeek) |
| `token` | Regular content token |
| `sources` | Related wiki pages |
| `done` | Final answer + metadata |

### Backend

```python
async def event_generator():
    async for event in agent_pipeline.process_stream(msg):
        yield f"data: {json.dumps(event)}\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Frontend

```typescript
for await (const event of chatRepo.chatStream(payload)) {
  if (event.type === 'thinking') appendThinking(event.token)
  if (event.type === 'token') appendContent(event.token)
}
```

## DeepSeek Reasoning

DeepSeek v4 Flash outputs ~50-80 reasoning tokens before content. We show these in a collapsible "思考过程" section.

TTFT breakdown:
- Reasoning: ~0.6-1.0s
- Content: ~1.8-3.8s

## Issues Solved

- [[Thinking Events Missing]] — server restart problem
- [[SSE Proxy Buffering]] — Vite dev proxy fix

---
#sagemate #sse
