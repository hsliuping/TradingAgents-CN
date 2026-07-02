import sys
sys.path.insert(0, '.')

from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27019/')
db = client['trading_agents_v3']

cursor = db['prompt_templates'].find({
    'template_name': {'$regex': '风险评估助手'}
}).sort('created_at', -1)
templates = list(cursor)
print(f'找到 {len(templates)} 个相关模板：')
print()
for t in templates:
    print(f'  template_name: {t.get("template_name")}')
    print(f'  agent_type: {t.get("agent_type")}')
    print(f'  agent_name: {t.get("agent_name")}')
    print(f'  status: {t.get("status")}')
    print(f'  is_system: {t.get("is_system")}')
    print(f'  created_at: {t.get("created_at")}')
    print(f'  updated_at: {t.get("updated_at")}')
    print(f'  remark: {str(t.get("remark", ""))[:100]}')
    print()

client.close()
