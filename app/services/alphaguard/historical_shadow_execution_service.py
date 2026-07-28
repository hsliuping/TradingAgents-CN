"""Research-only execution approximation using the PR-006 pure engines."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, ROUND_FLOOR
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.execution_market_snapshot_service import (
    ExecutionMarketSnapshotService,
    ExecutionSnapshotError,
)
from app.services.alphaguard.fee_engine import FeeEngine
from app.services.alphaguard.matching_engine import MatchingEngine
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
)
from app.services.alphaguard.paper_policy_registry import (
    PaperPolicyRegistry,
)
from app.services.alphaguard.paper_storage import clean_document, mongo_date
from tradingagents.alphaguard.backfill_schemas import (
    ResearchShadowExecution,
    backfill_hash,
)
from tradingagents.alphaguard.paper_schemas import PaperOrder


class _ResearchDB:
    """Redirect the snapshot service's two writes into research collections."""

    _MAP = {
        "ag_execution_market_snapshots": "ag_research_execution_snapshots",
        "ag_paper_events": "ag_research_backfill_events",
    }

    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return self._db[self._MAP.get(name, name)]


class HistoricalShadowExecutionService:
    def __init__(self, db):
        self.db = db
        self.calendar = PaperTradingCalendarService(db)
        self.policies = PaperPolicyRegistry(db)
        self.matching = MatchingEngine()
        self.fees = FeeEngine()

    async def evaluate(
        self,
        *,
        backfill_run_id: str,
        sample_id: str,
        proposal,
        primary_label=None,
        now: datetime | None = None,
    ) -> ResearchShadowExecution:
        now = now or datetime.utcnow()
        execution_policy = await self.policies.execution_policy()
        fee_policy = await self.policies.fee_policy()
        account_policy = await self.policies.account_policy()
        base = {
            "backfill_run_id": backfill_run_id,
            "sample_id": sample_id,
            "proposal_id": proposal.proposal_id,
            "action": proposal.action_candidate,
            "matching_version": execution_policy.matching_engine_version,
            "fee_version": fee_policy.version,
        }
        if proposal.status != "TRIGGERED":
            return self._result(
                base,
                status="NOT_ELIGIBLE",
                reason=f"proposal status is {proposal.status}",
                now=now,
            )
        if proposal.action_candidate != "BUY" or proposal.entry_zone is None:
            return self._result(
                base,
                status="INSUFFICIENT_DATA",
                reason="first research executor requires a BUY entry zone",
                now=now,
            )
        sessions = await self.calendar.open_dates(after=proposal.trade_date)
        sessions = [
            item
            for item in sessions
            if proposal.valid_until is None or item <= proposal.valid_until.date()
        ]
        if not sessions:
            return self._result(
                base,
                status="INSUFFICIENT_DATA",
                reason="persisted calendar has no valid execution session",
                now=now,
            )
        limit_price = Decimal(str(proposal.entry_zone.upper))
        capital = account_policy.initial_cash * Decimal(
            str(proposal.initial_position_pct)
        )
        quantity = int(
            (capital / limit_price).to_integral_value(rounding=ROUND_FLOOR)
        )
        quantity = (
            quantity
            // execution_policy.cn_buy_lot_size
            * execution_policy.cn_buy_lot_size
        )
        if quantity <= 0:
            return self._result(
                base,
                status="NOT_ELIGIBLE",
                reason="normalized research quantity rounds to zero",
                now=now,
            )
        order = PaperOrder(
            order_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"research-order:{backfill_run_id}:{proposal.proposal_id}",
                )
            ),
            intent_id=f"research-intent:{proposal.proposal_id}",
            account_id=f"research-account:{backfill_run_id}",
            user_id=proposal.user_id,
            account_type="PAPER_QUANT",
            source_type="RESEARCH_BACKFILL",
            source_object_id=proposal.proposal_id,
            symbol=proposal.symbol,
            side="BUY",
            original_action="BUY",
            order_type="LIMIT",
            requested_quantity=quantity,
            reserved_quantity=quantity,
            remaining_quantity=quantity,
            limit_price=limit_price,
            status="SUBMITTED",
            trade_date=sessions[0],
            earliest_execute_at=datetime.combine(sessions[0], time(15, 0)),
            expires_at=datetime.combine(sessions[-1], time(23, 59, 59)),
            submitted_at=datetime.combine(sessions[0], time(9, 0)),
            created_at=now,
            updated_at=now,
        )
        attempts: list[dict] = []
        snapshot_service = ExecutionMarketSnapshotService(_ResearchDB(self.db))
        for execution_date in sessions:
            raw = clean_document(
                await self.db["stock_daily_quotes"].find_one(
                    {
                        "symbol": proposal.symbol,
                        "market": "CN",
                        "trade_date": {
                            "$in": [mongo_date(execution_date), execution_date.isoformat()]
                        },
                        "period": "daily",
                    }
                )
            )
            if raw is None:
                attempts.append(
                    {"trade_date": execution_date, "status": "MISSING_DAILY_BAR"}
                )
                continue
            if raw.get("limit_up_price") is None or raw.get("limit_down_price") is None:
                return self._result(
                    base,
                    status="INSUFFICIENT_DATA",
                    reason=(
                        "daily source lacks explicit limit-up/limit-down prices; "
                        "research executor will not infer board limits"
                    ),
                    order_payload={
                        **order.model_dump(mode="python"),
                        "attempts": attempts,
                    },
                    normalized_notional=account_policy.initial_cash,
                    now=now,
                )
            # Historical execution data is intentionally collected after the
            # simulated trade date.  The production snapshot service rejects
            # such collection timestamps, which is correct for live T+1
            # execution but not for a frozen research replay.  Remove only
            # ingestion metadata; trade_date, version, source reference and
            # content remain locked and auditable.
            research_record = dict(raw)
            research_record.pop("updated_at", None)
            research_record.pop("as_of", None)
            data_version = str(
                raw.get("raw_data_version") or raw.get("data_version") or ""
            )
            source_ref = str(raw.get("ref_id") or raw.get("data_ref") or "")
            if not data_version or not source_ref:
                return self._result(
                    base,
                    status="INSUFFICIENT_DATA",
                    reason="execution daily source lacks immutable version/reference",
                    order_payload=order.model_dump(mode="python"),
                    normalized_notional=account_policy.initial_cash,
                    now=now,
                )
            try:
                snapshot = await snapshot_service.create_from_daily_record(
                    record=research_record,
                    symbol=proposal.symbol,
                    trade_date=execution_date,
                    cutoff_at=datetime.combine(execution_date, time(15, 0)),
                    data_version=data_version,
                    source_ref=source_ref,
                    now=now,
                )
            except ExecutionSnapshotError as exc:
                return self._result(
                    base,
                    status="BLOCKED",
                    reason=str(exc),
                    order_payload=order.model_dump(mode="python"),
                    normalized_notional=account_policy.initial_cash,
                    now=now,
                )
            match = self.matching.match(
                order=order,
                snapshot=snapshot,
                policy=execution_policy,
                valid_reserved_quantity=quantity,
                matched_at=datetime.combine(execution_date, time(15, 0)),
            )
            attempts.append(
                {
                    "trade_date": execution_date,
                    "snapshot_id": snapshot.execution_snapshot_id,
                    "match": match.model_dump(mode="python"),
                }
            )
            if match.status not in {"PARTIAL_FILL", "FULL_FILL"}:
                continue
            assert match.price is not None
            notional = match.price * match.quantity
            entry_fee = self.fees.calculate(
                side="BUY", notional=notional, policy=fee_policy
            )
            gross_return = net_return = None
            fee_payload = {
                "entry_fee": entry_fee.model_dump(mode="python"),
                "exit_fee": None,
                "total_fee": entry_fee.total_fee,
            }
            if (
                primary_label is not None
                and primary_label.status == "CALCULATED"
                and primary_label.horizon_end_date is not None
            ):
                exit_bar = clean_document(
                    await self.db["stock_daily_quotes"].find_one(
                        {
                            "symbol": proposal.symbol,
                            "market": "CN",
                            "trade_date": {
                                "$in": [
                                    mongo_date(primary_label.horizon_end_date),
                                    primary_label.horizon_end_date.isoformat(),
                                ]
                            },
                            "period": "daily",
                        }
                    )
                )
                if exit_bar and exit_bar.get("close") is not None:
                    exit_price = Decimal(str(exit_bar["close"]))
                    exit_notional = exit_price * match.quantity
                    exit_fee = self.fees.calculate(
                        side="SELL", notional=exit_notional, policy=fee_policy
                    )
                    fee_payload = {
                        "entry_fee": entry_fee.model_dump(mode="python"),
                        "exit_fee": exit_fee.model_dump(mode="python"),
                        "total_fee": entry_fee.total_fee + exit_fee.total_fee,
                    }
                    gross_return = exit_price / match.price - Decimal("1")
                    net_return = (
                        exit_notional
                        - notional
                        - entry_fee.total_fee
                        - exit_fee.total_fee
                    ) / notional
            return self._result(
                base,
                status=(
                    "FILLED" if match.status == "FULL_FILL" else "PARTIALLY_FILLED"
                ),
                reason=match.reason,
                order_payload={
                    **order.model_dump(mode="python"),
                    "attempts": attempts,
                },
                match_payload=match.model_dump(mode="python"),
                fee_payload=fee_payload,
                normalized_notional=notional,
                gross_return=gross_return,
                net_return=net_return,
                now=now,
            )
        return self._result(
            base,
            status="NO_FILL",
            reason="no valid session produced a deterministic fill",
            order_payload={
                **order.model_dump(mode="python"),
                "attempts": attempts,
            },
            normalized_notional=account_policy.initial_cash,
            now=now,
        )

    @staticmethod
    def _result(
        base: dict,
        *,
        status: str,
        reason: str,
        now: datetime,
        order_payload: dict | None = None,
        match_payload: dict | None = None,
        fee_payload: dict | None = None,
        normalized_notional: Decimal | None = None,
        gross_return: Decimal | None = None,
        net_return: Decimal | None = None,
    ) -> ResearchShadowExecution:
        payload = {
            **base,
            "status": status,
            "reason": reason,
            "order_payload": order_payload,
            "match_payload": match_payload,
            "fee_payload": fee_payload,
            "normalized_notional": normalized_notional,
            "gross_return": gross_return,
            "net_return": net_return,
        }
        payload["input_hash"] = backfill_hash(payload)
        return ResearchShadowExecution(
            shadow_execution_id=str(
                uuid5(
                    NAMESPACE_URL,
                    "alphaguard:research-shadow:"
                    f"{base['backfill_run_id']}:{base['proposal_id']}",
                )
            ),
            created_at=now,
            **payload,
        )
