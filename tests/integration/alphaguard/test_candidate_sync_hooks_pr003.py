import pytest

from app.routers.paper import _sync_alphaguard_position_candidate
from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from app.services.favorites_service import FavoritesService
from scripts.migrate_favorites_to_candidates import migrate_database
from tradingagents.alphaguard.candidate_schemas import CandidateSource

from tests.unit.alphaguard._fakes import FakeDB


class RecordingCandidateService:
    def __init__(self, fail=False):
        self.fail = fail
        self.upserts = []
        self.removals = []
        self.failures = []

    async def upsert_source(self, **kwargs):
        if self.fail:
            raise RuntimeError("candidate sync unavailable")
        self.upserts.append(kwargs)

    async def remove_source(self, **kwargs):
        if self.fail:
            raise RuntimeError("candidate sync unavailable")
        self.removals.append(kwargs)
        return None, []

    async def record_sync_failure(self, **kwargs):
        self.failures.append(kwargs)


@pytest.mark.asyncio
async def test_favorite_add_and_remove_sync_user_selected(monkeypatch):
    db = FakeDB()
    recorder = RecordingCandidateService()
    monkeypatch.setattr(
        "app.services.alphaguard.candidate_pool_service.get_candidate_pool_service",
        lambda: recorder,
    )
    service = FavoritesService()
    service.db = db

    assert await service.add_favorite(
        user_id="user-1",
        stock_code="600519",
        stock_name="贵州茅台",
        market="A股",
    )
    assert recorder.upserts[0]["source"] == CandidateSource.USER_SELECTED

    assert await service.remove_favorite("user-1", "600519")
    assert recorder.removals[0]["source"] == CandidateSource.USER_SELECTED


@pytest.mark.asyncio
async def test_candidate_failure_does_not_break_favorite_write(monkeypatch):
    db = FakeDB()
    recorder = RecordingCandidateService(fail=True)
    monkeypatch.setattr(
        "app.services.alphaguard.candidate_pool_service.get_candidate_pool_service",
        lambda: recorder,
    )
    service = FavoritesService()
    service.db = db

    success = await service.add_favorite(
        user_id="user-1",
        stock_code="600519",
        stock_name="贵州茅台",
        market="CN",
    )
    assert success is True
    stored = await db["user_favorites"].find_one({"user_id": "user-1"})
    assert stored["favorites"][0]["stock_code"] == "600519"
    assert recorder.failures

    repaired = await CandidatePoolService(db).reconcile_user("user-1")
    candidate = await CandidatePoolService(db).get_by_identity(
        "user-1", "CN", "600519"
    )
    assert repaired["added"] == 1
    assert candidate is not None
    assert CandidateSource.USER_SELECTED in candidate.sources


@pytest.mark.asyncio
async def test_positive_and_zero_paper_position_sync(monkeypatch):
    recorder = RecordingCandidateService()
    monkeypatch.setattr(
        "app.services.alphaguard.candidate_pool_service.get_candidate_pool_service",
        lambda: recorder,
    )
    await _sync_alphaguard_position_candidate(
        user_id="user-1", code="600519", market="CN", quantity=100
    )
    await _sync_alphaguard_position_candidate(
        user_id="user-1", code="600519", market="CN", quantity=0
    )
    assert recorder.upserts[0]["source"] == CandidateSource.POSITION_REQUIRED
    assert recorder.removals[0]["source"] == CandidateSource.POSITION_REQUIRED


@pytest.mark.asyncio
async def test_candidate_failure_does_not_change_completed_paper_result(monkeypatch):
    recorder = RecordingCandidateService(fail=True)
    monkeypatch.setattr(
        "app.services.alphaguard.candidate_pool_service.get_candidate_pool_service",
        lambda: recorder,
    )
    completed_trade = {
        "quantity": 100,
        "price": 10.0,
        "commission": 5.0,
        "status": "filled",
    }
    before = dict(completed_trade)
    await _sync_alphaguard_position_candidate(
        user_id="user-1", code="600519", market="CN", quantity=100
    )
    assert completed_trade == before
    assert recorder.failures


@pytest.mark.asyncio
async def test_existing_favorites_migration_is_idempotent():
    db = FakeDB()
    await db["user_favorites"].insert_one(
        {
            "user_id": "migration-user",
            "favorites": [
                {
                    "stock_code": "600519.SH",
                    "market": "A股",
                    "stock_name": "贵州茅台",
                }
            ],
        }
    )

    dry_run = await migrate_database(db, dry_run=True)
    assert dry_run == {
        "added": 1,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }
    assert db["ag_candidates"].count() == 0

    first = await migrate_database(db, dry_run=False)
    second = await migrate_database(db, dry_run=False)
    assert first["added"] == 1
    assert second["skipped"] == 1
    assert db["ag_candidates"].count() == 1
