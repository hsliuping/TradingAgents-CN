"""检查 trader_v2 的提示词模板"""
import json

# 读取数据库导出文件
with open('install/database_export_config_2026-01-05.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取 prompt_templates 集合
all_data = data.get('data', {})
templates_data = all_data.get('prompt_templates', [])

# 查找 trader_v2 模板
templates = [t for t in templates_data
             if (t.get('agent_type') == 'trader_v2' and 
                 t.get('agent_name') == 'trader_v2')]

print(f"找到 {len(templates)} 个 trader_v2/trader_v2 模板\n")

if len(templates) == 0:
    print("❌ 未找到 trader_v2/trader_v2 模板！")
    print("\n尝试查找其他 trader 相关模板:")
    
    all_trader_templates = [t for t in templates_data
                            if 'trader' in t.get('agent_type', '').lower() or 
                               'trader' in t.get('agent_name', '').lower()]
    
    for t in all_trader_templates:
        print(f"  - {t.get('agent_type')}/{t.get('agent_name')}")
else:
    for idx, template in enumerate(templates, 1):
        _id = template.get('_id', {})
        preference = template.get('preference_id', template.get('preference_type', 'N/A'))
        is_system = template.get('is_system', False)
        status = template.get('status', 'N/A')
        
        content = template.get('content', {})
        system_prompt = content.get('system_prompt', '')
        
        print(f"{'=' * 80}")
        print(f"模板 {idx}: {preference} 偏好")
        print(f"  - _id: {_id}")
        print(f"  - is_system: {is_system}")
        print(f"  - status: {status}")
        print(f"\n系统提示词:")
        print(f"{'-' * 80}")
        print(system_prompt)
        print()

