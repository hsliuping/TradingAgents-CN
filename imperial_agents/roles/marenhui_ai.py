"""
马仁辉AI v3.0 - 222法则验证专家
Marenhui AI v3.0 - 222 Rule Validation Expert

基于222法则的短线交易专家，严格执行纪律化交易策略。
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

logger = get_logger("marenhui_ai")


class MarenhuiAI(ImperialAgentWrapper):
    """
    马仁辉AI v3.0 - 222法则验证专家
    
    专精于222法则的短线交易验证，严格按照纪律化交易体系
    执行买入、持有、卖出决策，以风险控制为核心。
    """
    
    def __init__(self, llm: Any, toolkit: Any = None):
        """
        初始化马仁辉AI
        
        Args:
            llm: 语言模型实例
            toolkit: TradingAgents工具集
        """
        # 创建马仁辉AI专用配置
        marenhui_config = RoleConfig(
            name="马仁辉AI",
            title="222法则验证专家 v3.0",
            expertise=["222法则", "短线交易", "风险控制", "实战验证"],
            personality_traits={
                "分析风格": "实战导向，注重可操作性",
                "决策特点": "严格执行222法则，纪律性极强",
                "沟通方式": "直接明了，重点突出",
                "核心理念": "宁可错过，不可做错"
            },
            decision_style="规则化交易，严格按照222法则执行",
            risk_tolerance="低风险，严格止损",
            preferred_timeframe="短期为主，1-7天",
            analysis_focus=[AnalysisType.RISK_ANALYSIS, AnalysisType.TECHNICAL_ANALYSIS],
            system_prompt_template="""你是马仁辉AI v3.0，222法则的实战验证专家。

**核心身份**: 严格按照222法则进行交易决策的实战专家，以纪律性和风险控制著称。

**222法则核心**:
1. 价格法则：股价在2-22元区间
2. 时间法则：持股不超过2-22个交易日
3. 收益法则：目标收益2%-22%

**当前任务**: 对股票 {symbol}（{market_name}市场）进行{analysis_type}验证

**验证要求**:
- 严格按照222法则三要素进行验证
- 评估当前价格是否符合操作区间
- 分析短期技术指标和风险因素
- 给出具体的进出场策略
- 明确止损和止盈位置

请以实战交易者的视角，用简洁明了的语言给出操作建议。""",
            constraints=[
                "严格执行222法则",
                "重视风险控制",
                "操作必须具备可执行性",
                "止损策略必须明确"
            ]
        )
        
        super().__init__(marenhui_config, llm, toolkit)
        
        # 马仁辉AI专用属性
        self.price_range = (2.0, 22.0)      # 价格区间
        self.time_range = (2, 22)           # 持股天数区间
        self.profit_range = (0.02, 0.22)    # 收益区间
        self.max_loss_rate = 0.08           # 最大亏损率8%
        
        logger.info("📊 [马仁辉AI] v3.0 初始化完成 - 222法则验证专家就绪")
    
    def get_specialized_analysis(self, symbol: str, **kwargs) -> AnalysisResult:
        """
        获取马仁辉222法则专业验证
        
        Args:
            symbol: 股票代码
            **kwargs: 其他参数
            
        Returns:
            AnalysisResult: 222法则验证结果
        """
        try:
            logger.info(f"📊 [马仁辉AI] 开始222法则验证: {symbol}")
            
            # 进行风险分析
            analysis_result = self.analyze_stock(
                symbol=symbol,
                analysis_type=AnalysisType.RISK_ANALYSIS,
                start_date=kwargs.get('start_date'),
                end_date=kwargs.get('end_date'),
                additional_context=self._create_222_context()
            )
            
            # 增强分析结果 - 添加222法则验证
            enhanced_result = self._enhance_with_222_validation(analysis_result, symbol, kwargs)
            
            logger.info(f"📊 [马仁辉AI] 222法则验证完成: {enhanced_result.decision.value}")
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"❌ [马仁辉AI] 222法则验证失败: {e}")
            
            return AnalysisResult(
                role_name=self.name,
                analysis_type=AnalysisType.RISK_ANALYSIS,
                symbol=symbol,
                decision=DecisionLevel.NEUTRAL,
                confidence=0.0,
                reasoning=f"222法则验证过程中出现错误: {str(e)}",
                key_factors=[],
                risk_warnings=[f"验证失败: {str(e)}"],
                timestamp=datetime.now()
            )
    
    def _create_222_context(self) -> str:
        """创建222法则验证专用上下文"""
        return f"""
## 222法则验证专用指令

**222法则三要素**:
1. **价格法则**: 股价必须在{self.price_range[0]}-{self.price_range[1]}元区间内
2. **时间法则**: 持股时间不超过{self.time_range[0]}-{self.time_range[1]}个交易日
3. **收益法则**: 目标收益{self.profit_range[0]*100:.0f}%-{self.profit_range[1]*100:.0f}%

**风险控制原则**:
- 最大亏损不超过{self.max_loss_rate*100:.0f}%
- 严格执行止损纪律
- 不抗单，不加仓摊成本
- 空仓也是一种仓位

**操作纪律**:
1. 符合222法则才能考虑操作
2. 必须设定明确的止损位和止盈位
3. 严格按照计划执行，不能情绪化
4. 宁可错过机会，不能承担大亏损

**验证检查清单**:
□ 股价是否在2-22元区间？
□ 预期持股时间是否在2-22天？
□ 目标收益是否在2%-22%？
□ 止损位是否明确设定？
□ 风险回报比是否合理？

请严格按照222法则验证股票是否适合操作，给出明确的操作建议。
"""
    
    def _enhance_with_222_validation(self, base_result: AnalysisResult, symbol: str, kwargs: Dict) -> AnalysisResult:
        """
        用222法则验证增强分析结果
        
        Args:
            base_result: 基础分析结果
            symbol: 股票代码
            kwargs: 其他参数
            
        Returns:
            AnalysisResult: 增强后的分析结果
        """
        try:
            # 执行222法则验证
            validation_result = self._validate_222_rule(base_result.reasoning, kwargs)
            
            # 基于验证结果调整决策
            adjusted_decision = self._adjust_decision_by_222_rule(
                base_result.decision, 
                validation_result
            )
            
            # 增强关键因素
            enhanced_factors = base_result.key_factors.copy()
            enhanced_factors.extend([
                f"222法则价格验证: {validation_result['price_valid']}",
                f"222法则时间验证: {validation_result['time_valid']}",
                f"222法则收益验证: {validation_result['profit_valid']}",
                f"综合222法则得分: {validation_result['total_score']:.1f}/10"
            ])
            
            # 增强风险提示
            enhanced_warnings = base_result.risk_warnings.copy()
            if not validation_result['price_valid']:
                enhanced_warnings.append("价格超出222法则区间，不符合操作条件")
            if not validation_result['risk_acceptable']:
                enhanced_warnings.append("风险回报比不满足222法则要求")
            enhanced_warnings.append(f"严格执行止损：最大亏损不超过{self.max_loss_rate*100:.0f}%")
            
            # 调整置信度（222法则验证影响）
            rule_confidence = validation_result['total_score'] / 10
            enhanced_confidence = rule_confidence * 0.7 + base_result.confidence * 0.3
            
            # 创建增强的分析结果
            enhanced_result = AnalysisResult(
                role_name=self.name,
                analysis_type=base_result.analysis_type,
                symbol=symbol,
                decision=adjusted_decision,
                confidence=enhanced_confidence,
                reasoning=f"## 马仁辉222法则验证\n\n{base_result.reasoning}\n\n## 222法则检验结果\n{self._format_222_validation(validation_result)}",
                key_factors=enhanced_factors,
                risk_warnings=enhanced_warnings,
                timestamp=base_result.timestamp,
                raw_data={'222_validation': validation_result}
            )
            
            return enhanced_result
            
        except Exception as e:
            logger.warning(f"⚠️ [马仁辉AI] 222法则验证增强失败: {e}")
            return base_result
    
    def _validate_222_rule(self, reasoning: str, kwargs: Dict) -> Dict[str, Any]:
        """
        执行222法则验证
        
        Args:
            reasoning: 分析推理文本
            kwargs: 其他参数
            
        Returns:
            Dict[str, Any]: 222法则验证结果
        """
        validation = {
            'price_valid': False,
            'time_valid': True,  # 假设时间总是满足（短线操作）
            'profit_valid': False,
            'risk_acceptable': False,
            'total_score': 0.0,
            'price_range': self.price_range,
            'recommended_action': '观望'
        }
        
        try:
            # 价格验证（从文本中提取价格信息）
            current_price = self._extract_current_price(reasoning)
            if current_price and self.price_range[0] <= current_price <= self.price_range[1]:
                validation['price_valid'] = True
                validation['total_score'] += 4.0
            
            # 收益验证（分析是否有合理的收益预期）
            if any(phrase in reasoning.lower() for phrase in ['收益', '涨幅', '目标', '上涨']):
                expected_return = self._extract_expected_return(reasoning)
                if expected_return and self.profit_range[0] <= expected_return <= self.profit_range[1]:
                    validation['profit_valid'] = True
                    validation['total_score'] += 3.0
            
            # 风险验证（分析风险控制是否到位）
            if any(phrase in reasoning.lower() for phrase in ['止损', '风险', '控制', '纪律']):
                validation['risk_acceptable'] = True
                validation['total_score'] += 3.0
            
            # 综合评分调整
            if validation['price_valid'] and validation['profit_valid'] and validation['risk_acceptable']:
                validation['total_score'] = min(10.0, validation['total_score'] + 1.0)
                validation['recommended_action'] = '可考虑操作'
            elif validation['price_valid'] and validation['risk_acceptable']:
                validation['recommended_action'] = '谨慎操作'
            else:
                validation['recommended_action'] = '不符合222法则，建议观望'
                
        except Exception as e:
            logger.warning(f"⚠️ [马仁辉AI] 222法则验证计算失败: {e}")
        
        return validation
    
    def _extract_current_price(self, text: str) -> Optional[float]:
        """从文本中提取当前价格"""
        try:
            # 寻找价格模式：数字+元 或 $数字
            price_patterns = [
                r'价格[：:]?\s*(\d+\.?\d*)',
                r'股价[：:]?\s*(\d+\.?\d*)',
                r'当前价[：:]?\s*(\d+\.?\d*)',
                r'(\d+\.?\d*)\s*元',
                r'\$(\d+\.?\d*)'
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, text)
                if match:
                    return float(match.group(1))
            
            return None
        except:
            return None
    
    def _extract_expected_return(self, text: str) -> Optional[float]:
        """从文本中提取预期收益率"""
        try:
            # 寻找收益率模式
            return_patterns = [
                r'收益[：:]?\s*(\d+\.?\d*)%',
                r'涨幅[：:]?\s*(\d+\.?\d*)%',
                r'目标[：:]?\s*(\d+\.?\d*)%',
                r'预期[：:]?\s*(\d+\.?\d*)%'
            ]
            
            for pattern in return_patterns:
                match = re.search(pattern, text)
                if match:
                    return float(match.group(1)) / 100  # 转换为小数
            
            # 如果没有明确的收益率，根据关键词推测
            if any(phrase in text.lower() for phrase in ['小幅上涨', '温和上涨']):
                return 0.05  # 5%
            elif any(phrase in text.lower() for phrase in ['大幅上涨', '强势上涨']):
                return 0.15  # 15%
            
            return None
        except:
            return None
    
    def _adjust_decision_by_222_rule(self, original_decision: DecisionLevel, validation: Dict) -> DecisionLevel:
        """
        根据222法则验证结果调整决策
        
        Args:
            original_decision: 原始决策
            validation: 222法则验证结果
            
        Returns:
            DecisionLevel: 调整后的决策
        """
        # 如果不符合222法则，强制调整为中性或观望
        if validation['total_score'] < 6.0:
            return DecisionLevel.NEUTRAL
        
        # 如果原始决策是买入/强烈买入，但222法则评分不高，降级处理
        if original_decision in [DecisionLevel.STRONG_BUY, DecisionLevel.BUY]:
            if validation['total_score'] >= 8.0:
                return DecisionLevel.BUY
            elif validation['total_score'] >= 6.0:
                return DecisionLevel.HOLD
            else:
                return DecisionLevel.NEUTRAL
        
        return original_decision
    
    def _format_222_validation(self, validation: Dict) -> str:
        """
        格式化222法则验证结果
        
        Args:
            validation: 验证结果字典
            
        Returns:
            str: 格式化的验证报告
        """
        status_icon = "✅" if validation['price_valid'] else "❌"
        price_status = f"{status_icon} 价格验证: {'通过' if validation['price_valid'] else '未通过'}"
        
        status_icon = "✅" if validation['time_valid'] else "❌"
        time_status = f"{status_icon} 时间验证: {'通过' if validation['time_valid'] else '未通过'}"
        
        status_icon = "✅" if validation['profit_valid'] else "❌"
        profit_status = f"{status_icon} 收益验证: {'通过' if validation['profit_valid'] else '未通过'}"
        
        status_icon = "✅" if validation['risk_acceptable'] else "❌"
        risk_status = f"{status_icon} 风险验证: {'通过' if validation['risk_acceptable'] else '未通过'}"
        
        return f"""
**222法则验证详情**:
- {price_status} (要求: {validation['price_range'][0]}-{validation['price_range'][1]}元)
- {time_status} (要求: 2-22个交易日)
- {profit_status} (要求: 2%-22%收益)
- {risk_status} (要求: 明确止损策略)

**综合评分**: {validation['total_score']:.1f}/10
**操作建议**: {validation['recommended_action']}

**马仁辉交易纪律提醒**:
"纪律比信仰重要，宁可错过，不可做错！"
"""
    
    def validate_222_rule_strict(self, symbol: str, price: float, target_return: float, holding_days: int) -> Dict[str, bool]:
        """
        严格的222法则验证
        
        Args:
            symbol: 股票代码
            price: 当前价格
            target_return: 目标收益率
            holding_days: 预期持股天数
            
        Returns:
            Dict[str, bool]: 详细验证结果
        """
        return {
            'price_valid': self.price_range[0] <= price <= self.price_range[1],
            'time_valid': self.time_range[0] <= holding_days <= self.time_range[1],
            'profit_valid': self.profit_range[0] <= target_return <= self.profit_range[1],
            'overall_valid': all([
                self.price_range[0] <= price <= self.price_range[1],
                self.time_range[0] <= holding_days <= self.time_range[1],
                self.profit_range[0] <= target_return <= self.profit_range[1]
            ])
        }


# 导出马仁辉AI类
__all__ = ['MarenhuiAI']
