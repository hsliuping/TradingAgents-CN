"""检查旧版 trader 的提示词模板"""
import json

# 读取数据库导出文件
with open('install/database_export_config_2026-01-05.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取 prompt_templates 集合
all_data = data.get('data', {})
templates_data = all_data.get('prompt_templates', [])

# 查找 trader 模板
templates = [t for t in templates_data
             if (t.get('agent_type') == 'trader' and 
                 t.get('agent_name') == 'trader')]

print(f"找到 {len(templates)} 个 trader/trader 模板\n")

for idx, template in enumerate(templates, 1):
    preference = template.get('preference_id', template.get('preference_type', 'N/A'))
    content = template.get('content', {})
    
    print(f"{'=' * 80}")
    print(f"模板 {idx}: {preference} 偏好")
    print(f"{'=' * 80}")
    
    print(f"\n系统提示词:")
    print(f"{'-' * 80}")
    print(content.get('system_prompt', ''))
    
    print(f"\n{'-' * 80}")
    print(f"输出格式:")
    print(f"{'-' * 80}")
    print(content.get('output_format', ''))
    
    print(f"\n{'-' * 80}")
    print(f"分析要求:")
    print(f"{'-' * 80}")
    print(content.get('analysis_requirements', ''))
    
    print("\n")

