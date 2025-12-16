"""调试v2.0工作流执行"""
import sys
sys.path.insert(0, '.')

import logging
from core.workflow.templates import V2_STOCK_ANALYSIS_WORKFLOW
from core.workflow.builder import WorkflowBuilder
from core.workflow.engine import WorkflowEngine

# 设置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=" * 80)
print("调试v2.0工作流执行")
print("=" * 80)

# 1. 创建legacy配置（模拟前端传入的配置）
print("\n1. 创建legacy配置...")
legacy_config = {
    "llm_provider": "dashscope",
    "quick_think_llm": "qwen-flash",
    "deep_think_llm": "qwen-flash",
    "temperature": 0.7,
    "max_tokens": 6000,
}
print(f"   ✅ 配置创建成功: {legacy_config}")

# 2. 创建工作流引擎
print("\n2. 创建工作流引擎...")
engine = WorkflowEngine(legacy_config=legacy_config)
engine.load(V2_STOCK_ANALYSIS_WORKFLOW)
print(f"   ✅ 工作流加载成功")

# 3. 编译工作流
print("\n3. 编译工作流...")
try:
    engine.compile()
    print(f"   ✅ 工作流编译成功")
except Exception as e:
    print(f"   ❌ 工作流编译失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 准备输入
print("\n4. 准备输入参数...")
inputs = {
    "ticker": "000001",
    "company_of_interest": "000001",
    "trade_date": "2025-12-15",
    "analysis_date": "2025-12-15",
}
print(f"   输入: {inputs}")

# 5. 执行工作流
print("\n5. 执行工作流...")
print("=" * 80)

try:
    # 使用stream模式查看每个节点的执行
    step_count = 0
    for chunk in engine._compiled_graph.stream(inputs, stream_mode="updates"):
        step_count += 1
        print(f"\n--- Step {step_count} ---")
        if isinstance(chunk, dict):
            for node_name, node_update in chunk.items():
                if node_name.startswith('__'):
                    continue

                print(f"节点: {node_name}")
                if isinstance(node_update, dict):
                    # 显示更新的字段
                    for key, value in node_update.items():
                        if isinstance(value, str):
                            value_preview = value[:100] + "..." if len(value) > 100 else value
                            print(f"  - {key}: {value_preview}")
                        else:
                            print(f"  - {key}: {type(value).__name__}")
                else:
                    print(f"  更新: {type(node_update).__name__}")

    print("\n" + "=" * 80)
    print(f"✅ 工作流执行完成，共 {step_count} 步")

except Exception as e:
    print(f"\n❌ 执行失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)

