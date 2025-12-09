# tradingagents/core/engine/phase_executors/research_debate.py
"""
研究辩论阶段执行器

执行多空研究和辩论：
1. BullResearcher (看多研究员) - 从乐观角度分析
2. BearResearcher (看空研究员) - 从谨慎角度分析
3. ResearchManager (研究经理) - 主持辩论，形成投资建议
"""

from typing import Any, Dict, Optional

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
        debate_rounds: int = 1,
        integrator: Any = None,
        memory_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化研究辩论阶段

        Args:
            llm_provider: LLM 提供者
            config: 阶段配置
            debate_rounds: 辩论轮数
            integrator: AgentIntegrator 实例
            memory_config: Memory 配置字典
        """
        super().__init__(llm_provider, config)
        self.debate_rounds = debate_rounds
        self.integrator = integrator
        self.memory_config = memory_config or {}

        # 研究员 Agent 缓存
        self._bull_researcher = None
        self._bear_researcher = None
        self._research_manager = None

    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行研究辩论阶段
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
        logger.info(f"📋 [{self.phase_name}] 收集到 {len(analyst_reports)} 份分析报告")

        # 2. 构建初始状态 (兼容现有 Agent)
        state = self._build_initial_state(context, analyst_reports)

        # 3. 执行多轮辩论
        for round_num in range(self.debate_rounds):
            logger.info(f"💬 [{self.phase_name}] 辩论第 {round_num + 1}/{self.debate_rounds} 轮")

            # 看多研究员发言
            state = self._run_bull_researcher(state)
            bull_argument = state["investment_debate_state"].get("current_response", "")

            # 看空研究员发言
            state = self._run_bear_researcher(state)
            bear_argument = state["investment_debate_state"].get("current_response", "")

            logger.info(f"📈 [多头] 论点长度: {len(bull_argument)} 字符")
            logger.info(f"📉 [空头] 论点长度: {len(bear_argument)} 字符")

        # 4. 研究经理总结并形成投资建议
        state = self._run_research_manager(state)
        investment_plan = state.get("investment_plan", "")

        # 5. 保存结果到 Context
        bull_history = state["investment_debate_state"].get("bull_history", "")
        bear_history = state["investment_debate_state"].get("bear_history", "")

        context.set(DataLayer.REPORTS, "bull_report", bull_history, source="bull_researcher")
        context.set(DataLayer.REPORTS, "bear_report", bear_history, source="bear_researcher")
        context.set(DataLayer.DECISIONS, "investment_plan", investment_plan, source="research_manager")
        context.set(DataLayer.DECISIONS, "investment_debate_state",
                   state["investment_debate_state"], source="research_debate")

        outputs["bull_report"] = "generated" if bull_history else None
        outputs["bear_report"] = "generated" if bear_history else None
        outputs["investment_plan"] = "generated" if investment_plan else None

        logger.info(f"📝 [{self.phase_name}] 投资建议长度: {len(investment_plan)} 字符")

        self.log_end(outputs)
        return outputs

    def _collect_analyst_reports(self, context: AnalysisContext) -> Dict[str, str]:
        """收集所有分析师报告"""
        # 从配置动态获取报告字段
        try:
            from core.agents.config import BUILTIN_AGENTS, AgentCategory
            report_fields = []
            for agent_id, metadata in BUILTIN_AGENTS.items():
                if metadata.category == AgentCategory.ANALYST:
                    if hasattr(metadata, 'output_field') and metadata.output_field:
                        report_fields.append(metadata.output_field)
        except ImportError:
            # 回退到硬编码
            report_fields = [
                "market_report", "news_report", "sentiment_report",
                "fundamentals_report", "sector_report", "index_report",
            ]

        reports = {}
        for field in report_fields:
            report = context.get(DataLayer.REPORTS, field)
            if report:
                reports[field] = report

        return reports

    def _build_initial_state(
        self,
        context: AnalysisContext,
        analyst_reports: Dict[str, str]
    ) -> Dict[str, Any]:
        """构建兼容现有 Agent 的初始状态"""
        ticker = context.get(DataLayer.CONTEXT, "ticker") or ""
        trade_date = context.get(DataLayer.CONTEXT, "trade_date") or ""

        # 构建状态
        state = {
            "company_of_interest": ticker,
            "trade_date": trade_date,
            "messages": [],
            # 投资辩论状态
            "investment_debate_state": {
                "history": "",
                "bull_history": "",
                "bear_history": "",
                "current_response": "",
                "count": 0,
                "judge_decision": ""
            }
        }

        # 添加分析师报告
        for field, report in analyst_reports.items():
            state[field] = report

        return state

    def _get_bull_researcher(self):
        """获取或创建看多研究员"""
        if self._bull_researcher is None:
            try:
                from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
                memory = self.memory_config.get("bull_memory")
                self._bull_researcher = create_bull_researcher(self.llm_provider, memory)
                logger.debug("🐂 [ResearchDebate] 创建 BullResearcher Agent")
            except Exception as e:
                logger.error(f"❌ [ResearchDebate] 创建 BullResearcher 失败: {e}")
        return self._bull_researcher

    def _get_bear_researcher(self):
        """获取或创建看空研究员"""
        if self._bear_researcher is None:
            try:
                from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
                memory = self.memory_config.get("bear_memory")
                self._bear_researcher = create_bear_researcher(self.llm_provider, memory)
                logger.debug("🐻 [ResearchDebate] 创建 BearResearcher Agent")
            except Exception as e:
                logger.error(f"❌ [ResearchDebate] 创建 BearResearcher 失败: {e}")
        return self._bear_researcher

    def _get_research_manager(self):
        """获取或创建研究经理"""
        if self._research_manager is None:
            try:
                from tradingagents.agents.managers.research_manager import create_research_manager
                memory = self.memory_config.get("invest_judge_memory")
                self._research_manager = create_research_manager(self.llm_provider, memory)
                logger.debug("👔 [ResearchDebate] 创建 ResearchManager Agent")
            except Exception as e:
                logger.error(f"❌ [ResearchDebate] 创建 ResearchManager 失败: {e}")
        return self._research_manager

    def _run_bull_researcher(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行看多研究"""
        agent = self._get_bull_researcher()
        if agent:
            try:
                result = agent(state)
                # 合并结果到状态
                if "investment_debate_state" in result:
                    state["investment_debate_state"] = result["investment_debate_state"]
                logger.info(f"🐂 [多头研究员] 发言完成")
            except Exception as e:
                logger.error(f"❌ [多头研究员] 执行失败: {e}")
        else:
            # 桩实现
            logger.warning("⚠️ [ResearchDebate] BullResearcher 不可用，使用桩实现")
            state["investment_debate_state"]["bull_history"] = "[桩] 看多分析报告"
            state["investment_debate_state"]["count"] += 1
        return state

    def _run_bear_researcher(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行看空研究"""
        agent = self._get_bear_researcher()
        if agent:
            try:
                result = agent(state)
                if "investment_debate_state" in result:
                    state["investment_debate_state"] = result["investment_debate_state"]
                logger.info(f"🐻 [空头研究员] 发言完成")
            except Exception as e:
                logger.error(f"❌ [空头研究员] 执行失败: {e}")
        else:
            logger.warning("⚠️ [ResearchDebate] BearResearcher 不可用，使用桩实现")
            state["investment_debate_state"]["bear_history"] = "[桩] 看空分析报告"
            state["investment_debate_state"]["count"] += 1
        return state

    def _run_research_manager(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行研究经理总结"""
        agent = self._get_research_manager()
        if agent:
            try:
                result = agent(state)
                if "investment_debate_state" in result:
                    state["investment_debate_state"] = result["investment_debate_state"]
                if "investment_plan" in result:
                    state["investment_plan"] = result["investment_plan"]
                logger.info(f"👔 [研究经理] 投资建议生成完成")
            except Exception as e:
                logger.error(f"❌ [研究经理] 执行失败: {e}")
                state["investment_plan"] = "[错误] 投资建议生成失败"
        else:
            logger.warning("⚠️ [ResearchDebate] ResearchManager 不可用，使用桩实现")
            state["investment_plan"] = "[桩] 投资建议"
        return state

