"""
测试配置管理器

验证工具、Agent、工作流配置管理器的功能
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 确保所有模块被加载
import core.agents.adapters  # noqa
import core.tools.implementations  # noqa


def test_tool_config_manager():
    """测试工具配置管理器"""
    print("\n" + "=" * 70)
    print("🧪 测试工具配置管理器")
    print("=" * 70)
    
    from core.config import ToolConfigManager
    from pymongo import MongoClient
    from app.core.config import settings
    
    # 连接数据库
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    
    manager = ToolConfigManager()
    manager.set_database(db)
    
    # 测试 1: 获取工具配置
    print("\n📝 测试 1: 获取工具配置...")
    tool_id = "get_stock_market_data_unified"
    config = manager.get_tool_config(tool_id)
    
    if config:
        print(f"   ✅ 获取配置成功:")
        print(f"      工具ID: {config.get('tool_id')}")
        print(f"      名称: {config.get('name')}")
        print(f"      启用: {config.get('enabled')}")
        print(f"      超时: {config.get('config', {}).get('timeout')}秒")
    else:
        print(f"   ❌ 获取配置失败")
        return False
    
    # 测试 2: 获取所有工具配置
    print("\n📝 测试 2: 获取所有工具配置...")
    all_configs = manager.get_all_tool_configs()
    print(f"   ✅ 共找到 {len(all_configs)} 个工具配置")
    for cfg in all_configs[:3]:  # 只显示前3个
        print(f"      - {cfg.get('tool_id')}: {cfg.get('name')}")
    
    # 测试 3: 更新工具运行时配置
    print("\n📝 测试 3: 更新工具运行时配置...")
    new_runtime_config = {
        "timeout": 60,
        "retry_count": 5,
        "cache_ttl": 600
    }
    success = manager.update_tool_runtime_config(tool_id, new_runtime_config)
    if success:
        print(f"   ✅ 运行时配置更新成功")
        # 验证更新
        updated_config = manager.get_tool_config(tool_id)
        print(f"      新超时: {updated_config.get('config', {}).get('timeout')}秒")
    else:
        print(f"   ❌ 运行时配置更新失败")
    
    client.close()
    return True


def test_agent_config_manager():
    """测试 Agent 配置管理器"""
    print("\n" + "=" * 70)
    print("🧪 测试 Agent 配置管理器")
    print("=" * 70)
    
    from core.config import AgentConfigManager
    from pymongo import MongoClient
    from app.core.config import settings
    
    # 连接数据库
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    
    manager = AgentConfigManager()
    manager.set_database(db)
    
    # 测试 1: 获取 Agent 配置
    print("\n📝 测试 1: 获取 Agent 配置...")
    agent_id = "market_analyst_v2"
    config = manager.get_agent_config(agent_id)
    
    if config:
        print(f"   ✅ 获取配置成功:")
        print(f"      Agent ID: {config.get('agent_id')}")
        print(f"      名称: {config.get('name')}")
        print(f"      启用: {config.get('enabled')}")
        print(f"      最大迭代: {config.get('config', {}).get('max_iterations')}")
        print(f"      默认工具: {config.get('default_tools')}")
    else:
        print(f"   ❌ 获取配置失败")
        return False
    
    # 测试 2: 获取所有 Agent 配置
    print("\n📝 测试 2: 获取所有 Agent 配置...")
    all_configs = manager.get_all_agent_configs()
    print(f"   ✅ 共找到 {len(all_configs)} 个 Agent 配置")
    for cfg in all_configs[:3]:  # 只显示前3个
        print(f"      - {cfg.get('agent_id')}: {cfg.get('name')}")
    
    # 测试 3: 更新 Agent 执行配置
    print("\n📝 测试 3: 更新 Agent 执行配置...")
    new_execution_config = {
        "max_iterations": 5,
        "timeout": 180,
        "temperature": 0.8
    }
    success = manager.update_agent_execution_config(agent_id, new_execution_config)
    if success:
        print(f"   ✅ 执行配置更新成功")
        # 验证更新
        updated_config = manager.get_agent_config(agent_id)
        print(f"      新最大迭代: {updated_config.get('config', {}).get('max_iterations')}")
    else:
        print(f"   ❌ 执行配置更新失败")
    
    client.close()
    return True


def test_workflow_config_manager():
    """测试工作流配置管理器"""
    print("\n" + "=" * 70)
    print("🧪 测试工作流配置管理器")
    print("=" * 70)
    
    from core.config import WorkflowConfigManager
    from pymongo import MongoClient
    from app.core.config import settings
    
    # 连接数据库
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    
    manager = WorkflowConfigManager()
    manager.set_database(db)

    # 测试 1: 创建工作流定义
    print("\n📝 测试 1: 创建工作流定义...")
    workflow_definition = {
        "workflow_id": "test_workflow",
        "name": "测试工作流",
        "description": "用于测试的简单工作流",
        "category": "test",
        "version": "1.0.0",
        "enabled": True,
        "execution_mode": "sequential",
        "nodes": [
            {"id": "start", "type": "start", "position": {"x": 100, "y": 100}},
            {"id": "agent1", "type": "agent", "agent_id": "market_analyst_v2", "position": {"x": 300, "y": 100}},
            {"id": "end", "type": "end", "position": {"x": 500, "y": 100}}
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "agent1"},
            {"id": "e2", "source": "agent1", "target": "end"}
        ],
        "parallel_groups": [],
        "config": {}
    }

    success = manager.save_workflow_definition(workflow_definition)
    if success:
        print(f"   ✅ 工作流定义创建成功")
    else:
        print(f"   ❌ 工作流定义创建失败")
        client.close()
        return False

    # 测试 2: 获取工作流定义
    print("\n📝 测试 2: 获取工作流定义...")
    definition = manager.get_workflow_definition("test_workflow")
    if definition:
        print(f"   ✅ 获取定义成功:")
        print(f"      工作流ID: {definition.get('workflow_id')}")
        print(f"      名称: {definition.get('name')}")
        print(f"      执行模式: {definition.get('execution_mode')}")
        print(f"      节点数: {len(definition.get('nodes', []))}")
        print(f"      边数: {len(definition.get('edges', []))}")
    else:
        print(f"   ❌ 获取定义失败")

    # 测试 3: 更新执行模式
    print("\n📝 测试 3: 更新执行模式...")
    success = manager.update_workflow_execution_mode("test_workflow", "parallel")
    if success:
        print(f"   ✅ 执行模式更新成功")
        # 验证更新
        updated_definition = manager.get_workflow_definition("test_workflow")
        print(f"      新执行模式: {updated_definition.get('execution_mode')}")
    else:
        print(f"   ❌ 执行模式更新失败")

    # 测试 4: 获取所有工作流定义
    print("\n📝 测试 4: 获取所有工作流定义...")
    all_definitions = manager.get_all_workflow_definitions()
    print(f"   ✅ 共找到 {len(all_definitions)} 个工作流定义")
    for defn in all_definitions:
        print(f"      - {defn.get('workflow_id')}: {defn.get('name')}")

    # 测试 5: 删除工作流定义
    print("\n📝 测试 5: 删除工作流定义...")
    success = manager.delete_workflow_definition("test_workflow")
    if success:
        print(f"   ✅ 工作流定义删除成功")
    else:
        print(f"   ❌ 工作流定义删除失败")

    client.close()
    return True


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("🧪 配置管理器测试")
    print("=" * 70)

    results = []

    # 测试工具配置管理器
    try:
        success = test_tool_config_manager()
        results.append(("工具配置管理器", success))
    except Exception as e:
        print(f"\n❌ 工具配置管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("工具配置管理器", False))

    # 测试 Agent 配置管理器
    try:
        success = test_agent_config_manager()
        results.append(("Agent 配置管理器", success))
    except Exception as e:
        print(f"\n❌ Agent 配置管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Agent 配置管理器", False))

    # 测试工作流配置管理器
    try:
        success = test_workflow_config_manager()
        results.append(("工作流配置管理器", success))
    except Exception as e:
        print(f"\n❌ 工作流配置管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("工作流配置管理器", False))

    # 打印测试总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")

    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n❌ 部分测试失败！")
        return 1


if __name__ == "__main__":
    exit(main())

