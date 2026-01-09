"""
检查所有工具绑定的一致性

检查项：
1. 数据库中绑定的工具是否在工具注册表中存在
2. 列出所有不一致的绑定
3. 提供修复建议

使用方法：
    python scripts/check_all_tool_bindings.py
"""

import asyncio
import sys
from pathlib import Path
from collections import defaultdict

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db
from core.tools.registry import ToolRegistry


async def main():
    print("=" * 80)
    print("检查所有工具绑定的一致性")
    print("=" * 80)
    
    # 初始化数据库
    print("\n📡 连接数据库...")
    await init_database()
    db = get_mongo_db()
    print("✅ 数据库连接成功")
    
    # 初始化工具注册表
    print("\n📦 加载工具注册表...")
    registry = ToolRegistry()
    all_tools = registry.list_all()
    registered_tool_ids = {tool.id for tool in all_tools}
    print(f"✅ 工具注册表中有 {len(registered_tool_ids)} 个工具")
    
    # 查询所有工具绑定
    print("\n📊 查询数据库中的工具绑定...")
    bindings = await db.tool_agent_bindings.find({}).to_list(length=None)
    print(f"✅ 数据库中有 {len(bindings)} 条工具绑定")
    
    # 按 agent_id 分组
    bindings_by_agent = defaultdict(list)
    for binding in bindings:
        bindings_by_agent[binding['agent_id']].append(binding)
    
    # 检查一致性
    print("\n" + "=" * 80)
    print("检查结果")
    print("=" * 80)
    
    missing_tools = []
    valid_bindings = []
    
    for agent_id, agent_bindings in sorted(bindings_by_agent.items()):
        print(f"\n🤖 Agent: {agent_id}")
        
        for binding in agent_bindings:
            tool_id = binding['tool_id']
            
            if tool_id in registered_tool_ids:
                print(f"   ✅ {tool_id}")
                valid_bindings.append(binding)
            else:
                print(f"   ❌ {tool_id} - 工具不存在")
                missing_tools.append({
                    'agent_id': agent_id,
                    'tool_id': tool_id,
                    'binding_id': binding['_id']
                })
    
    # 汇总统计
    print("\n" + "=" * 80)
    print("统计汇总")
    print("=" * 80)
    print(f"✅ 有效绑定: {len(valid_bindings)} 条")
    print(f"❌ 无效绑定: {len(missing_tools)} 条")
    
    # 详细列出无效绑定
    if missing_tools:
        print("\n" + "=" * 80)
        print("无效绑定详情")
        print("=" * 80)
        
        for item in missing_tools:
            print(f"\n❌ Agent: {item['agent_id']}")
            print(f"   工具 ID: {item['tool_id']}")
            print(f"   绑定 ID: {item['binding_id']}")
            
            # 查找相似的工具
            similar_tools = find_similar_tools(item['tool_id'], registered_tool_ids)
            if similar_tools:
                print(f"   💡 可能的替代工具:")
                for similar in similar_tools:
                    print(f"      - {similar}")
    
    # 生成修复建议
    if missing_tools:
        print("\n" + "=" * 80)
        print("修复建议")
        print("=" * 80)
        
        print("\n方法 1: 使用 MongoDB 命令修复")
        print("-" * 80)
        for item in missing_tools:
            similar = find_similar_tools(item['tool_id'], registered_tool_ids)
            if similar:
                suggested_tool = similar[0]
                print(f"""
db.tool_agent_bindings.updateOne(
    {{ "_id": ObjectId("{item['binding_id']}") }},
    {{ "$set": {{ "tool_id": "{suggested_tool}" }} }}
)
""")
        
        print("\n方法 2: 删除无效绑定")
        print("-" * 80)
        for item in missing_tools:
            print(f"""
db.tool_agent_bindings.deleteOne(
    {{ "_id": ObjectId("{item['binding_id']}") }}
)
""")
    
    else:
        print("\n✅ 所有工具绑定都是有效的！")
    
    # 列出所有已注册的工具（按类别）
    print("\n" + "=" * 80)
    print("已注册的工具列表（按类别）")
    print("=" * 80)
    
    tools_by_category = defaultdict(list)
    for tool in all_tools:
        tools_by_category[tool.category].append(tool.id)
    
    for category, tool_ids in sorted(tools_by_category.items()):
        print(f"\n📁 {category}:")
        for tool_id in sorted(tool_ids):
            print(f"   - {tool_id}")


def find_similar_tools(target: str, registered_tools: set) -> list:
    """
    查找相似的工具 ID
    
    相似度判断：
    1. 包含相同的关键词
    2. 编辑距离较小
    """
    similar = []
    
    # 提取关键词
    target_keywords = set(target.lower().replace('_', ' ').split())
    
    for tool_id in registered_tools:
        tool_keywords = set(tool_id.lower().replace('_', ' ').split())
        
        # 计算关键词重叠度
        overlap = len(target_keywords & tool_keywords)
        
        if overlap >= 2:  # 至少有2个关键词重叠
            similar.append(tool_id)
    
    return sorted(similar)


if __name__ == "__main__":
    asyncio.run(main())

