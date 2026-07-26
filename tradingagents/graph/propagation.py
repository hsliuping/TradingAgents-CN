# TradingAgents/graph/propagation.py

from typing import Dict, Any

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(
        self,
        company_name: str,
        trade_date: str,
        analysis_id: str | None = None,
        snapshot_id: str | None = None,
        data_quality_status: str | None = None,
        market: str | None = None,
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph."""
        from langchain_core.messages import HumanMessage

        if snapshot_id:
            if data_quality_status not in {"PASS", "WARN"}:
                raise ValueError(
                    "snapshot-backed analysis requires DataQuality PASS or WARN"
                )
            legacy_analysis = False
        else:
            if data_quality_status is not None:
                raise ValueError(
                    "data_quality_status cannot be supplied without snapshot_id"
                )
            legacy_analysis = True

        # 🔥 修复：创建明确的分析请求消息，而不是只传递股票代码
        # 这样可以确保所有LLM（包括DeepSeek）都能理解任务
        snapshot_context = (
            f"，证据快照为 {snapshot_id}，数据质量为 {data_quality_status}"
            if snapshot_id
            else "；这是没有 EvidenceSnapshot 的旧人工分析兼容路径"
        )
        analysis_request = (
            f"请对股票 {company_name} 进行全面分析，交易日期为 {trade_date}"
            f"{snapshot_context}。"
        )

        return {
            "messages": [HumanMessage(content=analysis_request)],
            "analysis_id": analysis_id or f"{company_name}:{trade_date}",
            "snapshot_id": snapshot_id,
            "data_quality_status": data_quality_status,
            "market": market,
            "legacy_analysis": legacy_analysis,
            "automated_execution_allowed": False,
            "company_of_interest": company_name,
            "trade_date": str(trade_date),
            "investment_debate_state": InvestDebateState(
                {"history": "", "current_response": "", "count": 0}
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "history": "",
                    "current_risky_response": "",
                    "current_safe_response": "",
                    "current_neutral_response": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",
            "normal_trade_plan": None,
            "top_review_decision": None,
            "decision_error": None,
            "normal_model_meta": None,
            "top_model_meta": None,
        }

    def get_graph_args(self, use_progress_callback: bool = False) -> Dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            use_progress_callback: If True, use 'updates' mode for node-level progress tracking.
                                  If False, use 'values' mode for complete state updates.
        """
        # 使用 'updates' 模式可以获取节点级别的更新，用于进度跟踪
        # 使用 'values' 模式可以获取完整的状态更新
        stream_mode = "updates" if use_progress_callback else "values"

        return {
            "stream_mode": stream_mode,
            "config": {"recursion_limit": self.max_recur_limit},
        }
