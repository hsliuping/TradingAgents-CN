#!/usr/bin/env python3
"""
TradingAgents-CN 核心交易智能体库

这是一个基于多智能体的股票研究系统，支持A股、港股和美股的综合研究分析。
"""

__version__ = "1.0.0"
__author__ = "TradingAgents-CN"
__description__ = "TradingAgents-CN - Multi-agent stock research system for Chinese markets"

# 导入核心模块
try:
    from .config import config_manager
    from .utils import logging_manager
except ImportError:
    # 如果导入失败，不影响模块的基本功能
    pass

__all__ = [
    "__version__",
    "__author__", 
    "__description__"
]