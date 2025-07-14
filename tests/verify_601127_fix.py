#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证601127股票名称修复效果的测试程序

这个程序用于验证修复后的tdx_utils.py是否正确显示601127的股票名称。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import traceback

def test_fixed_stock_name():
    """测试修复后的股票名称获取"""
    print("=== 验证601127股票名称修复效果 ===")
    
    try:
        from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider
        
        provider = TongDaXinDataProvider()
        
        # 测试多个股票代码
        test_codes = {
            '601127': '小康股份',  # 修复的目标
            '600519': '贵州茅台',  # 已有映射
            '688008': '澜起科技',  # 科创板
            '999999': '股票999999'  # 不存在的代码
        }
        
        print("\n股票名称映射测试结果:")
        all_correct = True
        
        for code, expected_name in test_codes.items():
            actual_name = provider._get_stock_name(code)
            is_correct = actual_name == expected_name
            status = "✅" if is_correct else "❌"
            
            print(f"  {status} {code}: 期望='{expected_name}', 实际='{actual_name}'")
            
            if not is_correct:
                all_correct = False
        
        # 特别验证601127
        name_601127 = provider._get_stock_name('601127')
        print(f"\n🎯 重点验证 - 601127股票名称:")
        if name_601127 == '小康股份':
            print(f"  ✅ 修复成功: 601127 -> {name_601127}")
        else:
            print(f"  ❌ 修复失败: 601127 -> {name_601127} (期望: 小康股份)")
            all_correct = False
            
        return all_correct
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        traceback.print_exc()
        return False

def test_real_time_data_with_fixed_name():
    """测试实时数据获取中的股票名称显示"""
    print("\n=== 测试实时数据中的股票名称 ===")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_tdx_provider
        
        provider = get_tdx_provider()
        
        if not provider.connect():
            print("❌ Tushare数据接口连接失败")
            return False
            
        print("✅ Tushare数据接口连接成功")
        
        # 获取601127的实时数据
        print("\n获取601127实时数据:")
        realtime_data = provider.get_real_time_data('601127')
        
        if realtime_data:
            stock_name = realtime_data.get('name', 'N/A')
            stock_price = realtime_data.get('price', 'N/A')
            change_percent = realtime_data.get('change_percent', 'N/A')
            
            print(f"  股票代码: 601127")
            print(f"  股票名称: {stock_name}")
            print(f"  当前价格: ¥{stock_price}")
            print(f"  涨跌幅: {change_percent}%")
            
            # 验证名称是否正确
            if stock_name == '小康股份':
                print(f"  ✅ 实时数据中股票名称正确: {stock_name}")
                return True
            else:
                print(f"  ❌ 实时数据中股票名称仍然错误: {stock_name} (期望: 小康股份)")
                return False
        else:
            print("  ❌ 无法获取601127的实时数据")
            return False
            
    except Exception as e:
        print(f"❌ 实时数据测试失败: {e}")
        traceback.print_exc()
        return False

def test_complete_data_flow():
    """测试完整的数据流程"""
    print("\n=== 测试完整数据流程 ===")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_china_stock_data
        
        # 设置日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        print(f"获取601127股票数据 ({start_date} 到 {end_date})")
        
        # 获取完整的股票数据
        result = get_china_stock_data('601127', start_date, end_date)
        
        if result and '小康股份' in result:
            print("✅ 完整数据流程中股票名称正确显示为'小康股份'")
            
            # 显示结果的前几行
            lines = result.split('\n')[:15]
            print("\n数据预览:")
            for line in lines:
                if line.strip():
                    print(f"  {line}")
            
            return True
        elif result and '股票601127' in result:
            print("❌ 完整数据流程中股票名称仍显示为'股票601127'")
            print("   这可能是因为缓存中仍有旧数据")
            return False
        else:
            print(f"❌ 完整数据流程失败或返回异常结果")
            return False
            
    except Exception as e:
        print(f"❌ 完整数据流程测试失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主验证函数"""
    print("🔍 验证601127股票名称修复效果")
    print("=" * 50)
    
    test_results = []
    
    # 执行验证测试
    test_results.append(("股票名称映射修复", test_fixed_stock_name()))
    test_results.append(("实时数据名称显示", test_real_time_data_with_fixed_name()))
    test_results.append(("完整数据流程", test_complete_data_flow()))
    
    # 验证总结
    print("\n" + "=" * 50)
    print("📊 验证总结")
    print("=" * 50)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    print(f"验证通过: {passed}/{total}")
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {test_name}")
    
    if passed == total:
        print("\n🎉 修复验证成功!")
        print("601127股票现在应该正确显示为'小康股份'")
        
        print("\n📋 后续建议:")
        print("1. 重启Web应用以确保所有模块使用更新后的代码")
        print("2. 清除相关缓存以避免显示旧的股票名称")
        print("3. 在Web界面中重新查询601127验证效果")
        print("4. 考虑添加更多股票的名称映射")
    else:
        print("\n⚠️ 修复验证部分失败")
        print("可能的原因:")
        print("1. 缓存中仍有旧数据")
        print("2. 某些模块未重新加载")
        print("3. 网络连接问题")
        
        print("\n建议操作:")
        print("1. 重启Python进程")
        print("2. 清除所有缓存")
        print("3. 重新测试")

if __name__ == "__main__":
    main()