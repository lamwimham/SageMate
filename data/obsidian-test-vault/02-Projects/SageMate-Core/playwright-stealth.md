---
title: playwright-stealth
category: concept
tags: [sagemate, scraping, anti-detection, browser]
created: 2026-04-21
---

# playwright-stealth

## What

Library that patches Playwright browser fingerprints to evade bot detection.

## Why We Need It

WeChat articles (`mp.weixin.qq.com`) detect automation and return "环境异常" verification pages. Standard Playwright is blocked.

## Integration

```python
from playwright_stealth import Stealth

self._stealth = Stealth(
    navigator_languages_override=("zh-CN", "zh", "en"),
    navigator_platform_override="MacIntel",
    navigator_user_agent_override=settings.user_agent,
    navigator_vendor_override="Google Inc.",
    webgl_vendor_override="Apple Inc.",
    webgl_renderer_override="Apple M1",
    chrome_runtime=True,  # Critical!
)
await self._stealth.apply_stealth_async(context)
```

## Lessons Learned

1. **Don't manually set `Sec-Ch-Ua-Mobile`** — conflicts with stealth patches
2. **Apply to `context`**, not just `page` — covers all pages in context
3. **Launch args matter** — `--disable-blink-features=AutomationControlled` is baseline

## Test Results

| URL | Before | After |
|-----|--------|-------|
| WeChat article | 34KB (blocked) | 3.9MB (full content) |
| `#js_content` found | ❌ | ✅ |

---
#sagemate #scraping
