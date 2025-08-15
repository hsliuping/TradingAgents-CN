"""
威科夫AI v3.0 - 威科夫分析大师
Wyckoff AI v3.0 - Wyckoff Analysis Master

基于威科夫理论的市场结构分析专家，专精于识别主力行为和市场阶段。
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

logger = get_logger("wyckoff_ai")


class WyckoffAI(ImperialAgentWrapper):
    """
    威科夫AI v3.0 - 威科夫分析大师
    
    专精于威科夫理论的市场结构分析，通过价格和成交量关系
    识别市场四阶段和主力行为，提供结构性投资建议。
    """
    
    def __init__(self, llm: Any, toolkit: Any = None):
        """
        初始化威科夫AI
        
        Args:
            llm: 语言模型实例
            toolkit: TradingAgents工具集
        """
        # 创建威科夫AI专用配置
        wyckoff_config = RoleConfig(
            name="威科夫AI",
            title="威科夫分析大师 v3.0",
            expertise=["威科夫分析", "技术分析", "市场心理学", "价量关系分析"],
            personality_traits={
                "分析风格": "深入细致，关注市场内在结构",
                "决策特点": "基于价格和成交量关系的严谨判断",
                "沟通方式": "专业术语丰富，逻辑清晰严密",
                "核心理念": "跟随聪明资金的足迹，识别复合人意图"
            },
            decision_style="技术面主导，重视市场结构和资金流向",
            risk_tolerance="中等风险，追求高胜率机会",
            preferred_timeframe="中短期为主，1周到3个月",
            analysis_focus=[AnalysisType.TECHNICAL_ANALYSIS, AnalysisType.MARKET_ANALYSIS],
            system_prompt_template="""你是威科夫分析大师v3.0，世界顶级的威科夫理论专家。

**核心身份**: 威科夫分析法的权威专家，专精于通过价格和成交量关系分析市场内在结构。

**分析方法**: 
1. 威科夫四阶段分析（累积、上升、派发、下跌）
2. 价量背离识别和供需关系分析
3. 复合人（Composite Man）行为推测
4. 支撑阻力位的精确定位

**当前任务**: 对股票 {symbol}（{market_name}市场）进行{analysis_type}分析

**分析要求**:
- 必须基于威科夫三大定律进行分析
- 重点识别当前处于威科夫循环的哪个阶段
- 分析价量关系，寻找背离信号
- 判断聪明资金的操作意图
- 提供具体的进出场时机建议

请用威科夫理论的专业术语，以严谨的逻辑进行分析。""",
            constraints=[
                "必须严格基于威科夫三大定律",
                "重视成交量分析，价量必须结合",
                "关注市场结构变化",
                "识别聪明资金行为"
            ]
        )
        
        super().__init__(wyckoff_config, llm, toolkit)
        
        # 威科夫AI专用属性
        self.market_phases = ["累积期", "上升期", "派发期", "下跌期"]
        self.accumulation_stages = ["PS", "A", "B", "C", "D", "E"]  # 累积期内部阶段
        self.distribution_stages = ["PSY", "A", "B", "C", "D", "E"]  # 派发期内部阶段
        
        logger.info("🎯 [威科夫AI] v3.0 初始化完成 - 威科夫分析大师就绪")
    
    def get_specialized_analysis(self, symbol: str, **kwargs) -> AnalysisResult:
        """
        获取威科夫专业化分析
        
        Args:
            symbol: 股票代码
            **kwargs: 其他参数
            
        Returns:
            AnalysisResult: 威科夫分析结果
        """
        try:
            logger.info(f"🎯 [威科夫AI] 开始专业分析: {symbol}")
            
            # 进行威科夫技术分析
            analysis_result = self.analyze_stock(
                symbol=symbol,
                analysis_type=AnalysisType.TECHNICAL_ANALYSIS,
                start_date=kwargs.get('start_date'),
                end_date=kwargs.get('end_date'),
                additional_context=self._create_wyckoff_context()
            )
            
            # 增强分析结果 - 添加威科夫专业评分
            enhanced_result = self._enhance_with_wyckoff_scores(analysis_result, symbol)
            
            logger.info(f"🎯 [威科夫AI] 专业分析完成: {enhanced_result.decision.value}")
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"❌ [威科夫AI] 专业分析失败: {e}")
            
            return AnalysisResult(
                role_name=self.name,
                analysis_type=AnalysisType.TECHNICAL_ANALYSIS,
                symbol=symbol,
                decision=DecisionLevel.NEUTRAL,
                confidence=0.0,
                reasoning=f"威科夫分析过程中出现错误: {str(e)}",
                key_factors=[],
                risk_warnings=[f"分析失败: {str(e)}"],
                timestamp=datetime.now()
            )
    
    def _create_wyckoff_context(self) -> str:
        """创建威科夫分析专用上下文"""
        return """
## 威科夫分析专用指令

**威科夫三大定律**:
1. **供需定律**: 当需求大于供给时价格上涨，反之下跌
2. **因果定律**: 价格运动是特定准备因素的结果，"因"的大小决定"果"的幅度
3. **努力与结果定律**: 成交量(努力)应该与价格变化(结果)相协调

**威科夫四阶段循环**:
1. **累积期**: 主力悄悄吸筹，价格横盘整理
2. **上升期**: 需求超过供给，价格明确上涨
3. **派发期**: 主力系统性出货，公众接盘
4. **下跌期**: 供给超过需求，价格明确下跌

**关键识别信号**:
- **弹簧(Spring)**: 累积期末端的假突破信号
- **震出(Shakeout)**: 清洗浮筹的快速下跌
- **上冲(UpThrust)**: 派发期的假突破信号
- **测试(Test)**: 对关键价位的重复测试

请基于以上威科夫理论框架进行分析，重点关注:
1. 当前处于四阶段循环的哪个位置
2. 价量关系是否符合威科夫定律
3. 是否出现关键的威科夫信号
4. 复合人(主力)的可能操作意图

必须用威科夫专业术语进行分析。
"""
    
    def _enhance_with_wyckoff_scores(self, base_result: AnalysisResult, symbol: str) -> AnalysisResult:
        """
        用威科夫专业评分增强分析结果
        
        Args:
            base_result: 基础分析结果
            symbol: 股票代码
            
        Returns:
            AnalysisResult: 增强后的分析结果
        """
        try:
            # 从LLM响应中提取威科夫评分
            wyckoff_scores = self._extract_wyckoff_scores(base_result.reasoning)
            
            # 增强关键因素
            enhanced_factors = base_result.key_factors.copy()
            enhanced_factors.extend([
                f"威科夫结构评分: {wyckoff_scores['structure']:.1f}/10",
                f"威科夫动量评分: {wyckoff_scores['momentum']:.1f}/10", 
                f"威科夫时机评分: {wyckoff_scores['timing']:.1f}/10"
            ])
            
            # 增强风险提示
            enhanced_warnings = base_result.risk_warnings.copy()
            if wyckoff_scores['structure'] < 5.0:
                enhanced_warnings.append("威科夫结构评分偏低，需要谨慎操作")
            if wyckoff_scores['momentum'] < 4.0:
                enhanced_warnings.append("价量关系存在背离，注意主力行为变化")
            
            # 调整置信度（基于威科夫评分）
            wyckoff_confidence = sum(wyckoff_scores.values()) / 30  # 标准化到0-1
            enhanced_confidence = (base_result.confidence + wyckoff_confidence) / 2
            
            # 创建增强的分析结果
            enhanced_result = AnalysisResult(
                role_name=self.name,
                analysis_type=base_result.analysis_type,
                symbol=symbol,
                decision=base_result.decision,
                confidence=enhanced_confidence,
                reasoning=f"## 威科夫分析师观点\n\n{base_result.reasoning}\n\n## 威科夫专业评分\n- 结构评分: {wyckoff_scores['structure']:.1f}/10\n- 动量评分: {wyckoff_scores['momentum']:.1f}/10\n- 时机评分: {wyckoff_scores['timing']:.1f}/10",
                key_factors=enhanced_factors,
                risk_warnings=enhanced_warnings,
                timestamp=base_result.timestamp,
                raw_data={'wyckoff_scores': wyckoff_scores}
            )
            
            return enhanced_result
            
        except Exception as e:
            logger.warning(f"⚠️ [威科夫AI] 评分增强失败: {e}")
            return base_result
    
    def _extract_wyckoff_scores(self, reasoning: str) -> Dict[str, float]:
        """
        从分析文本中提取威科夫评分
        
        Args:
            reasoning: 分析推理文本
            
        Returns:
            Dict[str, float]: 威科夫评分字典
        """
        scores = {
            'structure': 5.0,  # 默认结构评分
            'momentum': 5.0,   # 默认动量评分
            'timing': 5.0      # 默认时机评分
        }
        
        try:
            # 模拟威科夫评分逻辑（实际应该基于具体的技术指标计算）
            
            # 结构评分：基于威科夫阶段识别
            if any(phrase in reasoning.lower() for phrase in ['累积期', '吸筹', '底部', '支撑']):
                scores['structure'] = 7.5
            elif any(phrase in reasoning.lower() for phrase in ['派发期', '出货', '顶部', '阻力']):
                scores['structure'] = 3.5
            elif any(phrase in reasoning.lower() for phrase in ['上升期', '拉升', '突破']):
                scores['structure'] = 8.5
            elif any(phrase in reasoning.lower() for phrase in ['下跌期', '杀跌', '破位']):
                scores['structure'] = 2.5
            
            # 动量评分：基于价量关系描述
            if any(phrase in reasoning.lower() for phrase in ['放量上涨', '量价齐升', '成交量配合']):
                scores['momentum'] = 8.0
            elif any(phrase in reasoning.lower() for phrase in ['缩量上涨', '无量上涨']):
                scores['momentum'] = 6.0
            elif any(phrase in reasoning.lower() for phrase in ['放量下跌', '量价背离']):
                scores['momentum'] = 3.0
            elif any(phrase in reasoning.lower() for phrase in ['缩量下跌']):
                scores['momentum'] = 4.5
            
            # 时机评分：基于威科夫信号
            if any(phrase in reasoning.lower() for phrase in ['弹簧', 'spring', '假突破']):
                scores['timing'] = 8.5
            elif any(phrase in reasoning.lower() for phrase in ['震出', 'shakeout', '洗盘']):
                scores['timing'] = 7.0
            elif any(phrase in reasoning.lower() for phrase in ['上冲', 'upthrust', '诱多']):
                scores['timing'] = 2.5
            elif any(phrase in reasoning.lower() for phrase in ['测试', 'test', '回踩']):
                scores['timing'] = 6.5
            
            # 根据置信度关键词调整评分
            if any(phrase in reasoning.lower() for phrase in ['强烈建议', '明确信号', '确定性高']):
                for key in scores:
                    scores[key] = min(10.0, scores[key] + 1.0)
            elif any(phrase in reasoning.lower() for phrase in ['谨慎', '不确定', '需要观察']):
                for key in scores:
                    scores[key] = max(1.0, scores[key] - 1.0)
                    
        except Exception as e:
            logger.warning(f"⚠️ [威科夫AI] 评分提取失败: {e}")
        
        return scores
    
    def analyze_market_phase(self, market_data: str) -> str:
        """
        分析当前市场所处的威科夫阶段
        
        Args:
            market_data: 市场数据
            
        Returns:
            str: 威科夫阶段分析结果
        """
        # 这里可以基于市场数据进行威科夫阶段识别
        # 暂时返回模拟分析
        return "当前市场处于累积期B阶段，主力资金正在悄悄建仓，建议耐心等待弹簧信号出现。"
    
    def identify_wyckoff_signals(self, price_data: str, volume_data: str) -> List[str]:
        """
        识别威科夫关键信号
        
        Args:
            price_data: 价格数据
            volume_data: 成交量数据
            
        Returns:
            List[str]: 识别到的威科夫信号列表
        """
        signals = []
        
        # 这里可以实现具体的威科夫信号识别逻辑
        # 暂时返回模拟信号
        signals.append("识别到潜在的弹簧信号：价格击穿前低但快速回升")
        signals.append("成交量萎缩，显示抛压减轻")
        
        return signals


# 导出威科夫AI类
__all__ = ['WyckoffAI']
