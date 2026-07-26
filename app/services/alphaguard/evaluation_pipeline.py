"""Unified PR-007 evaluation orchestration with ag_eval_* writes only."""

from __future__ import annotations

from datetime import date, datetime
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.account_metric_service import AccountMetricService
from app.services.alphaguard.attribution_engine import AttributionEngine
from app.services.alphaguard.counterfactual_evaluation_engine import (
    CounterfactualEvaluationEngine,
)
from app.services.alphaguard.evaluation_audit_service import EvaluationAuditService
from app.services.alphaguard.evaluation_policy_registry import evaluation_policy
from app.services.alphaguard.evaluation_subject_builder import EvaluationSubjectBuilder
from app.services.alphaguard.horizon_label_service import HorizonLabelService
from app.services.alphaguard.module_metric_service import ModuleMetricService
from app.services.alphaguard.paired_comparison_service import (
    PairedComparisonService,
)
from app.services.alphaguard.paper_storage import clean_document, safe_error_message
from tradingagents.alphaguard.evaluation_schemas import (
    EvaluationSubject,
    EvaluationRun,
    EvaluationRunResult,
    evaluation_hash,
)


EVALUATION_WRITE_COLLECTIONS = [
    "ag_eval_subjects",
    "ag_eval_horizon_labels",
    "ag_eval_counterfactuals",
    "ag_eval_account_metrics",
    "ag_eval_paired_comparisons",
    "ag_eval_attributions",
    "ag_eval_attribution_overrides",
    "ag_eval_runs",
    "ag_eval_events",
    "ag_eval_factor_metrics",
    "ag_eval_regime_metrics",
    "ag_eval_strategy_metrics",
    "ag_eval_execution_metrics",
]


def evaluation_run_key(
    *,
    as_of_trade_date: date,
    user_id: str | None,
    evaluation_version: str,
) -> str:
    return evaluation_hash(
        {
            "as_of_trade_date": as_of_trade_date,
            "user_id": str(user_id) if user_id is not None else None,
            "evaluation_version": evaluation_version,
        }
    )


class EvaluationPipeline:
    def __init__(self, db):
        self.db = db
        self.policy = evaluation_policy()
        self.subjects = EvaluationSubjectBuilder(db)
        self.labels = HorizonLabelService(db)
        self.counterfactuals = CounterfactualEvaluationEngine(db)
        self.account_metrics = AccountMetricService(db)
        self.comparisons = PairedComparisonService(db)
        self.module_metrics = ModuleMetricService(db)
        self.attributions = AttributionEngine(db)
        self.audit = EvaluationAuditService(db)

    async def schedule(
        self,
        *,
        as_of_trade_date: date,
        user_id: str | None,
    ) -> tuple[EvaluationRun, bool]:
        key = evaluation_run_key(
            as_of_trade_date=as_of_trade_date,
            user_id=user_id,
            evaluation_version=self.policy.evaluation_version,
        )
        existing = clean_document(
            await self.db["ag_eval_runs"].find_one({"idempotency_key": key})
        )
        if existing:
            return EvaluationRun.model_validate(existing), False
        now = datetime.utcnow()
        run = EvaluationRun(
            evaluation_job_id=str(
                uuid5(NAMESPACE_URL, f"alphaguard:evaluation-run:{key}")
            ),
            as_of_trade_date=as_of_trade_date,
            user_id=str(user_id) if user_id is not None else None,
            evaluation_version=self.policy.evaluation_version,
            idempotency_key=key,
            status="PENDING",
            created_at=now,
            updated_at=now,
        )
        await self.db["ag_eval_runs"].insert_one(run.model_dump(mode="python"))
        return run, True

    async def evaluate_trade_date(
        self,
        *,
        as_of_trade_date: date,
        user_id: str | None = None,
        trace_id: str | None = None,
    ) -> EvaluationRunResult:
        run, _ = await self.schedule(
            as_of_trade_date=as_of_trade_date,
            user_id=user_id,
        )
        if run.status == "COMPLETED" and run.result is not None:
            return EvaluationRunResult.model_validate(run.result)
        now = datetime.utcnow()
        attempt = run.attempt_count + 1
        await self.db["ag_eval_runs"].update_one(
            {"evaluation_job_id": run.evaluation_job_id},
            {
                "$set": {
                    "status": "RUNNING",
                    "attempt_count": attempt,
                    "started_at": now,
                    "finished_at": None,
                    "error": None,
                    "updated_at": now,
                }
            },
        )
        await self.audit.record(
            "EVALUATION_RUN_STARTED",
            "evaluation-only pipeline started",
            trace_id=trace_id,
            evaluation_job_id=run.evaluation_job_id,
            user_id=run.user_id,
        )
        try:
            subjects, created, reused = await self.subjects.discover(
                user_id=user_id,
                decision_trade_date_lte=as_of_trade_date,
                evaluation_job_id=run.evaluation_job_id,
                trace_id=trace_id,
            )
            labels_by_subject = {}
            label_counts = {"CALCULATED": 0, "PENDING": 0, "INSUFFICIENT_DATA": 0}
            for subject in subjects:
                labels = await self.labels.calculate_all(
                    subject,
                    as_of_trade_date=as_of_trade_date,
                    evaluation_job_id=run.evaluation_job_id,
                    trace_id=trace_id,
                )
                labels_by_subject[subject.subject_id] = labels
                for label in labels:
                    key = (
                        label.status
                        if label.status in label_counts
                        else "INSUFFICIENT_DATA"
                    )
                    label_counts[key] += 1

            counterfactuals_by_subject = {}
            counterfactual_count = 0
            for subject in subjects:
                items = await self.counterfactuals.evaluate(
                    subject,
                    labels_by_subject[subject.subject_id],
                    evaluation_job_id=run.evaluation_job_id,
                    trace_id=trace_id,
                )
                counterfactuals_by_subject[subject.subject_id] = items
                counterfactual_count += len(items)

            period_start = min(
                (subject.decision_trade_date for subject in subjects),
                default=as_of_trade_date,
            )
            account_metrics = await self.account_metrics.calculate_all(
                period_start=period_start,
                period_end=as_of_trade_date,
                user_id=user_id,
                evaluation_job_id=run.evaluation_job_id,
                trace_id=trace_id,
            )
            comparisons = await self.comparisons.calculate_all(
                subjects,
                labels_by_subject,
                evaluation_job_id=run.evaluation_job_id,
                trace_id=trace_id,
            )
            await self.module_metrics.calculate_all(
                subjects,
                labels_by_subject,
                period_start=period_start,
                period_end=as_of_trade_date,
                scope_user_id=str(user_id) if user_id is not None else None,
            )
            attributions = await self.attributions.calculate_all(
                subjects,
                labels_by_subject,
                counterfactuals_by_subject,
                comparisons,
                evaluation_job_id=run.evaluation_job_id,
                trace_id=trace_id,
            )
            result = EvaluationRunResult(
                evaluation_job_id=run.evaluation_job_id,
                as_of_trade_date=as_of_trade_date,
                subjects_created=created,
                subjects_reused=reused,
                labels_calculated=label_counts["CALCULATED"],
                labels_pending=label_counts["PENDING"],
                labels_insufficient=label_counts["INSUFFICIENT_DATA"],
                counterfactuals_created=counterfactual_count,
                account_metrics_created=len(account_metrics),
                comparisons_created=len(comparisons),
                attributions_created=len(attributions),
                write_collections=EVALUATION_WRITE_COLLECTIONS,
                production_writes=False,
            )
            finished = datetime.utcnow()
            await self.db["ag_eval_runs"].update_one(
                {"evaluation_job_id": run.evaluation_job_id},
                {
                    "$set": {
                        "status": "COMPLETED",
                        "result": result.model_dump(mode="python"),
                        "finished_at": finished,
                        "error": None,
                        "updated_at": finished,
                    }
                },
            )
            await self.audit.record(
                "EVALUATION_RUN_COMPLETED",
                "evaluation-only pipeline completed without production writes",
                trace_id=trace_id,
                evaluation_job_id=run.evaluation_job_id,
                user_id=run.user_id,
            )
            return result
        except Exception as exc:
            finished = datetime.utcnow()
            safe_error = safe_error_message(exc)
            await self.db["ag_eval_runs"].update_one(
                {"evaluation_job_id": run.evaluation_job_id},
                {
                    "$set": {
                        "status": "FAILED",
                        "error": safe_error,
                        "finished_at": finished,
                        "updated_at": finished,
                    },
                    "$push": {
                        "error_history": {
                            "attempt_number": attempt,
                            "error": safe_error,
                            "at": finished,
                        }
                    },
                },
            )
            await self.audit.record(
                "EVALUATION_RUN_FAILED",
                safe_error,
                trace_id=trace_id,
                evaluation_job_id=run.evaluation_job_id,
                user_id=run.user_id,
            )
            raise

    async def evaluate_subject(
        self,
        *,
        subject_id: str,
        as_of_trade_date: date,
        trace_id: str | None = None,
    ) -> dict:
        """Idempotently evaluate one already-discovered analytical subject.

        This path is intentionally separate from a full EvaluationRun: it
        cannot calculate account-wide or paired metrics from an incomplete
        sample and it never discovers unrelated or future production objects.
        """

        raw = clean_document(
            await self.db["ag_eval_subjects"].find_one(
                {"subject_id": subject_id}
            )
        )
        if raw is None:
            raise LookupError("EvaluationSubject does not exist")
        subject = EvaluationSubject.model_validate(raw)
        if subject.decision_trade_date > as_of_trade_date:
            raise ValueError("subject decision date is after evaluation as-of date")
        labels = await self.labels.calculate_all(
            subject,
            as_of_trade_date=as_of_trade_date,
            trace_id=trace_id,
        )
        counterfactuals = await self.counterfactuals.evaluate(
            subject,
            labels,
            trace_id=trace_id,
        )
        stored_attribution = (
            await self.attributions.calculate_all(
                [subject],
                {subject.subject_id: labels},
                {subject.subject_id: counterfactuals},
                [],
                trace_id=trace_id,
            )
        )[0]
        return {
            "subject_id": subject.subject_id,
            "horizon_labels": [
                item.model_dump(mode="python") for item in labels
            ],
            "counterfactuals": [
                item.model_dump(mode="python") for item in counterfactuals
            ],
            "attribution": stored_attribution.model_dump(mode="python"),
            "production_writes": False,
        }
