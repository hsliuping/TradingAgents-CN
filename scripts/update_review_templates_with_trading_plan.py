"""更新复盘分析师的提示词模板，修复收益数据和股票名称显示问题"""
from pymongo import MongoClient
from bson import ObjectId

# 连接MongoDB
client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

print("=" * 80)
print("更新 reviewers_v2 类型的提示词模板 - 修复数据显示问题")
print("=" * 80)

# 定义要添加的数据约束
DATA_CONSTRAINTS = """

**重要约束**：
- 必须使用用户提示词中提供的真实数据（股票代码、股票名称、收益金额、收益率等）
- 不要在报告中编造或硬编码任何数据
- 报告中的所有数字必须与提示词中提供的数据完全一致
- 不要生成日期信息（如"分析日期：2025年4月5日"），日期由系统自动生成

请使用中文，基于真实数据进行分析。"""

# 更新情绪分析师 v2.0
print("\n" + "=" * 80)
print("更新情绪分析师 v2.0")
print("=" * 80)

emotion_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'emotion_analyst_v2'
})

for template in emotion_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')

    print(f"\n更新模板: {template_id} (偏好: {preference})")

    # 获取 content 字段
    content = template.get('content', {})
    system_prompt = content.get('system_prompt', '')
    constraints = content.get('constraints', '')

    updates = {}

    # 1. 在系统提示词末尾添加数据约束（如果还没有）
    if '**重要约束**' not in system_prompt and '**重要约束**' not in constraints:
        updated_constraints = constraints.rstrip() + DATA_CONSTRAINTS
        updates['content.constraints'] = updated_constraints
        print(f"  ✅ 已添加数据约束到 constraints 字段")
    else:
        print(f"  ⏭️  已包含数据约束")

    # 执行更新
    if updates:
        db.prompt_templates.update_one(
            {'_id': template_id},
            {'$set': updates}
        )
        print(f"  ✅ 模板已更新")

# 更新仓位分析师 v2.0
print("\n" + "=" * 80)
print("更新仓位分析师 v2.0")
print("=" * 80)

position_templates = db.prompt_templates.find({
    'agent_type': 'reviewers_v2',
    'agent_name': 'position_analyst_v2'
})

for template in position_templates:
    template_id = template['_id']
    preference = template.get('preference_id', 'N/A')

    print(f"\n更新模板: {template_id} (偏好: {preference})")

    # 获取 content 字段
    content = template.get('content', {})
    system_prompt = content.get('system_prompt', '')
    constraints = content.get('constraints', '')

    updates = {}

    # 1. 在 constraints 字段末尾添加数据约束（如果还没有）
    if '**重要约束**' not in system_prompt and '**重要约束**' not in constraints:
        updated_constraints = constraints.rstrip() + DATA_CONSTRAINTS
        updates['content.constraints'] = updated_constraints
        print(f"  ✅ 已添加数据约束到 constraints 字段")
    else:
        print(f"  ⏭️  已包含数据约束")

    # 执行更新
    if updates:
        db.prompt_templates.update_one(
            {'_id': template_id},
            {'$set': updates}
        )
        print(f"  ✅ 模板已更新")

print("\n" + "=" * 80)
print("更新完成！")
print("=" * 80)
print("\n说明：")
print("- 已在情绪分析师和仓位分析师的 constraints 字段中添加数据约束")
print("- 要求LLM必须使用提示词中提供的真实数据")
print("- 禁止LLM编造或硬编码数据")
print("- 这将修复报告中显示错误收益数据和股票名称的问题")
print("\n注意：")
print("- 股票名称通过代码中的 _build_user_prompt 方法传递")
print("- 需要重启后端服务才能生效")

