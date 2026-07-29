from __future__ import annotations

from datetime import datetime

import pytest

from app.services.alphaguard.evidence_snapshot_service import (
    calculate_immutable_hash,
)
from app.services.alphaguard.research_decision_path_validation_service import (
    CANONICAL_BACKFILL_RUN_ID,
    ResearchDecisionPathValidationService,
)
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_context
from tradingagents.alphaguard.evidence_schemas import (
    DataQualityReport,
    EvidenceSnapshot,
)


async def _seed_four_triggers(db: FakeDB) -> None:
    base = make_context().quant_proposal
    for index in range(4):
        sample_id = f"sample-{index}"
        snapshot_id = f"snapshot-{index}"
        proposal = base.model_copy(
            update={
                "proposal_id": f"proposal-{index}",
                "snapshot_id": snapshot_id,
            }
        )
        quality = DataQualityReport(
            quality_report_id=f"quality-{index}",
            symbol=proposal.symbol,
            market=proposal.market,
            trade_date=proposal.trade_date,
            status="PASS",
            completeness_score=1,
            freshness_score=1,
            consistency_score=1,
            checked_at=datetime(2026, 7, 1, 16),
        )
        draft = EvidenceSnapshot(
            snapshot_id=snapshot_id,
            user_id=proposal.user_id,
            symbol=proposal.symbol,
            market=proposal.market,
            trade_date=proposal.trade_date,
            price_cutoff_at=datetime(2026, 7, 1, 16),
            news_cutoff_at=datetime(2026, 7, 1, 16),
            announcement_cutoff_at=datetime(2026, 7, 1, 16),
            price_data_version="fixed",
            financial_data_version="fixed",
            news_data_version="fixed",
            data_quality=quality,
            raw_refs={
                "prices": ["stock_daily_quotes:price-1:2026-07-01"],
                "benchmark_prices": [
                    f"index_daily:index-{item}"
                    for item in range(61)
                ],
            },
            factor_version_set={"factor": "1.0.0"},
            strategy_version="strategy-set-v1",
            immutable_hash="0" * 64,
            created_at=datetime(2026, 7, 1, 16),
        )
        snapshot = draft.model_copy(
            update={"immutable_hash": calculate_immutable_hash(draft)}
        )
        await db["ag_research_quant_proposals"].insert_one(
            {
                "backfill_run_id": CANONICAL_BACKFILL_RUN_ID,
                "sample_id": sample_id,
                "snapshot_id": snapshot_id,
                "proposal_id": proposal.proposal_id,
                "quant_proposal": proposal.model_dump(mode="python"),
            }
        )
        await db["ag_research_snapshots"].insert_one(
            {
                "research_snapshot_id": f"research:{snapshot_id}",
                "backfill_run_id": CANONICAL_BACKFILL_RUN_ID,
                "sample_id": sample_id,
                "source_trade_date": proposal.trade_date,
                "evidence_snapshot": snapshot.model_dump(mode="python"),
                "calendar_reference_mode": "PERSISTED_RESEARCH_CONTROL",
                "version_selection_mode": "LOCKED_AT_BACKFILL_RUN",
                "run_mode": "RESEARCH_BACKFILL",
                "research_only": True,
                "automated_execution_allowed": False,
                "immutable_hash": f"{index + 1:064x}",
                "created_at": datetime(2026, 7, 1, 16),
                "schema_version": "alphaguard-historical-backfill-v1",
            }
        )
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "price-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": datetime(2026, 7, 1),
            "period": "daily",
            "close": 100,
        }
    )


@pytest.mark.asyncio
async def test_natural_triggers_without_status_do_not_enter_real_model_path(
    monkeypatch,
):
    db = FakeDB()
    await _seed_four_triggers(db)
    service = ResearchDecisionPathValidationService(db)

    async def structural_stub(**_kwargs):
        return {
            "validation_type": "STRUCTURAL_STUB_VALIDATION",
            "normal_status": "PROPOSE_TRADE",
            "top_status": "CONFIRM",
            "consensus_status": "CONSENSUS_PASS",
            "hard_risk_status": "PASS",
            "order_intent_created": False,
            "formal_write_allowed": False,
        }

    monkeypatch.setattr(service, "_structural_stub", structural_stub)
    preview = await service.run(execute=False)
    assert preview["eligible_real_model_sample_count"] == 0
    assert (
        preview["real_model_status"]
        == "NOT_CALLED_NO_EVIDENCE_COMPLETE_SAMPLE"
    )
    assert all(
        "VERSIONED_TRADING_STATUS_MISSING" in item["blocking_reasons"]
        for item in preview["natural_triggered_samples"]
    )
    assert await db[service.COLLECTION].count_documents({}) == 0

    created = await service.run(execute=True)
    reused = await service.run(execute=True)
    assert created["action"] == "CREATED"
    assert reused["action"] == "REUSED"
    assert created["result_hash"] == reused["result_hash"]
    assert await db[service.COLLECTION].count_documents({}) == 1
