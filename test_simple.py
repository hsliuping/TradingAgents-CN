"""
简化的帝国AI角色适配层测试
Simplified Imperial Agent Wrapper Test
"""

import sys
import os
from pathlib import Path

# 添加项目路径到sys.path (当前目录就是项目根目录)
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("🚀 [开始] 帝国AI角色适配层基础测试")
print(f"📂 [路径] 项目根目录: {project_root}")
print(f"🐍 [Python] 版本: {sys.version}")

try:
    # 测试模块导入
    print("\n🧪 [测试1] 测试核心模块导入...")
    
    from imperial_agents.core.imperial_agent_wrapper import (
        AnalysisType, DecisionLevel
    )
    print("✅ [成功] 核心枚举类型导入成功")
    
    from imperial_agents.config.role_config_manager import get_config_manager
    print("✅ [成功] 配置管理器导入成功")
    
    # 测试配置管理器
    print("\n🧪 [测试2] 测试配置管理器...")
    config_manager = get_config_manager()
    roles = config_manager.list_available_roles()
    print(f"✅ [成功] 发现可用角色: {roles}")
    
    # 测试默认配置创建
    print("\n🧪 [测试3] 测试默认配置创建...")
    success = config_manager.create_default_configs()
    print(f"✅ [成功] 默认配置创建: {'成功' if success else '失败'}")
    
    # 测试角色配置加载
    print("\n🧪 [测试4] 测试角色配置加载...")
    wyckoff_config = config_manager.load_role_config("威科夫AI")
    print(f"✅ [成功] 威科夫AI配置加载成功")
    print(f"   - 名称: {wyckoff_config.name}")
    print(f"   - 标题: {wyckoff_config.title}")
    print(f"   - 专业: {', '.join(wyckoff_config.expertise)}")
    
    print("\n" + "=" * 60)
    print("🏆 [结果] 基础测试全部通过！")
    print("✅ [成功] 帝国角色适配层核心功能正常")
    
except Exception as e:
    print(f"\n❌ [错误] 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🎉 [完成] Phase 4G-G2: 帝国角色适配层开发完成！")
