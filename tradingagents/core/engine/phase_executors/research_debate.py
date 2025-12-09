# tradingagents/core/engine/phase_executors/research_debate.py
"""
研究辩论阶段执行器

执行多空研究和辩论：
1. BullResearcher (看多研究员) - 从乐观角度分析
2. BearResearcher (看空研究员) - 从谨慎角度分析
3. ResearchManager (研究经理) - 主持辩论，形成投资建议
"""

from typing import Any, Dict, List, Optional

from tradingagents.utils.logging_init import get_logger

from ..analysis_context import AnalysisContext
from ..data_access_manager import DataAccessManager
from ..data_contract import DataLayer
from .base import PhaseExecutor

logger = get_logger("default")


class ResearchDebatePhase(PhaseExecutor):
    """
    研究辩论阶段执行器
    
    协调多空研究员进行辩论，
    由研究经理综合形成投资建议
    """
    
    phase_name = "ResearchDebatePhase"
    
    def __init__(
        self,
        llm_provider: Any = None,
        config: Optional[Dict[str, Any]] = None,
        debate_rounds: int = 1
    ):
        """
        初始化研究辩论阶段
        
        Args:
            llm_provider: LLM 提供者
            config: 阶段配置
            debate_rounds: 辩论轮数
        """
        super().__init__(llm_provider, config)
        self.debate_rounds = debate_rounds
    
    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行研究辩论阶段
        
        Args:
            context: 分析上下文
            data_manager: 数据访问管理器
            
        Returns:
            辩论结果摘要
        """
        self.log_start()
        
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.info(f"🔬 [{self.phase_name}] 研究辩论: {ticker}")
        
        outputs = {
            "ticker": ticker,
            "debate_rounds": self.debate_rounds,
            "bull_report": None,
            "bear_report": None,
            "investment_plan": None
        }
        
        # 1. 收集分析师报告
        analyst_reports = self._collect_analyst_reports(context)
        logger.debug(f"📋 [{self.phase_name}] 收集到 {len(analyst_reports)} 份报告")
        
        # 2. 执行看多研究
        bull_report = self._run_bull_researcher(context, analyst_reports)
        context.set(DataLayer.REPORTS, "bull_report", bull_report, source="bull_researcher")
        outputs["bull_report"] = "generated"
        
        # 3. 执行看空研究
        bear_report = self._run_bear_researcher(context, analyst_reports)
        context.set(DataLayer.REPORTS, "bear_report", bear_report, source="bear_researcher")
        outputs["bear_report"] = "generated"
        
        # 4. 执行辩论（可多轮）
        for round_num in range(self.debate_rounds):
            logger.info(f"💬 [{self.phase_name}] 辩论第 {round_num + 1} 轮")
            debate_result = self._run_debate_round(context, bull_report, bear_report, round_num)
            context.set(
                DataLayer.DECISIONS, 
                "investment_debate", 
                debate_result, 
                source="research_manager"
            )
        
        # 5. 形成投资建议
        investment_plan = self._form_investment_plan(context, bull_report, bear_report)
        context.set(DataLayer.DECISIONS, "investment_plan", investment_plan, source="research_manager")
        outputs["investment_plan"] = "generated"
        
        self.log_end(outputs)
        return outputs
    
    def _collect_analyst_reports(self, context: AnalysisContext) -> Dict[str, str]:
        """收集所有分析师报告"""
        report_fields = [
            "market_report",
            "news_report",
            "sentiment_report",
            "fundamentals_report",
            "sector_report",
            "index_report",
        ]
        
        reports = {}
        for field in report_fields:
            report = context.get(DataLayer.REPORTS, field)
            if report:
                reports[field] = report
        
        return reports
    
    def _run_bull_researcher(
        self,
        context: AnalysisContext,
        analyst_reports: Dict[str, str]
    ) -> str:
        """
        执行看多研究
        
        TODO: 集成实际的 BullResearcher Agent
        """
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.info(f"📈 [{self.phase_name}] 执行看多研究: {ticker}")
        
        # 桩实现
        return f"[BullResearcher] {ticker} 看多分析报告占位"
    
    def _run_bear_researcher(
        self,
        context: AnalysisContext,
        analyst_reports: Dict[str, str]
    ) -> str:
        """
        执行看空研究

        TODO: 集成实际的 BearResearcher Agent
        """
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.info(f"📉 [{self.phase_name}] 执行看空研究: {ticker}")

        # 桩实现
        return f"[BearResearcher] {ticker} 看空分析报告占位"

    def _run_debate_round(
        self,
        context: AnalysisContext,
        bull_report: str,
        bear_report: str,
        round_num: int
    ) -> Dict[str, Any]:
        """
        执行一轮辩论

        TODO: 集成实际的辩论逻辑
        """
        ticker = context.get(DataLayer.CONTEXT, "ticker")

        return {
            "round": round_num + 1,
            "ticker": ticker,
            "bull_arguments": f"看多论点 - 第 {round_num + 1} 轮",
            "bear_arguments": f"看空论点 - 第 {round_num + 1} 轮",
            "conclusion": "辩论结论占位"
        }

    def _form_investment_plan(
        self,
        context: AnalysisContext,
        bull_report: str,
        bear_report: str
    ) -> Dict[str, Any]:
        """
        形成投资建议

        TODO: 集成实际的投资建议生成逻辑
        """
        ticker = context.get(DataLayer.CONTEXT, "ticker")

        return {
            "ticker": ticker,
            "recommendation": "hold",  # buy/sell/hold
            "confidence": 0.5,
            "rationale": "投资建议占位",
            "risk_factors": [],
            "opportunities": []
        }

