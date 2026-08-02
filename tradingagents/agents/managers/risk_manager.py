"""Risk Judge emitting PR-002 legacy or PR-005 quant-bound review objects."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from tradingagents.agents.utils.instrument_utils import build_instrument_context
from tradingagents.alphaguard.decision_control_schemas import (
    DecisionContext,
    canonical_hash,
)
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
    TopReviewDecision,
    validate_review_against_plan,
)
from tradingagents.alphaguard.structured_output import (
    invoke_json_object,
    model_output_schema,
    not_run_meta,
)
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")

TOP_REVIEW_PROMPT_NAME = "top_review_decision"
TOP_REVIEW_PROMPT_VERSION = "top_review_decision_v1"
TOP_REVIEW_QUANT_PROMPT_VERSION = "top_review_decision_quant_v1"


def _configured_provider(config: dict[str, Any]) -> str:
    return str(config.get("deep_provider") or config.get("llm_provider") or "unknown")


def _configured_model(config: dict[str, Any]) -> str | None:
    return config.get("deep_think_llm")


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


def _context_bound_review_schema(
    context: DecisionContext | None,
    normal_plan: NormalTradePlan,
) -> dict[str, Any]:
    schema = model_output_schema(TopReviewDecision)
    if context is None:
        return schema
    definitions = schema.get("$defs", {})
    evidence = definitions.get("EvidenceRef", {}).get("properties", {})
    if "evidence_id" in evidence:
        evidence["evidence_id"] = {
            "description": "Must be one of the immutable Snapshot evidence IDs.",
            "enum": sorted(context.evidence_ids()),
            "title": "Evidence Id",
            "type": "string",
        }
    adjusted = definitions.get("NormalTradePlan", {}).get("properties", {})
    if adjusted:
        adjusted["action"] = {
            "description": "Must not reverse or change the Normal plan direction.",
            "enum": list(dict.fromkeys([normal_plan.action, "NONE", "HOLD", "WAIT"])),
            "title": "Action",
            "type": "string",
        }
        for field in ("initial_position_pct", "max_position_pct"):
            maximum = getattr(normal_plan, field)
            if maximum is not None and field in adjusted:
                adjusted[field]["anyOf"] = [
                    {"maximum": maximum, "minimum": 0, "type": "number"},
                    {"type": "null"},
                ]
    return schema


def _failure_review(
    *,
    status: str,
    plan_id: str,
    snapshot_id: str,
    model_meta: ModelExecutionMeta,
    reason: str,
    context: DecisionContext | None = None,
    revision_round: int = 0,
) -> TopReviewDecision:
    return TopReviewDecision(
        review_id=str(uuid4()),
        snapshot_id=snapshot_id,
        plan_id=plan_id,
        analysis_id=context.analysis_id if context else None,
        decision_context_id=context.decision_context_id if context else None,
        quant_proposal_id=context.quant_proposal_id if context else None,
        symbol=context.symbol if context else None,
        market=context.market if context else None,
        trade_date=context.trade_date if context else None,
        strategy_id=context.strategy_id if context else None,
        strategy_version=context.strategy_version if context else None,
        revision_round=revision_round,
        status=status,
        completeness_score=0,
        logic_consistency_score=0,
        risk_control_score=0,
        missing_evidence=[],
        logical_conflicts=[],
        risk_findings=[],
        adjusted_plan=None,
        material_change_fields=[],
        review_reason=reason,
        model_meta=model_meta,
    )


def _render_review(review: TopReviewDecision) -> str:
    lines = [
        "# AlphaGuard 顶尖模型风险终审",
        f"- 状态：{review.status}",
        f"- 审核编号：{review.review_id}",
        f"- 原计划编号：{review.plan_id}",
        f"- 完整性评分：{review.completeness_score:.2f}",
        f"- 逻辑一致性评分：{review.logic_consistency_score:.2f}",
        f"- 风险控制评分：{review.risk_control_score:.2f}",
        f"- 终审理由：{review.review_reason}",
    ]
    if review.material_change_fields:
        lines.append("- 重大变更字段：" + ", ".join(review.material_change_fields))
    if review.model_meta.error_type:
        lines.append(f"- 错误类别：{review.model_meta.error_type}")
    lines.append(
        f"- Prompt：{review.model_meta.prompt_name}@{review.model_meta.prompt_version}"
    )
    return "\n".join(lines)


def create_risk_manager(llm, memory, config: dict[str, Any] | None = None):
    config = config or {}

    def risk_manager_node(state) -> dict:
        context = (
            DecisionContext.model_validate(state["decision_context"])
            if state.get("decision_context")
            else None
        )
        company_name = context.symbol if context else state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        risk_debate_state = dict(state.get("risk_debate_state") or {})
        reports = {
            "market_report": state.get("market_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "news_report": state.get("news_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
        }
        past_memory_str = ""
        # Formal quant review is snapshot-only; old memory is legacy-only.
        if memory is not None and context is None:
            try:
                memories = memory.get_memories(
                    "\n\n".join(str(value) for value in reports.values()),
                    n_matches=2,
                )
                past_memory_str = "\n\n".join(
                    str(item.get("recommendation", ""))
                    for item in memories
                    if item.get("recommendation")
                )
            except Exception as exc:
                logger.warning(
                    "Risk Judge memory lookup failed: %s", exc.__class__.__name__
                )

        prompt_version = (
            str(config.get("top_prompt_version"))
            if context and config.get("top_prompt_version")
            else TOP_REVIEW_QUANT_PROMPT_VERSION
            if context
            else TOP_REVIEW_PROMPT_VERSION
        )
        raw_plan = state.get("normal_trade_plan")
        try:
            if raw_plan is None:
                raise ValueError("normal_trade_plan is missing")
            normal_plan = NormalTradePlan.model_validate(raw_plan)
        except (ValidationError, ValueError, TypeError) as exc:
            message = "Risk Judge blocked: valid normal_trade_plan is required"
            meta = not_run_meta(
                llm=llm,
                provider=_configured_provider(config),
                configured_model_name=_configured_model(config),
                prompt_name=TOP_REVIEW_PROMPT_NAME,
                prompt_version=prompt_version,
                error_type="MISSING_OR_INVALID_NORMAL_PLAN",
                error_message=f"{message}: {exc.__class__.__name__}",
                trace_id=state.get("trace_id"),
                context_hash=(
                    state.get("model_runtime_context_hash")
                    or (context.context_hash if context else None)
                ),
                attempt_number=int(state.get("attempt_number") or 1),
            )
            review = _failure_review(
                status="INVALID_OUTPUT",
                plan_id="unavailable-plan",
                snapshot_id=(
                    context.snapshot_id
                    if context
                    else state.get("snapshot_id")
                    or f"legacy-analysis:{state.get('analysis_id') or 'unknown'}"
                ),
                model_meta=meta,
                reason=message,
                context=context,
            )
            decision_error = {
                "stage": "RISK_JUDGE",
                "status": "INVALID_OUTPUT",
                "error_type": "MISSING_OR_INVALID_NORMAL_PLAN",
                "error_message": message,
            }
        else:
            if normal_plan.status in {"MODEL_FAILED", "INVALID_OUTPUT"}:
                message = f"Risk Judge not run after {normal_plan.status}"
                meta = not_run_meta(
                    llm=llm,
                    provider=_configured_provider(config),
                    configured_model_name=_configured_model(config),
                    prompt_name=TOP_REVIEW_PROMPT_NAME,
                    prompt_version=prompt_version,
                    error_type=f"UPSTREAM_{normal_plan.status}",
                    error_message=message,
                    trace_id=state.get("trace_id"),
                    context_hash=(
                        state.get("model_runtime_context_hash")
                        or (context.context_hash if context else None)
                    ),
                    attempt_number=int(state.get("attempt_number") or 1),
                )
                review = _failure_review(
                    status="SUSPEND",
                    plan_id=normal_plan.plan_id,
                    snapshot_id=normal_plan.snapshot_id,
                    model_meta=meta,
                    reason=message,
                    context=context,
                    revision_round=normal_plan.revision_round,
                )
                decision_error = state.get("decision_error") or {
                    "stage": "TRADER",
                    "status": normal_plan.status,
                    "error_type": f"UPSTREAM_{normal_plan.status}",
                    "error_message": message,
                }
            else:
                output_schema = _context_bound_review_schema(context, normal_plan)
                output_schema_json = json.dumps(
                    output_schema, ensure_ascii=False, sort_keys=True
                )
                quant_rules = ""
                if context:
                    quant_rules = """
- 必须同时审阅 DecisionContext、原 QuantTradeProposal、NormalTradePlan、
  市场状态、账户/组合证据、风险政策摘要和快照风险事件。
- 不能独立发起或反转交易，不能提高仓位、扩大入场区间、延长有效期、
  删除原条件、改变策略/证据链/核心 thesis，或从 null 新增 target_price。
- RISK_ADJUST 只可降低仓位/置信度、缩窄区间、缩短有效期并追加风险条件。
- 无法证明纯降险时使用 MATERIAL_REVISION 或 REJECT。
- 方向错误必须 REJECT，不能在本链路研究相反方向。"""
                system_content = f"""你是 AlphaGuard 顶尖模型风险终审，不是第二个 Trader。唯一正式输出是严格 JSON。
Prompt：{TOP_REVIEW_PROMPT_NAME}@{prompt_version}
- 只能 CONFIRM、RISK_ADJUST、MATERIAL_REVISION、REJECT、SUSPEND。
- CONFIRM 不带 adjusted_plan；RISK_ADJUST 必须带 adjusted_plan。
- MATERIAL_REVISION 必须带 adjusted_plan 和 material_change_fields。
- REJECT/SUSPEND 不带 adjusted_plan。
- target_price 可为 null，禁止推算。
- 不得生成 model_meta，不得创建订单。
{quant_rules}
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
                        "normal_trade_plan": normal_plan.model_dump(mode="json"),
                        "market_regime": context.market_regime.model_dump(mode="json"),
                        "account_evidence": [
                            item.model_dump(mode="json")
                            for item in context.account_evidence
                        ],
                        "portfolio_evidence": [
                            item.model_dump(mode="json")
                            for item in context.portfolio_evidence
                        ],
                        "risk_policy_summary": state.get("risk_policy_summary"),
                        "evaluation_clock": state.get("evaluation_clock"),
                    }
                    if context
                    else {
                        "normal_trade_plan": normal_plan.model_dump(mode="json"),
                        "risk_debate_history": risk_debate_state.get("history", ""),
                        "reports": reports,
                        "past_memory": past_memory_str,
                    }
                )
                registered_template = config.get("top_prompt_template")
                if context and registered_template:
                    system_content = str(registered_template).format(
                        context_json=json.dumps(
                            context.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        normal_plan_json=json.dumps(
                            normal_plan.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        research_json=json.dumps(
                            state.get("tradingagents_research") or {},
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    )
                    system_content += (
                        "\n\nExact model-facing JSON Schema:\n"
                        + output_schema_json
                    )
                invocation = invoke_json_object(
                    llm=llm,
                    messages=[
                        {"role": "system", "content": system_content},
                        {
                            "role": "user",
                            "content": json.dumps(
                                user_payload, ensure_ascii=False, default=str
                            ),
                        },
                    ],
                    schema_model=TopReviewDecision,
                    provider=_configured_provider(config),
                    configured_model_name=_configured_model(config),
                    prompt_name=TOP_REVIEW_PROMPT_NAME,
                    prompt_version=prompt_version,
                    trace_id=state.get("trace_id"),
                    template_hash=hashlib.sha256(
                        system_content.encode()
                    ).hexdigest(),
                    context_hash=(
                        state.get("model_runtime_context_hash")
                        or (context.context_hash if context else None)
                    ),
                    input_hash=canonical_hash(user_payload),
                    attempt_number=int(state.get("attempt_number") or 1),
                    structured_output_mode=str(
                        config.get("top_structured_output_mode") or "AUTO"
                    ),
                    model_profile_id=config.get("top_profile_id"),
                    model_profile_version=config.get("top_profile_version"),
                    prompt_id=config.get("top_prompt_id"),
                    input_cost_per_million=config.get(
                        "top_input_cost_per_million"
                    ),
                    output_cost_per_million=config.get(
                        "top_output_cost_per_million"
                    ),
                    cost_currency=str(config.get("cost_currency") or "USD"),
                    max_retries=int(
                        state.get("model_max_retries")
                        if state.get("model_max_retries") is not None
                        else config.get("top_max_retries") or 0
                    ),
                    retry_backoff_seconds=float(
                        config.get("top_retry_backoff_seconds") or 0
                    ),
                    schema_override=output_schema,
                )
                decision_error = None
                if invocation.failure_status:
                    review = _failure_review(
                        status=invocation.failure_status,
                        plan_id=normal_plan.plan_id,
                        snapshot_id=normal_plan.snapshot_id,
                        model_meta=invocation.model_meta,
                        reason=invocation.error_message or "风险终审模型执行失败",
                        context=context,
                        revision_round=normal_plan.revision_round,
                    )
                    decision_error = {
                        "stage": "RISK_JUDGE",
                        "status": invocation.failure_status,
                        "error_type": invocation.error_type,
                        "error_message": invocation.error_message,
                    }
                else:
                    payload = dict(invocation.payload or {})
                    adjusted = payload.get("adjusted_plan")
                    attempted_identity_changes: list[str] = []
                    if isinstance(adjusted, dict):
                        adjusted = dict(adjusted)
                        for field in (
                            "plan_id",
                            "snapshot_id",
                            "quant_proposal_id",
                            "analysis_id",
                            "decision_context_id",
                            "symbol",
                            "market",
                            "strategy_id",
                            "strategy_version",
                            "revision_round",
                            "supersedes_plan_id",
                            "revision_request_id",
                        ):
                            supplied = adjusted.get(field)
                            expected = getattr(normal_plan, field)
                            if supplied is not None and str(supplied) != str(expected):
                                attempted_identity_changes.append(field)
                        adjusted.update(
                            {
                                field: getattr(normal_plan, field)
                                for field in (
                                    "plan_id",
                                    "snapshot_id",
                                    "quant_proposal_id",
                                    "analysis_id",
                                    "decision_context_id",
                                    "symbol",
                                    "market",
                                    "trade_date",
                                    "strategy_id",
                                    "strategy_version",
                                    "revision_round",
                                    "supersedes_plan_id",
                                    "revision_request_id",
                                )
                            },
                            model_meta=invocation.model_meta.model_dump(mode="json"),
                        )
                        payload["adjusted_plan"] = adjusted
                    payload.update(
                        review_id=str(uuid4()),
                        snapshot_id=normal_plan.snapshot_id,
                        plan_id=normal_plan.plan_id,
                        analysis_id=context.analysis_id if context else None,
                        decision_context_id=(
                            context.decision_context_id if context else None
                        ),
                        quant_proposal_id=(
                            context.quant_proposal_id if context else None
                        ),
                        symbol=context.symbol if context else None,
                        market=context.market if context else None,
                        trade_date=context.trade_date if context else None,
                        strategy_id=context.strategy_id if context else None,
                        strategy_version=(
                            context.strategy_version if context else None
                        ),
                        revision_round=normal_plan.revision_round,
                        model_meta=invocation.model_meta.model_dump(mode="json"),
                    )
                    try:
                        if attempted_identity_changes:
                            raise ValueError(
                                "top model attempted forbidden identity changes: "
                                + ", ".join(sorted(attempted_identity_changes))
                            )
                        review = TopReviewDecision.model_validate(payload)
                        validate_review_against_plan(review, normal_plan)
                        if context:
                            from app.services.alphaguard.decision_validation import (
                                validate_review_against_context,
                                validate_risk_adjustment,
                            )

                            validate_review_against_context(
                                review,
                                normal_plan,
                                context,
                                model_runtime_context_hash=state.get(
                                    "model_runtime_context_hash"
                                ),
                            )
                            if (
                                review.status == "RISK_ADJUST"
                                and review.adjusted_plan is not None
                            ):
                                violations = validate_risk_adjustment(
                                    normal_plan, review.adjusted_plan
                                )
                                if violations:
                                    raise ValueError("; ".join(violations))
                    except (ValidationError, ValueError) as exc:
                        reason = str(exc).replace("\n", " ").strip()[:240]
                        message = (
                            "TopReviewDecision schema/permission validation failed: "
                            f"{exc.__class__.__name__}"
                            + (f":{reason}" if reason else "")
                        )
                        review = _failure_review(
                            status="INVALID_OUTPUT",
                            plan_id=normal_plan.plan_id,
                            snapshot_id=normal_plan.snapshot_id,
                            model_meta=_invalid_meta(
                                invocation.model_meta,
                                "SCHEMA_VALIDATION_ERROR",
                                message,
                            ),
                            reason=message,
                            context=context,
                            revision_round=normal_plan.revision_round,
                        )
                        decision_error = {
                            "stage": "RISK_JUDGE",
                            "status": "INVALID_OUTPUT",
                            "error_type": "SCHEMA_VALIDATION_ERROR",
                            "error_message": message,
                        }

        rendered = _render_review(review)
        risk_debate_state.update(
            {"judge_decision": rendered, "latest_speaker": "Judge"}
        )
        logger.info(
            "AlphaGuard Risk Judge completed: status=%s review_id=%s prompt=%s",
            review.status,
            review.review_id,
            prompt_version,
        )
        return {
            "risk_debate_state": risk_debate_state,
            "top_review_decision": review.model_dump(mode="json"),
            "top_model_meta": review.model_meta.model_dump(mode="json"),
            "top_model_attempts": [
                item.model_dump(mode="json")
                for item in (
                    invocation.attempt_metas
                    if "invocation" in locals()
                    else (review.model_meta,)
                )
            ],
            "decision_error": decision_error,
            "final_trade_decision": rendered,
        }

    return risk_manager_node
