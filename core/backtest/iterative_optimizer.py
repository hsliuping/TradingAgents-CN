"""
迭代优化器 - 实现 OpenClaw 风格的策略迭代优化
执行回测 → 评估结果 → 优化策略 → 再次回测 → 直到满意
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from .engine_client import BacktestEngineClient
from .result_evaluator import (
    evaluate_backtest_result,
    optimize_strategy_based_on_evaluation,
    should_optimize_strategy,
)
from .dsl_evaluator import evaluate_strategy_python_full

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3  # 最大迭代次数，避免无限循环


class IterationResult:
    """单次迭代结果"""
    def __init__(
        self,
        iteration: int,
        strategy: Dict[str, Any],
        backtest_result: Dict[str, Any],
        evaluation: Dict[str, Any],
        optimization_applied: bool = False,
    ):
        self.iteration = iteration
        self.strategy = strategy
        self.backtest_result = backtest_result
        self.evaluation = evaluation
        self.optimization_applied = optimization_applied


class IterativeOptimizer:
    """迭代优化器"""
    
    def __init__(self, engine_client: Optional[BacktestEngineClient] = None):
        self.engine_client = engine_client or BacktestEngineClient()
        self.iterations: List[IterationResult] = []
    
    async def optimize_strategy(
        self,
        user_description: str,
        initial_strategy: Dict[str, Any],
        max_iterations: int = MAX_ITERATIONS,
    ) -> Dict[str, Any]:
        """
        迭代优化策略直到满意或达到最大迭代次数
        
        Args:
            user_description: 用户原始需求描述
            initial_strategy: 初始策略（code + config）
            max_iterations: 最大迭代次数
            
        Returns:
            {
                "final_strategy": {...},
                "final_result": {...},
                "final_evaluation": {...},
                "iterations": [...],
                "optimization_summary": "优化过程总结"
            }
        """
        self.iterations = []
        current_strategy = initial_strategy
        
        logger.info("开始迭代优化，最大迭代次数: %d", max_iterations)
        
        for iteration in range(1, max_iterations + 1):
            logger.info("=== 第 %d 次迭代 ===", iteration)
            
            # 1. 执行回测
            logger.info("执行回测...")
            backtest_result = await self._run_backtest(current_strategy)
            
            if not backtest_result.get("success"):
                error_msg = backtest_result.get("error", "回测执行失败")
                logger.error("回测失败: %s", error_msg)
                # 如果是第一次迭代就失败，直接返回错误
                if iteration == 1:
                    return {
                        "final_strategy": current_strategy,
                        "final_result": backtest_result,
                        "final_evaluation": {"overall_score": 0, "is_satisfactory": False},
                        "iterations": [],
                        "optimization_summary": f"初始策略回测失败: {error_msg}",
                        "error": error_msg
                    }
                # 如果不是第一次，使用上一次的结果
                break
            
            # 2. 评估结果
            logger.info("评估回测结果...")
            evaluation = await evaluate_backtest_result(
                user_description, current_strategy, backtest_result
            )
            
            # 记录本次迭代
            iteration_result = IterationResult(
                iteration=iteration,
                strategy=current_strategy,
                backtest_result=backtest_result,
                evaluation=evaluation,
                optimization_applied=False,
            )
            self.iterations.append(iteration_result)
            
            logger.info(
                "评估完成 - 评分: %d/100, 满意度: %s, 优化优先级: %s",
                evaluation.get("overall_score", 0),
                "满意" if evaluation.get("is_satisfactory") else "不满意",
                evaluation.get("optimization_priority", "unknown")
            )
            
            # 3. 判断是否需要继续优化
            if not should_optimize_strategy(evaluation):
                logger.info("策略已满足要求，停止优化")
                break
            
            if iteration >= max_iterations:
                logger.info("达到最大迭代次数，停止优化")
                break
            
            # 4. 生成优化版本
            logger.info("生成优化策略...")
            try:
                optimized_strategy = await optimize_strategy_based_on_evaluation(
                    user_description, current_strategy, evaluation, backtest_result
                )
                
                # 5. 验证优化后的策略
                logger.info("验证优化策略...")
                passed, errors = await evaluate_strategy_python_full(
                    optimized_strategy["code"], 
                    optimized_strategy["config"],
                    run_execution_check=True
                )
                
                if not passed:
                    logger.warning("优化策略验证失败: %s", "; ".join(errors))
                    # 如果优化失败，停止迭代
                    break
                
                current_strategy = optimized_strategy
                iteration_result.optimization_applied = True
                
                logger.info("策略优化完成，准备下一轮迭代")
                
            except Exception as e:
                logger.exception("策略优化失败: %s", e)
                break
        
        # 生成最终结果
        final_iteration = self.iterations[-1] if self.iterations else None
        if not final_iteration:
            return {
                "final_strategy": initial_strategy,
                "final_result": {"success": False, "error": "无有效迭代结果"},
                "final_evaluation": {"overall_score": 0, "is_satisfactory": False},
                "iterations": [],
                "optimization_summary": "优化过程异常终止",
                "error": "无有效迭代结果"
            }
        
        optimization_summary = self._generate_optimization_summary()
        
        return {
            "final_strategy": final_iteration.strategy,
            "final_result": final_iteration.backtest_result,
            "final_evaluation": final_iteration.evaluation,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "score": it.evaluation.get("overall_score", 0),
                    "is_satisfactory": it.evaluation.get("is_satisfactory", False),
                    "optimization_applied": it.optimization_applied,
                    "summary": it.backtest_result.get("summary", {}),
                }
                for it in self.iterations
            ],
            "optimization_summary": optimization_summary,
        }
    
    async def _run_backtest(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """执行回测"""
        try:
            if "code" in strategy and "config" in strategy:
                # Python 策略
                return await self.engine_client.run_python(
                    strategy["code"], strategy["config"]
                )
            else:
                # DSL 策略
                return await self.engine_client.run(strategy)
        except Exception as e:
            logger.exception("回测执行异常")
            return {"success": False, "error": str(e)}
    
    def _generate_optimization_summary(self) -> str:
        """生成优化过程总结"""
        if not self.iterations:
            return "无迭代记录"
        
        first_score = self.iterations[0].evaluation.get("overall_score", 0)
        final_score = self.iterations[-1].evaluation.get("overall_score", 0)
        total_iterations = len(self.iterations)
        
        summary = f"经过 {total_iterations} 轮迭代优化，"
        summary += f"策略评分从 {first_score} 提升到 {final_score}。"
        
        if final_score >= 70:
            summary += "策略已达到满意水平。"
        else:
            summary += "策略仍有改进空间，建议人工进一步调整。"
        
        return summary
