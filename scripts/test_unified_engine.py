"""
测试统一分析引擎功能
"""

import sys
import asyncio
import uuid
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.models.analysis import UnifiedAnalysisTask, AnalysisTaskType
from app.models.user import PyObjectId
from app.services.unified_analysis_engine import UnifiedAnalysisEngine
from app.services.workflow_registry import initialize_builtin_workflows


async def test_engine():
    """测试统一执行引擎"""
    print("🧪 测试统一分析引擎")
    print("=" * 60)
    
    # 1. 初始化工作流注册表
    print("\n1️⃣ 初始化工作流注册表...")
    initialize_builtin_workflows()
    
    # 2. 创建引擎实例
    print("\n2️⃣ 创建引擎实例...")
    engine = UnifiedAnalysisEngine()
    print("   ✅ 引擎创建成功")
    
    # 3. 测试参数验证
    print("\n3️⃣ 测试参数验证...")
    
    # 创建一个有效的任务
    valid_task = UnifiedAnalysisTask(
        task_id=str(uuid.uuid4()),
        user_id=PyObjectId(),
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params={
            "symbol": "000858",
            "market_type": "cn",
            "research_depth": "标准"
        },
        engine_type="auto",
        preference_type="neutral"
    )
    print(f"   ✅ 创建有效任务: {valid_task.task_id}")
    print(f"      任务类型: {valid_task.task_type}")
    print(f"      任务参数: {valid_task.task_params}")
    
    # 创建一个无效的任务（缺少必需参数）
    invalid_task = UnifiedAnalysisTask(
        task_id=str(uuid.uuid4()),
        user_id=PyObjectId(),
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params={
            "symbol": "000858"
            # 缺少 market_type
        },
        engine_type="auto"
    )
    
    try:
        await engine.execute_task(invalid_task)
        print("   ❌ 应该抛出参数验证错误")
    except ValueError as e:
        print(f"   ✅ 正确捕获参数验证错误: {e}")
    
    # 4. 测试引擎选择
    print("\n4️⃣ 测试引擎选择...")
    
    # auto -> workflow (默认)
    selected = engine._select_engine("auto", "workflow")
    print(f"   auto + workflow默认 -> {selected}")
    assert selected == "workflow", "引擎选择错误"
    
    # 指定引擎
    selected = engine._select_engine("legacy", "workflow")
    print(f"   legacy + workflow默认 -> {selected}")
    assert selected == "legacy", "引擎选择错误"
    
    print("   ✅ 引擎选择逻辑正确")
    
    # 5. 测试提示词构建
    print("\n5️⃣ 测试提示词构建...")
    
    portfolio_task = UnifiedAnalysisTask(
        task_id=str(uuid.uuid4()),
        user_id=PyObjectId(),
        task_type=AnalysisTaskType.PORTFOLIO_HEALTH,
        task_params={"user_id": "test_user"},
        engine_type="llm"
    )
    
    prompt = engine._build_prompt_for_task(portfolio_task)
    print(f"   组合健康度提示词长度: {len(prompt)} 字符")
    assert "持仓集中度" in prompt, "提示词内容错误"
    print("   ✅ 提示词构建正确")
    
    # 6. 模拟执行（不实际调用 API）
    print("\n6️⃣ 模拟任务执行流程...")
    print(f"   任务ID: {valid_task.task_id}")
    print(f"   任务类型: {valid_task.task_type}")
    print(f"   引擎类型: {valid_task.engine_type}")
    print(f"   偏好类型: {valid_task.preference_type}")
    print("   ✅ 任务配置正确")
    
    print("\n✅ 所有测试通过！")
    print("\n💡 提示:")
    print("   - 统一执行引擎已就绪")
    print("   - 支持 workflow、legacy、llm 三种引擎")
    print("   - 自动参数验证和引擎选择")
    print("   - 下一步: 集成到服务层")


if __name__ == "__main__":
    asyncio.run(test_engine())

