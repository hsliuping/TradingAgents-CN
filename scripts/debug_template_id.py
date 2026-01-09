"""调试模板 ID 问题"""
import asyncio
from app.core.database import init_database, get_mongo_db
from bson import ObjectId


async def check():
    await init_database()
    db = get_mongo_db()
    
    template_id = '6940138ec33e723006ecef63'
    
    # 测试 ObjectId 是否有效
    try:
        oid = ObjectId(template_id)
        print(f'ObjectId valid: {oid}')
    except Exception as e:
        print(f'ObjectId invalid: {e}')
    
    # 查询数据库
    result = await db['prompt_templates'].find_one({'_id': ObjectId(template_id)})
    print(f'Database result by ObjectId: {result}')
    
    # 查询字符串 id
    result2 = await db['prompt_templates'].find_one({'_id': template_id})
    print(f'Database result by string: {result2}')
    
    # 查所有模板的 _id
    cursor = db['prompt_templates'].find({}, {'_id': 1, 'template_name': 1, 'agent_name': 1})
    templates = await cursor.to_list(length=50)
    print(f'\n找到 {len(templates)} 个模板:')
    for t in templates[:15]:
        print(f"  {t['_id']} ({type(t['_id']).__name__}) - {t.get('template_name', 'N/A')}")
    
    # 检查是否有这个ID的模板
    print(f'\n检查 ID {template_id}:')
    for t in templates:
        if str(t['_id']) == template_id:
            print(f'  找到匹配: {t}')
            break
    else:
        print(f'  未找到匹配的模板')


if __name__ == '__main__':
    asyncio.run(check())

