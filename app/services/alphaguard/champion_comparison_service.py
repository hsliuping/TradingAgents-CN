"""Balanced Champion/Challenger comparison across all required evidence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import ExperimentRepository
from app.services.alphaguard.promotion_policy_service import (
    PromotionPolicyService,
)
from tradingagents.alphaguard.experiment_schemas import (
    ChallengerAssignment,
    ChampionComparisonReport,
    ExperimentRunResult,
    experiment_hash,
)


def _average(values) -> Decimal | None:
    clean = [Decimal(str(value)) for value in values if value is not None]
    return sum(clean, Decimal("0")) / Decimal(len(clean)) if clean else None


def _as_trade_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


class ChampionComparisonService:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)
        self.registry = ExperimentRegistry(db)
        self.policies = PromotionPolicyService(db)
        self.audit = ExperimentAuditService(db)

    async def create(
        self,
        experiment_id: str,
        *,
        now: datetime | None = None,
    ) -> ChampionComparisonReport:
        now = now or datetime.utcnow()
        definition = await self.registry.get(experiment_id)
        policy = await self.policies.get(definition.promotion_policy_version)
        run_documents = await self.repository.list(
            "runs", {"experiment_id": experiment_id}
        )
        result_documents = await self.repository.list(
            "run_results",
            {
                "run_id": {
                    "$in": [item["run_id"] for item in run_documents]
                }
            },
        )
        results = [
            ExperimentRunResult.model_validate(item)
            for item in result_documents
        ]
        run_by_id = {item["run_id"]: item for item in run_documents}
        historical = [
            item
            for item in results
            if run_by_id[item.run_id]["run_type"] == "HISTORICAL_REPLAY"
        ]
        out_of_sample = [
            item
            for item in results
            if run_by_id[item.run_id]["run_type"] == "OUT_OF_SAMPLE"
        ]
        leakage = await self.repository.list(
            "leakage_audits",
            {"run_id": {"$in": [item.run_id for item in results]}},
        )
        robustness = await self.repository.list(
            "robustness_reports",
            {"run_id": {"$in": [item.run_id for item in results]}},
        )
        shadows = await self.repository.list(
            "shadow_runs", {"experiment_id": experiment_id}
        )
        assignments = await self.repository.list(
            "challenger_assignments", {"experiment_id": experiment_id}
        )
        sample_count = sum(item.sample_count for item in historical)
        out_of_sample_count = sum(
            item.sample_count for item in out_of_sample
        )
        paired_count = sum(
            int(item.paired_metrics.get("paired_sample_count", 0))
            for item in historical + out_of_sample
        )
        eligible_count = sum(
            item.eligible_sample_count for item in historical + out_of_sample
        )
        paired_coverage = (
            Decimal(paired_count) / Decimal(eligible_count)
            if eligible_count
            else None
        )
        champion_net = _average(
            item.champion_metrics.get("net_return")
            for item in historical + out_of_sample
        )
        challenger_net = _average(
            item.challenger_metrics.get("net_return")
            for item in historical + out_of_sample
        )
        champion_drawdown = _average(
            item.champion_metrics.get("max_drawdown")
            for item in historical + out_of_sample
        )
        challenger_drawdown = _average(
            item.challenger_metrics.get("max_drawdown")
            for item in historical + out_of_sample
        )
        leakage_status = (
            "PASS"
            if leakage and all(item["status"] == "PASS" for item in leakage)
            else "FAIL"
            if any(item["status"] == "FAIL" for item in leakage)
            else "INCOMPLETE"
        )
        robustness_status = (
            "PASS"
            if robustness
            and all(item["status"] == "PASS" for item in robustness)
            else "FAIL"
            if any(item["status"] == "FAIL" for item in robustness)
            else "INCOMPLETE"
        )
        completed_shadows = [
            item for item in shadows if item["status"] == "COMPLETED"
        ]
        shadow_status = "PASS" if completed_shadows else "INCOMPLETE"
        completed_assignments = [
            ChallengerAssignment.model_validate(item)
            for item in assignments
            if item["status"] == "COMPLETED"
        ]
        challenger_status = (
            "PASS" if completed_assignments else "INCOMPLETE"
        )
        minimum = policy.minimum_sample_rules
        shadow_days = max(
            (int(item.get("observed_trade_days", 0)) for item in shadows),
            default=0,
        )
        integrity_errors = sum(
            int(item.get("integrity_error_count", 0)) for item in shadows
        )
        challenger_days = 0
        for assignment in completed_assignments:
            snapshots = await self.db["ag_paper_account_snapshots"].find(
                {"account_id": assignment.account_id}
            ).to_list(length=None)
            active_dates = {
                _as_trade_date(item["trade_date"])
                for item in snapshots
                if item.get("trade_date") is not None
                and _as_trade_date(item["trade_date"])
                >= assignment.activation_trade_date
                and (
                    assignment.deactivation_trade_date is None
                    or _as_trade_date(item["trade_date"])
                    <= assignment.deactivation_trade_date
                )
            }
            challenger_days = max(challenger_days, len(active_dates))
        available_regimes = sorted(
            {
                key
                for item in results
                for key in item.regime_breakdown
            }
        )

        gates: list[dict] = []

        def gate(rule: str, passed: bool, actual, required) -> None:
            gates.append(
                {
                    "rule": rule,
                    "status": "PASS" if passed else "FAIL",
                    "actual": actual,
                    "required": required,
                    "reason": (
                        "policy requirement satisfied"
                        if passed
                        else "required comparison evidence is missing or failed"
                    ),
                }
            )

        gate(
            "historical_samples",
            sample_count >= int(minimum["historical_samples"] or 0),
            sample_count,
            minimum["historical_samples"],
        )
        gate(
            "out_of_sample_samples",
            out_of_sample_count
            >= int(minimum["out_of_sample_samples"] or 0),
            out_of_sample_count,
            minimum["out_of_sample_samples"],
        )
        gate(
            "paired_samples",
            paired_count >= int(minimum["paired_samples"] or 0),
            paired_count,
            minimum["paired_samples"],
        )
        required_coverage = minimum.get("paired_coverage")
        gate(
            "paired_coverage",
            required_coverage is None
            or (
                paired_coverage is not None
                and paired_coverage >= Decimal(str(required_coverage))
            ),
            paired_coverage,
            required_coverage,
        )
        gate(
            "leakage",
            not policy.require_leakage_pass or leakage_status == "PASS",
            leakage_status,
            "PASS",
        )
        gate(
            "robustness",
            not policy.require_robustness_pass
            or robustness_status == "PASS",
            robustness_status,
            "PASS",
        )
        gate(
            "shadow",
            not policy.require_shadow
            or (
                shadow_status == "PASS"
                and shadow_days >= int(minimum["shadow_trade_days"] or 0)
            ),
            {"status": shadow_status, "trade_days": shadow_days},
            {"minimum_trade_days": minimum["shadow_trade_days"]},
        )
        gate(
            "paper_challenger",
            not policy.require_paper_challenger
            or (
                challenger_status == "PASS"
                and challenger_days
                >= int(minimum["challenger_trade_days"] or 0)
            ),
            {"status": challenger_status, "trade_days": challenger_days},
            {"minimum_trade_days": minimum["challenger_trade_days"]},
        )
        gate(
            "integrity_errors",
            integrity_errors <= policy.maximum_integrity_errors,
            integrity_errors,
            policy.maximum_integrity_errors,
        )
        required_regimes = int(
            policy.stability_thresholds.get("minimum_regime_segments") or 0
        )
        gate(
            "regime_segments",
            len(available_regimes) >= required_regimes,
            available_regimes,
            required_regimes,
        )
        champion_summary = {
            "average_net_return": champion_net,
            "average_max_drawdown": champion_drawdown,
            "run_count": len(historical) + len(out_of_sample),
        }
        challenger_summary = {
            "average_net_return": challenger_net,
            "average_max_drawdown": challenger_drawdown,
            "run_count": len(historical) + len(out_of_sample),
        }
        value_added = {
            "net_return": (
                challenger_net - champion_net
                if challenger_net is not None and champion_net is not None
                else None
            ),
            "max_drawdown": (
                challenger_drawdown - champion_drawdown
                if challenger_drawdown is not None
                and champion_drawdown is not None
                else None
            ),
            "improved_metrics": [],
            "worsened_metrics": [],
            "not_comparable_metrics": [],
            "insufficient_metrics": [],
        }
        for name, value in (
            ("net_return", value_added["net_return"]),
            ("max_drawdown", value_added["max_drawdown"]),
        ):
            if value is None:
                value_added["insufficient_metrics"].append(name)
            elif (
                name == "net_return" and value > 0
            ) or (
                name == "max_drawdown" and value > 0
            ):
                value_added["improved_metrics"].append(name)
            elif value < 0:
                value_added["worsened_metrics"].append(name)
        top_trade = _average(
            item.top_trade_contribution_pct for item in results
        )
        top_five = _average(
            item.top_five_trade_contribution_pct for item in results
        )
        max_top_trade = policy.stability_thresholds.get(
            "maximum_top_trade_contribution_pct"
        )
        max_top_five = policy.stability_thresholds.get(
            "maximum_top_five_trade_contribution_pct"
        )
        gate(
            "top_trade_dependency",
            max_top_trade is None
            or (
                top_trade is not None
                and top_trade <= Decimal(str(max_top_trade))
            ),
            top_trade,
            max_top_trade,
        )
        gate(
            "top_five_trade_dependency",
            max_top_five is None
            or (
                top_five is not None
                and top_five <= Decimal(str(max_top_five))
            ),
            top_five,
            max_top_five,
        )
        preliminary_failures = [
            item["rule"] for item in gates if item["status"] == "FAIL"
        ]
        status = (
            "INSUFFICIENT_DATA"
            if sample_count == 0 or paired_count == 0
            else "NOT_COMPARABLE"
            if preliminary_failures
            else "READY"
        )
        report_payload = {
            "experiment_id": experiment_id,
            "status": status,
            "historical_result_ids": [item.result_id for item in historical],
            "out_of_sample_result_ids": [
                item.result_id for item in out_of_sample
            ],
            "robustness_report_ids": [
                item["robustness_report_id"] for item in robustness
            ],
            "shadow_run_ids": [item["shadow_run_id"] for item in shadows],
            "challenger_assignment_ids": [
                item["assignment_id"] for item in assignments
            ],
            "sample_count": sample_count,
            "paired_sample_count": paired_count,
            "paired_coverage": paired_coverage,
            "champion_summary": champion_summary,
            "challenger_summary": challenger_summary,
            "value_added_summary": value_added,
            "return_comparison": {
                "champion": champion_net,
                "challenger": challenger_net,
                "difference": value_added["net_return"],
            },
            "drawdown_comparison": {
                "champion": champion_drawdown,
                "challenger": challenger_drawdown,
                "worsening": (
                    abs(challenger_drawdown) - abs(champion_drawdown)
                    if challenger_drawdown is not None
                    and champion_drawdown is not None
                    else None
                ),
            },
            "cost_comparison": {
                "champion": _average(
                    item.champion_metrics.get("fee_drag_pct")
                    for item in results
                ),
                "challenger": _average(
                    item.challenger_metrics.get("fee_drag_pct")
                    for item in results
                ),
            },
            "turnover_comparison": {
                "champion": _average(
                    item.champion_metrics.get("turnover")
                    for item in results
                ),
                "challenger": _average(
                    item.challenger_metrics.get("turnover")
                    for item in results
                ),
            },
            "regime_stability_comparison": {
                "required_segments": policy.stability_thresholds.get(
                    "minimum_regime_segments"
                ),
                "available_segments": available_regimes,
            },
            "outlier_dependency_comparison": {
                "top_trade_contribution_pct": top_trade,
                "top_five_trade_contribution_pct": top_five,
            },
            "leakage_status": leakage_status,
            "robustness_status": robustness_status,
            "shadow_consistency_status": shadow_status,
            "challenger_consistency_status": challenger_status,
            "gate_results": gates,
            "promotion_policy_version": policy.policy_version,
        }
        report_hash = experiment_hash(report_payload)
        report = ChampionComparisonReport(
            comparison_report_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:comparison:{experiment_id}:{report_hash}",
                )
            ),
            report_hash=report_hash,
            created_at=now,
            **report_payload,
        )
        stored, created = await self.repository.save_immutable(
            "comparison_reports",
            report,
            identity={"comparison_report_id": report.comparison_report_id},
            hash_field="report_hash",
        )
        if created:
            await self.audit.record(
                "COMPARISON_REPORT_CREATED",
                f"comparison status={stored.status}; gates include negative results",
                experiment_id=experiment_id,
                comparison_report_id=stored.comparison_report_id,
                user_id=definition.user_id,
                market=definition.market,
                result_hash=stored.report_hash,
            )
        return stored
