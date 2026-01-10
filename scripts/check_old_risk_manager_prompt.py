"""检查是否有旧版的 risk_manager 提示词（不要求 JSON 格式）"""
import json

# 读取数据库导出文件
with open('install/database_export_config_2026-01-05.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取 prompt_templates 集合
all_data = data.get('data', {})
templates_data = all_data.get('prompt_templates', [])

# 查找所有 risk_manager 模板
risk_manager_templates = [t for t in templates_data
                          if 'risk_manager' in t.get('agent_name', '')]

print(f"找到 {len(risk_manager_templates)} 个 risk_manager 模板\n")

for idx, template in enumerate(risk_manager_templates, 1):
    agent_type = template.get('agent_type', 'N/A')
    agent_name = template.get('agent_name', 'N/A')
    preference = template.get('preference_id', 'N/A')
    
    print(f"{'=' * 80}")
    print(f"模板 {idx}: {agent_type}/{agent_name} (偏好: {preference})")
    print(f"{'=' * 80}")
    
    content = template.get('content', {})
    system_prompt = content.get('system_prompt', '')
    
    # 检查是否要求 JSON 格式
    has_json_requirement = 'json' in system_prompt.lower() or '```json' in system_prompt.lower()
    
    # 检查是否提到"买入、卖出或持有"
    has_trade_action = '买入' in system_prompt or '卖出' in system_prompt or 'buy' in system_prompt.lower() or 'sell' in system_prompt.lower()
    
    print(f"\n特征:")
    print(f"  - 要求 JSON 格式: {'✅ 是' if has_json_requirement else '❌ 否'}")
    print(f"  - 提到交易动作: {'✅ 是' if has_trade_action else '❌ 否'}")
    
    print(f"\n系统提示词:")
    print(f"{'-' * 80}")
    print(system_prompt)
    print()

