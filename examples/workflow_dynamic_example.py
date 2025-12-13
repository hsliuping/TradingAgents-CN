"""
工作流动态功能示例

演示如何使用 WorkflowBuilder 和 WorkflowEngine 的动态功能：
1. 动态工具绑定
2. 动态状态生成
3. 工作流配置优化
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.workflow.models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position
)
from core.workflow.builder import WorkflowBuilder
from core.workflow.engine import WorkflowEngine
from core.config.binding_manager import BindingManager


def example_1_dynamic_tool_binding():
    """示例 1: 动态工具绑定"""
    print("\n" + "=" * 70)
    print("示例 1: 动态工具绑定")
    print("=" * 70)
    
    print("\n📝 说明：")
    print("   WorkflowBuilder 会自动从 BindingManager 获取 Agent 的工具列表")
    print("   无需在代码中硬编码工具映射")
    
    # 创建工作流
    workflow = WorkflowDefinition(
        id="dynamic_tools_workflow",
        name="动态工具绑定示例",
        description="演示动态工具绑定",
        nodes=[
            NodeDefinition(
                id="__start__",
                type=NodeType.START,
                label="开始",
                position=Position(x=100, y=100)
            ),
            NodeDefinition(
                id="analyst",
                type=NodeType.ANALYST,
                agent_id="market_analyst_v2",
                label="市场分析师",
                position=Position(x=300, y=100)
            ),
            NodeDefinition(
                id="__end__",
                type=NodeType.END,
                label="结束",
                position=Position(x=500, y=100)
            )
        ],
        edges=[
            EdgeDefinition(id="e1", source="__start__", target="analyst", type=EdgeType.NORMAL),
            EdgeDefinition(id="e2", source="analyst", target="__end__", type=EdgeType.NORMAL)
        ]
    )
    
    # 创建 WorkflowBuilder
    builder = WorkflowBuilder()
    
    print(f"\n✅ WorkflowBuilder 已创建")
    print(f"   BindingManager: 已初始化")
    
    # 构建工作流
    graph = builder.build(workflow)
    
    print(f"\n✅ 工作流已构建")
    print(f"   工作流 ID: {workflow.id}")
    print(f"   Agent 工具将从 BindingManager 动态加载")


def example_2_dynamic_state():
    """示例 2: 动态状态生成"""
    print("\n" + "=" * 70)
    print("示例 2: 动态状态生成")
    print("=" * 70)
    
    print("\n📝 说明：")
    print("   WorkflowEngine 可以根据 Agent IO 定义自动生成状态类")
    print("   状态字段包括所有 Agent 的输入和输出")
    
    # 创建工作流
    workflow = WorkflowDefinition(
        id="dynamic_state_workflow",
        name="动态状态生成示例",
        description="演示动态状态生成",
        nodes=[
            NodeDefinition(
                id="__start__",
                type=NodeType.START,
                label="开始",
                position=Position(x=100, y=100)
            ),
            NodeDefinition(
                id="analyst",
                type=NodeType.ANALYST,
                agent_id="market_analyst_v2",
                label="市场分析师",
                position=Position(x=300, y=100)
            ),
            NodeDefinition(
                id="__end__",
                type=NodeType.END,
                label="结束",
                position=Position(x=500, y=100)
            )
        ],
        edges=[
            EdgeDefinition(id="e1", source="__start__", target="analyst", type=EdgeType.NORMAL),
            EdgeDefinition(id="e2", source="analyst", target="__end__", type=EdgeType.NORMAL)
        ]
    )
    
    # 创建 WorkflowEngine（启用动态状态）
    engine = WorkflowEngine(use_dynamic_state=True)
    engine.load(workflow)
    
    print(f"\n✅ WorkflowEngine 已创建（动态状态模式）")
    
    # 编译工作流
    engine.compile()
    
    print(f"\n✅ 工作流已编译")
    print(f"   状态类已自动生成")
    print(f"   状态字段来自 Agent IO 定义")


def example_3_configuration_priority():
    """示例 3: 配置优先级"""
    print("\n" + "=" * 70)
    print("示例 3: 配置优先级")
    print("=" * 70)
    
    print("\n📝 说明：")
    print("   配置优先级：数据库配置 > 代码配置")
    print("   可以在数据库中覆盖代码中的工具绑定")
    
    binding_manager = BindingManager()
    
    # 示例：获取工具绑定
    agent_id = "market_analyst_v2"
    workflow_id = "test_workflow"
    
    print(f"\n🔍 查询工具绑定:")
    print(f"   Agent: {agent_id}")
    print(f"   Workflow: {workflow_id}")
    
    # 从 BindingManager 获取工具
    tools = binding_manager.get_tools_for_workflow_agent(workflow_id, agent_id)
    
    if tools:
        print(f"\n✅ 找到数据库配置:")
        print(f"   工具列表: {tools}")
    else:
        print(f"\n📝 未找到数据库配置，将使用代码配置")


def main():
    """运行所有示例"""
    print("\n" + "=" * 70)
    print("🎯 工作流动态功能示例")
    print("=" * 70)
    
    # 示例 1
    example_1_dynamic_tool_binding()
    
    # 示例 2
    example_2_dynamic_state()
    
    # 示例 3
    example_3_configuration_priority()
    
    print("\n" + "=" * 70)
    print("✅ 所有示例运行完成")
    print("=" * 70)
    
    print("\n💡 提示：")
    print("   1. 动态工具绑定：无需硬编码工具映射")
    print("   2. 动态状态生成：自动从 Agent IO 定义生成状态类")
    print("   3. 配置优先级：数据库配置 > 代码配置")
    print("   4. 向后兼容：默认使用传统模式，可选启用动态功能")


if __name__ == "__main__":
    main()

