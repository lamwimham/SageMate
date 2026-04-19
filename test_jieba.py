"""Test script for Jieba FTS5 integration"""
import asyncio
import sys
sys.path.insert(0, 'src')
from sagemate.core.store import Store
from sagemate.models import WikiPage, WikiCategory

async def test():
    store = Store("data/sagemate.db")
    await store.connect()
    
    # Check existing pages
    pages = await store.list_pages()
    print(f"📚 Total pages in DB: {len(pages)}")
    
    # Search test
    for kw in ["减肥", "饮食", "learning", "bias"]:
        results = await store.search(kw)
        print(f"🔍 Search '{kw}': {len(results)} results")
        if results:
            for r in results[:2]:
                print(f"  -> {r.title} ({r.slug})")
        else:
            print(f"  -> No results")

    await store.close()

if __name__ == "__main__":
    asyncio.run(test())
