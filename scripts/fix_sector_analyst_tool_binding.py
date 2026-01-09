"""
修复 sector_analyst_v2 的工具绑定

问题：数据库中绑定的 get_sector_performance 工具不存在
解决：将其改为 get_sector_data

使用方法：
    python scripts/fix_sector_analyst_tool_binding.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db


async def main():
    print("=" * 80)
    print("修复 sector_analyst_v2 的工具绑定")
    print("=" * 80)
    
    # 初始化数据库
    print("\n📡 连接数据库...")
    await init_database()
    db = get_mongo_db()
    print("✅ 数据库连接成功")
    
    # 查询当前绑定
    print("\n1. 查询当前绑定:")
    bindings = await db.tool_agent_bindings.find({
        "agent_id": "sector_analyst_v2"
    }).to_list(length=None)
    
    for binding in bindings:
        print(f"   - {binding['tool_id']}")
    
    # 查找需要修复的绑定
    print("\n2. 查找需要修复的绑定:")
    wrong_binding = await db.tool_agent_bindings.find_one({
        "agent_id": "sector_analyst_v2",
        "tool_id": "get_sector_performance"
    })
    
    if not wrong_binding:
        print("   ℹ️  未找到需要修复的绑定")
        return
    
    print(f"   ❌ 找到错误绑定: get_sector_performance")
    print(f"      _id: {wrong_binding['_id']}")
    
    # 更新绑定
    print("\n3. 更新绑定:")
    result = await db.tool_agent_bindings.update_one(
        {"_id": wrong_binding["_id"]},
        {"$set": {"tool_id": "get_sector_data"}}
    )
    
    if result.modified_count > 0:
        print("   ✅ 更新成功: get_sector_performance -> get_sector_data")
    else:
        print("   ⚠️  未更新任何记录")
    
    # 验证修复
    print("\n4. 验证修复:")
    updated_bindings = await db.tool_agent_bindings.find({
        "agent_id": "sector_analyst_v2"
    }).to_list(length=None)
    
    for binding in updated_bindings:
        print(f"   ✅ {binding['tool_id']}")
    
    print("\n" + "=" * 80)
    print("✅ 修复完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

