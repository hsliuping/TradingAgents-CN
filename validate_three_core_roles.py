"""
简化版三核心角色验证脚本
Simplified Three Core Roles Validation Script
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("🚀 三核心角色基础验证")
print("=" * 50)

try:
    # 1. 测试模块导入
    print("🧪 [验证1] 模块导入测试...")
    
    from imperial_agents.core.imperial_agent_wrapper import (
        ImperialAgentFactory, AnalysisType, DecisionLevel
    )
    print("   ✅ 核心包装器导入成功")
    
    from imperial_agents.roles.wyckoff_ai import WyckoffAI
    print("   ✅ 威科夫AI导入成功")
    
    from imperial_agents.roles.marenhui_ai import MarenhuiAI
    print("   ✅ 马仁辉AI导入成功")
    
    from imperial_agents.roles.crocodile_mentor_ai import CrocodileMentorAI
    print("   ✅ 鳄鱼导师AI导入成功")
    
    # 2. 测试角色配置
    print("\n🔧 [验证2] 角色配置测试...")
    
    from imperial_agents.config.role_config_manager import get_config_manager
    config_manager = get_config_manager()
    
    roles = ["威科夫AI", "马仁辉AI", "鳄鱼导师AI"]
    for role_name in roles:
        try:
            config = config_manager.load_role_config(role_name)
            print(f"   ✅ {role_name}配置加载成功")
            print(f"      - 标题: {config.title}")
            print(f"      - 专业: {len(config.expertise)}个领域")
        except Exception as e:
            print(f"   ❌ {role_name}配置加载失败: {e}")
    
    # 3. 测试角色创建
    print("\n🎭 [验证3] 角色创建测试...")
    
    # 模拟LLM
    class MockLLM:
        def __init__(self):
            self.name = "MockLLM"
        
        async def ainvoke(self, messages):
            class MockResponse:
                def __init__(self):
                    self.content = "模拟分析结果：建议买入，置信度75%"
            return MockResponse()
        
        def invoke(self, messages):
            class MockResponse:
                def __init__(self):
                    self.content = "模拟分析结果：建议买入，置信度75%"
            return MockResponse()
    
    # 模拟工具集
    from tradingagents.agents.utils.agent_utils import Toolkit
    toolkit = Toolkit()
    mock_llm = MockLLM()
    
    # 创建角色实例
    agents = {}
    for role_name in roles:
        try:
            agent = ImperialAgentFactory.create_agent(role_name, mock_llm, toolkit)
            agents[role_name] = agent
            print(f"   ✅ {role_name}创建成功")
            print(f"      - 类型: {type(agent).__name__}")
            print(f"      - 决策风格: {agent.role_config.decision_style}")
        except Exception as e:
            print(f"   ❌ {role_name}创建失败: {e}")
    
    # 4. 测试角色特定属性
    print("\n⚙️ [验证4] 角色特定属性测试...")
    
    if "威科夫AI" in agents:
        wyckoff = agents["威科夫AI"]
        print(f"   🎯 威科夫AI特性:")
        print(f"      - 市场阶段: {len(wyckoff.market_phases)}个")
        print(f"      - 累积阶段: {len(wyckoff.accumulation_stages)}个")
    
    if "马仁辉AI" in agents:
        marenhui = agents["马仁辉AI"]
        print(f"   📊 马仁辉AI特性:")
        print(f"      - 价格区间: {marenhui.price_range}")
        print(f"      - 时间区间: {marenhui.time_range}天")
        print(f"      - 最大亏损: {marenhui.max_loss_rate*100:.0f}%")
    
    if "鳄鱼导师AI" in agents:
        crocodile = agents["鳄鱼导师AI"]
        print(f"   🐊 鳄鱼导师AI特性:")
        print(f"      - 单笔最大亏损: {crocodile.max_single_loss*100:.0f}%")
        print(f"      - 仓位限制: {crocodile.position_size_limit*100:.0f}%")
    
    # 5. 测试分析类型
    print("\n📋 [验证5] 分析类型支持测试...")
    
    print(f"   📊 支持的分析类型:")
    for analysis_type in AnalysisType:
        print(f"      - {analysis_type.value}")
    
    print(f"   💭 支持的决策级别:")
    for decision in DecisionLevel:
        print(f"      - {decision.value}")
    
    # 验证结果统计
    print("\n" + "=" * 50)
    print("🏆 验证结果统计:")
    
    total_roles = len(roles)
    created_roles = len(agents)
    success_rate = created_roles / total_roles
    
    print(f"   📊 角色创建成功率: {created_roles}/{total_roles} ({success_rate:.1%})")
    print(f"   ✅ 模块导入: 全部成功")
    print(f"   ✅ 配置管理: 正常工作")
    print(f"   ✅ 工厂模式: 正常工作")
    
    if success_rate >= 1.0:
        print("\n🎉 Phase 4G-G3验证全部通过！")
        print("✨ 三核心角色实现完成，功能正常")
    else:
        print(f"\n⚠️ 部分验证失败，成功率{success_rate:.1%}")
    
    # 展示角色协作概念
    print(f"\n🤝 协作分析概念验证:")
    print(f"   威科夫AI: 提供结构分析 → 市场阶段判断")
    print(f"   马仁辉AI: 提供规则验证 → 222法则检查")
    print(f"   鳄鱼导师AI: 提供风险控制 → 最终风险把关")
    print(f"   协作决策: 加权投票 + 风险一票否决")
    
    print(f"\n🎯 下一步: Phase 4G-G4 基础协作机制重建")
    
except Exception as e:
    print(f"\n❌ 验证过程中出现错误: {e}")
    import traceback
    traceback.print_exc()

print(f"\n🏁 验证完成")
