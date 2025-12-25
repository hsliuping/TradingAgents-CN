"""
修复 review_manager_v2 模板的问题：
1. 隐藏百分比显示（前端已修复）
2. 明确总分应该是分项评分的平均值
3. 禁止LLM生成日期信息
"""

from pymongo import MongoClient

# 数据库连接
mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
db_name = 'tradingagents'

client = MongoClient(mongo_uri)
db = client[db_name]
collection = db['prompt_templates']

# 新的输出格式要求
new_output_format = """请以JSON格式输出复盘报告，必须严格按照以下结构：

```json
{
    "overall_score": 7,
    "timing_score": 7,
    "position_score": 7,
    "discipline_score": 6,
    "summary": "2-3句话的综合评价（必须是字符串，不能是对象）",
    "strengths": ["优点1", "优点2", "优点3"],
    "weaknesses": ["不足1", "不足2", "不足3"],
    "suggestions": ["建议1", "建议2", "建议3"],
    "lessons": "经验教训总结（必须是字符串）"
}
```

**重要提示**：
1. overall_score、timing_score、position_score、discipline_score 必须是 1-10 的整数
2. overall_score 应该是 timing_score、position_score、discipline_score 的平均值（四舍五入）
   例如：timing_score=7, position_score=7, discipline_score=6，则 overall_score = round((7+7+6)/3) = 7
3. summary 和 lessons 必须是字符串，不能是对象或数组
4. strengths、weaknesses、suggestions 必须是字符串数组
5. 请根据实际分析给出真实的评分，不要使用示例中的默认值
6. **禁止在输出中包含任何日期信息**（如"2025年4月5日"、"分析时间"等），日期由系统自动生成
7. summary、lessons、strengths、weaknesses、suggestions 中都不要包含日期"""

# 新的约束条件
new_constraints = """必须基于真实数据进行分析，保持客观中立的立场。
输出必须是有效的JSON格式，summary必须是字符串，不能是对象。
总分必须是分项评分的平均值（四舍五入）。
禁止在任何输出中包含日期信息，日期由系统自动生成。"""

# 更新所有 review_manager_v2 的模板
result = collection.update_many(
    {
        'agent_type': 'reviewers_v2',
        'agent_name': 'review_manager_v2'
    },
    {
        '$set': {
            'content.output_format': new_output_format,
            'content.constraints': new_constraints
        }
    }
)

print(f"✅ 已更新 {result.modified_count} 个模板")

# 验证更新
templates = collection.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'review_manager_v2'
})

print("\n📋 更新后的模板列表：")
for template in templates:
    print(f"  - {template.get('template_name')} (preference: {template.get('preference_type')})")
    print(f"    output_format 长度: {len(template['content']['output_format'])}")
    print(f"    constraints 长度: {len(template['content']['constraints'])}")

client.close()
print("\n✅ 完成")

