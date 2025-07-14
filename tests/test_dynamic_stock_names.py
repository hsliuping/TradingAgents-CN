#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试动态股票名称获取功能
验证Tushare数据接口动态获取股票名称是否正常工作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider

def test_dynamic_stock_name_retrieval():
    """测试动态股票名称获取功能"""
    print("=== 测试动态股票名称获取功能 ===")
    
    # 测试股票代码列表
    test_stocks = [
        '000001',  # 平安银行
        '000002',  # 万科A
        '600519',  # 贵州茅台
        '600036',  # 招商银行
        '601127',  # 小康股份
        '002594',  # 比亚迪
        '300750',  # 宁德时代
        '688981',  # 中芯国际
        '601398',  # 工商银行
        '000858',  # 五粮液
        '999999',  # 不存在的股票
    ]
    
    try:
        provider = TongDaXinDataProvider()
        
        if not provider.connect():
            print("❌ Tushare数据接口连接失败")
            return False
            
        print("✅ Tushare数据接口连接成功")
        print("\n开始测试动态股票名称获取...")
        
        success_count = 0
        total_count = len(test_stocks)
        
        for i, stock_code in enumerate(test_stocks, 1):
            print(f"\n[{i}/{total_count}] 测试股票: {stock_code}")
            
            try:
                # 获取股票名称
                stock_name = provider._get_stock_name(stock_code)
                print(f"  股票名称: {stock_name}")
                
                # 验证结果
                if stock_name and not stock_name.startswith('股票'):
                    print(f"  ✅ 成功获取真实股票名称")
                    success_count += 1
                elif stock_name.startswith('股票'):
                    print(f"  ⚠️ 返回默认名称（可能是无效股票代码）")
                    if stock_code == '999999':  # 预期的无效股票
                        success_count += 1
                else:
                    print(f"  ❌ 获取失败")
                    
            except Exception as e:
                print(f"  ❌ 获取股票名称时出错: {e}")
        
        print(f"\n=== 测试结果 ===")
        print(f"成功: {success_count}/{total_count}")
        print(f"成功率: {success_count/total_count*100:.1f}%")
        
        provider.disconnect()
        
        return success_count >= total_count * 0.8  # 80%成功率认为测试通过
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        return False

def test_cache_functionality():
    """测试缓存功能"""
    print("\n=== 测试缓存功能 ===")
    
    try:
        provider = TongDaXinDataProvider()
        
        if not provider.connect():
            print("❌ Tushare数据接口连接失败")
            return False
        
        test_code = '000001'
        
        # 第一次获取（应该从API获取）
        print(f"第一次获取 {test_code} 的名称...")
        import time
        start_time = time.time()
        name1 = provider._get_stock_name(test_code)
        time1 = time.time() - start_time
        print(f"  结果: {name1}")
        print(f"  耗时: {time1:.3f}秒")
        
        # 第二次获取（应该从缓存获取）
        print(f"\n第二次获取 {test_code} 的名称...")
        start_time = time.time()
        name2 = provider._get_stock_name(test_code)
        time2 = time.time() - start_time
        print(f"  结果: {name2}")
        print(f"  耗时: {time2:.3f}秒")
        
        # 验证结果
        if name1 == name2:
            print(f"  ✅ 缓存功能正常，两次结果一致")
            if time2 < time1 * 0.1:  # 缓存应该快很多
                print(f"  ✅ 缓存显著提升了性能")
                cache_success = True
            else:
                print(f"  ⚠️ 缓存性能提升不明显")
                cache_success = False
        else:
            print(f"  ❌ 缓存功能异常，两次结果不一致")
            cache_success = False
        
        provider.disconnect()
        return cache_success
        
    except Exception as e:
        print(f"❌ 缓存测试过程中出错: {e}")
        return False

def test_complete_data_flow():
    """测试完整数据流程"""
    print("\n=== 测试完整数据流程 ===")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_china_stock_data
        
        test_code = '601127'  # 小康股份
        start_date = '2024-01-01'
        end_date = '2024-01-31'
        
        print(f"测试获取 {test_code} 的完整数据...")
        
        result = get_china_stock_data(test_code, start_date, end_date)
        
        if result and '小康股份' in result:
            print("✅ 完整数据流程测试成功，股票名称正确显示")
            return True
        elif result and '股票601127' in result:
            print("⚠️ 完整数据流程运行，但使用了默认名称")
            return False
        else:
            print("❌ 完整数据流程测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 完整数据流程测试出错: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 开始测试动态股票名称获取功能")
    print("=" * 50)
    
    # 测试1: 动态股票名称获取
    test1_result = test_dynamic_stock_name_retrieval()
    
    # 测试2: 缓存功能
    test2_result = test_cache_functionality()
    
    # 测试3: 完整数据流程
    test3_result = test_complete_data_flow()
    
    # 总结
    print("\n" + "=" * 50)
    print("📊 测试总结")
    print(f"动态名称获取: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"缓存功能: {'✅ 通过' if test2_result else '❌ 失败'}")
    print(f"完整数据流程: {'✅ 通过' if test3_result else '❌ 失败'}")
    
    overall_success = test1_result and test2_result and test3_result
    
    if overall_success:
        print("\n🎉 所有测试通过！动态股票名称获取功能正常工作")
        print("\n📝 功能特点:")
        print("  • 使用Tushare数据接口动态获取股票名称")
        print("  • 支持缓存机制，提高性能")
        print("  • 自动处理无效股票代码")
        print("  • 完全移除硬编码股票名称")
    else:
        print("\n⚠️ 部分测试失败，请检查实现")
    
    return overall_success

if __name__ == "__main__":
    main()