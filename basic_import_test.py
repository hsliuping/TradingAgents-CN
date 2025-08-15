#!/usr/bin/env python3
"""
最简单的导入测试
"""

import sys
from pathlib import Path

# 添加路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("🚀 开始最简单的导入测试")
print(f"Python版本: {sys.version}")
print(f"项目路径: {project_root}")

# 测试1: 检查基本路径
print("\n📁 检查目录结构:")
imperial_path = project_root / "imperial_agents"
print(f"imperial_agents目录存在: {imperial_path.exists()}")

core_path = imperial_path / "core"
print(f"core目录存在: {core_path.exists()}")

roles_path = imperial_path / "roles"
print(f"roles目录存在: {roles_path.exists()}")

config_path = imperial_path / "config"
print(f"config目录存在: {config_path.exists()}")

# 测试2: 尝试导入
print("\n🧪 尝试导入测试:")

try:
    import imperial_agents
    print("✅ imperial_agents模块导入成功")
except Exception as e:
    print(f"❌ imperial_agents模块导入失败: {e}")

try:
    from imperial_agents.core import imperial_agent_wrapper
    print("✅ imperial_agent_wrapper模块导入成功")
except Exception as e:
    print(f"❌ imperial_agent_wrapper模块导入失败: {e}")

try:
    from imperial_agents.roles import wyckoff_ai
    print("✅ wyckoff_ai模块导入成功")
except Exception as e:
    print(f"❌ wyckoff_ai模块导入失败: {e}")

try:
    from imperial_agents.roles import marenhui_ai
    print("✅ marenhui_ai模块导入成功")
except Exception as e:
    print(f"❌ marenhui_ai模块导入失败: {e}")

try:
    from imperial_agents.roles import crocodile_mentor_ai
    print("✅ crocodile_mentor_ai模块导入成功")
except Exception as e:
    print(f"❌ crocodile_mentor_ai模块导入失败: {e}")

print("\n🎯 基础导入测试完成！")
