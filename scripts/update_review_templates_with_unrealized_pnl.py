"""
更新复盘相关的提示词模板，添加浮动盈亏字段支持

更新以下 Agent 的模板：
1. review_manager_v2 - 复盘总结师
2. timing_analyst_v2 - 时机分析师
3. position_analyst_v2 - 仓位分析师
4. emotion_analyst_v2 - 情绪分析师
5. attribution_analyst_v2 - 归因分析师

添加的变量：
- unrealized_pnl: 浮动盈亏
- unrealized_pnl_pct: 浮动盈亏百分比
- total_pnl: 总盈亏（已实现+浮动）
- total_pnl_pct: 总收益率（已实现+浮动）
- is_holding: 是否持仓中
- current_price: 当前价格
"""

from pymongo import MongoClient
from datetime import datetime
import re

# 数据库连接（使用默认值，可以从环境变量读取）
MONGO_URI = "mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin"
DB_NAME = "tradingagents"


def update_user_prompt_content(content: str, agent_name: str) -> str:
    """更新用户提示词内容，添加浮动盈亏相关变量"""
    
    # 移除 Jinja2 条件语法（因为 format_template 不支持）
    updated_content = re.sub(r'\{%\s*if[^%]*%\}([^%]*)\{%\s*endif\s*%\}', r'\1', content)
    updated_content = re.sub(r'\{%\s*if[^%]*%\}', '', updated_content)
    updated_content = re.sub(r'\{%\s*endif\s*%\}', '', updated_content)
    
    # 检查是否已经包含预构建的变量（pnl_info, return_info）
    if "{{pnl_info}}" in updated_content or "{{return_info}}" in updated_content:
        print(f"   ⚠️  模板已包含预构建变量，跳过更新")
        return updated_content
    
    # 1. 替换盈亏金额显示（使用预构建的 pnl_info 变量）
    # 代码中会根据条件构建完整的文本并传递给模板
    pnl_patterns = [
        (r'- 盈亏金额[：:]\s*\{\{realized_pnl\}\}元', 
         r'- 盈亏金额: {{pnl_info}}'),
        (r'- 盈亏金额[：:]\s*\{\{pnl_sign\}\}\{\{realized_pnl\}\}元',
         r'- 盈亏金额: {{pnl_info}}'),
        (r'- 盈亏金额[：:]\s*\{\{pnl_sign\}\}\{\{total_pnl\}\}元[^{]*',
         r'- 盈亏金额: {{pnl_info}}'),
        (r'盈亏金额[：:]\s*\{\{pnl_sign\}\}\{\{realized_pnl\}\}元',
         r'盈亏金额: {{pnl_info}}'),
    ]
    
    for pattern, replacement in pnl_patterns:
        updated_content = re.sub(pattern, replacement, updated_content)
    
    # 2. 替换收益率显示（使用预构建的 return_info 变量）
    return_patterns = [
        (r'- 收益率[：:]\s*\{\{realized_pnl_pct\}\}%',
         r'- 收益率: {{return_info}}'),
        (r'- 收益率[：:]\s*\{\{pnl_sign\}\}\{\{realized_pnl_pct\}\}%[^{]*',
         r'- 收益率: {{return_info}}'),
        (r'- 收益率[：:]\s*\{\{pnl_sign\}\}\{\{total_pnl_pct\}\}%[^{]*',
         r'- 收益率: {{return_info}}'),
        (r'收益率[：:]\s*\{\{pnl_sign\}\}\{\{realized_pnl_pct\}\}%',
         r'收益率: {{return_info}}'),
    ]
    
    for pattern, replacement in return_patterns:
        updated_content = re.sub(pattern, replacement, updated_content)
    
    # 3. 替换持仓状态（使用预构建的 holding_status 变量）
    if "{{holding_status}}" not in updated_content:
        if "持仓状态" in updated_content:
            updated_content = re.sub(
                r'- 持仓状态[：:][^{]*',
                r'- 持仓状态: {{holding_status}}',
                updated_content
            )
        elif "=== 交易信息 ===" in updated_content:
            updated_content = updated_content.replace(
                "=== 交易信息 ===",
                "=== 交易信息 ===\n- 持仓状态: {{holding_status}}"
            )
    
    # 4. 添加重要提示（针对持仓中的交易）
    if "**重要提示**" not in updated_content or "浮动盈亏" not in updated_content:
        important_note = """

**重要提示**：
- 如果交易还在持仓中（is_holding == "是"），请综合考虑已实现盈亏和浮动盈亏来评价整体表现
- 浮动盈亏反映了当前持仓的潜在收益/亏损，是评价交易决策的重要指标
- 不要仅基于已实现盈亏（可能为0）就认为交易"收益归零"，要结合浮动盈亏进行综合评价
- 总盈亏 = 已实现盈亏 + 浮动盈亏（持仓中时）
"""
        # 在提示词末尾添加
        if updated_content.strip().endswith("```"):
            # 如果以代码块结尾，在代码块前添加
            updated_content = updated_content.replace("```", important_note + "\n```")
        else:
            updated_content = updated_content + important_note
    
    return updated_content


def update_templates():
    """更新复盘相关的提示词模板"""
    print("=" * 80)
    print("🔄 开始更新复盘相关提示词模板（添加浮动盈亏支持）")
    print("=" * 80)
    
    # 连接数据库
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db['prompt_templates']
    
    # 需要更新的 Agent 列表
    agents_to_update = [
        ("reviewers_v2", "review_manager_v2"),
        ("reviewers_v2", "timing_analyst_v2"),
        ("reviewers_v2", "position_analyst_v2"),
        ("reviewers_v2", "emotion_analyst_v2"),
        ("reviewers_v2", "attribution_analyst_v2"),
    ]
    
    total_updated = 0
    
    for agent_type, agent_name in agents_to_update:
        print(f"\n📋 处理: {agent_type} / {agent_name}")
        print("-" * 80)
        
        # 查询所有相关模板
        templates = list(collection.find({
            "agent_type": agent_type,
            "agent_name": agent_name
        }))
        
        if not templates:
            print(f"   ⚠️  未找到模板")
            continue
        
        print(f"   ✅ 找到 {len(templates)} 个模板")
        
        for template in templates:
            template_id = template.get("_id")
            preference_type = template.get("preference_type", "null")
            template_name = template.get("template_name", "N/A")
            content = template.get("content", {})
            
            print(f"\n   📝 模板: {template_name} (preference_type: {preference_type})")
            
            # 更新 user_prompt
            if "user_prompt" in content:
                old_user_prompt = content["user_prompt"]
                new_user_prompt = update_user_prompt_content(old_user_prompt, agent_name)
                
                if old_user_prompt != new_user_prompt:
                    # 更新模板
                    content["user_prompt"] = new_user_prompt
                    
                    result = collection.update_one(
                        {"_id": template_id},
                        {
                            "$set": {
                                "content": content,
                                "updated_at": datetime.now()
                            }
                        }
                    )
                    
                    if result.modified_count > 0:
                        print(f"      ✅ 更新成功")
                        total_updated += 1
                    else:
                        print(f"      ⚠️  更新失败")
                else:
                    print(f"      ⏭️  无需更新（已包含新变量）")
            else:
                print(f"      ⚠️  模板中没有 user_prompt 字段")
    
    print("\n" + "=" * 80)
    print(f"✅ 更新完成！共更新 {total_updated} 个模板")
    print("=" * 80)
    
    client.close()


if __name__ == "__main__":
    update_templates()
