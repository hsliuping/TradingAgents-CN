from datetime import datetime

import pytest
from pydantic import ValidationError

from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from tradingagents.alphaguard.candidate_schemas import (
    CandidateEntry,
    CandidateSource,
    CandidateStatus,
    validate_candidate_transition,
)
from tradingagents.alphaguard.instruments import normalize_instrument

from tests.unit.alphaguard._fakes import FakeDB


def candidate_payload(**overrides):
    now = datetime.utcnow()
    payload = {
        "candidate_id": "candidate-1",
        "user_id": "user-1",
        "symbol": "600519.SH",
        "market": "A股",
        "name": "贵州茅台",
        "sources": {
            CandidateSource.USER_SELECTED,
            CandidateSource.USER_SELECTED,
        },
        "status": CandidateStatus.WATCHING,
        "priority": 50,
        "added_at": now,
        "updated_at": now,
        "next_scan_at": None,
        "cooldown_until": None,
        "active_plan_id": None,
        "active_order_ids": [],
        "held_account_ids": [],
        "removal_requested": False,
    }
    payload.update(overrides)
    return payload


def test_candidate_entry_normalizes_and_deduplicates_sources():
    candidate = CandidateEntry.model_validate(candidate_payload())
    assert candidate.market == "CN"
    assert candidate.symbol == "600519"
    assert candidate.sources == {CandidateSource.USER_SELECTED}


def test_candidate_entry_rejects_invalid_market():
    with pytest.raises(ValidationError):
        CandidateEntry.model_validate(candidate_payload(market="MARS"))


@pytest.mark.parametrize("priority", [-1, 101])
def test_candidate_entry_rejects_invalid_priority(priority):
    with pytest.raises(ValidationError):
        CandidateEntry.model_validate(candidate_payload(priority=priority))


@pytest.mark.parametrize(
    ("market", "symbol", "expected"),
    [
        ("CN", "600519", ("CN", "600519")),
        ("SH", "SH600519", ("CN", "600519")),
        ("A_SHARE", "600519.SH", ("CN", "600519")),
        ("HK", "700.HK", ("HK", "00700")),
        ("US", "aapl", ("US", "AAPL")),
    ],
)
def test_instrument_normalization(market, symbol, expected):
    assert normalize_instrument(symbol, market) == expected


def test_allowed_and_illegal_candidate_transitions():
    validate_candidate_transition(
        CandidateStatus.WATCHING, CandidateStatus.SIGNAL_DETECTED
    )
    with pytest.raises(ValueError):
        validate_candidate_transition(
            CandidateStatus.WATCHING, CandidateStatus.APPROVED
        )


def test_removed_reactivation_requires_source():
    with pytest.raises(ValueError):
        validate_candidate_transition(
            CandidateStatus.REMOVED, CandidateStatus.WATCHING
        )
    validate_candidate_transition(
        CandidateStatus.REMOVED,
        CandidateStatus.WATCHING,
        source_readded=True,
    )


@pytest.mark.asyncio
async def test_duplicate_symbol_variants_keep_single_candidate():
    db = FakeDB()
    service = CandidatePoolService(db)
    first = await service.upsert_source(
        user_id="user-1",
        symbol="SH600519",
        market="SH",
        source=CandidateSource.USER_SELECTED,
    )
    second = await service.upsert_source(
        user_id="user-1",
        symbol="600519.SH",
        market="CN",
        source=CandidateSource.USER_SELECTED,
    )
    assert first.candidate_id == second.candidate_id
    assert db["ag_candidates"].count() == 1


@pytest.mark.asyncio
async def test_user_and_position_sources_merge():
    service = CandidatePoolService(FakeDB())
    await service.upsert_source(
        user_id="user-1",
        symbol="600519",
        market="CN",
        source=CandidateSource.USER_SELECTED,
    )
    candidate = await service.upsert_source(
        user_id="user-1",
        symbol="600519",
        market="CN",
        source=CandidateSource.POSITION_REQUIRED,
        held_account_id="manual-paper:user-1",
    )
    assert candidate.sources == {
        CandidateSource.USER_SELECTED,
        CandidateSource.POSITION_REQUIRED,
    }
    assert candidate.status == CandidateStatus.POSITION_HELD


@pytest.mark.asyncio
async def test_removing_favorite_keeps_position_monitoring():
    db = FakeDB()
    service = CandidatePoolService(db)
    await db["paper_positions"].insert_one(
        {"user_id": "user-1", "code": "600519", "market": "CN", "quantity": 100}
    )
    await service.upsert_source(
        user_id="user-1",
        symbol="600519",
        market="CN",
        source=CandidateSource.USER_SELECTED,
    )
    await service.upsert_source(
        user_id="user-1",
        symbol="600519",
        market="CN",
        source=CandidateSource.POSITION_REQUIRED,
        held_account_id="manual-paper:user-1",
    )
    candidate, reasons = await service.remove_source(
        user_id="user-1",
        symbol="600519",
        market="CN",
        source=CandidateSource.USER_SELECTED,
        removal_requested=True,
    )
    assert candidate is not None
    assert CandidateSource.USER_SELECTED not in candidate.sources
    assert CandidateSource.POSITION_REQUIRED in candidate.sources
    assert candidate.status == CandidateStatus.POSITION_HELD
    assert candidate.removal_requested is True
    assert "positive_position" in reasons


@pytest.mark.asyncio
async def test_no_source_or_dependency_marks_removed_without_physical_delete():
    db = FakeDB()
    service = CandidatePoolService(db)
    candidate = await service.upsert_source(
        user_id="user-1",
        symbol="600519",
        market="CN",
        source=CandidateSource.USER_SELECTED,
    )
    removed, reasons = await service.request_removal(
        candidate.candidate_id, "user-1"
    )
    assert reasons == []
    assert removed.status == CandidateStatus.REMOVED
    assert db["ag_candidates"].count() == 1


@pytest.mark.asyncio
async def test_reconciliation_is_idempotent_and_isolates_users():
    db = FakeDB()
    service = CandidatePoolService(db)
    await db["paper_positions"].insert_one(
        {"user_id": "user-1", "code": "600519", "market": "CN", "quantity": 100}
    )
    await service.reconcile_user("user-1")
    await service.reconcile_user("user-1")
    await service.upsert_source(
        user_id="user-2",
        symbol="600519",
        market="CN",
        source=CandidateSource.USER_SELECTED,
    )
    assert db["ag_candidates"].count() == 2
    user_one = await service.list_candidates("user-1")
    user_two = await service.list_candidates("user-2")
    assert len(user_one) == len(user_two) == 1
    assert user_one[0].candidate_id != user_two[0].candidate_id
