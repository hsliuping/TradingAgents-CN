"""
检查所有模板
"""

import requests
import json

# 获取所有模板
response = requests.get('http://127.0.0.1:8000/api/v1/templates')
if response.status_code == 200:
    data = response.json()
    print("\n所有模板:")
    print("=" * 80)

    # 检查返回的数据结构
    if isinstance(data, dict) and "templates" in data:
        templates = data["templates"]
    else:
        templates = data

    for t in templates:
        if isinstance(t, dict):
            agent_type = t.get("agent_type", "unknown")
            agent_name = t.get("agent_name", "unknown")
            status = t.get("status", "unknown")
            is_system = t.get("is_system", False)
            print(f"  {agent_type}/{agent_name} (status: {status}, is_system: {is_system})")

    print("\n" + "=" * 80)
    print(f"总计: {len(templates)} 个模板")
else:
    print(f"错误: {response.status_code}")
    print(response.text)

