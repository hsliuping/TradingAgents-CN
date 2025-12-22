"""
更新 review_manager_v2 模板，添加正确的 JSON 输出格式要求
"""

from pymongo import MongoClient

# 数据库连接
mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
db_name = 'tradingagents'

client = MongoClient(mongo_uri)
db = client[db_name]
collection = db['prompt_templates']

# 新的输出格式要求（使用文本格式避免 JSON 代码块被过滤）
new_output_format = """请以JSON格式输出复盘报告，必须严格按照以下结构：

{
    "overall_score": 75,
    "timing_score": 70,
    "position_score": 80,
    "discipline_score": 75,
    "summary": "综合评价文字...",
    "strengths": ["优点1", "优点2", "优点3"],
    "weaknesses": ["不足1", "不足2"],
    "suggestions": ["建议1", "建议2", "建议3"]
}

字段说明：
- overall_score: 总体评分，0-100的整数
- timing_score: 时机评分，0-100的整数
- position_score: 仓位评分，0-100的整数
- discipline_score: 纪律评分，0-100的整数
- summary: 综合评价，必须是字符串
- strengths: 做得好的地方，必须是字符串数组，至少2-3个要点
- weaknesses: 需要改进的地方，必须是字符串数组，至少2-3个要点
- suggestions: 改进建议，必须是字符串数组，至少2-3个要点

重要提醒：
1. 必须返回有效的JSON格式
2. 所有评分必须是0-100的整数
3. summary必须是字符串，不能是对象
4. strengths、weaknesses、suggestions必须是字符串数组
5. 请根据实际分析给出真实的评分，不要使用默认值50"""

# 更新所有 review_manager_v2 的模板
result = collection.update_many(
    {
        'agent_type': 'reviewers_v2',
        'agent_name': 'review_manager_v2'
    },
    {
        '$set': {
            'content.output_format': new_output_format
        }
    }
)

print(f"✅ 已更新 {result.modified_count} 个模板")

# 验证更新
templates = collection.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'review_manager_v2'
})

print("\n=== 更新后的模板 ===")
for template in templates:
    print(f"\n模板: {template.get('template_name')}")
    print(f"偏好: {template.get('preference_type')}")
    print(f"输出格式长度: {len(template.get('content', {}).get('output_format', ''))}")
    print(f"输出格式前200字符:\n{template.get('content', {}).get('output_format', '')[:200]}...")

client.close()

