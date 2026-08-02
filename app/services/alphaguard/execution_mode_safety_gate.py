"""Fail-closed execution boundary for non-realtime AlphaGuard lineage."""

from __future__ import annotations

from typing import Any


class ExecutionModeBlockedError(ValueError):
    pass


class ExecutionModeSafetyGate:
    """Resolve source lineage before an outbox event or intent can exist."""

    BLOCKED_RUN_MODES = {
        "PRODUCTION_REPROCESS",
        "EVIDENCE_CONTRACT_VALIDATION",
        "RESEARCH_BACKFILL",
        "UI_DEMO",
    }

    def __init__(self, db):
        self.db = db

    @classmethod
    def assert_snapshot_allowed(cls, snapshot: dict[str, Any]) -> None:
        run_mode = snapshot.get("run_mode")
        explicitly_disabled = (
            snapshot.get("automated_execution_allowed") is False
        )
        if run_mode in cls.BLOCKED_RUN_MODES or explicitly_disabled:
            raise ExecutionModeBlockedError(
                "execution blocked by immutable snapshot run mode: "
                f"{run_mode or 'EXPLICITLY_DISABLED'}"
            )

    async def assert_outbox_allowed(
        self,
        *,
        event_type: str,
        source_object_id: str,
    ) -> None:
        snapshot_id: str | None = None
        if event_type == "CREATE_QUANT_BENCHMARK_INTENT":
            source = await self.db["ag_quant_proposals"].find_one(
                {"proposal_id": source_object_id}
            )
            snapshot_id = str(source.get("snapshot_id")) if source else None
        elif event_type == "CREATE_NORMAL_BENCHMARK_INTENT":
            report = await self.db["analysis_reports"].find_one(
                {
                    "$or": [
                        {"normal_trade_plan.plan_id": source_object_id},
                        {"normal_trade_plan_history.plan_id": source_object_id},
                    ]
                }
            )
            snapshot_id = str(report.get("snapshot_id")) if report else None
        elif event_type == "CREATE_TOP_CONFIRMED_INTENT":
            source = await self.db["ag_risk_decisions"].find_one(
                {"risk_decision_id": source_object_id}
            )
            snapshot_id = str(source.get("snapshot_id")) if source else None
        elif event_type == "CREATE_CHALLENGER_INTENT":
            source = await self.db["ag_exp_shadow_outputs"].find_one(
                {
                    "output_id": source_object_id,
                    "run_type": "PAPER_CHALLENGER",
                }
            )
            snapshot_id = str(source.get("snapshot_id")) if source else None
        if not snapshot_id:
            return
        snapshot = await self.db["ag_evidence_snapshots"].find_one(
            {"snapshot_id": snapshot_id}
        )
        if snapshot is not None:
            self.assert_snapshot_allowed(snapshot)
