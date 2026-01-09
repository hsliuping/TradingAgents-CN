"""
检查 sector_analyst_v2 的工具绑定
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db
from core.tools.registry import ToolRegistry


async def main():
    print("=" * 80)
    print("检查 sector_analyst_v2 的工具绑定")
    print("=" * 80)
    
    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    # 查询数据库中的工具绑定
    print("\n1. 数据库中的工具绑定:")
    bindings = await db.tool_agent_bindings.find({
        "agent_id": "sector_analyst_v2"
    }).to_list(length=None)
    
    for binding in bindings:
        print(f"   - {binding['tool_id']}")
    
    # 查询工具注册表
    print("\n2. 工具注册表中的工具:")
    registry = ToolRegistry()
    all_tools = registry.list_all()
    
    sector_tools = [t for t in all_tools if 'sector' in t.id.lower()]
    for tool in sector_tools:
        print(f"   - {tool.id} ({tool.name})")
    
    # 检查绑定的工具是否存在
    print("\n3. 检查绑定的工具是否存在:")
    for binding in bindings:
        tool_id = binding['tool_id']
        tool = registry.get(tool_id)
        if tool:
            print(f"   ✅ {tool_id} - 存在")
        else:
            print(f"   ❌ {tool_id} - 不存在")
            
            # 查找相似的工具
            similar = [t for t in all_tools if tool_id.replace('_', '') in t.id.replace('_', '')]
            if similar:
                print(f"      可能的替代工具:")
                for t in similar:
                    print(f"        - {t.id}")


if __name__ == "__main__":
    asyncio.run(main())

