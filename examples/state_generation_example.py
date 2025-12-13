"""
工作流状态自动生成示例

演示如何使用 StateSchemaBuilder 和 StateRegistry 为工作流自动生成状态类
"""

import sys
import os
from typing import TypedDict
from langchain_core.messages import BaseMessage

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.state.builder import StateSchemaBuilder
from core.state.registry import StateRegistry
from core.state.models import StateFieldDefinition, FieldType


def example_1_basic_state_generation():
    """示例1：基本的状态生成"""
    print("\n" + "=" * 70)
    print("示例 1: 为 position_analysis 工作流生成状态类")
    print("=" * 70)
    
    # 创建 StateRegistry
    registry = StateRegistry()
    
    # 定义工作流的 Agent 列表
    workflow_id = "position_analysis"
    agent_ids = ["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
    
    print(f"\n工作流 ID: {workflow_id}")
    print(f"Agent 列表: {agent_ids}")
    
    # 自动生成状态 Schema
    schema = registry.get_or_build(
        workflow_id=workflow_id,
        agent_ids=agent_ids
    )
    
    print(f"\n✅ 状态 Schema 生成成功")
    print(f"   字段总数: {len(schema.fields)}")
    print(f"   字段列表: {list(schema.fields.keys())}")
    
    # 获取生成的 TypedDict 类
    state_class = registry.get_state_class(workflow_id)
    
    print(f"\n✅ TypedDict 类生成成功")
    print(f"   类名: {state_class.__name__}")
    print(f"   类型注解: {state_class.__annotations__}")
    
    return state_class


def example_2_state_with_custom_fields():
    """示例2：带自定义字段的状态生成"""
    print("\n" + "=" * 70)
    print("示例 2: 生成带自定义输入字段的状态类")
    print("=" * 70)
    
    builder = StateSchemaBuilder()
    
    # 定义自定义输入字段
    input_fields = [
        StateFieldDefinition(
            name="ticker",
            type=FieldType.STRING,
            description="股票代码",
            required=True
        ),
        StateFieldDefinition(
            name="trade_date",
            type=FieldType.STRING,
            description="交易日期",
            required=True
        ),
        StateFieldDefinition(
            name="position_size",
            type=FieldType.NUMBER,
            description="持仓数量",
            required=False,
            default=0.0
        )
    ]
    
    print(f"\n自定义输入字段:")
    for field in input_fields:
        print(f"  - {field.name}: {field.type.value} ({'必填' if field.required else '可选'})")
    
    # 构建状态 Schema
    schema = builder.build_from_agents(
        workflow_id="position_analysis_custom",
        agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"],
        input_fields=input_fields
    )
    
    print(f"\n✅ 状态 Schema 生成成功")
    print(f"   输入字段: {[f.name for f in schema.get_input_field_objects()]}")
    print(f"   输出字段: {[f.name for f in schema.get_output_field_objects()]}")
    
    # 生成 TypedDict 类
    state_class = builder.generate_typed_dict(schema)
    
    print(f"\n✅ TypedDict 类生成成功")
    print(f"   类名: {state_class.__name__}")
    
    # 创建状态实例示例
    print(f"\n📝 状态实例示例:")
    state_example = {
        "messages": [],
        "ticker": "AAPL",
        "trade_date": "2024-12-13",
        "position_size": 100.0
    }
    print(f"   {state_example}")
    
    return state_class


def example_3_inspect_agent_dependencies():
    """示例3：检查 Agent 依赖关系"""
    print("\n" + "=" * 70)
    print("示例 3: 检查 Agent 依赖关系")
    print("=" * 70)
    
    builder = StateSchemaBuilder()
    
    schema = builder.build_from_agents(
        workflow_id="position_analysis",
        agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
    )
    
    print(f"\nAgent 依赖关系:")
    if schema.agent_dependencies:
        for agent_id, deps in schema.agent_dependencies.items():
            if deps:
                print(f"  {agent_id} 依赖于:")
                for dep in deps:
                    print(f"    - {dep}")
    else:
        print("  无依赖关系")
    
    # 计算执行顺序
    agent_ids = ["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
    execution_order = schema.get_execution_order(agent_ids)
    
    print(f"\n推荐执行顺序:")
    for i, agent_id in enumerate(execution_order, 1):
        deps = schema.agent_dependencies.get(agent_id, [])
        print(f"  {i}. {agent_id} (依赖数: {len(deps)})")


def main():
    """运行所有示例"""
    print("\n" + "=" * 70)
    print("🎯 工作流状态自动生成示例")
    print("=" * 70)
    
    # 示例 1
    state_class_1 = example_1_basic_state_generation()
    
    # 示例 2
    state_class_2 = example_2_state_with_custom_fields()
    
    # 示例 3
    example_3_inspect_agent_dependencies()
    
    print("\n" + "=" * 70)
    print("✅ 所有示例运行完成")
    print("=" * 70)
    print("\n💡 关键要点:")
    print("  1. StateRegistry 自动缓存生成的状态类")
    print("  2. StateSchemaBuilder 从 Agent IO 定义自动推导字段")
    print("  3. 支持自定义输入字段")
    print("  4. 自动分析 Agent 依赖关系")
    print("  5. 生成的 TypedDict 类可直接用于 LangGraph")


if __name__ == "__main__":
    main()

