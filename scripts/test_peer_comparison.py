"""
测试同业对比数据获取
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.providers.china.tushare import get_tushare_provider


async def test_peer_comparison():
    """测试同业对比数据获取"""
    provider = get_tushare_provider()
    
    # 测试1: 获取全国地产行业股票列表
    print("=" * 80)
    print("📊 测试1: 获取全国地产行业股票列表")
    print("=" * 80)
    
    stocks_df = await provider.get_industry_stocks("全国地产")
    if stocks_df is not None and not stocks_df.empty:
        print(f"✅ 找到 {len(stocks_df)} 只股票")
        print(f"\n前10只股票:")
        print(stocks_df.head(10)[['ts_code', 'name', 'industry']])
    else:
        print(f"❌ 未找到股票")
        return
    
    # 测试2: 获取全国地产行业的每日指标
    print(f"\n{'='*80}")
    print(f"📊 测试2: 获取全国地产行业的每日指标 (2025-12-10)")
    print('='*80)
    
    daily_basic_df = await provider.get_sector_stocks_daily_basic(
        industry="全国地产",
        trade_date="20251210"
    )
    
    if daily_basic_df is not None and not daily_basic_df.empty:
        print(f"✅ 获取到 {len(daily_basic_df)} 只股票的数据")
        print(f"\n前10只股票:")
        print(daily_basic_df.head(10)[['ts_code', 'name', 'total_mv', 'pe_ttm', 'pb', 'turnover_rate']])
        
        # 检查万科A的数据
        print(f"\n{'='*80}")
        print(f"📊 万科A (000002.SZ) 的数据:")
        print('='*80)
        wanke = daily_basic_df[daily_basic_df['ts_code'] == '000002.SZ']
        if not wanke.empty:
            print(wanke[['ts_code', 'name', 'total_mv', 'pe_ttm', 'pb', 'turnover_rate']])
        else:
            print("❌ 未找到万科A的数据")
    else:
        print(f"❌ 未获取到数据")
    
    # 测试3: 直接调用 daily_basic API
    print(f"\n{'='*80}")
    print(f"📊 测试3: 直接调用 daily_basic API (2025-12-10)")
    print('='*80)
    
    daily_df = await asyncio.to_thread(
        provider.api.daily_basic,
        trade_date='20251210',
        fields='ts_code,trade_date,close,pe,pe_ttm,pb,ps,total_mv,circ_mv,turnover_rate'
    )
    
    if daily_df is not None and not daily_df.empty:
        print(f"✅ 获取到 {len(daily_df)} 只股票的数据")
        
        # 筛选全国地产行业的股票
        industry_codes = set(stocks_df['ts_code'].tolist())
        result_df = daily_df[daily_df['ts_code'].isin(industry_codes)]
        
        print(f"✅ 全国地产行业有 {len(result_df)} 只股票有数据")
        print(f"\n前10只股票:")
        print(result_df.head(10)[['ts_code', 'total_mv', 'pe_ttm', 'pb', 'turnover_rate']])
        
        # 检查万科A
        wanke = result_df[result_df['ts_code'] == '000002.SZ']
        if not wanke.empty:
            print(f"\n万科A的数据:")
            print(wanke[['ts_code', 'total_mv', 'pe_ttm', 'pb', 'turnover_rate']])
        else:
            print(f"\n❌ 万科A没有数据")
    else:
        print(f"❌ 未获取到数据")


async def main():
    """主函数"""
    await test_peer_comparison()
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

