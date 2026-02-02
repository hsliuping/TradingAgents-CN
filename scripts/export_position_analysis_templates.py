"""
导出持仓分析相关的提示词模板

导出范围：
1. position_analysis_v2 类型的所有模板
2. 包括 pa_technical_v2 和 pa_fundamental_v2
3. 包括所有 preference_type（aggressive, neutral, conservative, with_cache_*, without_cache_*）
"""

import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_mongo_db_sync
from bson import ObjectId

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 ObjectId 和 datetime"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def export_templates():
    """导出相关模板"""
    db = get_mongo_db_sync()
    templates_collection = db.prompt_templates
    
    # 需要导出的 Agent
    agents_to_export = [
        {"agent_type": "position_analysis_v2", "agent_name": "pa_technical_v2"},
        {"agent_type": "position_analysis_v2", "agent_name": "pa_fundamental_v2"},
    ]
    
    all_templates = []
    
    for agent_info in agents_to_export:
        agent_type = agent_info["agent_type"]
        agent_name = agent_info["agent_name"]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"导出 Agent: {agent_type}/{agent_name}")
        logger.info(f"{'='*60}")
        
        # 查询该 Agent 的所有模板
        query = {
            "agent_type": agent_type,
            "agent_name": agent_name
        }
        
        templates = list(templates_collection.find(query).sort("preference_type", 1))
        
        logger.info(f"找到 {len(templates)} 个模板")
        
        for template in templates:
            template_data = {
                "_id": str(template.get("_id")),
                "agent_type": template.get("agent_type"),
                "agent_name": template.get("agent_name"),
                "template_name": template.get("template_name"),
                "preference_type": template.get("preference_type"),
                "is_system": template.get("is_system", False),
                "status": template.get("status"),
                "version": template.get("version", 1),
                "created_at": template.get("created_at"),
                "updated_at": template.get("updated_at"),
                "content": template.get("content", {}),
                "remark": template.get("remark", ""),
            }
            
            # 分析内容结构
            content = template_data["content"]
            content_fields = list(content.keys()) if content else []
            content_field_count = len(content_fields)
            
            logger.info(f"\n📋 模板: {template_data['template_name']}")
            logger.info(f"   preference_type: {template_data['preference_type']}")
            logger.info(f"   内容字段数: {content_field_count}")
            logger.info(f"   内容字段: {content_fields}")
            
            # 检查关键字段是否存在
            has_system_prompt = "system_prompt" in content
            has_user_prompt = "user_prompt" in content
            has_tool_guidance = "tool_guidance" in content
            has_analysis_requirements = "analysis_requirements" in content
            has_output_format = "output_format" in content
            
            logger.info(f"   ✅ system_prompt: {has_system_prompt} ({len(content.get('system_prompt', ''))} 字符)" if has_system_prompt else f"   ❌ system_prompt: 缺失")
            logger.info(f"   ✅ user_prompt: {has_user_prompt} ({len(content.get('user_prompt', ''))} 字符)" if has_user_prompt else f"   ❌ user_prompt: 缺失")
            logger.info(f"   ✅ tool_guidance: {has_tool_guidance} ({len(content.get('tool_guidance', ''))} 字符)" if has_tool_guidance else f"   ❌ tool_guidance: 缺失")
            logger.info(f"   ✅ analysis_requirements: {has_analysis_requirements} ({len(content.get('analysis_requirements', ''))} 字符)" if has_analysis_requirements else f"   ❌ analysis_requirements: 缺失")
            logger.info(f"   ✅ output_format: {has_output_format} ({len(content.get('output_format', ''))} 字符)" if has_output_format else f"   ❌ output_format: 缺失")
            
            # 显示内容预览（前200字符）
            if has_system_prompt:
                system_preview = content.get("system_prompt", "")[:200]
                logger.info(f"   📝 system_prompt 预览: {system_preview}...")
            if has_user_prompt:
                user_preview = content.get("user_prompt", "")[:200]
                logger.info(f"   📝 user_prompt 预览: {user_preview}...")
            
            all_templates.append(template_data)
    
    # 保存到文件
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"position_analysis_templates_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_templates, f, ensure_ascii=False, indent=2, cls=JSONEncoder)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ 导出完成！")
    logger.info(f"   文件路径: {output_file}")
    logger.info(f"   模板总数: {len(all_templates)}")
    logger.info(f"{'='*60}")
    
    # 生成分析报告
    generate_analysis_report(all_templates, output_dir, timestamp)
    
    return output_file


def generate_analysis_report(templates: List[Dict[str, Any]], output_dir: Path, timestamp: str):
    """生成分析报告"""
    report_lines = []
    report_lines.append("# 持仓分析提示词模板分析报告\n")
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append(f"模板总数: {len(templates)}\n\n")
    
    # 按 Agent 分组
    agents = {}
    for template in templates:
        agent_key = f"{template['agent_type']}/{template['agent_name']}"
        if agent_key not in agents:
            agents[agent_key] = []
        agents[agent_key].append(template)
    
    for agent_key, agent_templates in agents.items():
        report_lines.append(f"## {agent_key}\n")
        report_lines.append(f"模板数量: {len(agent_templates)}\n\n")
        
        # 按 preference_type 分类
        pref_groups = {}
        for template in agent_templates:
            pref_type = template.get("preference_type") or "null"
            if pref_type not in pref_groups:
                pref_groups[pref_type] = []
            pref_groups[pref_type].append(template)
        
        for pref_type, pref_templates in sorted(pref_groups.items()):
            report_lines.append(f"### preference_type: {pref_type}\n")
            
            for template in pref_templates:
                content = template.get("content", {})
                content_fields = list(content.keys())
                
                report_lines.append(f"#### {template['template_name']}\n")
                report_lines.append(f"- **ID**: `{template['_id']}`\n")
                report_lines.append(f"- **状态**: {template['status']}\n")
                report_lines.append(f"- **版本**: {template['version']}\n")
                report_lines.append(f"- **内容字段数**: {len(content_fields)}\n")
                report_lines.append(f"- **内容字段**: {', '.join(content_fields)}\n")
                
                # 检查完整性
                required_fields = ["system_prompt", "user_prompt", "tool_guidance", "analysis_requirements", "output_format"]
                missing_fields = [f for f in required_fields if f not in content_fields]
                
                if missing_fields:
                    report_lines.append(f"- **⚠️ 缺失字段**: {', '.join(missing_fields)}\n")
                else:
                    report_lines.append(f"- **✅ 结构完整**\n")
                
                # 字段长度统计
                if "system_prompt" in content:
                    report_lines.append(f"- **system_prompt 长度**: {len(content.get('system_prompt', ''))} 字符\n")
                if "user_prompt" in content:
                    report_lines.append(f"- **user_prompt 长度**: {len(content.get('user_prompt', ''))} 字符\n")
                
                report_lines.append("\n")
    
    # 问题总结
    report_lines.append("## 问题总结\n\n")
    
    # 统计缺失字段的模板
    incomplete_templates = []
    for template in templates:
        content = template.get("content", {})
        required_fields = ["system_prompt", "user_prompt"]
        missing_fields = [f for f in required_fields if f not in content]
        if missing_fields:
            incomplete_templates.append({
                "template": template,
                "missing_fields": missing_fields
            })
    
    if incomplete_templates:
        report_lines.append(f"### ⚠️ 结构不完整的模板 ({len(incomplete_templates)} 个)\n\n")
        for item in incomplete_templates:
            template = item["template"]
            missing = item["missing_fields"]
            report_lines.append(f"- **{template['template_name']}** (`{template['preference_type']}`)\n")
            report_lines.append(f"  - 缺失字段: {', '.join(missing)}\n")
            report_lines.append(f"  - Agent: {template['agent_type']}/{template['agent_name']}\n")
            report_lines.append(f"  - ID: `{template['_id']}`\n\n")
    else:
        report_lines.append("### ✅ 所有模板结构完整\n\n")
    
    # 对比分析
    report_lines.append("## 对比分析\n\n")
    
    # 对比 with_cache 和 without_cache 模板
    for agent_key, agent_templates in agents.items():
        report_lines.append(f"### {agent_key}\n\n")
        
        # 查找旧版模板（aggressive/neutral/conservative）
        old_templates = {t["preference_type"]: t for t in agent_templates 
                        if t.get("preference_type") in ["aggressive", "neutral", "conservative"]}
        
        # 查找新版模板（with_cache_*/without_cache_*）
        new_templates = {t["preference_type"]: t for t in agent_templates 
                        if t.get("preference_type", "").startswith(("with_cache_", "without_cache_"))}
        
        if old_templates and new_templates:
            report_lines.append("#### 旧版模板（参考模板）\n\n")
            for pref_type, template in sorted(old_templates.items()):
                content = template.get("content", {})
                report_lines.append(f"- **{pref_type}**: {len(content)} 个字段\n")
            
            report_lines.append("\n#### 新版模板（需要修复）\n\n")
            for pref_type, template in sorted(new_templates.items()):
                content = template.get("content", {})
                missing = [f for f in ["system_prompt", "user_prompt"] if f not in content]
                status = "❌ 不完整" if missing else "✅ 完整"
                report_lines.append(f"- **{pref_type}**: {len(content)} 个字段 {status}\n")
                if missing:
                    report_lines.append(f"  - 缺失: {', '.join(missing)}\n")
    
    # 保存报告
    report_file = output_dir / f"position_analysis_templates_analysis_{timestamp}.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("".join(report_lines))
    
    logger.info(f"📊 分析报告已生成: {report_file}")
    
    return report_file


if __name__ == "__main__":
    logger.info("开始导出持仓分析提示词模板...")
    try:
        output_file = export_templates()
        logger.info(f"\n✅ 导出完成！文件: {output_file}")
    except Exception as e:
        logger.error(f"\n❌ 导出失败: {e}", exc_info=True)
