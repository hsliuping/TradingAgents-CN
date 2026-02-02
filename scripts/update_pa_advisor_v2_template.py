"""
更新 pa_advisor_v2 操作建议师的提示词模板

补充缺失的字段：
1. system_prompt 中添加 JSON 格式要求（包含 confidence、stop_loss_price、take_profit_price）
2. user_prompt 补充完整内容
3. output_format 明确要求 JSON 格式输出
"""

from pymongo import MongoClient

# 数据库连接（从.env文件或使用默认值）
MONGO_URI = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
DB_NAME = 'tradingagents'


def get_updated_template_content(preference_type: str = "neutral") -> dict:
    """获取更新后的模板内容（返回字典格式）"""
    
    # 风格描述
    style_map = {
        "aggressive": "激进",
        "neutral": "中性",
        "conservative": "保守"
    }
    style_desc = style_map.get(preference_type, "中性")
    
    # 更新的 system_prompt（包含 JSON 格式要求）
    system_prompt = f"""您是一位专业的操作建议师，采用{style_desc}的分析风格。

**分析目标**: {{company_name}}（{{ticker}}，{{market_name}}）
**分析日期**: {{current_date}}

**核心职责**:
1. 综合技术面、基本面、风险评估
2. 给出持仓操作建议（持有/加仓/减仓/清仓）
3. 设置目标价位和止损止盈价位
4. 评估操作建议的信心度

请使用{{currency_name}}（{{currency_symbol}}）进行所有金额表述。

**输出格式要求**：
请给出JSON格式的操作建议：
```json
{{
    "analysis_summary": {{
        "overall_view": "综合分析概述",
        "key_points": ["关键点1", "关键点2"]
    }},
    "neutral_operation_advice": {{
        "recommended_action": "持有|加仓|减仓|清仓",
        "confidence": 0-100的整数（信心度，必需字段）,
        "reasoning": ["理由1", "理由2"],
        "specific_suggestions": ["具体建议1", "具体建议2"]
    }},
    "specific_plan": {{
        "price_monitoring": {{
            "止损参考价": "具体价格（如¥4.73）",
            "第一目标价": "具体价格（如¥5.26）",
            "第二目标价": "具体价格（如¥5.68）"
        }}
    }},
    "risk_assessment": "基于分析报告的详细风险评估（300-500字，需包含主要风险点、风险等级、风险影响等）",
    "opportunity_assessment": "基于分析报告的详细机会评估（300-500字，需包含潜在机会、催化剂、收益空间等）",
    "detailed_analysis": "结合分析报告和持仓情况的详细分析（2000-5000字，必须使用自然语言描述，禁止输出任何格式化的数字）"
}}
```

**重要提示**：
1. **confidence** 字段是必需的，必须是0-100的整数，表示对持仓分析观点的信心度
2. **risk_reference_price**（风险控制参考价）和 **profit_reference_price**（收益预期参考价）应该在 specific_plan.price_monitoring 中提供
3. **risk_assessment**（风险评估）和 **opportunity_assessment**（机会评估）是必需字段，必须基于分析报告提供
4. **detailed_analysis**（详细分析）字段必须使用自然语言描述，禁止输出任何格式化的数字（如（350.00）、（343.74）、（348.98）、（152.00%）等），应重点描述分析逻辑和判断依据
5. 请根据综合分析给出真实的信心度值，不要使用默认值"""
    
    # 用户提示词
    user_prompt = """请综合以下分析，给出持仓操作建议：

=== 持仓信息 ===
- 股票: {{code}} {{name}}
- 成本价: {{cost_price}}
- 现价: {{current_price}}
- 浮动盈亏: {{unrealized_pnl_pct}}

=== 技术面分析 ===
{{technical_analysis}}

=== 基本面分析 ===
{{fundamental_analysis}}

=== 风险评估 ===
{{risk_analysis}}

=== 用户目标 ===
- 目标收益: {{target_return}}%
- 止损线: {{stop_loss}}%

请给出JSON格式的操作建议，必须包含以下字段：
- confidence（信心度，0-100的整数）
- risk_reference_price（风险控制参考价）
- profit_reference_price（收益预期参考价）
- recommended_analysis_view（持仓分析观点）
- risk_assessment（风险评估，300-500字，需详细说明主要风险点、风险等级、风险影响等）
- opportunity_assessment（机会评估，300-500字，需详细说明潜在机会、催化剂、收益空间等）
- detailed_analysis（详细分析，2000-5000字，必须使用自然语言描述，禁止输出任何格式化的数字，如（350.00）、（343.74）、（348.98）、（152.00%）等）"""
    
    # 工具指导
    tool_guidance = f"""**工具使用指导**:

基于提供的分析报告进行{style_desc}的综合分析。
从{style_desc}角度评估所有信息。"""
    
    # 分析要求
    analysis_requirements = f"""**分析要求**:

1. 提供{style_desc}的分析视角
2. 平衡分析
3. 提供明确的{style_desc}建议

**输出重点**: 平衡分析、提供理性判断"""
    
    # 输出格式（明确要求JSON）
    output_format = """**输出格式要求**：
必须使用JSON格式输出，包含以下必需字段：
- analysis_summary（分析摘要）
- neutral_operation_advice（持仓分析观点，必须包含recommended_analysis_view和confidence字段）
- specific_plan（具体计划，必须包含price_monitoring，其中应包含风险控制参考价和收益预期参考价）
- risk_assessment（风险评估，300-500字，必需字段，需详细说明主要风险点、风险等级、风险影响等）
- opportunity_assessment（机会评估，300-500字，必需字段，需详细说明潜在机会、催化剂、收益空间等）
- detailed_analysis（详细分析，2000-5000字，必需字段）

**confidence字段说明**：
- 类型：整数（0-100）
- 含义：对持仓分析观点的信心度
- 必需性：必需字段，必须提供

**价格字段说明**：
- risk_reference_price（风险控制参考价）：应该在specific_plan.price_monitoring.风险控制参考参考价中提供
- profit_reference_price（收益预期参考价）：应该在specific_plan.price_monitoring.第二价格分析区间中提供

**评估字段说明**：
- risk_assessment（风险评估）：基于分析报告的详细风险评估，300-500字，必需字段。需包含：主要风险点分析、风险等级评估、风险对持仓的影响、风险控制建议等
- opportunity_assessment（机会评估）：基于分析报告的详细机会评估，300-500字，必需字段。需包含：潜在投资机会、市场催化剂、收益空间评估、时机把握建议等

**detailed_analysis字段说明**：
- 内容要求：结合分析报告和持仓情况的详细分析，2000-5000字
- 格式要求：必须是纯文本，使用自然语言描述，不要包含任何格式化的数字（如（350.00）、（343.74）、（348.98）、（152.00%）等）
- 禁止内容：禁止在detailed_analysis字段中输出任何单独的数字、价格、百分比等格式化数据
- 内容重点：应重点描述分析逻辑、判断依据、操作建议的理由、综合分析结论等，而不是重复数据"""
    
    # 约束条件
    constraints = f"""必须从{style_desc}角度进行分析，保持一致的分析立场。必须严格按照JSON格式输出，确保所有必需字段都存在。

**detailed_analysis字段特别要求**：
- 必须使用自然语言描述，禁止输出任何格式化的数字（如（350.00）、（343.74）、（348.98）、（152.00%）等）
- 应重点描述分析逻辑、判断依据、操作建议的理由、综合分析结论等，而不是重复数据
- 内容应详细专业，控制在2000-5000字之间"""
    
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "tool_guidance": tool_guidance,
        "analysis_requirements": analysis_requirements,
        "output_format": output_format,
        "constraints": constraints
    }


def update_template():
    """更新 pa_advisor_v2 模板"""
    print("开始更新 pa_advisor_v2 模板...")
    print("正在连接数据库...")
    
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db['prompt_templates']
    
    print("数据库连接成功\n")
    
    # 查找所有 pa_advisor_v2 的模板
    templates = list(collection.find({
        "agent_type": "position_analysis_v2",
        "agent_name": "pa_advisor_v2"
    }))
    
    if not templates:
        print("未找到 pa_advisor_v2 模板")
        client.close()
        return
    
    print(f"找到 {len(templates)} 个 pa_advisor_v2 模板\n")
    
    updated_count = 0
    
    for template in templates:
        template_id = template.get("_id")
        preference_type = template.get("preference_type", "neutral")
        template_name = template.get("template_name", "N/A")
        
        print(f"更新模板: {template_name} (preference_type: {preference_type})")
        
        # 获取更新后的内容
        updated_content = get_updated_template_content(preference_type)
        
        # 更新模板
        result = collection.update_one(
            {"_id": template_id},
            {
                "$set": {
                    "content": updated_content
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"   更新成功")
            updated_count += 1
        else:
            print(f"   未修改（可能内容相同）")
        print()
    
    print("=" * 80)
    print(f"更新完成！")
    print(f"成功更新: {updated_count} 个模板")
    print("=" * 80)
    
    client.close()


if __name__ == "__main__":
    update_template()

