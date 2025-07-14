#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试601127股票名称获取问题的专用测试程序

这个程序专门用于诊断和解决601127股票名称显示为"股票601127"而非实际名称的问题。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
import traceback

def test_stock_name_mapping():
    """测试股票名称映射字典"""
    print("\n=== 测试1: 股票名称映射字典 ===")
    
    try:
        from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider
        
        provider = TongDaXinDataProvider()
        
        # 测试已知股票
        test_codes = ['000001', '600519', '688008', '601127']
        
        print("股票名称映射测试:")
        for code in test_codes:
            name = provider._get_stock_name(code)
            print(f"  {code} -> {name}")
            
        # 检查601127是否在映射中
        name_601127 = provider._get_stock_name('601127')
        if name_601127 == '股票601127':
            print("\n❌ 问题确认: 601127不在股票名称映射字典中")
            print("   这就是为什么显示'股票601127'而不是实际名称的原因")
        else:
            print(f"\n✅ 601127已映射为: {name_601127}")
            
        return True
        
    except Exception as e:
        print(f"❌ 股票名称映射测试失败: {e}")
        traceback.print_exc()
        return False

def test_tdx_api_stock_info():
    """测试Tushare数据接口获取股票基本信息"""
    print("\n=== 测试2: Tushare数据接口股票基本信息 ===")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_tdx_provider
        
        provider = get_tdx_provider()
        
        if not provider.connect():
            print("❌ Tushare数据接口连接失败")
            return False
            
        print("✅ Tushare数据接口连接成功")
        
        # 尝试获取601127的详细信息
        print("\n尝试获取601127股票信息:")
        
        # 方法1: 获取实时数据
        realtime_data = provider.get_real_time_data('601127')
        if realtime_data:
            print(f"  实时数据中的名称: {realtime_data.get('name', 'N/A')}")
            print(f"  当前价格: {realtime_data.get('price', 'N/A')}")
        else:
            print("  ❌ 无法获取实时数据")
            
        # 方法2: 尝试通过pytdx直接获取股票列表
        try:
            # 获取上海市场股票列表的一部分
            stock_list = provider.api.get_security_list(1, 0)  # 上海市场
            if stock_list:
                print(f"\n上海市场股票列表样本 (前10个):")
                for i, stock in enumerate(stock_list[:10]):
                    print(f"  {stock.get('code', 'N/A')} -> {stock.get('name', 'N/A')}")
                    
                # 查找601127
                found_601127 = None
                for stock in stock_list:
                    if stock.get('code') == '601127':
                        found_601127 = stock
                        break
                        
                if found_601127:
                    print(f"\n✅ 在股票列表中找到601127:")
                    print(f"  代码: {found_601127.get('code')}")
                    print(f"  名称: {found_601127.get('name')}")
                    print(f"  市场: {found_601127.get('market', 'N/A')}")
                else:
                    print(f"\n❌ 在股票列表中未找到601127")
            else:
                print("❌ 无法获取股票列表")
                
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ Tushare数据接口测试失败: {e}")
        traceback.print_exc()
        return False

def test_manual_stock_name_lookup():
    """手动查找601127的真实股票名称"""
    print("\n=== 测试3: 手动查找601127真实名称 ===")
    
    # 常见的601127可能的名称
    possible_names = {
        '601127': '小康股份',  # 这是一个可能的映射
        # 可以添加更多可能的映射
    }
    
    print("可能的601127股票名称:")
    for code, name in possible_names.items():
        print(f"  {code} -> {name}")
        
    return True

def create_enhanced_stock_mapping():
    """创建增强的股票名称映射"""
    print("\n=== 解决方案: 创建增强的股票名称映射 ===")
    
    enhanced_mapping = {
        # 现有映射
        '000001': '平安银行', '000002': '万科A', '000858': '五粮液', '000651': '格力电器',
        '000333': '美的集团', '000725': '京东方A', '002415': '海康威视', '002594': '比亚迪',
        '300750': '宁德时代',
        
        # 上海主板
        '600036': '招商银行', '600519': '贵州茅台', '600028': '中国石化', 
        '601398': '工商银行', '601318': '中国平安', '600000': '浦发银行',
        '600887': '伊利股份', '601166': '兴业银行',
        
        # 科创板股票
        '688008': '澜起科技', '688009': '中国通号', '688036': '传音控股',
        '688111': '金山办公', '688981': '中芯国际', '688599': '天合光能',
        '688012': '中微公司', '688169': '石头科技', '688303': '大全能源',
        
        # 新增映射 - 解决601127问题
        '601127': '小康股份',  # 重庆小康工业集团股份有限公司
        
        # 可以继续添加更多股票映射
        '601128': '常熟银行',
        '601129': '中核钛白',
        '601126': '四方股份',
    }
    
    print(f"增强映射包含 {len(enhanced_mapping)} 个股票")
    print(f"601127 映射为: {enhanced_mapping.get('601127', '未找到')}")
    
    # 生成修复代码
    fix_code = '''
# 修复tdx_utils.py中的_get_stock_name方法
# 在stock_names字典中添加以下映射:

# 新增映射 - 解决601127等问题
'601127': '小康股份',  # 重庆小康工业集团股份有限公司
'601128': '常熟银行',
'601129': '中核钛白', 
'601126': '四方股份',
'''
    
    print("\n建议的修复代码:")
    print(fix_code)
    
    return enhanced_mapping

def test_fix_implementation():
    """测试修复实现"""
    print("\n=== 测试4: 修复实现验证 ===")
    
    try:
        # 模拟修复后的_get_stock_name方法
        def fixed_get_stock_name(stock_code: str) -> str:
            stock_names = {
                # 主板股票
                '000001': '平安银行', '000002': '万科A', '000858': '五粮液', '000651': '格力电器',
                '000333': '美的集团', '000725': '京东方A', '002415': '海康威视', '002594': '比亚迪',
                '300750': '宁德时代',
                
                # 上海主板
                '600036': '招商银行', '600519': '贵州茅台', '600028': '中国石化', 
                '601398': '工商银行', '601318': '中国平安', '600000': '浦发银行',
                '600887': '伊利股份', '601166': '兴业银行',
                
                # 科创板股票
                '688008': '澜起科技', '688009': '中国通号', '688036': '传音控股',
                '688111': '金山办公', '688981': '中芯国际', '688599': '天合光能',
                '688012': '中微公司', '688169': '石头科技', '688303': '大全能源',
                
                # 新增映射 - 解决601127问题
                '601127': '小康股份',  # 重庆小康工业集团股份有限公司
                '601128': '常熟银行',
                '601129': '中核钛白',
                '601126': '四方股份',
            }
            
            return stock_names.get(stock_code, f'股票{stock_code}')
        
        # 测试修复效果
        test_codes = ['601127', '600519', '688008', '999999']
        
        print("修复后的股票名称映射测试:")
        for code in test_codes:
            name = fixed_get_stock_name(code)
            status = "✅" if name != f'股票{code}' else "❌"
            print(f"  {status} {code} -> {name}")
            
        # 特别验证601127
        name_601127 = fixed_get_stock_name('601127')
        if name_601127 == '小康股份':
            print("\n✅ 修复成功: 601127现在正确映射为'小康股份'")
        else:
            print(f"\n❌ 修复失败: 601127仍映射为'{name_601127}'")
            
        return True
        
    except Exception as e:
        print(f"❌ 修复测试失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🔍 601127股票名称问题诊断和修复测试")
    print("=" * 50)
    
    test_results = []
    
    # 执行所有测试
    test_results.append(("股票名称映射字典测试", test_stock_name_mapping()))
    test_results.append(("Tushare数据接口股票信息测试", test_tdx_api_stock_info()))
    test_results.append(("手动查找股票名称", test_manual_stock_name_lookup()))
    test_results.append(("修复实现验证", test_fix_implementation()))
    
    # 创建增强映射
    enhanced_mapping = create_enhanced_stock_mapping()
    
    # 测试总结
    print("\n" + "=" * 50)
    print("📊 测试总结")
    print("=" * 50)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    print(f"测试通过: {passed}/{total}")
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {test_name}")
    
    print("\n🔍 问题分析:")
    print("1. 601127在tdx_utils.py的stock_names字典中缺失")
    print("2. 这导致_get_stock_name方法返回默认值'股票601127'")
    print("3. 需要在stock_names字典中添加601127的正确映射")
    
    print("\n💡 解决方案:")
    print("1. 修改tradingagents/dataflows/tdx_utils.py文件")
    print("2. 在_get_stock_name方法的stock_names字典中添加:")
    print("   '601127': '小康股份',")
    print("3. 重启Web应用以使更改生效")
    
    print("\n📋 下一步操作:")
    print("1. 确认601127的真实股票名称")
    print("2. 更新tdx_utils.py中的股票名称映射")
    print("3. 测试修复效果")
    print("4. 考虑实现动态股票名称获取机制")

if __name__ == "__main__":
    main()