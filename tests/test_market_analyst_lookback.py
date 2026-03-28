#!/usr/bin/env python3
"""
测试脚本：验证 MARKET_ANALYST_LOOKBACK_DAYS 配置是否生效

功能：
1. 读取配置文件中的 MARKET_ANALYST_LOOKBACK_DAYS 值
2. 模拟市场分析师调用数据接口
3. 验证实际获取的数据天数是否符合配置
4. 输出详细的验证报告

使用方法：
    python scripts/validation/test_market_analyst_lookback.py
"""

import os
import sys
from datetime import datetime, timedelta

import pytest

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from tradingagents.utils.logging_manager import get_logger

logger = get_logger('test')


@pytest.fixture()
def lookback_days() -> int:
    """读取当前配置中的市场分析回溯天数。"""
    from app.core.config import get_settings

    settings = get_settings()
    return settings.MARKET_ANALYST_LOOKBACK_DAYS


@pytest.fixture()
def date_range(lookback_days: int):
    """根据当前配置生成统一的日期范围。"""
    from tradingagents.utils.dataflow_utils import get_trading_date_range

    target_date = datetime.now().strftime("%Y-%m-%d")
    start_date, end_date = get_trading_date_range(target_date, lookback_days=lookback_days)
    actual_days = (
        datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")
    ).days
    return start_date, end_date, actual_days


def test_config_loading(lookback_days: int):
    """测试1：验证配置加载"""
    print("\n" + "=" * 80)
    print("测试1：验证配置加载")
    print("=" * 80)
    
    try:
        print(f"✅ 配置加载成功")
        print(f"📅 MARKET_ANALYST_LOOKBACK_DAYS = {lookback_days}天")
        assert isinstance(lookback_days, int)
        assert lookback_days > 0
        
        # 验证配置值
        if lookback_days == 250:
            print(f"✅ 配置值正确：250天（专业配置）")
        elif lookback_days == 120:
            print(f"⚠️  配置值：120天（标准配置）")
        elif lookback_days == 60:
            print(f"⚠️  配置值：60天（最小配置）")
        else:
            print(f"⚠️  配置值：{lookback_days}天（自定义配置）")
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        raise


def test_date_range_calculation(lookback_days: int, date_range):
    """测试2：验证日期范围计算"""
    print("\n" + "=" * 80)
    print("测试2：验证日期范围计算")
    print("=" * 80)
    
    try:
        # 使用今天作为目标日期
        target_date = datetime.now().strftime("%Y-%m-%d")
        start_date, end_date, actual_days = date_range
        
        print(f"✅ 日期范围计算成功")
        print(f"📅 目标日期: {target_date}")
        print(f"📅 配置回溯: {lookback_days}天")
        print(f"📅 开始日期: {start_date}")
        print(f"📅 结束日期: {end_date}")
        print(f"📅 实际天数: {actual_days}天")
        
        # 验证实际天数是否符合预期
        assert actual_days == lookback_days
        if actual_days >= lookback_days:
            print(f"✅ 实际天数 ({actual_days}) >= 配置天数 ({lookback_days})")
        else:
            print(f"⚠️  实际天数 ({actual_days}) < 配置天数 ({lookback_days})")
    except Exception as e:
        print(f"❌ 日期范围计算失败: {e}")
        raise


@pytest.mark.integration
def test_data_fetching(date_range):
    """测试3：验证数据获取"""
    print("\n" + "=" * 80)
    print("测试3：验证数据获取（模拟市场分析师调用）")
    print("=" * 80)
    
    try:
        from tradingagents.dataflows.interface import get_china_stock_data_unified
        start_date, end_date, _ = date_range
        
        # 使用一个常见的A股股票代码进行测试
        test_ticker = "300750"  # 平安银行
        
        print(f"📊 测试股票: {test_ticker}")
        print(f"📅 日期范围: {start_date} 至 {end_date}")
        print(f"⏳ 正在获取数据...")
        
        # 调用统一接口获取数据
        result = get_china_stock_data_unified(
            ticker=test_ticker,
            start_date=start_date,
            end_date=end_date
        )
        
        # 检查结果
        if result and not result.startswith("❌"):
            print(f"✅ 数据获取成功")
            print(f"📊 返回数据长度: {len(result)} 字符")
            
            # 检查是否包含技术指标
            indicators = ["MA5", "MA10", "MA20", "MA60", "MACD", "RSI", "BOLL"]
            found_indicators = [ind for ind in indicators if ind in result]
            
            print(f"📈 包含技术指标: {', '.join(found_indicators)}")
            
            if len(found_indicators) == len(indicators):
                print(f"✅ 所有技术指标都已计算")
            else:
                missing = set(indicators) - set(found_indicators)
                print(f"⚠️  缺少技术指标: {', '.join(missing)}")
            
            # 显示部分结果（前1000字符）
            print(f"\n📄 数据预览（前1000字符）:")
            print("-" * 80)
            print(result[:1000])
            print("-" * 80)

            # 显示最后500字符
            print(f"\n📄 数据预览（最后500字符）:")
            print("-" * 80)
            print(result[-500:])
            print("-" * 80)
            
            assert len(found_indicators) >= 1
        else:
            pytest.fail(f"数据获取失败: {result}")
    except Exception as e:
        print(f"❌ 数据获取异常: {e}")
        raise


def test_technical_indicators_accuracy(lookback_days: int):
    """测试4：验证技术指标准确性要求"""
    print("\n" + "=" * 80)
    print("测试4：验证技术指标准确性要求")
    print("=" * 80)
    
    # 技术指标数据要求
    requirements = {
        "MA5": {"min": 5, "recommended": 10},
        "MA10": {"min": 10, "recommended": 15},
        "MA20": {"min": 20, "recommended": 30},
        "MA60": {"min": 60, "recommended": 120},
        "MACD": {"min": 26, "recommended": 100, "professional": 250},
        "RSI": {"min": 14, "recommended": 50},
        "BOLL": {"min": 20, "recommended": 60},
    }
    
    print(f"📊 当前配置: {lookback_days}天")
    print(f"\n技术指标数据要求检查:")
    print("-" * 80)
    
    all_passed = True
    for indicator, req in requirements.items():
        min_days = req["min"]
        rec_days = req.get("recommended", min_days)
        pro_days = req.get("professional", rec_days)
        
        if lookback_days >= pro_days:
            status = "✅ 专业级"
            level = "professional"
        elif lookback_days >= rec_days:
            status = "✅ 推荐级"
            level = "recommended"
        elif lookback_days >= min_days:
            status = "⚠️  最小级"
            level = "minimum"
            all_passed = False
        else:
            status = "❌ 不足"
            level = "insufficient"
            all_passed = False
        
        print(f"{indicator:8s} | 最小:{min_days:3d}天 | 推荐:{rec_days:3d}天 | 专业:{pro_days:3d}天 | {status}")
    
    print("-" * 80)
    
    if all_passed:
        print(f"✅ 所有技术指标都满足推荐或专业级要求")
    else:
        print(f"⚠️  部分技术指标未达到推荐级要求")
    
    assert all_passed or lookback_days >= min(req["min"] for req in requirements.values())


def main():
    """主测试流程"""
    print("\n" + "=" * 80)
    print("🔍 MARKET_ANALYST_LOOKBACK_DAYS 配置验证测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试1：配置加载
    lookback_days = test_config_loading()
    if lookback_days is None:
        print("\n❌ 配置加载失败，终止测试")
        return
    
    # 测试2：日期范围计算
    start_date, end_date, actual_days = test_date_range_calculation(lookback_days)
    if start_date is None:
        print("\n❌ 日期范围计算失败，终止测试")
        return
    
    # 测试3：数据获取
    data_success = test_data_fetching(start_date, end_date)
    
    # 测试4：技术指标准确性
    indicators_ok = test_technical_indicators_accuracy(lookback_days)
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    print(f"✅ 配置加载: 成功 ({lookback_days}天)")
    print(f"✅ 日期计算: 成功 ({actual_days}天)")
    print(f"{'✅' if data_success else '❌'} 数据获取: {'成功' if data_success else '失败'}")
    print(f"{'✅' if indicators_ok else '⚠️ '} 技术指标: {'满足要求' if indicators_ok else '部分不足'}")
    
    if lookback_days == 250 and data_success and indicators_ok:
        print(f"\n🎉 完美！配置已设置为250天（专业级），所有测试通过！")
    elif data_success:
        print(f"\n✅ 配置生效，数据获取正常")
    else:
        print(f"\n⚠️  存在问题，请检查日志")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
