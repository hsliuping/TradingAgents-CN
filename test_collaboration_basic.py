"""
简化测试 - 验证Phase 4G-G4协作机制
Simplified Test - Validate Phase 4G-G4 Collaboration System
"""

import sys
import os
import asyncio
from datetime import datetime

# 添加项目路径到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    # 测试核心导入
    print("🔧 [导入测试] 开始导入核心模块...")
    
    from imperial_agents.core.imperial_agent_wrapper import (
        AnalysisResult, 
        AnalysisType, 
        DecisionLevel,
        RoleConfig
    )
    print("✅ [导入成功] imperial_agent_wrapper")
    
    from imperial_agents.core.collaboration_system import (
        RealDataCollaborationSystem,
        CollaborationMode,
        ConflictLevel,
        CollaborationResult
    )
    print("✅ [导入成功] collaboration_system")
    
    print("🎉 [导入完成] 所有核心模块导入成功!")
    
except ImportError as e:
    print(f"❌ [导入失败] {e}")
    print("请检查模块路径和依赖")
    sys.exit(1)

def test_basic_functionality():
    """测试基础功能"""
    print("\n🧪 [基础测试] 开始基础功能测试")
    print("=" * 50)
    
    # 测试枚举类型
    print("🔍 [枚举测试] 测试枚举类型...")
    
    # 测试CollaborationMode
    for mode in CollaborationMode:
        print(f"  协作模式: {mode.value}")
    
    # 测试ConflictLevel
    for level in ConflictLevel:
        print(f"  冲突级别: {level.value}")
    
    # 测试DecisionLevel
    for decision in DecisionLevel:
        print(f"  决策级别: {decision.value}")
    
    print("✅ [枚举测试] 枚举类型测试通过")
    
    # 测试数据结构
    print("\n🏗️ [数据结构测试] 测试数据结构...")
    
    # 创建测试分析结果
    test_result = AnalysisResult(
        role_name="测试角色",
        analysis_type=AnalysisType.TECHNICAL_ANALYSIS,
        symbol="000001.SZ",
        decision=DecisionLevel.BUY,
        confidence=0.8,
        reasoning="这是一个测试分析",
        key_factors=["测试因素1", "测试因素2"],
        risk_warnings=["测试风险1"],
        timestamp=datetime.now()
    )
    
    print(f"  分析结果: {test_result.role_name} - {test_result.decision.value}")
    print(f"  置信度: {test_result.confidence:.2%}")
    
    # 测试转换为字典
    result_dict = test_result.to_dict()
    print(f"  字典转换: 包含 {len(result_dict)} 个字段")
    
    print("✅ [数据结构测试] 数据结构测试通过")
    
    return True

def test_collaboration_result():
    """测试协作结果"""
    print("\n🤝 [协作结果测试] 测试协作结果数据结构...")
    
    # 创建个体分析结果
    individual_results = [
        AnalysisResult(
            role_name="威科夫AI",
            analysis_type=AnalysisType.TECHNICAL_ANALYSIS,
            symbol="000001.SZ",
            decision=DecisionLevel.BUY,
            confidence=0.8,
            reasoning="技术分析支持买入",
            key_factors=["技术突破"],
            risk_warnings=["短期波动"],
            timestamp=datetime.now()
        ),
        AnalysisResult(
            role_name="马仁辉AI", 
            analysis_type=AnalysisType.RISK_ANALYSIS,
            symbol="000001.SZ",
            decision=DecisionLevel.HOLD,
            confidence=0.75,
            reasoning="222法则部分符合",
            key_factors=["价格区间合理"],
            risk_warnings=["需要止损"],
            timestamp=datetime.now()
        )
    ]
    
    # 创建协作结果
    collaboration_result = CollaborationResult(
        symbol="000001.SZ",
        collaboration_mode=CollaborationMode.PARALLEL,
        individual_results=individual_results,
        consensus_decision=DecisionLevel.BUY,
        consensus_confidence=0.775,
        conflict_level=ConflictLevel.MINOR_CONFLICT,
        conflict_details=["轻微决策分歧"],
        final_reasoning="综合分析倾向买入",
        risk_alerts=["注意风险控制"],
        execution_time=2.5,
        timestamp=datetime.now()
    )
    
    print(f"  协作结果: {collaboration_result.symbol}")
    print(f"  协作模式: {collaboration_result.collaboration_mode.value}")
    print(f"  共识决策: {collaboration_result.consensus_decision.value}")
    print(f"  冲突级别: {collaboration_result.conflict_level.value}")
    print(f"  参与角色: {len(collaboration_result.individual_results)} 个")
    
    # 测试转换为字典
    result_dict = collaboration_result.to_dict()
    print(f"  字典转换: 包含 {len(result_dict)} 个字段")
    
    print("✅ [协作结果测试] 协作结果测试通过")
    
    return True

def test_system_initialization():
    """测试系统初始化"""
    print("\n🚀 [系统初始化测试] 测试协作系统初始化...")
    
    try:
        # 创建模拟LLM
        from langchain_community.llms.fake import FakeListLLM
        responses = ["测试响应1", "测试响应2", "测试响应3"]
        llm = FakeListLLM(responses=responses)
        
        print("✅ [模拟LLM] 模拟LLM创建成功")
        
        # 初始化协作系统
        collaboration_system = RealDataCollaborationSystem(llm)
        
        print("✅ [协作系统] 协作系统初始化成功")
        print(f"  智能体数量: {len(collaboration_system.agents)}")
        print(f"  决策权重: {collaboration_system.decision_weights}")
        print(f"  风险阈值: {collaboration_system.risk_thresholds}")
        
        # 测试智能体
        for name, agent in collaboration_system.agents.items():
            print(f"  {name}: {agent.title}")
        
        return True
        
    except Exception as e:
        print(f"❌ [初始化失败] {e}")
        return False

def main():
    """主测试函数"""
    print("🎊 Phase 4G-G4 基础协作机制 - 简化验证测试")
    print("🎯 Imperial AI Collaboration System - Basic Validation")
    print("=" * 60)
    
    test_results = []
    
    # 执行测试
    tests = [
        ("基础功能测试", test_basic_functionality),
        ("协作结果测试", test_collaboration_result),
        ("系统初始化测试", test_system_initialization)
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n📋 [执行测试] {test_name}")
            result = test_func()
            test_results.append((test_name, result))
            
            if result:
                print(f"✅ [测试通过] {test_name}")
            else:
                print(f"❌ [测试失败] {test_name}")
                
        except Exception as e:
            print(f"❌ [测试异常] {test_name}: {e}")
            test_results.append((test_name, False))
    
    # 测试结果汇总
    print("\n" + "=" * 60)
    print("📊 [测试汇总] Phase 4G-G4 基础功能验证结果")
    print("=" * 60)
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed_tests += 1
    
    success_rate = passed_tests / total_tests * 100 if total_tests > 0 else 0
    
    print(f"\n📈 [总体结果]")
    print(f"  测试通过: {passed_tests}/{total_tests}")
    print(f"  成功率: {success_rate:.1f}%")
    
    if success_rate == 100:
        print(f"\n🎉 [验证成功] Phase 4G-G4 基础协作机制验证完全通过!")
        print(f"🚀 [准备就绪] 系统已准备好进行实际分析")
        print(f"🎯 [下一步] 可以开始Phase 4G-G5的完整实现")
    elif success_rate >= 80:
        print(f"\n🟡 [部分成功] 大部分功能验证通过，有少量问题需要修复")
    else:
        print(f"\n🔴 [需要修复] 存在重要问题，需要进一步调试")
    
    print("\n🏁 [测试完成] Phase 4G-G4 基础协作机制验证测试结束")
    
    return success_rate == 100

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
