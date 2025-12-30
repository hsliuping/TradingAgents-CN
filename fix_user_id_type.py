"""修复 unified_analysis_tasks 集合中的 user_id 类型

将字符串类型的 user_id 转换为 ObjectId 类型
"""
import asyncio
import sys
from bson import ObjectId

# 添加项目路径
sys.path.insert(0, '.')

from app.core.database import init_database, close_database, get_mongo_db


async def fix_user_id_types():
    """修复 user_id 类型"""
    try:
        # 初始化数据库连接
        print("🔄 初始化数据库连接...")
        await init_database()
        
        db = get_mongo_db()
        collection = db.unified_analysis_tasks
        
        # 查找所有 user_id 为字符串类型的任务
        print("\n📋 查找需要修复的任务...")
        
        # 获取所有任务
        all_tasks = await collection.find().to_list(None)
        
        fixed_count = 0
        error_count = 0
        
        for task in all_tasks:
            task_id = task.get('task_id')
            user_id = task.get('user_id')
            
            # 检查 user_id 类型
            if isinstance(user_id, str):
                print(f"\n🔧 修复任务: {task_id}")
                print(f"   当前 user_id: {user_id} (类型: {type(user_id)})")
                
                try:
                    # 转换为 ObjectId
                    new_user_id = ObjectId(user_id)
                    
                    # 更新数据库
                    result = await collection.update_one(
                        {"task_id": task_id},
                        {"$set": {"user_id": new_user_id}}
                    )
                    
                    if result.modified_count > 0:
                        print(f"   ✅ 已修复: {user_id} -> ObjectId('{user_id}')")
                        fixed_count += 1
                    else:
                        print(f"   ⚠️ 未修改（可能已经是正确类型）")
                        
                except Exception as e:
                    print(f"   ❌ 修复失败: {e}")
                    error_count += 1
            else:
                print(f"✓ 任务 {task_id} 的 user_id 已经是 ObjectId 类型")
        
        print("\n" + "=" * 60)
        print("📊 修复统计:")
        print(f"   总任务数: {len(all_tasks)}")
        print(f"   已修复: {fixed_count}")
        print(f"   失败: {error_count}")
        print("=" * 60)
        
        # 验证修复结果
        print("\n🔍 验证修复结果...")
        
        # 查询一个示例任务
        sample_task = await collection.find_one()
        if sample_task:
            print(f"\n示例任务:")
            print(f"  task_id: {sample_task.get('task_id')}")
            print(f"  user_id: {sample_task.get('user_id')}")
            print(f"  user_id 类型: {type(sample_task.get('user_id'))}")
            
            # 尝试查询
            user_id = sample_task.get('user_id')
            if isinstance(user_id, ObjectId):
                count = await collection.count_documents({"user_id": user_id})
                print(f"\n✅ 使用 ObjectId 查询成功: 找到 {count} 个任务")
            else:
                print(f"\n⚠️ user_id 仍然不是 ObjectId 类型")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭数据库连接
        print("\n🔄 关闭数据库连接...")
        await close_database()


if __name__ == "__main__":
    print("=" * 60)
    print("修复 unified_analysis_tasks 集合中的 user_id 类型")
    print("=" * 60)
    
    asyncio.run(fix_user_id_types())
    
    print("\n✅ 修复完成！")

