"""
通过API检查所有模板
"""

import requests
import json

# 获取所有模板
response = requests.get('http://127.0.0.1:8000/api/v1/templates')
if response.status_code == 200:
    data = response.json()
    print(f'API响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...')

    # 检查响应格式
    if isinstance(data, dict) and 'data' in data:
        templates = data['data']
    else:
        templates = data

    print(f'\n总共 {len(templates)} 个模板')
    print()

    # 按agent_type分组
    by_type = {}
    for t in templates:
        agent_type = t['agent_type']
        if agent_type not in by_type:
            by_type[agent_type] = []
        by_type[agent_type].append(t)

    for agent_type in sorted(by_type.keys()):
        print(f'{agent_type}:')
        for t in by_type[agent_type]:
            pref = t.get('preference_type', 'N/A')
            print(f"  - {t['agent_name']} (preference: {pref})")
else:
    print(f'错误: {response.status_code}')

