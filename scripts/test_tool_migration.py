"""
测试工具迁移

验证新的插件化工具系统是否正常工作
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_tool_loader():
    """测试工具加载器"""
    print("\n" + "=" * 60)
    print("测试 1: 工具加载器")
    print("=" * 60)
    
    from core.tools import ToolLoader, get_tool_loader
    
    # 获取全局加载器
    loader = get_tool_loader()
    
    # 加载所有工具
    count = loader.load_all()
    print(f"✅ 加载了 {count} 个工具模块")
    
    # 显示已加载的模块
    modules = loader.get_loaded_modules()
    print(f"\n已加载的模块:")
    for module in modules:
        print(f"  - {module}")
    
    return True


def test_tool_registry():
    """测试工具注册表"""
    print("\n" + "=" * 60)
    print("测试 2: 工具注册表")
    print("=" * 60)
    
    from core.tools import ToolRegistry, get_tool_registry
    
    # 获取注册表
    registry = get_tool_registry()
    
    # 检查统一工具是否已注册
    unified_tools = [
        "get_stock_market_data_unified",
        "get_stock_fundamentals_unified",
        "get_stock_news_unified",
        "get_stock_sentiment_unified"
    ]
    
    print(f"\n检查统一工具注册状态:")
    for tool_id in unified_tools:
        if registry.has_tool(tool_id):
            metadata = registry.get_tool(tool_id)
            print(f"  ✅ {tool_id}")
            print(f"     名称: {metadata.name}")
            print(f"     类别: {metadata.category}")
            print(f"     在线: {metadata.is_online}")
        else:
            print(f"  ❌ {tool_id} - 未注册")
            return False
    
    # 获取所有工具
    all_tools = registry.get_all_tools()
    print(f"\n注册表中共有 {len(all_tools)} 个工具")
    
    # 按类别分组
    from collections import defaultdict
    by_category = defaultdict(list)
    for tool in all_tools:
        by_category[tool.category].append(tool.id)
    
    print(f"\n按类别分组:")
    for category, tools in sorted(by_category.items()):
        print(f"  {category}: {len(tools)} 个工具")
        for tool_id in tools:
            print(f"    - {tool_id}")
    
    return True


def test_tool_functions():
    """测试工具函数获取"""
    print("\n" + "=" * 60)
    print("测试 3: 工具函数获取")
    print("=" * 60)
    
    from core.tools import ToolRegistry, get_tool_registry
    
    registry = get_tool_registry()
    
    # 测试获取工具函数
    tool_id = "get_stock_market_data_unified"
    
    if registry.has_tool(tool_id):
        # 获取函数
        func = registry.get_function(tool_id)
        print(f"✅ 成功获取工具函数: {tool_id}")
        print(f"   函数名: {func.__name__}")
        print(f"   文档: {func.__doc__[:100]}...")
        
        # 获取 LangChain 工具
        lc_tool = registry.get_langchain_tool(tool_id)
        print(f"✅ 成功获取 LangChain 工具")
        print(f"   工具名: {lc_tool.name}")
        print(f"   描述: {lc_tool.description[:100]}...")
        
        return True
    else:
        print(f"❌ 工具未注册: {tool_id}")
        return False


def test_binding_manager():
    """测试绑定管理器"""
    print("\n" + "=" * 60)
    print("测试 4: 绑定管理器")
    print("=" * 60)
    
    from core.config import BindingManager
    
    bm = BindingManager()
    
    # 测试获取 Agent 的工具列表
    agent_id = "market_analyst"
    tools = bm.get_tools_for_agent(agent_id)
    
    print(f"Agent '{agent_id}' 的工具:")
    for tool_id in tools:
        print(f"  - {tool_id}")
    
    # 验证工具是否在注册表中
    from core.tools import get_tool_registry
    registry = get_tool_registry()
    
    print(f"\n验证工具是否已注册:")
    for tool_id in tools:
        if registry.has_tool(tool_id):
            print(f"  ✅ {tool_id}")
        else:
            print(f"  ❌ {tool_id} - 未在注册表中")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧪 工具迁移测试")
    print("=" * 60)
    
    tests = [
        ("工具加载器", test_tool_loader),
        ("工具注册表", test_tool_registry),
        ("工具函数获取", test_tool_functions),
        ("绑定管理器", test_binding_manager),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"测试失败 '{name}': {e}", exc_info=True)
            results.append((name, False))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    # 返回是否所有测试都通过
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n❌ 部分测试失败")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

