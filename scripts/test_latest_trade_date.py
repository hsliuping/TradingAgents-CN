"""
测试获取最新交易日的逻辑
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.tools.index_tools import _get_latest_trade_date


async def test_latest_trade_date():
    """测试获取最新交易日"""
    print("=" * 80)
    print("📅 测试获取最新交易日逻辑")
    print("=" * 80)
    
    # 测试不同的日期
    test_cases = [
        ("2025-12-11", "今天（可能是非交易日）"),
        ("2025-12-10", "昨天"),
        ("2025-12-08", "上周日"),
        ("2025-12-07", "上周六"),
        ("2025-12-06", "上周五"),
        ("2024-12-10", "去年同期"),
    ]
    
    for test_date, description in test_cases:
        print(f"\n📊 测试日期: {test_date} ({description})")
        
        try:
            latest_date = await _get_latest_trade_date(test_date)
            
            # 格式化显示
            formatted_date = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:8]}"
            
            if latest_date == test_date.replace('-', ''):
                print(f"   ✅ 使用原始日期: {formatted_date}")
            else:
                print(f"   📅 自动调整为最近交易日: {formatted_date}")
                
        except Exception as e:
            print(f"   ❌ 错误: {e}")


async def main():
    """主函数"""
    await test_latest_trade_date()
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

