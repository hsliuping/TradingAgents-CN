"""
测试工作流注册表功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.workflow_registry import initialize_builtin_workflows, AnalysisWorkflowRegistry
from app.models.analysis import AnalysisTaskType


def test_registry():
    """测试注册表功能"""
    print("🧪 测试工作流注册表")
    print("=" * 60)
    
    # 1. 初始化内置工作流
    print("\n1️⃣ 初始化内置工作流...")
    initialize_builtin_workflows()
    
    # 2. 列出所有工作流
    print("\n2️⃣ 列出所有工作流:")
    all_workflows = AnalysisWorkflowRegistry.list_all()
    print(f"   共 {len(all_workflows)} 个工作流")
    for config in all_workflows:
        print(f"   - {config.task_type.value}: {config.name}")
        print(f"     工作流ID: {config.workflow_id}")
        print(f"     默认引擎: {config.default_engine}")
        print(f"     必需参数: {config.required_params}")
        print(f"     超时时间: {config.timeout}秒")
        print()
    
    # 3. 获取特定工作流配置
    print("\n3️⃣ 获取股票分析工作流配置:")
    stock_config = AnalysisWorkflowRegistry.get_config(AnalysisTaskType.STOCK_ANALYSIS)
    if stock_config:
        print(f"   ✅ 找到配置: {stock_config.name}")
        print(f"   描述: {stock_config.description}")
        print(f"   必需参数: {stock_config.required_params}")
        print(f"   可选参数: {stock_config.optional_params}")
    else:
        print("   ❌ 未找到配置")
    
    # 4. 验证参数
    print("\n4️⃣ 验证任务参数:")
    
    # 有效参数
    valid_params = {
        "symbol": "000858",
        "market_type": "cn",
        "research_depth": "标准"
    }
    is_valid, error = AnalysisWorkflowRegistry.validate_params(
        AnalysisTaskType.STOCK_ANALYSIS,
        valid_params
    )
    print(f"   有效参数: {is_valid} - {error or '无错误'}")
    
    # 无效参数（缺少必需参数）
    invalid_params = {
        "symbol": "000858"
        # 缺少 market_type
    }
    is_valid, error = AnalysisWorkflowRegistry.validate_params(
        AnalysisTaskType.STOCK_ANALYSIS,
        invalid_params
    )
    print(f"   无效参数: {is_valid} - {error or '无错误'}")
    
    # 5. 获取默认参数
    print("\n5️⃣ 获取默认参数:")
    default_params = AnalysisWorkflowRegistry.get_default_params(AnalysisTaskType.STOCK_ANALYSIS)
    print(f"   默认参数: {default_params}")
    
    # 6. 按标签筛选
    print("\n6️⃣ 按标签筛选工作流:")
    debate_workflows = AnalysisWorkflowRegistry.list_by_tag("辩论机制")
    print(f"   包含'辩论机制'标签的工作流: {len(debate_workflows)} 个")
    for config in debate_workflows:
        print(f"   - {config.name}")
    
    print("\n✅ 测试完成！")


if __name__ == "__main__":
    test_registry()

