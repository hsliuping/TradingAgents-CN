#!/usr/bin/env python
"""
AB 测试脚本

验证单股分析 API 支持 legacy 和 unified 两种引擎切换
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_engine_enum():
    """测试引擎枚举"""
    print("\n" + "=" * 60)
    print("测试 AnalysisEngine 枚举")
    print("=" * 60)

    from app.models.analysis import AnalysisEngine

    print(f"   ✅ LEGACY = {AnalysisEngine.LEGACY.value}")
    print(f"   ✅ UNIFIED = {AnalysisEngine.UNIFIED.value}")

    # 测试枚举值比较
    assert AnalysisEngine.LEGACY.value == "legacy"
    assert AnalysisEngine.UNIFIED.value == "unified"

    print("\n✅ AnalysisEngine 枚举测试通过")


def test_analysis_parameters():
    """测试 AnalysisParameters 模型"""
    print("\n" + "=" * 60)
    print("测试 AnalysisParameters 模型")
    print("=" * 60)

    from app.models.analysis import AnalysisParameters, AnalysisEngine

    # 测试默认值
    params = AnalysisParameters()
    print(f"   📋 默认引擎: {params.engine}")
    assert params.engine == AnalysisEngine.LEGACY, "默认引擎应为 LEGACY"

    # 测试指定引擎
    params_unified = AnalysisParameters(engine=AnalysisEngine.UNIFIED)
    print(f"   📋 指定引擎: {params_unified.engine}")
    assert params_unified.engine == AnalysisEngine.UNIFIED

    # 测试 workflow_id
    params_with_workflow = AnalysisParameters(
        engine=AnalysisEngine.UNIFIED,
        workflow_id="test-workflow-123"
    )
    print(f"   📋 工作流 ID: {params_with_workflow.workflow_id}")
    assert params_with_workflow.workflow_id == "test-workflow-123"

    print("\n✅ AnalysisParameters 模型测试通过")


def test_single_analysis_request():
    """测试单股分析请求"""
    print("\n" + "=" * 60)
    print("测试 SingleAnalysisRequest 模型")
    print("=" * 60)

    from app.models.analysis import SingleAnalysisRequest, AnalysisParameters, AnalysisEngine

    # 测试带引擎参数的请求
    request = SingleAnalysisRequest(
        symbol="000858",
        parameters=AnalysisParameters(
            engine=AnalysisEngine.UNIFIED,
            workflow_id="my-custom-workflow",
            market_type="A股"
        )
    )

    print(f"   📊 股票代码: {request.get_symbol()}")
    print(f"   🔧 引擎类型: {request.parameters.engine.value}")
    print(f"   📋 工作流 ID: {request.parameters.workflow_id}")

    assert request.parameters.engine == AnalysisEngine.UNIFIED
    assert request.parameters.workflow_id == "my-custom-workflow"

    print("\n✅ SingleAnalysisRequest 模型测试通过")


def test_router_imports():
    """测试路由导入"""
    print("\n" + "=" * 60)
    print("测试路由导入")
    print("=" * 60)

    from app.routers.analysis import router, submit_single_analysis, submit_batch_analysis
    from app.services.unified_analysis_service import get_unified_analysis_service

    print(f"   ✅ router: {router}")
    print(f"   ✅ submit_single_analysis: {submit_single_analysis}")
    print(f"   ✅ submit_batch_analysis: {submit_batch_analysis}")
    print(f"   ✅ get_unified_analysis_service: {get_unified_analysis_service}")

    # 验证统一服务可以实例化
    service = get_unified_analysis_service()
    print(f"   ✅ UnifiedAnalysisService 实例: {type(service).__name__}")

    # 验证有 execute_analysis_for_ab_test 方法
    assert hasattr(service, "execute_analysis_for_ab_test"), "缺少 execute_analysis_for_ab_test 方法"
    print(f"   ✅ execute_analysis_for_ab_test 方法存在")

    print("\n✅ 路由导入测试通过")


def main():
    print("=" * 60)
    print("AB 测试功能验证")
    print("=" * 60)

    try:
        test_engine_enum()
        test_analysis_parameters()
        test_single_analysis_request()
        test_router_imports()

        print("\n" + "=" * 60)
        print("🎉 所有 AB 测试功能验证通过！")
        print("=" * 60)
        print("\n📋 AB 测试用法:")
        print("   - engine='legacy': 使用旧引擎 (TradingAgentsGraph)")
        print("   - engine='unified': 使用新引擎 (WorkflowEngine)")
        print("\n📝 API 调用示例:")
        print('   POST /api/analysis/single')
        print('   {')
        print('     "symbol": "000858",')
        print('     "parameters": {')
        print('       "engine": "unified",')
        print('       "workflow_id": "optional-custom-workflow-id"')
        print('     }')
        print('   }')

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

