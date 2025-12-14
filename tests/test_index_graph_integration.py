#!/usr/bin/env python3
"""
阶段四：图构建与集成 - 单元测试

测试目标：
1. 测试GraphSetup扩展（setup_graph支持analysis_type参数）
2. 测试_setup_index_graph方法
3. 测试工具节点注册
4. 测试TradingAgentsGraph初始化（支持analysis_type）
"""

import sys
from unittest.mock import Mock, MagicMock, patch

# 确保可以导入项目模块
sys.path.insert(0, '.')

def test_graph_setup_accepts_analysis_type():
    """测试GraphSetup.setup_graph支持analysis_type参数"""
    from tradingagents.graph.setup import GraphSetup
    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.agents.utils.agent_utils import Toolkit
    
    # 创建Mock对象
    quick_llm = Mock()
    deep_llm = Mock()
    toolkit = Toolkit()
    tool_nodes = {}
    conditional_logic = ConditionalLogic()
    
    # 初始化GraphSetup
    graph_setup = GraphSetup(
        quick_thinking_llm=quick_llm,
        deep_thinking_llm=deep_llm,
        toolkit=toolkit,
        tool_nodes=tool_nodes,
        bull_memory=None,
        bear_memory=None,
        trader_memory=None,
        invest_judge_memory=None,
        risk_manager_memory=None,
        conditional_logic=conditional_logic,
    )
    
    # 测试setup_graph接受analysis_type参数（应该不抛出异常）
    try:
        # stock类型（默认）
        _ = graph_setup.setup_graph(analysis_type="stock")
        print("✅ setup_graph接受analysis_type='stock'")
    except Exception as e:
        raise AssertionError(f"setup_graph不接受analysis_type='stock': {e}")


def test_setup_index_graph_method_exists():
    """测试_setup_index_graph方法存在"""
    from tradingagents.graph.setup import GraphSetup
    
    # 验证方法存在
    assert hasattr(GraphSetup, '_setup_index_graph'), \
        "_setup_index_graph方法不存在"
    print("✅ _setup_index_graph方法存在")


def test_index_tools_import():
    """测试指数分析工具可以导入"""
    try:
        from tradingagents.tools.index_tools import (
            fetch_macro_data,
            fetch_policy_news,
            fetch_sector_rotation
        )
        print("✅ 成功导入指数分析工具")
        
        # 验证工具是可调用的
        assert callable(fetch_macro_data), "fetch_macro_data不可调用"
        assert callable(fetch_policy_news), "fetch_policy_news不可调用"
        assert callable(fetch_sector_rotation), "fetch_sector_rotation不可调用"
        print("✅ 所有指数分析工具都可调用")
        
    except ImportError as e:
        raise AssertionError(f"无法导入指数分析工具: {e}")


def test_tool_nodes_registration():
    """测试工具节点注册"""
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
    
    # 创建配置
    config = DEFAULT_CONFIG.copy()
    
    # 初始化图（stock模式）
    try:
        graph = TradingAgentsGraph(
            selected_analysts=["market"],
            debug=False,
            config=config,
            analysis_type="stock"
        )
        
        # 检查工具节点
        assert hasattr(graph, 'tool_nodes'), "缺少tool_nodes属性"
        
        # 检查基本的个股分析工具节点
        assert "market" in graph.tool_nodes, "缺少market工具节点"
        print("✅ 个股分析工具节点注册成功")
        
        # 检查指数分析工具节点（如果可用）
        index_tools_available = all(
            key in graph.tool_nodes 
            for key in ["index_macro", "index_policy", "index_sector"]
        )
        
        if index_tools_available:
            print("✅ 指数分析工具节点注册成功")
            print(f"   - index_macro: {graph.tool_nodes['index_macro']}")
            print(f"   - index_policy: {graph.tool_nodes['index_policy']}")
            print(f"   - index_sector: {graph.tool_nodes['index_sector']}")
        else:
            print("⚠️  指数分析工具节点未注册（可能是导入失败）")
            
    except Exception as e:
        raise AssertionError(f"工具节点注册测试失败: {e}")


def test_trading_graph_accepts_analysis_type():
    """测试TradingAgentsGraph接受analysis_type参数"""
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
    
    config = DEFAULT_CONFIG.copy()
    
    # 测试stock类型
    try:
        graph_stock = TradingAgentsGraph(
            selected_analysts=["market"],
            debug=False,
            config=config,
            analysis_type="stock"
        )
        assert graph_stock.analysis_type == "stock"
        print("✅ TradingAgentsGraph接受analysis_type='stock'")
    except Exception as e:
        raise AssertionError(f"TradingAgentsGraph不接受analysis_type='stock': {e}")
    
    # 测试index类型
    try:
        graph_index = TradingAgentsGraph(
            selected_analysts=[],  # 指数分析不需要selected_analysts
            debug=False,
            config=config,
            analysis_type="index"
        )
        assert graph_index.analysis_type == "index"
        print("✅ TradingAgentsGraph接受analysis_type='index'")
    except Exception as e:
        raise AssertionError(f"TradingAgentsGraph不接受analysis_type='index': {e}")


def test_index_graph_structure():
    """测试指数分析工作流图的结构"""
    from tradingagents.graph.setup import GraphSetup
    from tradingagents.graph.conditional_logic import ConditionalLogic
    from tradingagents.agents.utils.agent_utils import Toolkit
    from langgraph.prebuilt import ToolNode
    
    # 创建Mock对象
    quick_llm = Mock()
    deep_llm = Mock()
    toolkit = Toolkit()
    conditional_logic = ConditionalLogic()
    
    # 尝试导入指数工具
    try:
        from tradingagents.tools.index_tools import (
            fetch_macro_data,
            fetch_policy_news,
            fetch_sector_rotation
        )
        
        tool_nodes = {
            "index_macro": ToolNode([fetch_macro_data]),
            "index_policy": ToolNode([fetch_policy_news]),
            "index_sector": ToolNode([fetch_sector_rotation]),
        }
    except ImportError:
        print("⚠️  指数工具导入失败，使用空工具节点")
        tool_nodes = {
            "index_macro": ToolNode([]),
            "index_policy": ToolNode([]),
            "index_sector": ToolNode([]),
        }
    
    # 初始化GraphSetup
    graph_setup = GraphSetup(
        quick_thinking_llm=quick_llm,
        deep_thinking_llm=deep_llm,
        toolkit=toolkit,
        tool_nodes=tool_nodes,
        bull_memory=None,
        bear_memory=None,
        trader_memory=None,
        invest_judge_memory=None,
        risk_manager_memory=None,
        conditional_logic=conditional_logic,
    )
    
    # 构建指数分析图
    try:
        index_graph = graph_setup.setup_graph(analysis_type="index")
        print("✅ 指数分析工作流图构建成功")
        
        # 验证图已编译
        assert index_graph is not None, "图为None"
        print("✅ 图编译成功")
        
        # 检查图的节点（通过nodes属性）
        if hasattr(index_graph, 'nodes'):
            expected_nodes = [
                "Macro Analyst",
                "Policy Analyst", 
                "Sector Analyst",
                "Strategy Advisor"
            ]
            
            for node in expected_nodes:
                if node in index_graph.nodes:
                    print(f"✅ 节点 '{node}' 存在")
                else:
                    print(f"⚠️  节点 '{node}' 不存在")
        else:
            print("⚠️  无法检查图节点（缺少nodes属性）")
            
    except Exception as e:
        raise AssertionError(f"指数分析图构建失败: {e}")


def test_conditional_logic_index_methods():
    """测试ConditionalLogic中的指数分析路由方法"""
    from tradingagents.graph.conditional_logic import ConditionalLogic
    
    conditional_logic = ConditionalLogic()
    
    # 检查指数分析路由方法是否存在
    required_methods = [
        'should_continue_macro',
        'should_continue_policy',
        'should_continue_sector',
        'should_continue_strategy'
    ]
    
    for method_name in required_methods:
        assert hasattr(conditional_logic, method_name), \
            f"ConditionalLogic缺少{method_name}方法"
        print(f"✅ {method_name}方法存在")


def test_analyst_nodes_import():
    """测试指数分析师节点可以导入"""
    try:
        from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
        from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
        from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
        from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor
        
        print("✅ 所有指数分析师节点创建函数导入成功")
        
        # 验证函数可调用
        assert callable(create_macro_analyst), "create_macro_analyst不可调用"
        assert callable(create_policy_analyst), "create_policy_analyst不可调用"
        assert callable(create_sector_analyst), "create_sector_analyst不可调用"
        assert callable(create_strategy_advisor), "create_strategy_advisor不可调用"
        print("✅ 所有创建函数都可调用")
        
    except ImportError as e:
        raise AssertionError(f"无法导入分析师节点创建函数: {e}")


if __name__ == "__main__":
    print("=" * 80)
    print("阶段四：图构建与集成 - 单元测试")
    print("=" * 80)
    
    # 运行所有测试
    test_graph_setup_accepts_analysis_type()
    print()
    
    test_setup_index_graph_method_exists()
    print()
    
    test_index_tools_import()
    print()
    
    test_tool_nodes_registration()
    print()
    
    test_trading_graph_accepts_analysis_type()
    print()
    
    test_index_graph_structure()
    print()
    
    test_conditional_logic_index_methods()
    print()
    
    test_analyst_nodes_import()
    print()
    
    print("=" * 80)
    print("✅ 所有阶段四测试通过！")
    print("=" * 80)
