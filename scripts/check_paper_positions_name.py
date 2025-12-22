"""检查 paper_positions 和 paper_trades 集合中的股票名称字段"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def main():
    # 直接连接 MongoDB
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_uri)
    db = client['trading_agents']
    
    # 查询几条 paper_positions 记录
    positions = await db['paper_positions'].find({}).limit(5).to_list(None)
    
    print('=== paper_positions 集合示例数据 ===')
    if positions:
        for pos in positions:
            print(f"代码: {pos.get('code')}, 名称: {pos.get('name')}, 数量: {pos.get('quantity')}")
    else:
        print('没有数据')
    
    # 查询几条 paper_trades 记录
    trades = await db['paper_trades'].find({}).limit(5).to_list(None)
    
    print('\n=== paper_trades 集合示例数据 ===')
    if trades:
        for trade in trades:
            print(f"代码: {trade.get('code')}, 方向: {trade.get('side')}, 数量: {trade.get('quantity')}")
            print(f"  包含字段: {', '.join(trade.keys())}")
    else:
        print('没有数据')
    
    # 统计有名称和没名称的记录
    total_positions = await db['paper_positions'].count_documents({})
    with_name = await db['paper_positions'].count_documents({"name": {"$exists": True, "$ne": None, "$ne": ""}})
    
    print(f'\n=== 统计信息 ===')
    print(f'paper_positions 总记录数: {total_positions}')
    print(f'有名称的记录数: {with_name}')
    print(f'没有名称的记录数: {total_positions - with_name}')

    client.close()

if __name__ == "__main__":
    asyncio.run(main())

