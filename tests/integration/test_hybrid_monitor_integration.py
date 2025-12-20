import pytest
import asyncio
from datetime import datetime
from tradingagents.dataflows.hybrid_provider import HybridIndexDataProvider
from tradingagents.dataflows.realtime_monitor import RealtimeMarketMonitor

@pytest.mark.asyncio
async def test_hybrid_provider_integration():
    """Test HybridIndexDataProvider functionality"""
    provider = HybridIndexDataProvider()
    
    # 1. Test Macro Data
    print("\nTesting Macro Data...")
    macro_data = await provider.get_macro_data()
    assert isinstance(macro_data, dict)
    # Note: macro data might be empty if API fails or network issues, but type should be dict
    print(f"Macro Data keys: {list(macro_data.keys())}")
    
    # 2. Test Sector Flows
    print("\nTesting Sector Flows...")
    sector_flows = await provider.get_sector_flows_async()
    assert isinstance(sector_flows, dict)
    if sector_flows:
        assert 'top_sectors' in sector_flows
        assert 'bottom_sectors' in sector_flows
        print(f"Top Sectors count: {len(sector_flows.get('top_sectors', []))}")
    
    # 3. Test News
    print("\nTesting News...")
    news = await provider.get_latest_news_async(limit=5)
    assert isinstance(news, list)
    if news:
        print(f"Got {len(news)} news items")
        print(f"Sample news: {news[0].get('title', 'No Title')}")

@pytest.mark.asyncio
async def test_realtime_monitor_integration():
    """Test RealtimeMarketMonitor functionality"""
    monitor = RealtimeMarketMonitor()
    
    # 1. Test Morning Snapshot
    print("\nTesting Morning Snapshot...")
    morning = await monitor.get_morning_snapshot()
    assert isinstance(morning, dict)
    assert morning['session'] == 'morning'
    assert 'global_market_summary' in morning
    assert 'opening_flow' in morning
    print("Morning Snapshot generated successfully")
    
    # 2. Test Closing Snapshot
    print("\nTesting Closing Snapshot...")
    closing = await monitor.get_closing_snapshot()
    assert isinstance(closing, dict)
    assert closing['session'] == 'closing'
    assert 'sector_flow_summary' in closing
    assert 'policy_alerts' in closing
    print("Closing Snapshot generated successfully")
    
    # 3. Test Market Status
    status = await monitor.get_market_status()
    assert isinstance(status, dict)
    assert 'is_open' in status
    print(f"Market Status: {status}")

if __name__ == "__main__":
    # Allow running directly
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_hybrid_provider_integration())
    loop.run_until_complete(test_realtime_monitor_integration())
