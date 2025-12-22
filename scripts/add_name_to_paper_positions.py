"""为 paper_positions 集合添加 name 字段"""
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

    print('=== 为 paper_positions 添加 name 字段 ===\n')

    # 获取所有没有 name 字段的 paper_positions 记录
    positions = await db['paper_positions'].find({'name': {'$exists': False}}).to_list(None)

    print(f'找到 {len(positions)} 条需要更新的 paper_positions 记录\n')

    updated_count = 0
    failed_count = 0

    for pos in positions:
        code = pos.get('code')

        # 从 stock_basic_info 获取股票名称
        stock_info = await db['stock_basic_info'].find_one({'code': code})

        if stock_info and stock_info.get('name'):
            name = stock_info.get('name')

            # 更新 paper_positions
            result = await db['paper_positions'].update_one(
                {'_id': pos['_id']},
                {'$set': {'name': name}}
            )

            if result.modified_count > 0:
                print(f'✅ 更新: {code} -> {name}')
                updated_count += 1
            else:
                print(f'⚠️  更新失败: {code}')
                failed_count += 1
        else:
            print(f'❌ 未找到股票信息: {code}')
            failed_count += 1

    print(f'\n=== 更新统计 ===')
    print(f'✅ 已更新: {updated_count}')
    print(f'❌ 失败: {failed_count}')
    print(f'📝 总计: {len(positions)}')

    client.close()

if __name__ == "__main__":
    asyncio.run(main())

