"""Candidate pool persistence, state policy, and reconciliation."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.database import get_mongo_db
from app.services.alphaguard.paper_storage import to_mongo_value
from tradingagents.alphaguard.candidate_schemas import (
    CANDIDATE_EVENT_SCHEMA_VERSION,
    CANDIDATE_SCHEMA_VERSION,
    CandidateEntry,
    CandidateEvent,
    CandidateEventType,
    CandidateSource,
    CandidateStatus,
    validate_candidate_transition,
)
from tradingagents.alphaguard.instruments import normalize_instrument, normalize_market


logger = logging.getLogger("webapi")

_IN_PROGRESS_STATUSES = {
    CandidateStatus.AI_ANALYZING,
    CandidateStatus.TOP_REVIEWING,
}
_TERMINAL_ORDER_STATUSES = {"filled", "cancelled", "canceled", "rejected", "expired"}


def _without_mongo_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    cleaned = dict(document)
    cleaned.pop("_id", None)
    return cleaned


def _candidate_document(candidate: CandidateEntry) -> dict[str, Any]:
    data = candidate.model_dump(mode="python")
    data["sources"] = sorted(source.value for source in candidate.sources)
    data["status"] = candidate.status.value
    return to_mongo_value(data)


def _event_document(event: CandidateEvent) -> dict[str, Any]:
    data = event.model_dump(mode="python")
    data["event_type"] = event.event_type.value
    data["previous_status"] = (
        event.previous_status.value if event.previous_status else None
    )
    data["new_status"] = event.new_status.value if event.new_status else None
    data["source_added"] = event.source_added.value if event.source_added else None
    data["source_removed"] = (
        event.source_removed.value if event.source_removed else None
    )
    return data


class CandidatePoolService:
    """Single write boundary for AlphaGuard candidate records."""

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        return self._db if self._db is not None else get_mongo_db()

    async def _record_event(
        self,
        *,
        candidate_id: str,
        user_id: str,
        event_type: CandidateEventType,
        reason: str,
        previous_status: CandidateStatus | None = None,
        new_status: CandidateStatus | None = None,
        source_added: CandidateSource | None = None,
        source_removed: CandidateSource | None = None,
        trace_id: str | None = None,
    ) -> CandidateEvent:
        event = CandidateEvent(
            event_id=str(uuid4()),
            candidate_id=candidate_id,
            user_id=str(user_id),
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            source_added=source_added,
            source_removed=source_removed,
            reason=reason,
            trace_id=trace_id,
            created_at=datetime.utcnow(),
            schema_version=CANDIDATE_EVENT_SCHEMA_VERSION,
        )
        await self.db["ag_candidate_events"].insert_one(_event_document(event))
        return event

    async def get_candidate(
        self, candidate_id: str, user_id: str | None = None
    ) -> CandidateEntry | None:
        query: dict[str, Any] = {"candidate_id": candidate_id}
        if user_id is not None:
            query["user_id"] = str(user_id)
        document = await self.db["ag_candidates"].find_one(query)
        cleaned = _without_mongo_id(document)
        return CandidateEntry.model_validate(cleaned) if cleaned else None

    async def get_by_identity(
        self, user_id: str, market: str, symbol: str
    ) -> CandidateEntry | None:
        normalized_market, normalized_symbol = normalize_instrument(symbol, market)
        document = await self.db["ag_candidates"].find_one(
            {
                "user_id": str(user_id),
                "market": normalized_market,
                "symbol": normalized_symbol,
            }
        )
        cleaned = _without_mongo_id(document)
        return CandidateEntry.model_validate(cleaned) if cleaned else None

    async def list_candidates(
        self,
        user_id: str,
        *,
        market: str | None = None,
        status: CandidateStatus | None = None,
        source: CandidateSource | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[CandidateEntry]:
        query: dict[str, Any] = {"user_id": str(user_id)}
        normalized_market = None
        if market:
            normalized_market = normalize_market(market, symbol)
            query["market"] = normalized_market
        if status:
            query["status"] = status.value
        if source:
            query["sources"] = source.value
        if symbol:
            if normalized_market is None:
                raise ValueError("market is required when filtering by symbol")
            query["symbol"] = normalize_instrument(symbol, normalized_market)[1]
        cursor = (
            self.db["ag_candidates"]
            .find(query)
            .sort([("priority", -1), ("updated_at", -1)])
            .limit(limit)
        )
        return [
            CandidateEntry.model_validate(_without_mongo_id(document))
            for document in await cursor.to_list(length=limit)
        ]

    async def upsert_source(
        self,
        *,
        user_id: str,
        symbol: str,
        market: str,
        source: CandidateSource,
        name: str | None = None,
        priority: int = 50,
        held_account_id: str | None = None,
        trace_id: str | None = None,
        reason: str = "candidate source synchronized",
        recommendation_id: str | None = None,
        recommendation_run_id: str | None = None,
        recommendation_score: float | None = None,
        recommendation_trade_date: date | None = None,
        recommendation_reason_summary: str | None = None,
    ) -> CandidateEntry:
        normalized_market, normalized_symbol = normalize_instrument(symbol, market)
        identity = {
            "user_id": str(user_id),
            "market": normalized_market,
            "symbol": normalized_symbol,
        }
        current = await self.get_by_identity(
            str(user_id), normalized_market, normalized_symbol
        )
        now = datetime.utcnow()

        if current is None:
            status = (
                CandidateStatus.POSITION_HELD
                if source == CandidateSource.POSITION_REQUIRED
                else CandidateStatus.WATCHING
            )
            candidate = CandidateEntry(
                candidate_id=str(uuid4()),
                user_id=str(user_id),
                symbol=normalized_symbol,
                market=normalized_market,
                name=name,
                sources={source},
                status=status,
                priority=priority,
                added_at=now,
                updated_at=now,
                next_scan_at=None,
                cooldown_until=None,
                active_plan_id=None,
                active_order_ids=[],
                held_account_ids=[held_account_id] if held_account_id else [],
                removal_requested=False,
                recommendation_id=recommendation_id,
                recommendation_run_id=recommendation_run_id,
                recommendation_score=recommendation_score,
                recommendation_trade_date=recommendation_trade_date,
                recommendation_reason_summary=recommendation_reason_summary,
                schema_version=CANDIDATE_SCHEMA_VERSION,
            )
            try:
                await self.db["ag_candidates"].insert_one(
                    _candidate_document(candidate)
                )
            except DuplicateKeyError:
                current = await self.get_by_identity(
                    str(user_id), normalized_market, normalized_symbol
                )
                if current is None:
                    raise
            else:
                await self._record_event(
                    candidate_id=candidate.candidate_id,
                    user_id=str(user_id),
                    event_type=CandidateEventType.CREATED,
                    previous_status=None,
                    new_status=candidate.status,
                    source_added=source,
                    reason=reason,
                    trace_id=trace_id,
                )
                return candidate

        assert current is not None
        source_was_present = source in current.sources
        previous_status = current.status
        sources = set(current.sources)
        sources.add(source)
        held_account_ids = set(current.held_account_ids)
        if held_account_id:
            held_account_ids.add(held_account_id)

        reactivated = current.status == CandidateStatus.REMOVED
        target_status = CandidateStatus.WATCHING if reactivated else current.status
        if reactivated:
            validate_candidate_transition(
                current.status,
                target_status,
                source_readded=True,
            )

        candidate = current.model_copy(
            update={
                "name": name or current.name,
                "sources": sources,
                "status": target_status,
                "priority": priority if not source_was_present else current.priority,
                "held_account_ids": sorted(held_account_ids),
                "removal_requested": False,
                "recommendation_id": recommendation_id or current.recommendation_id,
                "recommendation_run_id": (
                    recommendation_run_id or current.recommendation_run_id
                ),
                "recommendation_score": (
                    recommendation_score
                    if recommendation_score is not None
                    else current.recommendation_score
                ),
                "recommendation_trade_date": (
                    recommendation_trade_date or current.recommendation_trade_date
                ),
                "recommendation_reason_summary": (
                    recommendation_reason_summary
                    or current.recommendation_reason_summary
                ),
                "updated_at": now,
            }
        )
        candidate = CandidateEntry.model_validate(candidate.model_dump(mode="python"))
        await self.db["ag_candidates"].replace_one(identity, _candidate_document(candidate))

        if reactivated:
            await self._record_event(
                candidate_id=candidate.candidate_id,
                user_id=candidate.user_id,
                event_type=CandidateEventType.REACTIVATED,
                previous_status=previous_status,
                new_status=CandidateStatus.WATCHING,
                source_added=source,
                reason=reason,
                trace_id=trace_id,
            )
        elif not source_was_present:
            await self._record_event(
                candidate_id=candidate.candidate_id,
                user_id=candidate.user_id,
                event_type=CandidateEventType.SOURCE_ADDED,
                previous_status=previous_status,
                new_status=candidate.status,
                source_added=source,
                reason=reason,
                trace_id=trace_id,
            )

        if (
            source == CandidateSource.POSITION_REQUIRED
            and candidate.status != CandidateStatus.POSITION_HELD
        ):
            candidate = await self.transition_status(
                candidate.candidate_id,
                candidate.user_id,
                CandidateStatus.POSITION_HELD,
                reason="positive paper position requires monitoring",
                trace_id=trace_id,
            )
        return candidate

    async def transition_status(
        self,
        candidate_id: str,
        user_id: str,
        target: CandidateStatus,
        *,
        reason: str,
        trace_id: str | None = None,
    ) -> CandidateEntry:
        current = await self.get_candidate(candidate_id, user_id)
        if current is None:
            raise LookupError("candidate not found")
        validate_candidate_transition(current.status, target)
        candidate = current.model_copy(
            update={"status": target, "updated_at": datetime.utcnow()}
        )
        candidate = CandidateEntry.model_validate(candidate.model_dump(mode="python"))
        await self.db["ag_candidates"].replace_one(
            {"candidate_id": candidate_id, "user_id": str(user_id)},
            _candidate_document(candidate),
        )
        if current.status != target:
            await self._record_event(
                candidate_id=candidate_id,
                user_id=str(user_id),
                event_type=CandidateEventType.STATUS_CHANGED,
                previous_status=current.status,
                new_status=target,
                reason=reason,
                trace_id=trace_id,
            )
        return candidate

    async def sync_top_confirmed_paper_state(
        self,
        *,
        candidate_id: str,
        user_id: str,
        account_id: str,
        order_id: str,
        order_status: str,
        position_quantity: int,
        trace_id: str | None = None,
    ) -> CandidateEntry:
        """PR-006 state hook for PAPER_TOP_CONFIRMED only.

        Callers must enforce the account type. Benchmark accounts never call
        this method and therefore cannot mutate the main Candidate lifecycle.
        """

        current = await self.get_candidate(candidate_id, str(user_id))
        if current is None:
            raise LookupError("candidate not found")
        active_statuses = {
            "CREATED",
            "RESERVED",
            "SUBMITTED",
            "PENDING",
            "PARTIALLY_FILLED",
            "SETTLEMENT_PENDING",
            "SETTLEMENT_FAILED",
        }
        active_orders = set(current.active_order_ids)
        held_accounts = set(current.held_account_ids)
        if order_status in active_statuses:
            active_orders.add(order_id)
        else:
            active_orders.discard(order_id)
        if position_quantity > 0:
            held_accounts.add(account_id)
            target = CandidateStatus.POSITION_HELD
        else:
            held_accounts.discard(account_id)
            if active_orders:
                target = CandidateStatus.ORDER_PENDING
            elif order_status == "FILLED":
                target = CandidateStatus.WATCHING
            elif order_status in {"CANCELLED", "EXPIRED"}:
                target = CandidateStatus.APPROVED
            elif order_status == "REJECTED":
                target = CandidateStatus.REJECTED
            else:
                target = CandidateStatus.ORDER_PENDING
        if current.status != target:
            validate_candidate_transition(current.status, target)
        now = datetime.utcnow()
        candidate = CandidateEntry.model_validate(
            current.model_copy(
                update={
                    "status": target,
                    "active_order_ids": sorted(active_orders),
                    "held_account_ids": sorted(held_accounts),
                    "updated_at": now,
                }
            ).model_dump(mode="python")
        )
        await self.db["ag_candidates"].replace_one(
            {"candidate_id": candidate_id, "user_id": str(user_id)},
            _candidate_document(candidate),
        )
        if current.status != target:
            await self._record_event(
                candidate_id=candidate_id,
                user_id=str(user_id),
                event_type=CandidateEventType.STATUS_CHANGED,
                previous_status=current.status,
                new_status=target,
                reason=(
                    "PAPER_TOP_CONFIRMED automatic execution state synchronized"
                ),
                trace_id=trace_id,
            )
        return candidate

    async def update_candidate(
        self,
        candidate_id: str,
        user_id: str,
        changes: dict[str, Any],
        *,
        trace_id: str | None = None,
    ) -> CandidateEntry:
        current = await self.get_candidate(candidate_id, user_id)
        if current is None:
            raise LookupError("candidate not found")
        target = changes.pop("status", None)
        if target is not None:
            target = CandidateStatus(target)
            if target == CandidateStatus.REMOVED:
                raise ValueError("use protected removal instead of setting REMOVED")
            current = await self.transition_status(
                candidate_id,
                user_id,
                target,
                reason="candidate status updated through API",
                trace_id=trace_id,
            )
        allowed = {"name", "priority", "next_scan_at", "cooldown_until"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported candidate fields: {sorted(unknown)}")
        if changes:
            changes["updated_at"] = datetime.utcnow()
            current = CandidateEntry.model_validate(
                current.model_copy(update=changes).model_dump(mode="python")
            )
            await self.db["ag_candidates"].replace_one(
                {"candidate_id": candidate_id, "user_id": str(user_id)},
                _candidate_document(current),
            )
        return current

    async def _live_monitoring_reasons(
        self, candidate: CandidateEntry, remaining_sources: set[CandidateSource]
    ) -> tuple[list[str], list[str], list[str]]:
        from app.services.alphaguard.evaluation_repository import (
            EvaluationRepository,
        )

        reasons: list[str] = []
        held_accounts = set(candidate.held_account_ids)
        active_orders = set(candidate.active_order_ids)

        positions = await self.db["paper_positions"].find(
            {"user_id": candidate.user_id, "quantity": {"$gt": 0}}
        ).to_list(length=None)
        for position in positions:
            try:
                market, symbol = normalize_instrument(
                    position.get("code") or position.get("symbol"),
                    position.get("market") or candidate.market,
                )
            except ValueError:
                continue
            if market == candidate.market and symbol == candidate.symbol:
                held_accounts.add(
                    str(position.get("account_id") or f"manual-paper:{candidate.user_id}")
                )

        orders = await self.db["paper_orders"].find(
            {
                "user_id": candidate.user_id,
                "status": {"$nin": sorted(_TERMINAL_ORDER_STATUSES)},
            }
        ).to_list(length=None)
        for order in orders:
            try:
                market, symbol = normalize_instrument(
                    order.get("code") or order.get("symbol"),
                    order.get("market") or candidate.market,
                )
            except ValueError:
                continue
            if market == candidate.market and symbol == candidate.symbol:
                active_orders.add(str(order.get("order_id") or order.get("_id")))

        if remaining_sources:
            reasons.append("remaining_sources")
        if held_accounts:
            reasons.append("positive_position")
        if active_orders:
            reasons.append("unfinished_order")
        if candidate.active_plan_id:
            reasons.append("active_plan")
        if candidate.status in _IN_PROGRESS_STATUSES:
            reasons.append("analysis_in_progress")
        if (
            await EvaluationRepository(self.db).pending_candidate_count(
                candidate.candidate_id
            )
            > 0
        ):
            reasons.append("pending_evaluation")
        return sorted(set(reasons)), sorted(held_accounts), sorted(active_orders)

    async def remove_source(
        self,
        *,
        user_id: str,
        symbol: str,
        market: str,
        source: CandidateSource,
        removal_requested: bool = False,
        held_account_id: str | None = None,
        trace_id: str | None = None,
        reason: str = "candidate source removed",
    ) -> tuple[CandidateEntry | None, list[str]]:
        current = await self.get_by_identity(user_id, market, symbol)
        if current is None:
            return None, []
        sources = set(current.sources)
        source_was_present = source in sources
        sources.discard(source)
        held_account_ids = set(current.held_account_ids)
        if held_account_id:
            held_account_ids.discard(held_account_id)

        probe = current.model_copy(
            update={
                "sources": sources,
                "held_account_ids": sorted(held_account_ids),
            }
        )
        monitoring_reasons, live_accounts, active_orders = (
            await self._live_monitoring_reasons(probe, sources)
        )
        if "positive_position" in monitoring_reasons:
            sources.add(CandidateSource.POSITION_REQUIRED)

        target_status = current.status
        request_flag = current.removal_requested or removal_requested
        if not monitoring_reasons:
            target_status = CandidateStatus.REMOVED
            validate_candidate_transition(current.status, target_status)
            request_flag = False
        elif (
            current.status == CandidateStatus.POSITION_HELD
            and "positive_position" not in monitoring_reasons
        ):
            target_status = CandidateStatus.WATCHING
            validate_candidate_transition(current.status, target_status)

        candidate = current.model_copy(
            update={
                "sources": sources,
                "status": target_status,
                "held_account_ids": live_accounts,
                "active_order_ids": active_orders,
                "removal_requested": request_flag,
                **(
                    {
                        "recommendation_id": None,
                        "recommendation_run_id": None,
                        "recommendation_score": None,
                        "recommendation_trade_date": None,
                        "recommendation_reason_summary": None,
                    }
                    if source == CandidateSource.SYSTEM_RECOMMENDED_CONFIRMED
                    else {}
                ),
                "updated_at": datetime.utcnow(),
            }
        )
        candidate = CandidateEntry.model_validate(candidate.model_dump(mode="python"))
        await self.db["ag_candidates"].replace_one(
            {"candidate_id": candidate.candidate_id},
            _candidate_document(candidate),
        )

        if source_was_present:
            await self._record_event(
                candidate_id=candidate.candidate_id,
                user_id=candidate.user_id,
                event_type=CandidateEventType.SOURCE_REMOVED,
                previous_status=current.status,
                new_status=candidate.status,
                source_removed=source,
                reason=reason,
                trace_id=trace_id,
            )
        if target_status == CandidateStatus.REMOVED:
            await self._record_event(
                candidate_id=candidate.candidate_id,
                user_id=candidate.user_id,
                event_type=CandidateEventType.MARKED_REMOVED,
                previous_status=current.status,
                new_status=target_status,
                reason="all monitoring dependencies cleared",
                trace_id=trace_id,
            )
        elif removal_requested:
            await self._record_event(
                candidate_id=candidate.candidate_id,
                user_id=candidate.user_id,
                event_type=CandidateEventType.REMOVAL_BLOCKED,
                previous_status=current.status,
                new_status=candidate.status,
                reason="monitoring retained: " + ",".join(monitoring_reasons),
                trace_id=trace_id,
            )
        return candidate, monitoring_reasons

    async def request_removal(
        self, candidate_id: str, user_id: str, trace_id: str | None = None
    ) -> tuple[CandidateEntry, list[str]]:
        current = await self.get_candidate(candidate_id, user_id)
        if current is None:
            raise LookupError("candidate not found")
        removable_source = (
            CandidateSource.USER_SELECTED
            if CandidateSource.USER_SELECTED in current.sources
            else CandidateSource.SYSTEM_RECOMMENDED_CONFIRMED
        )
        candidate, reasons = await self.remove_source(
            user_id=current.user_id,
            symbol=current.symbol,
            market=current.market,
            source=removable_source,
            removal_requested=True,
            trace_id=trace_id,
            reason="user requested candidate removal",
        )
        assert candidate is not None
        if reasons:
            await self._record_event(
                candidate_id=candidate.candidate_id,
                user_id=candidate.user_id,
                event_type=CandidateEventType.REMOVAL_REQUESTED,
                previous_status=current.status,
                new_status=candidate.status,
                reason="removal request recorded",
                trace_id=trace_id,
            )
        return candidate, reasons

    async def reconcile_user(
        self, user_id: str, trace_id: str | None = None
    ) -> dict[str, int]:
        stats = {"added": 0, "updated": 0, "removed_source": 0, "skipped": 0, "failed": 0}
        favorite_identities: set[tuple[str, str]] = set()
        favorite_rows: list[dict[str, Any]] = []

        favorite_document = await self.db["user_favorites"].find_one(
            {"user_id": str(user_id)}
        )
        favorite_rows.extend((favorite_document or {}).get("favorites", []))

        user_identifiers: list[Any] = [str(user_id)]
        if ObjectId.is_valid(str(user_id)):
            user_identifiers.append(ObjectId(str(user_id)))
        user_document = await self.db["users"].find_one(
            {"_id": {"$in": user_identifiers}}
        )
        favorite_rows.extend((user_document or {}).get("favorite_stocks", []))

        for favorite in favorite_rows:
            try:
                market, symbol = normalize_instrument(
                    favorite.get("stock_code") or favorite.get("symbol"),
                    favorite.get("market") or "CN",
                )
                favorite_identities.add((market, symbol))
                existing = await self.get_by_identity(user_id, market, symbol)
                await self.upsert_source(
                    user_id=user_id,
                    symbol=symbol,
                    market=market,
                    source=CandidateSource.USER_SELECTED,
                    name=favorite.get("stock_name") or favorite.get("name"),
                    trace_id=trace_id,
                    reason="favorite reconciliation",
                )
                if existing is None:
                    stats["added"] += 1
                elif CandidateSource.USER_SELECTED not in existing.sources:
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception:
                stats["failed"] += 1
                logger.exception("AlphaGuard favorite reconciliation failed")

        favorite_cursor = self.db["ag_candidates"].find(
            {
                "user_id": str(user_id),
                "sources": CandidateSource.USER_SELECTED.value,
            }
        )
        for document in await favorite_cursor.to_list(length=None):
            candidate = CandidateEntry.model_validate(_without_mongo_id(document))
            if (candidate.market, candidate.symbol) in favorite_identities:
                continue
            try:
                await self.remove_source(
                    user_id=user_id,
                    symbol=candidate.symbol,
                    market=candidate.market,
                    source=CandidateSource.USER_SELECTED,
                    trace_id=trace_id,
                    reason="favorite removal reconciliation",
                )
                stats["removed_source"] += 1
            except Exception:
                stats["failed"] += 1
                logger.exception("AlphaGuard favorite removal reconciliation failed")

        positive: set[tuple[str, str]] = set()
        positions = await self.db["paper_positions"].find(
            {"user_id": str(user_id), "quantity": {"$gt": 0}}
        ).to_list(length=None)
        for position in positions:
            try:
                market, symbol = normalize_instrument(
                    position.get("code") or position.get("symbol"),
                    position.get("market") or "CN",
                )
                positive.add((market, symbol))
                existing = await self.get_by_identity(user_id, market, symbol)
                await self.upsert_source(
                    user_id=user_id,
                    symbol=symbol,
                    market=market,
                    source=CandidateSource.POSITION_REQUIRED,
                    name=position.get("name"),
                    held_account_id=str(
                        position.get("account_id") or f"manual-paper:{user_id}"
                    ),
                    trace_id=trace_id,
                    reason="paper position reconciliation",
                )
                stats["updated" if existing else "added"] += 1
            except Exception:
                stats["failed"] += 1
                logger.exception("AlphaGuard position reconciliation failed")

        cursor = self.db["ag_candidates"].find(
            {"user_id": str(user_id), "sources": CandidateSource.POSITION_REQUIRED.value}
        )
        for document in await cursor.to_list(length=None):
            candidate = CandidateEntry.model_validate(_without_mongo_id(document))
            if (candidate.market, candidate.symbol) in positive:
                continue
            try:
                await self.remove_source(
                    user_id=user_id,
                    symbol=candidate.symbol,
                    market=candidate.market,
                    source=CandidateSource.POSITION_REQUIRED,
                    held_account_id=f"manual-paper:{user_id}",
                    trace_id=trace_id,
                    reason="zero-position reconciliation",
                )
                stats["removed_source"] += 1
            except Exception:
                stats["failed"] += 1
                logger.exception("AlphaGuard zero-position reconciliation failed")

        await self._record_event(
            candidate_id=f"reconcile:{user_id}",
            user_id=str(user_id),
            event_type=CandidateEventType.RECONCILED,
            reason=f"candidate reconciliation completed: {stats}",
            trace_id=trace_id,
        )
        return stats

    async def record_sync_failure(
        self,
        *,
        user_id: str,
        symbol: str,
        market: str,
        reason: str,
        trace_id: str | None = None,
    ) -> None:
        try:
            normalized_market, normalized_symbol = normalize_instrument(symbol, market)
            candidate = await self.get_by_identity(
                user_id, normalized_market, normalized_symbol
            )
            candidate_id = (
                candidate.candidate_id
                if candidate
                else f"unresolved:{user_id}:{normalized_market}:{normalized_symbol}"
            )
            await self._record_event(
                candidate_id=candidate_id,
                user_id=str(user_id),
                event_type=CandidateEventType.SYNC_FAILED,
                reason=reason[:500],
                trace_id=trace_id,
            )
        except Exception:
            logger.exception("Unable to persist AlphaGuard SYNC_FAILED event")


def get_candidate_pool_service() -> CandidatePoolService:
    return CandidatePoolService()
