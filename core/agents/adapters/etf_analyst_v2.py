"""
ETF 分析师智能体 v2.0

分析 ETF 净值、规模、费率、跟踪误差等（ETF 无 PE/PB/ROE）
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from ..base import BaseAgent
from ..config import AgentConfig, AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class EtfAnalystAgentV2(BaseAgent):
    """
    ETF 分析师智能体 v2.0

    分析 ETF 的净值、规模、费率、跟踪指数、跟踪误差等。
    ETF 无 PE/PB/ROE，使用专用指标。
    """

    metadata = AgentMetadata(
        id="etf_analyst_v2",
        name="ETF 分析师 v2.0",
        description="分析 ETF 净值、规模、费率、跟踪误差等。ETF 无 PE/PB/ROE。",
        category=AgentCategory.ANALYST,
        license_tier=LicenseTier.FREE,
        default_tools=["get_etf_fundamentals"],
        version="2.0.0",
        inputs=[
            AgentInput(name="ticker", type="string", description="ETF 代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="fundamentals_report", type="string", description="ETF 分析报告"),
        ],
        requires_tools=True,
        output_field="fundamentals_report",
        report_label="【ETF 分析 v2】",
        workflow_stage="analyst",
        growth_role="extractor",
        growth_outputs=["fundamentals_report"],
        memory_scope_hint="object_tracking",
        review_level="auto_pending",
        growth_source_type="analysis_report",
    )

    def __init__(
        self,
        config: Optional[Any] = None,
        llm: Optional[BaseChatModel] = None,
        tool_ids: Optional[list] = None
    ):
        super().__init__(config=config, llm=llm, tool_ids=tool_ids)
        if tool_ids is None and llm is not None:
            tool_ids = self.load_tools_from_config()
            if tool_ids:
                self._load_tools_v2(tool_ids)

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        ticker = state.get("ticker") or state.get("company_of_interest")
        trade_date = state.get("trade_date") or state.get("end_date") or state.get("analysis_date")

        if not ticker:
            raise ValueError("缺少必需参数: ticker")

        logger.info(f"开始 ETF 分析: {ticker} (日期: {trade_date})")

        system_prompt = self._build_system_prompt(state)
        user_prompt = self._build_user_prompt(ticker, trade_date, state)

        system_prompt = self._apply_global_trading_advice_guard(system_prompt)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        if self._llm and self.tools:
            analysis = self.invoke_with_tools(messages, analysis_prompt=self._build_analysis_prompt(ticker))
        else:
            logger.warning("没有配置 LLM 或工具，返回模拟结果")
            analysis = self._generate_mock_report(ticker, trade_date)

        return {"fundamentals_report": analysis}

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        template_variables = {}
        if state:
            template_variables["ticker"] = state.get("ticker", "")
            template_variables["company_name"] = state.get("company_name", "")
            analysis_date = state.get("analysis_date") or state.get("trade_date")
            if analysis_date:
                template_variables["current_date"] = str(analysis_date)[:10]
                template_variables["analysis_date"] = str(analysis_date)[:10]

        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="etf_analyst_v2",
            variables=template_variables,
            state=state or {},
            context=state.get("context") if state else None,
            fallback_prompt=None,
            prompt_type="system"
        )

        if prompt:
            return prompt

        return """你是专业的 ETF 分析师。ETF 是跟踪指数的基金，没有 PE/PB/ROE 等个股估值指标。

你的任务：
1. 调用 get_etf_fundamentals 获取 ETF 数据
2. 分析净值、规模、跟踪指数、涨跌幅
3. 评估跟踪误差、流动性风险
4. 提供研究观察

禁止使用 PE/PB/ROE 分析 ETF。"""

    def _build_user_prompt(self, ticker: str, trade_date: str, state: Dict[str, Any] = None) -> str:
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="etf_analyst_v2",
            variables={"ticker": ticker, "analysis_date": trade_date or "", "current_date": trade_date or ""},
            state=state or {},
            context=state.get("context") if state else None,
            fallback_prompt=None,
            prompt_type="user"
        )
        if prompt:
            return prompt
        return f"请分析 ETF {ticker}。分析日期：{trade_date}。请调用工具获取数据后生成报告。"

    def _build_analysis_prompt(self, ticker: str) -> str:
        return f"""基于获取的数据，生成 {ticker} 的 ETF 分析报告，包括：
1. 净值与规模
2. 跟踪指数表现
3. 流动性评估
4. 研究观察
禁止使用 PE/PB/ROE。"""

    def _generate_mock_report(self, ticker: str, trade_date: str) -> str:
        return f"""ETF 分析报告（模拟）

代码: {ticker}
日期: {trade_date}

净值走势：待获取数据
规模：待获取数据
跟踪指数：待获取数据
建议：请配置数据源后重新分析"""
