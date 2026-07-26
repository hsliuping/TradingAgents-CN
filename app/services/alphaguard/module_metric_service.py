"""Deterministic module-level evaluation summaries with explicit sample limits."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.evaluation_policy_registry import evaluation_policy
from app.services.alphaguard.evaluation_repository import EvaluationRepository
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.evaluation_schemas import (
    ModuleEvaluationMetric,
    evaluation_hash,
)


def _average(values) -> Decimal | None:
    values = [Decimal(str(value)) for value in values if value is not None]
    return sum(values, Decimal("0")) / len(values) if values else None


class ModuleMetricService:
    def __init__(self, db):
        self.db = db
        self.repository = EvaluationRepository(db)
        self.policy = evaluation_policy()

    async def calculate_all(
        self,
        subjects: list,
        labels_by_subject: dict[str, list],
        *,
        period_start: date,
        period_end: date,
        scope_user_id: str | None = None,
    ) -> list[ModuleEvaluationMetric]:
        metrics: list[ModuleEvaluationMetric] = []
        stage_map = {
            "NORMAL_MODEL": "NORMAL_MODEL",
            "TOP_MODEL": "TOP_MODEL",
            "CONSENSUS": "CONSENSUS",
            "HARD_RISK": "HARD_RISK",
            "BENCHMARK_SAFETY": "BENCHMARK_SAFETY",
            "EXECUTION": "EXECUTION",
        }
        for stage, module_type in stage_map.items():
            groups: dict[str, list] = defaultdict(list)
            for subject in subjects:
                if subject.decision_stage == stage:
                    groups[subject.decision_status].append(subject)
            for status, items in groups.items():
                metrics.append(
                    self._subject_metric(
                        module_type,
                        status,
                        items,
                        labels_by_subject,
                        period_start,
                        period_end,
                        scope_user_id=scope_user_id,
                    )
                )

        quant_subjects = {
            item.snapshot_id: item
            for item in subjects
            if item.subject_type == "QUANT_PROPOSAL"
        }
        factor_groups: dict[str, list[tuple[dict, object]]] = defaultdict(list)
        for raw in await self.db["ag_factor_results"].find({}).to_list(length=None):
            result = clean_document(raw)
            subject = quant_subjects.get(str(result.get("snapshot_id")))
            if subject and period_start <= subject.decision_trade_date <= period_end:
                factor_groups[
                    f"{result.get('factor_id')}:{result.get('factor_version')}"
                ].append((result, subject))
        for key, items in factor_groups.items():
            returns_by_horizon: dict[str, list[Decimal]] = defaultdict(list)
            scores: list[Decimal] = []
            direction_hits: list[bool] = []
            mfe_values: list[Decimal] = []
            mae_values: list[Decimal] = []
            score_buckets: dict[str, list[Decimal]] = defaultdict(list)
            missing = 0
            for result, subject in items:
                score = result.get("normalized_score")
                calculated = (
                    result.get("raw_value") is not None
                    and score is not None
                    and result.get("direction") != "UNKNOWN"
                )
                if not calculated:
                    missing += 1
                    continue
                scores.append(Decimal(str(score)))
                subject_labels = {
                    item.horizon: item
                    for item in labels_by_subject.get(subject.subject_id, [])
                    if item.status == "CALCULATED"
                    and item.anchor_type == "DECISION_CLOSE"
                }
                for horizon, label in subject_labels.items():
                    if label.raw_forward_return is not None:
                        returns_by_horizon[horizon].append(label.raw_forward_return)
                primary = subject_labels.get(
                    self.policy.primary_attribution_horizon
                )
                if primary is not None:
                    if primary.mfe is not None:
                        mfe_values.append(primary.mfe)
                    if primary.mae is not None:
                        mae_values.append(primary.mae)
                    direction = str(result.get("direction"))
                    if direction in {"POSITIVE", "NEGATIVE"}:
                        direction_hits.append(
                            (direction == "POSITIVE" and primary.raw_forward_return > 0)
                            or (
                                direction == "NEGATIVE"
                                and primary.raw_forward_return < 0
                            )
                        )
                    bucket = (
                        "0-20"
                        if score < 20
                        else "20-40"
                        if score < 40
                        else "40-60"
                        if score < 60
                        else "60-80"
                        if score < 80
                        else "80-100"
                    )
                    score_buckets[bucket].append(primary.raw_forward_return)
            sample_count = len(items)
            comparable = len(
                returns_by_horizon.get(
                    self.policy.primary_attribution_horizon, []
                )
            )
            status = (
                "CALCULATED"
                if comparable >= self.policy.cross_section_min_samples
                else "INSUFFICIENT_SAMPLE"
            )
            metrics.append(
                self._metric(
                    "FACTOR",
                    key,
                    period_start,
                    period_end,
                    status,
                    sample_count,
                    comparable,
                    {
                        "coverage_rate": (
                            Decimal(sample_count - missing) / sample_count
                            if sample_count
                            else None
                        ),
                        "missing_rate": (
                            Decimal(missing) / sample_count if sample_count else None
                        ),
                        **{
                            f"average_{horizon.lower()}_return": _average(
                                returns_by_horizon.get(horizon, [])
                            )
                            for horizon in ("1D", "5D", "10D", "20D")
                        },
                        "direction_hit_rate": (
                            Decimal(sum(direction_hits))
                            / Decimal(len(direction_hits))
                            if direction_hits
                            else None
                        ),
                        "average_mfe": _average(mfe_values),
                        "average_mae": _average(mae_values),
                        "score_bucket_returns_10d": {
                            bucket: _average(values)
                            for bucket, values in sorted(score_buckets.items())
                        },
                        "rank_ic": None,
                        "rank_ic_status": (
                            "NOT_CALCULATED_CROSS_SECTION_TOO_SMALL"
                            if comparable < self.policy.cross_section_min_samples
                            else "NOT_CALCULATED_MIXED_TRADE_DATES"
                        ),
                        "future_normalization_used": False,
                    },
                    scope_user_id=scope_user_id,
                )
            )

        regime_by_snapshot = {
            str(item.get("snapshot_id")): clean_document(item)
            for item in await self.db["ag_regime_results"].find({}).to_list(length=None)
        }
        regime_groups: dict[str, list] = defaultdict(list)
        strategy_groups: dict[str, list] = defaultdict(list)
        for subject in quant_subjects.values():
            if not (period_start <= subject.decision_trade_date <= period_end):
                continue
            regime = regime_by_snapshot.get(subject.snapshot_id)
            if regime:
                regime_groups[str(regime.get("regime"))].append(subject)
            strategy_groups[
                f"{subject.lineage_ids.get('strategy_id', 'unknown')}:"
                f"{subject.lineage_ids.get('strategy_version', 'unknown')}:"
                f"{subject.decision_status}"
            ].append(subject)
        for key, items in regime_groups.items():
            primary_labels = [
                self._primary(labels_by_subject.get(item.subject_id, []))
                for item in items
            ]
            primary_labels = [item for item in primary_labels if item is not None]
            metrics.append(
                self._subject_metric(
                    "REGIME",
                    key,
                    items,
                    labels_by_subject,
                    period_start,
                    period_end,
                    additional={
                        "regime_correctness_claimed": False,
                        "average_benchmark_return_10d": _average(
                            item.benchmark_return for item in primary_labels
                        ),
                        "average_benchmark_mfe": _average(
                            item.mfe for item in primary_labels
                        ),
                        "average_benchmark_mae": _average(
                            item.mae for item in primary_labels
                        ),
                        "market_breadth_status": "UNAVAILABLE",
                    },
                    scope_user_id=scope_user_id,
                )
            )
        for key, items in strategy_groups.items():
            metrics.append(
                self._subject_metric(
                    "STRATEGY",
                    key,
                    items,
                    labels_by_subject,
                    period_start,
                    period_end,
                    scope_user_id=scope_user_id,
                )
            )

        stored = []
        collection_for = {
            "FACTOR": "factor_metrics",
            "REGIME": "regime_metrics",
            "STRATEGY": "strategy_metrics",
        }
        for metric in metrics:
            name = collection_for.get(metric.module_type, "execution_metrics")
            saved, _ = await self.repository.save_immutable(
                name,
                metric,
                identity={"metric_id": metric.metric_id},
            )
            stored.append(saved)
        return stored

    def _primary(self, labels):
        return next(
            (
                item
                for item in labels
                if item.horizon == self.policy.primary_attribution_horizon
                and item.status == "CALCULATED"
                and item.anchor_type == "DECISION_CLOSE"
            ),
            None,
        )

    def _subject_metric(
        self,
        module_type,
        key,
        subjects,
        labels_by_subject,
        period_start,
        period_end,
        additional=None,
        scope_user_id=None,
    ):
        labels = [
            self._primary(labels_by_subject.get(item.subject_id, []))
            for item in subjects
        ]
        labels = [item for item in labels if item is not None]
        sample_count = len(subjects)
        comparable = len(labels)
        status = (
            "NO_DATA"
            if sample_count == 0
            else "CALCULATED"
            if comparable >= self.policy.paired_min_samples
            else "INSUFFICIENT_SAMPLE"
        )
        labels_by_horizon = {
            horizon: [
                label
                for subject in subjects
                for label in labels_by_subject.get(subject.subject_id, [])
                if label.horizon == horizon
                and label.status == "CALCULATED"
                and label.anchor_type == "DECISION_CLOSE"
            ]
            for horizon in ("1D", "5D", "10D", "20D")
        }
        non_trade_statuses = {
            "WATCH",
            "WAIT",
            "NO_TRADE",
            "REJECT",
            "REJECTED",
            "CONSENSUS_REJECT",
            "SUSPEND",
        }
        missed = avoided = 0
        for subject in subjects:
            label = self._primary(labels_by_subject.get(subject.subject_id, []))
            if label is None or subject.decision_status not in non_trade_statuses:
                continue
            if label.raw_forward_return >= Decimal("0.05"):
                missed += 1
            if label.raw_forward_return <= Decimal("-0.05"):
                avoided += 1
        touched = [
            item.entry_zone_touched
            for item in labels
            if item.entry_zone_touched is not None
        ]
        metrics = {
            "coverage_rate": (
                Decimal(comparable) / sample_count if sample_count else None
            ),
            **{
                f"average_{horizon.lower()}_return": _average(
                    item.raw_forward_return
                    for item in labels_by_horizon[horizon]
                )
                for horizon in ("1D", "5D", "10D", "20D")
            },
            **{
                f"average_action_aligned_{horizon.lower()}_return": _average(
                    item.action_aligned_return
                    for item in labels_by_horizon[horizon]
                )
                for horizon in ("1D", "5D", "10D", "20D")
            },
            "average_mae": _average(item.mae for item in labels),
            "average_mfe": _average(item.mfe for item in labels),
            "selected_for_execution_rate": (
                Decimal(sum(item.selected_for_execution for item in subjects))
                / sample_count
                if sample_count
                else None
            ),
            "actual_execution_rate": (
                Decimal(sum(item.actual_execution_exists for item in subjects))
                / sample_count
                if sample_count
                else None
            ),
            "rejection_rate": (
                Decimal(
                    sum(
                        item.decision_status
                        in {"REJECT", "REJECTED", "CONSENSUS_REJECT"}
                        for item in subjects
                    )
                )
                / sample_count
                if sample_count
                else None
            ),
            "adjustment_rate": (
                Decimal(
                    sum(
                        item.decision_status
                        in {"RISK_ADJUST", "MATERIAL_REVISION", "REDUCE"}
                        for item in subjects
                    )
                )
                / sample_count
                if sample_count
                else None
            ),
            "model_error_rate": (
                Decimal(
                    sum(
                        item.decision_status
                        in {"MODEL_FAILED", "INVALID_OUTPUT"}
                        for item in subjects
                    )
                )
                / sample_count
                if sample_count
                else None
            ),
            "avoided_loss_count": avoided,
            "missed_opportunity_count": missed,
            "entry_touch_rate": (
                Decimal(sum(touched)) / Decimal(len(touched))
                if touched
                else None
            ),
            **(additional or {}),
        }
        return self._metric(
            module_type,
            key,
            period_start,
            period_end,
            status,
            sample_count,
            comparable,
            metrics,
            scope_user_id=scope_user_id,
        )

    @staticmethod
    def _metric(
        module_type,
        key,
        period_start,
        period_end,
        status,
        sample_count,
        comparable,
        metrics,
        scope_user_id=None,
    ):
        payload = {
            "scope_user_id": scope_user_id,
            "module_type": module_type,
            "group_key": key,
            "period_start": period_start,
            "period_end": period_end,
            "status": status,
            "sample_count": sample_count,
            "comparable_count": comparable,
            "metrics": metrics,
            "metric_version": "module-metric-v1",
        }
        payload["input_hash"] = evaluation_hash(payload)
        return ModuleEvaluationMetric(
            metric_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:module-metric:{module_type}:{key}:"
                    f"{period_start}:{period_end}:{scope_user_id}:module-metric-v1",
                )
            ),
            calculated_at=datetime.utcnow(),
            **payload,
        )
