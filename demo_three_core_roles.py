"""
帝国AI三核心角色协作分析演示
Imperial AI Three Core Roles Collaborative Analysis Demo

展示威科夫AI、马仁辉AI、鳄鱼导师AI的协作分析能力
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from imperial_agents.core.imperial_agent_wrapper import ImperialAgentFactory, AnalysisType
from tradingagents.agents.utils.agent_utils import Toolkit


class MockLLM:
    """模拟LLM用于演示"""
    
    def __init__(self, role_name: str):
        self.role_name = role_name
    
    async def ainvoke(self, messages):
        return self._create_mock_response()
    
    def invoke(self, messages):
        return self._create_mock_response()
    
    def _create_mock_response(self):
        """创建角色特定的模拟响应"""
        class MockResponse:
            def __init__(self, content):
                self.content = content
        
        if "威科夫" in self.role_name:
            return MockResponse("""**决策建议**: 买入
**置信度**: 85%
**关键因素**: 
- 威科夫分析显示当前处于累积期末端的弹簧阶段
- 价量关系健康，成交量在关键位置放大
- 主力资金完成建仓，准备启动上升行情
- 技术结构完整，支撑位明确

**风险提示**:
- 需要突破确认，防止假突破
- 大盘配合度需要关注

**详细分析**:
通过威科夫四阶段分析，当前股票已完成充分的累积阶段整理。
复合人（主力资金）的操作轨迹清晰可见：早期悄悄吸筹，中期反复测试，
现在出现明显的弹簧信号，表明假跌破已经结束，真正的上涨即将开始。
建议在回调时分批建仓，严格设置止损位。""")
        
        elif "马仁辉" in self.role_name:
            return MockResponse("""**决策建议**: 谨慎买入
**置信度**: 75%
**关键因素**: 
- 股价12.50元，符合222法则价格区间要求
- 计划持股5-8个交易日，符合时间规则
- 目标收益6%，在合理收益范围内
- 短线技术指标支持操作

**风险提示**:
- 严格执行8%止损，绝不抗单
- 如果3个交易日内无明显表现，考虑出场
- 大盘如有异动，立即止损

**详细分析**:
经过222法则严格验证，该股票基本满足操作条件：
1. 价格验证✅：12.50元在2-22元区间内
2. 时间验证✅：预期持股5-8天，符合短线要求  
3. 收益验证✅：目标6%收益，风险回报比合理
设定止损位11.50元，目标位13.25元。严格按纪律执行，宁可错过不可做错。""")
        
        elif "鳄鱼" in self.role_name:
            return MockResponse("""**决策建议**: 谨慎观望
**置信度**: 50%
**关键因素**: 
- 整体风险可控，但需要严格止损
- 仓位控制在总资金的3%以内
- 必须设定明确的风险控制计划
- 市场波动性需要密切关注

**风险提示**:
- 🚨 高波动性风险：需要做好心理准备
- 💀 鳄鱼法则：亏损2%立即止损，绝不犹豫
- 📉 强制出场：不要试图摊平成本
- 🐊 核心提醒：保本第一，收益第二
- 💰 资金管理：单笔投资不超过总资金5%

**详细分析**:
从风险管理的角度看，虽然技术面分析显示有操作机会，但必须建立完善的风险控制体系。
当前市场环境下，任何操作都要以保护本金为第一要务。
建议操作前制定完整的资金管理计划：
- 总仓位不超过30%
- 单个股票不超过5%  
- 设定明确的止损位和止盈位
- 准备好心理预期，严格执行纪律
记住鳄鱼法则：当你发现自己犯错时，立即出场！""")
        
        else:
            return MockResponse("基础分析：建议谨慎操作，做好风险控制。")


def demo_individual_analysis():
    """演示单个角色的分析能力"""
    print("🎭 [演示] 三核心角色个体分析能力")
    print("=" * 70)
    
    toolkit = Toolkit()
    demo_symbol = "600036"  # 招商银行
    
    # 创建三个角色实例
    agents = {
        "威科夫AI": ImperialAgentFactory.create_agent("威科夫AI", MockLLM("威科夫AI"), toolkit),
        "马仁辉AI": ImperialAgentFactory.create_agent("马仁辉AI", MockLLM("马仁辉AI"), toolkit),
        "鳄鱼导师AI": ImperialAgentFactory.create_agent("鳄鱼导师AI", MockLLM("鳄鱼导师AI"), toolkit)
    }
    
    results = {}
    
    for role_name, agent in agents.items():
        print(f"\n{agent.role_config.title} 分析:")
        print("-" * 50)
        
        # 获取专业分析
        result = agent.get_specialized_analysis(
            symbol=demo_symbol,
            start_date="2025-07-01",
            end_date="2025-08-15"
        )
        
        results[role_name] = result
        
        # 显示分析摘要
        print(f"📊 决策: {result.decision.value}")
        print(f"🎯 置信度: {result.confidence:.1%}")
        print(f"💡 关键因素: {len(result.key_factors)} 个")
        print(f"⚠️ 风险提示: {len(result.risk_warnings)} 个")
        
        # 显示核心观点
        if result.key_factors:
            print(f"核心观点: {result.key_factors[0]}")
        
        if result.risk_warnings:
            print(f"主要风险: {result.risk_warnings[0]}")
    
    return results


def demo_collaborative_decision(results):
    """演示协作决策机制"""
    print("\n🤝 [演示] 三角色协作决策机制")
    print("=" * 70)
    
    # 收集各角色的决策和置信度
    decisions_data = []
    for role_name, result in results.items():
        decisions_data.append({
            'role': role_name,
            'decision': result.decision.value,
            'confidence': result.confidence,
            'risk_count': len(result.risk_warnings)
        })
    
    # 显示决策矩阵
    print("📊 决策矩阵:")
    print("角色名称".ljust(12) + "决策".ljust(10) + "置信度".ljust(8) + "风险数")
    print("-" * 40)
    for data in decisions_data:
        print(f"{data['role'].ljust(12)}{data['decision'].ljust(10)}{data['confidence']:.1%}".ljust(8) + f"{data['risk_count']}")
    
    # 协作决策算法
    print(f"\n🧠 协作决策过程:")
    
    # 1. 鳄鱼法则一票否决权
    crocodile_result = results["鳄鱼导师AI"]
    if crocodile_result.confidence < 0.6:
        collaborative_decision = "鳄鱼导师AI风险警告，建议暂停操作"
        print(f"   🐊 风险一票否决: {collaborative_decision}")
    else:
        # 2. 加权平均决策
        wyckoff_weight = 0.4    # 威科夫AI权重40%（结构分析）
        marenhui_weight = 0.35  # 马仁辉AI权重35%（规则验证）
        crocodile_weight = 0.25 # 鳄鱼导师AI权重25%（风险控制）
        
        # 决策评分（买入=1, 持有=0.5, 中性=0, 卖出=-0.5, 强烈卖出=-1）
        decision_scores = {
            "强烈买入": 1.0, "买入": 0.8, "谨慎买入": 0.6,
            "持有": 0.5, "中性": 0.0, "谨慎观望": 0.0,
            "卖出": -0.5, "强烈卖出": -1.0
        }
        
        weighted_score = (
            decision_scores.get(results["威科夫AI"].decision.value, 0) * wyckoff_weight +
            decision_scores.get(results["马仁辉AI"].decision.value, 0) * marenhui_weight +
            decision_scores.get(results["鳄鱼导师AI"].decision.value, 0) * crocodile_weight
        )
        
        # 置信度加权
        avg_confidence = (
            results["威科夫AI"].confidence * wyckoff_weight +
            results["马仁辉AI"].confidence * marenhui_weight +
            results["鳄鱼导师AI"].confidence * crocodile_weight
        )
        
        print(f"   📈 威科夫结构分析权重: {wyckoff_weight*100:.0f}%")
        print(f"   📊 马仁辉规则验证权重: {marenhui_weight*100:.0f}%") 
        print(f"   🐊 鳄鱼风险控制权重: {crocodile_weight*100:.0f}%")
        print(f"   🎯 加权决策得分: {weighted_score:.2f}")
        print(f"   📊 综合置信度: {avg_confidence:.1%}")
        
        # 最终决策
        if weighted_score >= 0.7:
            collaborative_decision = "强烈建议买入"
        elif weighted_score >= 0.4:
            collaborative_decision = "建议买入"
        elif weighted_score >= 0.2:
            collaborative_decision = "可考虑买入"
        elif weighted_score >= -0.2:
            collaborative_decision = "保持观望"
        else:
            collaborative_decision = "建议回避"
    
    print(f"\n🎯 最终协作决策: {collaborative_decision}")
    
    return collaborative_decision


def demo_risk_management_cascade():
    """演示分层风险管理机制"""
    print("\n🛡️ [演示] 分层风险管理机制")
    print("=" * 70)
    
    print("帝国AI三层风险防护体系:")
    print("┌─────────────────────────────────────────┐")
    print("│ 🎯 第一层：威科夫AI结构风险识别         │")
    print("│   • 市场阶段判断                       │")
    print("│   • 主力行为分析                       │") 
    print("│   • 结构性风险预警                     │")
    print("├─────────────────────────────────────────┤")
    print("│ 📊 第二层：马仁辉AI规则风险控制         │")
    print("│   • 222法则合规性检查                  │")
    print("│   • 操作纪律执行                       │")
    print("│   • 短线风险管理                       │")
    print("├─────────────────────────────────────────┤")
    print("│ 🐊 第三层：鳄鱼导师AI终极风险防护       │")
    print("│   • 鳄鱼法则严格执行                   │")
    print("│   • 资金管理铁律                       │")
    print("│   • 一票否决权                         │")
    print("└─────────────────────────────────────────┘")
    
    print("\n风险管理协作流程:")
    print("1. 威科夫AI识别结构性风险 → 结构评分")
    print("2. 马仁辉AI验证操作合规性 → 规则评分")
    print("3. 鳄鱼导师AI执行最终风控 → 风险评分")
    print("4. 三层评分综合 → 最终决策")
    
    print("\n特殊风险处理机制:")
    print("• 🚨 鳄鱼导师AI检测到致命风险 → 立即否决")
    print("• ⚠️ 马仁辉AI发现规则不符 → 降级处理")  
    print("• 🎯 威科夫AI识别结构问题 → 调整策略")


def demo_real_world_scenario():
    """演示真实场景应用"""
    print("\n🌍 [演示] 真实场景应用案例")
    print("=" * 70)
    
    scenario = {
        "股票": "平安银行 (000001)", 
        "当前价格": "12.80元",
        "场景": "突破前期高点，成交量放大",
        "市场环境": "大盘震荡上行",
        "时间": "2025年8月15日"
    }
    
    print(f"📈 分析场景: {scenario['股票']}")
    print(f"💰 当前价格: {scenario['当前价格']}")
    print(f"🔍 技术特征: {scenario['场景']}")
    print(f"🌐 市场环境: {scenario['市场环境']}")
    print(f"📅 分析时间: {scenario['时间']}")
    
    print(f"\n三角色分析思路对比:")
    
    # 威科夫AI视角
    print(f"\n🎯 威科夫AI视角:")
    print(f"   • 关注点: 是否完成累积，主力行为如何")
    print(f"   • 分析法: 威科夫四阶段 + 价量关系")
    print(f"   • 决策依据: 结构完整性 + 复合人意图")
    
    # 马仁辉AI视角
    print(f"\n📊 马仁辉AI视角:")
    print(f"   • 关注点: 是否符合222法则操作条件")
    print(f"   • 分析法: 价格区间 + 时间周期 + 目标收益")
    print(f"   • 决策依据: 规则合规性 + 执行纪律")
    
    # 鳄鱼导师AI视角  
    print(f"\n🐊 鳄鱼导师AI视角:")
    print(f"   • 关注点: 风险是否可控，资金是否安全")
    print(f"   • 分析法: 鳄鱼法则 + 资金管理")
    print(f"   • 决策依据: 风险回报比 + 本金保护")
    
    print(f"\n🤝 协作优势:")
    print(f"   ✅ 多角度验证，降低决策偏差")
    print(f"   ✅ 分层风控，确保资金安全")
    print(f"   ✅ 优势互补，提升决策质量")


def main():
    """主演示函数"""
    print("🎭 帝国AI三核心角色协作分析演示")
    print("=" * 80)
    print(f"📅 演示时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 演示目标: 展示威科夫AI、马仁辉AI、鳄鱼导师AI的协作分析能力")
    
    try:
        # 1. 演示个体分析能力
        results = demo_individual_analysis()
        
        # 2. 演示协作决策机制
        collaborative_decision = demo_collaborative_decision(results)
        
        # 3. 演示风险管理体系
        demo_risk_management_cascade()
        
        # 4. 演示真实场景应用
        demo_real_world_scenario()
        
        print("\n" + "=" * 80)
        print("🏆 演示总结:")
        print("✨ 三个核心角色各司其职，优势互补")
        print("🤝 协作决策机制科学合理，风险可控")
        print("🛡️ 分层风险管理体系完善，保护资金安全")
        print(f"🎯 本次演示协作决策: {collaborative_decision}")
        
        print("\n🎊 Phase 4G-G3: 三核心角色实现 - 演示圆满成功！")
        
        print(f"\n📋 核心成就清单:")
        print(f"   ✅ 威科夫AI v3.0 - 基于威科夫理论的结构分析专家")
        print(f"   ✅ 马仁辉AI v3.0 - 基于222法则的规则验证专家")
        print(f"   ✅ 鳄鱼导师AI v3.0 - 基于鳄鱼法则的风险控制专家")
        print(f"   ✅ 协作决策机制 - 加权投票 + 风险一票否决")
        print(f"   ✅ 分层风险防护 - 三层风险管理体系")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    print(f"\n🏁 演示{'成功' if success else '失败'}")
