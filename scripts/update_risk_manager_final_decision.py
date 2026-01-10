"""
更新 risk_manager 和 risk_manager_v2 的提示词模板
让它在生成风险评估的同时，也生成最终交易决策

修改内容：
1. 在 JSON 输出格式中添加 final_trade_decision 字段
2. 要求 LLM 综合投资建议、交易计划、风险评估，生成最终决策
"""

from pymongo import MongoClient
from datetime import datetime

# 数据库连接
MONGO_URI = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
DB_NAME = 'tradingagents'

# 新的 JSON 输出格式（包含 final_trade_decision）
NEW_OUTPUT_FORMAT = '''```json
{
    "risk_level": "低/中/高",
    "risk_score": 0.0-1.0之间的数字,
    "reasoning": "详细的风险评估理由（200-500字）",
    "key_risks": ["风险1", "风险2", "风险3"],
    "risk_control": "风险控制措施建议",
    "investment_adjustment": "对投资计划的调整建议",
    "final_trade_decision": {
        "action": "买入/持有/卖出",
        "confidence": 0-100之间的整数,
        "target_price": 目标价格（数字）,
        "stop_loss": 止损价格（数字）,
        "position_ratio": "建议仓位比例（如5%、10%）",
        "reasoning": "最终交易决策的综合推理（300-600字）",
        "summary": "一句话总结（50字以内）",
        "risk_warning": "关键风险提示（100字以内）"
    }
}
```'''

# 新的 output_format 字段内容
NEW_OUTPUT_FORMAT_FIELD = '''**输出格式要求**：
必须使用JSON格式输出，包含以下必需字段：
- risk_level（风险等级：低/中/高）
- risk_score（风险评分，0-1，必需字段）
- reasoning（详细的风险评估理由和分析依据，200-500字，必需字段）
- key_risks（主要风险点列表，可选）
- risk_control（风险控制建议，可选）
- investment_adjustment（投资建议调整，可选）
- **final_trade_decision（最终交易决策，必需字段）**

**final_trade_decision 字段说明**：
- action: 买入/持有/卖出（必需）
- confidence: 0-100的信心度（必需）
- target_price: 目标价格（必需）
- stop_loss: 止损价格（必需）
- position_ratio: 建议仓位比例，如"5%-8%"（必需）
- reasoning: 最终交易决策的综合推理，300-600字（必需）
- summary: 一句话总结，50字以内（必需）
- risk_warning: 关键风险提示，100字以内（必需）

**reasoning字段说明**：
- 类型：字符串（200-500字）
- 含义：详细的风险评估理由和分析依据
- 必需性：必需字段，必须提供
- 内容要求：必须说明为什么给出这个风险评估、基于哪些风险因素、关键风险判断因素和逻辑推理过程'''

# 系统提示词模板（根据偏好）
def get_system_prompt(preference_type):
    style_map = {
        'aggressive': ('激进', '更倾向于发现投资机会，强调成长潜力，积极寻找买入理由', '更关注上涨潜力和成长机会，在风险可控的前提下，倾向于给出买入建议', '较高的风险承受能力'),
        'neutral': ('中性', '客观评估，平衡分析，提供理性判断', '客观权衡看涨和看跌观点，基于证据做出理性决策', '平衡的风险收益比'),
        'conservative': ('保守', '更关注风险评估，强调安全边际，识别潜在问题', '更关注风险因素，在确认安全边际的前提下，谨慎给出投资建议', '较低的风险承受能力'),
    }
    
    style_name, style_desc, decision_focus, risk_tolerance = style_map.get(preference_type, style_map['neutral'])
    
    return f'''你是一位{style_name}的风险管理者，需要综合各方风险观点做出风险评估，并生成最终交易决策。

**分析风格**: {style_name}的分析风格，{style_desc}

你的职责：
1. 综合分析激进、保守、中性三方的风险观点
2. 识别关键风险因素
3. 评估风险的可能性和影响
4. 形成{style_name}、理性的风险评估
5. 提出风险控制建议
6. **综合投资建议、交易计划、风险评估，生成最终交易决策**

决策要求：
- {decision_focus}
- {risk_tolerance}
- 客观、理性、基于证据
- 给出明确的风险评级
- 详细说明风险评估理由
- **必须生成完整的 final_trade_decision 字段**
- 使用中文输出

输出格式要求：
请以JSON格式输出风险评估和最终交易决策，必须包含以下字段：
{NEW_OUTPUT_FORMAT}

**重要提示**：
1. **final_trade_decision** 是必需字段，必须包含完整的交易决策
2. **final_trade_decision.reasoning** 应该综合：
   - 研究经理的投资建议（看涨/看跌观点）
   - 交易员的交易计划（买入价、止损、止盈）
   - 风险评估结果（风险等级、关键风险）
   - 得出最终的投资结论（300-600字）
3. **final_trade_decision.action** 必须明确：买入、持有、或卖出
4. **final_trade_decision.summary** 是一句话总结，用于前端显示'''


def update_templates():
    """更新所有 risk_manager 模板"""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db['prompt_templates']

    # 需要更新的 agent
    agents_to_update = [
        ('managers', 'risk_manager'),
        ('managers_v2', 'risk_manager_v2'),
    ]

    preferences = ['aggressive', 'neutral', 'conservative']

    updated_count = 0

    for agent_type, agent_name in agents_to_update:
        for pref in preferences:
            # 查找现有模板（注意：字段名是 preference_type，不是 preference_id）
            query = {
                'agent_type': agent_type,
                'agent_name': agent_name,
                'preference_type': pref
            }

            template = collection.find_one(query)

            if template:
                # 更新现有模板（同时更新 system_prompt 和 output_format）
                new_system_prompt = get_system_prompt(pref)

                result = collection.update_one(
                    {'_id': template['_id']},
                    {
                        '$set': {
                            'content.system_prompt': new_system_prompt,
                            'content.output_format': NEW_OUTPUT_FORMAT_FIELD,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )

                if result.modified_count > 0:
                    updated_count += 1
                    print(f"✅ 更新: {agent_type}/{agent_name} (preference: {pref})")
                else:
                    print(f"⚠️ 未修改: {agent_type}/{agent_name} (preference: {pref})")
            else:
                print(f"❌ 未找到: {agent_type}/{agent_name} (preference: {pref})")

    # 🔥 额外处理：更新所有 risk_manager 相关的模板（不管 preference_type）
    print("\n🔍 查找所有 risk_manager 相关模板...")
    all_risk_templates = list(collection.find({
        'agent_name': {'$regex': 'risk_manager'}
    }))

    for template in all_risk_templates:
        agent_type = template.get('agent_type', '')
        agent_name = template.get('agent_name', '')
        pref = template.get('preference_type', 'neutral')

        # 检查是否已经包含 final_trade_decision
        content = template.get('content', {})
        system_prompt = content.get('system_prompt', '')

        # 检查 output_format 是否包含 final_trade_decision
        output_format = content.get('output_format', '')

        if 'final_trade_decision' not in system_prompt or 'final_trade_decision' not in output_format:
            new_system_prompt = get_system_prompt(pref)

            result = collection.update_one(
                {'_id': template['_id']},
                {
                    '$set': {
                        'content.system_prompt': new_system_prompt,
                        'content.output_format': NEW_OUTPUT_FORMAT_FIELD,
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            if result.modified_count > 0:
                updated_count += 1
                print(f"✅ 补充更新: {agent_type}/{agent_name} (preference: {pref})")
        else:
            print(f"⏭️ 已包含 final_trade_decision: {agent_type}/{agent_name} (preference: {pref})")

    print(f"\n✅ 共更新 {updated_count} 个模板")
    client.close()


if __name__ == '__main__':
    print("=" * 60)
    print("更新 risk_manager 提示词模板")
    print("添加 final_trade_decision 字段")
    print("=" * 60)
    update_templates()

