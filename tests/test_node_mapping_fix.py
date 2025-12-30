"""
测试节点映射修复

验证：
1. 所有 v2 节点都有映射（包括 neutral_analyst_v2 等）
2. step_name 和 message 是不同的
3. step_name 是简短的中文名称
4. message 是详细的描述
"""

import pytest
from core.workflow.engine import WorkflowEngine


def test_v2_risk_analysts_mapping():
    """测试 v2 风险分析师节点映射"""
    
    engine = WorkflowEngine(None)
    
    # 测试所有 v2 风险分析师节点
    test_cases = [
        ("risky_analyst_v2", "激进分析师", "⚡ 激进分析师正在评估高风险机会..."),
        ("safe_analyst_v2", "保守分析师", "🛡️ 保守分析师正在评估风险因素..."),
        ("neutral_analyst_v2", "中性分析师", "⚖️ 中性分析师正在平衡风险收益..."),
        ("risk_manager_v2", "风险管理者", "👔 风险管理者正在做最终决策..."),
    ]
    
    print("\n测试 v2 风险分析师节点映射:")
    for node_name, expected_step_name, expected_message in test_cases:
        progress, message, step_name = engine._get_node_progress_info(node_name)
        
        print(f"\n节点: {node_name}")
        print(f"  进度: {progress}%")
        print(f"  步骤名称: {step_name}")
        print(f"  消息: {message}")
        
        # 验证步骤名称和消息是不同的
        assert step_name != message, f"步骤名称和消息不应该相同: {node_name}"
        
        # 验证步骤名称是简短的中文
        assert step_name == expected_step_name, f"步骤名称不匹配: 期望 '{expected_step_name}'，实际 '{step_name}'"
        
        # 验证消息是详细的描述
        assert message == expected_message, f"消息不匹配: 期望 '{expected_message}'，实际 '{message}'"
        
        # 验证步骤名称不包含英文下划线
        assert "_" not in step_name, f"步骤名称不应包含下划线: {step_name}"
        
        print(f"  ✅ 验证通过")


def test_all_v2_nodes_mapping():
    """测试所有 v2 节点都有正确的映射"""
    
    engine = WorkflowEngine(None)
    
    # 所有 v2 节点
    v2_nodes = [
        # 分析师
        "market_analyst_v2",
        "fundamentals_analyst_v2",
        "news_analyst_v2",
        "social_analyst_v2",
        "sector_analyst_v2",
        "index_analyst_v2",
        # 研究员
        "bull_researcher_v2",
        "bear_researcher_v2",
        "research_manager_v2",
        # 交易员
        "trader_v2",
        # 风险管理
        "risky_analyst_v2",
        "safe_analyst_v2",
        "neutral_analyst_v2",
        "risk_manager_v2",
    ]
    
    print("\n测试所有 v2 节点映射:")
    for node_name in v2_nodes:
        progress, message, step_name = engine._get_node_progress_info(node_name)
        
        print(f"\n{node_name}:")
        print(f"  步骤名称: {step_name}")
        print(f"  消息: {message}")
        
        # 验证返回值不为空
        assert progress is not None, f"进度不应为空: {node_name}"
        assert message is not None, f"消息不应为空: {node_name}"
        assert step_name is not None, f"步骤名称不应为空: {node_name}"
        
        # 验证步骤名称和消息是不同的
        assert step_name != message, f"步骤名称和消息不应该相同: {node_name}"
        
        # 验证步骤名称是中文（不包含 _v2 后缀）
        assert "_v2" not in step_name, f"步骤名称不应包含 _v2: {step_name}"
        assert "_" not in step_name, f"步骤名称不应包含下划线: {step_name}"
        
        # 验证消息包含 emoji 和中文描述
        assert len(message) > len(step_name), f"消息应该比步骤名称更详细: {node_name}"
        
        print(f"  ✅ 验证通过")


def test_step_name_vs_message_difference():
    """测试步骤名称和消息的区别"""
    
    engine = WorkflowEngine(None)
    
    test_cases = [
        ("market_analyst_v2", "市场分析师", "📈 市场分析师正在分析技术指标和市场趋势..."),
        ("neutral_analyst_v2", "中性分析师", "⚖️ 中性分析师正在平衡风险收益..."),
        ("trader_v2", "交易员", "💼 交易员正在制定交易计划..."),
    ]
    
    print("\n测试步骤名称和消息的区别:")
    for node_name, expected_step_name, expected_message in test_cases:
        progress, message, step_name = engine._get_node_progress_info(node_name)
        
        print(f"\n节点: {node_name}")
        print(f"  步骤名称 (current_step_name): {step_name}")
        print(f"  消息 (message): {message}")
        
        # 验证步骤名称是简短的
        assert len(step_name) < 10, f"步骤名称应该简短: {step_name}"
        
        # 验证消息是详细的
        assert len(message) > 10, f"消息应该详细: {message}"
        
        # 验证步骤名称不包含 emoji
        assert not any(ord(c) > 127 for c in step_name if c in "📈💰📰💬📊🐂🐻🔬💼⚡🛡️⚖️👔"), \
            f"步骤名称不应包含 emoji: {step_name}"
        
        # 验证消息包含 emoji
        assert any(ord(c) > 127 for c in message), f"消息应该包含 emoji: {message}"
        
        print(f"  ✅ 验证通过")


def test_v1_nodes_also_updated():
    """测试 v1 节点也更新了"""
    
    engine = WorkflowEngine(None)
    
    test_cases = [
        ("market_analyst", "市场分析师"),
        ("neutral_analyst", "中性分析师"),
        ("trader", "交易员"),
    ]
    
    print("\n测试 v1 节点也更新了:")
    for node_name, expected_step_name in test_cases:
        progress, message, step_name = engine._get_node_progress_info(node_name)
        
        print(f"\n节点: {node_name}")
        print(f"  步骤名称: {step_name}")
        print(f"  消息: {message}")
        
        # 验证步骤名称是中文
        assert step_name == expected_step_name, f"步骤名称不匹配: 期望 '{expected_step_name}'，实际 '{step_name}'"
        
        # 验证步骤名称和消息是不同的
        assert step_name != message, f"步骤名称和消息不应该相同: {node_name}"
        
        print(f"  ✅ 验证通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

