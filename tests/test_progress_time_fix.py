"""
测试进度跟踪器的时间计算修复

验证：
1. elapsed_time、remaining_time、estimated_total_time 的数学一致性
2. v2 版本的节点名称映射
"""

import time
import pytest
from app.services.progress.tracker import RedisProgressTracker
from core.workflow.engine import WorkflowEngine


def test_time_calculation_consistency():
    """测试时间计算的一致性"""
    # 创建进度跟踪器
    tracker = RedisProgressTracker(
        task_id="test_task_001",
        analysts=["market_analyst_v2", "fundamentals_analyst_v2", "news_analyst_v2"],
        research_depth="深度",
        llm_provider="dashscope"
    )
    
    # 等待1秒
    time.sleep(1)
    
    # 更新进度到50%
    tracker.update_progress({
        'progress_percentage': 50,
        'last_message': '分析进行中...'
    })
    
    # 获取进度数据
    progress_data = tracker.to_dict()
    
    # 验证时间字段存在
    assert 'elapsed_time' in progress_data
    assert 'remaining_time' in progress_data
    assert 'estimated_total_time' in progress_data
    
    elapsed = progress_data['elapsed_time']
    remaining = progress_data['remaining_time']
    estimated_total = progress_data['estimated_total_time']
    
    # 验证数学一致性：elapsed + remaining ≈ estimated_total
    # 允许1秒的误差（因为计算时间有微小延迟）
    sum_time = elapsed + remaining
    diff = abs(sum_time - estimated_total)
    
    print(f"\n时间计算验证:")
    print(f"  已用时间: {elapsed:.2f}秒")
    print(f"  预计剩余: {remaining:.2f}秒")
    print(f"  预计总时长: {estimated_total:.2f}秒")
    print(f"  总和: {sum_time:.2f}秒")
    print(f"  差值: {diff:.2f}秒")
    
    assert diff < 1.0, f"时间计算不一致: {elapsed} + {remaining} = {sum_time} ≠ {estimated_total}"
    
    # 验证已用时间大于0（因为我们等待了1秒）
    assert elapsed >= 1.0, f"已用时间应该至少1秒，实际: {elapsed}"
    
    # 验证预计总时长符合预期（3个分析师 + 深度分析 = 330 * 2.0 = 660秒）
    expected_total = 660
    assert abs(estimated_total - expected_total) < 10, f"预计总时长应该约为{expected_total}秒，实际: {estimated_total}"


def test_v2_node_name_mapping():
    """测试 v2 版本的节点名称映射"""
    engine = WorkflowEngine()

    # 测试 v2 分析师节点
    v2_nodes = [
        ("market_analyst_v2", "市场分析师"),
        ("fundamentals_analyst_v2", "基本面分析师"),
        ("news_analyst_v2", "新闻分析师"),
        ("social_analyst_v2", "社媒分析师"),
        ("sector_analyst_v2", "板块分析师"),
        ("index_analyst_v2", "大盘分析师"),
    ]

    print("\nv2 节点名称映射验证:")
    for node_id, expected_keyword in v2_nodes:
        progress, message, step_name = engine._get_node_progress_info(node_id)
        
        print(f"  {node_id}:")
        print(f"    进度: {progress}%")
        print(f"    消息: {message}")
        print(f"    步骤名: {step_name}")
        
        # 验证返回值不为 None
        assert progress is not None, f"节点 {node_id} 应该有进度映射"
        assert message is not None, f"节点 {node_id} 应该有消息映射"
        assert step_name is not None, f"节点 {node_id} 应该有步骤名映射"
        
        # 验证消息包含预期的关键词
        assert expected_keyword in message, f"节点 {node_id} 的消息应该包含 '{expected_keyword}'"
        
        # 验证步骤名与节点ID一致
        assert step_name == node_id, f"节点 {node_id} 的步骤名应该是 {node_id}，实际: {step_name}"


def test_progress_update_time_recalculation():
    """测试每次更新进度时都会重新计算时间"""
    tracker = RedisProgressTracker(
        task_id="test_task_002",
        analysts=["market_analyst_v2"],
        research_depth="快速",
        llm_provider="dashscope"
    )
    
    # 第一次获取时间
    time.sleep(0.5)
    tracker.update_progress({'progress_percentage': 25})
    data1 = tracker.to_dict()
    elapsed1 = data1['elapsed_time']
    
    # 第二次获取时间（等待1秒后）
    time.sleep(1)
    tracker.update_progress({'progress_percentage': 50})
    data2 = tracker.to_dict()
    elapsed2 = data2['elapsed_time']
    
    print(f"\n时间重新计算验证:")
    print(f"  第一次已用时间: {elapsed1:.2f}秒")
    print(f"  第二次已用时间: {elapsed2:.2f}秒")
    print(f"  时间差: {elapsed2 - elapsed1:.2f}秒")
    
    # 验证第二次的已用时间大于第一次（至少增加了1秒）
    assert elapsed2 > elapsed1, "第二次的已用时间应该大于第一次"
    assert (elapsed2 - elapsed1) >= 0.9, f"时间差应该至少0.9秒，实际: {elapsed2 - elapsed1}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

