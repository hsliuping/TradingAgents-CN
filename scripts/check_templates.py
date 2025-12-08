"""检查数据库中的模板数据"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    mongo_url = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
    print(f"连接: {mongo_url[:50]}...")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client['tradingagents']
    
    # 查询 market_analyst 的所有模板
    print('\n=== 查询 market_analyst 模板 ===')
    cursor = db.prompt_templates.find({'agent_type': 'analysts', 'agent_name': 'market_analyst'})
    templates = await cursor.to_list(length=100)
    
    for doc in templates:
        print(f"ID: {doc['_id']}")
        print(f"  template_name: {doc.get('template_name')}")
        print(f"  is_system: {doc.get('is_system')}")
        print(f"  status: {doc.get('status')}")
        print(f"  created_by: {doc.get('created_by')}")
        print()
    
    print(f"总数: {len(templates)}")
    
    # 查看所有不同的 agent_name
    print('\n=== 所有不同的 agent_name ===')
    pipeline = [
        {"$group": {"_id": {"agent_type": "$agent_type", "agent_name": "$agent_name"}}},
        {"$sort": {"_id.agent_type": 1, "_id.agent_name": 1}}
    ]
    cursor = db.prompt_templates.aggregate(pipeline)
    async for doc in cursor:
        print(f"  {doc['_id']['agent_type']} / {doc['_id']['agent_name']}")
    
    # 查询用户 6915d05ac52e760d74ed36a2 创建的模板
    print('\n=== 检查 created_by 字段类型 ===')
    cursor = db.prompt_templates.find({'is_system': False})
    templates = await cursor.to_list(length=100)
    for doc in templates:
        created_by = doc.get('created_by')
        print(f"ID: {doc['_id']}")
        print(f"  agent_name: {doc.get('agent_name')}")
        print(f"  created_by: {created_by}")
        print(f"  created_by type: {type(created_by)}")
        print()

    # 尝试用 ObjectId 查询
    from bson import ObjectId
    print('\n=== 用 ObjectId 查询 ===')
    cursor = db.prompt_templates.find({'created_by': ObjectId('6915d05ac52e760d74ed36a2')})
    templates = await cursor.to_list(length=100)
    print(f"用 ObjectId 查询结果: {len(templates)}")

    print('\n=== 用字符串查询 ===')
    cursor = db.prompt_templates.find({'created_by': '6915d05ac52e760d74ed36a2'})
    templates = await cursor.to_list(length=100)
    print(f"用字符串查询结果: {len(templates)}")

if __name__ == '__main__':
    asyncio.run(main())

