"""调试用户ID匹配问题"""
import asyncio
from app.core.database import get_mongo_db
from app.models.user import PyObjectId
from bson import ObjectId

async def debug_user_id():
    db = get_mongo_db()
    
    print("=" * 60)
    print("检查 unified_analysis_tasks 集合中的任务")
    print("=" * 60)
    
    # 获取所有任务
    tasks = await db.unified_analysis_tasks.find().limit(5).to_list(5)
    
    for i, task in enumerate(tasks, 1):
        print(f"\n任务 {i}:")
        print(f"  task_id: {task.get('task_id')}")
        print(f"  user_id: {task.get('user_id')}")
        print(f"  user_id 类型: {type(task.get('user_id'))}")
        print(f"  status: {task.get('status')}")
        print(f"  task_type: {task.get('task_type')}")
    
    print("\n" + "=" * 60)
    print("检查 users 集合")
    print("=" * 60)
    
    # 获取所有用户
    users = await db.users.find().limit(5).to_list(5)
    
    for i, user in enumerate(users, 1):
        print(f"\n用户 {i}:")
        print(f"  _id: {user.get('_id')}")
        print(f"  _id 类型: {type(user.get('_id'))}")
        print(f"  username: {user.get('username')}")
        print(f"  email: {user.get('email')}")
    
    # 尝试匹配
    if tasks and users:
        print("\n" + "=" * 60)
        print("尝试匹配任务和用户")
        print("=" * 60)
        
        task_user_id = tasks[0].get('user_id')
        user_id = users[0].get('_id')
        
        print(f"\n任务的 user_id: {task_user_id} (类型: {type(task_user_id)})")
        print(f"用户的 _id: {user_id} (类型: {type(user_id)})")
        print(f"是否相等: {task_user_id == user_id}")
        
        # 尝试不同的查询方式
        print("\n测试查询:")
        
        # 方式1: 直接使用 ObjectId
        count1 = await db.unified_analysis_tasks.count_documents({"user_id": user_id})
        print(f"  使用 ObjectId 查询: {count1} 条")
        
        # 方式2: 转换为字符串
        count2 = await db.unified_analysis_tasks.count_documents({"user_id": str(user_id)})
        print(f"  使用字符串查询: {count2} 条")
        
        # 方式3: 使用 PyObjectId
        try:
            py_obj_id = PyObjectId(str(user_id))
            count3 = await db.unified_analysis_tasks.count_documents({"user_id": py_obj_id})
            print(f"  使用 PyObjectId 查询: {count3} 条")
        except Exception as e:
            print(f"  使用 PyObjectId 查询失败: {e}")
        
        # 统计查询
        print("\n测试统计查询:")
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        cursor = db.unified_analysis_tasks.aggregate(pipeline)
        results = await cursor.to_list(None)
        print(f"  聚合结果: {results}")

if __name__ == "__main__":
    asyncio.run(debug_user_id())

