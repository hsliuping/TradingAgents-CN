"""集成测试：验证模拟交易中的 name 字段"""
import pytest
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

@pytest.fixture
async def mongo_db():
    """获取 MongoDB 连接"""
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_uri)
    db = client['tradingagents']
    yield db
    client.close()

@pytest.mark.asyncio
async def test_paper_position_name_field_cn(mongo_db):
    """测试 A股持仓的 name 字段"""
    test_user_id = "test_cn_user"
    
    # 清理
    await mongo_db['paper_positions'].delete_many({'user_id': test_user_id})
    
    # 创建持仓
    position = {
        'user_id': test_user_id,
        'code': '300750',
        'name': '宁德时代',
        'market': 'CN',
        'currency': 'CNY',
        'quantity': 100,
        'available_qty': 0,
        'frozen_qty': 0,
        'avg_cost': 100.0,
        'updated_at': '2025-12-19T00:00:00'
    }
    
    result = await mongo_db['paper_positions'].insert_one(position)
    
    # 验证
    saved = await mongo_db['paper_positions'].find_one({'_id': result.inserted_id})
    assert saved is not None
    assert saved['name'] == '宁德时代'
    assert saved['code'] == '300750'
    assert saved['market'] == 'CN'
    
    # 清理
    await mongo_db['paper_positions'].delete_many({'user_id': test_user_id})

@pytest.mark.asyncio
async def test_paper_position_name_field_hk(mongo_db):
    """测试 港股持仓的 name 字段"""
    test_user_id = "test_hk_user"
    
    # 清理
    await mongo_db['paper_positions'].delete_many({'user_id': test_user_id})
    
    # 创建持仓
    position = {
        'user_id': test_user_id,
        'code': '00700',
        'name': '腾讯控股',
        'market': 'HK',
        'currency': 'HKD',
        'quantity': 100,
        'available_qty': 100,
        'frozen_qty': 0,
        'avg_cost': 100.0,
        'updated_at': '2025-12-19T00:00:00'
    }
    
    result = await mongo_db['paper_positions'].insert_one(position)
    
    # 验证
    saved = await mongo_db['paper_positions'].find_one({'_id': result.inserted_id})
    assert saved is not None
    assert saved['name'] == '腾讯控股'
    assert saved['code'] == '00700'
    assert saved['market'] == 'HK'
    
    # 清理
    await mongo_db['paper_positions'].delete_many({'user_id': test_user_id})

@pytest.mark.asyncio
async def test_paper_position_name_field_us(mongo_db):
    """测试 美股持仓的 name 字段"""
    test_user_id = "test_us_user"
    
    # 清理
    await mongo_db['paper_positions'].delete_many({'user_id': test_user_id})
    
    # 创建持仓
    position = {
        'user_id': test_user_id,
        'code': 'AAPL',
        'name': '苹果公司',
        'market': 'US',
        'currency': 'USD',
        'quantity': 100,
        'available_qty': 100,
        'frozen_qty': 0,
        'avg_cost': 100.0,
        'updated_at': '2025-12-19T00:00:00'
    }
    
    result = await mongo_db['paper_positions'].insert_one(position)
    
    # 验证
    saved = await mongo_db['paper_positions'].find_one({'_id': result.inserted_id})
    assert saved is not None
    assert saved['name'] == '苹果公司'
    assert saved['code'] == 'AAPL'
    assert saved['market'] == 'US'
    
    # 清理
    await mongo_db['paper_positions'].delete_many({'user_id': test_user_id})

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

