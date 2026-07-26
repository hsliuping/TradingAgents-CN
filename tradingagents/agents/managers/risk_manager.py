"""Risk Judge node that emits AlphaGuard's authoritative TopReviewDecision."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from tradingagents.agents.utils.instrument_utils import build_instrument_context
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
    TopReviewDecision,
    validate_review_against_plan,
)
from tradingagents.alphaguard.structured_output import (
    invoke_json_object,
    model_output_schema_json,
    not_run_meta,
)
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")

TOP_REVIEW_PROMPT_NAME = "top_review_decision"
TOP_REVIEW_PROMPT_VERSION = "top_review_decision_v1"


def _configured_provider(config: dict[str, Any]) -> str:
    return str(
        config.get("deep_provider") or config.get("llm_provider") or "unknown"
    )


def _configured_model(config: dict[str, Any]) -> str | None:
    return config.get("deep_think_llm")


def _failure_review(
    *,
    status: str,
    plan_id: str,
    snapshot_id: str,
    model_meta: ModelExecutionMeta,
    reason: str,
) -> TopReviewDecision:
    return TopReviewDecision(
        review_id=str(uuid4()),
        snapshot_id=snapshot_id,
        plan_id=plan_id,
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


def _render_review(review: TopReviewDecision) -> str:
    """Human/report compatibility text derived only from the validated review."""

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
        lines.append(
            "- 重大变更字段：" + ", ".join(review.material_change_fields)
        )
    if review.model_meta.error_type:
        lines.append(f"- 错误类别：{review.model_meta.error_type}")
    lines.append(
        f"- Prompt：{review.model_meta.prompt_name}@{review.model_meta.prompt_version}"
    )
    return "\n".join(lines)


def create_risk_manager(llm, memory, config: dict[str, Any] | None = None):
    config = config or {}

    def risk_manager_node(state) -> dict:
        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        risk_debate_state = dict(state.get("risk_debate_state") or {})
        history = str(risk_debate_state.get("history", ""))
        reports = {
            "market_report": state.get("market_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "news_report": state.get("news_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
        }
        current_situation = "\n\n".join(str(value) for value in reports.values())

        past_memory_str = ""
        if memory is not None:
            try:
                memories = memory.get_memories(current_situation, n_matches=2)
                past_memory_str = "\n\n".join(
                    str(item.get("recommendation", ""))
                    for item in memories
                    if item.get("recommendation")
                )
            except Exception as exc:
                logger.warning(
                    "Risk Judge memory lookup failed; continuing without memory: %s",
                    exc.__class__.__name__,
                )

        raw_plan = state.get("normal_trade_plan")
        try:
            if raw_plan is None:
                raise ValueError("normal_trade_plan is missing from AgentState")
            normal_plan = NormalTradePlan.model_validate(raw_plan)
        except (ValidationError, ValueError, TypeError) as exc:
            message = "Risk Judge blocked: valid normal_trade_plan is required"
            meta = not_run_meta(
                llm=llm,
                provider=_configured_provider(config),
                configured_model_name=_configured_model(config),
                prompt_name=TOP_REVIEW_PROMPT_NAME,
                prompt_version=TOP_REVIEW_PROMPT_VERSION,
                error_type="MISSING_OR_INVALID_NORMAL_PLAN",
                error_message=f"{message}: {exc.__class__.__name__}",
            )
            review = _failure_review(
                status="INVALID_OUTPUT",
                plan_id="unavailable-plan",
                snapshot_id=(
                    state.get("snapshot_id")
                    or f"legacy-analysis:{state.get('analysis_id') or 'unknown'}"
                ),
                model_meta=meta,
                reason=message,
            )
            decision_error = {
                "stage": "RISK_JUDGE",
                "status": "INVALID_OUTPUT",
                "error_type": "MISSING_OR_INVALID_NORMAL_PLAN",
                "error_message": message,
            }
        else:
            if normal_plan.status in {"MODEL_FAILED", "INVALID_OUTPUT"}:
                message = (
                    "Risk Judge suspended because the authoritative normal plan "
                    f"ended with {normal_plan.status}"
                )
                meta = not_run_meta(
                    llm=llm,
                    provider=_configured_provider(config),
                    configured_model_name=_configured_model(config),
                    prompt_name=TOP_REVIEW_PROMPT_NAME,
                    prompt_version=TOP_REVIEW_PROMPT_VERSION,
                    error_type=f"UPSTREAM_{normal_plan.status}",
                    error_message=message,
                )
                review = _failure_review(
                    status="SUSPEND",
                    plan_id=normal_plan.plan_id,
                    snapshot_id=normal_plan.snapshot_id,
                    model_meta=meta,
                    reason=message,
                )
                decision_error = state.get("decision_error") or {
                    "stage": "TRADER",
                    "status": normal_plan.status,
                    "error_type": f"UPSTREAM_{normal_plan.status}",
                    "error_message": message,
                }
            else:
                schema_json = model_output_schema_json(TopReviewDecision)
                messages = [
                    {
                        "role": "system",
                        "content": f"""你是 AlphaGuard 的顶尖模型风险终审（Risk Judge），不是第二个独立 Trader。你的唯一正式机器输出是一个严格 JSON 对象，不得输出 Markdown、解释前缀或 JSON 之外的文本。

Prompt 名称与固定版本：{TOP_REVIEW_PROMPT_NAME}@{TOP_REVIEW_PROMPT_VERSION}

强制语义：
- 只能对给定 NormalTradePlan 做 CONFIRM、RISK_ADJUST、MATERIAL_REVISION、REJECT 或 SUSPEND。
- 不得绕过普通模型独立发起交易，不得把非交易计划改成交易计划，不得产生与原计划方向相反的新交易。
- CONFIRM 时 adjusted_plan 必须为 null。
- RISK_ADJUST 必须提供 adjusted_plan。
- MATERIAL_REVISION 必须提供 adjusted_plan 和非空 material_change_fields。
- REJECT/SUSPEND 不得产生 adjusted_plan。
- target_price 可以为 null；不得推算、猜测或因其缺失改变动作。
- 不得生成 model_meta；运行时会注入真实模型执行元数据。
- 不得创建订单，也不得假设 ConsensusEngine、HardRiskEngine 或 PR-003 证据快照已经存在。

模型输出 JSON Schema：
{schema_json}

标的约束：
{instrument_context}""",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "normal_trade_plan": normal_plan.model_dump(
                                    mode="json"
                                ),
                                "risk_debate_history": history,
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
                    schema_model=TopReviewDecision,
                    provider=_configured_provider(config),
                    configured_model_name=_configured_model(config),
                    prompt_name=TOP_REVIEW_PROMPT_NAME,
                    prompt_version=TOP_REVIEW_PROMPT_VERSION,
                )
                decision_error = None
                if invocation.failure_status:
                    review = _failure_review(
                        status=invocation.failure_status,
                        plan_id=normal_plan.plan_id,
                        snapshot_id=normal_plan.snapshot_id,
                        model_meta=invocation.model_meta,
                        reason=invocation.error_message or "风险终审模型执行失败",
                    )
                    decision_error = {
                        "stage": "RISK_JUDGE",
                        "status": invocation.failure_status,
                        "error_type": invocation.error_type,
                        "error_message": invocation.error_message,
                    }
                else:
                    payload = dict(invocation.payload or {})
                    adjusted_plan = payload.get("adjusted_plan")
                    if isinstance(adjusted_plan, dict):
                        adjusted_plan = dict(adjusted_plan)
                        adjusted_plan.update(
                            plan_id=normal_plan.plan_id,
                            snapshot_id=normal_plan.snapshot_id,
                            quant_proposal_id=normal_plan.quant_proposal_id,
                            model_meta=invocation.model_meta.model_dump(mode="json"),
                        )
                        payload["adjusted_plan"] = adjusted_plan
                    payload.update(
                        review_id=str(uuid4()),
                        snapshot_id=normal_plan.snapshot_id,
                        plan_id=normal_plan.plan_id,
                        model_meta=invocation.model_meta.model_dump(mode="json"),
                    )
                    try:
                        review = TopReviewDecision.model_validate(payload)
                        validate_review_against_plan(review, normal_plan)
                    except (ValidationError, ValueError) as exc:
                        message = (
                            "TopReviewDecision schema/relationship validation "
                            f"failed: {exc.__class__.__name__}"
                        )
                        invalid_meta = _invalid_meta(
                            invocation.model_meta,
                            "SCHEMA_VALIDATION_ERROR",
                            message,
                        )
                        review = _failure_review(
                            status="INVALID_OUTPUT",
                            plan_id=normal_plan.plan_id,
                            snapshot_id=normal_plan.snapshot_id,
                            model_meta=invalid_meta,
                            reason=message,
                        )
                        decision_error = {
                            "stage": "RISK_JUDGE",
                            "status": "INVALID_OUTPUT",
                            "error_type": "SCHEMA_VALIDATION_ERROR",
                            "error_message": message,
                        }

        rendered = _render_review(review)
        risk_debate_state.update(
            {
                "judge_decision": rendered,
                "latest_speaker": "Judge",
            }
        )
        review_dict = review.model_dump(mode="json")
        logger.info(
            "AlphaGuard Risk Judge completed: status=%s review_id=%s prompt=%s",
            review.status,
            review.review_id,
            TOP_REVIEW_PROMPT_VERSION,
        )
        return {
            "risk_debate_state": risk_debate_state,
            "top_review_decision": review_dict,
            "top_model_meta": review.model_meta.model_dump(mode="json"),
            "decision_error": decision_error,
            # Compatibility/report field only. It is never parsed back into a
            # machine decision.
            "final_trade_decision": rendered,
        }

    return risk_manager_node
