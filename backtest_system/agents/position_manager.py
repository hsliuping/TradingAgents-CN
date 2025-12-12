"""
仓位管理智能体
Position Manager Agent

基于多Agent分析结果进行智能仓位决策
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import pandas as pd
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PositionDecision:
    """仓位决策结果"""
    target_position: float  # 目标仓位比例 (0-1)
    confidence: float       # 决策置信度 (0-1)
    reason: str           # 决策理由
    risk_level: str       # 风险等级: "low", "medium", "high"
    execution_strategy: str # 执行策略: "immediate", "gradual"

class PositionManager:
    """仓位管理智能体"""

    def __init__(self, config: Dict = None):
        """
        初始化仓位管理器

        Args:
            config: 配置参数
        """
        self.config = config or {}

        # 默认配置
        self.default_config = {
            "max_position_change": 0.3,      # 单日最大仓位变化
            "min_position": 0.0,            # 最小仓位
            "max_position": 1.0,            # 最大仓位
            "confidence_threshold": 0.6,     # 置信度阈值
            "risk_adjustment_factor": 0.2,   # 风险调整因子
        }

        # 合并配置
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value

        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def make_position_decision(
        self,
        current_position: float,
        available_capital: float,
        market_analysis: Dict,
        risk_indicators: Dict,
        historical_performance: Dict = None,
        use_llm: bool = True
    ) -> PositionDecision:
        """
        基于市场分析结果做出仓位决策

        Args:
            current_position: 当前仓位比例 (0-1)
            available_capital: 可用资金
            market_analysis: 市场分析结果
            risk_indicators: 风险指标
            historical_performance: 历史表现数据

        Returns:
            PositionDecision: 仓位决策结果
        """

        # 使用LLM进行决策或使用传统规则
        if use_llm:
            return self._llm_based_decision(
                current_position, available_capital,
                market_analysis, risk_indicators, historical_performance
            )
        else:
            # 构建决策提示词
            decision_prompt = self._build_decision_prompt(
                current_position, available_capital,
                market_analysis, risk_indicators, historical_performance
            )

            # 分析市场状态
            market_state = self._analyze_market_state(market_analysis)

        # 生成基础仓位目标
        base_target_position = self._calculate_base_position(
            market_analysis, market_state, current_position
        )

        # 风险调整
        adjusted_target_position = self._risk_adjust_position(
            base_target_position, risk_indicators
        )

        # 置信度评估
        confidence = self._calculate_confidence(
            market_analysis, risk_indicators, market_state
        )

        # 确定执行策略
        execution_strategy = self._determine_execution_strategy(
            current_position, adjusted_target_position, confidence
        )

        # 生成决策理由
        reason = self._generate_decision_reason(
            market_state, market_analysis, risk_indicators,
            current_position, adjusted_target_position
        )

        # 风险等级评估
        risk_level = self._assess_risk_level(risk_indicators, market_state)

        # 最终仓位限制
        final_target_position = max(
            self.config["min_position"],
            min(self.config["max_position"], adjusted_target_position)
        )

        # 单日仓位变化限制
        max_change = self.config["max_position_change"]
        if abs(final_target_position - current_position) > max_change:
            if final_target_position > current_position:
                final_target_position = current_position + max_change
            else:
                final_target_position = current_position - max_change

        decision = PositionDecision(
            target_position=final_target_position,
            confidence=confidence,
            reason=reason,
            risk_level=risk_level,
            execution_strategy=execution_strategy
        )

        self.logger.info(f"仓位决策: {decision}")
        return decision

    def _build_decision_prompt(
        self,
        current_position: float,
        available_capital: float,
        market_analysis: Dict,
        risk_indicators: Dict,
        historical_performance: Dict
    ) -> str:
        """构建决策提示词"""

        prompt = f"""
你是一位专业的仓位管理专家，需要根据以下信息做出精准的仓位决策：

## 当前持仓状态
- 当前仓位: {current_position:.1%}
- 可用资金: {available_capital:,.2f}元
- 持仓成本: {market_analysis.get('cost_basis', 'N/A')}
- 当前盈亏: {market_analysis.get('pnl_ratio', 'N/A')}

## 市场分析结果
- 技术分析信号强度: {market_analysis.get('technical_strength', 0):.2f}
- 基本面评分: {market_analysis.get('fundamental_score', 0):.2f}
- 新闻情绪: {market_analysis.get('news_sentiment', 'neutral')}
- 机构观点一致性: {market_analysis.get('institutional_consensus', 0):.2f}

## 价格走势分析
- 近期趋势: {market_analysis.get('price_trend', 'unknown')}
- 支撑位: {market_analysis.get('support_level', 'N/A')}
- 阻力位: {market_analysis.get('resistance_level', 'N/A')}
- 成交量变化: {market_analysis.get('volume_change', 'N/A')}

## 风险评估
- 波动率水平: {risk_indicators.get('volatility', 0):.2f}
- 市场情绪指数: {risk_indicators.get('market_sentiment', 0):.2f}
- 系统性风险: {risk_indicators.get('systemic_risk', 'medium')}
- 流动性风险: {risk_indicators.get('liquidity_risk', 'low')}

请基于以上信息，分析当前市场状态并给出合理的仓位建议。
重点关注：
1. 市场当前处于什么阶段（趋势、震荡、反转）
2. 各类信号的强度和一致性
3. 风险收益比是否合理
4. 是否需要采取防守或进攻策略
"""

        return prompt

    def _analyze_market_state(self, market_analysis: Dict) -> str:
        """分析市场状态"""

        technical_strength = market_analysis.get('technical_strength', 0)
        fundamental_score = market_analysis.get('fundamental_score', 0)
        news_sentiment = market_analysis.get('news_sentiment', 'neutral')
        price_trend = market_analysis.get('price_trend', 'unknown')
        volume_change = market_analysis.get('volume_change', 0)

        # 震荡市场判断
        if (abs(technical_strength) < 0.3 and
            fundamental_score < 0.5 and
            price_trend in ['sideways', 'unknown']):
            return "sideways"

        # 上升趋势判断
        if (technical_strength > 0.5 and
            fundamental_score > 0.6 and
            news_sentiment in ['positive', 'very_positive'] and
            price_trend in ['upward', 'bullish']):
            return "uptrend"

        # 下降趋势判断
        if (technical_strength < -0.5 and
            fundamental_score < 0.4 and
            news_sentiment in ['negative', 'very_negative'] and
            price_trend in ['downward', 'bearish']):
            return "downtrend"

        # 缩量整理
        if abs(volume_change) < 0.2 and price_trend == 'sideways':
            return "consolidation"

        # 放量突破
        if volume_change > 0.5 and abs(technical_strength) > 0.6:
            return "breakout"

        return "uncertain"

    def _calculate_base_position(
        self,
        market_analysis: Dict,
        market_state: str,
        current_position: float
    ) -> float:
        """计算基础仓位目标"""

        # 根据市场状态设置基础仓位
        state_positions = {
            "uptrend": 0.8,        # 上升趋势 - 高仓位
            "downtrend": 0.2,      # 下降趋势 - 低仓位
            "sideways": 0.5,       # 震荡市 - 中等仓位
            "consolidation": 0.4,  # 整理期 - 偏防守
            "breakout": 0.7,       # 突破期 - 积极参与
            "uncertain": 0.5       # 不确定 - 中性
        }

        base_position = state_positions.get(market_state, 0.5)

        # 根据技术指标强度调整
        technical_strength = market_analysis.get('technical_strength', 0)
        technical_adjustment = technical_strength * 0.2

        # 根据基本面调整
        fundamental_score = market_analysis.get('fundamental_score', 0)
        fundamental_adjustment = (fundamental_score - 0.5) * 0.3

        # 根据新闻情绪调整
        sentiment_map = {
            'very_positive': 0.15, 'positive': 0.1, 'neutral': 0,
            'negative': -0.1, 'very_negative': -0.15
        }
        news_sentiment = market_analysis.get('news_sentiment', 'neutral')
        sentiment_adjustment = sentiment_map.get(news_sentiment, 0)

        # 计算最终基础仓位
        final_position = (base_position +
                         technical_adjustment +
                         fundamental_adjustment +
                         sentiment_adjustment)

        return max(0, min(1, final_position))

    def _risk_adjust_position(
        self,
        base_position: float,
        risk_indicators: Dict
    ) -> float:
        """基于风险指标调整仓位"""

        volatility = risk_indicators.get('volatility', 0.2)
        market_sentiment = risk_indicators.get('market_sentiment', 0.5)
        systemic_risk = risk_indicators.get('systemic_risk', 'medium')

        # 波动率调整
        if volatility > 0.3:  # 高波动率
            volatility_adjustment = -0.2
        elif volatility > 0.2:  # 中等波动率
            volatility_adjustment = -0.1
        else:  # 低波动率
            volatility_adjustment = 0

        # 市场情绪调整
        if market_sentiment < 0.3:  # 市场恐慌
            sentiment_adjustment = -0.15
        elif market_sentiment > 0.7:  # 市场过度乐观
            sentiment_adjustment = -0.05  # 防止追高
        else:
            sentiment_adjustment = 0

        # 系统性风险调整
        systemic_risk_adjustments = {
            'low': 0, 'medium': -0.05, 'high': -0.15, 'very_high': -0.25
        }
        systemic_adjustment = systemic_risk_adjustments.get(systemic_risk, -0.05)

        # 风险调整因子
        risk_factor = self.config["risk_adjustment_factor"]

        total_adjustment = (volatility_adjustment +
                           sentiment_adjustment +
                           systemic_adjustment) * risk_factor

        adjusted_position = base_position + total_adjustment

        return max(0, min(1, adjusted_position))

    def _calculate_confidence(
        self,
        market_analysis: Dict,
        risk_indicators: Dict,
        market_state: str
    ) -> float:
        """计算决策置信度"""

        # 基础置信度
        base_confidence = 0.5

        # 信号一致性
        technical_strength = abs(market_analysis.get('technical_strength', 0))
        fundamental_score = market_analysis.get('fundamental_score', 0)
        institutional_consensus = market_analysis.get('institutional_consensus', 0)

        # 计算信号一致性得分
        signal_consistency = (technical_strength + fundamental_score + institutional_consensus) / 3

        # 市场状态确定性
        state_confidence = {
            "uptrend": 0.8, "downtrend": 0.8, "sideways": 0.6,
            "consolidation": 0.5, "breakout": 0.7, "uncertain": 0.3
        }

        state_certainty = state_confidence.get(market_state, 0.5)

        # 风险水平影响置信度
        volatility = risk_indicators.get('volatility', 0.2)
        if volatility > 0.3:
            risk_penalty = -0.2
        elif volatility > 0.2:
            risk_penalty = -0.1
        else:
            risk_penalty = 0

        # 最终置信度
        final_confidence = (base_confidence * 0.3 +
                           signal_consistency * 0.4 +
                           state_certainty * 0.3 +
                           risk_penalty)

        return max(0, min(1, final_confidence))

    def _determine_execution_strategy(
        self,
        current_position: float,
        target_position: float,
        confidence: float
    ) -> str:
        """确定执行策略"""

        position_change = abs(target_position - current_position)

        # 小幅调整直接执行
        if position_change < 0.1:
            return "immediate"

        # 大幅调整根据置信度决定
        if confidence > 0.8:
            return "immediate"
        elif confidence > 0.6:
            return "gradual"
        else:
            return "gradual"  # 低置信度时分批执行

    def _generate_decision_reason(
        self,
        market_state: str,
        market_analysis: Dict,
        risk_indicators: Dict,
        current_position: float,
        target_position: float
    ) -> str:
        """生成决策理由"""

        reasons = []

        # 市场状态描述
        state_descriptions = {
            "uptrend": "市场处于上升趋势，技术指标显示较强上涨动能",
            "downtrend": "市场处于下降趋势，风险较高需要降低仓位",
            "sideways": "市场震荡整理，建议保持中等仓位等待方向明确",
            "consolidation": "市场缩量整理，建议保守操作控制风险",
            "breakout": "出现放量突破信号，可适度增加仓位参与",
            "uncertain": "市场方向不明，建议谨慎操作维持现状"
        }

        reasons.append(state_descriptions.get(market_state, "市场状态分析中"))

        # 技术分析理由
        technical_strength = market_analysis.get('technical_strength', 0)
        if technical_strength > 0.5:
            reasons.append("技术指标显示积极信号")
        elif technical_strength < -0.5:
            reasons.append("技术指标显示消极信号")

        # 基本面理由
        fundamental_score = market_analysis.get('fundamental_score', 0)
        if fundamental_score > 0.7:
            reasons.append("基本面支撑较强")
        elif fundamental_score < 0.3:
            reasons.append("基本面存在担忧")

        # 新闻情绪理由
        news_sentiment = market_analysis.get('news_sentiment', 'neutral')
        if news_sentiment in ['positive', 'very_positive']:
            reasons.append("新闻情绪偏正面")
        elif news_sentiment in ['negative', 'very_negative']:
            reasons.append("新闻情绪偏负面需要谨慎")

        # 风险控制理由
        volatility = risk_indicators.get('volatility', 0.2)
        if volatility > 0.3:
            reasons.append("市场波动率较高，需要控制风险")

        # 仓位变化理由
        if target_position > current_position:
            reasons.append(f"建议从{current_position:.1%}加仓至{target_position:.1%}")
        elif target_position < current_position:
            reasons.append(f"建议从{current_position:.1%}减仓至{target_position:.1%}")
        else:
            reasons.append("建议维持当前仓位不变")

        return "；".join(reasons)

    def _assess_risk_level(
        self,
        risk_indicators: Dict,
        market_state: str
    ) -> str:
        """评估风险等级"""

        volatility = risk_indicators.get('volatility', 0.2)
        market_sentiment = risk_indicators.get('market_sentiment', 0.5)
        systemic_risk = risk_indicators.get('systemic_risk', 'medium')

        # 计算风险得分
        risk_score = 0

        # 波动率风险
        if volatility > 0.3:
            risk_score += 3
        elif volatility > 0.2:
            risk_score += 2
        else:
            risk_score += 1

        # 市场情绪风险
        if market_sentiment < 0.3:
            risk_score += 3
        elif market_sentiment > 0.8:
            risk_score += 2
        else:
            risk_score += 1

        # 系统性风险
        systemic_risk_scores = {
            'low': 1, 'medium': 2, 'high': 3, 'very_high': 4
        }
        risk_score += systemic_risk_scores.get(systemic_risk, 2)

        # 市场状态风险
        high_risk_states = ['downtrend', 'uncertain']
        if market_state in high_risk_states:
            risk_score += 1

        # 确定风险等级
        if risk_score <= 3:
            return "low"
        elif risk_score <= 6:
            return "medium"
        elif risk_score <= 8:
            return "high"
        else:
            return "very_high"

    def _llm_based_decision(
        self,
        current_position: float,
        available_capital: float,
        market_analysis: Dict,
        risk_indicators: Dict,
        historical_performance: Dict = None
    ) -> PositionDecision:
        """
        使用大语言模型进行仓位决策

        Args:
            current_position: 当前仓位比例
            available_capital: 可用资金
            market_analysis: 市场分析结果
            risk_indicators: 风险指标
            historical_performance: 历史表现数据

        Returns:
            PositionDecision: 仓位决策结果
        """

        try:
            # 调用LLM进行决策
            llm_decision = self._call_llm_for_position_decision(
                current_position, available_capital,
                market_analysis, risk_indicators, historical_performance
            )

            # 解析LLM返回的结果
            target_position = self._parse_llm_position(llm_decision, current_position)
            confidence = self._parse_llm_confidence(llm_decision)
            reason = self._parse_llm_reason(llm_decision)
            risk_level = self._assess_risk_from_llm(llm_decision, risk_indicators)
            execution_strategy = self._determine_execution_strategy_from_llm(llm_decision)

            return PositionDecision(
                target_position=target_position,
                confidence=confidence,
                reason=reason,
                risk_level=risk_level,
                execution_strategy=execution_strategy
            )

        except Exception as e:
            self.logger.error(f"LLM决策失败，回退到规则决策: {e}")
            # 回退到传统的规则决策
            return self.make_position_decision(
                current_position, available_capital,
                market_analysis, risk_indicators, historical_performance, use_llm=False
            )

    def _call_llm_for_position_decision(
        self,
        current_position: float,
        available_capital: float,
        market_analysis: Dict,
        risk_indicators: Dict,
        historical_performance: Dict = None
    ) -> str:
        """
        调用大语言模型进行仓位决策

        Returns:
            str: LLM的决策结果（JSON格式）
        """

        # 构建详细的决策提示词
        prompt = self._build_llm_decision_prompt(
            current_position, available_capital,
            market_analysis, risk_indicators, historical_performance
        )

        try:
            # 使用项目中的DeepSeek适配器
            from tradingagents.llm_adapters.deepseek_adapter import ChatDeepSeek, create_deepseek_llm

            # 创建DeepSeek LLM实例
            llm = create_deepseek_llm(
                model="deepseek-chat",
                temperature=0.3,  # 较低的温度保证决策稳定性
                max_tokens=1000
            )

            # 调用LLM
            response = llm.invoke(prompt)

            # 提取文本内容
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)

            return response_text

        except ImportError:
            self.logger.warning("无法导入LLM工具，使用模拟LLM响应")
            return self._simulate_llm_response(
                current_position, market_analysis, risk_indicators
            )
        except Exception as e:
            self.logger.error(f"调用LLM失败: {e}")
            return self._simulate_llm_response(
                current_position, market_analysis, risk_indicators
            )

    def _build_llm_decision_prompt(
        self,
        current_position: float,
        available_capital: float,
        market_analysis: Dict,
        risk_indicators: Dict,
        historical_performance: Dict = None
    ) -> str:
        """构建LLM决策提示词"""

        # 格式化市场分析数据
        tech_analysis = market_analysis.get("technical_analysis", {})
        sentiment_analysis = market_analysis.get("sentiment_analysis", {})
        fundamentals = market_analysis.get("fundamentals_analysis", {})
        market_state = market_analysis.get("market_state", {})

        prompt = f"""
你是一位专业的投资组合管理专家，需要基于以下全面的市场分析做出精准的仓位决策。

## 当前投资组合状态
- 当前仓位: {current_position:.1%}
- 可用资金: {available_capital:,.2f}元
- 投资组合总价值: {available_capital / (1 - current_position):,.2f}元

## 技术分析结果
- 技术信号: {tech_analysis.get('signal', 'unknown')}
- 技术强度: {tech_analysis.get('strength', 0):.3f}
- RSI指标: {tech_analysis.get('indicators', {}).get('rsi', 50):.1f}
- 成交量信号: {tech_analysis.get('indicators', {}).get('volume_signal', 'normal')}
- 移动平均线: MA5={tech_analysis.get('indicators', {}).get('ma5', 0):.2f}, MA20={tech_analysis.get('indicators', {}).get('ma20', 0):.2f}

## 新闻情绪分析
- 情绪倾向: {sentiment_analysis.get('sentiment', 'neutral')}
- 情绪得分: {sentiment_analysis.get('score', 0):.3f}
- 情绪置信度: {sentiment_analysis.get('confidence', 0):.3f}
- 相关新闻数量: {sentiment_analysis.get('news_count', 0)}

## 基本面分析
- 市盈率(PE): {fundamentals.get('pe_ratio', 0):.2f}
- 市净率(PB): {fundamentals.get('pb_ratio', 0):.2f}
- 净资产收益率(ROE): {fundamentals.get('roe', 0):.2%}
- 负债率: {fundamentals.get('debt_ratio', 0):.2%}
- 基本面评级: {fundamentals.get('rating', 'unknown')}

## 市场状态分析
- 趋势方向: {market_state.get('trend', 'unknown')}
- 市场状态: {market_state.get('state', 'normal')}
- 趋势强度: {market_state.get('strength', 0):.3f}
- 整体信心: {market_state.get('confidence', 0):.3f}

## 风险评估指标
- 综合风险等级: {risk_indicators.get('risk_level', 'medium')}
- 风险评分: {risk_indicators.get('risk_score', 0):.3f}
- 波动率风险: {risk_indicators.get('volatility_risk', 0):.3f}
- 情绪风险: {risk_indicators.get('sentiment_risk', 0):.3f}
- 不确定性风险: {risk_indicators.get('uncertainty_risk', 0):.3f}

## 历史表现
{self._format_historical_performance(historical_performance)}

## 决策要求
请基于以上全面的信息，做出专业的仓位决策。你的决策需要考虑：

1. **多维度分析**：综合考虑技术面、基本面、情绪面
2. **风险控制**：严格控制下行风险，保护本金安全
3. **收益优化**：在风险可控的前提下追求合理收益
4. **市场适应性**：根据不同市场状态调整策略
5. **长期视角**：考虑长期投资价值，避免短期噪音

请以JSON格式返回你的决策：

```json
{{
    "target_position": 0.75,  // 目标仓位比例，范围0-1
    "confidence": 0.85,        // 决策置信度，范围0-1
    "reason": "详细说明你的决策理由",
    "risk_level": "medium",    // 风险等级：low/medium/high/very_high
    "execution_strategy": "gradual",  // 执行策略：immediate/gradual
    "market_outlook": "bullish",      // 市场展望：bullish/bearish/neutral
    "time_horizon": "medium",        // 投资期限：short/medium/long
    "key_factors": [              // 关键影响因素
        "技术指标显示上涨趋势",
        "基本面支撑良好",
        "市场情绪积极"
    ]
}}
```

请确保你的决策逻辑清晰，理由充分，并且严格控制风险。
"""

        return prompt

    def _format_historical_performance(self, historical_performance: Dict) -> str:
        """格式化历史表现数据"""
        if not historical_performance:
            return "- 无历史表现数据"

        return f"""
- 平均日收益率: {historical_performance.get('avg_daily_return', 0):.4f}
- 波动率: {historical_performance.get('volatility', 0):.4f}
- 夏普比率: {historical_performance.get('sharpe_ratio', 0):.3f}
- 最大回撤: {historical_performance.get('max_drawdown', 0):.4f}
- 胜率: {historical_performance.get('win_rate', 0):.2%}
"""

    def _simulate_llm_response(
        self,
        current_position: float,
        market_analysis: Dict,
        risk_indicators: Dict
    ) -> str:
        """模拟LLM响应（当真实LLM不可用时）"""

        # 基于市场分析生成模拟决策
        tech_signal = market_analysis.get("technical_analysis", {}).get("signal", "neutral")
        tech_strength = market_analysis.get("technical_analysis", {}).get("strength", 0.5)
        sentiment = market_analysis.get("sentiment_analysis", {}).get("sentiment", "neutral")
        risk_level = risk_indicators.get("risk_level", "medium")

        # 计算目标仓位
        if tech_signal == "bullish" and sentiment == "positive":
            if risk_level == "low":
                target_position = min(0.9, current_position + 0.3)
            elif risk_level == "medium":
                target_position = min(0.7, current_position + 0.2)
            else:
                target_position = min(0.5, current_position + 0.1)
        elif tech_signal == "bearish" and sentiment == "negative":
            if risk_level == "high":
                target_position = max(0.1, current_position - 0.3)
            else:
                target_position = max(0.2, current_position - 0.2)
        else:
            target_position = max(0.3, min(0.7, 0.5 + (tech_strength - 0.5) * 0.4))

        # 生成理由
        reasons = []
        if tech_signal == "bullish":
            reasons.append("技术指标显示积极信号")
        elif tech_signal == "bearish":
            reasons.append("技术指标显示消极信号")

        if sentiment == "positive":
            reasons.append("市场情绪偏正面")
        elif sentiment == "negative":
            reasons.append("市场情绪需要谨慎")

        if risk_level == "high":
            reasons.append("当前风险较高，需要控制仓位")

        reason = "；".join(reasons)

        # 生成置信度
        confidence = min(0.9, max(0.3, tech_strength + 0.2))

        return f'''{{
    "target_position": {target_position:.3f},
    "confidence": {confidence:.3f},
    "reason": "{reason}",
    "risk_level": "{risk_level}",
    "execution_strategy": "gradual",
    "market_outlook": "{tech_signal}",
    "time_horizon": "medium",
    "key_factors": ["模拟决策分析", "技术指标: {tech_signal}", "市场情绪: {sentiment}", "风险等级: {risk_level}"]
}}'''

    def _extract_json_from_response(self, llm_response: str) -> Dict:
        """从LLM响应中提取JSON内容"""
        import json
        import re

        try:
            # 首先尝试直接解析
            return json.loads(llm_response)
        except json.JSONDecodeError:
            pass

        try:
            # 尝试提取```json代码块
            pattern = r'```json\s*(.*?)\s*```'
            match = re.search(pattern, llm_response, re.DOTALL)
            if match:
                json_content = match.group(1).strip()
                return json.loads(json_content)
        except (json.JSONDecodeError, AttributeError):
            pass

        try:
            # 尝试提取任何```代码块
            pattern = r'```\s*(.*?)\s*```'
            match = re.search(pattern, llm_response, re.DOTALL)
            if match:
                json_content = match.group(1).strip()
                return json.loads(json_content)
        except (json.JSONDecodeError, AttributeError):
            pass

        try:
            # 尝试查找JSON对象模式
            pattern = r'\{\s*".*?"\s*:\s*.*?\}'
            match = re.search(pattern, llm_response, re.DOTALL)
            if match:
                json_content = match.group(0)
                return json.loads(json_content)
        except (json.JSONDecodeError, AttributeError):
            pass

        # 如果所有方法都失败，返回空字典
        return {}

    def _parse_llm_position(self, llm_response: str, current_position: float) -> float:
        """解析LLM返回的目标仓位"""
        try:
            response_dict = self._extract_json_from_response(llm_response)
            target_position = float(response_dict.get("target_position", current_position))

            # 确保仓位在合理范围内
            return max(0.0, min(1.0, target_position))

        except Exception as e:
            self.logger.error(f"解析LLM仓位失败: {e}")
            return current_position

    def _parse_llm_confidence(self, llm_response: str) -> float:
        """解析LLM返回的置信度"""
        try:
            response_dict = self._extract_json_from_response(llm_response)
            confidence = float(response_dict.get("confidence", 0.5))
            return max(0.0, min(1.0, confidence))
        except Exception as e:
            self.logger.error(f"解析LLM置信度失败: {e}")
            return 0.5

    def _parse_llm_reason(self, llm_response: str) -> str:
        """解析LLM返回的决策理由"""
        try:
            response_dict = self._extract_json_from_response(llm_response)
            reason = response_dict.get("reason", "LLM决策分析")
            return reason[:500]  # 限制长度
        except Exception as e:
            self.logger.error(f"解析LLM理由失败: {e}")
            return "LLM决策分析"

    def _assess_risk_from_llm(self, llm_response: str, risk_indicators: Dict) -> str:
        """从LLM响应中评估风险等级"""
        try:
            response_dict = self._extract_json_from_response(llm_response)
            llm_risk = response_dict.get("risk_level", "medium")

            # 结合系统风险指标进行最终判断
            system_risk = risk_indicators.get("risk_level", "medium")
            system_score = risk_indicators.get("risk_score", 0.5)

            # 风险加权
            if system_score > 0.7 and system_risk in ["high", "very_high"]:
                return system_risk
            else:
                return llm_risk

        except Exception as e:
            self.logger.error(f"评估LLM风险等级失败: {e}")
            return risk_indicators.get("risk_level", "medium")

    def _determine_execution_strategy_from_llm(self, llm_response: str) -> str:
        """从LLM响应中确定执行策略"""
        try:
            response_dict = self._extract_json_from_response(llm_response)
            strategy = response_dict.get("execution_strategy", "gradual")
            return strategy if strategy in ["immediate", "gradual"] else "gradual"
        except Exception as e:
            self.logger.error(f"确定LLM执行策略失败: {e}")
            return "gradual"