import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pymongo import MongoClient
from app.core.config import settings

client = MongoClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]

agents = ['bull_researcher_v2','bear_researcher_v2','research_manager_v2','risky_analyst_v2','safe_analyst_v2','neutral_analyst_v2','risk_manager_v2','trader_v2','valuation_analyst_v1']

print("=" * 60)
print("agent_configs 集合:")
for a in agents:
    doc = db.agent_configs.find_one({"agent_id": a})
    if doc:
        print(f'  {a}: 存在, enabled={doc.get("enabled")}, source={doc.get("metadata",{}).get("source","?")}')
    else:
        print(f'  {a}: 不存在')

print("\n" + "=" * 60)
print("registry 中已注册的 agent:")
try:
    from core.agents.registry import AgentRegistry
    reg = AgentRegistry()
    for a in agents:
        if reg.is_registered(a):
            print(f'  {a}: 已注册')
        else:
            print(f'  {a}: 未注册')
except Exception as e:
    print(f'  registry 查询失败: {e}')

client.close()
