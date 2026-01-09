"""
检查工具绑定数据
"""
import os
import sys
from pymongo import MongoClient

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings

def check_bindings():
    """检查工具绑定"""
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]
    
    print("=" * 80)
    print("检查 tool_agent_bindings 集合")
    print("=" * 80)
    
    # 检查 sector_analyst_v2 的绑定
    agent_id = "sector_analyst_v2"
    bindings = list(db.tool_agent_bindings.find({"agent_id": agent_id}))
    
    print(f"\n🔍 查询条件: agent_id = '{agent_id}'")
    print(f"📦 找到 {len(bindings)} 条绑定记录\n")
    
    if bindings:
        for idx, binding in enumerate(bindings, 1):
            print(f"[{idx}] 绑定记录:")
            print(f"    - _id: {binding.get('_id')}")
            print(f"    - agent_id: {binding.get('agent_id')}")
            print(f"    - tool_id: {binding.get('tool_id')}")
            print(f"    - enabled: {binding.get('enabled', True)}")
            print(f"    - priority: {binding.get('priority', 0)}")
            print()
    else:
        print("⚠️ 没有找到任何绑定记录！")
        print("\n可能的原因:")
        print("1. 数据库中确实没有绑定数据")
        print("2. agent_id 不匹配（大小写、下划线等）")
        print("3. 集合名称错误")
    
    # 检查集合中的所有数据
    print("\n" + "=" * 80)
    print("检查集合中的所有绑定记录")
    print("=" * 80)
    
    all_bindings = list(db.tool_agent_bindings.find().limit(10))
    print(f"\n📦 集合中共有 {db.tool_agent_bindings.count_documents({})} 条记录")
    print(f"📋 显示前 10 条:\n")
    
    if all_bindings:
        for idx, binding in enumerate(all_bindings, 1):
            print(f"[{idx}] agent_id: {binding.get('agent_id')}, tool_id: {binding.get('tool_id')}")
    else:
        print("⚠️ 集合为空！")
    
    # 检查是否有类似的 agent_id
    print("\n" + "=" * 80)
    print("检查是否有类似的 agent_id")
    print("=" * 80)
    
    similar_agents = db.tool_agent_bindings.distinct("agent_id")
    print(f"\n📋 集合中的所有 agent_id ({len(similar_agents)} 个):\n")
    
    for agent in sorted(similar_agents):
        count = db.tool_agent_bindings.count_documents({"agent_id": agent})
        marker = "👉" if "sector" in agent.lower() else "  "
        print(f"{marker} {agent} ({count} 个工具)")
    
    client.close()

if __name__ == "__main__":
    check_bindings()

