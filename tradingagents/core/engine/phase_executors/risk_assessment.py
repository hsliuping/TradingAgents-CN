# tradingagents/core/engine/phase_executors/risk_assessment.py
"""
风险评估阶段执行器

执行多维度风险评估：
1. RiskyRisk (激进风控) - 风险承受度高
2. SafeRisk (稳健风控) - 风险承受度低
3. NeutralRisk (中性风控) - 平衡风险和收益
4. RiskManager (风控经理) - 综合评估，形成最终决策
"""

from typing import Any, Dict, List, Optional

from tradingagents.utils.logging_init import get_logger

from ..analysis_context import AnalysisContext
from ..data_access_manager import DataAccessManager
from ..data_contract import DataLayer
from .base import PhaseExecutor

logger = get_logger("default")


class RiskAssessmentPhase(PhaseExecutor):
    """
    风险评估阶段执行器
    
    执行多维度风险评估，形成最终交易决策
    """
    
    phase_name = "RiskAssessmentPhase"
    
    def __init__(
        self,
        llm_provider: Any = None,
        config: Optional[Dict[str, Any]] = None,
        risk_profiles: Optional[List[str]] = None
    ):
        """
        初始化风险评估阶段
        
        Args:
            llm_provider: LLM 提供者
            config: 阶段配置
            risk_profiles: 风控类型列表，默认全部
        """
        super().__init__(llm_provider, config)
        self.risk_profiles = risk_profiles or ["risky", "safe", "neutral"]
    
    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行风险评估阶段
        
        Args:
            context: 分析上下文
            data_manager: 数据访问管理器
            
        Returns:
            风险评估结果
        """
        self.log_start()
        
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.info(f"⚖️ [{self.phase_name}] 风险评估: {ticker}")
        
        outputs = {
            "ticker": ticker,
            "risk_reports": [],
            "final_decision": None
        }
        
        # 获取交易信号
        trade_signal = context.get(DataLayer.DECISIONS, "trade_signal")
        investment_plan = context.get(DataLayer.DECISIONS, "investment_plan")
        
        if trade_signal is None:
            logger.warning(f"⚠️ [{self.phase_name}] 未找到交易信号，跳过风险评估")
            return outputs
        
        # 1. 执行各风控评估
        risk_reports = {}
        
        if "risky" in self.risk_profiles:
            risky_report = self._run_risky_risk(context, trade_signal)
            context.set(DataLayer.REPORTS, "risky_risk_report", risky_report, source="risky_risk")
            risk_reports["risky"] = risky_report
            outputs["risk_reports"].append("risky")
        
        if "safe" in self.risk_profiles:
            safe_report = self._run_safe_risk(context, trade_signal)
            context.set(DataLayer.REPORTS, "safe_risk_report", safe_report, source="safe_risk")
            risk_reports["safe"] = safe_report
            outputs["risk_reports"].append("safe")
        
        if "neutral" in self.risk_profiles:
            neutral_report = self._run_neutral_risk(context, trade_signal)
            context.set(DataLayer.REPORTS, "neutral_risk_report", neutral_report, source="neutral_risk")
            risk_reports["neutral"] = neutral_report
            outputs["risk_reports"].append("neutral")
        
        # 2. 综合风险评估
        risk_assessment = self._aggregate_risk_assessment(risk_reports)
        context.set(DataLayer.DECISIONS, "risk_assessment", risk_assessment, source="risk_manager")
        
        # 3. 形成最终决策
        final_decision = self._form_final_decision(context, trade_signal, risk_assessment)
        context.set(DataLayer.DECISIONS, "final_decision", final_decision, source="risk_manager")
        outputs["final_decision"] = final_decision.get("action")
        
        self.log_end(outputs)
        return outputs
    
    def _run_risky_risk(self, context: AnalysisContext, trade_signal: Dict[str, Any]) -> Dict[str, Any]:
        """激进风控评估"""
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.debug(f"🔥 [{self.phase_name}] 激进风控: {ticker}")
        
        return {
            "profile": "risky",
            "ticker": ticker,
            "risk_tolerance": "high",
            "position_adjustment": 1.2,  # 建议放大仓位
            "assessment": "风险可控，可以加大仓位"
        }
    
    def _run_safe_risk(self, context: AnalysisContext, trade_signal: Dict[str, Any]) -> Dict[str, Any]:
        """稳健风控评估"""
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.debug(f"🛡️ [{self.phase_name}] 稳健风控: {ticker}")
        
        return {
            "profile": "safe",
            "ticker": ticker,
            "risk_tolerance": "low",
            "position_adjustment": 0.5,  # 建议减小仓位
            "assessment": "建议谨慎操作，减小仓位"
        }
    
    def _run_neutral_risk(self, context: AnalysisContext, trade_signal: Dict[str, Any]) -> Dict[str, Any]:
        """中性风控评估"""
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.debug(f"⚖️ [{self.phase_name}] 中性风控: {ticker}")

        return {
            "profile": "neutral",
            "ticker": ticker,
            "risk_tolerance": "medium",
            "position_adjustment": 1.0,  # 维持原仓位
            "assessment": "风险收益比合理，维持建议"
        }

    def _aggregate_risk_assessment(self, risk_reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        聚合风险评估结果

        Args:
            risk_reports: 各风控报告

        Returns:
            综合风险评估
        """
        # 计算平均仓位调整
        adjustments = [r.get("position_adjustment", 1.0) for r in risk_reports.values()]
        avg_adjustment = sum(adjustments) / len(adjustments) if adjustments else 1.0

        # 统计风险意见
        opinions = {r.get("risk_tolerance"): r.get("assessment") for r in risk_reports.values()}

        return {
            "avg_position_adjustment": avg_adjustment,
            "risk_opinions": opinions,
            "overall_risk_level": self._determine_risk_level(avg_adjustment)
        }

    def _determine_risk_level(self, adjustment: float) -> str:
        """根据仓位调整确定风险级别"""
        if adjustment > 1.1:
            return "low"  # 可放大仓位，风险低
        elif adjustment < 0.7:
            return "high"  # 需减小仓位，风险高
        else:
            return "medium"

    def _form_final_decision(
        self,
        context: AnalysisContext,
        trade_signal: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        形成最终决策

        综合交易信号和风险评估，输出最终交易决策

        Args:
            context: 分析上下文
            trade_signal: 交易信号
            risk_assessment: 风险评估

        Returns:
            最终决策
        """
        ticker = context.get(DataLayer.CONTEXT, "ticker")

        # 获取原始信号
        original_action = trade_signal.get("action", "HOLD")
        original_position = trade_signal.get("position_size", 0.0)
        confidence = trade_signal.get("confidence", 0.5)

        # 应用风险调整
        adjustment = risk_assessment.get("avg_position_adjustment", 1.0)
        adjusted_position = original_position * adjustment

        # 限制仓位范围
        adjusted_position = max(0.0, min(1.0, adjusted_position))

        # 如果调整后仓位太小，改为 HOLD
        if adjusted_position < 0.1 and original_action != "HOLD":
            final_action = "HOLD"
            adjusted_position = 0.0
        else:
            final_action = original_action

        return {
            "ticker": ticker,
            "action": final_action,
            "position_size": adjusted_position,
            "original_position": original_position,
            "position_adjustment": adjustment,
            "confidence": confidence,
            "risk_level": risk_assessment.get("overall_risk_level", "medium"),
            "rationale": trade_signal.get("rationale", ""),
            "risk_summary": risk_assessment.get("risk_opinions", {}),
        }

