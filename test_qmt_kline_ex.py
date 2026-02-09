#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 QMT K线数据获取（使用 get_market_data_ex）
"""
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.services.data_sources.qmt_adapter import QMTAdapter

def test_kline_with_ex():
    """测试使用 get_market_data_ex 获取 K 线数据"""
    print("=" * 60)
    print("🔍 测试 QMT K线数据获取（get_market_data_ex）")
    print("=" * 60)
    
    adapter = QMTAdapter()
    
    if not adapter.is_available():
        print("❌ QMT 不可用")
        return
    
    print("✅ QMT 可用")
    
    # 测试股票列表
    test_stocks = [
        ("000001", "平安银行"),
        ("600000", "浦发银行"),
        ("000002", "万科A"),
    ]
    
    for code, name in test_stocks:
        print(f"\n{'=' * 60}")
        print(f"📊 测试股票: {code} ({name})")
        print(f"{'=' * 60}")
        
        # 获取日线数据
        kline = adapter.get_kline(code, period="day", limit=5)
        
        if kline:
            print(f"✅ 成功获取 {len(kline)} 条 K 线数据")
            print("\n最近 5 条数据：")
            for i, item in enumerate(kline[-5:], 1):
                print(f"  {i}. 日期: {item['date']}")
                print(f"     开盘: {item['open']:.2f}, 最高: {item['high']:.2f}")
                print(f"     最低: {item['low']:.2f}, 收盘: {item['close']:.2f}")
                print(f"     成交量: {item['volume']:.0f}, 成交额: {item['amount']:.2f}")
        else:
            print(f"❌ 未获取到 K 线数据")
            print(f"💡 提示：可能需要在 MiniQMT 中手动下载历史数据")

if __name__ == "__main__":
    test_kline_with_ex()

