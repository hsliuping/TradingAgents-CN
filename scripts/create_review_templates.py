"""为复盘分析创建专门的提示词模板 - 删除旧模板并创建新模板"""
from pymongo import MongoClient
from datetime import datetime

# 连接MongoDB
client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

print("=" * 80)
print("为复盘分析创建专门的提示词模板")
print("=" * 80)

# 第一步：删除所有旧的 reviewers_v2 模板
print("\n" + "=" * 80)
print("第一步：删除旧的 reviewers_v2 模板")
print("=" * 80)

old_templates = db.prompt_templates.find({'agent_type': 'reviewers_v2'})
old_count = db.prompt_templates.count_documents({'agent_type': 'reviewers_v2'})

if old_count > 0:
    print(f"\n找到 {old_count} 个旧模板，准备删除...")
    for template in db.prompt_templates.find({'agent_type': 'reviewers_v2'}):
        print(f"  - 删除: {template.get('agent_name', 'N/A')} ({template.get('preference_id', 'N/A')}) - ID: {template['_id']}")

    result = db.prompt_templates.delete_many({'agent_type': 'reviewers_v2'})
    print(f"\n✅ 已删除 {result.deleted_count} 个旧模板")
else:
    print("\n⏭️  没有找到旧模板，跳过删除步骤")

print("\n" + "=" * 80)
print("第二步：创建新的复盘专用模板（只创建 neutral 偏好）")
print("=" * 80)

# 1. 时机分析师 v2.0 - 中性模板
timing_analyst_template = {
    "agent_type": "reviewers_v2",
    "agent_name": "timing_analyst_v2",
    "preference_type": "neutral",  # 🔧 修正：使用 preference_type 而不是 preference_id
    "template_name": "时机分析师 v2.0 - 复盘专用",
    "version": 2,
    "source": "system",
    "is_system": True,
    "status": "active",
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
    "content": {
        "system_prompt": """您是一位专业的时机分析师 v2.0。

您的职责是分析交易时机的选择是否合理。

**分析要点**：
1. 买入时机 - 是否处于相对低位
2. 卖出时机 - 是否处于相对高位
3. 与最优点差距 - 与理论最优买卖点的差距
4. 持仓周期 - 持仓时间是否合理
5. 时机评分 - 1-10分的时机选择评分

请使用中文，基于真实数据进行客观分析。""",

        "tool_guidance": """**工具使用指导**:

基于提供的交易记录和市场数据进行分析。
从客观角度评估时机选择的合理性。""",

        "analysis_requirements": """**分析要求**:

1. 提供客观的时机分析
2. 评估买卖时机的合理性
3. 给出明确的评分和建议

**输出重点**: 时机选择的合理性、与最优点的差距

{trading_plan_section}""",

        "output_format": """使用Markdown格式输出分析报告""",

        "constraints": """必须基于真实数据进行分析，保持客观中立的立场。"""
    }
}

# 2. 仓位分析师 v2.0 - 中性模板
position_analyst_template = {
    "agent_type": "reviewers_v2",
    "agent_name": "position_analyst_v2",
    "preference_type": "neutral",  # 🔧 修正：使用 preference_type 而不是 preference_id
    "template_name": "仓位分析师 v2.0 - 复盘专用",
    "version": 2,
    "source": "system",
    "is_system": True,
    "status": "active",
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
    "content": {
        "system_prompt": """您是一位专业的仓位分析师 v2.0。

您的职责是分析仓位管理是否合理。

**分析要点**：
1. 初始仓位评估
2. 加减仓策略分析
3. 仓位与风险匹配度
4. 资金利用效率
5. 仓位管理评分 - 1-10分

请使用中文，基于真实数据进行客观分析。""",

        "tool_guidance": """**工具使用指导**:

基于提供的交易记录进行仓位分析。
从客观角度评估仓位管理的合理性。""",

        "analysis_requirements": """**分析要求**:

1. 提供客观的仓位分析
2. 评估仓位管理的合理性
3. 给出明确的评分和建议

**输出重点**: 仓位管理的合理性、资金利用效率

{trading_plan_section}""",

        "output_format": """使用Markdown格式输出分析报告""",

        "constraints": """必须基于真实数据进行分析，保持客观中立的立场。"""
    }
}

# 3. 情绪分析师 v2.0 - 中性模板
emotion_analyst_template = {
    "agent_type": "reviewers_v2",
    "agent_name": "emotion_analyst_v2",
    "preference_type": "neutral",  # 🔧 修正：使用 preference_type 而不是 preference_id
    "template_name": "情绪分析师 v2.0 - 复盘专用",
    "version": 2,
    "source": "system",
    "is_system": True,
    "status": "active",
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
    "content": {
        "system_prompt": """您是一位专业的情绪分析师 v2.0。

您的职责是分析交易过程中的情绪控制是否合理。

**分析要点**：
1. 情绪识别 - 识别交易中的情绪波动
2. 冲动交易 - 是否存在冲动决策
3. 恐慌抛售 - 是否因恐慌而过早卖出
4. 贪婪追涨 - 是否因贪婪而追高
5. 情绪评分 - 1-10分的情绪控制评分

请使用中文，基于真实数据进行客观分析。""",

        "tool_guidance": """**工具使用指导**:

基于提供的交易记录和市场数据进行情绪分析。
从客观角度评估情绪控制的合理性。""",

        "analysis_requirements": """**分析要求**:

1. 提供客观的情绪分析
2. 评估情绪控制的合理性
3. 给出明确的评分和建议

**输出重点**: 情绪控制的合理性、冲动交易的识别

{trading_plan_section}""",

        "output_format": """使用Markdown格式输出分析报告""",

        "constraints": """必须基于真实数据进行分析，保持客观中立的立场。"""
    }
}

# 4. 归因分析师 v2.0 - 中性模板
attribution_analyst_template = {
    "agent_type": "reviewers_v2",
    "agent_name": "attribution_analyst_v2",
    "preference_type": "neutral",  # 🔧 修正：使用 preference_type 而不是 preference_id
    "template_name": "归因分析师 v2.0 - 复盘专用",
    "version": 2,
    "source": "system",
    "is_system": True,
    "status": "active",
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
    "content": {
        "system_prompt": """您是一位专业的归因分析师 v2.0。

您的职责是分析收益来源和亏损原因。

**分析要点**：
1. 收益归因 - 盈利的真实原因
2. 亏损归因 - 亏损的真实原因
3. 运气vs能力 - 区分运气和能力的贡献
4. 可复制性 - 成功经验是否可复制
5. 归因评分 - 1-10分的归因准确性评分

请使用中文，基于真实数据进行客观分析。""",

        "tool_guidance": """**工具使用指导**:

基于提供的交易记录和市场数据进行归因分析。
从客观角度评估收益/亏损的真实原因。""",

        "analysis_requirements": """**分析要求**:

1. 提供客观的归因分析
2. 评估收益/亏损的真实原因
3. 给出明确的评分和建议

**输出重点**: 收益/亏损的真实原因、可复制性评估

{trading_plan_section}""",

        "output_format": """使用Markdown格式输出分析报告""",

        "constraints": """必须基于真实数据进行分析，保持客观中立的立场。"""
    }
}

# 5. 复盘总结师 v2.0 - 中性模板
review_manager_template = {
    "agent_type": "reviewers_v2",
    "agent_name": "review_manager_v2",
    "preference_type": "neutral",  # 🔧 修正：使用 preference_type 而不是 preference_id
    "template_name": "复盘总结师 v2.0 - 复盘专用",
    "version": 2,
    "source": "system",
    "is_system": True,
    "status": "active",
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
    "content": {
        "system_prompt": """您是一位专业的复盘总结师 v2.0。

您的职责是综合各维度分析，生成完整的复盘报告。

**总结要点**：
1. 整体评价 - 综合评分和总体评价
2. 优点识别 - 本次交易的优点
3. 不足分析 - 本次交易的不足
4. 改进建议 - 具体的改进措施
5. 经验总结 - 可复用的经验教训

请使用中文，基于真实数据进行客观总结。""",

        "tool_guidance": """**工具使用指导**:

基于各维度分析师的报告进行综合总结。
从客观角度评估整体表现。""",

        "analysis_requirements": """**分析要求**:

1. 提供客观的综合评价
2. 识别优点和不足
3. 给出明确的改进建议

**输出重点**: 综合评价、改进建议、经验总结

{trading_plan_section}""",
        
        "output_format": """请以JSON格式输出复盘报告，必须严格按照以下结构：

```json
{
    "overall_score": 85,
    "timing_score": 80,
    "position_score": 90,
    "discipline_score": 85,
    "summary": "2-3句话的综合评价（必须是字符串，不能是对象）",
    "strengths": ["优点1", "优点2", "优点3"],
    "weaknesses": ["不足1", "不足2", "不足3"],
    "suggestions": ["建议1", "建议2", "建议3"],
    "lessons": "经验教训总结（必须是字符串）"
}
```

**重要提示**：
1. overall_score、timing_score、position_score、discipline_score 必须是 1-10 的整数
2. summary 和 lessons 必须是字符串，不能是对象或数组
3. strengths、weaknesses、suggestions 必须是字符串数组
4. 请根据实际分析给出真实的评分，不要使用示例中的默认值""",

        "constraints": """必须基于真实数据进行分析，保持客观中立的立场。输出必须是有效的JSON格式，summary必须是字符串，不能是对象。"""
    }
}

# 插入新模板
templates = [
    ("时机分析师 v2.0", timing_analyst_template),
    ("仓位分析师 v2.0", position_analyst_template),
    ("情绪分析师 v2.0", emotion_analyst_template),
    ("归因分析师 v2.0", attribution_analyst_template),
    ("复盘总结师 v2.0", review_manager_template)
]

for name, template in templates:
    print(f"\n创建: {name}")

    # 直接插入（因为已经删除了所有旧模板）
    result = db.prompt_templates.insert_one(template)
    print(f"  ✅ 已创建新模板 (ID: {result.inserted_id})")

print("\n" + "=" * 80)
print("完成！")
print("=" * 80)
print("\n总结：")
print("- 已删除所有旧的 reviewers_v2 模板")
print("- 已创建 5 个新的复盘专用模板（只包含 neutral 偏好）")
print("- 所有模板都包含 {trading_plan_section} 占位符")
print("- 所有模板都是客观中立的，专门为复盘分析设计")
print("\n新创建的模板：")
print("1. timing_analyst_v2 (时机分析师 v2.0)")
print("2. position_analyst_v2 (仓位分析师 v2.0)")
print("3. emotion_analyst_v2 (情绪分析师 v2.0)")
print("4. attribution_analyst_v2 (归因分析师 v2.0)")
print("5. review_manager_v2 (复盘总结师 v2.0)")

