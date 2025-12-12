"""
测试 daily_info 接口返回的完整数据结构
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.providers.china.tushare import get_tushare_provider


async def test_daily_info_structure():
    """测试 daily_info 接口的数据结构"""
    print("=" * 80)
    print("📊 测试 daily_info 接口数据结构")
    print("=" * 80)
    
    provider = get_tushare_provider()
    
    # 使用最近的交易日
    trade_date = '20241210'
    
    print(f"\n📅 查询日期: {trade_date}")
    
    # 获取数据
    df = await provider.get_daily_info(
        trade_date=trade_date,
        use_cache=False
    )
    
    if df is not None and not df.empty:
        print(f"\n✅ 成功获取数据: {len(df)} 条")
        print(f"\n📋 所有列名:")
        for i, col in enumerate(df.columns, 1):
            print(f"   {i:2d}. {col}")
        
        print(f"\n📊 完整数据:")
        print(df.to_string())
        
        print(f"\n🔍 检查关键字段:")
        key_fields = ['up_count', 'down_count', 'amount', 'vol', 'com_count']
        for field in key_fields:
            if field in df.columns:
                print(f"   ✅ {field}: 存在")
                print(f"      示例值: {df[field].iloc[0] if len(df) > 0 else 'N/A'}")
            else:
                print(f"   ❌ {field}: 不存在")
    else:
        print("❌ 无数据")


async def main():
    """主函数"""
    await test_daily_info_structure()
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

