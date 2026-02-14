"""
计划执行器

按照 AnalysisPlan 中的 DAG 依赖关系调度工具调用：
- 无依赖步骤用 asyncio.gather 并行执行
- 有依赖步骤等待依赖完成后执行
- 单步骤超时 60s，整体超时由调用方控制

依赖：
- core/tools/registry.py — 工具函数获取
- core/agents/planner_models.py — 数据模型
"""

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from core.tools import get_tool_registry

from .planner_models import AnalysisPlan, PlanStep, StepResult

logger = logging.getLogger(__name__)

# 单步骤执行超时（秒）
STEP_TIMEOUT_SECONDS = 60


class PlanExecutor:
    """
    计划执行器

    根据 AnalysisPlan 中步骤的 depends_on 关系，
    按拓扑排序分组并行/串行执行工具调用。
    """

    def __init__(self):
        self._registry = get_tool_registry()

    async def execute(
        self,
        plan: AnalysisPlan,
        on_step_started: Optional[Callable] = None,
        on_step_completed: Optional[Callable] = None,
    ) -> List[StepResult]:
        """
        执行分析计划中的所有步骤。

        Args:
            plan: 分析计划
            on_step_started: 步骤开始回调 (step_id, tool, intent)
            on_step_completed: 步骤完成回调 (StepResult)

        Returns:
            所有步骤的执行结果列表
        """
        if not plan.steps:
            return []

        all_results: Dict[int, StepResult] = {}
        groups = plan.parallel_groups

        for group in groups:
            tasks = [
                self._execute_step(step, on_step_started, on_step_completed)
                for step in group
            ]
            group_results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(group, group_results):
                if isinstance(result, Exception):
                    sr = StepResult(
                        step_id=step.id,
                        tool=step.tool,
                        intent=step.intent,
                        success=False,
                        error=str(result),
                    )
                    if on_step_completed:
                        on_step_completed(sr)
                    all_results[step.id] = sr
                else:
                    all_results[step.id] = result

        # 按步骤 ID 排序返回
        return [all_results[sid] for sid in sorted(all_results.keys())]

    async def _execute_step(
        self,
        step: PlanStep,
        on_started: Optional[Callable] = None,
        on_completed: Optional[Callable] = None,
    ) -> StepResult:
        """执行单个步骤"""
        if on_started:
            on_started(step.id, step.tool, step.intent)

        start_time = time.time()

        func = self._registry.get_function(step.tool)
        if func is None:
            sr = StepResult(
                step_id=step.id,
                tool=step.tool,
                intent=step.intent,
                success=False,
                error=f"工具 '{step.tool}' 未注册或无函数实现",
            )
            if on_completed:
                on_completed(sr)
            return sr

        try:
            result = await asyncio.wait_for(
                self._invoke_tool(func, step.args),
                timeout=STEP_TIMEOUT_SECONDS,
            )
            duration_ms = int((time.time() - start_time) * 1000)

            sr = StepResult(
                step_id=step.id,
                tool=step.tool,
                intent=step.intent,
                success=True,
                result=result,
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            sr = StepResult(
                step_id=step.id,
                tool=step.tool,
                intent=step.intent,
                success=False,
                error=f"工具执行超时（{STEP_TIMEOUT_SECONDS}s）",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            sr = StepResult(
                step_id=step.id,
                tool=step.tool,
                intent=step.intent,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

        if on_completed:
            on_completed(sr)
        return sr

    @staticmethod
    async def _invoke_tool(func: Callable, args: Dict[str, Any]) -> Any:
        """调用工具函数（自动处理同步/异步）"""
        # 防御层：过滤掉工具函数不接受的参数，避免 LLM 自创参数导致 TypeError
        try:
            sig = inspect.signature(func)
            valid_params = set(sig.parameters.keys())
            # 检查是否有 **kwargs，如果有则不过滤
            has_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
            if not has_var_keyword:
                filtered_args = {k: v for k, v in args.items() if k in valid_params}
                if len(filtered_args) != len(args):
                    removed = set(args.keys()) - valid_params
                    logger.warning(
                        f"[PlanExecutor] 过滤了工具 {func.__name__} 不支持的参数: {removed}"
                    )
                args = filtered_args
        except (ValueError, TypeError):
            pass  # 无法获取签名时不过滤

        if inspect.iscoroutinefunction(func):
            return await func(**args)
        else:
            # 同步函数在线程池中执行，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(**args))

