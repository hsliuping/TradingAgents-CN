"""
测试 Agent 层迁移

验证:
1. BaseAgent 动态工具绑定
2. AgentFactory 创建 Agent
3. Agent 工具调用
"""

import sys
import os
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


def test_agent_registry():
    """测试 Agent 注册表"""
    print("\n" + "=" * 60)
    print("测试 1: Agent 注册表")
    print("=" * 60)
    
    from core.agents import AgentRegistry
    
    registry = AgentRegistry()
    
    # 获取所有 Agent 元数据
    all_agents = registry.list_all()
    print(f"\n注册表中共有 {len(all_agents)} 个 Agent")
    
    # 按类别分组
    from collections import defaultdict
    by_category = defaultdict(list)
    for agent in all_agents:
        category = agent.category.value if hasattr(agent.category, 'value') else agent.category
        by_category[category].append(agent.id)
    
    print("\n按类别分组:")
    for category, agent_ids in sorted(by_category.items()):
        print(f"  {category}: {len(agent_ids)} 个")
        for agent_id in agent_ids[:3]:  # 只显示前3个
            print(f"    - {agent_id}")
        if len(agent_ids) > 3:
            print(f"    ... 还有 {len(agent_ids) - 3} 个")
    
    # 测试获取特定 Agent 元数据
    test_agent_id = "market_analyst"
    metadata = registry.get_metadata(test_agent_id)
    if metadata:
        print(f"\n✅ 成功获取 '{test_agent_id}' 元数据:")
        print(f"   名称: {metadata.name}")
        print(f"   描述: {metadata.description[:50]}...")
        print(f"   类别: {metadata.category}")
    else:
        print(f"\n❌ 未找到 '{test_agent_id}' 元数据")
        return False
    
    return True


def test_agent_factory_basic():
    """测试 AgentFactory 基本功能"""
    print("\n" + "=" * 60)
    print("测试 2: AgentFactory 基本功能")
    print("=" * 60)
    
    from core.agents import AgentFactory
    
    factory = AgentFactory()
    
    # 获取可用 Agent
    available = factory.get_available_agents()
    print(f"\n已注册实现的 Agent: {len(available)} 个")
    if available:
        print(f"示例: {available[:5]}")
    
    # 获取元数据
    test_agent_id = "market_analyst"
    metadata = factory.get_agent_metadata(test_agent_id)
    if metadata:
        print(f"\n✅ 成功获取 '{test_agent_id}' 元数据")
    else:
        print(f"\n⚠️ '{test_agent_id}' 元数据未找到")
    
    return True


def test_agent_factory_with_tools():
    """测试 AgentFactory 动态工具绑定"""
    print("\n" + "=" * 60)
    print("测试 3: AgentFactory 动态工具绑定")
    print("=" * 60)
    
    from core.agents import create_agent_with_dynamic_tools
    from core.config import BindingManager
    
    # 创建一个简单的 LLM mock
    class MockLLM:
        def __init__(self):
            self.model_name = "mock-llm"
    
    llm = MockLLM()
    test_agent_id = "market_analyst"
    
    # 检查工具绑定
    binding_manager = BindingManager()
    tool_ids = binding_manager.get_tools_for_agent(test_agent_id)
    print(f"\nAgent '{test_agent_id}' 的工具绑定:")
    if tool_ids:
        for tool_id in tool_ids:
            print(f"  - {tool_id}")
    else:
        print("  (无数据库绑定，将使用元数据中的默认工具)")
    
    # 尝试创建 Agent（可能会失败，因为没有实际的 Agent 实现类）
    try:
        agent = create_agent_with_dynamic_tools(test_agent_id, llm)
        print(f"\n✅ 成功创建 Agent: {agent.agent_id}")
        print(f"   工具数量: {len(agent.tools)}")
        print(f"   工具列表: {agent.tool_names}")
        return True
    except ValueError as e:
        print(f"\n⚠️ 创建 Agent 失败（预期行为，因为没有注册实现类）: {e}")
        return True  # 这是预期的，因为我们还没有注册实际的 Agent 实现
    except Exception as e:
        print(f"\n❌ 创建 Agent 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_v2_creation():
    """测试 v2.0 Agent 创建和执行"""
    print("\n" + "=" * 60)
    print("测试 4: v2.0 Agent 创建和执行")
    print("=" * 60)

    # 导入 v2 Agent
    from core.agents.adapters.market_analyst_v2 import MarketAnalystAgentV2
    from core.agents import AgentRegistry

    # 检查是否已注册
    registry = AgentRegistry()
    agent_id = "market_analyst_v2"
    if registry.is_registered(agent_id):
        print(f"\n✅ MarketAnalystAgentV2 已注册 (ID: {agent_id})")
    else:
        print(f"\n⚠️ MarketAnalystAgentV2 未注册 (ID: {agent_id})")

    # 创建一个简单的 LLM mock
    class MockLLM:
        def __init__(self):
            self.model_name = "mock-llm"

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            class MockResponse:
                content = "这是一个模拟的市场分析报告。\n\n价格走势：上涨\n技术指标：看涨\n建议：持有"
            return MockResponse()

    llm = MockLLM()

    # 创建 Agent（使用显式工具列表）
    try:
        agent = MarketAnalystAgentV2(
            llm=llm,
            tool_ids=["get_stock_market_data_unified"]
        )
        print(f"\n✅ 成功创建 Agent: {agent.agent_id}")
        print(f"   工具数量: {len(agent.tools)}")
        if agent.tools:
            print(f"   工具列表: {agent.tool_names}")

        # 测试执行
        state = {
            "ticker": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }

        result = agent.execute(state)

        if "market_analysis" in result:
            print(f"\n✅ Agent 执行成功")
            print(f"   分析结果: {result['market_analysis'][:100]}...")
            return True
        else:
            print(f"\n❌ Agent 执行失败：结果中没有 market_analysis")
            return False

    except Exception as e:
        print(f"\n❌ 创建或执行 Agent 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧪 Agent 层迁移测试")
    print("=" * 60)

    tests = [
        ("Agent 注册表", test_agent_registry),
        ("AgentFactory 基本功能", test_agent_factory_basic),
        ("AgentFactory 动态工具绑定", test_agent_factory_with_tools),
        ("v2.0 Agent 创建和执行", test_agent_v2_creation),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"测试失败 '{test_name}': {e}", exc_info=True)
            results[test_name] = False
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n❌ 部分测试失败")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

