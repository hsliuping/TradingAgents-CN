
import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from tradingagents.dataflows.interface import get_hk_stock_data_unified
from tradingagents.dataflows.providers.hk.improved_hk import get_improved_hk_provider

def verify_hk_unified():
    symbol = "0700.HK"
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    print(f"Testing get_hk_stock_data_unified for {symbol}...")
    try:
        result = get_hk_stock_data_unified(symbol, start_date, end_date)
        print("\nResult snippet:")
        print(result[:500])
        
        if "❌" in result:
            print("\n❌ Verification Failed: Error in result")
        else:
            print("\n✅ Verification Passed: Data returned successfully")
            
    except Exception as e:
        print(f"\n❌ Verification Failed: Exception occurred: {e}")

def verify_provider_direct():
    symbol = "0700.HK"
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    print(f"\nTesting improved_hk_provider.get_daily_data for {symbol}...")
    try:
        provider = get_improved_hk_provider()
        df = provider.get_daily_data(symbol, start_date, end_date)
        
        if df is not None and not df.empty:
            print(f"✅ Provider returned DataFrame with shape: {df.shape}")
            print("Columns:", df.columns.tolist())
            print("Head:\n", df.head())
        else:
            print("❌ Provider returned empty or None")
            
    except Exception as e:
        print(f"❌ Provider test failed: {e}")

if __name__ == "__main__":
    verify_provider_direct()
    verify_hk_unified()
