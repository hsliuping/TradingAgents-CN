"""
Agent Builder 工作流节点实现

每个节点负责：
  1. 通过 LLM 与用户沟通
  2. 调用指定的必需工具
  3. 将工具结果写入 state
  4. 更新 current_node / stage

注意：
  - 节点不决定下一步去哪（由条件边决定）
  - 节点不决定哪些工具可用（由图定义决定）
  - LLM 只负责沟通和按节点要求调用工具
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.embedded_nanobot.workflows.agent_builder_state import AgentBuilderState

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 节点内 LLM 调用辅助（基于 UnifiedLLMClient，标准 Function Calling）
# ──────────────────────────────────────────────────────────────

def _convert_messages(messages: List[Dict[str, Any]]) -> List[Any]:
    """把 dict 形式的消息转换为 UnifiedLLMClient 期望的 Message Pydantic 对象。

    从 TradingAgentsLLMProvider._convert_messages 提取，保留 tool_calls 转换。
    """
    from core.llm.models import Message, MessageRole, ToolCall as CoreToolCall

    converted: List[Message] = []
    for msg in messages:
        role = MessageRole(msg.get("role", "user"))
        tool_calls = None
        raw_tool_calls = msg.get("tool_calls") or []
        if raw_tool_calls:
            tool_calls = []
            for item in raw_tool_calls:
                if isinstance(item, dict):
                    function = item.get("function") or {}
                    arguments = function.get("arguments") or {}
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except Exception:
                            arguments = {}
                    tool_calls.append(CoreToolCall(
                        id=str(item.get("id") or ""),
                        name=str(function.get("name") or ""),
                        arguments=arguments if isinstance(arguments, dict) else {},
                    ))
        converted.append(Message(
            role=role,
            content=msg.get("content") if isinstance(msg.get("content"), str) else None,
            name=msg.get("name"),
            tool_call_id=msg.get("tool_call_id"),
            tool_calls=tool_calls,
        ))
    return converted


def _to_openai_tool_schema(tool: Any) -> Optional[Dict[str, Any]]:
    """把 Nanobot Tool 转换为 OpenAI Function Calling 格式。

    Nanobot Tool.to_schema() 返回: {"name": ..., "description": ..., "parameters": ...}
    OpenAI 期望: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    """
    if tool is None:
        return None
    try:
        schema = tool.to_schema()
    except Exception:
        return None
    if not isinstance(schema, dict) or not schema.get("name"):
        return None
    return {
        "type": "function",
        "function": {
            "name": schema.get("name", ""),
            "description": schema.get("description", ""),
            "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
        },
    }


def _collect_tool_schemas(
    tool_registry: Any,
    required_tool_name: Any,
    include_inspect_tools: bool = False,
) -> List[Dict[str, Any]]:
    """收集要传给 LLM 的工具 schema（OpenAI 格式）。"""
    schemas: List[Dict[str, Any]] = []
    if not tool_registry:
        return schemas

    names: List[str] = []
    if isinstance(required_tool_name, list):
        names = [n for n in required_tool_name if n]
    elif required_tool_name:
        names = [required_tool_name]

    for name in names:
        tool = tool_registry.get(name)
        schema = _to_openai_tool_schema(tool)
        if schema:
            schemas.append(schema)

    if include_inspect_tools:
        for inspect_name in ("inspect_agent_workshop_assets", "search_project_capabilities"):
            if inspect_name in names:
                continue
            tool = tool_registry.get(inspect_name)
            schema = _to_openai_tool_schema(tool)
            if schema:
                schemas.append(schema)

    return schemas


async def _stream_chunked(text: str, on_stream: Optional[Callable], chunk_size: int = 40, delay: float = 0.012) -> None:
    """把完整文本按块流式推送（模拟流式效果）。"""
    if not text or not on_stream:
        return
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        try:
            await on_stream(chunk)
        except Exception:
            pass
        if delay > 0:
            await asyncio.sleep(delay)


async def _run_node_tool_first(
    state: AgentBuilderState,
    system_prompt: str,
    tool_registry: Any,
    llm_client: Any,
    required_tool_name: str,
    include_inspect_tools: bool = False,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """工具先行模式（字符串模式）：代码直接调工具 → LLM 总结 → 分块流式推送。

    不让 LLM 决策调哪个工具，从根本上消除 XML 泄露。
    适用于节点已知必须调用某个特定工具的场景（7 个节点用此模式）。
    """
    # 1. 构建工具参数（沿用 _build_force_call_params 的完整逻辑）
    tool_params = _build_force_call_params(required_tool_name, state)

    # 2. 执行工具
    tool_events: List[Dict[str, Any]] = []
    tool_results: Dict[str, Any] = {}

    await _emit_event(event_callback, "tool", f"执行：{required_tool_name}")
    try:
        result = await tool_registry.execute(required_tool_name, tool_params)
        result_str = str(result) if not isinstance(result, str) else result
        tool_results[required_tool_name] = result_str
        tool_events.append({"name": required_tool_name, "params": tool_params, "status": "ok"})
        await _emit_event(event_callback, "tool_done", f"完成：{required_tool_name}")
        logger.info("[NodeToolFirst][Ok] %s len=%d", required_tool_name, len(result_str))
    except Exception as e:
        logger.error("[NodeToolFirst][Error] %s: %s", required_tool_name, e, exc_info=True)
        result_str = f"Error: {e}"
        tool_results[required_tool_name] = result_str
        tool_events.append({"name": required_tool_name, "params": tool_params, "status": "error", "error": str(e)})
        await _emit_event(event_callback, "tool_error", f"失败：{required_tool_name}")

    # 3. LLM 总结（非流式 achat → 分块推送）
    await _emit_event(event_callback, "progress", "正在分析结果...")

    user_msg_content = state.get("user_message", "") or ""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg_content},
        {
            "role": "user",
            "content": (
                f"工具 {required_tool_name} 已执行完成，以下是工具返回结果：\n\n"
                f"{result_str[:6000]}\n\n"
                "请基于以上工具结果，结合用户的需求，给出自然语言回复。"
                "不要输出任何工具调用 XML 或 JSON，只输出对用户说的话。"
            ),
        },
    ]

    try:
        response = await llm_client.achat(
            _convert_messages(messages),
            temperature=0.3,
            auto_execute_tools=False,
        )
        final_text = getattr(response, "content", "") or ""
    except Exception as e:
        logger.error("[NodeToolFirst][LLMError] %s", e, exc_info=True)
        final_text = f"抱歉，处理过程中出现了问题：{e}"

    # 4. 分块流式推送
    await _stream_chunked(final_text, on_stream)

    return final_text, tool_events, tool_results


async def _run_node_llm_fc(
    state: AgentBuilderState,
    system_prompt: str,
    tool_registry: Any,
    llm_client: Any,
    required_tool_name: List[str],
    include_inspect_tools: bool = False,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """LLM Function Calling 模式（列表模式）：标准 FC 协议让 LLM 决策调哪个工具。

    使用 OpenAI 标准 Function Calling，工具调用通过 API 返回（非文本），
    不会产生 XML 泄露。适用于节点需要在多个工具中选择的场景（1 个节点用此模式）。

    注意：UnifiedLLMClient 内部 _tools 字典需要包含 LLM 可能调用的工具函数。
    """
    # 1. 收集工具 schema（OpenAI 格式）
    tool_schemas = _collect_tool_schemas(tool_registry, required_tool_name, include_inspect_tools)
    if not tool_schemas:
        # 没有可用工具，退化为纯 LLM 调用
        return await _run_node_plain(state, system_prompt, llm_client, event_callback, on_stream)

    # 2. 把工具函数注入到 llm_client（UnifiedLLMClient 通过 _tools 字典执行工具）
    tools_to_inject: Dict[str, Callable] = {}
    for name in required_tool_name:
        tool = tool_registry.get(name) if tool_registry else None
        if tool is None:
            continue
        # 优先使用 tool.func / tool.execute / tool.run（取决于 Nanobot Tool 的实现）
        func = None
        for attr in ("func", "execute", "run", "_func", "handler"):
            candidate = getattr(tool, attr, None)
            if callable(candidate):
                func = candidate
                break
        if func is None:
            # 退而求其次：用 tool_registry.execute 包装一个 callable
            async def _wrapped(_name=name, _registry=tool_registry):
                # 注意：这里没法接收参数，仅作占位；实际参数由 aexecute_tool_call 传入
                raise RuntimeError(f"工具 {_name} 缺少可调用的函数句柄，请检查 Tool 实现")
            func = _wrapped
        tools_to_inject[name] = func

    # 临时注入工具到 llm_client（不影响其他请求，因为 _tools 是实例级 dict）
    # 注意：auto_execute_tools=True 时 UnifiedLLMClient 会用 self._tools 执行工具
    try:
        llm_client.inject_tools(tools_to_inject)
    except Exception as e:
        logger.warning("[NodeLLMFC][InjectTools] %s", e)

    # 3. LLM 决策调哪个工具（auto_execute_tools=True，标准 FC 协议）
    user_msg_content = state.get("user_message", "") or ""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg_content},
    ]

    tools_used: List[str] = []
    tool_events: List[Dict[str, Any]] = []
    tool_results: Dict[str, Any] = {}

    async def _progress(payload: Dict[str, Any]) -> None:
        event = payload.get("event", "")
        tool_name = payload.get("tool", "")
        if event == "tool_started" and tool_name:
            await _emit_event(event_callback, "tool", f"执行：{tool_name}")
        elif event == "tool_completed" and tool_name:
            preview = payload.get("preview", "")
            tool_results[tool_name] = preview  # 仅作记录，下面会用 registry.execute 重新获取完整结果
            is_error = payload.get("is_error", False)
            status = "error" if is_error else "ok"
            tool_events.append({"name": tool_name, "params": payload.get("arguments", {}), "status": status})
            tools_used.append(tool_name)
            if is_error:
                await _emit_event(event_callback, "tool_error", f"失败：{tool_name}")
            else:
                await _emit_event(event_callback, "tool_done", f"完成：{tool_name}")

    await _emit_event(event_callback, "progress", "正在分析需求...")

    try:
        response = await llm_client.achat(
            _convert_messages(messages),
            tools=tool_schemas,
            auto_execute_tools=True,
            max_tool_rounds=3,
            tools_used=tools_used,
            dry_run=False,
            progress_callback=_progress,
            temperature=0.3,
        )
        final_text = getattr(response, "content", "") or ""
    except Exception as e:
        logger.error("[NodeLLMFC][LLMError] %s", e, exc_info=True)
        final_text = f"抱歉，处理过程中出现了问题：{e}"

    # 4. 分块流式推送
    await _stream_chunked(final_text, on_stream)

    return final_text, tool_events, tool_results


async def _run_node_plain(
    state: AgentBuilderState,
    system_prompt: str,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """纯 LLM 调用模式：不传任何工具，让 LLM 直接回复。

    用于不需要工具调用的节点（如纯等待/澄清）。
    """
    user_msg_content = state.get("user_message", "") or ""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg_content},
    ]

    try:
        response = await llm_client.achat(
            _convert_messages(messages),
            temperature=0.3,
            auto_execute_tools=False,
        )
        final_text = getattr(response, "content", "") or ""
    except Exception as e:
        logger.error("[NodePlain][LLMError] %s", e, exc_info=True)
        final_text = f"抱歉，处理过程中出现了问题：{e}"

    await _stream_chunked(final_text, on_stream)
    return final_text, [], {}


async def _run_node_llm(
    state: AgentBuilderState,
    system_prompt: str,
    tool_registry: Any,
    llm_client: Any,
    required_tool_name: Any = "",
    include_inspect_tools: bool = False,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """节点 LLM 调用统一入口（基于 UnifiedLLMClient，无 XML 泄露）。

    根据 required_tool_name 类型路由到不同模式：
    - 字符串（非空）：工具先行模式（_run_node_tool_first）
    - 列表：LLM Function Calling 模式（_run_node_llm_fc）
    - 空字符串：纯 LLM 调用模式（_run_node_plain）
    """
    if isinstance(required_tool_name, list) and required_tool_name:
        return await _run_node_llm_fc(
            state, system_prompt, tool_registry, llm_client,
            required_tool_name, include_inspect_tools,
            event_callback, on_stream,
        )
    if required_tool_name and isinstance(required_tool_name, str):
        return await _run_node_tool_first(
            state, system_prompt, tool_registry, llm_client,
            required_tool_name, include_inspect_tools,
            event_callback, on_stream,
        )
    return await _run_node_plain(state, system_prompt, llm_client, event_callback, on_stream)



async def _invoke_stream(callback: Optional[Callable], text: str):
    """安全调用 stream callback。"""
    if callback and text:
        try:
            await callback(text)
        except Exception:
            pass


def _build_force_call_params(tool_name: str, state: AgentBuilderState) -> dict:
    """为强制调用的工具构造最小参数。"""
    user_msg = state.get("user_message", "")
    spec_id = state.get("spec_id", "")

    if tool_name == "prepare_agent_requirement_intake":
        return {"user_request": user_msg}
    if tool_name == "prepare_agent_generation_confirmation":
        # 需要 agent_id, agent_name, target_responsibility, tool_ids
        spec_name = state.get("spec_name", "") or "候选 Agent"
        responsibility = state.get("requirement_summary", "") or spec_name
        proposed_plan = state.get("proposed_plan", {}) or {}
        preferred_tools = proposed_plan.get("preferred_tools", "")
        if isinstance(preferred_tools, list):
            tool_ids = ",".join(str(t) for t in preferred_tools if t)
        elif isinstance(preferred_tools, str) and preferred_tools and "（" not in preferred_tools:
            tool_ids = preferred_tools
        else:
            tool_ids = ""
        # 优先使用 state 中的 spec_id（英文 slug），没有则从名称生成
        agent_id = state.get("spec_id", "")
        if not agent_id:
            from core.tools.implementations.agent_builder.nanobot_agent_builder_tools import _fallback_slug_from_name
            agent_id = _fallback_slug_from_name(spec_name, state.get("original_user_request", ""), responsibility)
        return {
            "agent_id": agent_id,
            "agent_name": spec_name,
            "target_responsibility": responsibility,
            "tool_ids": tool_ids,
        }
    if tool_name == "analyze_agent_workshop_gaps":
        # analyze_agent_workshop_gaps 优先复用当前工坊 session，确保重跑的是当前 Agent 的能力缺口分析。
        session_id = str(state.get("workshop_session_id") or "").strip()
        if session_id:
            return {"session_id": session_id}
        spec_name = state.get("spec_name", "") or "候选 Agent"
        responsibility = state.get("requirement_summary", "") or spec_name
        agent_id = state.get("spec_id", "")
        if not agent_id:
            from core.tools.implementations.agent_builder.nanobot_agent_builder_tools import _fallback_slug_from_name
            agent_id = _fallback_slug_from_name(spec_name, state.get("original_user_request", ""), responsibility)
        return {
            "agent_id": agent_id,
            "agent_name": spec_name,
            "target_responsibility": responsibility,
        }
    if tool_name == "propose_agent_build_plans":
        # propose_agent_build_plans 只接受 gap_report_json / agent_responsibility / agent_output_shape
        gap_report = state.get("gap_report", {}) or {}
        # 如果 gap_report 是错误响应，当作空处理，让工具走 fallback
        if isinstance(gap_report, dict) and gap_report.get("status") == "error":
            gap_report = {}
        responsibility = state.get("requirement_summary", "") or state.get("spec_name", "")
        return {
            "gap_report_json": json.dumps(gap_report, ensure_ascii=False) if gap_report else "{}",
            "agent_responsibility": responsibility,
        }
    if tool_name == "generate_confirmed_candidate_agent":
        # 从 state 中重建必需参数
        original_request = state.get("original_user_request", "") or user_msg
        spec_name = state.get("spec_name", "") or original_request[:30]
        responsibility = state.get("requirement_summary", "") or spec_name
        candidate_plans = state.get("candidate_plans", []) or []
        selected_plan_id = state.get("selected_plan_id", "direct")
        gap_report = state.get("gap_report", {}) or {}
        if not isinstance(gap_report, dict):
            gap_report = {}

        # 注意：required_new_skills 是"需要新建的能力描述"，不是已注册的 tool_id
        # 不能直接作为 tool_ids 传给 bind_agent_tools_and_validate_candidate
        # 应该从 gap_report.existing_tools / suggested_tools 中提取真实 tool_id

        # 优先从 gap_report.existing_tools 提取（这些是已注册的可用工具）
        tool_ids = ""
        existing_tools = gap_report.get("existing_tools", []) or []
        if isinstance(existing_tools, list) and existing_tools:
            # existing_tools 格式可能是 "tool_id | 描述" 或纯 "tool_id"
            ids: list[str] = []
            for item in existing_tools:
                text = str(item or "").strip()
                if not text:
                    continue
                # 提取 | 之前的 tool_id 部分
                if "|" in text:
                    tid = text.split("|", 1)[0].strip()
                else:
                    tid = text
                if tid:
                    ids.append(tid)
            if ids:
                tool_ids = ",".join(ids[:8])  # 最多 8 个

        # 如果 existing_tools 为空，尝试从 suggested_tools 提取 tool_id
        if not tool_ids:
            suggested_tools = gap_report.get("suggested_tools", []) or []
            if isinstance(suggested_tools, list):
                ids = []
                for item in suggested_tools:
                    if isinstance(item, dict):
                        tid = str(item.get("tool_id") or "").strip()
                        if tid:
                            ids.append(tid)
                    elif isinstance(item, str):
                        if item.strip():
                            ids.append(item.strip())
                if ids:
                    tool_ids = ",".join(ids[:5])

        # 兜底：使用 search_project_capabilities（始终可用，让 Agent 至少能查能力）
        if not tool_ids:
            tool_ids = "search_project_capabilities"
            logger.warning("[GenAgent][ForceParams] 无可用工具，兜底使用 search_project_capabilities")

        # 生成 agent_id：优先使用 state 中的 spec_id（由 prepare_agent_requirement_intake /
        # prepare_agent_generation_confirmation 设置），避免意图漂移检测报错。
        # 只有 spec_id 为空时才用 slug 兜底。
        agent_id = spec_id
        if not agent_id:
            from core.tools.implementations.agent_builder.nanobot_agent_builder_tools import _fallback_slug_from_name
            agent_id = _fallback_slug_from_name(spec_name, original_request, responsibility)

        system_prompt = (
            f"你是一名专注于 {responsibility} 的财经分析助手。"
            f"基于用户的原始需求「{original_request}」，使用平台提供的工具获取真实数据，"
            f"输出结构化分析报告，包含核心判断、关键依据和风险提示。"
        )

        # 序列化 gap_report 供 direct/complete/quick 方案使用
        gap_report_json = json.dumps(gap_report, ensure_ascii=False) if gap_report else "{}"

        # 提取 blocking_gaps 作为 acknowledged_gaps
        # 语义：用户选择方案即表示知晓并接受这些缺口（force-call 场景下无独立确认步骤）
        blocking_gaps_list = gap_report.get("blocking_gaps", []) or []
        if isinstance(blocking_gaps_list, list):
            ack_gaps = [str(g or "").strip() for g in blocking_gaps_list if str(g or "").strip()]
        else:
            ack_gaps = []
        acknowledged_gaps_json = json.dumps(ack_gaps, ensure_ascii=False) if ack_gaps else ""

        logger.info(
            "[GenAgent][ForceParams] plan=%s tool_ids=%s gap_report_keys=%s ack_gaps=%d",
            selected_plan_id, tool_ids, list(gap_report.keys()) if gap_report else [], len(ack_gaps),
        )

        return {
            "agent_id": agent_id,
            "agent_name": spec_name,
            "target_responsibility": responsibility,
            "tool_ids": tool_ids,
            "system_prompt": system_prompt,
            "selected_plan_id": selected_plan_id,
            "confirmed": True,
            "allow_overwrite": True,  # force-call 场景下允许覆盖（避免历史脏数据阻塞）
            "gap_report_json": gap_report_json,
            "acknowledged_gaps": acknowledged_gaps_json,
        }
    if tool_name == "build_agent_workshop_version":
        # 需要 session_id，从 state 中获取
        return {"session_id": state.get("workshop_session_id", "")}
    if tool_name == "run_agent_workshop_real_data_test":
        # 需要 version_id 和 stock_symbol
        version_id = _sanitize_version_id(state.get("version_id", ""))
        test_symbol = state.get("test_symbol", "")
        # 从用户消息中尝试提取股票代码（兜底）
        if not test_symbol:
            msg = state.get("user_message", "")
            m = re.search(r"\b(00\d{4}|30\d{4}|60\d{4}|68\d{4})\b", msg)
            if m:
                test_symbol = m.group(1)
                state["test_symbol"] = test_symbol
        return {
            "version_id": version_id,
            "stock_symbol": test_symbol,
            "market_type": "A股",
        }
    if tool_name == "publish_agent_workshop_version":
        # 需要 version_id
        return {"version_id": _sanitize_version_id(state.get("version_id", ""))}
    if tool_name == "evaluate_agent_workshop_version":
        # 需要 version_id
        return {"version_id": _sanitize_version_id(state.get("version_id", ""))}
    if tool_name == "iterate_agent_workshop_version":
        return {
            "version_id": _sanitize_version_id(state.get("version_id", "")),
            "feedback": state.get("user_message", "") or "升级需求",
        }
    return {}


async def _emit_event(callback: Optional[Callable], event_type: str, label: str, payload: Any = None):
    """发送事件到 SSE 流。"""
    if callback:
        try:
            await callback(event_type, label, payload)
        except Exception:
            pass


def _is_confirm_like(msg: str) -> bool:
    """判断消息是否像确认/认可。"""
    t = (msg or "").strip().lower()
    if not t:
        return False
    confirm_keywords = ("确认", "好的", "可以", "行", "没问题", "ok", "yes", "确认无误", "同意")
    return any(kw in t for kw in confirm_keywords)


def _extract_json_from_result(result_str: str) -> dict:
    """从工具结果字符串中提取 JSON。"""
    if not result_str:
        return {}
    try:
        return json.loads(result_str)
    except json.JSONDecodeError:
        # 尝试提取 JSON 块
        m = re.search(r'\{[\s\S]*\}', result_str)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {}


def _sanitize_version_id(value: Any) -> str:
    """清洗 version_id，确保返回干净的 version_id 字符串。

    防御性处理：当 build_agent_workshop_version 工具未及时修复时，
    version_id 可能被 json.dumps(default=str) 转成 Pydantic 对象的 str repr，
    形如 "id=ObjectId('...') version_id='agent_xxx_v1' spec_id='...' ..."。
    这里从这种 repr 中提取真正的 version_id。
    """
    if value is None:
        return ""
    # dict：直接取 version_id 字段
    if isinstance(value, dict):
        return str(value.get("version_id") or "").strip()
    text = str(value).strip()
    if not text:
        return ""
    # 检测是否是对象 repr（包含 version_id= 或 ObjectId( 标记）
    if "version_id=" in text or "ObjectId(" in text:
        # 尝试提取 version_id='...' 或 version_id="..."
        m = re.search(r"version_id=['\"]([^'\"]+)['\"]", text)
        if m:
            return m.group(1).strip()
        # 兜底：如果整个字符串不像 version_id（含空格/等号/括号），返回空
        if "=" in text or "(" in text or " " in text:
            logger.warning(
                "[SanitizeVersionId] version_id 看起来是对象 repr，无法提取: %s",
                text[:200],
            )
            return ""
    return text


# ──────────────────────────────────────────────────────────────
# 节点函数
# ──────────────────────────────────────────────────────────────

async def node_classify_user_intent(
    state: AgentBuilderState,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """LLM 意图分类节点（v2：拓扑感知 + 置信度 + 按节点定制提示词）。

    根据 current_node 选择不同提示词，让 LLM 关注当前阶段核心问题。
    confidence < 0.7 时由 route_after_classify 触发 clarification_needed。
    """
    current_node = state.get("current_node", "")
    msg = state.get("user_message", "") or ""

    # ── 积累对话历史（最近 N 轮） ──
    history = state.setdefault("message_history", [])
    prev_response = state.get("final_response", "") or ""
    if prev_response and history and history[-1].get("role") == "user":
        # 上一步的 agent 回复还没记录 → 补上
        pass  # 不重复插入，分类时统一追加
    if msg:
        if prev_response:
            history.append({"role": "agent", "content": prev_response})
        history.append({"role": "user", "content": msg})
        # 限制最近 20 条（10 轮）
        if len(history) > 20:
            state["message_history"] = history[-20:]

    node_type = _classify_node_type(current_node)
    classify_prompt = _build_classify_prompt(state, node_type)

    # ── 意图分类提示词日志（调试用）──
    _log_intent_classify_prompt(node_type, classify_prompt, msg)

    messages = [
        {"role": "system", "content": "你是意图分类器，只输出 JSON。"},
        {"role": "user", "content": classify_prompt},
    ]

    try:
        response = await llm_client.achat(
            _convert_messages(messages),
            temperature=0.0,
            auto_execute_tools=False,
        )
        raw = getattr(response, "content", "") or ""
        result = _extract_json_from_result(raw)
        if not result or "intent" not in result:
            # 兜底：用极简规则
            intent = _fallback_classify_intent(msg, current_node)
            result = {"intent": intent, "confidence": 0.3, "reason": "LLM fallback"}
            logger.warning(
                "[ClassifyIntent][Fallback] LLM 返回无法解析: %s, 使用兜底: %s",
                raw[:200], intent,
            )

        if _is_rerun_gap_analysis_request(msg):
            result = {
                "intent": "rerun_gap",
                "confidence": 0.98,
                "reason": "用户明确要求重新执行 Agent 工坊能力缺口分析",
            }
        elif _is_regenerate_plan_request(msg):
            result = {
                "intent": "regenerate_plan",
                "confidence": 0.95,
                "reason": "用户要求基于当前能力缺口重新生成候选解决方案",
            }

        state["user_intent"] = result.get("intent", "explore_more")
        state["intent_confidence"] = float(result.get("confidence", 0.0))
        state["intent_reason"] = str(result.get("reason", "") or "")

        if state["user_intent"] == "rerun_gap":
            state["gap_report"] = {}
            state["candidate_plans"] = []
            state["pending_options"] = []
            state["selected_plan_id"] = ""
            state["clarification_needed"] = False
        elif state["user_intent"] == "regenerate_plan":
            state["candidate_plans"] = []
            state["pending_options"] = []
            state["selected_plan_id"] = ""
            state["clarification_needed"] = False

        if result.get("selected_index"):
            state["user_selected_index"] = int(result["selected_index"])
        elif result.get("selected_id"):
            state["user_selected_id"] = str(result["selected_id"])

        # LLM 从上下文中推断的测试股票代码
        if result.get("test_symbol"):
            state["test_symbol"] = str(result["test_symbol"]).strip()

        if state.get("user_intent") == "retry":
            state["test_result"] = {}
            state["official_acceptance_decision"] = ""
            state["final_response"] = ""
            state["tool_events"] = []
            state["clarification_needed"] = False

        # ── 股票名 → 代码解析 ──
        # 如果 test_symbol 不是 6 位数字代码（是股票名如"科大讯飞"），尝试解析成代码。
        # 先查 hardcoded 常见股票映射表，查不到再用 LLM 解析。
        test_symbol = state.get("test_symbol", "")
        if test_symbol and not re.match(r"^\d{6}$", test_symbol):
            resolved = _resolve_stock_name_to_code(test_symbol)
            if resolved:
                logger.info(
                    "[ClassifyIntent][NameResolve] test_symbol '%s' → '%s'",
                    test_symbol, resolved,
                )
                state["test_symbol"] = resolved
            else:
                # 解析失败：清空 test_symbol，让 wait_test_request 输出"请提供股票代码"提示
                logger.warning(
                    "[ClassifyIntent][NameResolve] 无法解析 test_symbol='%s'，"
                    "清空并触发澄清提示", test_symbol,
                )
                state["test_symbol"] = ""

        # ── 兜底：wait_test_request 节点 + confirmed/retry 意图但没 test_symbol ──
        # 防御 LLM 没按提示词要求输出 test_symbol 字段的情况。
        # 从 message_history / final_response 中提取 Agent 最近建议的股票代码填入。
        if (
            current_node in ("wait_test_request", "generate_candidate_agent", "wait_evaluation", "evaluate_or_publish")
            and state.get("user_intent") in ("confirmed", "retry", "select_option")
            and not state.get("test_symbol")
        ):
            fallback_code = ""
            # 换股重测时，优先从用户本轮消息解析股票名/代码。
            if state.get("user_intent") == "retry":
                fallback_code = _resolve_stock_name_to_code(msg)
            if not fallback_code:
                fallback_code = _extract_suggested_stock_from_state(state)
            if fallback_code:
                state["test_symbol"] = fallback_code
                logger.info(
                    "[ClassifyIntent][FallbackSymbol] LLM 未输出 test_symbol，"
                    "从历史中提取到建议代码: %s", fallback_code,
                )

        logger.info(
            "[ClassifyIntent] node=%s type=%s msg=%.60s → intent=%s confidence=%.2f reason=%s",
            current_node, node_type, msg, state["user_intent"],
            state["intent_confidence"], state["intent_reason"][:80],
        )

        # ── 意图分类结果日志（与提示词配对）──
        _log_intent_classify_result(
            node_type, state["user_intent"], state["intent_confidence"],
            state["intent_reason"], raw, result,
        )
    except Exception as e:
        logger.error("[ClassifyIntent][Error] %s, 使用兜底", e, exc_info=True)
        state["user_intent"] = _fallback_classify_intent(msg, current_node)
        state["intent_confidence"] = 0.0
        state["intent_reason"] = f"LLM error: {e}"

    # ── 预判：本轮意图是否会让流程"停留在原地"（无法推进）──
    # 条件函数对 state 的修改不会持久化到节点，所以在这里（节点内）
    # 预先计算 clarification_needed，供 wait 节点输出澄清提示，
    # 避免把上一轮的内容重复输出一遍。
    # 注意：低置信度（<0.7）会在 route_after_classify 中触发 clarification_needed，
    # 这里不重复设置。
    intent = state["user_intent"]
    if state.get("intent_confidence", 0.0) >= 0.7:
        state["clarification_needed"] = _will_stay_on_wait_node(state)
    else:
        # 低置信度：不预判，由 route_after_classify 统一处理
        state["clarification_needed"] = False

    # ── 错误恢复阶段的特殊处理 ──
    # 如果用户意图是 actionable（confirmed/retry/select_option），
    # 说明用户想重试，需要清除旧错误标记。
    # 必须在节点内做（路由函数的 state 修改不持久化）。
    if current_node == "error_recovery" and intent in ("confirmed", "retry", "select_option"):
        errors = state.get("errors", []) or []
        if errors:
            state["errors"] = errors[:-1] if len(errors) > 1 else []
            logger.info(
                "[ClassifyIntent] error_recovery retry: 清除旧错误, "
                "remaining=%d", len(state.get("errors", [])),
            )

    return state


def _classify_node_type(current_node: str) -> str:
    """将节点名映射到意图分类的节点类型，每种类型有独立提示词。"""
    if current_node in ("wait_intake_confirmation", "wait_requirement_confirmation"):
        return "confirmation"
    if current_node == "wait_plan_selection":
        return "plan_selection"
    if current_node in ("wait_test_request", "wait_evaluation", "evaluate_or_publish", "generate_candidate_agent"):
        return "test_eval"
    if current_node == "error_recovery":
        return "error"
    return "generic"


def _extract_suggested_stock_from_state(state: AgentBuilderState) -> str:
    """从 message_history / final_response 中提取 Agent 最近建议的股票代码。

    用于 wait_test_request 节点的兜底：当 LLM 分类结果没有 test_symbol 字段，
    但用户回复是确认/同意语气时，从历史中找最近一条含股票代码的 agent 回复。
    """
    history = state.get("message_history", []) or []
    candidates = list(reversed(history))
    prev_resp = state.get("final_response", "") or ""
    if prev_resp:
        candidates.insert(0, {"role": "agent", "content": prev_resp})
    for entry in candidates:
        if not isinstance(entry, dict) or entry.get("role") != "agent":
            continue
        content = str(entry.get("content", ""))
        m = re.search(r"\b(00\d{4}|30\d{4}|60\d{4}|68\d{4}|6\d{4})\b", content)
        if m:
            return m.group(1)
    return ""


def _resolve_stock_name_to_code(query: str) -> str:
    """通过本地股票基础信息集合把股票名称/代码解析为 6 位股票代码。"""
    text = str(query or "").strip()
    if not text:
        return ""
    m = re.search(r"\b(00\d{4}|30\d{4}|60\d{4}|68\d{4}|6\d{4})\b", text)
    if m:
        return m.group(1)

    # 清理常见口语词，保留股票名关键词。
    keyword = re.sub(r"(换|一个|股票|测试|一下|重测|再测|用|的|代码|证券)", "", text).strip()
    keyword = keyword or text
    if not keyword:
        return ""

    try:
        from core.skill_runtime.project_access import query_stock_collection

        escaped = re.escape(keyword)
        projection = {"_id": 0, "code": 1, "symbol": 1, "name": 1, "source": 1}
        docs = query_stock_collection(
            "stock_basic_info",
            filters={
                "$or": [
                    {"name": keyword},
                    {"name": {"$regex": escaped, "$options": "i"}},
                    {"code": keyword},
                    {"symbol": keyword},
                ]
            },
            projection=projection,
            limit=20,
        )
        if not docs:
            return ""

        def _score(doc: Dict[str, Any]) -> tuple[int, int]:
            name = str(doc.get("name") or "")
            source = str(doc.get("source") or "")
            exact = 1 if name == keyword else 0
            preferred_source = 1 if source in ("tushare", "multi_source", "akshare", "baostock") else 0
            return (exact, preferred_source)

        best = sorted(docs, key=_score, reverse=True)[0]
        code = str(best.get("code") or best.get("symbol") or "").strip()
        code_match = re.search(r"\d{6}", code)
        if code_match:
            return code_match.group(0)
    except Exception as exc:
        logger.warning("[ResolveStockName] 查询 stock_basic_info 失败: %s", exc)
    return ""


# ── 意图分类提示词日志 ──

_INTENT_PROMPT_LOGGER: Optional[logging.Logger] = None
_INTENT_PROMPT_LOG_PATH: str = ""


def _get_intent_prompt_logger() -> logging.Logger:
    """获取意图分类提示词专用 logger，写入独立的日志文件。"""
    global _INTENT_PROMPT_LOGGER, _INTENT_PROMPT_LOG_PATH
    if _INTENT_PROMPT_LOGGER is not None:
        return _INTENT_PROMPT_LOGGER

    from pathlib import Path
    logs_dir = Path(__file__).resolve().parents[3] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    _INTENT_PROMPT_LOG_PATH = str(logs_dir / "intent_classify_prompts.log")

    _INTENT_PROMPT_LOGGER = logging.getLogger("intent_classify_prompts")
    _INTENT_PROMPT_LOGGER.setLevel(logging.DEBUG)
    _INTENT_PROMPT_LOGGER.propagate = False  # 不污染 root logger

    # 如果已有 handler 则不再重复添加
    if not any(isinstance(h, logging.FileHandler) for h in _INTENT_PROMPT_LOGGER.handlers):
        handler = logging.FileHandler(_INTENT_PROMPT_LOG_PATH, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "\n" + "=" * 80 + "\n[%(asctime)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        _INTENT_PROMPT_LOGGER.addHandler(handler)

    return _INTENT_PROMPT_LOGGER


def _log_intent_classify_prompt(node_type: str, prompt: str, user_msg: str):
    """将意图分类的完整提示词写入独立日志文件。"""
    try:
        log = _get_intent_prompt_logger()
        sep = "-" * 60
        log.debug(
            "node_type=%s\n"
            "user_message=%s\n"
            "%s\n"
            "%s\n"
            "%s",
            node_type,
            user_msg,
            sep,
            prompt,
            sep,
        )
    except Exception:
        pass  # 日志失败不影响主流程


def _log_intent_classify_result(
    node_type: str, intent: str, confidence: float,
    reason: str, raw_response: str, parsed: dict,
):
    """将意图分类的结果写入独立日志文件（与提示词在同一个文件，紧挨着）。"""
    try:
        log = _get_intent_prompt_logger()
        log.debug(
            ">>> 分类结果: intent=%s confidence=%.2f reason=%s\n"
            ">>> LLM 原始响应: %s",
            intent, confidence, reason,
            raw_response[:500] if raw_response else "(empty)",
        )
    except Exception:
        pass


def _format_recent_history(state: AgentBuilderState, rounds: int = 3) -> str:
    """从 message_history 中取最近 N 轮对话，格式化为 prompt 可用的文本。"""
    history = state.get("message_history", []) or []
    recent = history[-(rounds * 2):]  # 每轮 = agent + user
    if not recent:
        return "（暂无对话历史）"
    lines = []
    for entry in recent:
        role = entry.get("role", "unknown")
        content = str(entry.get("content", ""))[-5000:]
        label = "Agent" if role == "agent" else "用户" if role == "user" else role
        lines.append(f"[{label}] {content}")
    return "\n".join(lines)


def _is_rerun_gap_analysis_request(message: str) -> bool:
    """判断用户是否要求重跑 Agent 工坊能力缺口分析。"""
    text = str(message or "").strip().lower()
    if not text:
        return False
    has_gap_word = any(word in text for word in ("gap", "缺口", "能力缺口"))
    has_rerun_word = any(word in text for word in ("重新", "重跑", "再做", "再跑", "重做", "刷新", "rerun", "re-run"))
    has_analysis_word = any(word in text for word in ("分析", "盘点", "检查", "扫描"))
    return has_gap_word and has_rerun_word and has_analysis_word


def _is_regenerate_plan_request(message: str) -> bool:
    """判断用户是否要求基于当前 gap 重新生成候选解决方案。"""
    text = str(message or "").strip().lower()
    if not text:
        return False
    has_regen_word = any(word in text for word in ("重新", "重跑", "再做", "再生成", "重做", "刷新", "rerun", "re-run"))
    has_plan_word = any(word in text for word in ("方案", "解决方案", "候选方案", "plan", "plans"))
    return has_regen_word and has_plan_word



def _build_intent_shared_context(state: AgentBuilderState, node_type: str) -> str:
    """构建所有意图分类提示词共用的业务背景。"""
    current_node = state.get("current_node", "") or "START"
    spec_name = state.get("spec_name", "") or "未命名 Agent"
    stage = state.get("stage", "") or "未知阶段"
    user_message = state.get("user_message", "") or ""
    awaiting_user = bool(state.get("awaiting_user"))

    workflow_steps = """
1. 需求探索：理解用户想创建/迭代什么 Agent，形成初步需求草案。
2. 需求确认：确认 Agent 名称、职责边界、输入输出和不要做的事情。
3. 能力缺口分析：检查平台已有工具/Skill 是否足够支撑该 Agent。
4. 方案选择：让用户选择推荐方案、精简方案或其他构建路径。
5. Agent 生成/构建：生成候选 Agent 配置、Prompt、工具绑定和版本。
6. 真实数据测试：用用户指定的股票代码或股票名称跑一次真实样例。
7. 测试评估/发布：用户决定发布、换股票重测、修改 Agent 或结束。
""".strip()

    return f"""## 项目与业务背景
你是 TradingAgentsCN「Agent 工坊」里的意图分类器，不是普通聊天助手。
Agent 工坊用于帮助用户创建或迭代一个可运行的财经分析 Agent：从需求澄清、能力匹配、方案选择、生成构建、真实数据测试，到发布评估。

## 当前会话对象
- 正在处理的 Agent：{spec_name}
- 当前节点：{current_node}
- 当前阶段：{stage}
- 节点类型：{node_type}
- 是否正在等待用户输入：{awaiting_user}
- 用户本轮原话：{user_message}

## Agent 工坊标准流程
{workflow_steps}

## 分类原则
- 必须结合「当前节点 + 用户本轮原话 + 最近三轮对话历史 + 当前可选动作」判断用户真实意图。
- 用户的短回复（如“可以”“继续”“换一个”“按默认”“开始吧”）通常必须回看上一轮 Agent 问了什么，不能孤立理解。
- 区分“修改 Agent 设计”和“只换测试数据”：换股票测试是 retry，不是 revise。
- 区分“继续当前 Agent 流程”和“创建全新 Agent”：只有用户明确换成完全不同 Agent 主题时才是 new_agent。
- 在 Agent 工坊上下文中，用户说“gap / 缺口 / gap 分析”默认指“Agent 能力缺口分析/工具能力盘点”，不是股票 K 线里的跳空缺口；只有用户明确说“股价缺口/跳空缺口/K线缺口/走势图缺口”才按技术形态理解。
- 用户说“重新做/重跑/刷新 gap 分析”表示要对当前 Agent 重新执行能力缺口分析，意图应为 rerun_gap。
- 用户说“重新生成/刷新解决方案/候选方案/方案”表示基于当前 gap_report 重新生成候选构建方案，意图应为 regenerate_plan。
- 你只做意图分类和必要字段提取，不输出面向用户的解释。
"""


def _build_classify_prompt(state: AgentBuilderState, node_type: str) -> str:
    """根据节点类型选择定制化的意图分类提示词。"""
    if node_type == "confirmation":
        return _build_confirmation_prompt(state)
    elif node_type == "plan_selection":
        return _build_plan_selection_prompt(state)
    elif node_type == "test_eval":
        return _build_test_eval_prompt(state)
    elif node_type == "error":
        return _build_error_prompt(state)
    else:
        return _build_generic_prompt(state)


def _build_confirmation_prompt(state: AgentBuilderState) -> str:
    """需求确认阶段的意图分类提示词。主要关注：是否确认推进、是否修改需求。"""
    node = state.get("current_node", "")
    pending_q = state.get("pending_question", "") or ""
    msg = state.get("user_message", "") or ""
    spec_name = state.get("spec_name", "") or "未命名"
    recent_history = _format_recent_history(state, rounds=3)
    shared_context = _build_intent_shared_context(state, "confirmation")

    node_desc = {
        "wait_intake_confirmation": "需求探索阶段，Agent 刚提了需求草案和关键问题",
        "wait_requirement_confirmation": "需求确认阶段，Agent 刚确认了职责边界和输出形态",
    }.get(node, f"等待用户确认（{node}）")

    return f"""你是意图分类器。用户在 Agent 构建流程的需求确认阶段。

{shared_context}

## 当前节点
{node_desc}
上一条待确认问题：{pending_q}
Agent 名称：{spec_name}

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：用户确认，可以推进下一步（如"好的""可以""确认""没问题""就这样"）
- revise：用户要修改/补充需求（如"加一个维度""改输出格式""换个方向"）
- rerun_gap：重新执行当前 Agent 的能力缺口分析/工具能力盘点
- regenerate_plan：重新生成候选解决方案/构建方案
- explore_more：探讨/提问，没有明确推进指令
- cancel：取消/结束

## 输出格式（严格 JSON）
{{"intent": "confirmed|revise|rerun_gap|explore_more|cancel", "confidence": 0.85, "reason": "结合对话历史判断用户意图"}}

只输出 JSON。"""


def _build_plan_selection_prompt(state: AgentBuilderState) -> str:
    """方案选择阶段的意图分类提示词。主要关注：用户选了哪个方案。"""
    msg = state.get("user_message", "") or ""
    pending_options = state.get("pending_options", []) or []
    spec_name = state.get("spec_name", "") or "未命名"
    recent_history = _format_recent_history(state, rounds=3)
    shared_context = _build_intent_shared_context(state, "plan_selection")

    opts_lines = []
    for opt in pending_options:
        idx = opt.get("index", "")
        label = opt.get("name", opt.get("id", ""))
        rec = "（推荐）" if opt.get("recommended") else ""
        opts_lines.append(f"  {idx}. {label}{rec}")
    opts_desc = "\n".join(opts_lines)

    options_json = json.dumps(
        [{"index": o.get("index", ""), "id": o.get("id", "")} for o in pending_options],
        ensure_ascii=False,
    ) if pending_options else "[]"

    return f"""你是意图分类器。用户在 Agent 构建流程的方案选择阶段。

{shared_context}

## 当前节点
Agent「{spec_name}」的方案已生成，等待用户选择。

可选方案：
{opts_desc}

方案 index → id 映射：
{options_json}

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- select_option：用户选了某个方案（如"B""方案B""第二个""选A"）→ 输出 selected_index 或 selected_id
- confirmed：用户说"确认""推荐""按默认"→ 使用推荐方案
- revise：用户想修改需求，回到需求阶段
- rerun_gap：重新执行当前 Agent 的能力缺口分析/工具能力盘点
- explore_more：用户问问题但没有选择
- cancel：取消

## 输出格式（严格 JSON）
{{"intent": "select_option", "confidence": 0.95, "reason": "用户说了'B'", "selected_index": 2}}
或 {{"intent": "confirmed", "confidence": 0.9, "reason": "用户说按推荐的来"}}
或 {{"intent": "rerun_gap", "confidence": 0.95, "reason": "用户要求重新做能力缺口分析"}}

只输出 JSON。"""


def _build_test_eval_prompt(state: AgentBuilderState) -> str:
    """测试/评估阶段的意图分类提示词。

    主要关注：股票代码提取、发布 vs 重测 vs 修改 vs 新建 Agent。
    """
    current_node = state.get("current_node", "")
    msg = state.get("user_message", "") or ""
    spec_name = state.get("spec_name", "") or "未命名"
    published = "已发布" if state.get("official_acceptance_decision") == "published" else "未发布"
    test_status = state.get("test_result", {}).get("status", "未测试")
    recent_history = _format_recent_history(state, rounds=3)
    shared_context = _build_intent_shared_context(state, "test_eval")

    # 从历史中提取 Agent 建议的股票代码
    # 注意：generate_candidate_agent 节点的回复可能很长，600519 可能出现在回复中后部，
    # 不能用 content[:120] 截断，否则会丢失股票代码。
    # 同时，generate_candidate_agent 之后会经过 build_or_ready 节点（覆盖 final_response），
    # 因此需要从整个 message_history 中反向查找最近一条含股票代码的 agent 回复。
    last_hint_code = ""
    last_hint_snippet = ""
    if current_node in ("wait_test_request", "generate_candidate_agent"):
        history = state.get("message_history", []) or []
        # 也检查 state["final_response"]（上一轮 agent 回复，可能还没进入 history）
        candidates = list(reversed(history))
        prev_resp = state.get("final_response", "") or ""
        if prev_resp:
            candidates.insert(0, {"role": "agent", "content": prev_resp})
        for entry in candidates:
            if entry.get("role") != "agent":
                continue
            content = str(entry.get("content", ""))
            m = re.search(r"\b(00\d{4}|30\d{4}|60\d{4}|68\d{4}|6\d{4})\b", content)
            if m:
                last_hint_code = m.group(1)
                # 提取代码附近的上下文（前 80 字符 + 代码 + 后 80 字符），保留语义
                start = max(0, m.start() - 80)
                end = min(len(content), m.end() + 80)
                last_hint_snippet = content[start:end].replace("\n", " ").strip()
                break

    if last_hint_code:
        last_hint = (
            f"\n**Agent 最近建议了股票代码：{last_hint_code}**"
            f"（上下文：「...{last_hint_snippet}...」）\n"
            f"**关键规则**：如果用户回复是确认/同意/开始测试等肯定语气"
            f"（如「可以」「好的」「开始吧」「试跑」「开始测试」「按建议」），"
            f"应判定 intent=confirmed，并**必须**输出 test_symbol=\"{last_hint_code}\"。"
        )
    else:
        last_hint = ""

    node_context = {
        "wait_test_request": (
            f"Agent「{spec_name}」已就绪，等待用户给出测试标的。{last_hint}\n"
            f"用户可能：直接给代码（如 600519）；确认 Agent 建议的代码；给股票名但没代码；问问题；取消。"
        ),
        "wait_evaluation": (
            f"Agent「{spec_name}」测试已完成（状态={test_status}），发布状态={published}。\n"
            f"用户可能：发布上线；换股票重测；升级/修改 Agent 设计；重新做能力缺口分析；重新生成候选解决方案；新建其他 Agent；咨询问题；取消。"
        ),
        "evaluate_or_publish": (
            f"Agent「{spec_name}」正在评估阶段，测试状态={test_status}。\n"
            f"用户可能：发布/继续评估；重新测试；升级/修改需求；重新做能力缺口分析；重新生成候选解决方案；新建其他 Agent；咨询问题；取消。"
        ),
    }.get(current_node, f"Agent「{spec_name}」，节点={current_node}")

    return f"""你是意图分类器。用户在 Agent 构建流程的测试/评估阶段。

{shared_context}

## 当前节点
{node_context}

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：用户确认推进（发布/开始测试等）
- retry：换数据重测，Agent 设计不变（如"换科大讯飞再测""用茅台跑一下""重测"）
- revise：修改 Agent 设计（如"加一个现金流维度""改输出格式"）
- new_agent：用户描述的 Agent 与「{spec_name}」完全不同，想创建新 Agent
- rerun_gap：重新执行当前 Agent 的能力缺口分析/工具能力盘点（如"重新做一下gap分析吧""刷新能力缺口"）
- regenerate_plan：基于当前 gap_report 重新生成候选解决方案/构建方案（如"重新生成解决方案""刷新候选方案"）
- explore_more：探讨/提问，无明确操作指令
- cancel：取消/结束

## 关键区分
- "换一只股票测" → retry（只换测试数据，不改 Agent）
- "再加一个维度的分析" → revise（改 Agent 设计）
- "新建一个舆情分析Agent" → new_agent（全新 Agent，和当前无关）

- "重新做一下 gap 分析" → rerun_gap（当前 Agent 工坊能力缺口分析，不是股票技术缺口）
- "重新生成解决方案" → regenerate_plan（不重跑 gap，只基于当前 gap_report 重新生成候选方案）

## 输出格式（严格 JSON）
{{"intent": "confirmed|retry|revise|rerun_gap|regenerate_plan|new_agent|explore_more|cancel", "confidence": 0.85, "reason": "简短推理"}}

**重要**：
- 如果用户消息含有股票代码（如 600519），或确认了 Agent 上一轮建议的代码，额外输出：
  {{"intent": "confirmed", "confidence": 0.95, "reason": "用户给了代码/确认建议代码", "test_symbol": "600519"}}
- 如果用户要求换股票重测（retry 意图），且消息中含股票代码（如 002230），**必须**输出 test_symbol 字段：
  {{"intent": "retry", "confidence": 0.95, "reason": "用户要求换股重测", "test_symbol": "002230"}}
- 如果用户给了股票名但没代码（如"科大讯飞""茅台"），输出 test_symbol=股票名，由后续逻辑解析：
  {{"intent": "retry", "confidence": 0.9, "reason": "用户要求换股重测", "test_symbol": "科大讯飞"}}
- 用户在 wait_evaluation 说"发布""上线"→ confirmed
- 不确定时宁可给低置信度

只输出 JSON。"""


def _build_error_prompt(state: AgentBuilderState) -> str:
    """错误恢复阶段的意图分类提示词。主要关注：重试 vs 修改 vs 取消。"""
    msg = state.get("user_message", "") or ""
    recent_history = _format_recent_history(state, rounds=3)
    shared_context = _build_intent_shared_context(state, "error")
    errors = state.get("errors", []) or []
    err_lines = []
    for e in errors[-2:]:
        if isinstance(e, dict):
            err_lines.append(f"{e.get('node','?')}: {e.get('error','?')}")
    err_text = "; ".join(err_lines) if err_lines else "未知错误"

    return f"""你是意图分类器。用户在 Agent 构建流程的错误恢复阶段。

{shared_context}

## 当前节点
处理过程遇到了错误：{err_text}
用户需要决定下一步。

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：用户想重试失败步骤（如"重试""再来""retry"）
- revise：用户想修改需求，回到需求阶段
- rerun_gap：用户要求重新执行当前 Agent 的能力缺口分析/工具能力盘点（如"重新做一下gap分析"）
- regenerate_plan：用户要求重新生成候选解决方案/构建方案
- explore_more：用户问问题但没有明确指令
- cancel：取消/结束

## 输出格式（严格 JSON）
{{"intent": "confirmed|revise|rerun_gap|regenerate_plan|explore_more|cancel", "confidence": 0.85, "reason": "用户说重试"}}

只输出 JSON。"""


def _build_generic_prompt(state: AgentBuilderState) -> str:
    """通用兜底提示词（未知节点类型）。"""
    msg = state.get("user_message", "") or ""
    current_node = state.get("current_node", "")
    recent_history = _format_recent_history(state, rounds=3)
    shared_context = _build_intent_shared_context(state, "generic")

    return f"""你是意图分类器。用户当前在 Agent 构建流程中（节点={current_node}）。

{shared_context}

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：确认推进
- revise：修改需求
- new_agent：创建全新 Agent
- rerun_gap：重新执行当前 Agent 的能力缺口分析/工具能力盘点
- regenerate_plan：重新生成候选解决方案/构建方案
- explore_more：探讨/提问
- cancel：取消

## 输出格式（严格 JSON）
{{"intent": "confirmed|revise|rerun_gap|regenerate_plan|new_agent|explore_more|cancel", "confidence": 0.7, "reason": "..."}}

只输出 JSON。"""


def _will_stay_on_wait_node(state: AgentBuilderState) -> bool:
    """预判本轮是否会停留在当前 wait 节点（意图无法转化为有效推进）。

    与 route_after_classify 的路由逻辑保持一致。
    """
    current_node = state.get("current_node", "")
    intent = state.get("user_intent", "explore_more")
    msg = state.get("user_message", "") or ""

    if intent == "cancel":
        return False  # cancel → end，不算停留
    if intent == "rerun_gap":
        return False  # rerun_gap → gap_analysis
    if intent == "regenerate_plan":
        return False  # regenerate_plan → plan_generation

    if current_node in ("wait_intake_confirmation", "wait_requirement_confirmation"):
        # confirmed/select_option/revise 都能推进，只有 explore_more 停留
        return intent not in ("confirmed", "select_option", "revise")

    if current_node == "wait_plan_selection":
        if intent == "revise":
            return False
        if intent in ("select_option", "confirmed"):
            # 能否解析出方案？解析不出才停留
            from core.embedded_nanobot.workflows.agent_builder_conditions import (
                _resolve_selected_from_llm, _resolve_plan_selection,
            )
            if _resolve_selected_from_llm(state):
                return False
            selected_id, _ = _resolve_plan_selection(state.get("pending_options", []), msg)
            if selected_id:
                return False
            if intent == "confirmed":
                # confirmed 会用推荐/首个方案兜底
                if state.get("recommended_plan_id") or state.get("pending_options"):
                    return False
            return True
        return True  # explore_more

    if current_node == "wait_test_request":
        # LLM 已在 classify_intent 中提取 test_symbol（从消息或上下文）
        if state.get("test_symbol"):
            return False
        return True

    if current_node == "wait_evaluation":
        # confirmed → 发布；revise → 修改；retry → 重测；cancel → 取消
        # retry 需要 test_symbol，没有就停留（在 wait_test_request 输出"请提供股票代码"提示）
        if intent == "retry":
            return not state.get("test_symbol")
        return intent not in ("confirmed", "select_option", "revise", "cancel")

    if current_node == "evaluate_or_publish":
        # confirmed/retry/select_option → 重新测试；revise → 修改需求
        return intent not in ("confirmed", "select_option", "revise", "cancel", "retry")

    if current_node == "error_recovery":
        # confirmed/retry → 重试；revise → 修改需求
        return intent not in ("confirmed", "select_option", "revise", "cancel", "retry")

    return False


def _fallback_classify_intent(msg: str, current_node: str) -> str:
    """LLM 不可用时的极简兜底。只判断最明显的信号，不猜精细意图。"""
    from core.embedded_nanobot.workflows.agent_builder_conditions import (
        _is_cancel, _is_route_choice,
    )
    t = (msg or "").strip().lower()
    if _is_cancel(msg):
        return "cancel"
    if _is_rerun_gap_analysis_request(msg):
        return "rerun_gap"
    if _is_regenerate_plan_request(msg):
        return "regenerate_plan"
    if any(word in t for word in ("升级需求", "修改需求", "调整需求", "改需求")):
        return "revise"
    if _is_route_choice(msg):
        return "select_option"
    # 明确的单字/短词确认信号
    if t in ("确认", "好的", "可以", "行", "没问题", "ok", "yes", "对", "发布", "上线", "继续"):
        return "confirmed"
    return "explore_more"


async def node_requirement_intake(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """需求探索节点。

    调用 prepare_agent_requirement_intake 将用户需求结构化。
    """
    await _emit_event(event_callback, "step", "需求探索")
    await _emit_event(event_callback, "progress", "正在分析需求并生成默认方案")

    system_prompt = """你是 TradingAgentsCN 平台的财经产品专家 + Agent 构建顾问。

当前阶段：需求探索。用户想创建一个分析 Agent。

你的任务：
1. 以财经产品专家身份，根据用户描述给出默认方案草稿（抛砖引玉）
2. 必须调用 prepare_agent_requirement_intake 工具将需求结构化
3. 不要列问卷，一次最多问 1 个关键问题
4. 默认 A 股、结构化 Markdown 报告、只做研究分析、包含风险提示

你必须调用 prepare_agent_requirement_intake 工具。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state, system_prompt, tool_registry, llm_client,
        required_tool_name="prepare_agent_requirement_intake",
        include_inspect_tools=False,
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["final_response"] = final_text
    state["tool_events"] = tool_events
    state["current_node"] = "requirement_intake"

    # 保存原始用户请求，供后续节点 force-call 使用
    state["original_user_request"] = state.get("user_message", "")

    # 提取工具结果
    intake_result = _extract_json_from_result(
        tool_results.get("prepare_agent_requirement_intake", "{}")
    )
    if intake_result:
        proposed_plan = intake_result.get("proposed_plan", {}) or {}
        critical_questions = intake_result.get("critical_questions", []) or []
        can_proceed = intake_result.get("can_proceed_to_confirmation", False)

        # 从 proposed_plan 提取关键信息
        responsibility = str(proposed_plan.get("single_responsibility") or "").strip()
        # 优先使用 proposed_agent_name（简短 Agent 名，如"多维度估值分析助手"），
        # 而不是把整句职责描述（如"对A股上市公司执行多维度估值分析，输出结构化报告"）当名字
        proposed_name = str(proposed_plan.get("proposed_agent_name") or "").strip()
        proposed_slug = str(proposed_plan.get("proposed_agent_slug") or "").strip()
        if responsibility and responsibility != "（待确认）":
            state["requirement_summary"] = responsibility
            # spec_name 优先用简短名，没有时用职责描述的前 15 字
            state["spec_name"] = proposed_name or (responsibility[:15] + ("…" if len(responsibility) > 15 else ""))
        else:
            # 职责也待确认：用简短名或原始请求的前 15 字
            state["spec_name"] = proposed_name or state.get("original_user_request", "")[:15]
            state["requirement_summary"] = state.get("original_user_request", "")

        # 保存 spec_id（英文 slug），优先用 LLM 生成的 proposed_agent_slug
        if proposed_slug:
            state["spec_id"] = proposed_slug
        elif not state.get("spec_id"):
            # 兜底：从 spec_name 生成简单 slug
            import re
            from core.tools.implementations.agent_builder.nanobot_agent_builder_tools import _fallback_slug_from_name
            state["spec_id"] = _fallback_slug_from_name(
                state.get("spec_name", ""),
                state.get("original_user_request", ""),
                responsibility
            )

        # pending_question 来自 critical_questions
        if critical_questions and not can_proceed:
            state["pending_question"] = str(critical_questions[0].get("question", ""))
        else:
            state["pending_question"] = ""

        # stage
        state["stage"] = "draft_preparing" if can_proceed else "exploring"

        # 保存 proposed_plan 供后续节点使用
        state["proposed_plan"] = proposed_plan

    await _emit_event(event_callback, "step", "需求探索完成")
    return state


async def node_wait_intake_confirmation(
    state: AgentBuilderState,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """等待用户确认需求方向。

    wait 节点不调用 LLM，只做状态标记。
    """
    state["current_node"] = "wait_intake_confirmation"
    state["awaiting_user"] = True
    state["stage"] = "exploring"

    # 意图无法识别时输出澄清提示，避免重复上一轮内容
    if state.get("clarification_needed"):
        pending_q = state.get("pending_question", "")
        clarify = (
            "抱歉，我没太听明白你的意思。\n\n"
            + (f"我们正在确认这个问题：**{pending_q}**\n\n" if pending_q else "")
            + "你可以：\n"
            "- 回复「确认」「可以」按当前方案推进\n"
            "- 直接说出你想调整或补充的地方\n"
            "- 回复「取消」重新开始\n\n"
            "请再说得具体一点，我好继续帮你推进。"
        )
        state["final_response"] = clarify
        state["clarification_needed"] = False
        await _invoke_stream(on_stream, clarify)
        return state

    if state.get("pending_question"):
        await _emit_event(event_callback, "progress", f"待确认：{state['pending_question']}")

    return state


async def node_requirement_confirmation(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """需求确认节点。

    调用 prepare_agent_generation_confirmation 生成确认稿。
    纯业务确认，不涉及能力盘点、gap 分析、方案展示。
    """
    await _emit_event(event_callback, "step", "需求确认")
    await _emit_event(event_callback, "progress", "正在生成确认稿")

    system_prompt = f"""你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：需求确认。用户已确认基本方向，现在需要确认职责边界和输出形态。

已确认的需求：
- 名称：{state.get('spec_name', '未命名')}
- 摘要：{state.get('requirement_summary', '无')}

你的任务：
1. 调用 prepare_agent_generation_confirmation 生成确认稿
2. 确认稿只包含：职责范围、输出形态、非目标
3. 不要在此阶段展示工具候选、能力盘点、gap 分析、方案
4. 用户确认后，下一步是能力盘点

你必须调用 prepare_agent_generation_confirmation 工具。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state, system_prompt, tool_registry, llm_client,
        required_tool_name="prepare_agent_generation_confirmation",
        include_inspect_tools=False,  # 确认阶段不需要工具搜索
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["final_response"] = final_text
    state["tool_events"] = tool_events
    state["current_node"] = "requirement_confirmation"
    state["stage"] = "draft_preparing"

    # 提取工具结果
    conf_result = _extract_json_from_result(
        tool_results.get("prepare_agent_generation_confirmation", "{}")
    )
    if conf_result:
        state["confirmation_brief"] = conf_result.get("confirmation_brief", {})
        state["pending_question"] = conf_result.get("pending_question", "")
        # spec_id 可能在顶层、confirmation_brief.agent_id 或 confirmation_brief.proposed_agent_id
        conf_brief = conf_result.get("confirmation_brief", {}) or {}
        spec_id = (
            conf_result.get("spec_id")
            or conf_brief.get("agent_id")
            or conf_brief.get("proposed_agent_id")
            or state.get("spec_id", "")
        )
        if spec_id:
            state["spec_id"] = spec_id
        spec_name = (
            conf_result.get("spec_name")
            or conf_brief.get("agent_name")
            or conf_brief.get("proposed_agent_name")
            or state.get("spec_name", "")
        )
        if spec_name:
            state["spec_name"] = spec_name

    await _emit_event(event_callback, "step", "需求确认完成")
    return state


async def node_wait_requirement_confirmation(
    state: AgentBuilderState,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """等待用户确认需求边界。"""
    state["current_node"] = "wait_requirement_confirmation"
    state["awaiting_user"] = True
    state["stage"] = "requirement_confirmation_pending"

    # 意图无法识别时输出澄清提示，避免重复上一轮内容
    if state.get("clarification_needed"):
        pending_q = state.get("pending_question", "")
        clarify = (
            "抱歉，我没太听明白你的意思。\n\n"
            + (f"我们正在确认：**{pending_q}**\n\n" if pending_q else "")
            + "你可以：\n"
            "- 回复「确认」「可以」我就进入能力盘点\n"
            "- 说出你想调整的边界或要求\n"
            "- 回复「取消」重新开始\n\n"
            "请再说得具体一点。"
        )
        state["final_response"] = clarify
        state["clarification_needed"] = False
        await _invoke_stream(on_stream, clarify)
        return state

    if state.get("pending_question"):
        await _emit_event(event_callback, "progress", f"待确认：{state['pending_question']}")

    return state


async def node_gap_analysis(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """缺口分析节点。

    调用 analyze_agent_workshop_gaps 做真实 gap 分析。
    """
    await _emit_event(event_callback, "step", "缺口分析")
    await _emit_event(event_callback, "progress", "正在分析能力缺口")

    system_prompt = f"""你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：缺口分析。需要扫描平台现有能力并分析是否满足 Agent 需求。

Agent 信息：
- 名称：{state.get('spec_name', '未命名')}
- 需求：{state.get('requirement_summary', '无')}

你的任务：
1. 调用 analyze_agent_workshop_gaps 做能力扫描和缺口分析
2. 无论是否有 blocking gaps，都进入方案生成
3. 不要在此阶段直接生成方案或Agent

你必须调用 analyze_agent_workshop_gaps 工具。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state, system_prompt, tool_registry, llm_client,
        required_tool_name="analyze_agent_workshop_gaps",
        include_inspect_tools=False,
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["final_response"] = final_text
    state["tool_events"] = tool_events
    state["current_node"] = "gap_analysis"
    state["stage"] = "capability_check"

    # 提取 gap 报告
    gap_result = _extract_json_from_result(
        tool_results.get("analyze_agent_workshop_gaps", "{}")
    )
    if gap_result:
        # gap_result 是外层 wrapper：{status, session_id, spec_id, gap_report, summary}
        # state["gap_report"] 应保存内层真正的 gap_report（含 blocking_gaps、suggested_tools 等）
        inner_gap_report = gap_result.get("gap_report", {}) or {}
        # 兜底：若 gap_report 被序列化成字符串（理论上工具层已修复，这里防御性处理），
        # 尝试 JSON 解析回 dict。
        if isinstance(inner_gap_report, str) and inner_gap_report.strip().startswith("{"):
            try:
                parsed = json.loads(inner_gap_report)
                if isinstance(parsed, dict):
                    inner_gap_report = parsed
            except json.JSONDecodeError:
                pass
        if not isinstance(inner_gap_report, dict):
            inner_gap_report = {}
        state["gap_report"] = inner_gap_report

        blocking_gaps_count = len(inner_gap_report.get("blocking_gaps", []) or [])
        logger.info(
            "[GapAnalysis][Output] gap_report_keys=%s blocking_gaps=%d existing_tools=%d suggested_tools=%d",
            list(inner_gap_report.keys()),
            blocking_gaps_count,
            len(inner_gap_report.get("existing_tools", []) or []),
            len(inner_gap_report.get("suggested_tools", []) or []),
        )

        # 同时保存 session_id（analyze_agent_workshop_gaps 可能已自动创建 session）
        if gap_result.get("session_id") and not state.get("workshop_session_id"):
            state["workshop_session_id"] = gap_result["session_id"]
            logger.info("[GapAnalysis] 保存 workshop_session_id=%s", state["workshop_session_id"])
    else:
        logger.warning(
            "[GapAnalysis][EmptyResult] tool_results keys=%s raw_len=%d",
            list(tool_results.keys()),
            len(tool_results.get("analyze_agent_workshop_gaps", "") or ""),
        )

    await _emit_event(event_callback, "step", "缺口分析完成")
    return state


async def node_plan_generation(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """方案生成节点。

    调用 propose_agent_build_plans 生成结构化候选方案。
    这是唯一能生成方案的地方，LLM 不能口头生成方案。
    """
    await _emit_event(event_callback, "step", "方案生成")
    await _emit_event(event_callback, "progress", "正在生成候选方案")

    system_prompt = f"""你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：方案生成。gap 分析已完成，现在需要生成候选方案。

Agent 信息：
- 名称：{state.get('spec_name', '未命名')}
- Gap 报告：{json.dumps(state.get('gap_report', {}), ensure_ascii=False)[:1000]}

你的任务：
1. 调用 propose_agent_build_plans 工具生成结构化候选方案
2. 用业务语言向用户展示方案选项
3. 用户选择方案后，系统会调用 generate_confirmed_candidate_agent

你必须调用 propose_agent_build_plans 工具。不能口头生成方案。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state, system_prompt, tool_registry, llm_client,
        required_tool_name="propose_agent_build_plans",
        include_inspect_tools=False,
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["final_response"] = final_text
    state["tool_events"] = tool_events
    state["current_node"] = "plan_generation"
    state["stage"] = "plan_selection_pending"

    # 提取方案结果
    plan_result = _extract_json_from_result(
        tool_results.get("propose_agent_build_plans", "{}")
    )
    if plan_result:
        state["candidate_plans"] = plan_result.get("candidate_plans", [])
        state["pending_options"] = plan_result.get("pending_options", [])
        state["recommended_plan_id"] = plan_result.get("recommended_plan_id", "")
        state["pending_question"] = plan_result.get("pending_question", "")

    logger.info(
        "[ProposePlans][Output] plan_count=%d, pending_options=%d, recommended=%s",
        len(state.get("candidate_plans", [])),
        len(state.get("pending_options", [])),
        state.get("recommended_plan_id", ""),
    )

    await _emit_event(event_callback, "step", "方案生成完成")
    return state


async def node_wait_plan_selection(
    state: AgentBuilderState,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """等待用户选择方案。"""
    state["current_node"] = "wait_plan_selection"
    state["awaiting_user"] = True
    state["stage"] = "plan_selection_pending"

    # 意图无法识别时输出澄清提示，避免重复上一轮的方案列表
    if state.get("clarification_needed"):
        options = state.get("pending_options", []) or []
        lines = []
        for opt in options:
            idx = opt.get("index", "")
            label = opt.get("name", opt.get("id", ""))
            rec = "（推荐）" if opt.get("recommended") else ""
            lines.append(f"- 方案 {idx}：{label}{rec}")
        options_text = "\n".join(lines) if lines else ""
        clarify = (
            "抱歉，我没太听明白你选哪个方案。\n\n"
            + (f"可选方案如下：\n{options_text}\n\n" if options_text else "")
            + "请直接回复方案编号或字母（如「方案A」「B」「第二个」），"
            "或回复「推荐」按推荐方案推进。"
        )
        state["final_response"] = clarify
        state["clarification_needed"] = False
        await _invoke_stream(on_stream, clarify)
        return state

    if state.get("pending_question"):
        await _emit_event(event_callback, "progress", f"待选择：{state['pending_question']}")

    return state


async def node_generate_candidate_agent(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """生成 Agent 节点。

    调用 generate_confirmed_candidate_agent 生成 Agent 配置、Prompt、绑定。
    """
    await _emit_event(event_callback, "step", "生成 Agent")
    await _emit_event(event_callback, "progress", "正在写入配置和 Prompt")

    # 条件函数对 state 的修改不会持久化到节点，这里重新解析 selected_plan_id
    if not state.get("selected_plan_id"):
        from core.embedded_nanobot.workflows.agent_builder_conditions import _resolve_plan_selection
        msg = state.get("user_message", "")
        pending_options = state.get("pending_options", []) or []
        selected_id, reason = _resolve_plan_selection(pending_options, msg)
        if selected_id:
            state["selected_plan_id"] = selected_id
            logger.info("[GenerateAgent][ResolvedPlan] selected_plan_id=%s reason=%s", selected_id, reason)
        elif _is_confirm_like(msg) and state.get("recommended_plan_id"):
            state["selected_plan_id"] = state["recommended_plan_id"]
            logger.info("[GenerateAgent][ResolvedPlan] using recommended=%s", state["recommended_plan_id"])

    system_prompt = f"""你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：生成 Agent。用户已选择方案，现在需要生成 Agent。

Agent 信息：
- 名称：{state.get('spec_name', '未命名')}
- 选择的方案：{state.get('selected_plan_id', '未选择')}
- 候选方案：{json.dumps(state.get('candidate_plans', []), ensure_ascii=False)[:500]}
- Gap 报告：{json.dumps(state.get('gap_report', {}), ensure_ascii=False)[:500]}

你的任务：
1. 调用 generate_confirmed_candidate_agent 生成 Agent
2. 报告生成结果（配置、工具绑定、Prompt）
3. 如果是 quick 方案，说明已接受的缺口

你必须调用 generate_confirmed_candidate_agent 工具。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state, system_prompt, tool_registry, llm_client,
        required_tool_name="generate_confirmed_candidate_agent",
        include_inspect_tools=False,
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["final_response"] = final_text
    state["tool_events"] = tool_events
    state["current_node"] = "generate_candidate_agent"
    state["stage"] = "generating"

    # 提取生成结果
    gen_result = _extract_json_from_result(
        tool_results.get("generate_confirmed_candidate_agent", "{}")
    )
    if gen_result:
        state["generated_agent"] = gen_result

        # workshop_session_id 可能在多个位置
        workshop_session_id = (
            gen_result.get("workshop_session_id")
            or gen_result.get("session_id")
            or ""
        )
        if not workshop_session_id:
            # 从嵌套的 governance_boundary.workshop_governance.session_id 提取
            governance = gen_result.get("governance_boundary", {}) or {}
            workshop_governance = governance.get("workshop_governance", {}) or {}
            workshop_session_id = workshop_governance.get("session_id", "")
        if not workshop_session_id:
            # 从 steps.workshop_draft.session_id 提取
            steps = gen_result.get("steps", {}) or {}
            workshop_draft = steps.get("workshop_draft", {}) or {}
            workshop_session_id = workshop_draft.get("session_id", "")
        state["workshop_session_id"] = workshop_session_id

        # version_id 也在多个位置
        version_id = gen_result.get("version_id", "")
        if not version_id:
            governance = gen_result.get("governance_boundary", {}) or {}
            workshop_governance = governance.get("workshop_governance", {}) or {}
            version_id = workshop_governance.get("version_id", "")
        if not version_id:
            steps = gen_result.get("steps", {}) or {}
            workshop_version = steps.get("workshop_version", {}) or {}
            version_obj = workshop_version.get("version", {})
            if isinstance(version_obj, dict):
                version_id = version_obj.get("version_id", "")
            elif isinstance(version_obj, str):
                version_id = version_obj
        # 防御性清洗：version_id 可能是 AgentVersion 对象的 str repr
        # （json.dumps default=str 把 Pydantic 模型转成了字符串）
        version_id = _sanitize_version_id(version_id)
        state["version_id"] = version_id

        # build_status
        if gen_result.get("status") == "ok":
            state["build_status"] = "built" if version_id else "ready"
        else:
            state["build_status"] = "failed"
            err_msg = gen_result.get("message", "")
            err_stage = gen_result.get("stage", "")
            err_result = gen_result.get("result", {})
            # 同时保留字符串和 dict 形式，便于 node_error_recovery 处理
            error_entry = {
                "node": "generate_candidate_agent",
                "error": err_msg or f"stage={err_stage} result={err_result}" or "生成失败",
                "stage": err_stage,
                "message": err_msg,
            }
            state["errors"] = state.get("errors", []) + [error_entry]

        logger.info(
            "[GenerateAgent][Result] status=%s session_id=%s version_id=%s build_status=%s "
            "stage=%s message=%s result_keys=%s",
            gen_result.get("status", ""),
            workshop_session_id,
            version_id,
            state["build_status"],
            gen_result.get("stage", ""),
            gen_result.get("message", "")[:200],
            list(gen_result.get("result", {}).keys()) if isinstance(gen_result.get("result"), dict) else "N/A",
        )

    await _emit_event(event_callback, "step", "Agent 生成完成")
    return state


async def node_build_or_ready(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """构建/准备测试节点。

    根据方案决定是否需要构建 Workshop 版本。
    quick 方案跳过构建。
    """
    state["current_node"] = "build_or_ready"
    state["stage"] = "building"

    if state.get("selected_plan_id") == "quick":
        state["build_status"] = "skipped"
        await _emit_event(event_callback, "progress", "简化版方案，跳过版本构建")
        return state

    # 如果 generate 阶段已经自动构建了版本（auto_build_workshop_version=True），
    # 直接进入 wait_test_request，不需要再调 build_agent_workshop_version
    if state.get("build_status") == "built" and state.get("version_id"):
        await _emit_event(event_callback, "progress", "已在生成阶段自动构建版本，跳过重复构建")
        return state

    # 如果没有 workshop_session_id，无法构建（generate 失败或未同步）
    workshop_session_id = state.get("workshop_session_id", "")
    if not workshop_session_id:
        state["build_status"] = "skipped_no_session"
        state["stage"] = "skipped"
        logger.warning("[BuildOrReady] 没有 workshop_session_id，跳过构建")
        await _emit_event(event_callback, "progress", "无 Workshop 会话，跳过版本构建")
        return state

    await _emit_event(event_callback, "step", "构建版本")
    await _emit_event(event_callback, "progress", "正在构建 Workshop 版本")

    system_prompt = """你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：构建版本。Agent 已生成，现在需要构建 Workshop 版本。

你的任务：
1. 调用 build_agent_workshop_version 构建版本
2. 报告构建结果

你必须调用 build_agent_workshop_version 工具。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state, system_prompt, tool_registry, llm_client,
        required_tool_name="build_agent_workshop_version",
        include_inspect_tools=False,
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["final_response"] = final_text
    state["tool_events"] = tool_events
    state["stage"] = "building"

    build_result = _extract_json_from_result(
        tool_results.get("build_agent_workshop_version", "{}")
    )
    if build_result:
        # version_id 可能在顶层、summary.version_id 或 version.version_id
        version_id = build_result.get("version_id", "")
        if not version_id:
            summary = build_result.get("summary", {}) or {}
            version_id = summary.get("version_id", "")
        if not version_id:
            version_obj = build_result.get("version", {})
            if isinstance(version_obj, dict):
                version_id = version_obj.get("version_id", "")
            elif isinstance(version_obj, str):
                version_id = version_obj
        # 防御性清洗：version_id 可能是 AgentVersion 对象的 str repr
        version_id = _sanitize_version_id(version_id)
        if version_id:
            state["version_id"] = version_id

        # status="ok" 表示构建成功 → build_status="built"
        if build_result.get("status") == "ok":
            state["build_status"] = "built"
        else:
            state["build_status"] = "failed"
            err_msg = build_result.get("message") or build_result.get("error") or "构建失败"
            state["errors"] = state.get("errors", []) + [{
                "node": "build_or_ready",
                "error": str(err_msg)[:300],
                "stage": "building",
            }]
            logger.warning("[BuildOrReady][Failed] %s", str(err_msg)[:200])

    return state


async def node_wait_test_request(
    state: AgentBuilderState,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """等待用户给测试标的。"""
    state["current_node"] = "wait_test_request"
    state["awaiting_user"] = True
    state["stage"] = "testing"

    # 若上一轮意图无法识别（如给了股票名而非代码），输出澄清提示，
    # 而不是把上一次的生成结果重复展示一遍。
    if state.get("clarification_needed"):
        spec_name = state.get("spec_name", "") or "候选 Agent"
        clarify = (
            f"抱歉，我没太理解你的意思。「{spec_name}」已经就绪，"
            f"现在需要一个**具体的股票代码**来跑真实数据测试。\n\n"
            f"请直接回复 6 位股票代码，例如：\n"
            f"- 贵州茅台 → `600519`\n"
            f"- 宁德时代 → `300750`\n"
            f"- 招商银行 → `600036`\n\n"
            f"或者回复「跳过」直接进入发布评估。"
        )
        state["final_response"] = clarify
        state["clarification_needed"] = False
        await _invoke_stream(on_stream, clarify)
        await _emit_event(event_callback, "progress", "需要股票代码")
        return state

    await _emit_event(event_callback, "progress", "Agent 已就绪，等待测试标的")

    return state


async def node_iterate_agent_version(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """基于当前测试/发布版本发起下一轮迭代，创建新的草稿版本。"""
    state["current_node"] = "iterate_agent_version"
    state["awaiting_user"] = False
    state["stage"] = "iterating"

    system_prompt = """你是 TradingAgentsCN 平台的 Agent 工坊版本迭代助手。

当前阶段：用户要求升级/修改已测试或已发布的 Agent。

你的任务：
1. 调用 iterate_agent_workshop_version，基于当前 version_id 创建下一轮迭代草稿版本
2. 向用户说明已从当前版本创建了下一版草稿，并引导用户补充升级需求

你必须调用 iterate_agent_workshop_version 工具。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state,
        system_prompt,
        tool_registry,
        llm_client,
        required_tool_name="iterate_agent_workshop_version",
        include_inspect_tools=False,
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["tool_events"] = tool_events
    result = _extract_json_from_result(tool_results.get("iterate_agent_workshop_version", "{}"))
    if result and result.get("status") == "ok":
        new_session_id = str(result.get("session_id") or "").strip()
        new_spec_id = str(result.get("spec_id") or "").strip()
        new_version_id = _sanitize_version_id(result.get("version_id", ""))
        source_version_id = _sanitize_version_id(result.get("source_version_id", ""))
        if new_session_id:
            state["workshop_session_id"] = new_session_id
        if new_spec_id:
            state["spec_id"] = new_spec_id
        if new_version_id:
            state["version_id"] = new_version_id
            state["build_status"] = "draft"
        if source_version_id:
            state["source_version_id"] = source_version_id
        ai_message = str(result.get("ai_message") or "").strip()
        if ai_message:
            final_text = ai_message
        state["final_response"] = final_text
        state["current_node"] = "wait_intake_confirmation"
        state["stage"] = "requirement_refine"
        state["awaiting_user"] = True
        state["pending_question"] = "已创建下一版草稿，请补充或确认升级需求。"
    else:
        state["final_response"] = final_text
        state["current_node"] = "error_recovery"
        state["stage"] = "error_recovery"
        state["awaiting_user"] = True
        message = str((result or {}).get("message") or final_text or "发起下一轮迭代失败")
        state["errors"] = state.get("errors", []) + [{
            "node": "iterate_agent_version",
            "error": message[:300],
            "stage": "iterating",
        }]
    return state


async def node_wait_evaluation(
    state: AgentBuilderState,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """测试完成后等待用户决策：发布 / 重测 / 修改 / 取消。

    发布后回到此节点时，提示语调整为已发布状态。
    """
    state["current_node"] = "wait_evaluation"
    state["awaiting_user"] = True
    state["stage"] = "evaluating"
    published = state.get("official_acceptance_decision") == "published"

    if state.get("clarification_needed"):
        if published:
            clarify = (
                "抱歉，我不太确定你的意思。\n\n"
                "此版本已发布上线，你可以：\n"
                "- 回复「重测 [股票名]」用其他标的重新测试（如「重测 科大讯飞」）\n"
                "- 回复「升级需求」或「修改需求」创建新版本\n"
                "- 回复「重新做缺口分析」刷新能力缺口分析\n"
                "- 回复「重新生成解决方案」基于当前 gap 重新生成候选方案\n"
                "- 回复「新建 Agent」切换到新 Agent 创建\n"
                "- 回复「取消」结束当前会话\n\n"
                "请说得更具体一点。"
            )
        else:
            test_status = state.get("test_result", {}).get("status", "unknown")
            clarify = (
                f"抱歉，我不太确定你的意思。当前测试已完成（状态={test_status}）。\n\n"
                "你可以：\n"
                "- 回复「发布」确认发布此版本\n"
                "- 回复「重测 [股票名]」重新跑一轮测试（如「重测 贵州茅台」）\n"
                "- 回复「升级需求」或「修改需求」回到需求调整\n"
                "- 回复「重新做缺口分析」刷新能力缺口分析\n"
                "- 回复「重新生成解决方案」基于当前 gap 重新生成候选方案\n"
                "- 回复「新建 Agent」切换到新 Agent 创建\n"
                "- 回复「取消」结束流程\n\n"
                "请说得更具体一点。"
            )
        state["final_response"] = clarify
        state["clarification_needed"] = False
        await _invoke_stream(on_stream, clarify)
        return state

    if published:
        state["pending_question"] = (
            "Agent 已发布上线。可选操作：重测其他股票、升级/修改需求、重新做缺口分析、"
            "重新生成解决方案、新建 Agent、取消。"
        )
    else:
        state["pending_question"] = (
            "测试完成。可选操作：发布、重新测试、升级/修改需求、重新做缺口分析、"
            "重新生成解决方案、新建 Agent、取消。"
        )
    options_block = (
        "\n\n---\n"
        "你接下来可以选择：\n"
        + ("1. 发布/上线当前版本\n" if not published else "")
        + "2. 重新测试（可直接说：重测 科大讯飞）\n"
        + "3. 升级/修改需求\n"
        + "4. 重新做缺口分析\n"
        + "5. 重新生成解决方案\n"
        + "6. 新建其他 Agent\n"
        + "7. 取消/结束\n"
    )
    if options_block.strip() not in str(state.get("final_response", "")):
        state["final_response"] = (state.get("final_response", "") or "") + options_block
        await _invoke_stream(on_stream, options_block)
    await _emit_event(event_callback, "progress", state["pending_question"])

    return state


async def node_real_data_test(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """真数据测试节点。"""
    await _emit_event(event_callback, "step", "真数据测试")
    await _emit_event(event_callback, "progress", f"正在用 {state.get('test_symbol', '未知')} 测试")

    system_prompt = f"""你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：真数据测试。用户已提供测试标的。

Agent 信息：
- 名称：{state.get('spec_name', '未命名')}
- 测试标的：{state.get('test_symbol', '未指定')}

你的任务：
1. 调用 run_agent_workshop_real_data_test 进行真数据测试
2. 解读测试结果

你必须调用 run_agent_workshop_real_data_test 工具。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state, system_prompt, tool_registry, llm_client,
        required_tool_name="run_agent_workshop_real_data_test",
        include_inspect_tools=False,
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["final_response"] = final_text
    state["tool_events"] = tool_events
    state["current_node"] = "real_data_test"
    state["stage"] = "testing"

    test_result = _extract_json_from_result(
        tool_results.get("run_agent_workshop_real_data_test", "{}")
    )
    if test_result:
        state["test_result"] = test_result
        # 如果测试失败，记录错误便于 error_recovery 展示
        if test_result.get("status") == "error":
            err_msg = (
                test_result.get("message")
                or test_result.get("error")
                or "真数据测试失败"
            )
            failed_stage = test_result.get("failed_stage", "unknown")
            state["errors"] = state.get("errors", []) + [{
                "node": "real_data_test",
                "error": str(err_msg)[:300],
                "stage": "testing",
                "failed_stage": failed_stage,
            }]
            logger.warning(
                "[RealDataTest][Failed] stage=%s msg=%s | full_result_keys=%s",
                failed_stage,
                str(err_msg)[:500],
                list(test_result.keys()) if isinstance(test_result, dict) else "N/A",
            )
            # 打印完整的 tool_events 用于诊断
            tool_events_from_result = test_result.get("_tool_events") or test_result.get("tool_events") or []
            if tool_events_from_result:
                logger.info(
                    "[RealDataTest][ToolEvents] %s",
                    json.dumps(tool_events_from_result, ensure_ascii=False)[:1000],
                )

    return state


async def node_evaluate_or_publish(
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """评估/发布节点。"""
    state["current_node"] = "evaluate_or_publish"
    state["stage"] = "evaluating"
    state["awaiting_user"] = True  # 备选，一定保留以确保与用户互动，子状态在后续更新

    # 若上一轮意图无法识别（如用户说"重跑测试"但被误判为未知指令），
    # 输出澄清提示，而不是重新调用 LLM 尝试发布。
    if state.get("clarification_needed"):
        decision = state.get("official_acceptance_decision", "")
        test_status = state.get("test_result", {}).get("status", "unknown")
        clarify = (
            f"抱歉，我没太理解你的意思。当前版本处于评估阶段（测试状态={test_status}，"
            f"评估结论={decision}）。\n\n"
            "你可以：\n"
            "- 回复「发布」或「继续评估」继续当前评估/发布流程\n"
            "- 回复「重跑测试」或「重新测试」重新跑一轮真数据测试\n"
            "- 回复「升级需求」或「修改需求」回到需求调整阶段\n"
            "- 回复「重新做缺口分析」刷新能力缺口分析\n"
            "- 回复「重新生成解决方案」基于当前 gap 重新生成候选方案\n"
            "- 回复「新建 Agent」切换到新 Agent 创建\n"
            "- 回复「取消」结束当前流程\n\n"
            "请说得更具体一点。"
        )
        state["final_response"] = clarify
        state["clarification_needed"] = False
        await _invoke_stream(on_stream, clarify)
        return state

    await _emit_event(event_callback, "step", "评估与发布")
    await _emit_event(event_callback, "progress", "正在评估测试结果")

    system_prompt = f"""你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：评估与发布。测试已完成，需要评估结果并决定是否发布。

Agent 信息：
- 名称：{state.get('spec_name', '未命名')}
- 测试结果：{json.dumps(state.get('test_result', {}), ensure_ascii=False)[:1000]}

你的任务：
1. 如果测试通过，调用 publish_agent_workshop_version 发布
2. 如果测试有问题，调用 evaluate_agent_workshop_version 评估

你必须调用 publish_agent_workshop_version 或 evaluate_agent_workshop_version 工具。"""

    final_text, tool_events, tool_results = await _run_node_llm(
        state, system_prompt, tool_registry, llm_client,
        required_tool_name=["publish_agent_workshop_version", "evaluate_agent_workshop_version"],
        include_inspect_tools=False,
        event_callback=event_callback,
        on_stream=on_stream,
    )

    state["final_response"] = final_text
    state["tool_events"] = tool_events

    pub_result = _extract_json_from_result(
        tool_results.get("publish_agent_workshop_version", "{}")
    )
    eval_result = _extract_json_from_result(
        tool_results.get("evaluate_agent_workshop_version", "{}")
    )

    if pub_result:
        state["official_acceptance_decision"] = "published"
        state["current_node"] = "wait_evaluation"
        state["awaiting_user"] = True
        logger.info("[Eval] 发布成功，回到 wait_evaluation 等待用户后续指令")
    elif eval_result:
        decision = eval_result.get("decision", "revise")
        state["official_acceptance_decision"] = decision
        state["current_node"] = "wait_evaluation"
        state["awaiting_user"] = True
        logger.info("[Eval] 评估完成 decision=%s，回到 wait_evaluation 等待用户后续指令", decision)

    # 评估/发布完成后始终标记为等待用户，确保 checkpoint 被持久化
    state["awaiting_user"] = True
    state["stage"] = "completed"
    logger.info(
        "[Eval] evaluate_or_publish 完成 | current_node=%s | awaiting_user=%s | decision=%s",
        state["current_node"], state["awaiting_user"], state.get("official_acceptance_decision"),
    )

    return state


async def node_error_recovery(
    state: AgentBuilderState,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
) -> AgentBuilderState:
    """错误恢复节点。

    不自动回退或跳过，由用户决定下一步。
    """
    state["current_node"] = "error_recovery"
    state["awaiting_user"] = True

    # 若上一轮意图无法识别，输出澄清提示
    if state.get("clarification_needed"):
        errors = state.get("errors", [])
        err_lines = []
        for e in errors[-3:]:
            if isinstance(e, dict):
                err_lines.append(f"- {e.get('node','?')}: {e.get('error','?')}")
            else:
                err_lines.append(f"- {e}")
        err_text = "\n".join(err_lines)
        clarify = (
            f"抱歉，我没太理解你的意思。当前遇到了以下问题：\n{err_text}\n\n"
            "你可以：\n"
            "- 回复「重试」重新执行上一步\n"
            "- 回复「跳过」跳过当前步骤\n"
            "- 回复「修改」回到需求调整\n"
            "- 回复「取消」结束流程\n\n"
            "请说得更具体一点。"
        )
        state["final_response"] = clarify
        state["clarification_needed"] = False
        await _invoke_stream(on_stream, clarify)
        return state

    errors = state.get("errors", [])
    error_lines: list[str] = []
    for e in errors[-3:]:
        if isinstance(e, dict):
            node = e.get("node", "未知")
            err = e.get("error", "未知错误")
            error_lines.append(f"- {node}: {err}")
        else:
            # 兼容字符串形式错误
            error_lines.append(f"- {e}")
    error_text = "\n".join(error_lines)

    state["pending_question"] = (
        f"处理过程中遇到了一些问题：\n{error_text}\n\n"
        "你可以选择：\n"
        "  a) 重试\n"
        "  b) 跳过\n"
        "  c) 取消"
    )
    state["final_response"] = state["pending_question"]

    await _emit_event(event_callback, "step", "错误恢复")
    return state