"""Rule-based diagnostic attribution, explicitly not causal inference."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.services.alphaguard.attribution_rule_registry import (
    AttributionRuleRegistry,
)
from app.services.alphaguard.evaluation_audit_service import EvaluationAuditService
from app.services.alphaguard.evaluation_repository import EvaluationRepository
from tradingagents.alphaguard.evaluation_schemas import (
    AttributionOverride,
    AttributionRecord,
    evaluation_hash,
)


class AttributionEngine:
    def __init__(self, db):
        self.db = db
        self.registry = AttributionRuleRegistry()
        self.repository = EvaluationRepository(db)
        self.audit = EvaluationAuditService(db)

    async def calculate_all(
        self,
        subjects: list,
        labels_by_subject: dict[str, list],
        counterfactuals_by_subject: dict[str, list],
        comparisons: list,
        *,
        evaluation_job_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[AttributionRecord]:
        comparison_map: dict[str, list] = {}
        for comparison in comparisons:
            comparison_map.setdefault(comparison.left_subject_id, []).append(comparison)
            if comparison.right_subject_id:
                comparison_map.setdefault(comparison.right_subject_id, []).append(
                    comparison
                )
        results = []
        for subject in subjects:
            record = self.evaluate(
                subject,
                labels_by_subject.get(subject.subject_id, []),
                counterfactuals_by_subject.get(subject.subject_id, []),
                comparison_map.get(subject.subject_id, []),
            )
            stored, _ = await self.repository.save_attribution(record)
            results.append(stored)
            await self.audit.record(
                (
                    "ATTRIBUTION_CREATED"
                    if stored.status == "ATTRIBUTED"
                    else "ATTRIBUTION_INSUFFICIENT_EVIDENCE"
                ),
                f"rule-based diagnostic attribution status={stored.status}",
                evaluation_job_id=evaluation_job_id,
                trace_id=trace_id,
                subject_id=subject.subject_id,
                source_object_id=subject.source_object_id,
                snapshot_id=subject.snapshot_id,
                analysis_id=subject.analysis_id,
                user_id=subject.user_id,
                symbol=subject.symbol,
                decision_trade_date=subject.decision_trade_date,
                input_hash=stored.input_hash,
            )
        return results

    def evaluate(
        self,
        subject,
        labels: list,
        counterfactuals: list,
        comparisons: list,
    ) -> AttributionRecord:
        primary = next(
            (
                item
                for item in labels
                if item.horizon == self.registry.policy.primary_horizon
                and item.anchor_type == "DECISION_CLOSE"
            ),
            None,
        )
        if primary is None or primary.status == "PENDING":
            return self._record(
                subject,
                status="PENDING_HORIZON",
                outcome="UNRESOLVED",
                category=None,
                confidence=Decimal("0"),
                codes=["PRIMARY_HORIZON_NOT_MATURE"],
                evidence=[],
                explanation="Primary 10D horizon is not mature.",
                input_objects=[primary],
            )
        if primary.status != "CALCULATED":
            return self._record(
                subject,
                status="ATTRIBUTED",
                outcome="UNRESOLVED",
                category="DATA_QUALITY",
                confidence=Decimal("0.95"),
                codes=["ADJUSTED_PRICE_OR_BENCHMARK_UNAVAILABLE"],
                evidence=primary.data_refs,
                explanation=(
                    "Evaluation cannot establish a reliable adjusted-price "
                    "outcome; this is a data-quality diagnosis."
                ),
                input_objects=[primary],
            )
        threshold = self.registry.thresholds
        raw = primary.raw_forward_return or Decimal("0")
        aligned = primary.action_aligned_return
        non_trade = subject.action in {"HOLD", "WAIT", "REJECT", "SUSPEND"}
        if non_trade:
            if raw >= threshold["missed_opportunity_return"]:
                outcome = "MISSED_OPPORTUNITY"
            elif raw <= threshold["avoided_loss_return"]:
                outcome = "AVOIDED_LOSS"
            else:
                outcome = "NEUTRAL"
        elif aligned is not None and aligned >= threshold["success_return"]:
            outcome = "SUCCESS"
        elif aligned is not None and aligned <= threshold["loss_return"]:
            outcome = "LOSS"
        else:
            outcome = "NEUTRAL"

        category = None
        codes: list[str] = []
        confidence = Decimal("0.65")
        future_shock_refs = [
            item.evidence_id
            for item in subject.evidence_refs
            if item.source == "market_shock"
            and item.as_of is not None
            and item.as_of > subject.decision_cutoff_at
        ]
        if future_shock_refs and outcome == "LOSS":
            category = "MARKET_SHOCK"
            codes.append("STRUCTURED_POST_CUTOFF_MARKET_SHOCK")
            confidence = Decimal("0.80")
        elif (
            subject.entry_zone is not None
            and primary.entry_zone_touched is False
        ) or (
            primary.mae is not None
            and primary.mae <= threshold["material_mae"]
            and raw > 0
        ):
            category = "STRATEGY_ENTRY"
            codes.append(
                "ENTRY_ZONE_NOT_TOUCHED"
                if primary.entry_zone_touched is False
                else "EARLY_ENTRY_WITH_MATERIAL_MAE"
            )
            confidence = Decimal("0.80")
        elif subject.decision_stage == "EXECUTION" and (
            not subject.actual_execution_exists
            or subject.decision_status
            in {
                "REJECTED",
                "EXPIRED",
                "CANCELLED",
                "SETTLEMENT_FAILED",
            }
        ):
            category = "EXECUTION"
            codes.append("EXECUTION_DID_NOT_COMPLETE")
            confidence = Decimal("0.90")
        elif subject.decision_stage == "HARD_RISK":
            category = "HARD_RISK"
            codes.append(
                "RISK_AVOIDED_LOSS"
                if outcome == "AVOIDED_LOSS"
                else "RISK_MISSED_OPPORTUNITY"
                if outcome == "MISSED_OPPORTUNITY"
                else "RISK_OUTCOME_DIAGNOSTIC"
            )
        elif subject.decision_stage == "CONSENSUS":
            category = "CONSENSUS"
            codes.append("CONSENSUS_OUTCOME_DIAGNOSTIC")
        elif subject.decision_stage == "TOP_MODEL":
            category = "TOP_MODEL"
            codes.append(
                "TOP_REJECTION_OUTCOME"
                if non_trade
                else "TOP_CONFIRMATION_OUTCOME"
            )
        elif subject.decision_stage == "NORMAL_MODEL":
            category = "NORMAL_MODEL"
            codes.append(
                "NORMAL_MODEL_RELIABILITY_FAILURE"
                if subject.decision_status in {"MODEL_FAILED", "INVALID_OUTPUT"}
                else "NORMAL_MODEL_OUTCOME_DIAGNOSTIC"
            )
        elif subject.decision_stage == "QUANT":
            if (
                subject.decision_status in {"WATCH", "REJECTED"}
                and raw <= threshold["avoided_loss_return"]
            ):
                category = "CANDIDATE_SELECTION"
                codes.append("CANDIDATE_FILTERED_FUTURE_WEAKNESS")
            elif (
                primary.benchmark_return is not None
                and primary.benchmark_return
                <= threshold["avoided_loss_return"]
                and (
                    subject.selected_for_execution
                    or subject.decision_status == "TRIGGERED"
                )
            ):
                category = "REGIME_MISCLASSIFICATION"
                codes.append("RISKY_BENCHMARK_REGIME_ALLOWED_ENTRY")
            elif (
                outcome == "LOSS"
                and primary.relative_benchmark_return is not None
                and primary.relative_benchmark_return
                <= threshold["loss_return"]
            ):
                category = "FACTOR_FAILURE"
                codes.append("TRIGGERED_SIGNAL_UNDERPERFORMED_BENCHMARK")
            else:
                category = "CANDIDATE_SELECTION"
                codes.append("QUANT_CANDIDATE_OUTCOME_DIAGNOSTIC")
        else:
            category = "UNKNOWN"
            codes.append("NO_RULE_CAN_DISTINGUISH_PRIMARY_DRIVER")
            confidence = Decimal("0.25")

        contributing = []
        if category != "EXECUTION" and any(
            item.status in {"NO_FILL", "FAILED"} for item in counterfactuals
        ):
            contributing.append("EXECUTION")
        if category != "DATA_QUALITY" and primary.benchmark_return is None:
            contributing.append("DATA_QUALITY")
        evidence = sorted(
            set(
                primary.data_refs
                + future_shock_refs
                + [
                    comparison.comparison_id
                    for comparison in comparisons
                    if comparison.pairing_status == "PAIRED"
                ]
            )
        )
        return self._record(
            subject,
            status="ATTRIBUTED",
            outcome=outcome,
            category=category,
            confidence=confidence,
            codes=codes,
            evidence=evidence,
            explanation=(
                f"Rule-based diagnostic classified {outcome} at "
                f"{self.registry.policy.primary_horizon}; primary category "
                f"is {category}. This is not a causal claim."
            ),
            contributing=contributing,
            input_objects=[primary, counterfactuals, comparisons],
        )

    def _record(
        self,
        subject,
        *,
        status,
        outcome,
        category,
        confidence,
        codes,
        evidence,
        explanation,
        input_objects,
        contributing=None,
    ) -> AttributionRecord:
        rule_ids = [self.registry.rule_id(category)] if category else []
        payload = {
            "subject_id": subject.subject_id,
            "status": status,
            "outcome_class": outcome,
            "primary_category": category,
            "contributing_categories": contributing or [],
            "confidence": confidence,
            "rule_ids": rule_ids,
            "evidence_refs": sorted(set(evidence)),
            "explanation_codes": codes,
            "machine_explanation": explanation,
            "attribution_rule_version": self.registry.version,
            "calculated_at": (
                datetime.utcnow() if status in {"ATTRIBUTED", "NOT_REQUIRED"} else None
            ),
        }
        payload["input_hash"] = evaluation_hash(
            {
                **payload,
                "subject_hash": subject.immutable_hash,
                "inputs": input_objects,
            },
            exclude={"calculated_at"},
        )
        return AttributionRecord(
            attribution_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:attribution:{subject.subject_id}:"
                    f"{self.registry.version}",
                )
            ),
            **payload,
        )

    async def append_override(
        self,
        *,
        attribution: AttributionRecord,
        user_id: str,
        category: str,
        reason: str,
        trace_id: str | None = None,
    ) -> AttributionOverride:
        override = AttributionOverride(
            override_id=str(uuid4()),
            attribution_id=attribution.attribution_id,
            user_id=str(user_id),
            previous_primary_category=attribution.primary_category,
            overridden_primary_category=category,
            reason=reason,
            created_at=datetime.utcnow(),
        )
        await self.repository.append_override(override)
        await self.audit.record(
            "ATTRIBUTION_OVERRIDE_CREATED",
            "append-only human diagnostic override recorded",
            trace_id=trace_id,
            subject_id=attribution.subject_id,
            user_id=str(user_id),
        )
        return override
