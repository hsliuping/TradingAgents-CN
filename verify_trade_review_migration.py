
import sys
import os
import asyncio
import logging
from typing import Dict, Any, List

# Add project root to path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.services.trade_review_service import TradeReviewService

class TestTradeReviewService(TradeReviewService):
    def __init__(self):
        # Skip DB init
        self.db = None
        pass

async def verify_migration():
    service = TestTradeReviewService()
    
    # Test cases
    test_cases = [
        {"code": "0700.HK", "market": "HK", "name": "Tencent (HK)"},
        {"code": "AAPL", "market": "US", "name": "Apple (US)"},
        {"code": "600519", "market": "CN", "name": "Moutai (CN)"}
    ]
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    for case in test_cases:
        print(f"\nTesting {case['name']}...")
        try:
            klines = await service._fetch_kline_unified(
                code=case['code'],
                market=case['market'],
                start_date=start_date,
                end_date=end_date
            )
            
            if klines:
                print(f"✅ Success: Retrieved {len(klines)} records")
                print("First record:", klines[0])
            else:
                print("❌ Failed: No data returned")
                
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(verify_migration())
