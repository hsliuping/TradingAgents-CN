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
from dataclasses import asdict, is_dataclass
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
        prompt_template_type: str = "universal",
        prompt_template_name: Optional[str] = None,
        prompt_template_id: Optional[str] = None,
        prompt_template_status: Optional[str] = None,
        version_status: Optional[str] = None,
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
        self._prompt_template_type = str(prompt_template_type or "universal").strip() or "universal"
        self._prompt_template_name = str(prompt_template_name or agent_id).strip() or agent_id
        self._prompt_template_id = str(prompt_template_id or "").strip() or None
        self._prompt_template_status = str(prompt_template_status or "").strip() or None
        self._version_status = str(version_status or "").strip().lower() or None

        super().__init__(config=config, llm=llm, tool_ids=tool_ids)

    @property
    def agent_id(self) -> str:
        """返回动态 Agent ID（来自数据库配置）"""
        return getattr(self, "_dynamic_agent_id", "universal_agent")

    def _resolve_template_context(self, state: Dict[str, Any]) -> Any:
        context = state.get("context")
        if isinstance(context, dict):
            resolved_context = dict(context)
        elif context is not None and is_dataclass(context):
            resolved_context = asdict(context)
        elif context is not None:
            resolved_context = {
                "user_id": getattr(context, "user_id", None),
                "preference_id": getattr(context, "preference_id", None),
                "session_id": getattr(context, "session_id", None),
                "request_id": getattr(context, "request_id", None),
                "is_debug_mode": getattr(context, "is_debug_mode", False),
                "debug_template_id": getattr(context, "debug_template_id", None),
                "workflow_id": getattr(context, "workflow_id", None),
                "node_id": getattr(context, "node_id", None),
                "extra": getattr(context, "extra", None),
            }
        else:
            resolved_context = {}

        state_version_status = str(
            state.get("version_status")
            or resolved_context.get("version_status")
            or self._version_status
            or ""
        ).strip().lower()
        workflow_id = str(state.get("workflow_id") or resolved_context.get("workflow_id") or "").strip()
        should_force_debug = bool(
            self._prompt_template_id and (
                state_version_status in {"testing", "draft"}
                or workflow_id.startswith("agent_workshop_debug_")
            )
        )
        if should_force_debug:
            resolved_context["is_debug_mode"] = True
            resolved_context["debug_template_id"] = resolved_context.get("debug_template_id") or self._prompt_template_id
            resolved_context["version_status"] = state_version_status or self._version_status
            if workflow_id and not resolved_context.get("workflow_id"):
                resolved_context["workflow_id"] = workflow_id

        cleaned_context = {key: value for key, value in resolved_context.items() if value is not None}
        state["context"] = cleaned_context
        if cleaned_context.get("version_status") and not state.get("version_status"):
            state["version_status"] = cleaned_context.get("version_status")
        return cleaned_context

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        通用执行逻辑

        1. 从模板系统加载系统提示词（支持 workflow_id + node_id 三层优先级）
        2. 从模板系统加载用户提示词（或构建通用用户提示词）
        3. 调用 LLM + 工具
        4. 输出到 state[output_field]
        """
        logger.info(f"[UniversalAgent:{self.agent_id}] 🚀 开始执行")

        try:
            context = self._resolve_template_context(state)
            prompt_variables = self._build_prompt_variables(state)

            # 1. 系统提示词（从模板系统，三层优先级）
            system_prompt = self._get_prompt_from_template(
                agent_type=self._prompt_template_type,
                agent_name=self._prompt_template_name,
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
                agent_type=self._prompt_template_type,
                agent_name=self._prompt_template_name,
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

            system_prompt = self._apply_global_trading_advice_guard(system_prompt)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            logger.info(f"[UniversalAgent:{self.agent_id}] System prompt length: {len(system_prompt)}")
            logger.info(f"[UniversalAgent:{self.agent_id}] User prompt length: {len(user_prompt)}")

            if not self._llm:
                raise ValueError("LLM not initialized")

            if self._langchain_tools:
                logger.info(
                    f"[UniversalAgent:{self.agent_id}] 使用工具调用模式，"
                    f"工具数: {len(self._langchain_tools)}"
                )
                report = self.invoke_with_tools(messages)
            else:
                logger.warning(f"[UniversalAgent:{self.agent_id}] 无工具，直接调用 LLM")
                response = self._llm.invoke(messages)
                report = response.content if hasattr(response, "content") else str(response)
                self._last_llm_debug = {
                    "response_type": type(response).__name__,
                    "final_response_content": report,
                    "tool_mode": False,
                    "tool_trace": list(self._last_tool_debug),
                }

            is_debug_mode = bool(context.get('is_debug_mode', False)) if isinstance(context, dict) else bool(getattr(context, 'is_debug_mode', False)) if context else False
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
            return {self._output_field: f"执行失败: {str(e)}"}

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

请根据用户请求，调用相应工具获取数据，然后撰写详细的分析报告。

全局合规铁律：严禁给出任何交易建议或操作性指令，包括买卖建议、仓位建议、目标价、止损止盈、建仓区间与择时判断。"""

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

