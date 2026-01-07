"""
测试任务取消功能

验证任务在执行过程中可以被取消
"""

import asyncio
from app.core.database import init_database, get_mongo_db
from app.services.task_analysis_service import get_task_analysis_service
from app.models.analysis import AnalysisTaskType
from app.models.user import PyObjectId


async def test_task_cancellation():
    """测试任务取消"""
    print("=" * 60)
    print("🧪 测试任务取消功能")
    print("=" * 60)
    
    # 初始化数据库
    await init_database()
    
    # 获取服务
    task_service = get_task_analysis_service()
    
    # 创建测试任务
    print("\n1️⃣ 创建测试任务...")
    task = await task_service.create_task(
        user_id=PyObjectId("507f1f77bcf86cd799439011"),  # 测试用户ID
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params={
            "symbol": "000001",
            "market_type": "cn",
            "research_depth": "标准"
        },
        engine_type="workflow",
        preference_type="neutral"
    )
    
    print(f"✅ 任务已创建: {task.task_id}")
    print(f"   状态: {task.status}")
    
    # 异步执行任务（不等待完成）
    print("\n2️⃣ 开始执行任务...")
    task_future = asyncio.create_task(task_service.execute_task(task))
    
    # 等待3秒后取消任务
    print("\n3️⃣ 等待3秒后取消任务...")
    await asyncio.sleep(3)
    
    print("\n4️⃣ 取消任务...")
    success = await task_service.cancel_task(task.task_id)
    
    if success:
        print(f"✅ 任务取消请求已发送")
    else:
        print(f"❌ 任务取消失败（可能已完成）")
    
    # 等待任务执行完成（应该会抛出 TaskCancelledException）
    print("\n5️⃣ 等待任务执行完成...")
    try:
        result_task = await task_future
        print(f"📊 任务最终状态: {result_task.status}")
        print(f"   错误信息: {result_task.error_message}")
    except Exception as e:
        print(f"⚠️ 任务执行异常: {e}")
    
    # 查询任务状态
    print("\n6️⃣ 查询任务最终状态...")
    final_task = await task_service.get_task(task.task_id)
    if final_task:
        print(f"📊 最终状态: {final_task.status}")
        print(f"   进度: {final_task.progress}%")
        print(f"   错误信息: {final_task.error_message}")
        print(f"   执行时间: {final_task.execution_time:.2f}s")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_task_cancellation())

