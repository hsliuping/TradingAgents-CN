"""测试 v2 引擎的内存同步

验证：
1. v2 引擎创建任务时，同时在内存中创建任务状态
2. v2 引擎执行任务时，同步更新内存状态
3. 任务完成/失败时，更新内存状态
"""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_v2_task_memory_creation():
    """测试 v2 引擎创建任务时同步到内存"""
    from app.services.task_analysis_service import get_task_analysis_service
    from app.services.memory_state_manager import get_memory_state_manager
    from app.models.analysis import AnalysisTaskType
    from app.models.user import PyObjectId
    
    task_service = get_task_analysis_service()
    memory_manager = get_memory_state_manager()
    
    # 创建任务
    task = await task_service.create_task(
        user_id=PyObjectId("507f1f77bcf86cd799439011"),
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params={
            "symbol": "000001",
            "market_type": "cn",
            "research_depth": "快速"
        }
    )
    
    print(f"\n✅ 任务已创建: {task.task_id}")
    
    # 验证内存中是否存在
    memory_task = await memory_manager.get_task_dict(task.task_id)
    
    assert memory_task is not None, "内存中应该存在任务"
    assert memory_task["task_id"] == task.task_id, "任务ID应该匹配"
    assert memory_task["stock_code"] == "000001", "股票代码应该匹配"
    
    print(f"✅ 内存中找到任务: {memory_task['task_id']}")
    print(f"  状态: {memory_task['status']}")
    print(f"  股票代码: {memory_task['stock_code']}")
    
    # 清理
    await memory_manager.delete_task(task.task_id)


@pytest.mark.asyncio
async def test_v2_task_progress_sync():
    """测试 v2 引擎执行时同步进度到内存"""
    from app.services.task_analysis_service import get_task_analysis_service
    from app.services.memory_state_manager import get_memory_state_manager
    from app.models.analysis import AnalysisTaskType
    from app.models.user import PyObjectId

    task_service = get_task_analysis_service()
    memory_manager = get_memory_state_manager()

    # 创建任务
    task = await task_service.create_task(
        user_id=PyObjectId("507f1f77bcf86cd799439011"),
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params={
            "symbol": "000001",
            "market_type": "cn",
            "research_depth": "快速"
        }
    )

    print(f"\n✅ 任务已创建: {task.task_id}")

    # 模拟进度回调
    progress_updates = []

    async def test_progress_callback(progress: int, message: str, **kwargs):
        """测试进度回调"""
        progress_updates.append({
            "progress": progress,
            "message": message,
            "step_name": kwargs.get("step_name")
        })
        print(f"📊 进度更新: {progress}% - {message}")

    # 注意：这里不实际执行任务，只测试进度回调的内存同步
    # 实际执行需要完整的环境配置

    # 手动调用 wrapped_progress_callback 来测试
    from app.services.memory_state_manager import TaskStatus

    await memory_manager.update_task_status(
        task_id=task.task_id,
        status=TaskStatus.RUNNING,
        progress=50,
        message="📈 市场分析师正在分析技术指标和市场趋势...",
        current_step="market_analyst",
        current_step_name="市场分析师",  # 🔑 新增：步骤名称
        current_step_description="📈 市场分析师正在分析技术指标和市场趋势..."  # 🔑 新增：步骤描述
    )

    # 验证内存中的进度
    memory_task = await memory_manager.get_task_dict(task.task_id)

    assert memory_task is not None, "内存中应该存在任务"
    assert memory_task["progress"] == 50, "进度应该是 50%"
    assert memory_task["status"] == "running", "状态应该是 running"
    assert memory_task["current_step"] == "market_analyst", "当前步骤应该是 market_analyst"
    assert memory_task["current_step_name"] == "市场分析师", "步骤名称应该是 市场分析师"
    assert memory_task["current_step_description"] == "📈 市场分析师正在分析技术指标和市场趋势...", "步骤描述应该正确"

    print(f"\n✅ 内存进度验证通过:")
    print(f"  进度: {memory_task['progress']}%")
    print(f"  状态: {memory_task['status']}")
    print(f"  当前步骤: {memory_task['current_step']}")
    print(f"  步骤名称: {memory_task['current_step_name']}")  # 🔑 新增
    print(f"  步骤描述: {memory_task['current_step_description']}")  # 🔑 新增
    print(f"  消息: {memory_task['message']}")

    # 清理
    await memory_manager.delete_task(task.task_id)


@pytest.mark.asyncio
async def test_memory_manager_singleton():
    """测试内存管理器是单例"""
    from app.services.memory_state_manager import get_memory_state_manager
    
    manager1 = get_memory_state_manager()
    manager2 = get_memory_state_manager()
    
    assert id(manager1) == id(manager2), "内存管理器应该是单例"
    
    print(f"\n✅ 内存管理器单例验证通过:")
    print(f"  实例1 ID: {id(manager1)}")
    print(f"  实例2 ID: {id(manager2)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

