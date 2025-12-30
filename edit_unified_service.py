#!/usr/bin/env python
"""临时编辑脚本"""
import re

# 读取文件
with open('app/services/unified_analysis_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在方法开头添加日志
content = content.replace(
    '        """\n        from bson import ObjectId',
    '        """\n        logger.info(f"🔧 [持仓分析服务] create_position_analysis_task 被调用: user_id={user_id}, code={code}, market={market}")\n        from bson import ObjectId'
)

# 2. 在生成task_id后添加日志
content = content.replace(
    '        task_id = str(uuid.uuid4())\n        task_params = task_params or {}',
    '        task_id = str(uuid.uuid4())\n        logger.info(f"📝 [持仓分析服务] 生成任务ID: {task_id}")\n        task_params = task_params or {}'
)

# 3. 在创建任务前添加日志
content = content.replace(
    '        # 创建统一分析任务\n        task = UnifiedAnalysisTask(',
    '        # 创建统一分析任务\n        logger.info(f"🔄 [持仓分析服务] 创建 UnifiedAnalysisTask 对象...")\n        task = UnifiedAnalysisTask('
)

# 4. 在保存到数据库前添加日志
content = content.replace(
    '        # 保存到数据库\n        try:\n            db = get_mongo_db()',
    '        # 保存到数据库\n        logger.info(f"💾 [持仓分析服务] 准备保存到数据库...")\n        try:\n            db = get_mongo_db()'
)

# 5. 在insert_one后添加日志
content = content.replace(
    '            await db.unified_analysis_tasks.insert_one(task_dict)\n            logger.info(f"✅ [持仓分析] 任务已创建: {task_id} - {code}")',
    '            await db.unified_analysis_tasks.insert_one(task_dict)\n            logger.info(f"✅ [持仓分析服务] 已保存到数据库: {task_id}")\n            logger.info(f"✅ [持仓分析服务] 任务已创建: {task_id} - {code}")'
)

# 6. 在保存到内存前添加日志
content = content.replace(
    '        # 保存到内存状态管理器\n        memory_manager = get_memory_state_manager()',
    '        # 保存到内存状态管理器\n        logger.info(f"💾 [持仓分析服务] 准备保存到内存状态管理器...")\n        memory_manager = get_memory_state_manager()'
)

# 7. 在内存保存后添加日志
content = content.replace(
    '            parameters=task_params,\n        )\n\n        return {',
    '            parameters=task_params,\n        )\n        logger.info(f"✅ [持仓分析服务] 已保存到内存状态管理器")\n\n        logger.info(f"🎉 [持仓分析服务] 任务创建完成，准备返回结果")\n        return {'
)

# 8. 修改execute方法的日志
content = content.replace(
    '        logger.info(f"🚀 [持仓分析] 开始执行: {task_id} - {code}")\n\n        try:',
    '        logger.info(f"🚀 [持仓分析服务] execute_position_analysis 被调用: task_id={task_id}, code={code}")\n        logger.info(f"📋 [持仓分析服务] 任务参数: {task_params}")\n\n        try:\n            logger.info(f"🔄 [持仓分析服务] 开始执行分析流程...")'
)

# 写回文件
with open('app/services/unified_analysis_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 文件修改完成")

