"""Test script for inserting and searching Chinese content"""
import asyncio
import sys
sys.path.insert(0, 'src')
from sagemate.core.store import Store
from sagemate.models import WikiPage, WikiCategory

async def test():
    store = Store("data/sagemate.db")
    await store.connect()
    
    content = """
---
title: 健康饮食规划
slug: healthy-diet-plan
---

# 健康饮食规划

想要减肥，首先需要控制饮食。建议每天摄入足够的蔬菜、水果和优质蛋白质。
减少糖分和碳水化合物的摄入，保持水分充足。

## 具体建议
1. 早餐吃好，午餐吃饱，晚餐吃少。
2. 多喝水，少喝含糖饮料。
"""
    page = WikiPage(
        slug="healthy-diet-plan",
        title="健康饮食规划",
        category=WikiCategory.CONCEPT,
        file_path="/tmp/test_chinese.md",
        summary="关于减肥和饮食规划的建议"
    )
    
    # Insert
    await store.upsert_page(page, content)
    print("✅ Inserted Chinese page: 健康饮食规划")
    
    # Search tests
    for kw in ["减肥", "饮食", "规划", "糖分"]:
        results = await store.search(kw)
        print(f"🔍 Search '{kw}': {len(results)} results")
        if results:
            for r in results:
                print(f"  -> {r.title} ({r.slug})")

    await store.close()

if __name__ == "__main__":
    asyncio.run(test())
