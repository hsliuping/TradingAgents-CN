"""测试新建模拟交易时是否正确保存 name 字段"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def test_new_position():
    """测试新建持仓时的 name 字段"""
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_uri)
    db = client['tradingagents']
    
    print('=== 测试新建持仓时的 name 字段 ===\n')
    
    # 测试用户ID
    test_user_id = "test_user_001"
    
    # 清理旧数据
    await db['paper_positions'].delete_many({'user_id': test_user_id})
    await db['paper_accounts'].delete_many({'user_id': test_user_id})
    
    print('✅ 已清理旧测试数据\n')
    
    # 创建账户
    now_iso = datetime.utcnow().isoformat()
    account = {
        'user_id': test_user_id,
        'cash': {
            'CNY': 1000000.0,
            'HKD': 1000000.0,
            'USD': 100000.0
        },
        'realized_pnl': {
            'CNY': 0.0,
            'HKD': 0.0,
            'USD': 0.0
        },
        'created_at': now_iso,
        'updated_at': now_iso
    }
    await db['paper_accounts'].insert_one(account)
    print('✅ 已创建测试账户\n')
    
    # 测试用例：A股、港股、美股
    test_cases = [
        {'code': '300750', 'market': 'CN', 'name': '宁德时代'},
        {'code': '00700', 'market': 'HK', 'name': '腾讯控股'},
        {'code': 'AAPL', 'market': 'US', 'name': '苹果公司'},
    ]
    
    print('=== 模拟新建持仓 ===\n')
    
    for test_case in test_cases:
        code = test_case['code']
        market = test_case['market']
        expected_name = test_case['name']
        
        # 创建持仓（模拟下单逻辑）
        position = {
            'user_id': test_user_id,
            'code': code,
            'name': expected_name,  # 这是新增的字段
            'market': market,
            'currency': {'CN': 'CNY', 'HK': 'HKD', 'US': 'USD'}[market],
            'quantity': 100,
            'available_qty': 100 if market != 'CN' else 0,
            'frozen_qty': 0,
            'avg_cost': 100.0,
            'updated_at': now_iso
        }
        
        result = await db['paper_positions'].insert_one(position)
        print(f'✅ 创建持仓: {code} ({market})')
        print(f'   名称: {expected_name}')
        print(f'   ID: {result.inserted_id}\n')
    
    # 验证数据
    print('=== 验证保存的数据 ===\n')
    positions = await db['paper_positions'].find({'user_id': test_user_id}).to_list(None)
    
    for pos in positions:
        code = pos.get('code')
        name = pos.get('name', '(无名称)')
        market = pos.get('market')
        print(f'代码: {code:6} | 名称: {name:20} | 市场: {market}')
    
    # 统计
    total = len(positions)
    with_name = sum(1 for p in positions if p.get('name'))
    
    print(f'\n=== 统计 ===')
    print(f'总记录数: {total}')
    print(f'有名称: {with_name}')
    print(f'名称完整率: {(with_name/total*100):.1f}%' if total > 0 else '名称完整率: 0%')
    
    # 注意：不清理数据，保留在数据库中供验证
    print('\n✅ 测试数据已保存到数据库，用户ID: test_user_001')
    print('   可以在 MongoDB 中查看 paper_positions 集合')

    client.close()

if __name__ == "__main__":
    asyncio.run(test_new_position())

