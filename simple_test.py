#!/usr/bin/env python3
"""
简化的三核心角色测试脚本
Simple Test Script for Three Core Roles
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("🚀 简化版三核心角色测试")
print("=" * 50)

def test_basic_imports():
    """测试基本模块导入"""
    print("🧪 [测试1] 基本模块导入...")
    
    try:
        # 测试核心模块
        from imperial_agents.core.imperial_agent_wrapper import (
            ImperialAgentWrapper, AnalysisType, DecisionLevel
        )
        print("   ✅ 核心包装器模块导入成功")
        
        # 测试三个角色类
        from imperial_agents.roles.wyckoff_ai import WyckoffAI
        from imperial_agents.roles.marenhui_ai import MarenhuiAI  
        from imperial_agents.roles.crocodile_mentor_ai import CrocodileMentorAI
        print("   ✅ 三个核心角色类导入成功")
        
        # 测试配置管理
        from imperial_agents.config.role_config_manager import get_config_manager
        print("   ✅ 配置管理模块导入成功")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"   ❌ 其他错误: {e}")
        return False

def test_role_creation():
    """测试角色创建"""
    print("🎭 [测试2] 角色创建测试...")
    
    try:
        # 模拟LLM类
        class MockLLM:
            def __init__(self):
                self.name = "MockLLM"
            
            def invoke(self, messages):
                class MockResponse:
                    def __init__(self):
                        self.content = "模拟分析结果：建议谨慎操作，置信度65%"
                return MockResponse()
        
        # 模拟工具集
        class MockToolkit:
            def __init__(self):
                self.name = "MockToolkit"
                
        mock_llm = MockLLM()
        mock_toolkit = MockToolkit()
        
        # 创建三个角色
        from imperial_agents.roles.wyckoff_ai import WyckoffAI
        from imperial_agents.roles.marenhui_ai import MarenhuiAI  
        from imperial_agents.roles.crocodile_mentor_ai import CrocodileMentorAI
        
        wyckoff = WyckoffAI(mock_llm, mock_toolkit)
        print(f"   ✅ 威科夫AI创建成功: {wyckoff.name}")
        
        marenhui = MarenhuiAI(mock_llm, mock_toolkit)
        print(f"   ✅ 马仁辉AI创建成功: {marenhui.name}")
        
        crocodile = CrocodileMentorAI(mock_llm, mock_toolkit)
        print(f"   ✅ 鳄鱼导师AI创建成功: {crocodile.name}")
        
        return True, {'wyckoff': wyckoff, 'marenhui': marenhui, 'crocodile': crocodile}
        
    except Exception as e:
        print(f"   ❌ 角色创建失败: {e}")
        return False, {}

def test_role_attributes(agents):
    """测试角色属性"""
    print("⚙️ [测试3] 角色属性测试...")
    
    try:
        # 测试威科夫AI属性
        wyckoff = agents['wyckoff']
        print(f"   🎯 威科夫AI属性:")
        print(f"      - 市场阶段数: {len(wyckoff.market_phases)}")
        print(f"      - 累积阶段数: {len(wyckoff.accumulation_stages)}")
        print(f"      - 派发阶段数: {len(wyckoff.distribution_stages)}")
        
        # 测试马仁辉AI属性
        marenhui = agents['marenhui']
        print(f"   📊 马仁辉AI属性:")
        print(f"      - 价格区间: {marenhui.price_range}")
        print(f"      - 时间区间: {marenhui.time_range}天")
        print(f"      - 最大亏损率: {marenhui.max_loss_rate*100:.0f}%")
        
        # 测试鳄鱼导师AI属性
        crocodile = agents['crocodile']
        print(f"   🐊 鳄鱼导师AI属性:")
        print(f"      - 单笔最大亏损: {crocodile.max_single_loss*100:.0f}%")
        print(f"      - 仓位限制: {crocodile.position_size_limit*100:.0f}%")
        print(f"      - 风险警告阈值: {crocodile.risk_warning_threshold}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 属性测试失败: {e}")
        return False

def test_analysis_types():
    """测试分析类型和决策级别"""
    print("📋 [测试4] 分析类型测试...")
    
    try:
        from imperial_agents.core.imperial_agent_wrapper import AnalysisType, DecisionLevel
        
        print("   📊 支持的分析类型:")
        for analysis_type in AnalysisType:
            print(f"      - {analysis_type.value}")
        
        print("   💭 支持的决策级别:")
        for decision in DecisionLevel:
            print(f"      - {decision.value}")
            
        return True
        
    except Exception as e:
        print(f"   ❌ 分析类型测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始三核心角色基础功能测试...")
    
    # 测试1: 基本导入
    import_success = test_basic_imports()
    
    # 测试2: 角色创建
    if import_success:
        creation_success, agents = test_role_creation()
    else:
        creation_success, agents = False, {}
    
    # 测试3: 角色属性
    if creation_success:
        attribute_success = test_role_attributes(agents)
    else:
        attribute_success = False
    
    # 测试4: 分析类型
    if import_success:
        analysis_success = test_analysis_types()
    else:
        analysis_success = False
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    
    tests = [
        ("模块导入", import_success),
        ("角色创建", creation_success),
        ("角色属性", attribute_success),
        ("分析类型", analysis_success)
    ]
    
    passed = sum(1 for _, success in tests if success)
    total = len(tests)
    success_rate = passed / total
    
    for test_name, success in tests:
        status = "✅" if success else "❌"
        print(f"   {status} {test_name}: {'通过' if success else '失败'}")
    
    print(f"\n🏆 总体测试结果: {passed}/{total} ({success_rate:.1%})")
    
    if success_rate >= 1.0:
        print("🎉 所有测试通过！三核心角色基础功能正常。")
        print("✨ Phase 4G-G3 三核心角色实现验证成功！")
    elif success_rate >= 0.75:
        print("⚠️ 大部分测试通过，有少量问题需要修复。")
    else:
        print("❌ 测试失败较多，需要检查实现。")
    
    print(f"\n🎯 下一步: 创建Phase 4G-G3完成报告")
    print(f"🚀 准备进入: Phase 4G-G4 基础协作机制重建")

if __name__ == "__main__":
    main()
