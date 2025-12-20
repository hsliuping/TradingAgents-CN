
from tradingagents.tools.index_tools import fetch_multi_source_news
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_tool():
    print("Testing fetch_multi_source_news tool...")
    
    # Clear cache to force fresh fetch with new logic
    from tradingagents.dataflows.index_data import get_index_data_provider
    from datetime import datetime
    
    provider = get_index_data_provider()
    if provider.cache is not None:
        cache_key = f"multi_source_news_raw_{datetime.now().strftime('%Y%m%d_%H')}"
        provider.cache.index_cache.delete_one({"cache_key": cache_key})
        print(f"Cleared cache for key: {cache_key}")
    
    # 1. Test without keywords (General rolling news)
    print("\n--- Testing General Rolling News ---")
    try:
        result = fetch_multi_source_news.invoke({"keywords": "", "lookback_days": 1})
        print(result[:500] + "..." if len(result) > 500 else result)
    except Exception as e:
        print(f"Error: {e}")

    # 2. Test with keywords (e.g., "A股" or "美股" or "半导体")
    print("\n--- Testing Keyword '美股' ---")
    try:
        result = fetch_multi_source_news.invoke({"keywords": "美股", "lookback_days": 1})
        print(result[:500] + "..." if len(result) > 500 else result)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_tool()
