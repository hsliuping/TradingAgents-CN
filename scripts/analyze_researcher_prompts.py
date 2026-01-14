"""
从数据库读取多空辩论研究员的提示词，以产品经理角度分析优化建议

分析维度：
1. 提示词结构完整性
2. 约束文本重复情况
3. 可用报告列表是否明确
4. 提示词逻辑清晰度
5. 用户体验（LLM理解难度）
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_mongo_db_sync
from dotenv import load_dotenv
import logging
from typing import Dict, List, Any
import json

# 加载环境变量
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def analyze_prompt_structure(template: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析单个提示词模板的结构
    
    Returns:
        分析结果字典
    """
    content = template.get("content", {})
    agent_name = template.get("agent_name", "unknown")
    preference_type = template.get("preference_type", "unknown")
    template_name = template.get("template_name", "unknown")
    
    analysis = {
        "template_id": str(template.get("_id", "")),
        "template_name": template_name,
        "agent_name": agent_name,
        "preference_type": preference_type,
        "system_prompt": {
            "exists": "system_prompt" in content,
            "length": len(content.get("system_prompt", "")),
            "has_constraints": False,
            "constraints_text": "",
            "has_role_definition": False,
            "has_responsibilities": False,
            "issues": []
        },
        "user_prompt": {
            "exists": "user_prompt" in content,
            "length": len(content.get("user_prompt", "")),
            "has_constraints": False,
            "has_reports_info": False,
            "has_clear_instruction": False,
            "issues": []
        },
        "constraints": {
            "exists": "constraints" in content,
            "has_duplicate_constraints": False,
            "content": content.get("constraints", "")
        },
        "overall_issues": [],
        "optimization_suggestions": []
    }
    
    # 分析 system_prompt
    system_prompt = content.get("system_prompt", "")
    if system_prompt:
        analysis["system_prompt"]["has_role_definition"] = (
            "你是一位" in system_prompt or 
            "您是一位" in system_prompt or
            "你是" in system_prompt
        )
        analysis["system_prompt"]["has_responsibilities"] = (
            "职责" in system_prompt or 
            "需要" in system_prompt or
            "应该" in system_prompt
        )
        
        # 检查约束
        if "必须严格基于用户提示词中提供的实时分析报告" in system_prompt:
            analysis["system_prompt"]["has_constraints"] = True
            # 提取约束文本
            import re
            constraint_match = re.search(
                r'\*\*⚠️ 重要约束\*\*：?\n(- \*\*[^\n]+\*\*[^\n]*\n?)+',
                system_prompt
            )
            if constraint_match:
                analysis["system_prompt"]["constraints_text"] = constraint_match.group(0)
        
        # 检查问题
        if not analysis["system_prompt"]["has_role_definition"]:
            analysis["system_prompt"]["issues"].append("缺少角色定义")
        if not analysis["system_prompt"]["has_responsibilities"]:
            analysis["system_prompt"]["issues"].append("缺少职责说明")
        if not analysis["system_prompt"]["has_constraints"]:
            analysis["system_prompt"]["issues"].append("缺少约束说明")
    
    # 分析 user_prompt
    user_prompt = content.get("user_prompt", "")
    if user_prompt:
        # 检查约束（不应该有）
        if "必须严格基于" in user_prompt and ("重要要求" in user_prompt or "重要约束" in user_prompt):
            analysis["user_prompt"]["has_constraints"] = True
            analysis["user_prompt"]["issues"].append("包含约束文本（应该只在system_prompt中）")
        
        # 检查报告列表
        if "可用分析报告" in user_prompt or "📊 可用分析报告" in user_prompt:
            analysis["user_prompt"]["has_reports_info"] = True
        else:
            analysis["user_prompt"]["issues"].append("缺少可用报告列表说明")
        
        # 检查是否有清晰的指令
        if "请从" in user_prompt or "请分析" in user_prompt or "请撰写" in user_prompt:
            analysis["user_prompt"]["has_clear_instruction"] = True
        else:
            analysis["user_prompt"]["issues"].append("缺少清晰的任务指令")
    
    # 分析 constraints 字段
    constraints = content.get("constraints", "")
    if constraints:
        if "必须严格基于用户提示词中提供的实时分析报告" in constraints:
            analysis["constraints"]["has_duplicate_constraints"] = True
            analysis["overall_issues"].append("constraints字段包含重复的约束文本")
    
    # 检查整体问题：约束重复
    constraint_count = sum([
        analysis["system_prompt"]["has_constraints"],
        analysis["user_prompt"]["has_constraints"],
        analysis["constraints"]["has_duplicate_constraints"]
    ])
    
    if constraint_count > 1:
        analysis["overall_issues"].append(f"约束文本在{constraint_count}个地方重复出现")
    
    return analysis


def generate_optimization_suggestions(analysis: Dict[str, Any]) -> List[str]:
    """生成优化建议"""
    suggestions = []
    
    # 1. 约束重复问题
    constraint_locations = []
    if analysis["system_prompt"]["has_constraints"]:
        constraint_locations.append("system_prompt")
    if analysis["user_prompt"]["has_constraints"]:
        constraint_locations.append("user_prompt")
    if analysis["constraints"]["has_duplicate_constraints"]:
        constraint_locations.append("constraints字段")
    
    if len(constraint_locations) > 1:
        suggestions.append(
            f"🔴 **约束重复**：约束文本在 {', '.join(constraint_locations)} 中重复出现。"
            f"建议：只在 system_prompt 中保留约束，从 user_prompt 和 constraints 字段中移除。"
        )
    
    # 2. system_prompt 问题
    if not analysis["system_prompt"]["exists"]:
        suggestions.append("🔴 **缺少system_prompt**：必须定义系统提示词，包含角色、职责和约束。")
    else:
        if analysis["system_prompt"]["issues"]:
            suggestions.append(
                f"⚠️ **system_prompt不完整**：{', '.join(analysis['system_prompt']['issues'])}"
            )
    
    # 3. user_prompt 问题
    if not analysis["user_prompt"]["exists"]:
        suggestions.append("🔴 **缺少user_prompt**：必须定义用户提示词，包含任务指令和可用数据。")
    else:
        if analysis["user_prompt"]["issues"]:
            suggestions.append(
                f"⚠️ **user_prompt不完整**：{', '.join(analysis['user_prompt']['issues'])}"
            )
    
    # 4. 可用报告列表
    if not analysis["user_prompt"]["has_reports_info"]:
        suggestions.append(
            "💡 **缺少可用报告列表**：user_prompt中应该明确列出可用的分析报告类型"
            "（market_report、fundamentals_report、news_report等），帮助LLM理解可用数据。"
        )
    
    # 5. 提示词长度
    if analysis["system_prompt"]["length"] > 2000:
        suggestions.append(
            f"⚠️ **system_prompt过长**：当前长度 {analysis['system_prompt']['length']} 字符，"
            f"建议控制在1500字符以内，提高LLM理解效率。"
        )
    
    if analysis["user_prompt"]["length"] > 3000:
        suggestions.append(
            f"⚠️ **user_prompt过长**：当前长度 {analysis['user_prompt']['length']} 字符，"
            f"建议控制在2500字符以内，避免信息过载。"
        )
    
    return suggestions


def print_analysis_report(analyses: List[Dict[str, Any]]):
    """打印分析报告"""
    print("\n" + "="*80)
    print("📊 多空辩论研究员提示词分析报告（产品经理视角）")
    print("="*80)
    
    for i, analysis in enumerate(analyses, 1):
        print(f"\n{'─'*80}")
        print(f"📋 模板 {i}: {analysis['template_name']}")
        print(f"   Agent: {analysis['agent_name']} | 偏好类型: {analysis['preference_type']}")
        print(f"   Template ID: {analysis['template_id']}")
        print(f"{'─'*80}")
        
        # System Prompt 分析
        print(f"\n📝 System Prompt 分析:")
        print(f"   ✓ 存在: {'是' if analysis['system_prompt']['exists'] else '否'}")
        if analysis['system_prompt']['exists']:
            print(f"   ✓ 长度: {analysis['system_prompt']['length']} 字符")
            print(f"   ✓ 角色定义: {'是' if analysis['system_prompt']['has_role_definition'] else '否'}")
            print(f"   ✓ 职责说明: {'是' if analysis['system_prompt']['has_responsibilities'] else '否'}")
            print(f"   ✓ 包含约束: {'是' if analysis['system_prompt']['has_constraints'] else '否'}")
            if analysis['system_prompt']['issues']:
                print(f"   ⚠️ 问题: {', '.join(analysis['system_prompt']['issues'])}")
        
        # User Prompt 分析
        print(f"\n📝 User Prompt 分析:")
        print(f"   ✓ 存在: {'是' if analysis['user_prompt']['exists'] else '否'}")
        if analysis['user_prompt']['exists']:
            print(f"   ✓ 长度: {analysis['user_prompt']['length']} 字符")
            print(f"   ✓ 包含约束: {'是' if analysis['user_prompt']['has_constraints'] else '否'}")
            print(f"   ✓ 包含报告列表: {'是' if analysis['user_prompt']['has_reports_info'] else '否'}")
            print(f"   ✓ 清晰指令: {'是' if analysis['user_prompt']['has_clear_instruction'] else '否'}")
            if analysis['user_prompt']['issues']:
                print(f"   ⚠️ 问题: {', '.join(analysis['user_prompt']['issues'])}")
        
        # Constraints 字段分析
        print(f"\n📝 Constraints 字段分析:")
        print(f"   ✓ 存在: {'是' if analysis['constraints']['exists'] else '否'}")
        if analysis['constraints']['exists']:
            print(f"   ✓ 包含重复约束: {'是' if analysis['constraints']['has_duplicate_constraints'] else '否'}")
            if analysis['constraints']['has_duplicate_constraints']:
                print(f"   ⚠️ 问题: 包含与system_prompt重复的约束文本")
        
        # 整体问题
        if analysis['overall_issues']:
            print(f"\n🔴 整体问题:")
            for issue in analysis['overall_issues']:
                print(f"   • {issue}")
        
        # 优化建议
        suggestions = generate_optimization_suggestions(analysis)
        if suggestions:
            print(f"\n💡 优化建议:")
            for suggestion in suggestions:
                print(f"   {suggestion}")
        else:
            print(f"\n✅ 提示词结构良好，无需优化")
        
        # 显示约束文本（如果存在）
        if analysis['system_prompt']['constraints_text']:
            print(f"\n📄 System Prompt 中的约束文本:")
            print(f"   {analysis['system_prompt']['constraints_text'][:200]}...")
    
    # 总结
    print(f"\n{'='*80}")
    print("📊 总结")
    print(f"{'='*80}")
    
    total_templates = len(analyses)
    templates_with_issues = sum(1 for a in analyses if a['overall_issues'] or 
                               a['system_prompt']['issues'] or 
                               a['user_prompt']['issues'])
    
    print(f"   • 总模板数: {total_templates}")
    print(f"   • 需要优化的模板: {templates_with_issues}")
    print(f"   • 优化率: {templates_with_issues/total_templates*100:.1f}%")
    
    # 统计问题类型
    constraint_duplication_count = sum(
        1 for a in analyses 
        if (a['user_prompt']['has_constraints'] or 
            a['constraints']['has_duplicate_constraints'])
    )
    missing_reports_info_count = sum(
        1 for a in analyses 
        if not a['user_prompt']['has_reports_info']
    )
    
    print(f"\n   主要问题统计:")
    print(f"   • 约束重复: {constraint_duplication_count} 个模板")
    print(f"   • 缺少报告列表: {missing_reports_info_count} 个模板")


def main():
    """主函数"""
    db = get_mongo_db_sync()
    collection = db["prompt_templates"]
    
    # 查找所有看多和看空研究员的模板
    agent_names = ["bull_researcher_v2", "bear_researcher_v2"]
    
    all_analyses = []
    
    for agent_name in agent_names:
        logger.info(f"\n🔍 分析 {agent_name} 的模板...")
        
        templates = list(collection.find({"agent_name": agent_name}))
        logger.info(f"   找到 {len(templates)} 个模板")
        
        for template in templates:
            analysis = analyze_prompt_structure(template)
            all_analyses.append(analysis)
    
    # 打印分析报告
    print_analysis_report(all_analyses)
    
    # 可选：保存详细分析到JSON文件
    output_file = "researcher_prompts_analysis.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_analyses, f, ensure_ascii=False, indent=2)
    print(f"\n💾 详细分析结果已保存到: {output_file}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ 分析失败: {e}", exc_info=True)
        sys.exit(1)

