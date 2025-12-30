"""测试步骤名称和消息的分离

验证：
1. current_step_name 应该是简短的中文名称（如 "市场分析师"）
2. message 应该是详细的描述（如 "📈 市场分析师正在分析技术指标和市场趋势..."）
3. current_step_description 应该与 message 相同
"""

import pytest


def test_node_mapping_returns_three_values():
    """测试节点映射返回三个值：进度、消息、步骤名称"""
    from core.workflow.engine import WorkflowEngine
    
    # 创建引擎实例
    engine = WorkflowEngine()
    
    # 测试几个关键节点
    test_nodes = [
        "market_analyst_v2",
        "fundamentals_analyst_v2",
        "news_analyst_v2",
        "neutral_analyst_v2",
        "risk_manager_v2",
    ]
    
    for node_name in test_nodes:
        progress, message, step_name = engine._get_node_progress_info(node_name)
        
        print(f"\n节点: {node_name}")
        print(f"  进度: {progress}%")
        print(f"  步骤名称: {step_name}")
        print(f"  消息: {message}")
        
        # 验证返回值
        assert progress is not None, f"{node_name} 的进度不应为 None"
        assert isinstance(progress, (int, float)), f"{node_name} 的进度应该是数字"
        assert message is not None, f"{node_name} 的消息不应为 None"
        assert step_name is not None, f"{node_name} 的步骤名称不应为 None"
        
        # 验证步骤名称和消息不同
        assert step_name != message, f"{node_name} 的步骤名称和消息应该不同"
        
        # 验证步骤名称是简短的（不包含 emoji 和详细描述）
        assert len(step_name) < len(message), f"{node_name} 的步骤名称应该比消息短"
        
        # 验证消息包含 emoji 或详细描述
        assert len(message) > 10, f"{node_name} 的消息应该是详细的描述"


def test_progress_callback_parameters():
    """测试进度回调接收正确的参数"""
    from core.workflow.engine import WorkflowEngine
    
    # 创建引擎实例
    engine = WorkflowEngine()
    
    # 记录回调参数
    callback_params = []
    
    def test_callback(progress: float, message: str, **kwargs):
        """测试回调函数"""
        callback_params.append({
            "progress": progress,
            "message": message,
            "step_name": kwargs.get("step_name"),
            "kwargs": kwargs
        })
    
    # 设置回调
    engine.set_progress_callback(test_callback)
    
    # 模拟进度报告
    engine._report_progress(
        progress=50,
        message="📈 市场分析师正在分析技术指标和市场趋势...",
        step_name="市场分析师"
    )
    
    # 验证回调参数
    assert len(callback_params) == 1, "应该调用一次回调"
    
    params = callback_params[0]
    assert params["progress"] == 50, "进度应该是 50"
    assert params["message"] == "📈 市场分析师正在分析技术指标和市场趋势...", "消息应该是详细描述"
    assert params["step_name"] == "市场分析师", "步骤名称应该是简短名称"
    
    print("\n✅ 进度回调参数验证通过:")
    print(f"  进度: {params['progress']}%")
    print(f"  步骤名称: {params['step_name']}")
    print(f"  消息: {params['message']}")


def test_redis_progress_tracker_fields():
    """测试 RedisProgressTracker 的字段"""
    from app.services.progress.tracker import RedisProgressTracker
    
    # 创建 tracker
    tracker = RedisProgressTracker(
        task_id="test_task",
        analysts=["market", "fundamentals"],
        research_depth="标准",
        llm_provider="dashscope"
    )
    
    # 更新进度（模拟工作流引擎的回调）
    tracker.update_progress({
        "progress_percentage": 50,
        "last_message": "📈 市场分析师正在分析技术指标和市场趋势...",
        "current_step_name": "市场分析师",
        "current_step_description": "📈 市场分析师正在分析技术指标和市场趋势...",
    })
    
    # 获取字典
    data = tracker.to_dict()
    
    print("\n✅ RedisProgressTracker 字段验证:")
    print(f"  current_step_name: {data.get('current_step_name')}")
    print(f"  current_step_description: {data.get('current_step_description')}")
    print(f"  last_message: {data.get('last_message')}")
    
    # 验证字段
    assert "current_step_name" in data, "应该包含 current_step_name 字段"
    assert "current_step_description" in data, "应该包含 current_step_description 字段"
    assert data["current_step_name"] == "市场分析师", "步骤名称应该是简短名称"
    assert data["current_step_description"] == "📈 市场分析师正在分析技术指标和市场趋势...", "描述应该是详细描述"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

