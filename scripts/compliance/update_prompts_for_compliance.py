"""
提示词合规修改脚本

将提示词中的"目标价"和"操作建议"改为合规表述
"""

import asyncio
import re
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

# 术语替换映射
TERM_REPLACEMENTS = {
    # 目标价格相关
    "目标价": "价格分析区间",
    "目标价位": "价格分析区间",
    "target_price": "price_analysis_range",
    "第一目标价": "第一参考价位区间",
    "第二目标价": "第二参考价位区间",
    "止损价位": "风险控制参考价位",
    "stop_loss_price": "risk_reference_price",
    "止盈价位": "收益预期参考价位",
    "take_profit_price": "profit_reference_price",
    
    # 操作建议相关
    "操作建议": "持仓分析观点",
    "action": "analysis_view",
    "recommended_action": "market_view",
    "操作比例": "仓位分析",
    "action_ratio": "position_analysis",
    "买入": "看涨",
    "卖出": "看跌",
    "持有": "中性",
    "加仓": "增持观点",
    "减仓": "减持观点",
    "清仓": "观望观点",
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
        '"action"': '"analysis_view"',
        '"action_ratio"': '"position_analysis"',
        '"recommended_action"': '"market_view"',
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
    
    # 连接数据库
    mongodb_uri = os.getenv("MONGODB_CONNECTION_STRING")
    if not mongodb_uri:
        print("❌ 未找到 MONGODB_CONNECTION_STRING 环境变量")
        return
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[os.getenv("MONGODB_DATABASE", "tradingagents")]
    collection = db.prompt_templates
    
    # 需要更新的 Agent 类型
    agent_types = [
        "position_analysis",
        "position_analysis_v2",
        "trader_v2",
        "research_manager_v2",
        "risk_manager_v2",
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
    client.close()


async def preview_changes():
    """预览修改内容（不实际更新）"""
    
    mongodb_uri = os.getenv("MONGODB_CONNECTION_STRING")
    if not mongodb_uri:
        print("❌ 未找到 MONGODB_CONNECTION_STRING 环境变量")
        return
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[os.getenv("MONGODB_DATABASE", "tradingagents")]
    collection = db.prompt_templates
    
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
    
    client.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        print("🔍 预览模式（不实际更新）")
        asyncio.run(preview_changes())
    else:
        print("⚠️  警告：这将修改数据库中的提示词模板！")
        print("   如需预览修改内容，请运行: python update_prompts_for_compliance.py preview")
        response = input("\n是否继续？(yes/no): ")
        if response.lower() == "yes":
            asyncio.run(update_prompt_templates())
        else:
            print("❌ 已取消")
