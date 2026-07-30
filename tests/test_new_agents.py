"""
测试新创建的 Agent
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_report_generator_v2():
    """测试报告生成器 v2"""
    print("\n" + "="*60)
    print("测试 ReportGeneratorV2")
    print("="*60)
    
    try:
        from core.agents.post_processors import ReportGeneratorV2
        
        # 创建实例
        agent = ReportGeneratorV2()
        
        print(f"✅ Agent ID: {agent.metadata.id}")
        print(f"✅ Agent Name: {agent.metadata.name}")
        print(f"✅ Category: {agent.metadata.category}")
        print(f"✅ Version: {agent.metadata.version}")
        print(f"✅ Icon: {agent.metadata.icon}")
        
        # 测试执行
        test_state = {
            "ticker": "000001",
            "market_report": "市场分析报告内容...",
            "fundamentals_report": "基本面分析报告内容...",
            "bull_report": "积极证据观点...",
            "bear_report": "谨慎证据观点...",
        }
        
        result = agent.execute(test_state)
        
        print(f"\n✅ 执行成功!")
        print(f"   - 提取报告数: {len(result.get('generated_reports', {}))}")
        print(f"   - 结构化报告数: {len(result.get('structured_reports', {}))}")
        print(f"   - 摘要信息: {result.get('report_summary', {})}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_preparer_v2():
    """测试数据准备器 v2"""
    print("\n" + "="*60)
    print("测试 DataPreparerV2")
    print("="*60)
    
    try:
        from core.agents.post_processors import DataPreparerV2
        
        # 创建实例
        agent = DataPreparerV2()
        
        print(f"✅ Agent ID: {agent.metadata.id}")
        print(f"✅ Agent Name: {agent.metadata.name}")
        print(f"✅ Category: {agent.metadata.category}")
        print(f"✅ Version: {agent.metadata.version}")
        print(f"✅ Icon: {agent.metadata.icon}")
        
        # 测试执行
        test_state = {
            "ticker": "000001",
            "analysis_date": "2026-02-19",
        }
        
        result = agent.execute(test_state)
        
        print(f"\n✅ 执行成功!")
        print(f"   - 公司名称: {result.get('company_name', 'N/A')}")
        print(f"   - 所属行业: {result.get('industry', 'N/A')}")
        print(f"   - 当前价格: {result.get('current_price', 'N/A')}")
        print(f"   - 数据准备状态: {result.get('data_prepared', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_registry():
    """测试 Agent 注册"""
    print("\n" + "="*60)
    print("测试 Agent 注册")
    print("="*60)
    
    try:
        from core.agents.registry import get_registry
        
        registry = get_registry()
        
        # 检查是否注册
        report_gen = registry.get("report_generator_v2")
        data_prep = registry.get("data_preparer_v2")
        
        if report_gen:
            print(f"✅ ReportGeneratorV2 已注册")
        else:
            print(f"⚠️ ReportGeneratorV2 未注册")
        
        if data_prep:
            print(f"✅ DataPreparerV2 已注册")
        else:
            print(f"⚠️ DataPreparerV2 未注册")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🚀 开始测试新创建的 Agent\n")
    
    results = []
    
    # 测试报告生成器
    results.append(("ReportGeneratorV2", test_report_generator_v2()))
    
    # 测试数据准备器
    results.append(("DataPreparerV2", test_data_preparer_v2()))
    
    # 测试注册
    results.append(("Agent Registry", test_agent_registry()))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️ 部分测试失败")
    
    sys.exit(0 if all_passed else 1)

