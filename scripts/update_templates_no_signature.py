"""
更新提示词模板，在constraints字段中添加禁止生成署名信息的要求

本脚本会更新所有Agent的提示词模板，在constraints字段中添加禁止生成署名信息的约束。
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 如果dotenv不可用，尝试直接设置环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有dotenv，尝试从.env文件手动加载
    env_file = project_root / '.env'
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

from app.core.database import init_database, close_database, get_mongo_db


async def update_templates():
    """更新所有模板的约束条件"""
    # 初始化MongoDB连接
    await init_database()
    
    db = get_mongo_db()
    templates_collection = db.prompt_templates
    
    print("=" * 80)
    print("开始更新提示词模板约束条件")
    print("=" * 80)
    
    # 新的约束条件文本（追加到现有约束条件后面）
    new_constraint = "\n\n⚠️ **重要约束**：本报告由AI自动生成，禁止在报告中添加任何署名信息（如'撰写人'、'分析师'、'日期'、'声明'等）。禁止生成任何虚假的人名、作者信息或署名。报告内容应直接开始，无需添加任何署名、日期或声明信息。"
    
    # 查找所有模板
    templates = await templates_collection.find({}).to_list(length=None)
    
    total_updated = 0
    skipped = 0
    
    for template in templates:
        template_id = template["_id"]
        agent_name = template.get("agent_name", "unknown")
        preference_type = template.get("preference_type", "default")
        
        # 获取当前的constraints
        content = template.get("content", {})
        current_constraints = content.get("constraints", "")
        
        # 检查是否已经包含新的约束条件（避免重复添加）
        if "禁止在报告中添加任何署名信息" in current_constraints:
            print(f"⏭️  跳过 {agent_name} ({preference_type}): 已包含约束条件")
            skipped += 1
            continue
        
        # 追加新的约束条件
        if current_constraints:
            updated_constraints = current_constraints + new_constraint
        else:
            updated_constraints = new_constraint.strip()
        
        # 更新模板
        result = await templates_collection.update_one(
            {"_id": template_id},
            {"$set": {
                "content.constraints": updated_constraints,
                "updated_at": datetime.now()
            }}
        )
        
        if result.modified_count > 0:
            print(f"✅ 更新 {agent_name} ({preference_type}): 已添加禁止署名约束")
            total_updated += 1
        else:
            print(f"⚠️  更新失败 {agent_name} ({preference_type})")
    
    print("\n" + "=" * 80)
    print("更新完成")
    print("=" * 80)
    print(f"总共更新: {total_updated} 个模板")
    print(f"已跳过: {skipped} 个模板（已包含约束条件）")
    print(f"总计: {len(templates)} 个模板")
    print("=" * 80)
    
    # 关闭MongoDB连接
    await close_database()


if __name__ == "__main__":
    asyncio.run(update_templates())
