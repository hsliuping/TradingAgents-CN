"""
修复 position_analysis 任务的 user_id 类型

问题：position_analysis 任务的 user_id 被保存为字符串，而 stock_analysis 任务的 user_id 是 ObjectId
解决：将所有 position_analysis 任务的 user_id 从字符串转换为 ObjectId
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bson import ObjectId
from app.core.database import init_db, get_mongo_db
from tradingagents.utils.logging_manager import get_logger

logger = get_logger(__name__)


async def fix_user_id_types():
    """修复 user_id 类型"""
    try:
        # 初始化数据库
        await init_db()
        logger.info("✅ 数据库初始化成功")
        
        db = get_mongo_db()
        collection = db.unified_analysis_tasks
        
        # 查找所有 position_analysis 任务
        position_tasks = await collection.find({"task_type": "position_analysis"}).to_list(None)
        logger.info(f"📊 找到 {len(position_tasks)} 个 position_analysis 任务")
        
        fixed_count = 0
        skipped_count = 0
        
        for task in position_tasks:
            task_id = task.get('task_id')
            user_id = task.get('user_id')
            
            logger.info(f"🔍 检查任务: {task_id}, user_id: {user_id} (类型: {type(user_id)})")
            
            # 如果 user_id 是字符串，转换为 ObjectId
            if isinstance(user_id, str):
                try:
                    new_user_id = ObjectId(user_id)
                    
                    # 更新数据库
                    result = await collection.update_one(
                        {"task_id": task_id},
                        {"$set": {"user_id": new_user_id}}
                    )
                    
                    if result.modified_count > 0:
                        logger.info(f"✅ 修复任务 {task_id}: user_id 从字符串 '{user_id}' 转换为 ObjectId({new_user_id})")
                        fixed_count += 1
                    else:
                        logger.warning(f"⚠️ 任务 {task_id} 未被修改")
                        
                except Exception as e:
                    logger.error(f"❌ 转换失败: {task_id}, user_id: {user_id}, 错误: {e}")
            else:
                logger.info(f"⏭️ 跳过任务 {task_id}: user_id 已经是 ObjectId 类型")
                skipped_count += 1
        
        logger.info(f"\n📊 修复完成:")
        logger.info(f"  - 修复数量: {fixed_count}")
        logger.info(f"  - 跳过数量: {skipped_count}")
        logger.info(f"  - 总数量: {len(position_tasks)}")
        
        # 验证修复结果
        logger.info(f"\n🔍 验证修复结果...")
        position_tasks_after = await collection.find({"task_type": "position_analysis"}).to_list(None)
        
        string_count = 0
        objectid_count = 0
        
        for task in position_tasks_after:
            user_id = task.get('user_id')
            if isinstance(user_id, str):
                string_count += 1
                logger.warning(f"⚠️ 仍然是字符串: task_id={task.get('task_id')}, user_id={user_id}")
            elif isinstance(user_id, ObjectId):
                objectid_count += 1
        
        logger.info(f"\n📊 验证结果:")
        logger.info(f"  - ObjectId 类型: {objectid_count}")
        logger.info(f"  - 字符串类型: {string_count}")
        
        if string_count == 0:
            logger.info(f"✅ 所有 position_analysis 任务的 user_id 都已是 ObjectId 类型")
        else:
            logger.error(f"❌ 仍有 {string_count} 个任务的 user_id 是字符串类型")
        
    except Exception as e:
        logger.error(f"❌ 修复失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(fix_user_id_types())

