"""
更新 managers_v2 的提示词模板（research_manager_v2 和 risk_manager_v2）

补充缺失的字段：
1. system_prompt 中添加 JSON 格式要求（包含 reasoning、confidence/risk_score 字段）
2. user_prompt 补充完整内容，明确要求输出 reasoning
3. 支持所有 preference_type（aggressive, neutral, conservative）
4. 同时更新 managers/research_manager 和 managers_v2/research_manager_v2
5. 同时更新 managers/risk_manager 和 managers_v2/risk_manager_v2
"""

from pymongo import MongoClient

# 数据库连接
MONGO_URI = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
DB_NAME = 'tradingagents'

# Manager agents 配置
MANAGER_AGENTS = {
    "research_manager": {
        "old_agent_type": "managers",
        "old_agent_name": "research_manager",
        "new_agent_type": "managers_v2",
        "new_agent_name": "research_manager_v2",
        "display_name": "研究经理",
    },
    "risk_manager": {
        "old_agent_type": "managers",
        "old_agent_name": "risk_manager",
        "new_agent_type": "managers_v2",
        "new_agent_name": "risk_manager_v2",
        "display_name": "风险管理者",
    }
}


def get_updated_template_content(preference_type: str = "neutral", agent_key: str = "research_manager") -> dict:
    """获取更新后的模板内容（返回字典格式）
    
    Args:
        preference_type: 偏好类型（aggressive, neutral, conservative）
        agent_key: Agent键（research_manager 或 risk_manager）
    """
    
    # 偏好类型映射
    preference_map = {
        "aggressive": {
            "label": "激进",
            "style_desc": "激进的分析风格，更倾向于发现投资机会，强调成长潜力，积极寻找买入理由",
            "decision_focus": "更关注上涨潜力和成长机会，在风险可控的前提下，倾向于给出买入建议",
            "risk_tolerance": "较高的风险承受能力"
        },
        "neutral": {
            "label": "中性",
            "style_desc": "中性的分析风格，客观评估，平衡分析，提供理性判断",
            "decision_focus": "客观权衡看涨和看跌观点，基于证据做出理性决策",
            "risk_tolerance": "平衡的风险收益比"
        },
        "conservative": {
            "label": "保守",
            "style_desc": "保守的分析风格，更关注风险评估，强调安全边际，识别潜在问题",
            "decision_focus": "更关注风险因素，在确认安全边际的前提下，谨慎给出投资建议",
            "risk_tolerance": "较低的风险承受能力"
        }
    }
    
    pref_info = preference_map.get(preference_type, preference_map["neutral"])
    pref_label = pref_info["label"]
    style_desc = pref_info["style_desc"]
    decision_focus = pref_info["decision_focus"]
    risk_tolerance = pref_info["risk_tolerance"]
    
    # 根据 agent_key 生成不同的 system_prompt
    if agent_key == "research_manager":
        # 研究经理的 system_prompt
        system_prompt = f"""你是一位{pref_label}的研究经理，需要综合看涨和看跌观点做出决策。

**分析风格**: {style_desc}

你的职责：
1. 综合分析看涨和看跌观点
2. 权衡双方的理由和证据
3. 做出{pref_label}、理性的投资决策
4. 给出明确的投资建议（买入/持有/卖出）

决策要求：
- {decision_focus}
- {risk_tolerance}
- 客观、理性、基于证据
- 给出明确的建议
- 详细说明决策理由
- 使用中文输出

输出格式要求：
请以JSON格式输出投资计划，必须包含以下字段：
```json
{{
    "action": "买入|持有|卖出",
    "confidence": 0-100的整数（信心度，必需字段）,
    "target_price": 目标价格（数字，可选）,
    "risk_score": 0-1的风险评分（可选）,
    "reasoning": "详细的决策理由和分析依据（必需字段，200-500字，说明为什么做出这个投资建议，基于哪些分析依据）",
    "summary": "投资计划摘要（可选）",
    "risk_warning": "风险提示（可选）",
    "position_ratio": "建议持仓比例（可选）"
}}
```

**重要提示**：
1. **reasoning** 字段是必需字段，必须提供详细的决策理由和分析依据（200-500字）
2. **reasoning** 应该说明：
   - 为什么做出这个投资建议（买入/持有/卖出）
   - 基于哪些分析依据（技术面、基本面、市场环境、看涨观点、看跌观点等）
   - 关键判断因素和逻辑推理过程
   - 如何{decision_focus}
3. **confidence** 字段是必需字段，必须是0-100的整数，表示对投资建议的信心度
4. 请根据综合分析给出真实的信心度值和详细的决策理由，不要使用默认值
5. 必须从{pref_label}角度进行分析，保持一致的分析立场"""
        
        # 研究经理的用户提示词
        user_prompt = """请综合分析 {{company_name}}（{{ticker}}）的投资机会：

股票代码：{{ticker}}
公司名称：{{company_name}}
分析日期：{{analysis_date}}

【看涨观点】
{{bull_report}}

【看跌观点】
{{bear_report}}

【辩论总结】
{{debate_summary}}

请给出最终的投资计划（买入/持有/卖出）和详细理由。

**输出要求**：
1. 必须以JSON格式输出
2. 必须包含 **reasoning** 字段（详细的决策理由和分析依据，200-500字）
3. 必须包含 **confidence** 字段（0-100的整数，信心度）
4. **reasoning** 应该详细说明：
   - 为什么做出这个投资建议
   - 基于哪些分析依据（看涨观点、看跌观点、市场环境、技术面、基本面等）
   - 关键判断因素和逻辑推理过程
   - 如何权衡风险和收益"""
        
        tool_guidance = f"""**工具使用指导**:

基于提供的分析报告进行{pref_label}的综合分析。
从{pref_label}角度评估所有信息。"""
        
        analysis_requirements = f"""**分析要求**:

1. 提供{pref_label}的分析视角
2. {decision_focus}
3. 提供明确的{pref_label}建议

**输出重点**: {decision_focus}、{risk_tolerance}"""
        
        output_format = """**输出格式要求**：
必须使用JSON格式输出，包含以下必需字段：
- action（投资建议：买入/持有/卖出）
- confidence（信心度，0-100的整数，必需字段）
- target_price（目标价格，可选）
- risk_score（风险评分，0-1，可选）
- reasoning（详细的决策理由和分析依据，200-500字，必需字段）
- summary（投资计划摘要，可选）
- risk_warning（风险提示，可选）
- position_ratio（建议持仓比例，可选）

**reasoning字段说明**：
- 类型：字符串（200-500字）
- 含义：详细的决策理由和分析依据
- 必需性：必需字段，必须提供
- 内容要求：必须说明为什么做出这个投资建议、基于哪些分析依据、关键判断因素和逻辑推理过程"""
        
        constraints = f"必须从{pref_label}角度进行分析，保持一致的分析立场。必须严格按照JSON格式输出，确保所有必需字段（action、confidence、reasoning）都存在。"
    
    else:
        # 风险管理者的 system_prompt
        system_prompt = f"""你是一位{pref_label}的风险管理者，需要综合各方风险观点做出风险评估。

**分析风格**: {style_desc}

你的职责：
1. 综合分析激进、保守、中性三方的风险观点
2. 识别关键风险因素
3. 评估风险的可能性和影响
4. 形成{pref_label}、理性的风险评估
5. 提出风险控制建议

决策要求：
- {decision_focus}
- {risk_tolerance}
- 客观、理性、基于证据
- 给出明确的风险评级
- 详细说明风险评估理由
- 使用中文输出

输出格式要求：
请以JSON格式输出风险评估，必须包含以下字段：
```json
{{
    "risk_level": "低|中|高",
    "risk_score": 0-1的风险评分（必需字段）,
    "reasoning": "详细的风险评估理由和分析依据（必需字段，200-500字，说明为什么给出这个风险评估，基于哪些风险因素）",
    "key_risks": ["主要风险点1", "主要风险点2", ...],
    "risk_control": "风险控制建议（可选）",
    "investment_adjustment": "投资建议调整（可选）"
}}
```

**重要提示**：
1. **reasoning** 字段是必需字段，必须提供详细的风险评估理由和分析依据（200-500字）
2. **reasoning** 应该说明：
   - 为什么给出这个风险评估（低/中/高）
   - 基于哪些风险因素（激进观点、保守观点、市场环境、技术面、基本面等）
   - 关键风险判断因素和逻辑推理过程
   - 如何{decision_focus}
3. **risk_score** 字段是必需字段，必须是0-1之间的数字，表示风险评分
4. 请根据综合分析给出真实的风险评分和详细的风险评估理由，不要使用默认值
5. 必须从{pref_label}角度进行分析，保持一致的分析立场"""
        
        # 风险管理者的用户提示词
        user_prompt = """请综合分析 {{company_name}}（{{ticker}}）的投资风险：

股票代码：{{ticker}}
公司名称：{{company_name}}
分析日期：{{analysis_date}}

【投资计划】
{{investment_plan}}

【激进风险观点】
{{risky_opinion}}

【保守风险观点】
{{safe_opinion}}

【中性风险观点】
{{neutral_opinion}}

【风险辩论总结】
{{debate_summary}}

请给出最终的风险评估和风险控制建议。

**输出要求**：
1. 必须以JSON格式输出
2. 必须包含 **reasoning** 字段（详细的风险评估理由和分析依据，200-500字）
3. 必须包含 **risk_score** 字段（0-1的风险评分，必需字段）
4. **reasoning** 应该详细说明：
   - 为什么给出这个风险评估
   - 基于哪些风险因素（激进观点、保守观点、市场环境、技术面、基本面等）
   - 关键风险判断因素和逻辑推理过程
   - 如何权衡不同风险观点"""
        
        tool_guidance = f"""**工具使用指导**:

基于提供的风险观点进行{pref_label}的风险评估。
从{pref_label}角度评估所有风险信息。"""
        
        analysis_requirements = f"""**分析要求**:

1. 提供{pref_label}的风险评估视角
2. {decision_focus}
3. 提供明确的{pref_label}风险评估

**输出重点**: {decision_focus}、{risk_tolerance}"""
        
        output_format = """**输出格式要求**：
必须使用JSON格式输出，包含以下必需字段：
- risk_level（风险等级：低/中/高）
- risk_score（风险评分，0-1，必需字段）
- reasoning（详细的风险评估理由和分析依据，200-500字，必需字段）
- key_risks（主要风险点列表，可选）
- risk_control（风险控制建议，可选）
- investment_adjustment（投资建议调整，可选）

**reasoning字段说明**：
- 类型：字符串（200-500字）
- 含义：详细的风险评估理由和分析依据
- 必需性：必需字段，必须提供
- 内容要求：必须说明为什么给出这个风险评估、基于哪些风险因素、关键风险判断因素和逻辑推理过程"""
        
        constraints = f"必须从{pref_label}角度进行分析，保持一致的分析立场。必须严格按照JSON格式输出，确保所有必需字段（risk_level、risk_score、reasoning）都存在。"
    
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "tool_guidance": tool_guidance,
        "analysis_requirements": analysis_requirements,
        "output_format": output_format,
        "constraints": constraints,
    }


def update_template():
    """更新 managers_v2 模板（research_manager_v2 和 risk_manager_v2，支持所有 preference_type）"""
    print("开始更新 managers_v2 模板（research_manager_v2 和 risk_manager_v2）...")
    print("正在连接数据库...")
    
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db['prompt_templates']
    
    print("数据库连接成功\n")
    
    total_updated = 0
    total_created = 0
    
    # 遍历所有 manager agents
    for agent_key, agent_config in MANAGER_AGENTS.items():
        print("=" * 80)
        print(f"处理 Agent: {agent_config['display_name']} ({agent_key})")
        print("=" * 80)
        
        # 查找该 agent 的所有模板（包括旧版本和新版本）
        templates = list(collection.find({
            "$or": [
                {
                    "agent_type": agent_config["old_agent_type"],
                    "agent_name": agent_config["old_agent_name"]
                },
                {
                    "agent_type": agent_config["new_agent_type"],
                    "agent_name": agent_config["new_agent_name"]
                }
            ],
            "is_system": True,
            "status": "active"
        }))
        
        if not templates:
            print(f"未找到 {agent_key} 模板，尝试创建...")
            # 如果没有模板，创建三个默认模板（aggressive, neutral, conservative）
            # 同时创建旧版本和新版本两个版本
            preference_types = ["aggressive", "neutral", "conservative"]
            for pref_type in preference_types:
                updated_content = get_updated_template_content(pref_type, agent_key)
                # 创建旧版本
                new_template_old = {
                    "agent_type": agent_config["old_agent_type"],
                    "agent_name": agent_config["old_agent_name"],
                    "template_name": f"{agent_config['display_name']} v2.0 - {pref_type}",
                    "preference_type": pref_type,
                    "content": updated_content,
                    "is_system": True,
                    "status": "active",
                    "version": 1
                }
                collection.insert_one(new_template_old)
                print(f"   创建模板: {agent_config['old_agent_type']}/{agent_config['old_agent_name']} - {pref_type}")
                total_created += 1
                # 创建新版本
                new_template_v2 = {
                    "agent_type": agent_config["new_agent_type"],
                    "agent_name": agent_config["new_agent_name"],
                    "template_name": f"{agent_config['display_name']} v2.0 - {pref_type}",
                    "preference_type": pref_type,
                    "content": updated_content,
                    "is_system": True,
                    "status": "active",
                    "version": 1
                }
                collection.insert_one(new_template_v2)
                print(f"   创建模板: {agent_config['new_agent_type']}/{agent_config['new_agent_name']} - {pref_type}")
                total_created += 1
            print()
            templates = list(collection.find({
                "$or": [
                    {
                        "agent_type": agent_config["old_agent_type"],
                        "agent_name": agent_config["old_agent_name"]
                    },
                    {
                        "agent_type": agent_config["new_agent_type"],
                        "agent_name": agent_config["new_agent_name"]
                    }
                ],
                "is_system": True,
                "status": "active"
            }))
        
        print(f"找到 {len(templates)} 个 {agent_key} 模板\n")
        
        updated_count = 0
        created_count = 0
        
        # 确保所有 preference_type 都存在
        existing_preferences = {t.get("preference_type", "neutral") for t in templates}
        required_preferences = {"aggressive", "neutral", "conservative"}
        missing_preferences = required_preferences - existing_preferences
        
        # 创建缺失的模板（同时创建两个版本）
        for pref_type in missing_preferences:
            updated_content = get_updated_template_content(pref_type, agent_key)
            # 检查旧版本是否存在
            existing_old = collection.find_one({
                "agent_type": agent_config["old_agent_type"],
                "agent_name": agent_config["old_agent_name"],
                "preference_type": pref_type,
                "is_system": True,
                "status": "active"
            })
            if not existing_old:
                new_template_old = {
                    "agent_type": agent_config["old_agent_type"],
                    "agent_name": agent_config["old_agent_name"],
                    "template_name": f"{agent_config['display_name']} v2.0 - {pref_type}",
                    "preference_type": pref_type,
                    "content": updated_content,
                    "is_system": True,
                    "status": "active",
                    "version": 1
                }
                collection.insert_one(new_template_old)
                print(f"创建缺失的模板: {agent_config['old_agent_type']}/{agent_config['old_agent_name']} - {pref_type}")
                created_count += 1
                total_created += 1
            # 检查新版本是否存在
            existing_v2 = collection.find_one({
                "agent_type": agent_config["new_agent_type"],
                "agent_name": agent_config["new_agent_name"],
                "preference_type": pref_type,
                "is_system": True,
                "status": "active"
            })
            if not existing_v2:
                new_template_v2 = {
                    "agent_type": agent_config["new_agent_type"],
                    "agent_name": agent_config["new_agent_name"],
                    "template_name": f"{agent_config['display_name']} v2.0 - {pref_type}",
                    "preference_type": pref_type,
                    "content": updated_content,
                    "is_system": True,
                    "status": "active",
                    "version": 1
                }
                collection.insert_one(new_template_v2)
                print(f"创建缺失的模板: {agent_config['new_agent_type']}/{agent_config['new_agent_name']} - {pref_type}")
                created_count += 1
                total_created += 1
        
        # 重新查询所有模板（包括新创建的）
        templates = list(collection.find({
            "$or": [
                {
                    "agent_type": agent_config["old_agent_type"],
                    "agent_name": agent_config["old_agent_name"]
                },
                {
                    "agent_type": agent_config["new_agent_type"],
                    "agent_name": agent_config["new_agent_name"]
                }
            ],
            "is_system": True,
            "status": "active"
        }))
        
        # 更新现有模板
        for template in templates:
            template_id = template.get("_id")
            template_name = template.get("template_name", "N/A")
            preference_type = template.get("preference_type", "neutral")
            template_agent_type = template.get("agent_type", "N/A")
            template_agent_name = template.get("agent_name", "N/A")
            
            print(f"更新模板: {template_name} (agent_type: {template_agent_type}, agent_name: {template_agent_name}, preference_type: {preference_type})")
            
            # 根据 preference_type 和 agent_key 获取更新后的内容
            updated_content = get_updated_template_content(preference_type, agent_key)
            
            # 获取现有内容
            existing_content = template.get("content", {})
            
            # 合并更新（保留其他字段，更新所有字段）
            merged_content = {
                **existing_content,
                "system_prompt": updated_content["system_prompt"],
                "user_prompt": updated_content["user_prompt"],
                "tool_guidance": updated_content["tool_guidance"],
                "analysis_requirements": updated_content["analysis_requirements"],
                "output_format": updated_content["output_format"],
                "constraints": updated_content["constraints"],
            }
            
            # 检查 user_prompt 是否存在
            has_user_prompt = "user_prompt" in merged_content and merged_content["user_prompt"]
            user_prompt_length = len(merged_content.get("user_prompt", ""))
            
            print(f"   📝 user_prompt 存在: {has_user_prompt}, 长度: {user_prompt_length}")
            print(f"   📝 所有字段: {list(merged_content.keys())}")
            
            # 更新模板
            result = collection.update_one(
                {"_id": template_id},
                {
                    "$set": {
                        "content": merged_content
                    }
                }
            )
            
            if result.modified_count > 0:
                print(f"   ✅ 更新成功")
                # 验证更新后的内容
                updated_template = collection.find_one({"_id": template_id})
                updated_content_check = updated_template.get("content", {})
                has_user_prompt_after = "user_prompt" in updated_content_check and updated_content_check["user_prompt"]
                print(f"   ✅ 验证: user_prompt 已保存: {has_user_prompt_after}, 长度: {len(updated_content_check.get('user_prompt', ''))}")
                updated_count += 1
                total_updated += 1
            else:
                print(f"   ⏭️  未修改（可能内容相同）")
            print()
        
        print(f"✅ {agent_config['display_name']}: 更新 {updated_count} 个模板，创建 {created_count} 个模板\n")
    
    print("=" * 80)
    print(f"全部更新完成！")
    print(f"✅ 总共更新: {total_updated} 个模板")
    if total_created > 0:
        print(f"✅ 总共创建: {total_created} 个模板")
    print("=" * 80)
    
    client.close()


if __name__ == "__main__":
    update_template()


