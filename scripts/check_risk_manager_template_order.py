"""检查 managers/risk_manager 模板的顺序和 _id"""
import json

# 读取数据库导出文件
with open('install/database_export_config_2026-01-05.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取 prompt_templates 集合
all_data = data.get('data', {})
templates_data = all_data.get('prompt_templates', [])

# 查找 managers/risk_manager 模板
risk_manager_templates = []
for t in templates_data:
    if (t.get('agent_type') == 'managers' and 
        t.get('agent_name') == 'risk_manager'):
        risk_manager_templates.append(t)

print(f"找到 {len(risk_manager_templates)} 个 managers/risk_manager 模板\n")

for idx, template in enumerate(risk_manager_templates, 1):
    _id = template.get('_id', {})
    preference = template.get('preference_id', template.get('preference_type', 'N/A'))
    is_system = template.get('is_system', False)
    status = template.get('status', 'N/A')
    
    content = template.get('content', {})
    system_prompt = content.get('system_prompt', '')
    
    # 检查特征
    has_json = 'json' in system_prompt.lower() or '```json' in system_prompt.lower()
    has_trade_action = '买入' in system_prompt or '卖出' in system_prompt
    
    print(f"{'=' * 80}")
    print(f"模板 {idx}:")
    print(f"  - _id: {_id}")
    print(f"  - preference: {preference}")
    print(f"  - is_system: {is_system}")
    print(f"  - status: {status}")
    print(f"  - 要求 JSON: {'✅' if has_json else '❌'}")
    print(f"  - 提到交易动作: {'✅' if has_trade_action else '❌'}")
    print(f"\n系统提示词前200字符:")
    print(system_prompt[:200])
    print()

# 按 _id 排序（模拟 MongoDB 的默认排序）
print(f"\n{'=' * 80}")
print("按 _id 排序后的顺序（MongoDB find_one 会返回第一个）:")
print(f"{'=' * 80}\n")

# 将 _id 转换为可比较的格式
def get_oid_str(oid_dict):
    """从 ObjectId 字典中提取字符串"""
    if isinstance(oid_dict, dict) and '$oid' in oid_dict:
        return oid_dict['$oid']
    return ''

sorted_templates = sorted(risk_manager_templates, key=lambda t: get_oid_str(t.get('_id', {})))

for idx, template in enumerate(sorted_templates, 1):
    _id = template.get('_id', {})
    content = template.get('content', {})
    system_prompt = content.get('system_prompt', '')
    
    has_json = 'json' in system_prompt.lower()
    has_trade_action = '买入' in system_prompt or '卖出' in system_prompt
    
    print(f"{idx}. _id={_id}")
    print(f"   JSON格式: {'✅' if has_json else '❌'}, 交易动作: {'✅' if has_trade_action else '❌'}")
    print(f"   → {'【这个会被 find_one() 返回】' if idx == 1 else ''}")
    print()

