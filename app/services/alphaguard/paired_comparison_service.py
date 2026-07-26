"""Strict same-opportunity paired comparisons."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.evaluation_audit_service import EvaluationAuditService
from app.services.alphaguard.evaluation_policy_registry import evaluation_policy
from app.services.alphaguard.evaluation_repository import EvaluationRepository
from tradingagents.alphaguard.evaluation_schemas import (
    PairedDecisionComparison,
    evaluation_hash,
)


class PairedComparisonService:
    def __init__(self, db):
        self.db = db
        self.repository = EvaluationRepository(db)
        self.audit = EvaluationAuditService(db)
        self.version = evaluation_policy().comparison_version

    async def calculate_all(
        self,
        subjects: list,
        labels_by_subject: dict[str, list],
        *,
        evaluation_job_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[PairedDecisionComparison]:
        by_id = {item.subject_id: item for item in subjects}
        source_index = {
            (item.subject_type, item.source_object_id): item for item in subjects
        }
        pairs: list[tuple[str, object, object | None]] = []
        for right in subjects:
            lineage = right.lineage_ids
            left = None
            comparison_type = None
            if right.subject_type == "NORMAL_PLAN":
                left = source_index.get(
                    ("QUANT_PROPOSAL", lineage.get("proposal_id", ""))
                )
                comparison_type = "QUANT_VS_NORMAL"
            elif right.subject_type == "TOP_REVIEW":
                left = source_index.get(("NORMAL_PLAN", lineage.get("plan_id", "")))
                comparison_type = "NORMAL_VS_TOP"
            elif right.subject_type == "RISK_DECISION":
                consensus = source_index.get(
                    ("CONSENSUS", lineage.get("consensus_id", ""))
                )
                if consensus:
                    left = source_index.get(
                        ("TOP_REVIEW", consensus.lineage_ids.get("review_id", ""))
                    )
                comparison_type = (
                    "ORIGINAL_VS_RISK_REDUCED"
                    if right.decision_status == "REDUCE"
                    else "TOP_VS_HARD_RISK"
                )
            elif right.subject_type in {"ORDER_INTENT", "PAPER_ORDER", "PAPER_FILL"}:
                left = source_index.get(
                    ("RISK_DECISION", lineage.get("risk_decision_id", ""))
                ) or source_index.get(
                    ("NORMAL_PLAN", lineage.get("plan_id", ""))
                ) or source_index.get(
                    ("QUANT_PROPOSAL", lineage.get("proposal_id", ""))
                )
                comparison_type = "PLAN_VS_EXECUTION"
            if comparison_type and left:
                pairs.append((comparison_type, left, right))

        results = []
        seen = set()
        for comparison_type, left, right in pairs:
            identity = (comparison_type, left.subject_id, right.subject_id)
            if identity in seen:
                continue
            seen.add(identity)
            comparison = self.compare(
                comparison_type,
                left,
                right,
                labels_by_subject.get(left.subject_id, []),
                labels_by_subject.get(right.subject_id, []),
            )
            stored, _ = await self.repository.save_immutable(
                "paired_comparisons",
                comparison,
                identity={
                    "comparison_type": comparison.comparison_type,
                    "left_subject_id": comparison.left_subject_id,
                    "right_subject_id": comparison.right_subject_id,
                    "comparison_version": comparison.comparison_version,
                },
            )
            results.append(stored)
            await self.audit.record(
                (
                    "PAIRED_COMPARISON_CREATED"
                    if stored.pairing_status == "PAIRED"
                    else "PAIRED_COMPARISON_NOT_COMPARABLE"
                ),
                f"{stored.comparison_type} status={stored.pairing_status}",
                evaluation_job_id=evaluation_job_id,
                trace_id=trace_id,
                subject_id=left.subject_id,
                source_object_id=left.source_object_id,
                snapshot_id=left.snapshot_id,
                analysis_id=left.analysis_id,
                user_id=left.user_id,
                symbol=left.symbol,
                decision_trade_date=left.decision_trade_date,
                input_hash=stored.input_hash,
            )
        return results

    def compare(
        self,
        comparison_type: str,
        left,
        right,
        left_labels: list,
        right_labels: list,
    ) -> PairedDecisionComparison:
        reasons: list[str] = []
        if right is None:
            reasons.append("right subject is absent")
        else:
            for field in ("snapshot_id", "symbol", "market", "decision_trade_date"):
                if getattr(left, field) != getattr(right, field):
                    reasons.append(f"{field} differs")
        left_map = {
            item.horizon: item
            for item in left_labels
            if item.status == "CALCULATED" and item.anchor_type == "DECISION_CLOSE"
        }
        right_map = {
            item.horizon: item
            for item in right_labels
            if item.status == "CALCULATED" and item.anchor_type == "DECISION_CLOSE"
        }
        common = sorted(set(left_map) & set(right_map))
        if set(common) != {"1D", "5D", "10D", "20D"}:
            reasons.append("mature comparable horizons are incomplete")
        for horizon in common:
            left_label, right_label = left_map[horizon], right_map[horizon]
            if (
                left_label.price_data_version != right_label.price_data_version
                or left_label.price_adjustment_mode
                != right_label.price_adjustment_mode
                or left_label.benchmark_data_version
                != right_label.benchmark_data_version
                or left_label.benchmark_price_adjustment_mode
                != right_label.benchmark_price_adjustment_mode
                or left_label.horizon_end_date != right_label.horizon_end_date
            ):
                reasons.append(f"{horizon} price/evaluation contract differs")
        if comparison_type == "PLAN_VS_EXECUTION" and right is not None:
            if right.source_object_version is None:
                reasons.append("execution rule version is missing")
        paired = not reasons
        horizon_results: dict[str, dict] = {}
        values: dict[str, Decimal | None] = {}
        for horizon in ("1D", "5D", "10D", "20D"):
            left_label = left_map.get(horizon)
            right_label = right_map.get(horizon)
            left_value = left_label.action_aligned_return if left_label else None
            right_value = right_label.action_aligned_return if right_label else None
            value_added = (
                right_value - left_value
                if paired and left_value is not None and right_value is not None
                else None
            )
            values[horizon] = value_added
            horizon_results[horizon] = {
                "left_label_id": left_label.label_id if left_label else None,
                "right_label_id": right_label.label_id if right_label else None,
                "left_action_aligned_return": left_value,
                "right_action_aligned_return": right_value,
                "value_added": value_added,
                "comparable": paired,
            }
        payload = {
            "comparison_type": comparison_type,
            "snapshot_id": left.snapshot_id,
            "symbol": left.symbol,
            "decision_trade_date": left.decision_trade_date,
            "left_subject_id": left.subject_id,
            "right_subject_id": right.subject_id if right else None,
            "pairing_status": "PAIRED" if paired else "NOT_COMPARABLE",
            "comparability_reasons": reasons,
            "horizon_results": horizon_results,
            "execution_difference": {
                "left_executed": left.actual_execution_exists,
                "right_executed": (
                    right.actual_execution_exists if right else None
                ),
                "left_rule_version": left.source_object_version,
                "right_rule_version": (
                    right.source_object_version if right else None
                ),
            },
            "risk_difference": {
                "left_initial_position_pct": left.initial_position_pct,
                "right_initial_position_pct": (
                    right.initial_position_pct if right else None
                ),
                "left_max_position_pct": left.max_position_pct,
                "right_max_position_pct": (
                    right.max_position_pct if right else None
                ),
                "left_status": left.decision_status,
                "right_status": right.decision_status if right else None,
            },
            "value_added_1d": values["1D"],
            "value_added_5d": values["5D"],
            "value_added_10d": values["10D"],
            "value_added_20d": values["20D"],
            "comparison_version": self.version,
        }
        payload["input_hash"] = evaluation_hash(payload)
        right_id = right.subject_id if right else "missing"
        return PairedDecisionComparison(
            comparison_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:comparison:{comparison_type}:"
                    f"{left.subject_id}:{right_id}:{self.version}",
                )
            ),
            calculated_at=datetime.utcnow(),
            **payload,
        )
