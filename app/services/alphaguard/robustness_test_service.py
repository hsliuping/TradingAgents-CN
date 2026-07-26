"""Pure experiment-shadow robustness scenarios."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_config import robustness_policy
from app.services.alphaguard.experiment_repository import ExperimentRepository
from tradingagents.alphaguard.experiment_schemas import (
    ExperimentRun,
    ExperimentRunResult,
    RobustnessTestReport,
    experiment_hash,
)


def _d(value) -> Decimal:
    return Decimal(str(value))


def _compound(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    equity = Decimal("1")
    for value in values:
        equity *= Decimal("1") + value
    return equity - Decimal("1")


class RobustnessTestService:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)
        self.audit = ExperimentAuditService(db)
        self.policy = robustness_policy()

    async def run(
        self,
        run_id: str,
        *,
        now: datetime | None = None,
    ) -> RobustnessTestReport:
        now = now or datetime.utcnow()
        run_raw = await self.repository.get("runs", {"run_id": run_id})
        result_raw = await self.repository.get(
            "run_results", {"run_id": run_id}
        )
        if run_raw is None or result_raw is None:
            raise LookupError("completed experiment run/result required")
        run = ExperimentRun.model_validate(run_raw)
        result = ExperimentRunResult.model_validate(result_raw)
        returns = [
            _d(value)
            for value in result.paired_metrics.get("challenger_returns", [])
        ]
        if not returns:
            status = "INCOMPLETE"
            scenarios = [
                {
                    "scenario": name,
                    "status": "INSUFFICIENT_DATA",
                    "net_return": None,
                }
                for name in self.policy["scenarios"]
            ]
            failed = []
        else:
            baseline = _compound(returns)
            cost_unit = (
                (result.fee_drag_pct or Decimal("0"))
                / Decimal(max(len(returns), 1))
            )
            scenarios = []
            for name in self.policy["scenarios"]:
                transformed = list(returns)
                reason = None
                if name in self.policy["fee_multipliers"]:
                    multiplier = _d(self.policy["fee_multipliers"][name])
                    transformed = [
                        value - cost_unit * (multiplier - Decimal("1"))
                        for value in transformed
                    ]
                elif name in self.policy["slippage_multipliers"]:
                    multiplier = _d(
                        self.policy["slippage_multipliers"][name]
                    )
                    # The base result has already paid configured slippage.
                    # Stress adds a deterministic, experiment-only 5 bps unit.
                    transformed = [
                        value
                        - Decimal("0.0005")
                        * (multiplier - Decimal("1"))
                        for value in transformed
                    ]
                elif name == "ENTRY_DELAY_1D":
                    transformed = returns[1:]
                elif name == "LIQUIDITY_REDUCTION":
                    keep = max(1, int(len(returns) * float(
                        self.policy["liquidity_capacity_multiplier"]
                    )))
                    transformed = returns[:keep]
                elif name == "MISSING_NONCORE_DATA":
                    transformed = [
                        value
                        for index, value in enumerate(returns)
                        if index % 5 != 0
                    ]
                elif name == "WITHOUT_BEST_TRADE":
                    transformed = list(returns)
                    transformed.remove(max(transformed))
                elif name == "WITHOUT_TOP_5_TRADES":
                    transformed = sorted(returns)[:-5] if len(returns) > 5 else []
                elif name == "REGIME_SEGMENTED":
                    reason = "regime segments are reported separately"
                net_return = _compound(transformed)
                scenario_status = (
                    "INSUFFICIENT_DATA"
                    if net_return is None
                    else "FAIL"
                    if baseline is not None
                    and baseline >= 0
                    and net_return < 0
                    else "PASS"
                )
                scenario_detail = {}
                if name == "REGIME_SEGMENTED":
                    available = sorted(result.regime_breakdown)
                    required = sorted(self.policy["required_regimes"])
                    scenario_detail = {
                        "required_regimes": required,
                        "available_regimes": available,
                        "regime_breakdown": result.regime_breakdown,
                    }
                    if not available:
                        scenario_status = "INSUFFICIENT_DATA"
                scenarios.append(
                    {
                        "scenario": name,
                        "status": scenario_status,
                        "net_return": net_return,
                        "sample_count": len(transformed),
                        "reason": reason,
                        "formal_engine_mutated": False,
                        "production_account_writes": False,
                        **scenario_detail,
                    }
                )
            failed = [
                item["scenario"]
                for item in scenarios
                if item["status"] == "FAIL"
            ]
            status = (
                "FAIL"
                if failed
                else "INCOMPLETE"
                if any(
                    item["status"] == "INSUFFICIENT_DATA"
                    for item in scenarios
                )
                else "PASS"
            )
        by_name = {item["scenario"]: item for item in scenarios}
        input_hash = experiment_hash(
            {
                "run_result_hash": result.result_hash,
                "policy_hash": self.policy["immutable_hash"],
                "scenarios": scenarios,
            }
        )
        report = RobustnessTestReport(
            robustness_report_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:robustness:{run_id}:{input_hash}",
                )
            ),
            run_id=run_id,
            status=status,
            scenarios=scenarios,
            cost_stress_result={
                key: by_name[key]
                for key in ("FEE_1_5X", "FEE_2X")
            },
            slippage_stress_result={
                key: by_name[key]
                for key in ("SLIPPAGE_1_5X", "SLIPPAGE_2X")
            },
            delayed_entry_result=by_name["ENTRY_DELAY_1D"],
            missing_data_result=by_name["MISSING_NONCORE_DATA"],
            regime_segment_result=by_name["REGIME_SEGMENTED"],
            outlier_dependency_result={
                "without_best": by_name["WITHOUT_BEST_TRADE"],
                "without_top_five": by_name["WITHOUT_TOP_5_TRADES"],
            },
            failed_scenarios=failed,
            input_hash=input_hash,
            created_at=now,
        )
        stored, created = await self.repository.save_immutable(
            "robustness_reports",
            report,
            identity={"run_id": run_id},
            hash_field="input_hash",
        )
        if created:
            await self.audit.record(
                (
                    "ROBUSTNESS_TEST_COMPLETED"
                    if stored.status == "PASS"
                    else "ROBUSTNESS_TEST_FAILED"
                ),
                f"robustness status={stored.status}; failed={stored.failed_scenarios}",
                experiment_id=run.experiment_id,
                run_id=run_id,
                input_hash=stored.input_hash,
            )
        return stored
