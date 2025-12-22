"""测试 paper_positions 中的 name 字段"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def test_paper_positions_name():
    """测试 paper_positions 中的 name 字段"""
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_uri)
    db = client['tradingagents']
    
    print('=== 测试 paper_positions 中的 name 字段 ===\n')
    
    # 查询几条 paper_positions 记录
    positions = await db['paper_positions'].find({}).limit(10).to_list(None)
    
    print(f'找到 {len(positions)} 条 paper_positions 记录\n')
    
    if positions:
        print('=== 持仓示例 ===')
        for pos in positions:
            code = pos.get('code')
            name = pos.get('name', '(无名称)')
            market = pos.get('market', 'CN')
            qty = pos.get('quantity', 0)
            print(f'代码: {code:6} | 名称: {name:20} | 市场: {market} | 数量: {qty}')
    else:
        print('没有持仓数据')
    
    # 统计有名称和没名称的记录
    total = await db['paper_positions'].count_documents({})
    with_name = await db['paper_positions'].count_documents({
        'name': {'$exists': True, '$ne': None, '$ne': ''}
    })
    without_name = total - with_name
    
    print(f'\n=== 统计信息 ===')
    print(f'总记录数: {total}')
    print(f'有名称: {with_name}')
    print(f'无名称: {without_name}')
    
    if total > 0:
        percentage = (with_name / total) * 100
        print(f'名称完整率: {percentage:.1f}%')
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_paper_positions_name())

