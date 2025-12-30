#!/usr/bin/env python
"""为 _update_position_task_status 添加日志"""

with open('app/services/unified_analysis_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 在方法开头添加日志
old_code = '''    async def _update_position_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ):
        """更新持仓分析任务状态"""
        from app.core.database import get_mongo_db

        try:
            db = get_mongo_db()

            update_data = {
                "status": status,
                "message": message,
                "updated_at": datetime.now(),
            }'''

new_code = '''    async def _update_position_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ):
        """更新持仓分析任务状态"""
        logger.info(f"🔄 [持仓分析] 更新任务状态: task_id={task_id}, status={status}, has_result={result is not None}")
        from app.core.database import get_mongo_db

        try:
            db = get_mongo_db()
            logger.info(f"💾 [持仓分析] 准备更新数据库...")

            update_data = {
                "status": status,
                "message": message,
                "updated_at": datetime.now(),
            }'''

content = content.replace(old_code, new_code)

# 在 update_one 后添加日志
old_update = '''            await db.unified_analysis_tasks.update_one(
                {"task_id": task_id},
                {"$set": update_data}
            )

            # 更新内存状态'''

new_update = '''            result_obj = await db.unified_analysis_tasks.update_one(
                {"task_id": task_id},
                {"$set": update_data}
            )
            logger.info(f"✅ [持仓分析] 数据库更新完成: matched={result_obj.matched_count}, modified={result_obj.modified_count}")

            # 更新内存状态'''

content = content.replace(old_update, new_update)

# 在内存更新后添加日志
old_memory = '''            await memory_manager.update_task_status(
                task_id=task_id,
                status=memory_status,
                message=message or "",
            )

        except Exception as e:
            logger.error(f"❌ [持仓分析] 更新任务状态失败: {e}")'''

new_memory = '''            await memory_manager.update_task_status(
                task_id=task_id,
                status=memory_status,
                message=message or "",
            )
            logger.info(f"✅ [持仓分析] 内存状态更新完成")

        except Exception as e:
            logger.error(f"❌ [持仓分析] 更新任务状态失败: {e}", exc_info=True)'''

content = content.replace(old_memory, new_memory)

with open('app/services/unified_analysis_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 日志添加完成")

