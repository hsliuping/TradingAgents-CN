"""测试v2.0工作流的并行执行"""
import sys
sys.path.insert(0, '.')

from core.workflow.templates import V2_STOCK_ANALYSIS_WORKFLOW
from core.workflow.builder import WorkflowBuilder
from core.agents.config import AgentConfig

print("=" * 80)
print("测试v2.0工作流的并行执行")
print("=" * 80)

# 1. 检查工作流定义
print("\n1. 工作流定义:")
print(f"   ID: {V2_STOCK_ANALYSIS_WORKFLOW.id}")
print(f"   名称: {V2_STOCK_ANALYSIS_WORKFLOW.name}")
print(f"   节点数: {len(V2_STOCK_ANALYSIS_WORKFLOW.nodes)}")
print(f"   边数: {len(V2_STOCK_ANALYSIS_WORKFLOW.edges)}")

# 2. 检查并行分析师节点
parallel_node = V2_STOCK_ANALYSIS_WORKFLOW.get_node("parallel_analysts")
if parallel_node:
    print(f"\n2. 并行节点: {parallel_node.id}")
    print(f"   类型: {parallel_node.type}")
    
    # 找到从parallel_analysts出发的所有边
    edges_from_parallel = V2_STOCK_ANALYSIS_WORKFLOW.get_edges_from("parallel_analysts")
    print(f"\n3. 从并行节点出发的边 ({len(edges_from_parallel)}条):")
    for edge in edges_from_parallel:
        target_node = V2_STOCK_ANALYSIS_WORKFLOW.get_node(edge.target)
        print(f"   - {edge.source} -> {edge.target} ({target_node.label if target_node else 'unknown'})")

# 3. 检查合并节点
merge_node = V2_STOCK_ANALYSIS_WORKFLOW.get_node("merge_analysts")
if merge_node:
    print(f"\n4. 合并节点: {merge_node.id}")
    print(f"   类型: {merge_node.type}")
    
    # 找到指向merge_analysts的所有边
    edges_to_merge = [e for e in V2_STOCK_ANALYSIS_WORKFLOW.edges if e.target == "merge_analysts"]
    print(f"\n5. 指向合并节点的边 ({len(edges_to_merge)}条):")
    for edge in edges_to_merge:
        source_node = V2_STOCK_ANALYSIS_WORKFLOW.get_node(edge.source)
        print(f"   - {edge.source} -> {edge.target} ({source_node.label if source_node else 'unknown'})")

# 4. 尝试构建工作流
print("\n6. 尝试构建工作流...")
try:
    builder = WorkflowBuilder(default_config=AgentConfig())
    state_schema = builder._get_state_schema()
    print(f"   ✅ 状态Schema创建成功")
    print(f"   状态类: {state_schema.__name__}")
    
    # 检查状态字段的注解
    if hasattr(state_schema, '__annotations__'):
        print(f"\n7. 状态字段注解 (前10个):")
        for i, (field_name, field_type) in enumerate(list(state_schema.__annotations__.items())[:10]):
            print(f"   - {field_name}: {field_type}")
    
    print("\n8. 尝试编译工作流...")
    compiled_graph = builder.build(V2_STOCK_ANALYSIS_WORKFLOW)
    print(f"   ✅ 工作流编译成功")
    
except Exception as e:
    print(f"   ❌ 构建失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)

