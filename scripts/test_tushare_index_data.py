"""
测试 Tushare 指数数据接口

直接调用 Tushare API 查看返回数据
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.providers.china.tushare import get_tushare_provider


async def test_index_daily():
    """测试 index_daily 接口"""
    print("=" * 80)
    print("📊 测试 index_daily 接口（指数日线行情）")
    print("=" * 80)
    
    provider = get_tushare_provider()
    
    # 测试日期
    today = datetime.now()
    test_dates = [
        today.strftime('%Y%m%d'),  # 今天
        (today - timedelta(days=1)).strftime('%Y%m%d'),  # 昨天
        (today - timedelta(days=2)).strftime('%Y%m%d'),  # 前天
        (today - timedelta(days=3)).strftime('%Y%m%d'),  # 大前天
        '20241210',  # 固定日期
        '20241209',
        '20241206',  # 上周五
    ]
    
    for test_date in test_dates:
        print(f"\n📅 测试日期: {test_date}")
        
        # 测试上证指数
        df = await provider.get_index_daily(
            ts_code='000001.SH',
            start_date=test_date,
            end_date=test_date,
            use_cache=False  # 不使用缓存，直接调用API
        )
        
        if df is not None and not df.empty:
            print(f"✅ 成功获取数据: {len(df)} 条")
            print(f"   数据列: {list(df.columns)}")
            print(f"   数据预览:\n{df.head()}")
            break  # 找到有数据的日期就停止
        else:
            print(f"❌ 无数据")


async def test_index_dailybasic():
    """测试 index_dailybasic 接口"""
    print("\n" + "=" * 80)
    print("📊 测试 index_dailybasic 接口（指数每日指标）")
    print("=" * 80)
    
    provider = get_tushare_provider()
    
    # 测试日期
    today = datetime.now()
    test_dates = [
        today.strftime('%Y%m%d'),
        (today - timedelta(days=1)).strftime('%Y%m%d'),
        (today - timedelta(days=2)).strftime('%Y%m%d'),
        (today - timedelta(days=3)).strftime('%Y%m%d'),
        '20241210',
        '20241209',
        '20241206',
    ]
    
    for test_date in test_dates:
        print(f"\n📅 测试日期: {test_date}")
        
        # 测试上证指数
        df = await provider.get_index_dailybasic(
            ts_code='000001.SH',
            trade_date=test_date,
            use_cache=False
        )
        
        if df is not None and not df.empty:
            print(f"✅ 成功获取数据: {len(df)} 条")
            print(f"   数据列: {list(df.columns)}")
            print(f"   数据预览:\n{df.head()}")
            break
        else:
            print(f"❌ 无数据")


async def test_daily_info():
    """测试 daily_info 接口"""
    print("\n" + "=" * 80)
    print("📊 测试 daily_info 接口（市场交易统计）")
    print("=" * 80)
    
    provider = get_tushare_provider()
    
    # 测试日期
    today = datetime.now()
    test_dates = [
        today.strftime('%Y%m%d'),
        (today - timedelta(days=1)).strftime('%Y%m%d'),
        (today - timedelta(days=2)).strftime('%Y%m%d'),
        (today - timedelta(days=3)).strftime('%Y%m%d'),
        '20241210',
        '20241209',
        '20241206',
    ]
    
    for test_date in test_dates:
        print(f"\n📅 测试日期: {test_date}")
        
        df = await provider.get_daily_info(
            trade_date=test_date,
            use_cache=False
        )
        
        if df is not None and not df.empty:
            print(f"✅ 成功获取数据: {len(df)} 条")
            print(f"   数据列: {list(df.columns)}")
            print(f"   数据预览:\n{df.head()}")
            break
        else:
            print(f"❌ 无数据")


async def test_api_permissions():
    """测试 API 权限和积分"""
    print("\n" + "=" * 80)
    print("🔑 测试 API 权限和积分")
    print("=" * 80)
    
    provider = get_tushare_provider()
    
    if not provider.is_available():
        print("❌ Tushare 不可用")
        return
    
    print("✅ Tushare 已连接")
    print(f"   Token 来源: {provider.token_source}")


async def main():
    """主函数"""
    print("🚀 开始测试 Tushare 指数数据接口\n")
    
    # 测试连接和权限
    await test_api_permissions()
    
    # 测试各个接口
    await test_index_daily()
    await test_index_dailybasic()
    await test_daily_info()
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

