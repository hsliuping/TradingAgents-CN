"""Trader node that emits AlphaGuard's authoritative NormalTradePlan."""

from __future__ import annotations

import functools
import json
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage
from pydantic import ValidationError

from tradingagents.agents.utils.instrument_utils import build_instrument_context
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
)
from tradingagents.alphaguard.structured_output import (
    invoke_json_object,
    model_output_schema_json,
)
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")

NORMAL_TRADE_PROMPT_NAME = "normal_trade_plan"
NORMAL_TRADE_PROMPT_VERSION = "normal_trade_plan_v1"
LEGACY_QUANT_PROPOSAL_ID = "legacy-quant:none"


def _legacy_snapshot_id(state: dict[str, Any]) -> str:
    """PR-002 compatibility ID until PR-003 introduces EvidenceSnapshot."""

    analysis_id = state.get("analysis_id")
    if not analysis_id:
        company = state.get("company_of_interest", "unknown")
        trade_date = state.get("trade_date", "unknown-date")
        analysis_id = f"{company}:{trade_date}"
    return f"legacy-analysis:{analysis_id}"


def _failure_plan(
    *,
    state: dict[str, Any],
    status: str,
    model_meta: ModelExecutionMeta,
    message: str,
) -> NormalTradePlan:
    return NormalTradePlan(
        plan_id=str(uuid4()),
        snapshot_id=_legacy_snapshot_id(state),
        quant_proposal_id=LEGACY_QUANT_PROPOSAL_ID,
        status=status,
        action="NONE",
        confidence=0,
        thesis=message,
        bullish_evidence=[],
        bearish_evidence=[],
        entry_zone=None,
        initial_position_pct=None,
        max_position_pct=None,
        add_conditions=[],
        stop_conditions=[],
        reduce_conditions=[],
        exit_conditions=[],
        invalidation_conditions=[],
        target_price=None,
        valid_until=None,
        main_risks=[],
        unresolved_questions=[],
        model_meta=model_meta,
    )


def _invalid_meta(
    meta: ModelExecutionMeta,
    error_type: str,
    error_message: str,
) -> ModelExecutionMeta:
    data = meta.model_dump(mode="python")
    data.update(
        execution_status="INVALID_OUTPUT",
        error_type=error_type,
        error_message=error_message[:500],
    )
    return ModelExecutionMeta.model_validate(data)


def _render_plan(plan: NormalTradePlan) -> str:
    """Human/report compatibility text derived only from the validated plan."""

    lines = [
        "# AlphaGuard 普通模型交易计划",
        f"- 状态：{plan.status}",
        f"- 动作：{plan.action}",
        f"- 置信度：{plan.confidence:.2f}",
        f"- 计划编号：{plan.plan_id}",
        f"- 兼容快照编号：{plan.snapshot_id}",
        f"- 结论：{plan.thesis}",
    ]
    if plan.target_price is not None:
        lines.append(f"- 目标价：{plan.target_price}")
    else:
        lines.append("- 目标价：未提供（未推算）")
    if plan.model_meta.error_type:
        lines.append(f"- 错误类别：{plan.model_meta.error_type}")
    lines.append(
        f"- Prompt：{plan.model_meta.prompt_name}@{plan.model_meta.prompt_version}"
    )
    return "\n".join(lines)


def create_trader(llm, memory, config: dict[str, Any] | None = None):
    config = config or {}

    def trader_node(state, name):
        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        investment_plan = state.get("investment_plan", "")
        reports = {
            "market_report": state.get("market_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "news_report": state.get("news_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
        }
        current_situation = "\n\n".join(str(value) for value in reports.values())

        past_memory_str = "暂无历史记忆数据可参考。"
        if memory is not None:
            try:
                memories = memory.get_memories(current_situation, n_matches=2)
                recommendations = [
                    str(item.get("recommendation", ""))
                    for item in memories
                    if item.get("recommendation")
                ]
                if recommendations:
                    past_memory_str = "\n\n".join(recommendations)
            except Exception as exc:
                logger.warning(
                    "Trader memory lookup failed; continuing without memory: %s",
                    exc.__class__.__name__,
                )

        snapshot_id = _legacy_snapshot_id(state)
        schema_json = model_output_schema_json(NormalTradePlan)
        messages = [
            {
                "role": "system",
                "content": f"""你是 AlphaGuard 的普通模型 Trader。你的唯一正式机器输出是一个严格 JSON 对象，不得输出 Markdown、解释前缀或 JSON 之外的文本。

Prompt 名称与固定版本：{NORMAL_TRADE_PROMPT_NAME}@{NORMAL_TRADE_PROMPT_VERSION}
你的角色是提出或不提出普通模型交易计划，不是风险终审，也不能创建订单。

强制语义：
- status/action 必须严格匹配 Schema。
- 证据不足使用 INSUFFICIENT_DATA + NONE。
- 信息尚不确定但适合继续观察使用 WAIT + WAIT。
- 正常不交易使用 NO_TRADE + NONE/HOLD。
- 只有可执行逻辑完整时才使用 PROPOSE_TRADE + BUY/SELL/REDUCE。
- target_price 可以为 null。缺失时不得推算、猜测或改变 action。
- 不得生成 model_meta；运行时会注入真实供应商、模型、Prompt、时延与输出哈希。
- snapshot_id 必须是 {snapshot_id}，这是 PR-002 的显式兼容占位；PR-003 后才会替换为真实证据快照。
- quant_proposal_id 必须是 {LEGACY_QUANT_PROPOSAL_ID}，不得用空字符串掩盖 PR-003 尚未实施。
- PROPOSE_TRADE 若暂时不能给出 valid_until，必须填写 valid_until_compatibility_reason。
- BUY 若策略确实不需要 entry_zone，必须填写 entry_zone_not_required_reason。
- 任何错误、空白或缺字段都不得用 HOLD 掩盖。

模型输出 JSON Schema：
{schema_json}

标的约束：
{instrument_context}""",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "company": company_name,
                        "trade_date": state.get("trade_date"),
                        "legacy_research_plan": investment_plan,
                        "reports": reports,
                        "past_memory": past_memory_str,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ]

        invocation = invoke_json_object(
            llm=llm,
            messages=messages,
            schema_model=NormalTradePlan,
            provider=str(
                config.get("quick_provider")
                or config.get("llm_provider")
                or "unknown"
            ),
            configured_model_name=config.get("quick_think_llm"),
            prompt_name=NORMAL_TRADE_PROMPT_NAME,
            prompt_version=NORMAL_TRADE_PROMPT_VERSION,
        )

        decision_error = None
        if invocation.failure_status:
            plan = _failure_plan(
                state=state,
                status=invocation.failure_status,
                model_meta=invocation.model_meta,
                message=invocation.error_message or "模型执行失败",
            )
            decision_error = {
                "stage": "TRADER",
                "status": invocation.failure_status,
                "error_type": invocation.error_type,
                "error_message": invocation.error_message,
            }
        else:
            payload = dict(invocation.payload or {})
            payload.update(
                plan_id=str(uuid4()),
                snapshot_id=snapshot_id,
                quant_proposal_id=LEGACY_QUANT_PROPOSAL_ID,
                model_meta=invocation.model_meta.model_dump(mode="json"),
            )
            try:
                plan = NormalTradePlan.model_validate(payload)
            except ValidationError as exc:
                message = f"NormalTradePlan schema validation failed: {exc.error_count()} error(s)"
                invalid_meta = _invalid_meta(
                    invocation.model_meta,
                    "SCHEMA_VALIDATION_ERROR",
                    message,
                )
                plan = _failure_plan(
                    state=state,
                    status="INVALID_OUTPUT",
                    model_meta=invalid_meta,
                    message=message,
                )
                decision_error = {
                    "stage": "TRADER",
                    "status": "INVALID_OUTPUT",
                    "error_type": "SCHEMA_VALIDATION_ERROR",
                    "error_message": message,
                }

        rendered = _render_plan(plan)
        plan_dict = plan.model_dump(mode="json")
        logger.info(
            "AlphaGuard Trader completed: status=%s action=%s plan_id=%s prompt=%s",
            plan.status,
            plan.action,
            plan.plan_id,
            NORMAL_TRADE_PROMPT_VERSION,
        )
        return {
            "messages": [AIMessage(content=rendered)],
            "normal_trade_plan": plan_dict,
            "normal_model_meta": plan.model_meta.model_dump(mode="json"),
            "decision_error": decision_error,
            # Compatibility/report field only. It is never parsed back into a
            # machine decision.
            "trader_investment_plan": rendered,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
