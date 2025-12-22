"""检查数据库中的集合"""
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
    
    # 列出所有数据库
    databases = await client.list_database_names()
    print(f'=== 数据库列表 ===')
    for db_name in databases:
        print(f'  - {db_name}')
    
    # 检查 trading_agents 数据库
    db = client['trading_agents']
    collections = await db.list_collection_names()
    
    print(f'\n=== trading_agents 数据库中的集合 ===')
    for col_name in collections:
        count = await db[col_name].count_documents({})
        print(f'  - {col_name}: {count} 条记录')
    
    # 检查 paper_positions 集合
    if 'paper_positions' in collections:
        print(f'\n=== paper_positions 集合示例 ===')
        pos = await db['paper_positions'].find_one({})
        if pos:
            print(f'字段: {list(pos.keys())}')
            print(f'示例: {pos}')
    
    client.close()

if __name__ == "__main__":
    asyncio.run(main())

