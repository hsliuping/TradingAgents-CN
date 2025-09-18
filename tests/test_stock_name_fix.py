#!/usr/bin/env python3
"""
测试股票名称获取功能
验证601127股票名称是否能正确显示
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

def test_stock_name_mapping():
    """测试股票名称映射功能"""
    print("\n🧪 测试股票名称映射功能...")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_real_time_data
        
        # 测试多个股票代码
        test_symbols = ['601127', '688008', '000001', '600036']
        
        for symbol in test_symbols:
            print(f"\n📊 测试股票: {symbol}")
            try:
                data = get_real_time_data(symbol)
                if data:
                    print(f"  ✅ 股票代码: {data.get('code', 'N/A')}")
                    print(f"  📝 股票名称: {data.get('name', 'N/A')}")
                    print(f"  💰 当前价格: ¥{data.get('price', 'N/A')}")
                    print(f"  📈 涨跌幅: {data.get('change_percent', 'N/A')}%")
                else:
                    print(f"  ❌ 无法获取股票数据")
            except Exception as e:
                print(f"  ❌ 获取失败: {e}")
                
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    return True

def test_stock_name_method():
    """测试_get_stock_name方法"""
    print("\n🔍 测试_get_stock_name方法...")
    
    try:
        # 直接导入并测试_get_stock_name方法
        from tradingagents.dataflows.tdx_utils import _get_stock_name
        
        test_symbols = ['601127', '688008', '000001', '600036', '999999']
        
        for symbol in test_symbols:
            name = _get_stock_name(symbol)
            print(f"  📊 {symbol} -> {name}")
            
    except ImportError as e:
        print(f"❌ 导入_get_stock_name方法失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试_get_stock_name方法失败: {e}")
        return False
    
    return True

def test_stock_names_dict():
    """测试stock_names字典内容"""
    print("\n📚 测试stock_names字典内容...")
    
    try:
        from tradingagents.dataflows.tdx_utils import stock_names
        
        print(f"  📊 字典总数: {len(stock_names)}个股票")
        
        # 检查特定股票
        test_symbols = ['601127', '688008', '000001', '600036']
        
        for symbol in test_symbols:
            if symbol in stock_names:
                print(f"  ✅ {symbol}: {stock_names[symbol]}")
            else:
                print(f"  ❌ {symbol}: 未找到")
        
        # 显示前10个映射
        print("\n  📋 前10个股票映射:")
        for i, (code, name) in enumerate(list(stock_names.items())[:10]):
            print(f"    {code}: {name}")
            
    except ImportError as e:
        print(f"❌ 导入stock_names字典失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试stock_names字典失败: {e}")
        return False
    
    return True

def test_tdx_connection():
    """测试通达信连接"""
    print("\n🔗 测试Tushare数据接口连接...")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_tdx_provider
        
        provider = get_tdx_provider()
        if provider:
            print("  ✅ Tushare数据接口连接成功")
            
            # 测试获取股票基本信息
            try:
                quotes = provider.get_security_quotes([(0, '601127')])
                if quotes:
                    quote = quotes[0]
                    print(f"  📊 601127原始数据:")
                    print(f"    代码: {quote[0]}")
                    print(f"    名称: {quote[1] if len(quote) > 1 else 'N/A'}")
                    print(f"    价格: {quote[3] if len(quote) > 3 else 'N/A'}")
                    print(f"    涨跌: {quote[4] if len(quote) > 4 else 'N/A'}")
                    print(f"    涨跌幅: {quote[5] if len(quote) > 5 else 'N/A'}")
                    print(f"    成交量: {quote[6] if len(quote) > 6 else 'N/A'}")
                else:
                    print("  ❌ 无法获取股票行情数据")
            except Exception as e:
                print(f"  ❌ 获取行情数据失败: {e}")
        else:
            print("  ❌ Tushare数据接口连接失败")
            return False
            
    except ImportError as e:
        print(f"❌ 导入通达信模块失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试通达信连接失败: {e}")
        return False
    
    return True

def test_china_stock_data():
    """测试get_china_stock_data函数"""
    print("\n📈 测试get_china_stock_data函数...")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_china_stock_data
        from datetime import datetime, timedelta
        
        # 测试601127股票数据获取
        symbol = '601127'
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"  📊 获取{symbol}股票数据 ({start_date} 到 {end_date})")
        
        result = get_china_stock_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        if result:
            # 解析结果中的股票名称
            lines = result.split('\n')
            for line in lines[:20]:  # 只显示前20行
                if '股票名称' in line:
                    print(f"  📝 找到股票名称行: {line.strip()}")
                elif '当前价格' in line:
                    print(f"  💰 找到价格行: {line.strip()}")
                elif line.strip() and not line.startswith('#'):
                    print(f"  📄 {line.strip()}")
        else:
            print(f"  ❌ 无法获取{symbol}股票数据")
            
    except ImportError as e:
        print(f"❌ 导入get_china_stock_data函数失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试get_china_stock_data函数失败: {e}")
        return False
    
    return True

def main():
    """主测试函数"""
    print("🚀 开始股票名称获取功能测试...")
    print("=" * 60)
    
    tests = [
        ("股票名称字典测试", test_stock_names_dict),
        ("_get_stock_name方法测试", test_stock_name_method),
        ("通达信连接测试", test_tdx_connection),
        ("实时数据获取测试", test_stock_name_mapping),
        ("完整数据流程测试", test_china_stock_data)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"🧪 {test_name}")
        print(f"{'='*60}")
        
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name}执行异常: {e}")
            results[test_name] = False
    
    # 测试总结
    print(f"\n{'='*60}")
    print("📊 测试结果总结")
    print(f"{'='*60}")
    
    success_count = 0
    total_count = len(results)
    
    for test_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name}: {status}")
        if success:
            success_count += 1
    
    print(f"\n🎯 测试完成: {success_count}/{total_count} 项通过")
    
    if success_count == total_count:
        print("🎉 所有测试通过！股票名称功能正常")
    elif success_count > 0:
        print("⚠️ 部分测试通过，请检查失败的测试项")
    else:
        print("❌ 所有测试失败，请检查代码实现")
    
    # 针对601127的特别说明
    print(f"\n💡 关于601127股票:")
    print("- 如果显示'股票601127'，说明该股票不在映射字典中")
    print("- 需要在stock_names字典中添加601127的正确名称")
    print("- 或者通过其他方式获取股票名称")

if __name__ == "__main__":
    main()