"""
提示词合规修改脚本

将提示词中的"目标价"和"操作建议"改为合规表述
"""

import asyncio
import re
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db, close_database

# 术语替换映射 - 按长度降序排列，避免短词先替换导致长词无法匹配
TERM_REPLACEMENTS = {
    # 目标价格相关（长词优先）
    "目标价格": "价格分析区间",
    "目标价位": "价格分析区间",
    "目标价": "价格分析区间",
    "第一目标价": "第一参考价位区间",
    "第二目标价": "第二参考价位区间",
    "止损价位": "风险控制参考价位",
    "止盈价位": "收益预期参考价位",
    "stop_loss_price": "risk_reference_price",
    "take_profit_price": "profit_reference_price",
    "target_price": "price_analysis_range",

    # 建议相关（长词优先）
    "投资建议": "分析观点",
    "交易建议": "交易分析观点",
    "操作建议": "持仓分析观点",
    "具体建议": "分析要点",
    "建议价格": "参考价格",
    "建议止损价": "风险控制参考价位",
    "建议止盈价": "收益预期参考价位",
    "建议止损": "风险控制参考",
    "建议止盈": "收益预期参考",

    # 操作相关（长词优先）
    "recommended_action": "market_view",
    "操作比例": "风险敞口分析",
    "action_ratio": "risk_exposure_analysis",
    "仓位比例": "风险敞口比例",
    "position_ratio": "risk_exposure_ratio",
    "仓位配置": "风险敞口配置",
    "仓位分析": "风险敞口分析",
    "仓位管理": "风险敞口管理",
    "仓位": "风险敞口",

    # 买卖操作（长词优先）
    "建议买入": "偏多观点",
    "建议卖出": "偏空观点",
    "建议持有": "中性观点",
    "买入时机": "入场时机分析",
    "卖出时机": "离场时机分析",
    "买入": "看涨",
    "卖出": "看跌",
    "持有": "中性",
    "加仓": "增持观点",
    "减仓": "减持观点",
    "清仓": "观望观点",
    "建仓": "建立观察",

    # 止损止盈
    "止损线": "风险控制线",
    "止盈线": "收益预期线",
    "止损": "风险控制参考",
    "止盈": "收益预期参考",
    "stop_loss": "risk_control_reference",
    "take_profit": "profit_expectation_reference",

    # 交易相关术语
    "交易方向": "市场观点方向",
    "交易指令": "交易分析",
    "交易计划": "交易分析计划",
    "trading_direction": "market_view_direction",
    "trading_instruction": "trading_analysis",
    "trading_plan": "trading_analysis_plan",
    "生成具体的交易计划": "生成交易分析计划",
    "生成具体的交易指令": "生成交易分析",
    "确定交易方向": "分析市场观点",
}

# 免责声明
DISCLAIMER = """
**免责声明**：
本分析报告仅供参考，不构成投资建议。所有价格区间、市场观点均为分析参考，
不构成买卖操作建议。投资有风险，决策需谨慎。投资者应根据自身情况，结合
专业投资顾问意见，独立做出投资决策。
"""


def replace_terms(text: str) -> str:
    """替换文本中的术语"""
    result = text
    for old_term, new_term in TERM_REPLACEMENTS.items():
        # 使用正则表达式进行替换，保持大小写
        pattern = re.compile(re.escape(old_term), re.IGNORECASE)
        result = pattern.sub(new_term, result)
    return result


def update_json_format(text: str) -> str:
    """更新 JSON 格式中的字段名"""
    # 替换 JSON 字段名
    replacements = {
        '"target_price"': '"price_analysis_range"',
        '"stop_loss_price"': '"risk_reference_price"',
        '"take_profit_price"': '"profit_reference_price"',
        '"stop_loss"': '"risk_control_reference"',
        '"take_profit"': '"profit_expectation_reference"',
        '"action"': '"analysis_view"',
        '"action_ratio"': '"risk_exposure_analysis"',
        '"position_ratio"': '"risk_exposure_ratio"',
        '"recommended_action"': '"market_view"',
        '"trading_plan"': '"trading_analysis_plan"',
        '"trading_instruction"': '"trading_analysis"',
        '"investment_advice"': '"analysis_opinion"',
    }

    result = text
    for old_field, new_field in replacements.items():
        result = result.replace(old_field, new_field)

    return result


def add_disclaimer(text: str) -> str:
    """在提示词末尾添加免责声明"""
    if DISCLAIMER.strip() not in text:
        return text + "\n\n" + DISCLAIMER
    return text


async def update_prompt_templates():
    """更新数据库中的提示词模板"""
    
    # 初始化数据库连接
    try:
        await init_database()
        db = get_mongo_db()
        collection = db.prompt_templates
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("   请确保 MongoDB 服务正在运行，并且 .env 文件配置正确")
        return
    
    # 需要更新的 Agent 类型（覆盖所有有敏感词的类型）
    agent_types = [
        # 分析师
        "analysts",
        "analysts_v2",
        # 研究员
        "researchers",
        "researchers_v2",
        # 交易员
        "trader",
        "trader_v2",
        # 管理者
        "managers",
        "managers_v2",
        # 辩论者
        "debators",
        "debators_v2",
        # 持仓分析
        "position_analysis",
        "position_analysis_v2",
        # 复盘分析
        "reviewers",
        "reviewers_v2",
    ]
    
    updated_count = 0
    
    for agent_type in agent_types:
        print(f"\n🔍 查找 {agent_type} 的模板...")
        
        # 查找该类型的所有模板
        query = {"agent_type": agent_type}
        templates = await collection.find(query).to_list(length=None)
        
        print(f"   找到 {len(templates)} 个模板")
        
        for template in templates:
            template_id = template.get("_id")
            agent_name = template.get("agent_name", "unknown")
            
            print(f"\n   📝 更新模板: {agent_name} (ID: {template_id})")
            
            # 更新各个字段
            updated = False
            update_doc = {}
            
            # 更新 system_prompt
            if "content" in template and "system_prompt" in template["content"]:
                old_system = template["content"]["system_prompt"]
                new_system = replace_terms(old_system)
                new_system = update_json_format(new_system)
                new_system = add_disclaimer(new_system)
                
                if old_system != new_system:
                    update_doc["content.system_prompt"] = new_system
                    updated = True
                    print(f"      ✅ 更新 system_prompt")
            
            # 更新 analysis_requirements
            if "content" in template and "analysis_requirements" in template["content"]:
                old_req = template["content"]["analysis_requirements"]
                new_req = replace_terms(old_req)
                new_req = update_json_format(new_req)
                
                if old_req != new_req:
                    update_doc["content.analysis_requirements"] = new_req
                    updated = True
                    print(f"      ✅ 更新 analysis_requirements")
            
            # 更新 output_format
            if "content" in template and "output_format" in template["content"]:
                old_format = template["content"]["output_format"]
                new_format = replace_terms(old_format)
                new_format = update_json_format(new_format)
                
                if old_format != new_format:
                    update_doc["content.output_format"] = new_format
                    updated = True
                    print(f"      ✅ 更新 output_format")
            
            # 更新 tool_guidance
            if "content" in template and "tool_guidance" in template["content"]:
                old_guidance = template["content"]["tool_guidance"]
                new_guidance = replace_terms(old_guidance)

                if old_guidance != new_guidance:
                    update_doc["content.tool_guidance"] = new_guidance
                    updated = True
                    print(f"      ✅ 更新 tool_guidance")

            # 更新 user_prompt
            if "content" in template and "user_prompt" in template["content"]:
                old_user = template["content"]["user_prompt"]
                new_user = replace_terms(old_user)
                new_user = update_json_format(new_user)

                if old_user != new_user:
                    update_doc["content.user_prompt"] = new_user
                    updated = True
                    print(f"      ✅ 更新 user_prompt")

            # 更新 constraints
            if "content" in template and "constraints" in template["content"]:
                old_constraints = template["content"]["constraints"]
                new_constraints = replace_terms(old_constraints)

                if old_constraints != new_constraints:
                    update_doc["content.constraints"] = new_constraints
                    updated = True
                    print(f"      ✅ 更新 constraints")
            
            # 执行更新
            if updated:
                await collection.update_one(
                    {"_id": template_id},
                    {"$set": update_doc}
                )
                updated_count += 1
                print(f"      ✅ 模板更新完成")
            else:
                print(f"      ⏭️  无需更新")
    
    print(f"\n✅ 总共更新了 {updated_count} 个模板")
    
    # 关闭数据库连接
    await close_database()


async def preview_changes():
    """预览修改内容（不实际更新）"""
    
    # 初始化数据库连接
    try:
        await init_database()
        db = get_mongo_db()
        collection = db.prompt_templates
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return
    
    # 查找一个示例模板
    template = await collection.find_one({
        "agent_type": "position_analysis_v2",
        "agent_name": "pa_advisor_v2"
    })
    
    if not template:
        print("❌ 未找到示例模板")
        client.close()
        return
    
    print("=" * 80)
    print("预览修改内容")
    print("=" * 80)
    
    if "content" in template and "system_prompt" in template["content"]:
        old_text = template["content"]["system_prompt"]
        new_text = replace_terms(old_text)
        new_text = update_json_format(new_text)
        new_text = add_disclaimer(new_text)
        
        print("\n【修改前】")
        print("-" * 80)
        print(old_text[:500] + "...")
        
        print("\n【修改后】")
        print("-" * 80)
        print(new_text[:500] + "...")
        
        # 显示差异
        if old_text != new_text:
            print("\n【主要变化】")
            print("-" * 80)
            for old_term, new_term in TERM_REPLACEMENTS.items():
                    if old_term.lower() in old_text.lower():
                        print(f"  '{old_term}' → '{new_term}'")
    
    # 关闭数据库连接
    await close_database()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        print("🔍 预览模式（不实际更新）")
        asyncio.run(preview_changes())
    elif len(sys.argv) > 1 and sys.argv[1] == "--yes":
        # 自动确认模式
        print("🚀 自动确认模式，开始更新...")
        asyncio.run(update_prompt_templates())
    else:
        print("⚠️  警告：这将修改数据库中的提示词模板！")
        print("   如需预览修改内容，请运行: python update_prompts_for_compliance.py preview")
        print("   如需跳过确认，请运行: python update_prompts_for_compliance.py --yes")
        response = input("\n是否继续？(yes/no): ")
        if response.lower() == "yes":
            asyncio.run(update_prompt_templates())
        else:
            print("❌ 已取消")
