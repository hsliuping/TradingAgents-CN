"""
通用 Agent (UniversalAgent)

完全由数据库配置驱动的通用智能体，可以替代 80-95% 的专用 Agent 类。
所有行为（工具、提示词、输出字段）均由数据库配置定义，无任何硬编码业务逻辑。

设计原则（参考 OpenClaw 单一职责）：
- 一个 Agent 只做一件事：拿到上下文 → 用工具获取数据 → 写报告
- 复杂性通过工作流图结构表达，不在 Agent 内部
- 三层优先级：节点专属 > 工作流专属 > Agent 默认
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent
from .config import AgentConfig

logger = logging.getLogger(__name__)


class UniversalAgent(BaseAgent):
    """
    通用 Agent — 完全由数据库配置驱动

    工具加载顺序（三层优先级）：
    1. 节点专属：workflow_id + node_id + agent_id
    2. 工作流专属：workflow_id + agent_id
    3. Agent 默认：agent_id only

    提示词加载顺序（已由基类 _get_prompt_from_template 实现）：
    1. 节点专属模板（workflow_id + node_id）
    2. 工作流专属模板（workflow_id）
    3. Agent 默认模板
    4. 内置默认文本
    """

    # 类级别的 metadata 占位（由工厂动态设置，此处为 None 以满足类型注解）
    metadata = None

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm: Optional[Any] = None,
        tool_ids: Optional[List[str]] = None,
        agent_id: str = "universal_agent",
        agent_name: str = "通用智能体",
        agent_description: str = "由数据库配置驱动的通用智能体",
        output_field: str = "analysis_report",
        **kwargs,
    ):
        """
        初始化通用 Agent

        Args:
            config: Agent 运行时配置
            llm: LangChain LLM 实例
            tool_ids: 工具 ID 列表
            agent_id: 动态 Agent ID（来自 agent_configs 数据库）
            agent_name: Agent 显示名称
            agent_description: Agent 描述（用于构建默认提示词）
            output_field: 输出字段名（写入 state 的 key）
        """
        # 在 super().__init__() 之前设置动态属性，因为父类初始化会调用 self.agent_id
        self._dynamic_agent_id = agent_id
        self._agent_name = agent_name
        self._agent_description = agent_description
        self._output_field = output_field
        self._last_tool_debug = []
        self._last_llm_debug = {}
        # Agent Workshop 调试态：testing 版本 + debug template
        self._version_status = kwargs.pop('version_status', None)
        self._prompt_template_id = kwargs.pop('prompt_template_id', None)

        super().__init__(config=config, llm=llm, tool_ids=tool_ids)

    @property
    def agent_id(self) -> str:
        """返回动态 Agent ID（来自数据库配置）"""
        return getattr(self, "_dynamic_agent_id", "universal_agent")

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        通用执行逻辑

        1. 从模板系统加载系统提示词（支持 workflow_id + node_id 三层优先级）
        2. 从模板系统加载用户提示词（或构建通用用户提示词）
        3. 调用 LLM + 工具
        4. 输出到 state[output_field]
        """
        logger.info(f"[UniversalAgent:{self.agent_id}] 🚀 开始执行")

        # P1: 启动执行轨迹采集
        from core.agents.execution_trace_recorder import (
            start_execution_trace, is_trace_enabled
        )
        recorder = None
        if is_trace_enabled():
            try:
                recorder = start_execution_trace(self, state)
                self._last_trace_id = recorder.trace_id
            except Exception as e:
                logger.warning(f"⚠️ [UniversalAgent:{self.agent_id}] 启动轨迹采集失败（不影响 agent）: {e}")
                self._last_trace_id = None

        try:
            context = state.get("context")
            prompt_variables = self._build_prompt_variables(state)

            # 🔥 Agent Workshop 上下文注入：workflow_id + 调试态标记
            if isinstance(context, dict):
                workflow_id = state.get("workflow_id")
                if workflow_id and "workflow_id" not in context:
                    context["workflow_id"] = workflow_id
                version_status = getattr(self, '_version_status', None)
                prompt_template_id = getattr(self, '_prompt_template_id', None)
                if version_status == "testing" and prompt_template_id:
                    context["is_debug_mode"] = True
                    context["debug_template_id"] = prompt_template_id
            elif context is not None:
                workflow_id = state.get("workflow_id")
                if workflow_id and not hasattr(context, 'workflow_id'):
                    context.workflow_id = workflow_id
                version_status = getattr(self, '_version_status', None)
                prompt_template_id = getattr(self, '_prompt_template_id', None)
                if version_status == "testing" and prompt_template_id:
                    context.is_debug_mode = True
                    context.debug_template_id = prompt_template_id

            # 1. 系统提示词（从模板系统，三层优先级）
            system_prompt = self._get_prompt_from_template(
                agent_type="universal",
                agent_name=self.agent_id,
                variables=prompt_variables,
                state=state,
                context=context,
                fallback_prompt=None,
                prompt_type="system",
            )

            if not system_prompt:
                system_prompt = self._build_default_system_prompt()

            # 2. 用户提示词（从模板系统，三层优先级）
            user_prompt = self._get_prompt_from_template(
                agent_type="universal",
                agent_name=self.agent_id,
                variables=prompt_variables,
                state=state,
                context=context,
                fallback_prompt=None,
                prompt_type="user",
            )

            if not user_prompt:
                user_prompt = self._build_default_user_prompt(state)
            else:
                user_prompt = self._ensure_runtime_context(user_prompt, state)

            # 🔥 应用 prompt_overrides（允许测试时覆盖模板内容）
            overrides = state.get("prompt_overrides") or {}
            if isinstance(overrides, dict) and overrides:
                override_sys = overrides.get("system_prompt") or overrides.get("system")
                override_user = overrides.get("user_prompt") or overrides.get("user")
                if override_sys:
                    logger.info(f"[UniversalAgent:{self.agent_id}] prompt_overrides.system_prompt 已应用 "
                                f"(原长度 {len(system_prompt)} → 新长度 {len(str(override_sys))})")
                    system_prompt = str(override_sys)
                if override_user:
                    logger.info(f"[UniversalAgent:{self.agent_id}] prompt_overrides.user_prompt 已应用 "
                                f"(原长度 {len(user_prompt)} → 新长度 {len(str(override_user))})")
                    user_prompt = str(override_user)
                # 也支持嵌套在 content 里的格式
                content_overrides = overrides.get("content") or {}
                if isinstance(content_overrides, dict):
                    if content_overrides.get("system_prompt") or content_overrides.get("system"):
                        system_prompt = str(content_overrides.get("system_prompt") or content_overrides.get("system"))
                        logger.info(f"[UniversalAgent:{self.agent_id}] prompt_overrides.content.system_prompt 已应用")
                    if content_overrides.get("user_prompt") or content_overrides.get("user"):
                        user_prompt = str(content_overrides.get("user_prompt") or content_overrides.get("user"))
                        logger.info(f"[UniversalAgent:{self.agent_id}] prompt_overrides.content.user_prompt 已应用")

            execution_guidance = self._build_execution_plan_guidance(state)
            if execution_guidance:
                system_prompt = f"{system_prompt}\n\n{execution_guidance}"
                logger.info(
                    f"[UniversalAgent:{self.agent_id}] 已注入 Agent Workshop execution_plan 运行约束 "
                    f"(长度 {len(execution_guidance)})"
                )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            logger.info(f"[UniversalAgent:{self.agent_id}] System prompt length: {len(system_prompt)}")
            logger.info(f"[UniversalAgent:{self.agent_id}] User prompt length: {len(user_prompt)}")

            # P1: 记录 Prompt
            if recorder:
                try:
                    recorder.record_inputs({"ticker": state.get("ticker"), "workflow_id": state.get("workflow_id")})
                    recorder.record_prompts(system_prompt, user_prompt)
                except Exception as e:
                    logger.debug(f"[UniversalAgent:{self.agent_id}] 记录 Prompt 失败（不影响 agent）: {e}")

            if not self._llm:
                raise ValueError("LLM not initialized")

            if self._langchain_tools:
                logger.info(
                    f"[UniversalAgent:{self.agent_id}] 使用工具调用模式，"
                    f"工具数: {len(self._langchain_tools)}"
                )
                report = self.invoke_with_tools(messages)
                self._last_llm_debug = {
                    "response_type": "tool_invoke",
                    "final_response_content": report,
                    "tool_mode": True,
                    "tool_trace": list(getattr(self, '_tool_call_summaries_collected', [])),
                }
            else:
                logger.warning(f"[UniversalAgent:{self.agent_id}] 无工具，直接调用 LLM")
                import time as _time_llm
                _llm_start = _time_llm.time()
                response = self._llm.invoke(messages)
                _llm_duration_ms = int((_time_llm.time() - _llm_start) * 1000)
                report = response.content if hasattr(response, "content") else str(response)
                self._last_llm_debug = {
                    "response_type": type(response).__name__,
                    "final_response_content": report,
                    "tool_mode": False,
                    "tool_trace": list(self._last_tool_debug),
                }
                # P1: 记录 LLM 响应
                if recorder:
                    try:
                        recorder.record_llm_response(response, llm_duration_ms=_llm_duration_ms)
                    except Exception as e:
                        logger.debug(f"[UniversalAgent:{self.agent_id}] 记录 LLM 响应失败（不影响 agent）: {e}")

            # P1: 记录解析后的输出
            if recorder:
                try:
                    recorder.record_parsed_output({"report": report[:500] if isinstance(report, str) else str(report)[:500]})
                except Exception as e:
                    logger.debug(f"[UniversalAgent:{self.agent_id}] 记录解析输出失败（不影响 agent）: {e}")

            is_debug_mode = bool(getattr(context, 'is_debug_mode', False)) if context else False
            if is_debug_mode:
                logger.info(f"[UniversalAgent:{self.agent_id}] 调试模式 Prompt - system:\n{system_prompt}")
                logger.info(f"[UniversalAgent:{self.agent_id}] 调试模式 Prompt - user:\n{user_prompt}")
                logger.info(f"[UniversalAgent:{self.agent_id}] 调试模式 LLM 最终返回:\n{self._last_llm_debug.get('final_response_content', report)}")

            logger.info(f"[UniversalAgent:{self.agent_id}] ✅ 执行完成，输出到 '{self._output_field}'")
            result = {self._output_field: report}
            if is_debug_mode:
                result["__debug_prompt__"] = {
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "llm_final_response": self._last_llm_debug.get("final_response_content", report),
                    "response_type": self._last_llm_debug.get("response_type"),
                    "tool_mode": self._last_llm_debug.get("tool_mode"),
                    "tool_trace": self._last_llm_debug.get("tool_trace", []),
                }
            return result

        except Exception as e:
            logger.error(f"[UniversalAgent:{self.agent_id}] ❌ 执行失败: {e}", exc_info=True)
            # P1: 记录异常
            if recorder:
                try:
                    recorder.record_error(e)
                except Exception:
                    pass
            return {self._output_field: f"执行失败: {str(e)}"}
        finally:
            # P1: 完成轨迹采集并写入 MongoDB（非阻塞）
            if recorder:
                try:
                    recorder.finish()
                except Exception:
                    pass

    def _build_execution_plan_guidance(self, state: Dict[str, Any]) -> str:
        """把 Agent Workshop execution_plan 注入运行时提示词。

        build_version 生成的 execution_plan 是版本执行契约，不能只留在评估阶段。
        Runtime 必须在第一次工具调用前看到这些步骤、工具和验收项，否则 LLM 可能只按
        宽泛角色提示生成报告，跳过版本声明的关键工具。
        """
        plan = state.get("agent_workshop_execution_plan")
        if not isinstance(plan, dict) or not plan:
            return ""

        lines = [
            "## Agent Workshop Execution Plan（运行时强约束）",
            "以下内容来自当前版本的 build_version 执行计划。你必须按它执行，而不是只按角色描述自由发挥。",
        ]

        sample_input = plan.get("sample_input") if isinstance(plan.get("sample_input"), dict) else {}
        if sample_input:
            sample_parts = []
            for key in ("symbol", "market_type", "analysis_date", "task_description"):
                value = sample_input.get(key)
                if value:
                    sample_parts.append(f"{key}={value}")
            if sample_parts:
                lines.append(f"- 默认样本/任务上下文：{'; '.join(sample_parts)}")

        steps = plan.get("execution_steps") if isinstance(plan.get("execution_steps"), list) else []
        required_tools = []
        if steps:
            lines.append("- 执行步骤：")
            for index, step in enumerate(steps[:6], 1):
                if not isinstance(step, dict):
                    continue
                title = str(step.get("title") or step.get("step_id") or f"step-{index}").strip()
                objective = str(step.get("objective") or "").strip()
                tools = [str(item).strip() for item in (step.get("suggested_tools") or []) if str(item).strip()]
                expected = [str(item).strip() for item in (step.get("expected_evidence") or []) if str(item).strip()]
                required_tools.extend(tools)
                line = f"  {index}. {title}"
                if objective:
                    line += f"：{objective}"
                lines.append(line)
                if tools:
                    lines.append(f"     - 本步应优先调用工具：{', '.join(tools)}")
                if expected:
                    lines.append(f"     - 本步必须形成证据：{'；'.join(expected[:4])}")

        required_tools = list(dict.fromkeys(required_tools))
        if required_tools:
            lines.append(f"- 关键工具调用要求：如果本次任务涉及这些工具对应的核心能力，必须优先调用：{', '.join(required_tools)}。")
            lines.append("- 如果某个关键工具无法调用或返回无数据，必须在报告中说明失败原因和降级边界，不能用其他泛化报告冒充该工具结果。")

        checks = [str(item).strip() for item in (plan.get("acceptance_checks") or []) if str(item).strip()]
        if checks:
            lines.append("- 交付前自检项：")
            for item in checks[:8]:
                lines.append(f"  - {item}")

        fallback_rules = [str(item).strip() for item in (plan.get("fallback_rules") or []) if str(item).strip()]
        if fallback_rules:
            lines.append("- 降级规则：")
            for item in fallback_rules[:6]:
                lines.append(f"  - {item}")

        lines.append("- 严禁只写 Prompt 演示式报告；最终结论必须能对应到工具调用、上游结构化输入或明确的数据缺口说明。")
        return "\n".join(lines)

    def _build_prompt_variables(self, state: Dict[str, Any]) -> Dict[str, Any]:
        ticker = state.get("ticker") or state.get("stock_symbol") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date") or state.get("trade_date", "")
        return {
            "ticker": ticker,
            "stock_symbol": state.get("stock_symbol") or ticker,
            "company_of_interest": state.get("company_of_interest") or ticker,
            "analysis_date": analysis_date,
            "trade_date": state.get("trade_date") or analysis_date,
            "market_type": state.get("market_type", ""),
            "task_description": state.get("task_description", ""),
        }

    def _ensure_runtime_context(self, user_prompt: str, state: Dict[str, Any]) -> str:
        ticker = state.get("ticker") or state.get("stock_symbol") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date") or state.get("trade_date", "")
        market_type = state.get("market_type", "")
        task_description = state.get("task_description", "")

        context_lines = []
        if ticker:
            context_lines.append(f"- 股票代码: {ticker}")
        if analysis_date:
            context_lines.append(f"- 分析日期: {analysis_date}")
        if market_type:
            context_lines.append(f"- 市场: {market_type}")
        if task_description:
            context_lines.append(f"- 任务目标: {task_description}")

        if not context_lines:
            return user_prompt

        context_block = "\n\n本次任务输入:\n" + "\n".join(context_lines)
        if ticker and str(ticker) in user_prompt:
            return user_prompt
        return f"{user_prompt.rstrip()}{context_block}"

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示词（当模板系统无对应模板时使用）"""
        return f"""你是一位专业的{self._agent_name}。

{self._agent_description}

工作原则：
1. 基于工具获取的真实数据进行分析，不编造、不猜测
2. 结论明确，有理有据，逻辑清晰
3. 使用中文输出，格式结构清晰
4. 如工具返回数据缺失某维度，说明"该维度数据缺失，暂不分析"

请根据用户请求，调用相应工具获取数据，然后撰写详细的分析报告。"""

    def _build_default_user_prompt(self, state: Dict[str, Any]) -> str:
        """构建默认用户提示词（当模板系统无对应模板时使用）"""
        ticker = state.get("ticker") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date") or state.get("trade_date", "")

        if ticker and analysis_date:
            return (
                f"请分析 {ticker}（{analysis_date}）。"
                f"请调用工具获取相关数据，然后生成详细的分析报告。"
            )
        elif ticker:
            return f"请对 {ticker} 进行全面分析，调用工具获取相关数据后生成详细报告。"
        else:
            return "请根据你的角色职责，调用所需工具获取数据，生成详细的分析报告。"

