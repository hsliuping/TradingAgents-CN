"""
预定义工作流模板
"""

from .default_workflow import DEFAULT_WORKFLOW
from .simple_workflow import SIMPLE_WORKFLOW
from .position_analysis_workflow import POSITION_ANALYSIS_WORKFLOW
from .position_analysis_workflow_v2 import POSITION_ANALYSIS_WORKFLOW_V2
from .v2_stock_analysis_workflow import V2_STOCK_ANALYSIS_WORKFLOW
from .trade_review_workflow import TRADE_REVIEW_WORKFLOW
from .trade_review_workflow_v2 import TRADE_REVIEW_WORKFLOW_V2
from .single_agent_workflow import SingleAgentWorkflow

__all__ = [
    "DEFAULT_WORKFLOW",
    "SIMPLE_WORKFLOW",
    "TRADE_REVIEW_WORKFLOW",
    "TRADE_REVIEW_WORKFLOW_V2",
    "POSITION_ANALYSIS_WORKFLOW",
    "POSITION_ANALYSIS_WORKFLOW_V2",
    "V2_STOCK_ANALYSIS_WORKFLOW",
    "SingleAgentWorkflow",
]

