"""
Backtest System Package
智能回测系统包
"""

__version__ = "1.0.0"
__author__ = "TradingAgents-CN"

from .core.backtest_engine import BacktestEngine
from .core.portfolio_manager import PortfolioManager
from .agents.position_manager import PositionManager

__all__ = [
    "BacktestEngine",
    "PortfolioManager",
    "PositionManager"
]