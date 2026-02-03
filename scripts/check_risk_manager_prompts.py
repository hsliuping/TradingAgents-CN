"""检查 risk_manager 的提示词模板"""
import json

# 读取数据库导出文件
with open('install/database_export_config_2026-01-05.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取 prompt_templates 集合
all_data = data.get('data', {})
templates_data = all_data.get('prompt_templates', [])

# 查找 risk_manager 相关的模板
templates = [t for t in templates_data
             if 'risk_manager' in t.get('agent_name', '')]

print(f"找到 {len(templates)} 个 risk_manager 模板:\n")

for t in templates:
    agent_type = t.get('agent_type', 'N/A')
    agent_name = t.get('agent_name', 'N/A')
    preference = t.get('preference_id', 'N/A')
    
    print(f"=" * 80)
    print(f"Agent: {agent_type}/{agent_name}")
    print(f"偏好: {preference}")
    print(f"-" * 80)
    
    content = t.get('content', {})
    system_prompt = content.get('system_prompt', '')
    
    # 检查是否提到 final_trade_decision
    if 'final_trade_decision' in system_prompt.lower() or '最终分析结果' in system_prompt:
        print("⚠️ 提示词中提到了 'final_trade_decision' 或 '最终分析结果'")
        print(f"\n相关内容:")
        lines = system_prompt.split('\n')
        for i, line in enumerate(lines):
            if 'final_trade_decision' in line.lower() or '最终分析结果' in line:
                print(f"  第 {i+1} 行: {line.strip()}")
    else:
        print("✅ 提示词中未提到 'final_trade_decision' 或 '最终分析结果'")
    
    print(f"\n系统提示词前300字符:")
    print(system_prompt[:300])
    print()

