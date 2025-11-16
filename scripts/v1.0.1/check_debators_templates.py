"""
检查debators模板是否存在
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
import os

# 连接MongoDB
connection_string = os.getenv('MONGODB_CONNECTION_STRING', 'mongodb://localhost:27017')
client = MongoClient(connection_string)
db = client['tradingagents']
collection = db['prompt_templates']

print("\n检查所有模板:")
print("=" * 80)

# 查询所有模板
all_templates = collection.find()
for doc in all_templates:
    agent_type = doc.get('agent_type', 'N/A')
    agent_name = doc.get('agent_name', 'N/A')
    preference = doc.get('preference_type', 'N/A')
    status = doc.get('status', 'N/A')
    print(f"{agent_type:15} / {agent_name:25} (preference: {preference:12}, status: {status})")

print("=" * 80)

# 特别检查debators
print("\n特别检查 risk_mgmt (debators):")
debators = list(collection.find({'agent_type': 'risk_mgmt'}))
print(f"找到 {len(debators)} 个debator模板")
for doc in debators:
    print(f"  - {doc['agent_name']} (preference: {doc.get('preference_type', 'N/A')})")

client.close()

