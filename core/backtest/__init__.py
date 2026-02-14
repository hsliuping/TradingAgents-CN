"""
对话驱动回测 - 核心模块
engine_client: HTTP 调用 Backtrader 服务
strategy_analyzer: LLM 策略可行性分析
strategy_generator: LLM 策略 DSL 生成
"""
from .engine_client import BacktestEngineClient
from .strategy_analyzer import analyze_strategy_feasibility
from .strategy_generator import generate_strategy_dsl

__all__ = [
    "BacktestEngineClient",
    "analyze_strategy_feasibility",
    "generate_strategy_dsl",
]
