"""
导出提示词模板（合规修改前备份）

在修改提示词之前，先导出所有相关模板作为备份
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db, close_database
from datetime import datetime


def serialize_datetime(obj):
    """递归序列化 datetime 对象为字符串"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    else:
        return obj


async def export_prompts():
    """导出所有需要修改的提示词模板"""
    
    # 初始化数据库连接
    try:
        await init_database()
        db = get_mongo_db()
        collection = db.prompt_templates
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("   请确保 MongoDB 服务正在运行，并且 .env 文件配置正确")
        return
    
    # 需要导出的 Agent 类型
    agent_types = [
        "position_analysis",
        "position_analysis_v2",
        "trader_v2",
        "research_manager_v2",
        "risk_manager_v2",
        "managers_v2",  # research_manager_v2 可能使用这个类型
    ]
    
    # 创建导出目录
    export_dir = "exports/compliance_backup"
    os.makedirs(export_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = f"{export_dir}/prompts_backup_{timestamp}.json"
    
    all_templates = []
    total_count = 0
    
    print("=" * 80)
    print("导出提示词模板（合规修改前备份）")
    print("=" * 80)
    
    for agent_type in agent_types:
        print(f"\n🔍 查找 {agent_type} 的模板...")
        
        # 查找该类型的所有模板
        query = {"agent_type": agent_type}
        templates = await collection.find(query).to_list(length=None)
        
        print(f"   找到 {len(templates)} 个模板")
        
        for template in templates:
            # 使用序列化函数处理所有 datetime 对象
            template_doc = {
                "_id": str(template.get("_id")),
                "agent_type": template.get("agent_type"),
                "agent_name": template.get("agent_name"),
                "template_name": template.get("template_name"),
                "preference_type": template.get("preference_type"),
                "content": serialize_datetime(template.get("content", {})),
                "created_at": serialize_datetime(template.get("created_at")),
                "updated_at": serialize_datetime(template.get("updated_at")),
            }
            all_templates.append(template_doc)
            total_count += 1
            
            # 打印模板信息
            agent_name = template.get("agent_name", "unknown")
            template_name = template.get("template_name", "unknown")
            print(f"   ✅ {agent_name} - {template_name}")
    
    # 保存到文件
    export_data = {
        "export_time": datetime.now().isoformat(),
        "description": "合规修改前的提示词模板备份",
        "total_count": total_count,
        "agent_types": agent_types,
        "templates": all_templates
    }
    
    with open(export_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 导出完成！")
    print(f"   文件路径: {export_file}")
    print(f"   模板数量: {total_count}")
    print(f"\n📋 导出的模板列表:")
    for template in all_templates:
        print(f"   - {template['agent_type']}/{template['agent_name']} ({template.get('template_name', 'N/A')})")
    
    # 同时创建一个按 Agent 类型分组的导出
    grouped_file = f"{export_dir}/prompts_backup_grouped_{timestamp}.json"
    grouped_data = {}
    for template in all_templates:
        agent_type = template["agent_type"]
        if agent_type not in grouped_data:
            grouped_data[agent_type] = []
        grouped_data[agent_type].append(template)
    
    with open(grouped_file, "w", encoding="utf-8") as f:
        json.dump({
            "export_time": datetime.now().isoformat(),
            "description": "按 Agent 类型分组的提示词模板备份",
            "total_count": total_count,
            "grouped_templates": grouped_data
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 分组导出完成！")
    print(f"   文件路径: {grouped_file}")
    
    # 关闭数据库连接
    await close_database()
    
    return export_file, grouped_file


async def export_specific_prompts(agent_names: list = None):
    """导出特定 Agent 的提示词"""
    
    # 初始化数据库连接
    try:
        await init_database()
        db = get_mongo_db()
        collection = db.prompt_templates
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return
    
    # 如果指定了 agent_names，只导出这些
    if agent_names:
        query = {"agent_name": {"$in": agent_names}}
    else:
        # 导出所有相关 Agent
        query = {
            "agent_name": {
                "$in": [
                    "pa_advisor",
                    "pa_advisor_v2",
                    "trader_v2",
                    "research_manager_v2",
                    "risk_manager_v2"
                ]
            }
        }
    
    templates = await collection.find(query).to_list(length=None)
    
    export_dir = "exports/compliance_backup"
    os.makedirs(export_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = f"{export_dir}/prompts_specific_{timestamp}.json"
    
    export_data = {
        "export_time": datetime.now().isoformat(),
        "description": "特定 Agent 的提示词模板备份",
        "query": str(query),
        "templates": []
    }
    
    for template in templates:
        # 使用序列化函数处理所有 datetime 对象
        template_doc = {
            "_id": str(template.get("_id")),
            "agent_type": template.get("agent_type"),
            "agent_name": template.get("agent_name"),
            "template_name": template.get("template_name"),
            "preference_type": template.get("preference_type"),
            "content": serialize_datetime(template.get("content", {})),
            "created_at": serialize_datetime(template.get("created_at")),
            "updated_at": serialize_datetime(template.get("updated_at")),
        }
        export_data["templates"].append(template_doc)
    
    with open(export_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 导出完成: {export_file}")
    print(f"   模板数量: {len(export_data['templates'])}")
    
    # 关闭数据库连接
    await close_database()
    return export_file


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "specific":
        # 导出特定 Agent
        agent_names = sys.argv[2:] if len(sys.argv) > 2 else None
        asyncio.run(export_specific_prompts(agent_names))
    else:
        # 导出所有相关模板
        asyncio.run(export_prompts())
