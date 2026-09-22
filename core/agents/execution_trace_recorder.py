"""Agent 执行轨迹采集器

设计原则：
1. 非阻塞：所有异常内部捕获，不影响 agent 执行
2. 渐进式采集：record_prompts / record_llm_response / record_parsed_output 分步调用
3. 子类回填：base 写入后，子类通过 update_validation_sync 回填校验结果
4. 配置开关：settings.AGENT_EXECUTION_TRACE_ENABLED 控制是否启用
"""

# 注解惰性化：社区版剔除 execution_trace 模型后，类型注解（如 trace -> AgentExecutionTrace）
# 在 def 执行时不求值，避免 NameError；必须位于其他 import 之前
from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from typing import Any, Dict, Optional

from app.core.config import settings
from app.utils.timezone import now_tz

# 后端依赖可选导入：社区版（Apache 2.0 开源版）已将 app/models/execution_trace 与
# app/services/execution_trace_service 随 Pro 开源分离剔除。import 失败时本模块
# 降级为 no-op（is_trace_enabled 恒 False → 调用方 recorder 恒 None → 全部采集段跳过），
# 8 个调用方（analyst/researcher/manager/universal/base/trader_v2/fundamentals_analyst_v2/
# workflow builder）零改动，社区版分析主链路不受影响。
try:
    from app.pro.models.execution_trace import (
        AgentExecutionTrace,
        InputSnapshot,
        LLMConfigSnapshot,
        OutputSnapshot,
        PromptSnapshot,
        TokenUsage,
        ToolCallRecord,
        ValidationResult,
    )
    from app.pro.services.execution_trace_service import execution_trace_service
    _TRACE_BACKEND_AVAILABLE = True
except ImportError:  # 社区版路径：执行轨迹后端不可用
    _TRACE_BACKEND_AVAILABLE = False

logger = logging.getLogger(__name__)

# 线程本地变量：支持单次分析任务临时开启轨迹采集
# 当全局开关关闭时，可通过 enable_trace_for_current_thread() 在当前线程临时开启
_trace_thread_local = threading.local()


def enable_trace_for_current_thread() -> None:
    """为当前线程临时开启轨迹采集（单次分析任务级别）"""
    _trace_thread_local.enabled = True


def disable_trace_for_current_thread() -> None:
    """关闭当前线程的临时轨迹采集"""
    _trace_thread_local.enabled = False


def is_trace_enabled() -> bool:
    """检查是否启用轨迹采集

    优先级：后端可用性 > 线程本地临时标记 > 全局配置
    - 后端不可用（社区版）恒 False
    - 全局配置 AGENT_EXECUTION_TRACE_ENABLED 默认关闭
    - 分析任务可通过 enable_trace=true 参数临时开启（仅对本次执行生效）
    """
    # 后端不可用（社区版已剔除 execution_trace 体系）→ 恒关闭
    if not _TRACE_BACKEND_AVAILABLE:
        return False
    # 线程本地标记优先
    if getattr(_trace_thread_local, "enabled", False):
        return True
    # 全局配置
    return getattr(settings, "AGENT_EXECUTION_TRACE_ENABLED", False)


class ExecutionTraceRecorder:
    """执行轨迹采集器

    用法（在 ManagerAgent.execute 中）：
        recorder = start_execution_trace(self, state)
        try:
            recorder.record_inputs(inputs)
            recorder.record_prompts(system_prompt, user_prompt)
            response = self._llm.invoke(messages)
            recorder.record_llm_response(response, llm_duration_ms=500)
            decision = self._parse_response(response.content)
            recorder.record_parsed_output(decision)
            return result
        except Exception as e:
            recorder.record_error(e)
            raise
        finally:
            recorder.finish()  # 写入 MongoDB（非阻塞）

    子类回填（在 RiskManagerV2.execute 中）：
        result = super().execute(state)
        # ... 校验 ...
        self._record_trace_validation("passed"/"failed", error, details)
    """

    def __init__(
        self,
        agent_id: str,
        agent_version: str,
        agent_type: str,
        manager_type: Optional[str],
        state: Dict[str, Any],
    ):
        self._trace = AgentExecutionTrace(
            trace_id=str(uuid.uuid4()),
            agent_id=agent_id,
            agent_version=agent_version,
            agent_type=agent_type,
            manager_type=manager_type,
            started_at=now_tz(),
        )
        self._finished = False
        self._llm_duration_ms: Optional[int] = None

        # 从 state 提取工作流上下文
        self._extract_workflow_context(state)

        # 提取分析目标
        self._trace.ticker = state.get("ticker") or state.get("company_of_interest")
        self._trace.analysis_date = state.get("analysis_date") or state.get("trade_date") or state.get("end_date")

    def _extract_workflow_context(self, state: Dict[str, Any]) -> None:
        """从 state["_workflow_runtime"] 提取工作流上下文"""
        runtime = state.get("_workflow_runtime") or {}
        if isinstance(runtime, dict):
            self._trace.workflow_id = runtime.get("workflow_id")
            self._trace.execution_id = runtime.get("execution_id")
            self._trace.task_id = runtime.get("task_id") or runtime.get("execution_id")
            self._trace.user_id = runtime.get("user_id")
            self._trace.thread_id = runtime.get("thread_id")

    def record_llm_config(self, llm: Any) -> None:
        """记录 LLM 配置"""
        try:
            self._trace.llm_config = LLMConfigSnapshot(
                model_name=getattr(llm, "model_name", None) or getattr(llm, "model", None),
                temperature=getattr(llm, "temperature", None),
                max_tokens=getattr(llm, "max_tokens", None),
            )
        except Exception as e:
            logger.debug(f"记录 LLM 配置失败: {e}")

    def record_inputs(self, inputs: Dict[str, Any]) -> None:
        """记录输入快照"""
        try:
            input_lengths = {}
            for k, v in inputs.items():
                try:
                    input_lengths[k] = len(str(v)) if v else 0
                except Exception:
                    input_lengths[k] = 0
            self._trace.inputs = InputSnapshot(
                input_keys=list(inputs.keys()),
                input_lengths=input_lengths,
            )
        except Exception as e:
            logger.debug(f"记录输入快照失败: {e}")

    def record_prompts(self, system_prompt: str, user_prompt: str) -> None:
        """记录提示词快照（哈希 + 长度 + 全文）

        全文存储用于：前端查看、Prompt 优化对比、回归测试重放。
        哈希/长度保留用于 P2 反思扫描的 hash 聚类（体积小，扫描快）。
        """
        try:
            self._trace.prompts = PromptSnapshot(
                system_prompt_hash=hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16] if system_prompt else None,
                system_prompt_length=len(system_prompt) if system_prompt else 0,
                user_prompt_hash=hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()[:16] if user_prompt else None,
                user_prompt_length=len(user_prompt) if user_prompt else 0,
                system_prompt_full=system_prompt if system_prompt else None,
                user_prompt_full=user_prompt if user_prompt else None,
            )
        except Exception as e:
            logger.debug(f"记录提示词快照失败: {e}")

    def record_llm_response(self, response: Any, llm_duration_ms: Optional[int] = None) -> None:
        """记录 LLM 响应

        支持多次调用累加：
        - 工具调用模式下，LLM 会被调用多次（每次循环 + 最终报告）
        - 每次调用的 Token 用量累加到总用量
        - 输出快照只保留最后一次（最终报告），但 LLM 调用次数 +1
        """
        try:
            # 🔑 累加 LLM 调用次数
            self._trace.llm_call_count += 1

            # 累加 LLM 耗时
            if llm_duration_ms is not None:
                prev = self._llm_duration_ms or 0
                self._llm_duration_ms = prev + llm_duration_ms

            # 输出快照（覆盖式，保留最终报告）
            content = getattr(response, "content", "") or ""
            if content:
                self._trace.output = OutputSnapshot(
                    output_raw_length=len(content),
                    output_raw_preview=content[:500] if content else None,
                    output_raw_full=content if content else None,
                )

            # Token 用量累加（兼容 LangChain AIMessage）
            usage_meta = getattr(response, "usage_metadata", None)
            if isinstance(usage_meta, dict):
                prev_input = self._trace.token_usage.input_tokens or 0
                prev_output = self._trace.token_usage.output_tokens or 0
                prev_total = self._trace.token_usage.total_tokens or 0
                self._trace.token_usage = TokenUsage(
                    input_tokens=prev_input + (usage_meta.get("input_tokens") or 0),
                    output_tokens=prev_output + (usage_meta.get("output_tokens") or 0),
                    total_tokens=prev_total + (usage_meta.get("total_tokens") or 0),
                )

            # 从 response_metadata 补全 model_name
            resp_meta = getattr(response, "response_metadata", None)
            if isinstance(resp_meta, dict):
                model_from_resp = resp_meta.get("model_name") or resp_meta.get("model")
                if model_from_resp and not self._trace.llm_config.model_name:
                    self._trace.llm_config.model_name = model_from_resp
        except Exception as e:
            logger.debug(f"记录 LLM 响应失败: {e}")

    def record_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        success: bool = True,
        error: Optional[str] = None,
        result_length: int = 0,
        result_preview: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """记录一次工具调用"""
        try:
            self._trace.tool_calls.append(ToolCallRecord(
                tool_name=tool_name,
                tool_args=tool_args,
                success=success,
                error=error[:500] if error else None,
                result_length=result_length,
                result_preview=result_preview[:200] if result_preview else None,
                duration_ms=duration_ms,
            ))
        except Exception as e:
            logger.debug(f"记录工具调用失败: {e}")

    def record_parsed_output(self, parsed: Any) -> None:
        """记录解析后的输出"""
        try:
            if isinstance(parsed, dict):
                self._trace.output.output_parsed_keys = list(parsed.keys())
                self._trace.output.output_parsed_success = parsed.get("success", True)
                self._trace.output.output_parsed_type = "dict"
            else:
                self._trace.output.output_parsed_type = type(parsed).__name__
                self._trace.output.output_parsed_success = True
        except Exception as e:
            logger.debug(f"记录解析输出失败: {e}")

    def record_error(self, exc: Exception) -> None:
        """记录异常"""
        self._trace.success = False
        self._trace.error_message = str(exc)
        self._trace.error_type = type(exc).__name__

    @property
    def trace_id(self) -> str:
        return self._trace.trace_id

    @property
    def trace(self) -> AgentExecutionTrace:
        """暴露 trace 对象（供 TraderV2 等需要直接操作的场景）"""
        return self._trace

    def finish(self) -> None:
        """完成采集并写入 MongoDB（非阻塞）"""
        if self._finished:
            return
        self._finished = True
        try:
            self._trace.finished_at = now_tz()
            duration_ms = int(
                (self._trace.finished_at - self._trace.started_at).total_seconds() * 1000
            )
            self._trace.execution_duration_ms = duration_ms
            self._trace.llm_duration_ms = self._llm_duration_ms
            execution_trace_service.save_trace_sync(self._trace)
        except Exception as e:
            logger.warning(f"⚠️ 执行轨迹 finish 失败（不影响 agent）: {e}")

    def set_validation(
        self,
        validation_status: str,
        validation_error: Optional[str] = None,
        validation_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """回填校验结果到内存 trace 对象（供 finish 时一并写入）。

        解决 trader_v2 时序问题：trader_v2 的 record_trace_validation（DB update）
        在 finish（insert）之前执行，此时文档不存在导致 update no-op，
        随后 finish 的 insert 用内存中 validation=None 覆盖。

        本方法更新内存对象的 validation 字段，使 finish 的 insert 携带正确值。
        若已 finish（文档已 insert），则降级为 DB update（兼容 ManagerAgent
        在 super().execute finally 中先 finish、子类后回填的场景）。
        """
        try:
            if self._trace.validation is None:
                self._trace.validation = ValidationResult()
            self._trace.validation.validation_status = validation_status
            if validation_error is not None:
                self._trace.validation.validation_error = validation_error
            if validation_details is not None:
                self._trace.validation.validation_details = validation_details
        except Exception as e:
            logger.debug(f"记录校验结果到内存失败: {e}")
        # 若文档已 insert（finish 已执行），同步更新 DB
        if self._finished:
            record_trace_validation(
                trace_id=self._trace.trace_id,
                validation_status=validation_status,
                validation_error=validation_error,
                validation_details=validation_details,
            )


def start_execution_trace(
    agent: Any,
    state: Dict[str, Any],
) -> ExecutionTraceRecorder:
    """启动执行轨迹采集

    Args:
        agent: Agent 实例（需有 agent_id、get_metadata 属性）
        state: 工作流状态

    Returns:
        ExecutionTraceRecorder 实例
    """
    # 🔑 防重复：如果 agent 已经有活跃的 recorder，直接返回（避免 builder 层与适配器层重复创建）
    existing = getattr(agent, "_execution_recorder", None)
    if existing is not None and not existing._finished:
        return existing

    metadata = agent.get_metadata() if hasattr(agent, "get_metadata") else None
    agent_version = getattr(metadata, "version", "unknown") if metadata else "unknown"
    manager_type = getattr(agent, "manager_type", None)

    # 判断 agent_type（按基类类型标识属性区分）
    if manager_type is not None:
        agent_type = "manager"
    elif getattr(agent, "analyst_type", None) is not None:
        agent_type = "analyst"
    elif getattr(agent, "researcher_type", None) is not None:
        agent_type = "researcher"
    elif hasattr(agent, "output_field"):
        agent_type = "trader"
    else:
        agent_type = "manager"  # 默认兜底

    recorder = ExecutionTraceRecorder(
        agent_id=agent.agent_id,
        agent_version=agent_version,
        agent_type=agent_type,
        manager_type=manager_type,
        state=state,
    )

    # 记录 LLM 配置
    if hasattr(agent, "_llm") and agent._llm is not None:
        recorder.record_llm_config(agent._llm)

    # 🔑 自动绑定 recorder 到 agent，使 invoke_with_tools 能自动记录 LLM 响应
    # 这样所有继承 BaseAgent 的适配器（如 fundamentals_analyst_v2 等）都会自动记录 Token 用量
    try:
        agent._execution_recorder = recorder
    except Exception:
        pass

    return recorder


def record_trace_validation(
    trace_id: Optional[str],
    validation_status: str,
    validation_error: Optional[str] = None,
    validation_details: Optional[Dict[str, Any]] = None,
) -> None:
    """回填校验结果（供子类调用，非阻塞）"""
    if not trace_id or not is_trace_enabled():
        return
    try:
        execution_trace_service.update_validation_sync(
            trace_id=trace_id,
            validation_status=validation_status,
            validation_error=validation_error,
            validation_details=validation_details,
        )
    except Exception as e:
        logger.warning(f"⚠️ 回填校验结果失败（不影响 agent）: {e}")
