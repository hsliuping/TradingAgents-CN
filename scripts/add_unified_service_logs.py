#!/usr/bin/env python
"""
为统一分析服务添加详细日志
"""

import sys
from pathlib import Path

# 读取文件
service_file = Path("app/services/unified_analysis_service.py")
with open(service_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 修改 create_position_analysis_task 方法
old_create = '''    async def create_position_analysis_task(
        self,
        user_id: str,
        code: str,
        market: str = "CN",
        task_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建持仓分析任务"""
        from bson import ObjectId
        from app.core.database import get_mongo_db
        
        task_id = str(uuid.uuid4())
        task_params = task_params or {}
        
        # 创建统一分析任务
        task = UnifiedAnalysisTask('''

new_create = '''    async def create_position_analysis_task(
        self,
        user_id: str,
        code: str,
        market: str = "CN",
        task_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建持仓分析任务"""
        logger.info(f"🔧 [持仓分析服务] create_position_analysis_task 被调用: user_id={user_id}, code={code}, market={market}")
        
        from bson import ObjectId
        from app.core.database import get_mongo_db
        
        task_id = str(uuid.uuid4())
        task_params = task_params or {}
        logger.info(f"📝 [持仓分析服务] 生成任务ID: {task_id}")
        
        # 创建统一分析任务
        logger.info(f"🔄 [持仓分析服务] 创建 UnifiedAnalysisTask 对象...")
        task = UnifiedAnalysisTask('''

# 2. 在保存到数据库后添加日志
old_save_db = '''        # 保存到数据库
        db = get_mongo_db()
        task_dict = task.model_dump(by_alias=True, exclude={"id"})
        await db.unified_analysis_tasks.insert_one(task_dict)
        
        # 保存到内存状态管理器'''

new_save_db = '''        # 保存到数据库
        logger.info(f"💾 [持仓分析服务] 准备保存到数据库...")
        db = get_mongo_db()
        task_dict = task.model_dump(by_alias=True, exclude={"id"})
        logger.info(f"📋 [持仓分析服务] 任务字典: {list(task_dict.keys())}")
        result = await db.unified_analysis_tasks.insert_one(task_dict)
        logger.info(f"✅ [持仓分析服务] 已保存到数据库: _id={result.inserted_id}")
        
        # 保存到内存状态管理器
        logger.info(f"💾 [持仓分析服务] 准备保存到内存状态管理器...")'''

# 3. 在返回结果前添加日志
old_return = '''        logger.info(f"✅ [持仓分析] 任务已创建: {task_id} - {code}")
        
        return {
            "task_id": task_id,'''

new_return = '''        logger.info(f"✅ [持仓分析服务] 任务创建完成: {task_id} - {code}")
        
        result_dict = {
            "task_id": task_id,'''

# 4. 在 execute_position_analysis 开始添加更多日志
old_execute = '''    async def execute_position_analysis(
        self,
        task_id: str,
        user_id: str,
        code: str,
        market: str = "CN",
        task_params: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """执行持仓分析

        Args:
            task_id: 任务ID
            user_id: 用户ID
            code: 股票代码
            market: 市场类型
            task_params: 任务参数
            progress_callback: 进度回调函数

        Returns:
            分析结果字典
        """
        logger.info(f"🚀 [持仓分析] 开始执行: {task_id} - {code}")

        try:'''

new_execute = '''    async def execute_position_analysis(
        self,
        task_id: str,
        user_id: str,
        code: str,
        market: str = "CN",
        task_params: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """执行持仓分析

        Args:
            task_id: 任务ID
            user_id: 用户ID
            code: 股票代码
            market: 市场类型
            task_params: 任务参数
            progress_callback: 进度回调函数

        Returns:
            分析结果字典
        """
        logger.info(f"🚀 [持仓分析服务] execute_position_analysis 被调用: task_id={task_id}, code={code}")
        logger.info(f"📋 [持仓分析服务] 任务参数: {task_params}")

        try:
            logger.info(f"🔄 [持仓分析服务] 开始执行分析流程...")'''

# 执行替换
replacements = [
    (old_create, new_create, "create_position_analysis_task 方法开头"),
    (old_save_db, new_save_db, "保存到数据库部分"),
    (old_return, new_return, "返回结果部分"),
    (old_execute, new_execute, "execute_position_analysis 方法开头"),
]

success_count = 0
for old, new, desc in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"✅ 替换成功: {desc}")
        success_count += 1
    else:
        print(f"❌ 未找到: {desc}")

if success_count == len(replacements):
    # 写回文件
    with open(service_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n✅ 文件修改完成！成功替换 {success_count}/{len(replacements)} 处")
else:
    print(f"\n⚠️ 只成功替换了 {success_count}/{len(replacements)} 处，未写入文件")
    sys.exit(1)

