"""
QMT 数据源集成测试

测试前置条件：
1. 已安装 xtquant 库
2. MiniQMT 客户端已启动
3. 仅支持 Windows 系统

测试内容：
1. QMT 适配器可用性检查
2. 获取股票列表
3. 获取实时行情
4. 获取 K 线数据
5. QMT 同步服务测试
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_qmt_adapter():
    """测试 QMT 适配器基本功能"""
    print("\n" + "="*60)
    print("🧪 测试 1: QMT 适配器可用性检查")
    print("="*60)
    
    try:
        from app.services.data_sources.qmt_adapter import QMTAdapter
        
        adapter = QMTAdapter()
        is_available = adapter.is_available()
        
        if is_available:
            print("✅ QMT 适配器可用")
            print("   - xtquant 库已安装")
            print("   - MiniQMT 客户端已连接")
        else:
            print("❌ QMT 适配器不可用")
            print("   请检查：")
            print("   1. 是否已安装 xtquant 库")
            print("   2. MiniQMT 客户端是否已启动并登录")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    return True


async def test_get_stock_list():
    """测试获取股票列表"""
    print("\n" + "="*60)
    print("🧪 测试 2: 获取股票列表")
    print("="*60)
    
    try:
        from app.services.data_sources.qmt_adapter import QMTAdapter
        
        adapter = QMTAdapter()
        df = adapter.get_stock_list()
        
        if df is not None and not df.empty:
            print(f"✅ 成功获取 {len(df)} 只股票")
            print(f"\n前 5 只股票：")
            print(df.head().to_string())
            return True
        else:
            print("❌ 未获取到股票列表")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_get_realtime_quotes():
    """测试获取实时行情"""
    print("\n" + "="*60)
    print("🧪 测试 3: 获取实时行情")
    print("="*60)

    try:
        from app.services.data_sources.qmt_adapter import QMTAdapter

        adapter = QMTAdapter()
        quotes = adapter.get_realtime_quotes()

        if quotes:
            print(f"✅ 成功获取 {len(quotes)} 只股票的实时行情")
            # 显示前 5 只
            count = 0
            for code, quote in quotes.items():
                if count >= 5:
                    break
                print(f"\n{code}:")
                print(f"  最新价: {quote.get('close')}")
                print(f"  涨跌幅: {quote.get('pct_chg')}%")
                print(f"  成交额: {quote.get('amount')}")
                count += 1
            return True
        else:
            print("⚠️  未获取到实时行情")
            print("   可能原因：")
            print("   1. 当前非交易时间")
            print("   2. MiniQMT 未连接行情服务器")
            print("   3. 需要在交易时间段测试")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_get_kline():
    """测试获取 K 线数据"""
    print("\n" + "="*60)
    print("🧪 测试 4: 获取 K 线数据")
    print("="*60)
    
    try:
        from app.services.data_sources.qmt_adapter import QMTAdapter
        
        adapter = QMTAdapter()
        # 测试获取平安银行（000001）的日线数据
        kline = adapter.get_kline("000001", period="day", limit=5)
        
        if kline:
            print(f"✅ 成功获取 {len(kline)} 条 K 线数据（000001 平安银行）")
            print("\n最近 5 个交易日：")
            for item in kline:
                print(f"  {item.get('date')}: 开{item.get('open')} 高{item.get('high')} "
                      f"低{item.get('low')} 收{item.get('close')} 量{item.get('volume')}")
            return True
        else:
            print("❌ 未获取到 K 线数据")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n" + "🚀 " + "="*58)
    print("🚀 QMT 数据源集成测试")
    print("🚀 " + "="*58)
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试 1: 可用性检查
    if not await test_qmt_adapter():
        print("\n❌ QMT 不可用，跳过后续测试")
        return
    
    # 测试 2: 获取股票列表
    await test_get_stock_list()
    
    # 测试 3: 获取实时行情
    await test_get_realtime_quotes()
    
    # 测试 4: 获取 K 线数据
    await test_get_kline()
    
    print("\n" + "="*60)
    print("✅ 所有测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

