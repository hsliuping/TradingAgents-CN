"""Pure-Python identity, evidence, direction, and risk-adjustment validation."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.alphaguard.decision import DecisionContext
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
    TopReviewDecision,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _validate_model_meta(
    meta: ModelExecutionMeta,
    *,
    context: DecisionContext,
    prompt_versions: set[str],
    model_runtime_context_hash: str | None = None,
) -> None:
    expected_context_hash = model_runtime_context_hash or context.context_hash
    if meta.context_hash != expected_context_hash:
        raise ValueError("model execution context_hash mismatch")
    if (
        not meta.provider
        or not meta.model_name
        or not meta.model_version
        or not meta.prompt_name
        or meta.prompt_version not in prompt_versions
        or not meta.template_hash
        or not meta.input_hash
    ):
        raise ValueError("model execution metadata is incomplete")
    if not (meta.request_id or meta.trace_id):
        raise ValueError("model execution requires request_id or trace_id")
    if meta.execution_status == "SUCCESS" and not meta.raw_output_hash:
        raise ValueError("successful model execution requires raw_output_hash")


def validate_plan_against_context(
    plan: NormalTradePlan,
    context: DecisionContext,
    *,
    original_plan: NormalTradePlan | None = None,
    revision_request_id: str | None = None,
    additional_prompt_versions: set[str] | None = None,
    model_runtime_context_hash: str | None = None,
) -> None:
    required = {
        "analysis_id": (plan.analysis_id, context.analysis_id),
        "decision_context_id": (
            plan.decision_context_id,
            context.decision_context_id,
        ),
        "snapshot_id": (plan.snapshot_id, context.snapshot_id),
        "quant_proposal_id": (
            plan.quant_proposal_id,
            context.quant_proposal_id,
        ),
        "symbol": (plan.symbol, context.symbol),
        "market": (plan.market, context.market),
        "trade_date": (plan.trade_date, context.trade_date),
        "strategy_id": (plan.strategy_id, context.strategy_id),
        "strategy_version": (plan.strategy_version, context.strategy_version),
    }
    mismatches = [
        field for field, (actual, expected) in required.items() if actual != expected
    ]
    if mismatches:
        raise ValueError(f"plan context identity mismatch: {mismatches}")

    proposal = context.quant_proposal
    if plan.status == "PROPOSE_TRADE":
        if plan.action != proposal.action_candidate:
            raise ValueError("normal plan cannot reverse QuantTradeProposal action")
        if (
            plan.initial_position_pct is None
            or plan.max_position_pct is None
            or plan.initial_position_pct > proposal.initial_position_pct
            or plan.max_position_pct > proposal.max_position_pct
        ):
            raise ValueError("normal plan exceeds QuantTradeProposal position limits")
        referenced = {
            item.evidence_id
            for item in plan.bullish_evidence + plan.bearish_evidence
        }
        if not referenced:
            raise ValueError("PROPOSE_TRADE requires DecisionContext evidence")
        if not referenced.issubset(context.evidence_ids()):
            raise ValueError("normal plan references evidence outside DecisionContext")

    _validate_model_meta(
        plan.model_meta,
        context=context,
        prompt_versions={
            context.normal_prompt_version,
            "normal_trade_plan_revision_v1",
        }
        | (additional_prompt_versions or set()),
        model_runtime_context_hash=model_runtime_context_hash,
    )

    if original_plan is None:
        if plan.revision_round == 1 and (
            not plan.supersedes_plan_id or not plan.revision_request_id
        ):
            raise ValueError("persisted revision has incomplete lineage")
        if plan.revision_round not in {0, 1}:
            raise ValueError("revision_round must be 0 or 1")
    else:
        if (
            plan.revision_round != 1
            or plan.supersedes_plan_id != original_plan.plan_id
            or plan.revision_request_id != revision_request_id
        ):
            raise ValueError("revision lineage mismatch")
        if plan.action in {"BUY", "SELL", "REDUCE"} and (
            plan.action != context.quant_proposal.action_candidate
        ):
            raise ValueError("revision cannot reverse proposal direction")


def validate_review_against_context(
    review: TopReviewDecision,
    plan: NormalTradePlan,
    context: DecisionContext,
    *,
    model_runtime_context_hash: str | None = None,
) -> None:
    expected = {
        "analysis_id": context.analysis_id,
        "decision_context_id": context.decision_context_id,
        "quant_proposal_id": context.quant_proposal_id,
        "snapshot_id": context.snapshot_id,
        "plan_id": plan.plan_id,
        "symbol": context.symbol,
        "market": context.market,
        "trade_date": context.trade_date,
        "strategy_id": context.strategy_id,
        "strategy_version": context.strategy_version,
        "revision_round": plan.revision_round,
    }
    mismatches = [
        field for field, value in expected.items() if getattr(review, field) != value
    ]
    if mismatches:
        raise ValueError(f"review context identity mismatch: {mismatches}")
    if review.status == "CONFIRM" and plan.status != "PROPOSE_TRADE":
        raise ValueError("CONFIRM requires a proposed trade")
    _validate_model_meta(
        review.model_meta,
        context=context,
        prompt_versions={context.top_prompt_version},
        model_runtime_context_hash=model_runtime_context_hash,
    )
    if review.adjusted_plan is not None:
        validate_plan_against_context(
            review.adjusted_plan,
            context,
            additional_prompt_versions={context.top_prompt_version},
            model_runtime_context_hash=model_runtime_context_hash,
        )
        if review.status == "MATERIAL_REVISION":
            violations = validate_material_revision_authority(
                plan, review.adjusted_plan
            )
            if violations:
                raise ValueError("; ".join(violations))


def _contains_all(original: list, adjusted: list) -> bool:
    original_values = {
        item.model_dump_json(exclude_none=False) for item in original
    }
    adjusted_values = {
        item.model_dump_json(exclude_none=False) for item in adjusted
    }
    return original_values.issubset(adjusted_values)


def validate_material_revision_authority(
    original: NormalTradePlan,
    suggested: NormalTradePlan,
) -> list[str]:
    """A material request may change logic, but it still cannot raise risk."""

    errors: list[str] = []
    for field in (
        "action",
        "snapshot_id",
        "quant_proposal_id",
        "analysis_id",
        "decision_context_id",
        "symbol",
        "market",
        "trade_date",
        "strategy_id",
        "strategy_version",
    ):
        if getattr(suggested, field) != getattr(original, field):
            errors.append(f"{field} cannot be changed by MATERIAL_REVISION")
    for field in ("initial_position_pct", "max_position_pct", "confidence"):
        before, after = getattr(original, field), getattr(suggested, field)
        if before is not None and (after is None or after > before):
            errors.append(f"{field} cannot be increased or removed")
    if original.entry_zone is not None and (
        suggested.entry_zone is None
        or suggested.entry_zone.lower < original.entry_zone.lower
        or suggested.entry_zone.upper > original.entry_zone.upper
    ):
        errors.append("MATERIAL_REVISION cannot expand or remove entry_zone")
    if original.valid_until is not None and (
        suggested.valid_until is None
        or _aware(suggested.valid_until) > _aware(original.valid_until)
    ):
        errors.append("MATERIAL_REVISION cannot extend or remove valid_until")
    if original.target_price is None and suggested.target_price is not None:
        errors.append("MATERIAL_REVISION cannot invent target_price")
    elif original.target_price != suggested.target_price:
        errors.append("MATERIAL_REVISION cannot change target_price")
    for field in (
        "stop_conditions",
        "reduce_conditions",
        "exit_conditions",
        "invalidation_conditions",
        "main_risks",
    ):
        if not _contains_all(getattr(original, field), getattr(suggested, field)):
            errors.append(f"MATERIAL_REVISION cannot remove {field}")
    if suggested.add_conditions != original.add_conditions:
        errors.append("MATERIAL_REVISION cannot change add_conditions")
    return errors


def validate_risk_adjustment(
    original: NormalTradePlan,
    adjusted: NormalTradePlan,
) -> list[str]:
    """Return violations; an empty result proves the v1 adjustment is risk-only."""

    errors: list[str] = []
    immutable = (
        "analysis_id",
        "decision_context_id",
        "snapshot_id",
        "quant_proposal_id",
        "symbol",
        "market",
        "trade_date",
        "strategy_id",
        "strategy_version",
        "status",
        "action",
        "thesis",
        "target_price",
        "revision_round",
        "bullish_evidence",
        "bearish_evidence",
        "unresolved_questions",
        "entry_zone_not_required_reason",
        "valid_until_compatibility_reason",
    )
    for field in immutable:
        if getattr(adjusted, field) != getattr(original, field):
            errors.append(f"{field} cannot be changed by RISK_ADJUST")
    for field in ("initial_position_pct", "max_position_pct", "confidence"):
        before, after = getattr(original, field), getattr(adjusted, field)
        if before is None:
            if after is not None:
                errors.append(f"{field} cannot be introduced")
        elif after is None or after > before:
            errors.append(f"{field} can only be reduced")
    if original.entry_zone is None:
        if adjusted.entry_zone is not None:
            errors.append("entry_zone cannot be introduced")
    elif adjusted.entry_zone is None or (
        adjusted.entry_zone.lower < original.entry_zone.lower
        or adjusted.entry_zone.upper > original.entry_zone.upper
    ):
        errors.append("entry_zone must remain a subset")
    if original.valid_until is None:
        if adjusted.valid_until is not None:
            errors.append("valid_until cannot be introduced")
    elif adjusted.valid_until is None or _aware(adjusted.valid_until) > _aware(
        original.valid_until
    ):
        errors.append("valid_until can only be shortened")
    for field in (
        "stop_conditions",
        "reduce_conditions",
        "exit_conditions",
        "invalidation_conditions",
        "main_risks",
    ):
        if not _contains_all(getattr(original, field), getattr(adjusted, field)):
            errors.append(f"{field} may only append existing-safe conditions")
    if not _contains_all(original.add_conditions, adjusted.add_conditions) or (
        len(adjusted.add_conditions) != len(original.add_conditions)
    ):
        errors.append("add_conditions cannot be changed")
    return errors
