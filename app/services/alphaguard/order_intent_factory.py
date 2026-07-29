"""Internal-only creation of immutable OrderIntent records."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import (
    ConsensusDecision,
    RiskDecision,
)
from app.schemas.alphaguard.quant import QuantTradeProposal
from app.services.alphaguard.benchmark_execution_safety_gate import (
    BenchmarkExecutionSafetyGate,
)
from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
)
from app.services.alphaguard.execution_mode_safety_gate import (
    ExecutionModeSafetyGate,
)
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_audit_service import PaperAuditService
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
    TradingCalendarUnavailable,
)
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from app.services.alphaguard.paper_storage import clean_document, model_document
from app.services.alphaguard.risk_policy_registry import RiskPolicyRegistry
from app.services.alphaguard.snapshot_data_resolver import SnapshotDataResolver
from tradingagents.alphaguard.decision_schemas import NormalTradePlan
from tradingagents.alphaguard.paper_schemas import (
    BenchmarkExecutionDecision,
    ExecutionOutboxEvent,
    OrderIntent,
    PAPER_SCHEMA_VERSION,
    PaperPosition,
    paper_canonical_hash,
)


ACTIVE_ORDER_STATUSES = {
    "CREATED",
    "RESERVED",
    "SUBMITTED",
    "PENDING",
    "PARTIALLY_FILLED",
    "SETTLEMENT_PENDING",
    "SETTLEMENT_FAILED",
}


class OrderIntentRejected(ValueError):
    pass


class OrderIntentSuspended(RuntimeError):
    pass


class OrderIntentConflictError(ValueError):
    pass


def _without_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    return clean_document(document)


def _naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _explicit_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"1", "TRUE", "Y", "YES", "SUSPENDED", "停牌", "ST", "*ST"}:
            return True
        if normalized in {"0", "FALSE", "N", "NO", "NORMAL", "交易"}:
            return False
    return None


def _snapshot_trading_status(
    price_evidence: dict[str, Any] | None,
    instrument: dict[str, Any] | None,
    *,
    action: str,
) -> tuple[bool, bool]:
    source = {**(price_evidence or {}), **(instrument or {})}
    suspended = _explicit_bool(source.get("suspended"))
    if suspended is None and "tradestatus" in source:
        normalized = str(source["tradestatus"]).strip().upper()
        if normalized in {"0", "FALSE", "N", "NO", "SUSPENDED", "停牌"}:
            suspended = True
        elif normalized in {"1", "TRUE", "Y", "YES", "NORMAL", "交易"}:
            suspended = False
    st_status = None
    for field in ("st_status", "isST", "is_st"):
        if field in source:
            st_status = _explicit_bool(source[field])
            break
    known = suspended is not None and (action != "BUY" or st_status is not None)
    blocked = suspended is True or (action == "BUY" and st_status is True)
    return known, blocked


class OrderIntentFactory:
    """Only this internal service may persist automatic OrderIntent objects."""

    def __init__(self, db):
        self.db = db
        self.collection = db["ag_order_intents"]
        self.accounts = PaperAccountService(db)
        self.calendar = PaperTradingCalendarService(db)
        self.policies = PaperPolicyRegistry(db)
        self.audit = PaperAuditService(db)
        self.benchmark_gate = BenchmarkExecutionSafetyGate()
        self.execution_mode_gate = ExecutionModeSafetyGate(db)

    async def create_from_outbox(
        self,
        event: ExecutionOutboxEvent,
        *,
        now: datetime | None = None,
    ) -> OrderIntent:
        await self.execution_mode_gate.assert_outbox_allowed(
            event_type=event.event_type,
            source_object_id=event.source_object_id,
        )
        if event.status != "PROCESSING":
            raise OrderIntentRejected("outbox event must be PROCESSING")
        if event.event_type == "CREATE_TOP_CONFIRMED_INTENT":
            return await self._top_confirmed(event, now=now)
        if event.event_type == "CREATE_QUANT_BENCHMARK_INTENT":
            return await self._quant_benchmark(event, now=now)
        if event.event_type == "CREATE_NORMAL_BENCHMARK_INTENT":
            return await self._normal_benchmark(event, now=now)
        raise OrderIntentRejected("unsupported outbox event type")

    async def _top_confirmed(
        self,
        event: ExecutionOutboxEvent,
        *,
        now: datetime | None,
    ) -> OrderIntent:
        now = now or datetime.utcnow()
        raw = _without_id(
            await self.db["ag_risk_decisions"].find_one(
                {
                    "risk_decision_id": event.source_object_id,
                }
            )
        )
        if raw is None:
            raise OrderIntentRejected("RiskDecision does not exist")
        risk = RiskDecision.model_validate(raw)
        if risk.status not in {"PASS", "REDUCE"}:
            raise OrderIntentRejected("RiskDecision is not PASS or REDUCE")
        if risk.order_intent_created is not False:
            raise OrderIntentRejected("RiskDecision side-effect invariant is broken")
        if not risk.approved_quantity or risk.approved_quantity <= 0:
            raise OrderIntentRejected("RiskDecision approved_quantity is not positive")
        if risk.earliest_eligible_execute_at is None:
            raise OrderIntentSuspended("RiskDecision has no reliable execution date")
        consensus_raw = _without_id(
            await self.db["ag_consensus_decisions"].find_one(
                {"consensus_id": risk.consensus_id}
            )
        )
        if consensus_raw is None:
            raise OrderIntentRejected("ConsensusDecision does not exist")
        consensus = ConsensusDecision.model_validate(consensus_raw)
        if consensus.status != "CONSENSUS_PASS" or consensus.final_plan is None:
            raise OrderIntentRejected("ConsensusDecision is not a pass")
        plan = consensus.final_plan
        if (
            risk.snapshot_id != consensus.snapshot_id
            or risk.quant_proposal_id != consensus.quant_proposal_id
            or risk.analysis_id != consensus.analysis_id
            or consensus.plan_id != plan.plan_id
            or plan.snapshot_id != risk.snapshot_id
            or plan.quant_proposal_id != risk.quant_proposal_id
            or plan.action != risk.action
        ):
            raise OrderIntentRejected("Risk/Consensus/Plan identity mismatch")
        if plan.valid_until is None or _naive(plan.valid_until) < now:
            raise OrderIntentRejected("final plan has expired")
        context_raw = _without_id(
            await self.db["ag_decision_contexts"].find_one(
                {"analysis_id": risk.analysis_id}
            )
        )
        if context_raw is None:
            raise OrderIntentRejected("DecisionContext does not exist")
        if (
            str(context_raw.get("snapshot_id")) != risk.snapshot_id
            or str(context_raw.get("quant_proposal_id")) != risk.quant_proposal_id
            or str(context_raw.get("symbol")) != str(plan.symbol)
            or str(context_raw.get("market")) != str(plan.market)
        ):
            raise OrderIntentRejected("DecisionContext identity mismatch")
        snapshot = await EvidenceSnapshotService(self.db).get(
            risk.snapshot_id,
            event.user_id,
        )
        if snapshot is None or not EvidenceSnapshotService.verify_integrity(snapshot):
            raise OrderIntentRejected("EvidenceSnapshot is missing or tampered")
        if (
            snapshot.symbol != plan.symbol
            or snapshot.market != plan.market
            or snapshot.trade_date != plan.trade_date
        ):
            raise OrderIntentRejected("snapshot and final plan identity mismatch")
        account_id = event.account_id or risk.account_id
        if not account_id or risk.account_id != account_id:
            raise OrderIntentRejected("RiskDecision account_id mismatch")
        account = await self.accounts.get_account(account_id, user_id=event.user_id)
        if account is None or account.account_type != "PAPER_TOP_CONFIRMED":
            raise OrderIntentRejected("TOP_CONFIRMED automatic account not found")
        if account.status != "ACTIVE":
            raise OrderIntentSuspended("TOP_CONFIRMED automatic account is not active")
        execution = await self.policies.execution_policy()
        fee = await self.policies.fee_policy()
        earliest, expires = await self.calendar.execution_window(
            earliest_date=_naive(risk.earliest_eligible_execute_at).date(),
            validity_sessions=execution.validity_sessions,
        )
        expires = min(expires, _naive(plan.valid_until))
        return await self._create(
            event=event,
            account=account,
            source_type="RISK_DECISION",
            source_object_id=risk.risk_decision_id,
            snapshot_id=risk.snapshot_id,
            quant_proposal_id=risk.quant_proposal_id,
            plan_id=plan.plan_id,
            consensus_id=consensus.consensus_id,
            risk_decision_id=risk.risk_decision_id,
            symbol=str(plan.symbol),
            action=risk.action,
            quantity=risk.approved_quantity,
            limit_price=(
                Decimal(str(plan.entry_zone.upper))
                if plan.action == "BUY" and plan.entry_zone is not None
                else None
            ),
            earliest=earliest,
            expires=expires,
            analysis_id=risk.analysis_id,
            candidate_id=context_raw.get("candidate_id"),
            benchmark_only=False,
            consensus_approved=True,
            hard_risk_approved=True,
            execution_version=execution.version,
            matching_version=execution.matching_engine_version,
            fee_version=fee.version,
            now=now,
        )

    async def _quant_benchmark(
        self,
        event: ExecutionOutboxEvent,
        *,
        now: datetime | None,
    ) -> OrderIntent:
        raw = _without_id(
            await self.db["ag_quant_proposals"].find_one(
                {
                    "proposal_id": event.source_object_id,
                    "user_id": event.user_id,
                }
            )
        )
        if raw is None:
            raise OrderIntentRejected("QuantTradeProposal does not exist")
        proposal = QuantTradeProposal.model_validate(raw)
        if (
            proposal.status != "TRIGGERED"
            or proposal.action_candidate not in {"BUY", "SELL", "REDUCE"}
            or proposal.automated_execution_allowed is not False
        ):
            raise OrderIntentRejected("QuantTradeProposal is not benchmark eligible")
        return await self._benchmark(
            event=event,
            source_type="QUANT",
            source=proposal,
            action=proposal.action_candidate,
            source_object_id=proposal.proposal_id,
            snapshot_id=proposal.snapshot_id,
            quant_proposal_id=proposal.proposal_id,
            plan_id=None,
            symbol=proposal.symbol,
            market=proposal.market,
            trade_date=proposal.trade_date,
            requested_pct=proposal.initial_position_pct,
            requested_quantity=None,
            entry_price=(
                Decimal(str(proposal.entry_zone.upper))
                if proposal.entry_zone is not None
                else None
            ),
            valid_until=proposal.valid_until,
            analysis_id=event.analysis_id,
            candidate_id=proposal.candidate_id,
            now=now,
        )

    async def _normal_benchmark(
        self,
        event: ExecutionOutboxEvent,
        *,
        now: datetime | None,
    ) -> OrderIntent:
        if not event.analysis_id:
            raise OrderIntentRejected("normal benchmark event lacks analysis_id")
        report = _without_id(
            await self.db["analysis_reports"].find_one(
                {"analysis_id": event.analysis_id, "user_id": event.user_id}
            )
        )
        if report is None:
            raise OrderIntentRejected("analysis report does not exist")
        history = report.get("normal_trade_plan_history") or []
        matches = [
            NormalTradePlan.model_validate(item)
            for item in history
            if str(item.get("plan_id")) == event.source_object_id
            and int(item.get("revision_round", 0)) == 0
        ]
        if not matches:
            current = report.get("normal_trade_plan")
            if (
                current
                and str(current.get("plan_id")) == event.source_object_id
                and int(current.get("revision_round", 0)) == 0
            ):
                matches = [NormalTradePlan.model_validate(current)]
        if len(matches) != 1:
            raise OrderIntentRejected("unique round-0 NormalTradePlan not found")
        plan = matches[0]
        if plan.status != "PROPOSE_TRADE" or plan.action not in {
            "BUY",
            "SELL",
            "REDUCE",
        }:
            raise OrderIntentRejected("NormalTradePlan is not benchmark eligible")
        if not all(
            [
                plan.snapshot_id,
                plan.quant_proposal_id,
                plan.symbol,
                plan.market,
                plan.trade_date,
            ]
        ):
            raise OrderIntentRejected("NormalTradePlan lacks formal identity fields")
        return await self._benchmark(
            event=event,
            source_type="NORMAL",
            source=plan,
            action=plan.action,
            source_object_id=plan.plan_id,
            snapshot_id=plan.snapshot_id,
            quant_proposal_id=plan.quant_proposal_id,
            plan_id=plan.plan_id,
            symbol=str(plan.symbol),
            market=str(plan.market),
            trade_date=plan.trade_date,
            requested_pct=plan.initial_position_pct,
            requested_quantity=None,
            entry_price=(
                Decimal(str(plan.entry_zone.upper))
                if plan.entry_zone is not None
                else None
            ),
            valid_until=plan.valid_until,
            analysis_id=plan.analysis_id or event.analysis_id,
            candidate_id=event.candidate_id,
            now=now,
        )

    async def _benchmark(
        self,
        *,
        event: ExecutionOutboxEvent,
        source_type: str,
        source: Any,
        action: str,
        source_object_id: str,
        snapshot_id: str,
        quant_proposal_id: str,
        plan_id: str | None,
        symbol: str,
        market: str,
        trade_date,
        requested_pct: float | None,
        requested_quantity: int | None,
        entry_price: Decimal | None,
        valid_until: datetime | None,
        analysis_id: str | None,
        candidate_id: str | None,
        now: datetime | None,
    ) -> OrderIntent:
        now = now or datetime.utcnow()
        if market != "CN":
            raise OrderIntentRejected("automatic paper trading supports CN only")
        account_type = (
            "PAPER_QUANT" if source_type == "QUANT" else "PAPER_NORMAL"
        )
        account = (
            await self.accounts.get_account(event.account_id, user_id=event.user_id)
            if event.account_id
            else await self.accounts.get_user_account(event.user_id, account_type)
        )
        if account is None or account.account_type != account_type:
            raise OrderIntentRejected(f"{account_type} automatic account not found")
        snapshot_service = EvidenceSnapshotService(self.db)
        snapshot = await snapshot_service.get(snapshot_id, event.user_id)
        if snapshot is None or not snapshot_service.verify_integrity(snapshot):
            raise OrderIntentRejected("EvidenceSnapshot is missing or tampered")
        if (
            snapshot.symbol != symbol
            or snapshot.market != market
            or snapshot.trade_date != trade_date
        ):
            raise OrderIntentRejected("benchmark source and snapshot identity mismatch")
        resolved = await SnapshotDataResolver(self.db).resolve(
            snapshot.snapshot_id,
            user_id=event.user_id,
        )
        instrument = resolved.instruments[-1] if resolved.instruments else None
        price_evidence = resolved.prices[-1] if resolved.prices else None
        has_status, blocked = _snapshot_trading_status(
            price_evidence,
            instrument,
            action=action,
        )
        execution = await self.policies.execution_policy()
        risk_policy = await RiskPolicyRegistry(self.db).get_active()
        next_date = await self.calendar.next_open_date(trade_date)
        earliest, expires = await self.calendar.execution_window(
            earliest_date=next_date,
            validity_sessions=execution.validity_sessions,
        )
        if valid_until is not None:
            expires = min(expires, _naive(valid_until))
        if expires < earliest:
            raise OrderIntentRejected("benchmark source is expired before execution")
        position_raw = _without_id(
            await self.db["ag_paper_positions"].find_one(
                {
                    "account_id": account.account_id,
                    "market": "CN",
                    "symbol": symbol,
                }
            )
        )
        position = (
            PaperPosition.model_validate(position_raw)
            if position_raw
            else None
        )
        all_positions = [
            PaperPosition.model_validate(_without_id(item))
            for item in await self.db["ag_paper_positions"].find(
                {"account_id": account.account_id, "quantity": {"$gt": 0}}
            ).to_list(length=None)
        ]
        total_exposure = sum(
            (item.total_cost for item in all_positions),
            Decimal("0"),
        )
        duplicate = bool(
            await self.db["ag_paper_orders"].find_one(
                {
                    "account_id": account.account_id,
                    "symbol": symbol,
                    "side": "BUY" if action == "BUY" else "SELL",
                    "status": {"$in": sorted(ACTIVE_ORDER_STATUSES)},
                }
            )
        )
        requested_qty = requested_quantity
        if action in {"SELL", "REDUCE"} and requested_qty is None:
            requested_qty = position.available_quantity if position else 0
        decision = self.benchmark_gate.evaluate(
            source_type=source_type,
            source_object_id=source_object_id,
            account=account,
            action=action,
            requested_position_pct=requested_pct,
            requested_quantity=requested_qty,
            price=entry_price,
            current_quantity=position.quantity if position else 0,
            available_quantity=position.available_quantity if position else 0,
            current_position_value=position.total_cost if position else Decimal("0"),
            total_exposure_value=total_exposure,
            duplicate_active_order=duplicate,
            execution_date_available=True,
            trading_status_known=has_status,
            trading_blocked=blocked,
            max_single_position_pct=risk_policy.max_single_position_pct,
            max_total_exposure_pct=risk_policy.max_total_exposure_pct,
            cn_buy_lot_size=execution.cn_buy_lot_size,
            now=now,
        )
        await self._save_benchmark_decision(decision)
        if decision.status in {"REJECT", "SUSPEND"}:
            exception = (
                OrderIntentSuspended
                if decision.status == "SUSPEND"
                else OrderIntentRejected
            )
            raise exception(
                f"benchmark safety gate returned {decision.status}"
            )
        if not decision.approved_quantity:
            raise OrderIntentRejected("benchmark approved quantity is zero")
        return await self._create(
            event=event,
            account=account,
            source_type=(
                "QUANT_PROPOSAL" if source_type == "QUANT" else "NORMAL_PLAN"
            ),
            source_object_id=source_object_id,
            snapshot_id=snapshot_id,
            quant_proposal_id=quant_proposal_id,
            plan_id=plan_id,
            consensus_id=None,
            risk_decision_id=None,
            symbol=symbol,
            action=action,
            quantity=decision.approved_quantity,
            limit_price=entry_price if action == "BUY" else None,
            earliest=earliest,
            expires=expires,
            analysis_id=analysis_id,
            candidate_id=candidate_id,
            benchmark_only=True,
            consensus_approved=False,
            hard_risk_approved=False,
            execution_version=execution.version,
            matching_version=execution.matching_engine_version,
            fee_version=(await self.policies.fee_policy()).version,
            now=now,
        )

    async def _save_benchmark_decision(
        self,
        decision: BenchmarkExecutionDecision,
    ) -> None:
        identity = {
            "source_type": decision.source_type,
            "source_object_id": decision.source_object_id,
            "account_id": decision.account_id,
        }
        existing = _without_id(
            await self.db["ag_benchmark_execution_decisions"].find_one(identity)
        )
        if existing:
            stored = BenchmarkExecutionDecision.model_validate(existing)
            if stored.input_hash != decision.input_hash:
                raise OrderIntentConflictError(
                    "same benchmark identity has conflicting inputs"
                )
            return
        await self.db["ag_benchmark_execution_decisions"].insert_one(
            model_document(decision)
        )

    async def _create(
        self,
        *,
        event: ExecutionOutboxEvent,
        account,
        source_type: str,
        source_object_id: str,
        snapshot_id: str,
        quant_proposal_id: str | None,
        plan_id: str | None,
        consensus_id: str | None,
        risk_decision_id: str | None,
        symbol: str,
        action: str,
        quantity: int,
        limit_price: Decimal | None,
        earliest: datetime,
        expires: datetime,
        analysis_id: str | None,
        candidate_id: str | None,
        benchmark_only: bool,
        consensus_approved: bool,
        hard_risk_approved: bool,
        execution_version: str,
        matching_version: str,
        fee_version: str,
        now: datetime,
    ) -> OrderIntent:
        if action == "BUY" and limit_price is None:
            raise OrderIntentSuspended("BUY intent requires entry_zone upper bound")
        side = "BUY" if action == "BUY" else "SELL"
        order_type = "LIMIT" if action == "BUY" else "MARKET_ON_OPEN"
        key_payload = {
            "account_id": account.account_id,
            "source_type": source_type,
            "source_object_id": source_object_id,
            "side": side,
            "execution_policy_version": execution_version,
        }
        idempotency_key = paper_canonical_hash(key_payload)
        existing = _without_id(
            await self.collection.find_one({"idempotency_key": idempotency_key})
        )
        if existing:
            stored = OrderIntent.model_validate(existing)
            expected_static = {
                "account_id": account.account_id,
                "source_type": source_type,
                "source_object_id": source_object_id,
                "snapshot_id": snapshot_id,
                "quant_proposal_id": quant_proposal_id,
                "plan_id": plan_id,
                "consensus_id": consensus_id,
                "risk_decision_id": risk_decision_id,
                "symbol": symbol,
                "original_action": action,
                "quantity": quantity,
                "limit_price": limit_price,
                "earliest_execute_at": earliest,
                "expires_at": expires,
                "execution_policy_version": execution_version,
                "matching_engine_version": matching_version,
                "fee_policy_version": fee_version,
            }
            actual_static = {
                key: getattr(stored, key) for key in expected_static
            }
            if actual_static != expected_static:
                raise OrderIntentConflictError(
                    "same intent idempotency identity has different source content"
                )
            await self.audit.record(
                "ORDER_INTENT_REUSED",
                "existing immutable OrderIntent reused idempotently",
                user_id=event.user_id,
                account_id=account.account_id,
                account_type=account.account_type,
                intent_id=stored.intent_id,
                symbol=stored.symbol,
                source_type=stored.source_type,
                source_object_id=stored.source_object_id,
                snapshot_id=stored.snapshot_id,
                risk_decision_id=stored.risk_decision_id,
                now=now,
            )
            return stored
        payload = {
            "intent_id": str(
                uuid5(NAMESPACE_URL, f"alphaguard:intent:{idempotency_key}")
            ),
            "user_id": event.user_id,
            "account_id": account.account_id,
            "account_type": account.account_type,
            "source_type": source_type,
            "source_object_id": source_object_id,
            "analysis_id": analysis_id,
            "candidate_id": candidate_id,
            "snapshot_id": snapshot_id,
            "quant_proposal_id": quant_proposal_id,
            "plan_id": plan_id,
            "consensus_id": consensus_id,
            "risk_decision_id": risk_decision_id,
            "symbol": symbol,
            "market": "CN",
            "currency": "CNY",
            "original_action": action,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "limit_price": limit_price,
            "earliest_execute_at": earliest,
            "expires_at": expires,
            "execution_policy_version": execution_version,
            "matching_engine_version": matching_version,
            "fee_policy_version": fee_version,
            "account_state_snapshot_id": await self.accounts.account_state_hash(
                account.account_id
            ),
            "idempotency_key": idempotency_key,
            "created_at": now,
            "benchmark_only": benchmark_only,
            "consensus_approved": consensus_approved,
            "hard_risk_approved": hard_risk_approved,
            "execution_environment": "PAPER",
            "live_execution_allowed": False,
            "schema_version": PAPER_SCHEMA_VERSION,
        }
        payload["immutable_hash"] = paper_canonical_hash(
            payload,
            exclude={"intent_id", "immutable_hash", "created_at"},
        )
        intent = OrderIntent.model_validate(payload)
        await self.collection.insert_one(model_document(intent))
        await self.audit.record(
            "ORDER_INTENT_CREATED",
            "immutable internal paper OrderIntent created from eligible source",
            user_id=event.user_id,
            account_id=account.account_id,
            account_type=account.account_type,
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            source_type=intent.source_type,
            source_object_id=intent.source_object_id,
            snapshot_id=intent.snapshot_id,
            risk_decision_id=intent.risk_decision_id,
            now=now,
        )
        return intent
