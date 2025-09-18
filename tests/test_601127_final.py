#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终测试601127股票的完整功能
验证动态股票名称获取是否正常工作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tradingagents.dataflows.tdx_utils import get_china_stock_data
from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider

def test_601127_complete():
    """测试601127股票的完整功能"""
    print("=== 测试601127股票完整功能 ===")
    
    # 测试1: 直接测试股票名称获取
    print("\n📊 测试1: 直接获取股票名称")
    try:
        provider = TongDaXinDataProvider()
        if provider.connect():
            name = provider._get_stock_name('601127')
            print(f"  601127 股票名称: {name}")
            if name == "小康股份":
                print("  ✅ 股票名称正确")
            else:
                print(f"  ❌ 股票名称错误，期望'小康股份'，实际'{name}'")
            provider.disconnect()
        else:
            print("  ❌ 无法连接Tushare数据接口")
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
    
    # 测试2: 测试实时数据获取
    print("\n📊 测试2: 获取实时数据")
    try:
        provider = TongDaXinDataProvider()
        if provider.connect():
            data = provider.get_real_time_data('601127')
            if data:
                print(f"  实时数据: {data}")
                print("  ✅ 实时数据获取成功")
            else:
                print("  ❌ 无法获取实时数据")
            provider.disconnect()
        else:
            print("  ❌ 无法连接Tushare数据接口")
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
    
    # 测试3: 测试完整数据流程
    print("\n📊 测试3: 完整数据流程")
    try:
        result = get_china_stock_data(
            stock_code='601127',
            start_date='2024-01-01',
            end_date='2024-12-31'
        )
        
        if result and '小康股份' in result:
            print(f"  完整数据: {result[:200]}...")
            print("  ✅ 完整数据流程成功")
        else:
            print(f"  ❌ 完整数据流程失败，结果: {result}")
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
    
    # 测试4: 测试其他常用股票
    print("\n📊 测试4: 其他常用股票")
    test_stocks = [
        ('000001', '平安银行'),
        ('600519', '贵州茅台'),
        ('002594', '比亚迪'),
        ('300750', '宁德时代')
    ]
    
    try:
        provider = TongDaXinDataProvider()
        if provider.connect():
            for code, expected_name in test_stocks:
                name = provider._get_stock_name(code)
                if name == expected_name:
                    print(f"  ✅ {code}: {name}")
                else:
                    print(f"  ❌ {code}: 期望'{expected_name}'，实际'{name}'")
            provider.disconnect()
        else:
            print("  ❌ 无法连接Tushare数据接口")
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
    
    # 测试5: 测试未知股票
    print("\n📊 测试5: 未知股票")
    try:
        provider = TongDaXinDataProvider()
        if provider.connect():
            unknown_name = provider._get_stock_name('999999')
            print(f"  999999 股票名称: {unknown_name}")
            if unknown_name == "股票999999":
                print("  ✅ 未知股票处理正确")
            else:
                print(f"  ❌ 未知股票处理错误，期望'股票999999'，实际'{unknown_name}'")
            provider.disconnect()
        else:
            print("  ❌ 无法连接Tushare数据接口")
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_601127_complete()