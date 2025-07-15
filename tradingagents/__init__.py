"""TradingAgents - Multi-Agents LLM Financial Trading Framework."""

__version__ = "0.1.0"
__author__ = "TradingAgents Team"
__email__ = "yijia.xiao@cs.ucla.edu"

# Import main components
from .graph import TradingAgentsGraph
from .default_config import DEFAULT_CONFIG

__all__ = [
    "TradingAgentsGraph",
    "DEFAULT_CONFIG",
    "__version__",
]