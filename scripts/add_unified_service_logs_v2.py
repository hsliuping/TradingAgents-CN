#!/usr/bin/env python
"""
为统一分析服务添加详细日志 v2
"""

import sys
from pathlib import Path

# 读取文件
service_file = Path("app/services/unified_analysis_service.py")
with open(service_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 在关键位置插入日志
new_lines = []
for i, line in enumerate(lines, 1):
    new_lines.append(line)
    
    # 在 create_position_analysis_task 方法开头添加日志 (第 891 行后)
    if i == 891 and '"""' in line and i > 880:
        new_lines.append('        logger.info(f"🔧 [持仓分析服务] create_position_analysis_task 被调用: user_id={user_id}, code={code}, market={market}")\n')
    
    # 在生成 task_id 后添加日志 (第 895 行后)
    elif i == 895 and 'task_id = str(uuid.uuid4())' in line:
        new_lines.append('        logger.info(f"📝 [持仓分析服务] 生成任务ID: {task_id}")\n')
    
    # 在创建 UnifiedAnalysisTask 前添加日志 (第 898 行后)
    elif i == 898 and '# 创建统一分析任务' in line:
        new_lines.append('        logger.info(f"🔄 [持仓分析服务] 创建 UnifiedAnalysisTask 对象...")\n')
    
    # 在保存到数据库前添加日志 (第 913 行后)
    elif i == 913 and '# 保存到数据库' in line:
        new_lines.append('        logger.info(f"💾 [持仓分析服务] 准备保存到数据库...")\n')
    
    # 在 insert_one 后添加日志 (第 917 行后)
    elif i == 917 and 'await db.unified_analysis_tasks.insert_one(task_dict)' in line:
        new_lines.append('            logger.info(f"✅ [持仓分析服务] 已保存到数据库，任务ID: {task_id}")\n')
    
    # 修改第 918 行的日志
    elif i == 918 and 'logger.info(f"✅ [持仓分析] 任务已创建' in line:
        new_lines[-1] = '            logger.info(f"✅ [持仓分析服务] 任务已创建: {task_id} - {code}")\n'
    
    # 在保存到内存前添加日志 (第 923 行后)
    elif i == 923 and '# 保存到内存状态管理器' in line:
        new_lines.append('        logger.info(f"💾 [持仓分析服务] 准备保存到内存状态管理器...")\n')
    
    # 在内存保存后添加日志 (第 931 行后)
    elif i == 931 and ')' in line and i > 925 and i < 935:
        new_lines.append('        logger.info(f"✅ [持仓分析服务] 已保存到内存状态管理器")\n')
    
    # 在返回前添加日志 (第 933 行前)
    elif i == 933 and 'return {' in line:
        new_lines.insert(-1, '        logger.info(f"🎉 [持仓分析服务] 任务创建完成，准备返回结果")\n')
    
    # 在 execute_position_analysis 方法开头添加日志 (第 964 行后)
    elif i == 964 and 'logger.info(f"🚀 [持仓分析] 开始执行' in line:
        new_lines[-1] = '        logger.info(f"🚀 [持仓分析服务] execute_position_analysis 被调用: task_id={task_id}, code={code}")\n'
        new_lines.append('        logger.info(f"📋 [持仓分析服务] 任务参数: {task_params}")\n')

# 写回文件
with open(service_file, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('✅ 文件修改完成！')

