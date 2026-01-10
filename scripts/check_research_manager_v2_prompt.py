"""检查 research_manager_v2 的提示词模板"""
import json

# 读取数据库导出文件
with open('install/database_export_config_2026-01-05.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取 prompt_templates 集合
all_data = data.get('data', {})
templates_data = all_data.get('prompt_templates', [])

# 查找所有 research_manager_v2 模板
all_templates = [t for t in templates_data
                 if 'research_manager_v2' in t.get('agent_type', 'managers_v2')]

print(f"找到 {len(all_templates)} 个 research_manager_v2 模板:")
for t in all_templates:
    print(f"  - {t.get('agent_type')}/{t.get('agent_name')} - {t.get('preference_type')}")

# 查找 neutral 偏好的模板
templates = [t for t in all_templates if t.get('preference_type') == 'neutral']

print(f"\n找到 {len(templates)} 个 neutral 偏好模板\n")

if templates:
    template = templates[0]
    content = template.get('content', {})
    
    print(f"{'=' * 80}")
    print(f"系统提示词:")
    print(f"{'=' * 80}")
    print(content.get('system_prompt', ''))
    
    print(f"\n{'=' * 80}")
    print(f"输出格式:")
    print(f"{'=' * 80}")
    print(content.get('output_format', ''))
    
    print(f"\n{'=' * 80}")
    print(f"分析要求:")
    print(f"{'=' * 80}")
    print(content.get('analysis_requirements', ''))

