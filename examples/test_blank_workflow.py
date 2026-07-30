"""
测试空白工作流模板

演示如何使用空白工作流模板创建自定义流程
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from core.workflow.templates import BLANK_WORKFLOW
from core.workflow.models import NodeDefinition, EdgeDefinition, NodeType, EdgeType, Position


def test_blank_workflow_structure():
    """测试空白工作流的基本结构"""
    print("=" * 80)
    print("测试空白工作流模板")
    print("=" * 80)
    print()
    
    print("1. 工作流基本信息:")
    print(f"   ID: {BLANK_WORKFLOW.id}")
    print(f"   名称: {BLANK_WORKFLOW.name}")
    print(f"   描述: {BLANK_WORKFLOW.description}")
    print(f"   版本: {BLANK_WORKFLOW.version}")
    print(f"   标签: {', '.join(BLANK_WORKFLOW.tags)}")
    print()
    
    print("2. 节点列表:")
    for node in BLANK_WORKFLOW.nodes:
        print(f"   - {node.id} ({node.type}): {node.label}")
        print(f"     位置: ({node.position.x}, {node.position.y})")
    print()
    
    print("3. 边列表:")
    for edge in BLANK_WORKFLOW.edges:
        print(f"   - {edge.id}: {edge.source} -> {edge.target}")
        if edge.config:
            print(f"     配置: {edge.config}")
    print()


def test_custom_workflow():
    """测试创建自定义工作流"""
    print("=" * 80)
    print("创建自定义工作流示例")
    print("=" * 80)
    print()
    
    # 复制空白模板
    workflow = BLANK_WORKFLOW.model_copy(deep=True)
    workflow.id = "my_simple_analysis"
    workflow.name = "我的简单分析流程"
    workflow.description = "基于空白模板创建的自定义流程，包含市场分析师和研究整合员"
    
    print("1. 添加市场分析师节点...")
    workflow.nodes.append(
        NodeDefinition(
            id="market_analyst",
            type=NodeType.ANALYST,
            agent_id="market_analyst_v2",
            label="市场分析师",
            position=Position(x=400, y=200),
            config={
                "description": "分析市场数据和技术指标",
            }
        )
    )
    
    print("2. 添加研究整合员节点...")
    workflow.nodes.append(
        NodeDefinition(
            id="trader",
            type=NodeType.TRADER,
            agent_id="trader_v2",
            label="研究整合员",
            position=Position(x=400, y=350),
            config={
                "description": "根据分析结果生成用户版研究简报",
            }
        )
    )
    
    print("3. 删除默认的 start -> end 边...")
    workflow.edges = [
        edge for edge in workflow.edges 
        if edge.id != "e_start_end"
    ]
    
    print("4. 添加新的边连接...")
    workflow.edges.extend([
        EdgeDefinition(
            id="e1",
            source="start",
            target="market_analyst",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="e2",
            source="market_analyst",
            target="trader",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="e3",
            source="trader",
            target="end",
            type=EdgeType.NORMAL,
        ),
    ])
    
    print()
    print("✅ 自定义工作流创建完成!")
    print()
    print("工作流信息:")
    print(f"   ID: {workflow.id}")
    print(f"   名称: {workflow.name}")
    print(f"   节点数: {len(workflow.nodes)}")
    print(f"   边数: {len(workflow.edges)}")
    print()
    
    print("节点列表:")
    for node in workflow.nodes:
        print(f"   - {node.id} ({node.type}): {node.label}")
    print()
    
    print("边连接:")
    for edge in workflow.edges:
        print(f"   - {edge.source} -> {edge.target}")
    print()
    
    # 导出为 JSON（可以保存到数据库）
    print("5. 导出为 JSON...")
    workflow_json = workflow.model_dump(mode='json')
    print(f"   JSON 大小: {len(str(workflow_json))} 字符")
    print()
    
    return workflow


def main():
    """主函数"""
    # 测试 1: 空白工作流结构
    test_blank_workflow_structure()
    
    print()
    
    # 测试 2: 创建自定义工作流
    custom_workflow = test_custom_workflow()
    
    print("=" * 80)
    print("✅ 所有测试完成!")
    print("=" * 80)
    print()
    print("💡 提示:")
    print("   - 空白工作流模板可以通过前端界面或 Python 代码使用")
    print("   - 可以添加任意数量的节点和边")
    print("   - 支持并行分析、辩论机制等高级功能")
    print()


if __name__ == "__main__":
    main()

