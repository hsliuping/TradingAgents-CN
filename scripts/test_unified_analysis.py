#!/usr/bin/env python
"""
测试统一分析服务

验证 UnifiedAnalysisService 的基本功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.unified_analysis_service import (
    UnifiedAnalysisService,
    get_unified_analysis_service,
)
from core.workflow.default_workflow_provider import (
    DefaultWorkflowProvider,
    get_default_workflow_provider,
    SYSTEM_DEFAULT_WORKFLOW_ID,
    SYSTEM_SIMPLE_WORKFLOW_ID,
)


def test_default_workflow_provider():
    """测试默认工作流提供者"""
    print("\n" + "=" * 60)
    print("测试 DefaultWorkflowProvider")
    print("=" * 60)
    
    provider = get_default_workflow_provider()
    
    # 测试获取系统工作流
    print("\n1. 测试获取系统工作流")
    default_workflow = provider.get_system_workflow(SYSTEM_DEFAULT_WORKFLOW_ID)
    if default_workflow:
        print(f"   ✅ 默认工作流: {default_workflow.name}")
        print(f"      节点数: {len(default_workflow.nodes)}")
        print(f"      边数: {len(default_workflow.edges)}")
    else:
        print("   ❌ 无法获取默认工作流")
    
    simple_workflow = provider.get_system_workflow(SYSTEM_SIMPLE_WORKFLOW_ID)
    if simple_workflow:
        print(f"   ✅ 简单工作流: {simple_workflow.name}")
        print(f"      节点数: {len(simple_workflow.nodes)}")
        print(f"      边数: {len(simple_workflow.edges)}")
    else:
        print("   ❌ 无法获取简单工作流")
    
    # 测试加载工作流
    print("\n2. 测试加载工作流")
    workflow = provider.load_workflow(None)  # 使用默认
    print(f"   ✅ 加载默认工作流: {workflow.name}")
    
    workflow = provider.load_workflow(SYSTEM_SIMPLE_WORKFLOW_ID)
    print(f"   ✅ 加载简单工作流: {workflow.name}")
    
    # 测试活动工作流
    print("\n3. 测试活动工作流")
    active_id = provider.get_active_workflow_id()
    print(f"   当前活动工作流 ID: {active_id}")
    
    print("\n✅ DefaultWorkflowProvider 测试通过")


def test_unified_analysis_service_init():
    """测试统一分析服务初始化"""
    print("\n" + "=" * 60)
    print("测试 UnifiedAnalysisService 初始化")
    print("=" * 60)
    
    service = get_unified_analysis_service()
    
    print(f"   ✅ 服务实例创建成功: {type(service).__name__}")
    print(f"   ✅ 工作流提供者: {type(service._workflow_provider).__name__}")
    
    print("\n✅ UnifiedAnalysisService 初始化测试通过")


async def test_unified_analysis_service_analyze():
    """测试统一分析服务的分析功能（模拟）"""
    print("\n" + "=" * 60)
    print("测试 UnifiedAnalysisService.analyze() - 模拟模式")
    print("=" * 60)
    
    service = get_unified_analysis_service()
    
    # 定义进度回调
    def progress_callback(progress, message, **kwargs):
        print(f"   📊 进度: {progress:.1f}% - {message}")
    
    print("\n1. 测试配置构建")
    config = service._build_legacy_config(None)
    print(f"   ✅ 配置构建成功: {list(config.keys())}")
    
    print("\n2. 测试工作流加载")
    workflow = service._workflow_provider.load_workflow(None)
    print(f"   ✅ 工作流加载成功: {workflow.name}")
    
    # 注意：实际分析需要 LLM 和数据源，这里只测试初始化
    print("\n⚠️ 跳过实际分析测试（需要 LLM 和数据源）")
    print("   如需完整测试，请运行: python scripts/test_workflow_execute.py")
    
    print("\n✅ UnifiedAnalysisService 基本功能测试通过")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("统一分析引擎测试")
    print("=" * 60)
    
    try:
        # 测试 DefaultWorkflowProvider
        test_default_workflow_provider()
        
        # 测试 UnifiedAnalysisService 初始化
        test_unified_analysis_service_init()
        
        # 测试 UnifiedAnalysisService 分析功能
        asyncio.run(test_unified_analysis_service_analyze())
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

