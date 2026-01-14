"""
检查特定工具的参数匹配情况
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.tools.config import BUILTIN_TOOLS
import inspect
from core.tools.registry import ToolRegistry

# 要检查的工具
tools_to_check = [
    "get_trade_records",
    "get_market_snapshot_for_review"
]

registry = ToolRegistry()

print("=" * 80)
print("检查工具参数匹配情况")
print("=" * 80)

for tool_id in tools_to_check:
    print(f"\n{'='*80}")
    print(f"工具: {tool_id}")
    print(f"{'='*80}")
    
    # 1. 检查 BUILTIN_TOOLS 中的定义
    if tool_id in BUILTIN_TOOLS:
        metadata = BUILTIN_TOOLS[tool_id]
        print(f"\n📋 BUILTIN_TOOLS 定义:")
        print(f"   参数数量: {len(metadata.parameters)}")
        print(f"   参数列表:")
        for param in metadata.parameters:
            required_str = "必需" if param.required else "可选"
            default_str = f", 默认值: {param.default}" if param.default is not None else ""
            print(f"     - {param.name} ({param.type}): {param.description} [{required_str}]{default_str}")
    else:
        print(f"\n❌ BUILTIN_TOOLS 中未找到定义")
    
    # 2. 检查函数签名
    func = registry.get_function(tool_id)
    if func:
        print(f"\n🔧 函数签名:")
        sig = inspect.signature(func)
        print(f"   参数数量: {len(sig.parameters)}")
        print(f"   参数列表:")
        for param_name, param in sig.parameters.items():
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else "Any"
            default_str = f" = {param.default}" if param.default != inspect.Parameter.empty else ""
            required_str = "必需" if param.default == inspect.Parameter.empty else "可选"
            print(f"     - {param_name}: {param_type}{default_str} [{required_str}]")
    else:
        print(f"\n❌ 未找到函数实现")

