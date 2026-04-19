import asyncio
import sys
sys.path.insert(0, 'src')
from sagemate.pipeline.url_collector import URLCollector

async def test():
    url = "https://modelcontextprotocol.io/docs/getting-started/intro"
    print(f"🚀 Testing URL Collector: {url}")
    result = await URLCollector.collect(url)
    
    if result.success:
        print(f"✅ Success!")
        print(f"Title: {result.title}")
        print(f"Content Length: {len(result.content)} chars")
        print(f"First 200 chars: {result.content[:200]}...")
    else:
        print(f"❌ Failed: {result.error}")

if __name__ == "__main__":
    asyncio.run(test())
