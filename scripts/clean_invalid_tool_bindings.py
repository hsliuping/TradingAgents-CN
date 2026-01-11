#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清理无效的工具-Agent 绑定关系

删除 tool_agent_bindings 集合中引用了不存在工具的绑定记录
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_mongo_db_sync
from core.tools import get_tool_registry


def main():
    """主函数"""
    print("=" * 80)
    print("清理无效的工具-Agent 绑定关系")
    print("=" * 80)
    
    # 获取数据库
    db = get_mongo_db_sync()
    
    # 获取所有已注册的工具
    registry = get_tool_registry()
    registered_tools = set(registry._tools.keys())
    print(f"\n✅ 已注册的工具数量: {len(registered_tools)}")
    
    # 获取所有绑定关系
    bindings = list(db.tool_agent_bindings.find({}))
    print(f"📊 绑定关系总数: {len(bindings)}")
    
    # 检查无效的绑定
    print("\n🔍 检查无效绑定...")
    invalid_bindings = []
    
    for binding in bindings:
        tool_id = binding.get('tool_id')
        agent_id = binding.get('agent_id')
        
        if tool_id not in registered_tools:
            invalid_bindings.append(binding)
            print(f"  ❌ 无效绑定: tool_id={tool_id}, agent_id={agent_id}")
    
    print(f"\n📈 统计:")
    print(f"  - 总绑定数: {len(bindings)}")
    print(f"  - 有效绑定: {len(bindings) - len(invalid_bindings)}")
    print(f"  - 无效绑定: {len(invalid_bindings)}")
    
    if not invalid_bindings:
        print("\n✅ 没有发现无效绑定，无需清理")
        return
    
    # 确认删除
    print("\n⚠️  即将删除以下无效绑定:")
    for binding in invalid_bindings:
        print(f"  - {binding.get('tool_id')} -> {binding.get('agent_id')}")
    
    confirm = input("\n是否继续删除？(yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("❌ 取消删除操作")
        return
    
    # 删除无效绑定
    print("\n🗑️  正在删除无效绑定...")
    deleted_count = 0
    
    for binding in invalid_bindings:
        result = db.tool_agent_bindings.delete_one({'_id': binding['_id']})
        deleted_count += result.deleted_count
        if result.deleted_count > 0:
            print(f"  ✅ 已删除: {binding.get('tool_id')} -> {binding.get('agent_id')}")
    
    print(f"\n✅ 清理完成！共删除 {deleted_count} 条无效绑定")
    
    # 验证结果
    remaining_bindings = db.tool_agent_bindings.count_documents({})
    print(f"📊 剩余绑定数: {remaining_bindings}")


if __name__ == "__main__":
    main()

