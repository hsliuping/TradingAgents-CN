"""APScheduler entry points for idempotent PR-006 paper tasks."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.core.database import get_mongo_db
from app.utils.timezone import now_tz
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
)
from app.services.alphaguard.paper_task_service import PaperTaskService


def _minute_slot(name: str) -> str:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return f"{name}:{now.isoformat()}"


async def process_execution_outbox() -> dict:
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="process_execution_outbox",
        trade_date=None,
        idempotency_key=_minute_slot("process_execution_outbox"),
        operation=service.process_execution_outbox,
    )


async def create_order_intents() -> dict:
    # Kept as an explicit task name for operations; the reliable consumer above
    # performs factory + order submission as one idempotent outbox workflow.
    return await process_execution_outbox()


async def submit_paper_orders() -> int:
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="submit_paper_orders",
        trade_date=None,
        idempotency_key=_minute_slot("submit_paper_orders"),
        operation=service.submit_paper_orders,
    )


async def build_execution_market_snapshots(
    trade_date: date | None = None,
) -> dict:
    trade_date = trade_date or now_tz().date()
    calendar = PaperTradingCalendarService(get_mongo_db())
    if not await calendar.is_open_date(trade_date):
        return {"created": 0, "reused": 0, "skipped": "not a persisted open date"}
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="build_execution_market_snapshots",
        trade_date=trade_date,
        idempotency_key=f"build_execution_market_snapshots:{trade_date}",
        operation=lambda: service.build_execution_market_snapshots(trade_date),
    )


async def match_orders_for_trade_date(
    trade_date: date | None = None,
) -> dict:
    trade_date = trade_date or now_tz().date()
    calendar = PaperTradingCalendarService(get_mongo_db())
    if not await calendar.is_open_date(trade_date):
        return {"fills": 0, "no_fill": 0, "skipped": "not a persisted open date"}
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="match_orders_for_trade_date",
        trade_date=trade_date,
        idempotency_key=f"match_orders_for_trade_date:{trade_date}",
        operation=lambda: service.match_orders_for_trade_date(trade_date),
    )


async def settle_pending_fills() -> dict:
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="settle_pending_fills",
        trade_date=None,
        idempotency_key=_minute_slot("settle_pending_fills"),
        operation=service.settle_pending_fills,
    )


async def expire_orders() -> int:
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="expire_orders",
        trade_date=None,
        idempotency_key=_minute_slot("expire_orders"),
        operation=service.expire_orders,
    )


async def release_stale_reservations() -> int:
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="release_stale_reservations",
        trade_date=None,
        idempotency_key=_minute_slot("release_stale_reservations"),
        operation=service.release_stale_reservations,
    )


async def roll_position_lot_availability(
    trade_date: date | None = None,
) -> int:
    trade_date = trade_date or now_tz().date()
    calendar = PaperTradingCalendarService(get_mongo_db())
    if not await calendar.is_open_date(trade_date):
        return 0
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="roll_position_lot_availability",
        trade_date=trade_date,
        idempotency_key=f"roll_position_lot_availability:{trade_date}",
        operation=lambda: service.roll_position_lot_availability(trade_date),
    )


async def create_daily_account_snapshots(
    trade_date: date | None = None,
) -> int:
    trade_date = trade_date or now_tz().date()
    calendar = PaperTradingCalendarService(get_mongo_db())
    if not await calendar.is_open_date(trade_date):
        return 0
    service = PaperTaskService(get_mongo_db())
    return await service.run_once(
        job_type="create_daily_account_snapshots",
        trade_date=trade_date,
        idempotency_key=f"create_daily_account_snapshots:{trade_date}",
        operation=lambda: service.create_daily_account_snapshots(trade_date),
    )


async def reconcile_paper_accounts() -> dict:
    service = PaperTaskService(get_mongo_db())
    trade_date = now_tz().date()
    return await service.run_once(
        job_type="reconcile_paper_accounts",
        trade_date=trade_date,
        idempotency_key=f"reconcile_paper_accounts:{trade_date}",
        operation=service.reconcile_paper_accounts,
    )
