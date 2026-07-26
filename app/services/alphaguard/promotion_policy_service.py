"""Immutable PromotionPolicy registration and explicit gate evaluation."""

from __future__ import annotations

from app.services.alphaguard.experiment_config import promotion_policy
from app.services.alphaguard.experiment_repository import (
    ExperimentIntegrityConflict,
    ExperimentRepository,
)
from tradingagents.alphaguard.experiment_schemas import (
    ChampionComparisonReport,
    PromotionPolicy,
)


class PromotionPolicyService:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)

    async def register_builtin(self) -> tuple[PromotionPolicy, bool]:
        policy = promotion_policy()
        return await self.repository.save_immutable(
            "promotion_policies",
            policy,
            identity={
                "policy_id": policy.policy_id,
                "policy_version": policy.policy_version,
            },
            hash_field="immutable_hash",
        )

    async def get(self, policy_version: str) -> PromotionPolicy:
        raw = await self.repository.get(
            "promotion_policies", {"policy_version": policy_version}
        )
        if raw is None:
            builtin = promotion_policy()
            if builtin.policy_version != policy_version:
                raise LookupError("locked PromotionPolicy does not exist")
            return builtin
        policy = PromotionPolicy.model_validate(raw)
        if (
            policy.policy_version == promotion_policy().policy_version
            and policy.immutable_hash != promotion_policy().immutable_hash
        ):
            raise ExperimentIntegrityConflict("PromotionPolicy hash mismatch")
        return policy

    @staticmethod
    def check_report(
        policy: PromotionPolicy,
        report: ChampionComparisonReport,
    ) -> list[str]:
        failures: list[str] = []
        if report.status != "READY":
            failures.append(f"comparison_status:{report.status}")
        minimum = policy.minimum_sample_rules
        if report.sample_count < int(minimum["historical_samples"] or 0):
            failures.append("historical_samples")
        if report.paired_sample_count < int(minimum["paired_samples"] or 0):
            failures.append("paired_samples")
        required_coverage = minimum.get("paired_coverage")
        if (
            required_coverage is not None
            and (
                report.paired_coverage is None
                or report.paired_coverage < required_coverage
            )
        ):
            failures.append("paired_coverage")
        if policy.require_leakage_pass and report.leakage_status != "PASS":
            failures.append("leakage")
        if (
            policy.require_robustness_pass
            and report.robustness_status != "PASS"
        ):
            failures.append("robustness")
        if (
            policy.require_shadow
            and report.shadow_consistency_status != "PASS"
        ):
            failures.append("shadow")
        if (
            policy.require_paper_challenger
            and report.challenger_consistency_status != "PASS"
        ):
            failures.append("paper_challenger")
        max_drawdown_worsening = policy.risk_thresholds.get(
            "maximum_drawdown_worsening"
        )
        actual_worsening = report.drawdown_comparison.get("worsening")
        if (
            max_drawdown_worsening is not None
            and actual_worsening is not None
            and actual_worsening
            > type(actual_worsening)(str(max_drawdown_worsening))
        ):
            failures.append("maximum_drawdown_worsening")
        failures.extend(
            f"report_gate:{item.get('rule')}"
            for item in report.gate_results
            if item.get("status") == "FAIL"
        )
        return sorted(set(failures))
