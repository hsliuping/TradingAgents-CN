"""
对话驱动回测 - 核心模块
engine_client: HTTP 调用 Backtrader 服务
strategy_analyzer: LLM 策略可行性分析
strategy_generator: LLM 策略 DSL 生成
result_evaluator: LLM 回测结果评估和策略优化
iterative_optimizer: 迭代优化流程控制
"""
from .engine_client import BacktestEngineClient
from .strategy_analyzer import analyze_strategy_feasibility
from .strategy_generator import generate_strategy_dsl
from .result_evaluator import evaluate_backtest_result, optimize_strategy_based_on_evaluation
from .iterative_optimizer import IterativeOptimizer

__all__ = [
    "BacktestEngineClient",
    "analyze_strategy_feasibility",
    "generate_strategy_dsl",
    "evaluate_backtest_result",
    "optimize_strategy_based_on_evaluation",
    "IterativeOptimizer",
]
