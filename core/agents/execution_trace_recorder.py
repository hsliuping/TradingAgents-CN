"""Agent 执行轨迹采集器

设计原则：
1. 非阻塞：所有异常内部捕获，不影响 agent 执行
2. 渐进式采集：record_prompts / record_llm_response / record_parsed_output 分步调用
3. 子类回填：base 写入后，子类通过 update_validation_sync 回填校验结果
4. 配置开关：settings.AGENT_EXECUTION_TRACE_ENABLED 控制是否启用
"""

import hashlib
import logging
import uuid
from typing import Any, Dict, Optional

from app.core.config import settings
from app.models.execution_trace import (
    AgentExecutionTrace,
    InputSnapshot,
    LLMConfigSnapshot,
    OutputSnapshot,
    PromptSnapshot,
    TokenUsage,
)
from app.services.execution_trace_service import execution_trace_service
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)


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
        """记录提示词快照（哈希 + 长度）"""
        try:
            self._trace.prompts = PromptSnapshot(
                system_prompt_hash=hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16] if system_prompt else None,
                system_prompt_length=len(system_prompt) if system_prompt else 0,
                user_prompt_hash=hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()[:16] if user_prompt else None,
                user_prompt_length=len(user_prompt) if user_prompt else 0,
            )
        except Exception as e:
            logger.debug(f"记录提示词快照失败: {e}")

    def record_llm_response(self, response: Any, llm_duration_ms: Optional[int] = None) -> None:
        """记录 LLM 响应"""
        try:
            self._llm_duration_ms = llm_duration_ms

            # 输出快照
            content = getattr(response, "content", "") or ""
            self._trace.output = OutputSnapshot(
                output_raw_length=len(content),
                output_raw_preview=content[:500] if content else None,
            )

            # Token 用量（兼容 LangChain AIMessage）
            usage_meta = getattr(response, "usage_metadata", None)
            if isinstance(usage_meta, dict):
                self._trace.token_usage = TokenUsage(
                    input_tokens=usage_meta.get("input_tokens"),
                    output_tokens=usage_meta.get("output_tokens"),
                    total_tokens=usage_meta.get("total_tokens"),
                )

            # 从 response_metadata 补全 model_name
            resp_meta = getattr(response, "response_metadata", None)
            if isinstance(resp_meta, dict):
                model_from_resp = resp_meta.get("model_name") or resp_meta.get("model")
                if model_from_resp and not self._trace.llm_config.model_name:
                    self._trace.llm_config.model_name = model_from_resp
        except Exception as e:
            logger.debug(f"记录 LLM 响应失败: {e}")

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
    metadata = agent.get_metadata() if hasattr(agent, "get_metadata") else None
    agent_version = getattr(metadata, "version", "unknown") if metadata else "unknown"
    manager_type = getattr(agent, "manager_type", None)

    # 判断 agent_type
    agent_type = "manager"
    if manager_type is None and hasattr(agent, "output_field"):
        agent_type = "trader"

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

    return recorder


def is_trace_enabled() -> bool:
    """检查是否启用轨迹采集"""
    return getattr(settings, "AGENT_EXECUTION_TRACE_ENABLED", True)


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
