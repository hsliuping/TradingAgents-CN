"""
测试行业数据获取
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.providers.china.tushare import get_tushare_provider


async def test_industry_data():
    """测试行业数据获取"""
    provider = get_tushare_provider()
    
    # 测试1: 获取万科A的行业信息
    print("=" * 80)
    print("📊 测试1: 获取万科A (000002.SZ) 的行业信息")
    print("=" * 80)
    
    industry = await provider.get_stock_industry("000002.SZ")
    print(f"行业名称: {industry}")
    
    # 测试2: 尝试获取该行业的股票列表
    print(f"\n{'='*80}")
    print(f"📊 测试2: 获取 '{industry}' 行业的股票列表")
    print('='*80)
    
    stocks_df = await provider.get_industry_stocks(industry)
    if stocks_df is not None and not stocks_df.empty:
        print(f"✅ 找到 {len(stocks_df)} 只股票")
        print(f"\n前10只股票:")
        print(stocks_df.head(10)[['ts_code', 'name', 'industry']])
    else:
        print(f"❌ 未找到股票")
    
    # 测试3: 尝试不同的行业名称
    print(f"\n{'='*80}")
    print(f"📊 测试3: 尝试其他可能的行业名称")
    print('='*80)
    
    possible_names = ["全国地产", "房地产", "地产", "房地产开发", "全国性地产"]
    for name in possible_names:
        stocks_df = await provider.get_industry_stocks(name)
        if stocks_df is not None and not stocks_df.empty:
            print(f"✅ '{name}': 找到 {len(stocks_df)} 只股票")
        else:
            print(f"❌ '{name}': 未找到股票")
    
    # 测试4: 获取所有股票，看看有哪些行业
    print(f"\n{'='*80}")
    print(f"📊 测试4: 查看所有行业分类")
    print('='*80)
    
    all_stocks = await asyncio.to_thread(
        provider.api.stock_basic,
        list_status='L',
        fields='ts_code,name,industry'
    )
    
    if all_stocks is not None and not all_stocks.empty:
        industries = all_stocks['industry'].unique()
        print(f"✅ 共有 {len(industries)} 个行业分类")
        print(f"\n包含'地产'的行业:")
        real_estate_industries = [ind for ind in industries if '地产' in str(ind)]
        for ind in real_estate_industries:
            count = len(all_stocks[all_stocks['industry'] == ind])
            print(f"  - {ind}: {count} 只股票")
    
    # 测试5: 获取万科A的每日指标
    print(f"\n{'='*80}")
    print(f"📊 测试5: 获取万科A的每日指标")
    print('='*80)
    
    daily_basic = await asyncio.to_thread(
        provider.api.daily_basic,
        ts_code='000002.SZ',
        trade_date='20251210',
        fields='ts_code,trade_date,close,pe,pe_ttm,pb,ps,total_mv,circ_mv,turnover_rate'
    )
    
    if daily_basic is not None and not daily_basic.empty:
        print(f"✅ 获取到数据:")
        print(daily_basic)
    else:
        print(f"❌ 未获取到数据")


async def main():
    """主函数"""
    await test_industry_data()
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

