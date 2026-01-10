"""检查 risk_manager 的完整提示词内容"""
import json

# 读取数据库导出文件
with open('install/database_export_config_2026-01-05.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取 prompt_templates 集合
all_data = data.get('data', {})
templates_data = all_data.get('prompt_templates', [])

# 查找 managers/risk_manager (neutral)
template = None
for t in templates_data:
    if (t.get('agent_type') == 'managers' and 
        t.get('agent_name') == 'risk_manager' and
        t.get('preference_id') == 'neutral'):
        template = t
        break

if not template:
    # 尝试找第一个 managers/risk_manager
    for t in templates_data:
        if (t.get('agent_type') == 'managers' and 
            t.get('agent_name') == 'risk_manager'):
            template = t
            break

if template:
    print("=" * 80)
    print("找到 managers/risk_manager 模板")
    print("=" * 80)
    
    content = template.get('content', {})
    
    print("\n📋 系统提示词 (system_prompt):")
    print("-" * 80)
    print(content.get('system_prompt', ''))
    
    print("\n\n🔧 工具指导 (tool_guidance):")
    print("-" * 80)
    print(content.get('tool_guidance', ''))
    
    print("\n\n📊 分析要求 (analysis_requirements):")
    print("-" * 80)
    print(content.get('analysis_requirements', ''))
    
    print("\n\n📝 输出格式 (output_format):")
    print("-" * 80)
    print(content.get('output_format', ''))
    
    print("\n\n⚠️ 约束条件 (constraints):")
    print("-" * 80)
    print(content.get('constraints', ''))
    
else:
    print("❌ 未找到 managers/risk_manager 模板")

