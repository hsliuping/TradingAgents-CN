"""
测试市场宽度分析功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.tools.index_tools import get_market_breadth


async def test_market_breadth():
    """测试市场宽度分析"""
    print("=" * 80)
    print("📊 测试市场宽度分析")
    print("=" * 80)
    
    # 测试不同的日期
    test_dates = [
        "2025-12-11",  # 今天（会自动调整）
        "2025-12-10",  # 昨天
        "2024-12-10",  # 去年同期
    ]
    
    for test_date in test_dates:
        print(f"\n{'='*80}")
        print(f"📅 测试日期: {test_date}")
        print('='*80)
        
        try:
            report = await get_market_breadth(test_date)
            print(report)
            
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """主函数"""
    await test_market_breadth()
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

