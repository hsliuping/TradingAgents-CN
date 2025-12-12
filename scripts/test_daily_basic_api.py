"""
测试 Tushare daily_basic API 的数据可用性
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.providers.china.tushare import TushareProvider
from datetime import datetime, timedelta


async def test_daily_basic_dates():
    """测试不同日期的 daily_basic 数据可用性"""
    provider = TushareProvider()
    
    if not provider.is_available():
        print("❌ Tushare Provider 不可用")
        return
    
    print("=" * 80)
    print("📊 测试 daily_basic API 数据可用性")
    print("=" * 80)
    
    # 测试最近5个交易日
    today = datetime.now()
    for i in range(5):
        test_date = today - timedelta(days=i)
        date_str = test_date.strftime('%Y%m%d')
        
        print(f"\n{'='*80}")
        print(f"📅 测试日期: {date_str} ({test_date.strftime('%Y-%m-%d %A')})")
        print(f"{'='*80}")
        
        try:
            df = await asyncio.to_thread(
                provider.api.daily_basic,
                trade_date=date_str,
                fields='ts_code,trade_date,close,pe,pe_ttm,pb,total_mv'
            )
            
            if df is not None and not df.empty:
                print(f"✅ 获取到 {len(df)} 条数据")
                print(f"   前5条数据:")
                print(df.head())
                break  # 找到第一个有数据的日期就停止
            else:
                print(f"⚠️ 无数据")
                
        except Exception as e:
            print(f"❌ API 调用失败: {e}")
    
    print("\n" + "=" * 80)
    print("📊 测试特定股票的 daily_basic 数据")
    print("=" * 80)
    
    # 测试获取万科A的数据
    for i in range(5):
        test_date = today - timedelta(days=i)
        date_str = test_date.strftime('%Y%m%d')
        
        print(f"\n📅 {date_str}: ", end="")
        
        try:
            df = await asyncio.to_thread(
                provider.api.daily_basic,
                ts_code='000002.SZ',
                trade_date=date_str,
                fields='ts_code,trade_date,close,pe,pe_ttm,pb,total_mv'
            )
            
            if df is not None and not df.empty:
                print(f"✅ {len(df)} 条")
                print(f"   {df.to_dict('records')}")
                break
            else:
                print(f"⚠️ 无数据")
                
        except Exception as e:
            print(f"❌ {e}")


if __name__ == "__main__":
    asyncio.run(test_daily_basic_dates())

