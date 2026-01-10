"""
测试调试 agents API
"""
import requests

url = "http://localhost:8000/api/templates/debug/agents"

try:
    response = requests.get(url)
    response.raise_for_status()
    
    data = response.json()
    
    if data.get("success"):
        agents = data.get("data", [])
        print(f"✅ 成功获取 {len(agents)} 个 agents\n")
        
        # 按版本分组
        v1_agents = [a for a in agents if a.get("version") == "v1.0"]
        v2_agents = [a for a in agents if a.get("version") == "v2.0"]
        
        print(f"v1.0 agents ({len(v1_agents)} 个):")
        for a in v1_agents:
            print(f"  - {a['id']}: {a['name']} ({a['category']})")
        
        print(f"\nv2.0 agents ({len(v2_agents)} 个):")
        for a in v2_agents:
            print(f"  - {a['id']}: {a['name']} ({a['category']})")
        
        # 检查是否有 manager 和 trader
        managers = [a for a in agents if a.get("category") == "manager"]
        traders = [a for a in agents if a.get("category") == "trader"]
        
        print(f"\n管理者 ({len(managers)} 个):")
        for a in managers:
            print(f"  - {a['id']}: {a['name']} (v{a['version']})")
        
        print(f"\n交易员 ({len(traders)} 个):")
        for a in traders:
            print(f"  - {a['id']}: {a['name']} (v{a['version']})")
    else:
        print(f"❌ API 返回失败: {data}")
        
except Exception as e:
    print(f"❌ 请求失败: {e}")

