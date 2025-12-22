"""
测试港股实时价格是否包含股票名称
"""
import asyncio
from tradingagents.dataflows.providers.hk.hk_stock import get_hk_stock_provider


async def test_hk_stock_name():
    """测试港股实时价格是否包含股票名称"""
    print("=== 测试港股实时价格 name 字段 ===\n")
    
    provider = get_hk_stock_provider()
    
    # 测试股票列表
    test_stocks = [
        ("00700", "腾讯控股"),
        ("09988", "阿里巴巴"),
        ("01810", "小米集团"),
    ]
    
    for code, expected_name in test_stocks:
        print(f"📊 测试股票: {code} (预期名称: {expected_name})")
        
        try:
            # 获取实时价格
            quote = provider.get_real_time_price(code)
            
            if quote:
                print(f"✅ 获取成功:")
                print(f"   代码: {quote.get('symbol')}")
                print(f"   名称: {quote.get('name', '(无名称)')}")
                print(f"   价格: {quote.get('price')}")
                print(f"   货币: {quote.get('currency')}")
                
                # 检查是否包含 name 字段
                if 'name' in quote:
                    name = quote.get('name')
                    if name and not name.startswith('港股'):
                        print(f"   ✅ name 字段正确: {name}")
                    else:
                        print(f"   ⚠️ name 字段为默认值: {name}")
                else:
                    print(f"   ❌ 缺少 name 字段")
            else:
                print(f"❌ 获取失败: 返回 None")
                
        except Exception as e:
            print(f"❌ 异常: {e}")
        
        print()


if __name__ == "__main__":
    asyncio.run(test_hk_stock_name())

