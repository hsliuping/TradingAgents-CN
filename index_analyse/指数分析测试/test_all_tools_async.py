import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tradingagents.tools.index_tools import (
    fetch_policy_news, 
    fetch_sector_news, 
    fetch_multi_source_news,
    fetch_sector_rotation
)
from tradingagents.tools.international_news_tools import (
    fetch_bloomberg_news,
    fetch_cn_international_news
)

async def test_tools():
    print("🚀 Starting Async Tools Test...")
    
    # 1. Test Policy News
    print("\n📰 Testing fetch_policy_news...")
    try:
        # Check if it's a StructuredTool and use invoke/ainvoke
        if hasattr(fetch_policy_news, 'ainvoke'):
            res = await fetch_policy_news.ainvoke({"lookback_days": 3})
        else:
            res = await fetch_policy_news(lookback_days=3)
        print(f"✅ Policy News Result: {res[:100]}...")
    except Exception as e:
        print(f"❌ Policy News Failed: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test Sector News
    print("\n🏭 Testing fetch_sector_news (Semiconductor)...")
    try:
        if hasattr(fetch_sector_news, 'ainvoke'):
            res = await fetch_sector_news.ainvoke({"sector_name": "半导体", "lookback_days": 3})
        else:
            res = await fetch_sector_news(sector_name="半导体", lookback_days=3)
        print(f"✅ Sector News Result: {res[:100]}...")
    except Exception as e:
        print(f"❌ Sector News Failed: {e}")

    # 3. Test CN International News
    print("\n🌍 Testing fetch_cn_international_news (US Market)...")
    try:
        if hasattr(fetch_cn_international_news, 'ainvoke'):
            res = await fetch_cn_international_news.ainvoke({"keywords": "美股", "lookback_days": 3})
        else:
            res = await fetch_cn_international_news(keywords="美股", lookback_days=3)
        print(f"✅ CN Intl News Result: {res[:100]}...")
    except Exception as e:
        print(f"❌ CN Intl News Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_tools())
