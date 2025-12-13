"""
预定义工作流模板
"""

from .default_workflow import DEFAULT_WORKFLOW
from .simple_workflow import SIMPLE_WORKFLOW
from .trade_review_workflow import TRADE_REVIEW_WORKFLOW
from .position_analysis_workflow import POSITION_ANALYSIS_WORKFLOW

__all__ = [
    "DEFAULT_WORKFLOW",
    "SIMPLE_WORKFLOW",
    "TRADE_REVIEW_WORKFLOW",
    "POSITION_ANALYSIS_WORKFLOW",
]

