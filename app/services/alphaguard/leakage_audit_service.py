"""Fail-closed temporal/config leakage audit for experiment runs."""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_repository import ExperimentRepository
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.experiment_schemas import (
    ExperimentOutputPair,
    ExperimentRun,
    LeakageAuditReport,
    TimeSeriesSplitDefinition,
    experiment_hash,
)


class LeakageAuditService:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)
        self.event_audit = ExperimentAuditService(db)

    async def audit(
        self,
        run_id: str,
        *,
        explicit_findings: dict[str, bool] | None = None,
        evidence_refs: list[str] | None = None,
        now: datetime | None = None,
    ) -> LeakageAuditReport:
        now = now or datetime.utcnow()
        run_raw = await self.repository.get("runs", {"run_id": run_id})
        if run_raw is None:
            raise LookupError("ExperimentRun does not exist")
        run = ExperimentRun.model_validate(run_raw)
        outputs = [
            ExperimentOutputPair.model_validate(item)
            for item in await self.repository.list(
                "shadow_outputs", {"run_id": run_id}
            )
        ]
        findings = {
            "future_price_leakage": False,
            "future_financial_leakage": False,
            "future_news_leakage": False,
            "evaluation_label_leakage": False,
            "split_overlap_leakage": False,
            "current_config_leakage": False,
        }
        violations: list[str] = []
        for output in outputs:
            if any(
                ref.startswith("ag_eval_")
                for ref in output.decision_input_refs
            ):
                findings["evaluation_label_leakage"] = True
                violations.append(
                    f"{output.snapshot_id}: evaluation label entered decision inputs"
                )
            champion_ref = next(iter(run.champion_version_refs.values()))
            challenger_ref = next(iter(run.challenger_version_refs.values()))
            if (
                output.baseline_version_ref != champion_ref
                or output.challenger_version_ref != challenger_ref
            ):
                findings["current_config_leakage"] = True
                violations.append(
                    f"{output.snapshot_id}: output versions differ from locked run"
                )
        if run.split_id:
            split_raw = await self.repository.get(
                "time_splits", {"split_id": run.split_id}
            )
            if split_raw is None:
                findings["split_overlap_leakage"] = True
                violations.append("run references a missing time-series split")
            else:
                split = TimeSeriesSplitDefinition.model_validate(split_raw)
                if (
                    split.train_end
                    and split.train_end >= split.test_start
                ) or (
                    split.validation_end
                    and split.validation_end >= split.test_start
                ):
                    findings["split_overlap_leakage"] = True
                    violations.append("train/validation overlaps test period")
        for key, value in (explicit_findings or {}).items():
            if key not in findings:
                raise ValueError(f"unknown leakage finding: {key}")
            findings[key] = bool(value)
            if value:
                violations.append(f"explicit audit finding: {key}")
        if any(findings.values()):
            status = "FAIL"
        elif not outputs:
            status = "INCOMPLETE"
            violations.append("run has no immutable experiment outputs to audit")
        else:
            status = "PASS"
        payload = {
            "run_id": run_id,
            "status": status,
            **findings,
            "violations": sorted(set(violations)),
            "evidence_refs": sorted(set(evidence_refs or [])),
            "input_hash": experiment_hash(
                {
                    "run_input_hash": run.input_hash,
                    "run_result_hash": run.result_hash,
                    "output_hashes": [item.result_hash for item in outputs],
                    "findings": findings,
                    "violations": sorted(set(violations)),
                }
            ),
            "created_at": now,
        }
        report = LeakageAuditReport(
            leakage_audit_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:leakage-audit:{run_id}:{payload['input_hash']}",
                )
            ),
            **payload,
        )
        stored, created = await self.repository.save_immutable(
            "leakage_audits",
            report,
            identity={"run_id": run_id},
            hash_field="input_hash",
        )
        if created:
            await self.event_audit.record(
                (
                    "LEAKAGE_AUDIT_PASSED"
                    if stored.status == "PASS"
                    else "LEAKAGE_AUDIT_FAILED"
                ),
                (
                    "no future/config leakage detected"
                    if stored.status == "PASS"
                    else "; ".join(stored.violations)
                ),
                experiment_id=run.experiment_id,
                run_id=run_id,
                input_hash=stored.input_hash,
            )
        return stored
