"""检查缓存中的港股行情数据"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def check_cached_quote():
    """检查缓存中的 09988 行情数据"""
    client = AsyncIOMotorClient('mongodb://localhost:27017/')
    db = client['tradingagents']
    
    print("=== 检查缓存中的港股行情数据 ===\n")
    
    # 1. 检查 stock_data_cache 集合
    cache_data = await db['stock_data_cache'].find_one({
        'symbol': '09988',
        'data_source': 'hk_realtime_quote'
    })
    
    if cache_data:
        print("✅ 找到缓存数据")
        print(f"缓存时间: {cache_data.get('cached_at')}")
        print(f"数据源: {cache_data.get('data_source')}")
        
        # 解析数据
        data_str = cache_data.get('data', '{}')
        try:
            data = json.loads(data_str)
            print(f"\n缓存的数据:")
            print(f"  代码: {data.get('code')}")
            print(f"  名称: {data.get('name')}")
            print(f"  价格: {data.get('price')}")
            print(f"  来源: {data.get('source')}")
            print(f"  更新时间: {data.get('updated_at')}")
            
            # 检查 name 字段
            name = data.get('name', '')
            if name.startswith('港股'):
                print(f"\n⚠️ 名称是默认格式: {name}")
                print("   需要清除缓存，重新获取")
            else:
                print(f"\n✅ 名称正常: {name}")
        except Exception as e:
            print(f"❌ 解析数据失败: {e}")
    else:
        print("❌ 未找到缓存数据")
    
    # 2. 检查 paper_positions 中的数据
    print("\n=== 检查 paper_positions 中的 09988 ===\n")
    positions = await db['paper_positions'].find({'code': '09988'}).to_list(None)
    
    if positions:
        print(f"找到 {len(positions)} 条持仓记录")
        for pos in positions:
            print(f"  用户: {pos.get('user_id')}")
            print(f"  名称: {pos.get('name', '(无)')}")
            print(f"  数量: {pos.get('quantity')}")
            print(f"  创建时间: {pos.get('created_at')}")
            print()
    else:
        print("未找到持仓记录")
    
    client.close()

if __name__ == '__main__':
    asyncio.run(check_cached_quote())

