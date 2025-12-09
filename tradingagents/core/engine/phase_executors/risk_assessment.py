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
        risk_profiles: Optional[List[str]] = None,
        debate_rounds: int = 1,
        memory_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化风险评估阶段

        Args:
            llm_provider: LLM 提供者
            config: 阶段配置
            risk_profiles: 风控类型列表，默认全部
            debate_rounds: 辩论轮数
            memory_config: Memory 配置
        """
        super().__init__(llm_provider, config)
        self.risk_profiles = risk_profiles or ["risky", "safe", "neutral"]
        self.debate_rounds = debate_rounds
        self.memory_config = memory_config or {}

        # Agent 缓存
        self._risky_analyst = None
        self._safe_analyst = None
        self._neutral_analyst = None
        self._risk_manager = None
    
    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行风险评估阶段
        """
        self.log_start()

        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.info(f"⚖️ [{self.phase_name}] 风险评估: {ticker}")

        outputs = {
            "ticker": ticker,
            "risk_reports": [],
            "final_decision": None
        }

        # 获取交易信号和交易员计划
        trade_signal = context.get(DataLayer.DECISIONS, "trade_signal")
        trader_plan = context.get(DataLayer.DECISIONS, "trader_investment_plan")
        investment_plan = context.get(DataLayer.DECISIONS, "investment_plan")

        if trade_signal is None and trader_plan is None:
            logger.warning(f"⚠️ [{self.phase_name}] 未找到交易信号，跳过风险评估")
            self.log_end(outputs)
            return outputs

        # 构建初始状态
        state = self._build_initial_state(context, trader_plan or str(investment_plan))

        # 执行多轮风控辩论
        for round_num in range(self.debate_rounds):
            logger.info(f"💬 [{self.phase_name}] 风控辩论第 {round_num + 1}/{self.debate_rounds} 轮")

            # 激进风控发言
            if "risky" in self.risk_profiles:
                state = self._run_risky_analyst(state)
                outputs["risk_reports"].append("risky")

            # 稳健风控发言
            if "safe" in self.risk_profiles:
                state = self._run_safe_analyst(state)
                outputs["risk_reports"].append("safe")

            # 中性风控发言
            if "neutral" in self.risk_profiles:
                state = self._run_neutral_analyst(state)
                outputs["risk_reports"].append("neutral")

        # 风控经理总结
        state = self._run_risk_manager(state)

        # 保存结果
        risk_debate_state = state.get("risk_debate_state", {})
        final_trade_decision = state.get("final_trade_decision", "")

        context.set(DataLayer.DECISIONS, "risk_debate_state", risk_debate_state, source="risk_assessment")
        context.set(DataLayer.DECISIONS, "final_trade_decision", final_trade_decision, source="risk_manager")

        # 生成最终决策
        final_decision = self._form_final_decision_from_text(context, trade_signal, final_trade_decision)
        context.set(DataLayer.DECISIONS, "final_decision", final_decision, source="risk_manager")
        outputs["final_decision"] = final_decision.get("action")

        logger.info(f"📝 [{self.phase_name}] 最终决策: {final_decision.get('action')}")

        self.log_end(outputs)
        return outputs

    def _build_initial_state(self, context: AnalysisContext, trader_plan: str) -> Dict[str, Any]:
        """构建初始状态"""
        ticker = context.get(DataLayer.CONTEXT, "ticker") or ""
        trade_date = context.get(DataLayer.CONTEXT, "trade_date") or ""

        return {
            "company_of_interest": ticker,
            "trade_date": trade_date,
            "trader_investment_plan": trader_plan,
            "investment_plan": context.get(DataLayer.DECISIONS, "investment_plan") or "",
            "market_report": context.get(DataLayer.REPORTS, "market_report") or "",
            "sentiment_report": context.get(DataLayer.REPORTS, "sentiment_report") or "",
            "news_report": context.get(DataLayer.REPORTS, "news_report") or "",
            "fundamentals_report": context.get(DataLayer.REPORTS, "fundamentals_report") or "",
            "risk_debate_state": {
                "history": "",
                "risky_history": "",
                "safe_history": "",
                "neutral_history": "",
                "current_risky_response": "",
                "current_safe_response": "",
                "current_neutral_response": "",
                "count": 0,
                "judge_decision": ""
            }
        }

    def _get_risky_analyst(self):
        """获取或创建激进风控"""
        if self._risky_analyst is None:
            try:
                from tradingagents.agents.risk_mgmt.aggresive_debator import create_risky_debator
                self._risky_analyst = create_risky_debator(self.llm_provider)
                logger.debug("🔥 [RiskAssessment] 创建 RiskyAnalyst")
            except Exception as e:
                logger.error(f"❌ [RiskAssessment] 创建 RiskyAnalyst 失败: {e}")
        return self._risky_analyst

    def _get_safe_analyst(self):
        """获取或创建稳健风控"""
        if self._safe_analyst is None:
            try:
                from tradingagents.agents.risk_mgmt.conservative_debator import create_safe_debator
                self._safe_analyst = create_safe_debator(self.llm_provider)
                logger.debug("🛡️ [RiskAssessment] 创建 SafeAnalyst")
            except Exception as e:
                logger.error(f"❌ [RiskAssessment] 创建 SafeAnalyst 失败: {e}")
        return self._safe_analyst

    def _get_neutral_analyst(self):
        """获取或创建中性风控"""
        if self._neutral_analyst is None:
            try:
                from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
                self._neutral_analyst = create_neutral_debator(self.llm_provider)
                logger.debug("⚖️ [RiskAssessment] 创建 NeutralAnalyst")
            except Exception as e:
                logger.error(f"❌ [RiskAssessment] 创建 NeutralAnalyst 失败: {e}")
        return self._neutral_analyst

    def _get_risk_manager(self):
        """获取或创建风控经理"""
        if self._risk_manager is None:
            try:
                from tradingagents.agents.managers.risk_manager import create_risk_manager
                memory = self.memory_config.get("risk_memory")
                self._risk_manager = create_risk_manager(self.llm_provider, memory)
                logger.debug("👔 [RiskAssessment] 创建 RiskManager")
            except Exception as e:
                logger.error(f"❌ [RiskAssessment] 创建 RiskManager 失败: {e}")
        return self._risk_manager

    def _run_risky_analyst(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行激进风控"""
        agent = self._get_risky_analyst()
        if agent:
            try:
                result = agent(state)
                if "risk_debate_state" in result:
                    state["risk_debate_state"] = result["risk_debate_state"]
                logger.info("🔥 [激进风控] 发言完成")
            except Exception as e:
                logger.error(f"❌ [激进风控] 执行失败: {e}")
        return state

    def _run_safe_analyst(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行稳健风控"""
        agent = self._get_safe_analyst()
        if agent:
            try:
                result = agent(state)
                if "risk_debate_state" in result:
                    state["risk_debate_state"] = result["risk_debate_state"]
                logger.info("🛡️ [稳健风控] 发言完成")
            except Exception as e:
                logger.error(f"❌ [稳健风控] 执行失败: {e}")
        return state

    def _run_neutral_analyst(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行中性风控"""
        agent = self._get_neutral_analyst()
        if agent:
            try:
                result = agent(state)
                if "risk_debate_state" in result:
                    state["risk_debate_state"] = result["risk_debate_state"]
                logger.info("⚖️ [中性风控] 发言完成")
            except Exception as e:
                logger.error(f"❌ [中性风控] 执行失败: {e}")
        return state

    def _run_risk_manager(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行风控经理总结"""
        agent = self._get_risk_manager()
        if agent:
            try:
                result = agent(state)
                if "risk_debate_state" in result:
                    state["risk_debate_state"] = result["risk_debate_state"]
                if "final_trade_decision" in result:
                    state["final_trade_decision"] = result["final_trade_decision"]
                logger.info("👔 [风控经理] 最终决策生成完成")
            except Exception as e:
                logger.error(f"❌ [风控经理] 执行失败: {e}")
                state["final_trade_decision"] = "[错误] 风控决策生成失败"
        return state

    def _form_final_decision_from_text(
        self,
        context: AnalysisContext,
        trade_signal: Optional[Dict[str, Any]],
        final_text: str
    ) -> Dict[str, Any]:
        """从风控文本生成最终决策"""
        ticker = context.get(DataLayer.CONTEXT, "ticker")

        # 解析建议
        action, confidence = self._parse_action_from_text(final_text)

        # 如果有原始交易信号，合并信息
        if trade_signal and isinstance(trade_signal, dict):
            original_position = trade_signal.get("position_size", 0.0)
            original_rationale = trade_signal.get("rationale", "")
        else:
            original_position = 0.5
            original_rationale = ""

        # 根据风控建议调整仓位
        if action == "HOLD":
            position_size = 0.0
        else:
            position_size = min(confidence, 1.0) * original_position if original_position > 0 else confidence * 0.5

        return {
            "ticker": ticker,
            "action": action,
            "position_size": position_size,
            "confidence": confidence,
            "risk_level": self._determine_risk_level_from_text(final_text),
            "rationale": final_text[:500] if len(final_text) > 500 else final_text,
            "original_rationale": original_rationale[:200] if original_rationale else "",
        }

    def _parse_action_from_text(self, text: str) -> tuple:
        """从文本解析交易动作"""
        text_lower = text.lower()

        buy_keywords = ["买入", "增持", "看多", "建议买入", "buy", "bullish"]
        sell_keywords = ["卖出", "减持", "看空", "建议卖出", "sell", "bearish"]
        hold_keywords = ["持有", "观望", "hold", "neutral", "中性"]

        buy_score = sum(1 for kw in buy_keywords if kw in text_lower)
        sell_score = sum(1 for kw in sell_keywords if kw in text_lower)
        hold_score = sum(1 for kw in hold_keywords if kw in text_lower)

        if buy_score > sell_score and buy_score > hold_score:
            return "BUY", min(0.5 + buy_score * 0.1, 0.9)
        elif sell_score > buy_score and sell_score > hold_score:
            return "SELL", min(0.5 + sell_score * 0.1, 0.9)
        else:
            return "HOLD", 0.5

    def _determine_risk_level_from_text(self, text: str) -> str:
        """从文本判断风险级别"""
        text_lower = text.lower()

        high_risk_keywords = ["高风险", "风险较大", "谨慎", "危险", "high risk"]
        low_risk_keywords = ["低风险", "安全", "稳健", "low risk"]

        high_score = sum(1 for kw in high_risk_keywords if kw in text_lower)
        low_score = sum(1 for kw in low_risk_keywords if kw in text_lower)

        if high_score > low_score:
            return "high"
        elif low_score > high_score:
            return "low"
        else:
            return "medium"
    
