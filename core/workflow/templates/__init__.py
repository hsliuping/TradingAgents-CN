"""
预定义工作流模板（只保留 v2 版本）
"""

from .blank_workflow import BLANK_WORKFLOW
from .position_analysis_workflow_v2 import POSITION_ANALYSIS_WORKFLOW_V2
from .v2_stock_analysis_workflow import V2_STOCK_ANALYSIS_WORKFLOW
from .v2_etf_analysis_workflow import V2_ETF_ANALYSIS_WORKFLOW
from .trade_review_workflow_v2 import TRADE_REVIEW_WORKFLOW_V2
from .single_agent_workflow import SingleAgentWorkflow

__all__ = [
    "BLANK_WORKFLOW",
    "TRADE_REVIEW_WORKFLOW_V2",
    "POSITION_ANALYSIS_WORKFLOW_V2",
    "V2_STOCK_ANALYSIS_WORKFLOW",
    "V2_ETF_ANALYSIS_WORKFLOW",
    "SingleAgentWorkflow",
]
