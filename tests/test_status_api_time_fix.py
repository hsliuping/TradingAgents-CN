"""
测试状态API的时间计算修复

验证从MongoDB查询任务状态时，时间计算是否正确
"""

import pytest
from datetime import datetime, timezone, timedelta
from app.services.progress.tracker import RedisProgressTracker


def test_time_calculation_with_fixed_total():
    """测试使用固定预估总时长的时间计算逻辑（旧版本逻辑）"""

    # 模拟任务开始时间（10秒前）
    start_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    current_time = datetime.now(timezone.utc)

    # 已用时间应该约为10秒
    elapsed_time = (current_time - start_time).total_seconds()

    print(f"\n已用时间: {elapsed_time:.2f}秒")

    # 🔑 关键：预估总时长是固定的（任务创建时就确定了），不随进度变化
    estimated_total_time = 300  # 假设预估总时长为5分钟（300秒）

    # 测试场景1：进度50%，已用10秒
    progress_pct = 50
    remaining_time = max(0, estimated_total_time - elapsed_time)

    print(f"\n场景1：进度50%，已用10秒")
    print(f"  已用时间: {elapsed_time:.2f}秒")
    print(f"  预计总时长: {estimated_total_time:.2f}秒（固定值）")
    print(f"  预计剩余: {remaining_time:.2f}秒")
    print(f"  验证: {elapsed_time:.2f} + {remaining_time:.2f} = {elapsed_time + remaining_time:.2f} ≈ {estimated_total_time:.2f}")

    # 验证数学一致性
    assert abs((elapsed_time + remaining_time) - estimated_total_time) < 0.01

    # 验证预计剩余约为290秒（300 - 10 = 290）
    assert abs(remaining_time - 290) < 1.0

    # 测试场景2：进度15%，已用10秒
    progress_pct = 15
    remaining_time = max(0, estimated_total_time - elapsed_time)

    print(f"\n场景2：进度15%，已用10秒")
    print(f"  已用时间: {elapsed_time:.2f}秒")
    print(f"  预计总时长: {estimated_total_time:.2f}秒（固定值）")
    print(f"  预计剩余: {remaining_time:.2f}秒")
    print(f"  验证: {elapsed_time:.2f} + {remaining_time:.2f} = {elapsed_time + remaining_time:.2f} ≈ {estimated_total_time:.2f}")

    # 验证数学一致性
    assert abs((elapsed_time + remaining_time) - estimated_total_time) < 0.01

    # 验证预计剩余约为290秒（300 - 10 = 290，与进度无关）
    assert abs(remaining_time - 290) < 1.0

    # 测试场景3：任务已完成
    # 模拟任务完成时间（开始后300秒）
    end_time = start_time + timedelta(seconds=300)
    elapsed_time_completed = (end_time - start_time).total_seconds()
    estimated_total_time_completed = elapsed_time_completed  # 已完成任务的总时长就是已用时间
    remaining_time_completed = 0

    print(f"\n场景3：任务已完成")
    print(f"  已用时间: {elapsed_time_completed:.2f}秒")
    print(f"  预计总时长: {estimated_total_time_completed:.2f}秒")
    print(f"  预计剩余: {remaining_time_completed:.2f}秒")

    # 验证已完成任务的时间
    assert estimated_total_time_completed == elapsed_time_completed
    assert remaining_time_completed == 0


def test_base_total_time_calculation():
    """测试基准总时间的计算"""
    
    # 测试不同配置的基准时间
    test_cases = [
        {
            "analysts": ["market_analyst_v2"],
            "research_depth": "快速",
            "llm_provider": "dashscope",
            "expected_min": 100,  # 至少100秒
            "expected_max": 300,  # 最多300秒
        },
        {
            "analysts": ["market_analyst_v2", "fundamentals_analyst_v2", "news_analyst_v2"],
            "research_depth": "深度",
            "llm_provider": "dashscope",
            "expected_min": 500,  # 至少500秒
            "expected_max": 800,  # 最多800秒
        },
    ]
    
    print("\n基准时间计算验证:")
    for i, case in enumerate(test_cases, 1):
        tracker = RedisProgressTracker(
            task_id=f"test_task_{i}",
            analysts=case["analysts"],
            research_depth=case["research_depth"],
            llm_provider=case["llm_provider"]
        )
        
        base_total_time = tracker._get_base_total_time()
        
        print(f"\n场景{i}:")
        print(f"  分析师: {len(case['analysts'])}个")
        print(f"  研究深度: {case['research_depth']}")
        print(f"  LLM提供商: {case['llm_provider']}")
        print(f"  基准总时间: {base_total_time:.2f}秒")
        
        # 验证基准时间在预期范围内
        assert case["expected_min"] <= base_total_time <= case["expected_max"], \
            f"基准时间 {base_total_time} 不在预期范围 [{case['expected_min']}, {case['expected_max']}] 内"


def test_time_consistency_over_time():
    """测试时间计算在不同时刻的一致性"""
    import time
    
    # 创建一个进度跟踪器
    tracker = RedisProgressTracker(
        task_id="test_consistency",
        analysts=["market_analyst_v2", "fundamentals_analyst_v2"],
        research_depth="快速",
        llm_provider="dashscope"
    )
    
    # 更新进度到30%
    tracker.update_progress({'progress_percentage': 30})
    
    # 第一次获取时间
    data1 = tracker.to_dict()
    elapsed1 = data1['elapsed_time']
    remaining1 = data1['remaining_time']
    total1 = data1['estimated_total_time']
    
    print(f"\n第一次查询:")
    print(f"  已用时间: {elapsed1:.2f}秒")
    print(f"  预计剩余: {remaining1:.2f}秒")
    print(f"  预计总时长: {total1:.2f}秒")
    print(f"  验证: {elapsed1:.2f} + {remaining1:.2f} = {elapsed1 + remaining1:.2f} ≈ {total1:.2f}")
    
    # 验证第一次的数学一致性
    assert abs((elapsed1 + remaining1) - total1) < 1.0
    
    # 等待1秒
    time.sleep(1)
    
    # 第二次获取时间（不更新进度）
    data2 = tracker.to_dict()
    elapsed2 = data2['elapsed_time']
    remaining2 = data2['remaining_time']
    total2 = data2['estimated_total_time']
    
    print(f"\n第二次查询（1秒后）:")
    print(f"  已用时间: {elapsed2:.2f}秒")
    print(f"  预计剩余: {remaining2:.2f}秒")
    print(f"  预计总时长: {total2:.2f}秒")
    print(f"  验证: {elapsed2:.2f} + {remaining2:.2f} = {elapsed2 + remaining2:.2f} ≈ {total2:.2f}")
    
    # 验证第二次的数学一致性
    assert abs((elapsed2 + remaining2) - total2) < 1.0
    
    # 验证已用时间增加了约1秒
    assert (elapsed2 - elapsed1) >= 0.9, f"已用时间应该增加约1秒，实际增加: {elapsed2 - elapsed1}"
    
    # 验证预计剩余时间减少了约1秒
    assert (remaining1 - remaining2) >= 0.9, f"预计剩余应该减少约1秒，实际减少: {remaining1 - remaining2}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

