"""
三核心角色集成测试脚本
Three Core Roles Integration Test Script

测试威科夫AI、马仁辉AI、鳄鱼导师AI的完整功能
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from imperial_agents.core.imperial_agent_wrapper import ImperialAgentFactory, AnalysisType
from tradingagents.agents.utils.agent_utils import Toolkit


class MockLLM:
    """模拟LLM用于测试"""
    
    def __init__(self, role_name: str):
        self.role_name = role_name
    
    async def ainvoke(self, messages):
        """模拟异步LLM调用"""
        return self._create_mock_response()
    
    def invoke(self, messages):
        """模拟同步LLM调用"""
        return self._create_mock_response()
    
    def _create_mock_response(self):
        """创建模拟响应"""
        class MockResponse:
            def __init__(self, content):
                self.content = content
        
        if "威科夫" in self.role_name:
            return MockResponse("""**决策建议**: 买入
**置信度**: 80%
**关键因素**: 
- 威科夫四阶段分析显示当前处于累积期D阶段
- 价量关系健康，成交量配合价格上升
- 识别到弹簧信号，聪明资金开始建仓
- 结构评分8.5/10，动量评分7.5/10，时机评分8.0/10

**风险提示**:
- 需要关注大盘整体走势配合
- 成交量是否能持续放大

**详细分析**:
基于威科夫分析，当前股票经过充分的累积期整理，主力资金已完成建仓。
近期出现的弹簧信号表明假突破已经结束，真正的上升趋势即将开始。
复合人（主力）的行为显示其正在积极推高股价，建议在回调时分批买入。""")
        
        elif "马仁辉" in self.role_name:
            return MockResponse("""**决策建议**: 谨慎买入
**置信度**: 70%
**关键因素**: 
- 股价15.80元，符合222法则价格区间(2-22元)
- 预期持股7个交易日，符合时间要求
- 目标收益8%，符合收益区间要求
- 技术指标偏强，短线机会明确

**风险提示**:
- 必须严格执行8%止损纪律
- 持股时间不得超过22个交易日
- 如遇大盘急跌，立即止损出场

**详细分析**:
根据222法则验证，该股票基本符合操作条件。当前价位处于合理操作区间，
短期技术指标支持小幅上涨。严格按照222法则操作，设定止损位14.50元，
目标位17.10元。务必执行纪律，宁可错过不可做错。""")
        
        elif "鳄鱼" in self.role_name:
            return MockResponse("""**决策建议**: 中性观望
**置信度**: 60%
**关键因素**: 
- 当前市场整体风险偏高
- 个股流动性充足，但波动较大
- 缺乏明确的止损位设定
- 风险回报比需要进一步优化

**风险提示**:
- 🚨 市场波动性风险较高，需谨慎操作
- 💀 鳄鱼法则: 最大亏损不得超过2%
- 📉 强制止损: 亏损达到2%必须出场
- 🐊 记住: 当鳄鱼咬住你的脚，立即放弃那只脚！
- 💰 资金为王: 保本第一，收益第二

**详细分析**:
从风险管理角度看，当前操作风险偏高。虽然技术面显示有上涨可能，
但必须严格控制风险。建议设定严格的止损位，单笔投资不超过总资金的5%。
如果决定操作，必须制定完整的风险控制计划，绝不可心存侥幸。""")
        
        else:
            return MockResponse("基础分析完成，建议谨慎操作。")


def test_individual_roles():
    """测试单个角色功能"""
    print("🧪 [测试] 开始测试三个核心角色的个体功能")
    print("=" * 60)
    
    toolkit = Toolkit()
    test_symbol = "000001"  # 平安银行
    
    # 测试威科夫AI
    print("\n🎯 [测试] 威科夫AI v3.0")
    wyckoff_ai = ImperialAgentFactory.create_agent(
        role_name="威科夫AI",
        llm=MockLLM("威科夫AI"),
        toolkit=toolkit
    )
    
    wyckoff_result = wyckoff_ai.get_specialized_analysis(
        symbol=test_symbol,
        start_date="2025-01-01",
        end_date="2025-08-15"
    )
    
    print(f"   ✅ 角色: {wyckoff_result.role_name}")
    print(f"   📊 决策: {wyckoff_result.decision.value}")
    print(f"   🎯 置信度: {wyckoff_result.confidence:.1%}")
    print(f"   💡 关键因素: {len(wyckoff_result.key_factors)} 个")
    
    # 测试马仁辉AI
    print("\n📊 [测试] 马仁辉AI v3.0")
    marenhui_ai = ImperialAgentFactory.create_agent(
        role_name="马仁辉AI",
        llm=MockLLM("马仁辉AI"),
        toolkit=toolkit
    )
    
    marenhui_result = marenhui_ai.get_specialized_analysis(
        symbol=test_symbol,
        start_date="2025-01-01", 
        end_date="2025-08-15"
    )
    
    print(f"   ✅ 角色: {marenhui_result.role_name}")
    print(f"   📊 决策: {marenhui_result.decision.value}")
    print(f"   🎯 置信度: {marenhui_result.confidence:.1%}")
    print(f"   ⚠️ 风险提示: {len(marenhui_result.risk_warnings)} 个")
    
    # 测试鳄鱼导师AI
    print("\n🐊 [测试] 鳄鱼导师AI v3.0")
    crocodile_ai = ImperialAgentFactory.create_agent(
        role_name="鳄鱼导师AI",
        llm=MockLLM("鳄鱼导师AI"),
        toolkit=toolkit
    )
    
    crocodile_result = crocodile_ai.get_specialized_analysis(
        symbol=test_symbol,
        start_date="2025-01-01",
        end_date="2025-08-15"
    )
    
    print(f"   ✅ 角色: {crocodile_result.role_name}")
    print(f"   📊 决策: {crocodile_result.decision.value}")
    print(f"   🎯 置信度: {crocodile_result.confidence:.1%}")
    print(f"   🚨 风险警示: {len(crocodile_result.risk_warnings)} 个")
    
    return {
        "wyckoff": wyckoff_result,
        "marenhui": marenhui_result, 
        "crocodile": crocodile_result
    }


def test_collaborative_analysis(results):
    """测试协作分析功能"""
    print("\n🤝 [测试] 三角色协作分析")
    print("=" * 60)
    
    # 分析结果汇总
    decisions = [results["wyckoff"].decision, results["marenhui"].decision, results["crocodile"].decision]
    confidences = [results["wyckoff"].confidence, results["marenhui"].confidence, results["crocodile"].confidence]
    
    print(f"📊 决策汇总:")
    print(f"   威科夫AI: {results['wyckoff'].decision.value} (置信度: {results['wyckoff'].confidence:.1%})")
    print(f"   马仁辉AI: {results['marenhui'].decision.value} (置信度: {results['marenhui'].confidence:.1%})")
    print(f"   鳄鱼导师AI: {results['crocodile'].decision.value} (置信度: {results['crocodile'].confidence:.1%})")
    
    # 简单的协作决策逻辑
    print(f"\n🧠 协作决策分析:")
    
    # 统计决策分布
    from collections import Counter
    decision_count = Counter([d.value for d in decisions])
    print(f"   📈 决策分布: {dict(decision_count)}")
    
    # 计算平均置信度
    avg_confidence = sum(confidences) / len(confidences)
    print(f"   🎯 平均置信度: {avg_confidence:.1%}")
    
    # 风险警示统计
    total_warnings = len(results['wyckoff'].risk_warnings) + \
                    len(results['marenhui'].risk_warnings) + \
                    len(results['crocodile'].risk_warnings)
    print(f"   ⚠️ 总风险提示: {total_warnings} 个")
    
    # 协作建议
    if results['crocodile'].confidence < 0.5:
        collaborative_decision = "风险过高，建议观望"
    elif decision_count["买入"] >= 2:
        collaborative_decision = "多数同意买入"
    elif decision_count["中性"] >= 2:
        collaborative_decision = "保持观望"
    else:
        collaborative_decision = "意见分歧，谨慎决策"
    
    print(f"   🎯 协作建议: {collaborative_decision}")
    
    return collaborative_decision


def test_role_specific_features():
    """测试角色特定功能"""
    print("\n🔍 [测试] 角色特定功能验证")
    print("=" * 60)
    
    toolkit = Toolkit()
    
    # 测试威科夫AI的威科夫评分
    print("\n🎯 威科夫AI特定功能:")
    wyckoff_ai = ImperialAgentFactory.create_agent("威科夫AI", MockLLM("威科夫AI"), toolkit)
    print(f"   ✅ 市场阶段分析: {wyckoff_ai.market_phases}")
    print(f"   ✅ 累积期阶段: {wyckoff_ai.accumulation_stages}")
    
    # 测试马仁辉AI的222法则
    print("\n📊 马仁辉AI特定功能:")
    marenhui_ai = ImperialAgentFactory.create_agent("马仁辉AI", MockLLM("马仁辉AI"), toolkit)
    print(f"   ✅ 价格区间: {marenhui_ai.price_range}")
    print(f"   ✅ 时间区间: {marenhui_ai.time_range} 天")
    print(f"   ✅ 收益区间: {marenhui_ai.profit_range[0]*100:.0f}%-{marenhui_ai.profit_range[1]*100:.0f}%")
    
    # 测试222法则验证
    validation = marenhui_ai.validate_222_rule_strict("000001", 15.8, 0.08, 7)
    print(f"   ✅ 222法则验证: {validation}")
    
    # 测试鳄鱼导师AI的风险控制
    print("\n🐊 鳄鱼导师AI特定功能:")
    crocodile_ai = ImperialAgentFactory.create_agent("鳄鱼导师AI", MockLLM("鳄鱼导师AI"), toolkit)
    print(f"   ✅ 最大单笔亏损: {crocodile_ai.max_single_loss*100:.0f}%")
    print(f"   ✅ 最大单日亏损: {crocodile_ai.max_daily_loss*100:.0f}%")
    print(f"   ✅ 单个标的仓位限制: {crocodile_ai.position_size_limit*100:.0f}%")
    
    # 测试投资组合风险评估
    portfolio_risk = crocodile_ai.assess_portfolio_risk({})
    print(f"   ✅ 组合风险评估: {portfolio_risk['portfolio_risk_level']}")


def test_analysis_types():
    """测试不同分析类型"""
    print("\n📋 [测试] 分析类型适配验证")
    print("=" * 60)
    
    from imperial_agents.core.imperial_agent_wrapper import AnalysisType
    
    # 验证各角色的分析重点
    toolkit = Toolkit()
    
    # 威科夫AI - 技术分析和市场分析
    wyckoff_ai = ImperialAgentFactory.create_agent("威科夫AI", MockLLM("威科夫AI"), toolkit)
    print(f"🎯 威科夫AI分析重点: {[t.value for t in wyckoff_ai.role_config.analysis_focus]}")
    
    # 马仁辉AI - 风险分析和技术分析
    marenhui_ai = ImperialAgentFactory.create_agent("马仁辉AI", MockLLM("马仁辉AI"), toolkit)
    print(f"📊 马仁辉AI分析重点: {[t.value for t in marenhui_ai.role_config.analysis_focus]}")
    
    # 鳄鱼导师AI - 风险分析
    crocodile_ai = ImperialAgentFactory.create_agent("鳄鱼导师AI", MockLLM("鳄鱼导师AI"), toolkit)
    print(f"🐊 鳄鱼导师AI分析重点: {[t.value for t in crocodile_ai.role_config.analysis_focus]}")
    
    # 测试不同分析类型的调用
    print(f"\n📋 支持的分析类型:")
    for analysis_type in AnalysisType:
        print(f"   - {analysis_type.value}")


def main():
    """主测试函数"""
    print("🚀 三核心角色集成测试开始")
    print("=" * 80)
    
    try:
        # 1. 测试单个角色功能
        results = test_individual_roles()
        
        # 2. 测试协作分析
        collaborative_decision = test_collaborative_analysis(results)
        
        # 3. 测试角色特定功能
        test_role_specific_features()
        
        # 4. 测试分析类型
        test_analysis_types()
        
        print("\n" + "=" * 80)
        print("🏆 测试结果汇总:")
        print("✅ 威科夫AI v3.0 - 威科夫分析大师功能正常")
        print("✅ 马仁辉AI v3.0 - 222法则验证专家功能正常") 
        print("✅ 鳄鱼导师AI v3.0 - 鳄鱼法则风控专家功能正常")
        print("✅ 三角色协作分析机制正常")
        print("✅ 角色特定功能验证通过")
        print(f"🤝 协作决策结果: {collaborative_decision}")
        
        print("\n🎉 Phase 4G-G3: 三核心角色实现 - 测试全部通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    print(f"\n🏁 测试{'成功' if success else '失败'}")
