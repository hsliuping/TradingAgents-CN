"""
更新v2.0系统模板，添加禁止生成署名信息的约束条件

本脚本会更新所有v2.0 Agent的提示词模板，在constraints字段中添加禁止生成署名信息的要求。
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv()

from app.core.database import init_database, close_database, get_mongo_db


async def update_templates():
    """更新所有v2.0模板的约束条件"""
    # 初始化MongoDB连接
    await init_database()
    
    db = get_mongo_db()
    templates_collection = db.prompt_templates
    
    # v2.0 agent类型列表
    v2_agent_types = [
        "analysts_v2",
        "researchers_v2",
        "managers_v2",
        "trader_v2",
        "debators_v2",
        "reviewers_v2",
        "position_analysis_v2",
    ]
    
    print("=" * 80)
    print("开始更新v2.0系统模板约束条件")
    print("=" * 80)
    
    # 新的约束条件文本（追加到现有约束条件后面）
    new_constraint = """

⚠️ **重要约束**：
- 本报告由AI自动生成，禁止在报告中添加任何署名信息（如"撰写人"、"分析师"、"日期"、"声明"等）
- 禁止生成任何虚假的人名、作者信息或署名
- 报告内容应直接开始，无需添加任何署名、日期或声明信息"""
    
    total_updated = 0
    
    for agent_type in v2_agent_types:
        # 查找所有该类型的系统模板
        templates = await templates_collection.find({
            "agent_type": agent_type,
            "is_system": True
        }).to_list(length=None)
        
        for template in templates:
            template_id = template["_id"]
            current_constraints = template.get("content", {}).get("constraints", "")
            
            # 检查是否已经包含新的约束条件（避免重复添加）
            if "禁止在报告中添加任何署名信息" in current_constraints:
                print(f"⏭️  跳过 {template['agent_name']} ({template.get('preference_type', 'default')}): 已包含约束条件")
                continue
            
            # 追加新的约束条件
            updated_constraints = current_constraints + new_constraint if current_constraints else new_constraint.strip()
            
            # 更新模板
            result = await templates_collection.update_one(
                {"_id": template_id},
                {"$set": {
                    "content.constraints": updated_constraints,
                    "updated_at": template.get("updated_at")  # 保持原更新时间，或者可以更新为当前时间
                }}
            )
            
            if result.modified_count > 0:
                print(f"✅ 更新 {template['agent_name']} ({template.get('preference_type', 'default')}): 已添加禁止署名约束")
                total_updated += 1
            else:
                print(f"⚠️  更新失败 {template['agent_name']} ({template.get('preference_type', 'default')})")
    
    print("\n" + "=" * 80)
    print("更新完成")
    print("=" * 80)
    print(f"总共更新: {total_updated} 个模板")
    print("=" * 80)
    
    # 关闭MongoDB连接
    await close_database()


if __name__ == "__main__":
    asyncio.run(update_templates())
