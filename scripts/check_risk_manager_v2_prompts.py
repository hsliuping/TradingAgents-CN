"""检查 managers_v2/risk_manager_v2 的提示词模板"""
import json

# 读取数据库导出文件
with open('install/database_export_config_2026-01-05.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取 prompt_templates 集合
all_data = data.get('data', {})
templates_data = all_data.get('prompt_templates', [])

# 查找 managers_v2/risk_manager_v2 模板
templates = [t for t in templates_data
             if (t.get('agent_type') == 'managers_v2' and 
                 t.get('agent_name') == 'risk_manager_v2')]

print(f"找到 {len(templates)} 个 managers_v2/risk_manager_v2 模板\n")

for idx, template in enumerate(templates, 1):
    _id = template.get('_id', {})
    preference = template.get('preference_id', template.get('preference_type', 'N/A'))
    is_system = template.get('is_system', False)
    status = template.get('status', 'N/A')
    
    content = template.get('content', {})
    system_prompt = content.get('system_prompt', '')
    
    # 检查特征
    has_json = 'json' in system_prompt.lower() or '```json' in system_prompt.lower()
    has_trade_action = '买入' in system_prompt or '卖出' in system_prompt or 'buy' in system_prompt.lower()
    has_final_decision = 'final_trade_decision' in system_prompt.lower() or '最终分析结果' in system_prompt
    
    print(f"{'=' * 80}")
    print(f"模板 {idx}: {preference} 偏好")
    print(f"  - _id: {_id}")
    print(f"  - is_system: {is_system}")
    print(f"  - status: {status}")
    print(f"  - 要求 JSON: {'✅' if has_json else '❌'}")
    print(f"  - 提到交易动作: {'✅' if has_trade_action else '❌'}")
    print(f"  - 提到最终分析结果: {'✅' if has_final_decision else '❌'}")
    print(f"\n系统提示词:")
    print(f"{'-' * 80}")
    print(system_prompt)
    print()

# 按 preference 分组统计
print(f"\n{'=' * 80}")
print("按偏好分组:")
print(f"{'=' * 80}\n")

from collections import defaultdict
by_preference = defaultdict(list)
for t in templates:
    pref = t.get('preference_id', t.get('preference_type', 'N/A'))
    by_preference[pref].append(t)

for pref, tmps in by_preference.items():
    print(f"{pref}: {len(tmps)} 个模板")

