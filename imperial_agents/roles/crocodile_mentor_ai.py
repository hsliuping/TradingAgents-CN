"""
鳄鱼导师AI v3.0 - 鳄鱼法则风控专家
Crocodile Mentor AI v3.0 - Crocodile Rule Risk Management Expert

基于鳄鱼法则的风险管理专家，严格执行风险控制和资金管理策略。
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from imperial_agents.core.imperial_agent_wrapper import (
    ImperialAgentWrapper, 
    AnalysisResult, 
    AnalysisType, 
    DecisionLevel,
    RoleConfig
)
from tradingagents.utils.logging_init import get_logger

logger = get_logger("crocodile_ai")


class CrocodileMentorAI(ImperialAgentWrapper):
    """
    鳄鱼导师AI v3.0 - 鳄鱼法则风控专家
    
    专精于风险管理和资金保护，严格执行鳄鱼法则：
    当你知道自己犯错时，立即了结出场。保本第一，收益第二。
    """
    
    def __init__(self, llm: Any, toolkit: Any = None):
        """
        初始化鳄鱼导师AI
        
        Args:
            llm: 语言模型实例
            toolkit: TradingAgents工具集
        """
        # 创建鳄鱼导师AI专用配置
        crocodile_config = RoleConfig(
            name="鳄鱼导师AI",
            title="鳄鱼法则风控专家 v3.0",
            expertise=["风险管理", "鳄鱼法则", "心理控制", "资金管理"],
            personality_traits={
                "分析风格": "保守谨慎，风险优先",
                "决策特点": "绝不容忍大额亏损，严格执行止损",
                "沟通方式": "严肃认真，警示性强",
                "核心理念": "保本第一，收益第二"
            },
            decision_style="风险优先，宁可少赚不能大亏",
            risk_tolerance="极低风险，零容忍大亏",
            preferred_timeframe="所有时间框架的风险监控",
            analysis_focus=[AnalysisType.RISK_ANALYSIS],
            system_prompt_template="""你是鳄鱼导师AI v3.0，鳄鱼法则的严格执行者和风险管理专家。

**核心身份**: 专注于风险控制的导师，坚决执行鳄鱼法则，保护投资者免受重大损失。

**鳄鱼法则精髓**:
- 当你知道自己犯错时，立即了结出场
- 切勿试图调整头寸、摊平成本
- 承认错误比寻找借口更重要
- 小损失可以接受，大损失绝不容忍

**当前任务**: 对股票 {symbol}（{market_name}市场）进行{analysis_type}风险评估

**风险评估要求**:
- 识别所有潜在风险因素
- 评估最大可能损失
- 制定严格的止损策略
- 警示高风险操作
- 提供资金管理建议

请以严格的风险控制视角，重点警示风险，保护资金安全。""",
            constraints=[
                "风险控制是第一要务",
                "必须设置明确止损",
                "严禁建议高风险操作",
                "重视资金管理"
            ]
        )
        
        super().__init__(crocodile_config, llm, toolkit)
        
        # 鳄鱼导师AI专用属性
        self.max_single_loss = 0.02          # 单笔最大亏损2%
        self.max_daily_loss = 0.03           # 单日最大亏损3%
        self.max_weekly_loss = 0.05          # 单周最大亏损5%
        self.max_monthly_loss = 0.08         # 单月最大亏损8%
        self.position_size_limit = 0.1       # 单个标的最大仓位10%
        self.risk_warning_threshold = 0.8    # 风险警告阈值
        
        logger.info("🐊 [鳄鱼导师AI] v3.0 初始化完成 - 鳄鱼法则风控专家就绪")
    
    def get_specialized_analysis(self, symbol: str, **kwargs) -> AnalysisResult:
        """
        获取鳄鱼法则专业风险评估
        
        Args:
            symbol: 股票代码
            **kwargs: 其他参数
            
        Returns:
            AnalysisResult: 风险评估结果
        """
        try:
            logger.info(f"🐊 [鳄鱼导师AI] 开始风险评估: {symbol}")
            
            # 进行专业风险分析
            analysis_result = self.analyze_stock(
                symbol=symbol,
                analysis_type=AnalysisType.RISK_ANALYSIS,
                start_date=kwargs.get('start_date'),
                end_date=kwargs.get('end_date'),
                additional_context=self._create_crocodile_context()
            )
            
            # 增强分析结果 - 添加鳄鱼法则风险评估
            enhanced_result = self._enhance_with_crocodile_risk_assessment(analysis_result, symbol, kwargs)
            
            logger.info(f"🐊 [鳄鱼导师AI] 风险评估完成: {enhanced_result.decision.value}")
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"❌ [鳄鱼导师AI] 风险评估失败: {e}")
            
            return AnalysisResult(
                role_name=self.name,
                analysis_type=AnalysisType.RISK_ANALYSIS,
                symbol=symbol,
                decision=DecisionLevel.NEUTRAL,
                confidence=0.0,
                reasoning=f"风险评估过程中出现错误: {str(e)}",
                key_factors=[],
                risk_warnings=[f"评估失败: {str(e)}", "建议暂停操作，直到风险评估完成"],
                timestamp=datetime.now()
            )
    
    def _create_crocodile_context(self) -> str:
        """创建鳄鱼法则风险评估专用上下文"""
        return f"""
## 鳄鱼法则风险管理专用指令

**鳄鱼法则核心原则**:
1. **立即止损**: 发现错误立即出场，不要犹豫
2. **拒绝摊平**: 绝不加仓摊低成本，那是送死行为
3. **承认错误**: 认错比找借口更重要
4. **保护本金**: 小损失可以接受，大损失绝不容忍

**资金管理铁律**:
- 单笔最大亏损: 不超过{self.max_single_loss*100:.0f}%
- 单日最大亏损: 不超过{self.max_daily_loss*100:.0f}%
- 单周最大亏损: 不超过{self.max_weekly_loss*100:.0f}%
- 单月最大亏损: 不超过{self.max_monthly_loss*100:.0f}%
- 单个标的仓位: 不超过{self.position_size_limit*100:.0f}%

**风险识别清单**:
□ 是否有明确的止损位？
□ 最大可能亏损是否可控？
□ 是否存在系统性风险？
□ 流动性是否充足？
□ 是否有不可预知的突发风险？

**心理风险警示**:
- 贪婪会让你失去理智
- 恐惧会让你错失机会
- 希望会让你抗单到死
- 后悔会让你追涨杀跌

**鳄鱼导师金句**:
"鳄鱼咬住你的脚时，你越挣扎，陷得越深。唯一的办法是牺牲那只脚。"
"在市场中，这只脚就是你的亏损仓位。"

请从最严格的风险控制角度评估投资风险，重点强调风险警示。
"""
    
    def _enhance_with_crocodile_risk_assessment(self, base_result: AnalysisResult, symbol: str, kwargs: Dict) -> AnalysisResult:
        """
        用鳄鱼法则风险评估增强分析结果
        
        Args:
            base_result: 基础分析结果
            symbol: 股票代码
            kwargs: 其他参数
            
        Returns:
            AnalysisResult: 增强后的分析结果
        """
        try:
            # 执行鳄鱼法则风险评估
            risk_assessment = self._assess_crocodile_risks(base_result.reasoning, kwargs)
            
            # 基于风险评估强制调整决策（鳄鱼法则优先）
            adjusted_decision = self._adjust_decision_by_risk(
                base_result.decision, 
                risk_assessment
            )
            
            # 增强关键因素（添加风险要素）
            enhanced_factors = base_result.key_factors.copy()
            enhanced_factors.extend([
                f"鳄鱼法则风险等级: {risk_assessment['risk_level']}",
                f"最大损失预估: {risk_assessment['max_loss_estimate']:.1%}",
                f"止损纪律评分: {risk_assessment['stop_loss_score']:.1f}/10",
                f"资金管理评分: {risk_assessment['money_mgmt_score']:.1f}/10"
            ])
            
            # 大幅增强风险提示（鳄鱼导师的核心职责）
            enhanced_warnings = self._create_comprehensive_risk_warnings(risk_assessment)
            enhanced_warnings.extend(base_result.risk_warnings)
            
            # 基于风险重新计算置信度（风险越高，置信度越低）
            risk_adjusted_confidence = self._calculate_risk_adjusted_confidence(
                base_result.confidence, 
                risk_assessment
            )
            
            # 创建增强的分析结果
            enhanced_result = AnalysisResult(
                role_name=self.name,
                analysis_type=base_result.analysis_type,
                symbol=symbol,
                decision=adjusted_decision,
                confidence=risk_adjusted_confidence,
                reasoning=f"## 鳄鱼导师风险评估\n\n{base_result.reasoning}\n\n## 鳄鱼法则风险审查\n{self._format_risk_assessment(risk_assessment)}",
                key_factors=enhanced_factors,
                risk_warnings=enhanced_warnings,
                timestamp=base_result.timestamp,
                raw_data={'crocodile_risk_assessment': risk_assessment}
            )
            
            return enhanced_result
            
        except Exception as e:
            logger.warning(f"⚠️ [鳄鱼导师AI] 风险评估增强失败: {e}")
            return base_result
    
    def _assess_crocodile_risks(self, reasoning: str, kwargs: Dict) -> Dict[str, Any]:
        """
        执行鳄鱼法则风险评估
        
        Args:
            reasoning: 分析推理文本
            kwargs: 其他参数
            
        Returns:
            Dict[str, Any]: 风险评估结果
        """
        assessment = {
            'risk_level': '中等风险',
            'max_loss_estimate': 0.05,
            'stop_loss_score': 5.0,
            'money_mgmt_score': 5.0,
            'overall_risk_score': 5.0,
            'fatal_risks': [],
            'manageable_risks': [],
            'risk_mitigation': []
        }
        
        try:
            # 评估止损纪律
            stop_loss_mentions = len(re.findall(r'(止损|停损|止损位|损失|亏损)', reasoning, re.IGNORECASE))
            if stop_loss_mentions >= 3:
                assessment['stop_loss_score'] = 8.0
            elif stop_loss_mentions >= 1:
                assessment['stop_loss_score'] = 6.0
            else:
                assessment['stop_loss_score'] = 2.0
                assessment['fatal_risks'].append("缺乏明确的止损策略")
            
            # 评估资金管理意识
            if any(phrase in reasoning.lower() for phrase in ['仓位', '资金', '管理', '控制']):
                assessment['money_mgmt_score'] = 7.0
            else:
                assessment['money_mgmt_score'] = 3.0
                assessment['manageable_risks'].append("资金管理意识不足")
            
            # 评估波动性风险
            if any(phrase in reasoning.lower() for phrase in ['波动', '不稳定', '风险', '谨慎']):
                assessment['manageable_risks'].append("市场波动性风险")
                if '高波动' in reasoning.lower() or '剧烈波动' in reasoning.lower():
                    assessment['fatal_risks'].append("极高波动性风险")
            
            # 评估流动性风险
            if any(phrase in reasoning.lower() for phrase in ['流动性', '成交量', '交易量']):
                if '流动性不足' in reasoning.lower() or '成交稀少' in reasoning.lower():
                    assessment['fatal_risks'].append("流动性风险")
            
            # 评估情绪风险
            if any(phrase in reasoning.lower() for phrase in ['情绪', '恐慌', '贪婪', '冲动']):
                assessment['manageable_risks'].append("投资者情绪风险")
            
            # 评估系统性风险
            if any(phrase in reasoning.lower() for phrase in ['系统', '宏观', '政策', '黑天鹅']):
                assessment['fatal_risks'].append("系统性风险")
            
            # 计算综合风险等级
            fatal_count = len(assessment['fatal_risks'])
            manageable_count = len(assessment['manageable_risks'])
            
            if fatal_count >= 2:
                assessment['risk_level'] = '极高风险'
                assessment['overall_risk_score'] = 1.0
                assessment['max_loss_estimate'] = 0.15
            elif fatal_count == 1:
                assessment['risk_level'] = '高风险'
                assessment['overall_risk_score'] = 3.0
                assessment['max_loss_estimate'] = 0.10
            elif manageable_count >= 3:
                assessment['risk_level'] = '中等风险'
                assessment['overall_risk_score'] = 5.0
                assessment['max_loss_estimate'] = 0.05
            else:
                assessment['risk_level'] = '相对较低风险'
                assessment['overall_risk_score'] = 7.0
                assessment['max_loss_estimate'] = 0.03
            
            # 风险缓解建议
            assessment['risk_mitigation'] = [
                f"严格执行{self.max_single_loss*100:.0f}%止损纪律",
                f"控制仓位不超过总资金的{self.position_size_limit*100:.0f}%",
                "设定明确的止盈止损位",
                "避免情绪化交易",
                "建立完整的交易计划"
            ]
            
        except Exception as e:
            logger.warning(f"⚠️ [鳄鱼导师AI] 风险评估计算失败: {e}")
        
        return assessment
    
    def _adjust_decision_by_risk(self, original_decision: DecisionLevel, risk_assessment: Dict) -> DecisionLevel:
        """
        根据鳄鱼法则风险评估强制调整决策
        
        Args:
            original_decision: 原始决策
            risk_assessment: 风险评估结果
            
        Returns:
            DecisionLevel: 调整后的决策
        """
        # 鳄鱼导师的铁律：风险过高必须拒绝
        if risk_assessment['overall_risk_score'] <= 2.0:
            return DecisionLevel.NEUTRAL  # 极高风险，强制中性
        
        # 高风险情况下，降级处理
        if risk_assessment['overall_risk_score'] <= 4.0:
            if original_decision in [DecisionLevel.STRONG_BUY, DecisionLevel.BUY]:
                return DecisionLevel.HOLD  # 降级为持有
            elif original_decision == DecisionLevel.HOLD:
                return DecisionLevel.SELL  # 建议减仓
        
        # 中等风险，保守调整
        if risk_assessment['overall_risk_score'] <= 6.0:
            if original_decision == DecisionLevel.STRONG_BUY:
                return DecisionLevel.BUY  # 从强烈买入降为买入
        
        return original_decision
    
    def _create_comprehensive_risk_warnings(self, risk_assessment: Dict) -> List[str]:
        """
        创建全面的风险警示
        
        Args:
            risk_assessment: 风险评估结果
            
        Returns:
            List[str]: 风险警示列表
        """
        warnings = []
        
        # 致命风险警告
        for risk in risk_assessment['fatal_risks']:
            warnings.append(f"🚨 致命风险: {risk}")
        
        # 可管理风险警告
        for risk in risk_assessment['manageable_risks']:
            warnings.append(f"⚠️ 注意风险: {risk}")
        
        # 鳄鱼法则强制要求
        warnings.extend([
            f"💀 鳄鱼法则: 最大亏损不得超过{self.max_single_loss*100:.0f}%",
            f"📉 强制止损: 亏损达到{self.max_single_loss*100:.0f}%必须出场",
            "🐊 记住: 当鳄鱼咬住你的脚，立即放弃那只脚！",
            "💰 资金为王: 保本第一，收益第二"
        ])
        
        # 风险等级特殊警告
        if risk_assessment['risk_level'] == '极高风险':
            warnings.insert(0, "🔴 极高风险警告: 强烈建议暂停操作！")
        elif risk_assessment['risk_level'] == '高风险':
            warnings.insert(0, "🟠 高风险警告: 谨慎操作，严格止损！")
        
        return warnings
    
    def _calculate_risk_adjusted_confidence(self, original_confidence: float, risk_assessment: Dict) -> float:
        """
        基于风险评估调整置信度
        
        Args:
            original_confidence: 原始置信度
            risk_assessment: 风险评估结果
            
        Returns:
            float: 风险调整后的置信度
        """
        # 风险越高，置信度越低
        risk_penalty = (10 - risk_assessment['overall_risk_score']) / 10
        adjusted_confidence = original_confidence * (1 - risk_penalty * 0.5)
        
        # 确保置信度在合理范围内
        return max(0.1, min(0.9, adjusted_confidence))
    
    def _format_risk_assessment(self, assessment: Dict) -> str:
        """
        格式化风险评估结果
        
        Args:
            assessment: 风险评估结果
            
        Returns:
            str: 格式化的风险评估报告
        """
        risk_icon = "🔴" if assessment['risk_level'] == '极高风险' else \
                   "🟠" if assessment['risk_level'] == '高风险' else \
                   "🟡" if assessment['risk_level'] == '中等风险' else "🟢"
        
        report = f"""
**{risk_icon} 风险等级**: {assessment['risk_level']}
**📊 综合风险评分**: {assessment['overall_risk_score']:.1f}/10
**💸 最大损失预估**: {assessment['max_loss_estimate']:.1%}
**✂️ 止损纪律评分**: {assessment['stop_loss_score']:.1f}/10
**💰 资金管理评分**: {assessment['money_mgmt_score']:.1f}/10

**🚨 致命风险识别**:
"""
        
        if assessment['fatal_risks']:
            for risk in assessment['fatal_risks']:
                report += f"- ❌ {risk}\n"
        else:
            report += "- ✅ 未发现致命风险\n"
        
        report += "\n**⚠️ 可管理风险**:\n"
        if assessment['manageable_risks']:
            for risk in assessment['manageable_risks']:
                report += f"- 🔸 {risk}\n"
        else:
            report += "- ✅ 风险相对可控\n"
        
        report += "\n**🛡️ 风险缓解措施**:\n"
        for mitigation in assessment['risk_mitigation']:
            report += f"- 🔹 {mitigation}\n"
        
        report += f"""
---
**🐊 鳄鱼导师提醒**: 
"当你意识到自己犯错时，立即出场！不要心存幻想，不要试图摊平成本。
市场会给你无数次机会赚钱，但只需要一次致命错误就能让你出局。
记住：保护本金永远是第一位的！"
"""
        
        return report
    
    def assess_portfolio_risk(self, portfolio_data: Dict) -> Dict[str, Any]:
        """
        评估投资组合整体风险
        
        Args:
            portfolio_data: 投资组合数据
            
        Returns:
            Dict[str, Any]: 组合风险评估结果
        """
        # 这里可以实现投资组合风险评估逻辑
        return {
            'portfolio_risk_level': '中等风险',
            'diversification_score': 7.0,
            'concentration_risk': '单个股票集中度过高',
            'correlation_risk': '相关性风险可控',
            'overall_recommendation': '建议适度分散投资'
        }


# 导出鳄鱼导师AI类
__all__ = ['CrocodileMentorAI']
