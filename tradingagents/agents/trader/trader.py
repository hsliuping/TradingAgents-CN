"""Trader node emitting PR-002 legacy or PR-005 quant-bound NormalTradePlan."""

from __future__ import annotations

import functools
import hashlib
import json
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage
from pydantic import ValidationError

from tradingagents.agents.utils.instrument_utils import build_instrument_context
from tradingagents.alphaguard.decision_control_schemas import (
    DecisionContext,
    canonical_hash,
)
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
)
from tradingagents.alphaguard.structured_output import (
    invoke_json_object,
    model_output_schema,
)
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")

NORMAL_TRADE_PROMPT_NAME = "normal_trade_plan"
NORMAL_TRADE_PROMPT_VERSION = "normal_trade_plan_v1"
NORMAL_TRADE_QUANT_PROMPT_VERSION = "normal_trade_plan_quant_v1"
NORMAL_TRADE_REVISION_PROMPT_VERSION = "normal_trade_plan_revision_v1"
LEGACY_QUANT_PROPOSAL_ID = "legacy-quant:none"


def _decision_snapshot_id(state: dict[str, Any]) -> str:
    snapshot_id = state.get("snapshot_id")
    if snapshot_id:
        return str(snapshot_id)
    if state.get("legacy_analysis") is False:
        raise ValueError("non-legacy analysis requires snapshot_id")
    analysis_id = state.get("analysis_id")
    if not analysis_id:
        analysis_id = (
            f"{state.get('company_of_interest', 'unknown')}:"
            f"{state.get('trade_date', 'unknown-date')}"
        )
    return f"legacy-analysis:{analysis_id}"


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


def _validation_failure_detail(exc: Exception) -> str:
    if not isinstance(exc, ValidationError):
        reason = str(exc).replace("\n", " ").strip()[:240]
        return f"{exc.__class__.__name__}:{reason}" if reason else exc.__class__.__name__
    details = []
    for item in exc.errors(
        include_url=False,
        include_context=True,
        include_input=False,
    ):
        location = ".".join(str(part) for part in item.get("loc") or ()) or "root"
        error_type = str(item.get("type") or "validation_error")
        detail = f"{location}:{error_type}"
        # Pydantic's root validators otherwise collapse every semantic failure
        # to the same ``root:value_error`` marker.  The context contains the
        # validator's static ValueError, while ``include_input=False`` above
        # guarantees that no model payload or evidence text is retained.
        context = item.get("ctx")
        validator_error = context.get("error") if isinstance(context, dict) else None
        if validator_error is not None:
            safe_reason = str(validator_error).replace("\n", " ").strip()[:240]
            if safe_reason:
                detail = f"{detail}:{safe_reason}"
        details.append(detail)
    return "ValidationError[" + ",".join(details[:8]) + "]"


def _context_bound_plan_schema(context: DecisionContext | None) -> dict[str, Any]:
    """Compile existing DecisionContext limits into the model-facing schema."""

    schema = model_output_schema(NormalTradePlan)
    if context is None:
        return schema
    proposal = context.quant_proposal
    properties = schema["properties"]
    allowed_actions = [proposal.action_candidate, "NONE", "HOLD", "WAIT"]
    properties["action"] = {
        "description": (
            "For PROPOSE_TRADE the only allowed action is the immutable "
            f"QuantTradeProposal action {proposal.action_candidate}; passive "
            "outcomes use NONE, HOLD, or WAIT according to status."
        ),
        "enum": list(dict.fromkeys(allowed_actions)),
        "title": "Action",
        "type": "string",
    }
    for field, maximum in (
        ("initial_position_pct", proposal.initial_position_pct),
        ("max_position_pct", proposal.max_position_pct),
    ):
        properties[field]["anyOf"] = [
            {"maximum": maximum, "minimum": 0, "type": "number"},
            {"type": "null"},
        ]
        properties[field]["description"] += (
            f" Snapshot-bound maximum: {maximum}."
        )
    evidence = schema.get("$defs", {}).get("EvidenceRef", {})
    evidence_properties = evidence.get("properties", {})
    if "evidence_id" in evidence_properties:
        evidence_properties["evidence_id"] = {
            "description": "Must be one of the immutable Snapshot evidence IDs.",
            "enum": sorted(context.evidence_ids()),
            "title": "Evidence Id",
            "type": "string",
        }
    return schema


def _failure_plan(
    *,
    state: dict[str, Any],
    status: str,
    model_meta: ModelExecutionMeta,
    message: str,
) -> NormalTradePlan:
    context = (
        DecisionContext.model_validate(state["decision_context"])
        if state.get("decision_context")
        else None
    )
    revision = state.get("revision_request") or {}
    return NormalTradePlan(
        plan_id=str(uuid4()),
        snapshot_id=context.snapshot_id if context else _decision_snapshot_id(state),
        quant_proposal_id=(
            context.quant_proposal_id if context else LEGACY_QUANT_PROPOSAL_ID
        ),
        analysis_id=context.analysis_id if context else state.get("analysis_id"),
        decision_context_id=context.decision_context_id if context else None,
        symbol=context.symbol if context else None,
        market=context.market if context else state.get("market"),
        trade_date=context.trade_date if context else None,
        strategy_id=context.strategy_id if context else None,
        strategy_version=context.strategy_version if context else None,
        revision_round=1 if revision else 0,
        supersedes_plan_id=revision.get("original_plan_id"),
        revision_request_id=revision.get("revision_request_id"),
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


def _render_plan(plan: NormalTradePlan) -> str:
    lines = [
        "# AlphaGuard 普通模型交易计划",
        f"- 状态：{plan.status}",
        f"- 动作：{plan.action}",
        f"- 置信度：{plan.confidence:.2f}",
        f"- 计划编号：{plan.plan_id}",
        f"- 快照编号：{plan.snapshot_id}",
        f"- 结论：{plan.thesis}",
        (
            f"- 目标价：{plan.target_price}"
            if plan.target_price is not None
            else "- 目标价：未提供（未推算）"
        ),
    ]
    if plan.model_meta.error_type:
        lines.append(f"- 错误类别：{plan.model_meta.error_type}")
    lines.append(
        f"- Prompt：{plan.model_meta.prompt_name}@{plan.model_meta.prompt_version}"
    )
    return "\n".join(lines)


def create_trader(llm, memory, config: dict[str, Any] | None = None):
    config = config or {}

    def trader_node(state, name):
        context = (
            DecisionContext.model_validate(state["decision_context"])
            if state.get("decision_context")
            else None
        )
        company_name = context.symbol if context else state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        reports = {
            "market_report": state.get("market_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "news_report": state.get("news_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
        }
        current_situation = "\n\n".join(str(value) for value in reports.values())
        past_memory_str = "暂无历史记忆数据可参考。"
        # Quant mode is entirely determined by DecisionContext; old vector
        # memory is never injected into the formal PR-005 model input.
        if memory is not None and context is None:
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

        revision = state.get("revision_request")
        prompt_version = (
            str(config.get("normal_revision_prompt_version"))
            if revision and config.get("normal_revision_prompt_version")
            else str(config.get("normal_prompt_version"))
            if context and config.get("normal_prompt_version")
            else NORMAL_TRADE_REVISION_PROMPT_VERSION
            if revision
            else NORMAL_TRADE_QUANT_PROMPT_VERSION
            if context
            else NORMAL_TRADE_PROMPT_VERSION
        )
        snapshot_id = context.snapshot_id if context else _decision_snapshot_id(state)
        proposal_id = (
            context.quant_proposal_id if context else LEGACY_QUANT_PROPOSAL_ID
        )
        quant_rules = ""
        if context:
            proposal = context.quant_proposal
            quant_rules = f"""
- 唯一 QuantTradeProposal 为 {proposal.proposal_id}，方向为 {proposal.action_candidate}。
- PROPOSE_TRADE 只能使用 {proposal.action_candidate}，不得反向。
- initial_position_pct 不得超过 {proposal.initial_position_pct}；
  max_position_pct 不得超过 {proposal.max_position_pct}。
- 只能引用 DecisionContext 中已有 EvidenceRef；不得搜索或补全快照外数据。
- 运行时会注入全部证据链 ID、策略、标的和日期字段。
- missing_evidence 不得被描述成中性或安全事实。"""
        revision_rules = (
            """
- 这是唯一允许的 revision_round=1，必须回应 RevisionRequest。
- 可以改为 WAIT、NO_TRADE 或 INSUFFICIENT_DATA，但不得反向交易。
- 第二次终审后不会再次返回普通模型。"""
            if revision
            else ""
        )
        output_schema = _context_bound_plan_schema(context)
        output_schema_json = json.dumps(
            output_schema, ensure_ascii=False, sort_keys=True
        )
        system_content = f"""你是 AlphaGuard 的普通模型 Trader。唯一正式输出是严格 JSON，不得输出 JSON 以外文本。
Prompt：{NORMAL_TRADE_PROMPT_NAME}@{prompt_version}
- 证据不足：INSUFFICIENT_DATA + NONE。
- 可观察的不确定性：WAIT + WAIT。
- 正常不交易：NO_TRADE + NONE/HOLD。
- 完整交易计划：PROPOSE_TRADE + BUY/SELL/REDUCE。
- target_price 可以为 null，禁止推算或猜测。
- 不得生成 model_meta；运行时注入。
- snapshot_id 必须是 {snapshot_id}；quant_proposal_id 必须是 {proposal_id}。
- 失败、空白或缺字段不得伪装成 HOLD。
{quant_rules}
{revision_rules}
JSON Schema：
{output_schema_json}
标的约束：
{instrument_context}"""
        user_payload = (
            {
                "decision_context": context.model_dump(mode="json"),
                "quant_trade_proposal": context.quant_proposal.model_dump(
                    mode="json"
                ),
                "revision_request": revision,
                "original_plan": state.get("original_normal_trade_plan"),
                "evaluation_clock": state.get("evaluation_clock"),
            }
            if context
            else {
                "company": company_name,
                "trade_date": state.get("trade_date"),
                "legacy_research_plan": state.get("investment_plan", ""),
                "reports": reports,
                "past_memory": past_memory_str,
            }
        )
        registered_template = config.get(
            "normal_revision_prompt_template"
            if revision
            else "normal_prompt_template"
        )
        if context and registered_template:
            system_content = str(registered_template).format(
                context_json=json.dumps(
                    context.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                research_json=json.dumps(
                    state.get("tradingagents_research") or {},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                normal_plan_json=json.dumps(
                    state.get("original_normal_trade_plan") or {},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                revision_request_json=json.dumps(
                    revision or {},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
            system_content += (
                "\n\nExact model-facing JSON Schema:\n"
                + output_schema_json
            )
        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": json.dumps(
                    user_payload, ensure_ascii=False, default=str
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
            prompt_version=prompt_version,
            trace_id=state.get("trace_id"),
            template_hash=hashlib.sha256(system_content.encode()).hexdigest(),
            context_hash=(
                state.get("model_runtime_context_hash")
                or (context.context_hash if context else None)
            ),
            input_hash=canonical_hash(user_payload),
            attempt_number=int(state.get("attempt_number") or 1),
            structured_output_mode=str(
                config.get("normal_structured_output_mode") or "AUTO"
            ),
            model_profile_id=config.get("normal_profile_id"),
            model_profile_version=config.get("normal_profile_version"),
            prompt_id=config.get("normal_prompt_id"),
            input_cost_per_million=config.get("normal_input_cost_per_million"),
            output_cost_per_million=config.get("normal_output_cost_per_million"),
            cost_currency=str(config.get("cost_currency") or "USD"),
            max_retries=int(
                state.get("model_max_retries")
                if state.get("model_max_retries") is not None
                else config.get("normal_max_retries") or 0
            ),
            retry_backoff_seconds=float(
                config.get("normal_retry_backoff_seconds") or 0
            ),
            schema_override=output_schema,
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
                quant_proposal_id=proposal_id,
                analysis_id=context.analysis_id if context else state.get("analysis_id"),
                decision_context_id=context.decision_context_id if context else None,
                symbol=context.symbol if context else None,
                market=context.market if context else state.get("market"),
                trade_date=context.trade_date if context else None,
                strategy_id=context.strategy_id if context else None,
                strategy_version=context.strategy_version if context else None,
                revision_round=1 if revision else 0,
                supersedes_plan_id=revision.get("original_plan_id") if revision else None,
                revision_request_id=(
                    revision.get("revision_request_id") if revision else None
                ),
                model_meta=invocation.model_meta.model_dump(mode="json"),
            )
            try:
                plan = NormalTradePlan.model_validate(payload)
                if context:
                    from app.services.alphaguard.decision_validation import (
                        validate_plan_against_context,
                    )

                    original = (
                        NormalTradePlan.model_validate(
                            state["original_normal_trade_plan"]
                        )
                        if revision
                        else None
                    )
                    validate_plan_against_context(
                        plan,
                        context,
                        original_plan=original,
                        revision_request_id=(
                            revision.get("revision_request_id") if revision else None
                        ),
                        model_runtime_context_hash=state.get(
                            "model_runtime_context_hash"
                        ),
                    )
            except (ValidationError, ValueError) as exc:
                message = (
                    "NormalTradePlan schema/context validation failed: "
                    f"{_validation_failure_detail(exc)}"
                )
                plan = _failure_plan(
                    state=state,
                    status="INVALID_OUTPUT",
                    model_meta=_invalid_meta(
                        invocation.model_meta,
                        "SCHEMA_VALIDATION_ERROR",
                        message,
                    ),
                    message=message,
                )
                decision_error = {
                    "stage": "TRADER",
                    "status": "INVALID_OUTPUT",
                    "error_type": "SCHEMA_VALIDATION_ERROR",
                    "error_message": message,
                }

        rendered = _render_plan(plan)
        logger.info(
            "AlphaGuard Trader completed: status=%s action=%s plan_id=%s prompt=%s",
            plan.status,
            plan.action,
            plan.plan_id,
            prompt_version,
        )
        return {
            "messages": [AIMessage(content=rendered)],
            "normal_trade_plan": plan.model_dump(mode="json"),
            "normal_model_meta": plan.model_meta.model_dump(mode="json"),
            "normal_model_attempts": [
                item.model_dump(mode="json")
                for item in invocation.attempt_metas
            ],
            "decision_error": decision_error,
            "trader_investment_plan": rendered,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
