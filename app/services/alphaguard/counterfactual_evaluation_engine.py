"""Evaluation-only counterfactuals with zero production side effects."""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal, ROUND_FLOOR
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.evaluation_audit_service import EvaluationAuditService
from app.services.alphaguard.evaluation_policy_registry import evaluation_policy
from app.services.alphaguard.evaluation_repository import EvaluationRepository
from app.services.alphaguard.fee_engine import FeeEngine
from app.services.alphaguard.matching_engine import MatchingEngine
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from app.services.alphaguard.paper_storage import clean_document, mongo_date
from tradingagents.alphaguard.evaluation_schemas import (
    CounterfactualEvaluation,
    evaluation_hash,
)
from tradingagents.alphaguard.paper_schemas import (
    ExecutionMarketSnapshot,
    PaperOrder,
)


class CounterfactualEvaluationEngine:
    """Reuses pure match/fee algorithms but persists only ag_eval_* objects."""

    def __init__(self, db):
        self.db = db
        self.repository = EvaluationRepository(db)
        self.audit = EvaluationAuditService(db)
        self.policies = PaperPolicyRegistry(db)
        self.matcher = MatchingEngine()
        self.policy = evaluation_policy()

    async def evaluate(
        self,
        subject,
        labels: list,
        *,
        evaluation_job_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[CounterfactualEvaluation]:
        results = [
            await self._signal_only(subject, labels),
        ]
        if subject.action in {"BUY", "SELL", "REDUCE"}:
            results.append(await self._executable_shadow(subject, labels))
        if subject.action in {"SELL", "REDUCE"} and subject.actual_execution_exists:
            results.append(await self._continue_holding(subject, labels))
        stored_results: list[CounterfactualEvaluation] = []
        for result in results:
            stored, _ = await self.repository.save_counterfactual(result)
            stored_results.append(stored)
            await self.audit.record(
                (
                    "COUNTERFACTUAL_COMPLETED"
                    if stored.status in {"CALCULATED", "FILLED", "PARTIALLY_FILLED"}
                    else "COUNTERFACTUAL_NO_FILL"
                    if stored.status == "NO_FILL"
                    else "COUNTERFACTUAL_FAILED"
                    if stored.status == "FAILED"
                    else "COUNTERFACTUAL_STARTED"
                ),
                f"{stored.mode} counterfactual status={stored.status}",
                evaluation_job_id=evaluation_job_id,
                trace_id=trace_id,
                subject_id=subject.subject_id,
                source_object_id=subject.source_object_id,
                snapshot_id=subject.snapshot_id,
                analysis_id=subject.analysis_id,
                user_id=subject.user_id,
                symbol=subject.symbol,
                decision_trade_date=subject.decision_trade_date,
                input_hash=stored.input_hash,
            )
        return stored_results

    async def _signal_only(self, subject, labels) -> CounterfactualEvaluation:
        primary = next(
            (
                label
                for label in labels
                if label.horizon == self.policy.primary_attribution_horizon
                and label.anchor_type == "DECISION_CLOSE"
            ),
            None,
        )
        status = (
            "CALCULATED"
            if primary and primary.status == "CALCULATED"
            else "PENDING"
            if primary and primary.status == "PENDING"
            else "INSUFFICIENT_DATA"
        )
        notional = Decimal(self.policy.normalized_shadow_notional)
        aligned = (
            primary.action_aligned_return
            if primary and primary.status == "CALCULATED"
            else None
        )
        return self._result(
            subject,
            mode="SIGNAL_ONLY",
            status=status,
            normalized_notional=notional,
            gross_pnl=(notional * aligned if aligned is not None else None),
            fees=Decimal("0") if aligned is not None else None,
            net_pnl=(notional * aligned if aligned is not None else None),
            return_pct=aligned,
            max_adverse_excursion=(
                primary.mae if primary and primary.status == "CALCULATED" else None
            ),
            max_favorable_excursion=(
                primary.mfe if primary and primary.status == "CALCULATED" else None
            ),
            input_refs=(
                primary.data_refs if primary and primary.status == "CALCULATED" else []
            ),
            matching_version=self.matcher.version,
            fee_version="not-applicable",
        )

    async def _executable_shadow(self, subject, labels) -> CounterfactualEvaluation:
        if subject.market != "CN":
            return self._result(
                subject,
                mode="EXECUTABLE_SHADOW",
                status="NOT_ELIGIBLE",
                fee_version="unavailable",
                matching_version=self.matcher.version,
            )
        if subject.action == "BUY" and subject.entry_zone is None:
            return self._result(
                subject,
                mode="EXECUTABLE_SHADOW",
                status="NOT_ELIGIBLE",
                fee_version="unavailable",
                matching_version=self.matcher.version,
            )
        primary = next(
            (
                item
                for item in labels
                if item.horizon == self.policy.primary_attribution_horizon
                and item.anchor_type == "DECISION_CLOSE"
            ),
            None,
        )
        if primary is None or primary.status == "PENDING":
            return self._result(
                subject,
                mode="EXECUTABLE_SHADOW",
                status="PENDING",
                fee_version="unavailable",
                matching_version=self.matcher.version,
            )
        if primary.status != "CALCULATED" or primary.horizon_end_date is None:
            return self._result(
                subject,
                mode="EXECUTABLE_SHADOW",
                status="INSUFFICIENT_DATA",
                fee_version="unavailable",
                matching_version=self.matcher.version,
            )
        try:
            execution_policy = await self.policies.execution_policy()
            fee_policy = await self.policies.fee_policy()
        except (LookupError, ValueError):
            return self._result(
                subject,
                mode="EXECUTABLE_SHADOW",
                status="INSUFFICIENT_DATA",
                fee_version="unavailable",
                matching_version=self.matcher.version,
            )
        raw_snapshots = await self.db["ag_execution_market_snapshots"].find(
            {"symbol": subject.symbol, "market": "CN"}
        ).to_list(length=None)
        snapshots = []
        for item in raw_snapshots:
            snapshot = ExecutionMarketSnapshot.model_validate(
                clean_document(item)
            )
            if (
                subject.decision_trade_date
                < snapshot.trade_date
                <= primary.horizon_end_date
            ):
                snapshots.append(snapshot)
        snapshots.sort(key=lambda item: item.trade_date)
        if (
            not snapshots
            or snapshots[-1].trade_date != primary.horizon_end_date
        ):
            return self._result(
                subject,
                mode="EXECUTABLE_SHADOW",
                status="INSUFFICIENT_DATA",
                fee_version=fee_policy.version,
                matching_version=execution_policy.matching_engine_version,
            )
        limit_price = (
            Decimal(str(subject.entry_zone.upper))
            if subject.action == "BUY" and subject.entry_zone is not None
            else None
        )
        reference = limit_price or snapshots[0].open
        notional = Decimal(self.policy.normalized_shadow_notional)
        quantity = int(
            (notional / reference).to_integral_value(rounding=ROUND_FLOOR)
        )
        if subject.action == "BUY":
            quantity = (
                quantity // execution_policy.cn_buy_lot_size
                * execution_policy.cn_buy_lot_size
            )
        if quantity <= 0:
            return self._result(
                subject,
                mode="EXECUTABLE_SHADOW",
                status="NOT_ELIGIBLE",
                normalized_notional=notional,
                fee_version=fee_policy.version,
                matching_version=execution_policy.matching_engine_version,
            )
        side = "BUY" if subject.action == "BUY" else "SELL"
        order = PaperOrder(
            order_id=f"shadow:{subject.subject_id}",
            intent_id=f"shadow:{subject.subject_id}",
            account_id="evaluation-shadow-account",
            user_id=subject.user_id,
            account_type="PAPER_QUANT",
            candidate_id=subject.candidate_id,
            source_type="EVALUATION_SHADOW",
            source_object_id=subject.source_object_id,
            symbol=subject.symbol,
            side=side,
            original_action=subject.action,
            order_type="LIMIT" if side == "BUY" else "MARKET_ON_OPEN",
            requested_quantity=quantity,
            reserved_quantity=quantity,
            filled_quantity=0,
            remaining_quantity=quantity,
            limit_price=limit_price,
            status="PENDING",
            trade_date=snapshots[0].trade_date,
            earliest_execute_at=datetime.combine(snapshots[0].trade_date, time(9, 30)),
            expires_at=datetime.combine(
                primary.horizon_end_date,
                time(15, 0),
            ),
            created_at=datetime.combine(subject.decision_trade_date, time(15, 1)),
            updated_at=datetime.combine(subject.decision_trade_date, time(15, 1)),
        )
        fills: list[dict] = []
        fee_total = Decimal("0")
        gross_total = Decimal("0")
        filled_notional = Decimal("0")
        remaining = quantity
        shadow_order = order
        matched_snapshots: list[ExecutionMarketSnapshot] = []
        for snapshot in snapshots:
            result = self.matcher.match(
                order=shadow_order,
                snapshot=snapshot,
                policy=execution_policy,
                valid_reserved_quantity=remaining,
                matched_at=datetime.combine(snapshot.trade_date, time(15, 0)),
            )
            if result.status in {"FULL_FILL", "PARTIAL_FILL"}:
                assert result.price is not None
                fees = FeeEngine.calculate(
                    side=side,
                    notional=result.price * result.quantity,
                    policy=fee_policy,
                )
                fill_notional = result.price * result.quantity
                fills.append(
                    {
                        "trade_date": snapshot.trade_date,
                        "quantity": result.quantity,
                        "price": result.price,
                        "notional": fill_notional,
                        "fee_breakdown": fees.model_dump(mode="python"),
                        "execution_snapshot_id": snapshot.execution_snapshot_id,
                        "evaluation_only": True,
                    }
                )
                matched_snapshots.append(snapshot)
                fee_total += fees.total_fee
                filled_notional += fill_notional
                gross_total += (
                    (snapshots[-1].close - result.price) * result.quantity
                    if side == "BUY"
                    else (result.price - snapshots[-1].close) * result.quantity
                )
                remaining -= result.quantity
                if remaining == 0:
                    break
                shadow_order = shadow_order.model_copy(
                    update={
                        "filled_quantity": quantity - remaining,
                        "remaining_quantity": remaining,
                        "reserved_quantity": remaining,
                        "status": "PARTIALLY_FILLED",
                        "last_matched_trade_date": snapshot.trade_date,
                        "updated_at": datetime.combine(
                            snapshot.trade_date, time(15, 0)
                        ),
                    }
                )
        if not fills:
            return self._result(
                subject,
                mode="EXECUTABLE_SHADOW",
                status="NO_FILL",
                normalized_notional=notional,
                hypothetical_order=order.model_dump(mode="python"),
                fee_version=fee_policy.version,
                matching_version=execution_policy.matching_engine_version,
                input_refs=[item.execution_snapshot_id for item in snapshots],
            )
        average_fill_price = filled_notional / sum(
            int(item["quantity"]) for item in fills
        )
        first_match_date = matched_snapshots[0].trade_date
        post_fill_snapshots = [
            item for item in snapshots if item.trade_date >= first_match_date
        ]
        adverse = min(
            (
                item.low / average_fill_price - Decimal("1")
                if side == "BUY"
                else average_fill_price / item.high - Decimal("1")
            )
            for item in post_fill_snapshots
        )
        favorable = max(
            (
                item.high / average_fill_price - Decimal("1")
                if side == "BUY"
                else average_fill_price / item.low - Decimal("1")
            )
            for item in post_fill_snapshots
        )
        return self._result(
            subject,
            mode="EXECUTABLE_SHADOW",
            status=(
                "FILLED" if remaining == 0 else "PARTIALLY_FILLED"
            ),
            normalized_notional=notional,
            hypothetical_intent={
                "source_object_id": subject.source_object_id,
                "side": side,
                "quantity": quantity,
                "evaluation_only": True,
                "production_collection_write": False,
            },
            hypothetical_order=order.model_dump(mode="python"),
            hypothetical_fills=fills,
            gross_pnl=gross_total,
            fees=fee_total,
            net_pnl=gross_total - fee_total,
            return_pct=(
                (gross_total - fee_total) / filled_notional
                if filled_notional > 0
                else None
            ),
            max_adverse_excursion=adverse,
            max_favorable_excursion=favorable,
            fee_version=fee_policy.version,
            matching_version=execution_policy.matching_engine_version,
            input_refs=[item.execution_snapshot_id for item in snapshots],
        )

    async def _continue_holding(self, subject, labels) -> CounterfactualEvaluation:
        primary = next(
            (
                item
                for item in labels
                if item.horizon == self.policy.primary_attribution_horizon
                and item.anchor_type == "ACTUAL_FILL"
            ),
            None,
        )
        if primary is None or primary.status == "PENDING":
            return self._result(
                subject,
                mode="CONTINUE_HOLDING",
                status="PENDING",
                fee_version="actual-fill",
                matching_version="actual-fill",
            )
        if (
            primary.status != "CALCULATED"
            or primary.execution_anchor_price is None
            or primary.horizon_end_date is None
        ):
            return self._result(
                subject,
                mode="CONTINUE_HOLDING",
                status="INSUFFICIENT_DATA",
                fee_version="actual-fill",
                matching_version="actual-fill",
            )
        quantity = int(subject.lineage_ids.get("fill_quantity") or 0)
        if quantity <= 0:
            return self._result(
                subject,
                mode="CONTINUE_HOLDING",
                status="INSUFFICIENT_DATA",
                fee_version="actual-fill",
                matching_version="actual-fill",
            )
        fill_raw = clean_document(
            await self.db["ag_paper_fills"].find_one(
                {"fill_id": subject.lineage_ids.get("fill_id")}
            )
        )
        if fill_raw is None:
            return self._result(
                subject,
                mode="CONTINUE_HOLDING",
                status="INSUFFICIENT_DATA",
                fee_version="actual-fill",
                matching_version="actual-fill",
            )
        raw_horizon_snapshot = clean_document(
            await self.db["ag_execution_market_snapshots"].find_one(
                {
                    "symbol": subject.symbol,
                    "market": subject.market,
                    "trade_date": {
                        "$in": [
                            mongo_date(primary.horizon_end_date),
                            primary.horizon_end_date.isoformat(),
                        ]
                    },
                }
            )
        )
        if raw_horizon_snapshot is None:
            return self._result(
                subject,
                mode="CONTINUE_HOLDING",
                status="INSUFFICIENT_DATA",
                fee_version=str(fill_raw.get("fee_policy_version") or "actual-fill"),
                matching_version=str(
                    fill_raw.get("matching_engine_version") or "actual-fill"
                ),
            )
        horizon_snapshot = ExecutionMarketSnapshot.model_validate(
            raw_horizon_snapshot
        )
        fees = Decimal(str(fill_raw["fee_breakdown"]["total_fee"]))
        gross = (
            primary.execution_anchor_price - horizon_snapshot.close
        ) * quantity
        notional = primary.execution_anchor_price * quantity
        return self._result(
            subject,
            mode="CONTINUE_HOLDING",
            status="CALCULATED",
            normalized_notional=notional,
            gross_pnl=gross,
            fees=fees,
            net_pnl=gross - fees,
            return_pct=(gross - fees) / notional if notional > 0 else None,
            max_adverse_excursion=primary.mae,
            max_favorable_excursion=primary.mfe,
            fee_version=(
                str(fill_raw.get("fee_policy_version"))
                if fill_raw
                else "actual-fill"
            ),
            matching_version=(
                str(fill_raw.get("matching_engine_version"))
                if fill_raw
                else "actual-fill"
            ),
            input_refs=primary.data_refs
            + [horizon_snapshot.execution_snapshot_id],
        )

    def _result(
        self,
        subject,
        *,
        mode: str,
        status: str,
        fee_version: str,
        matching_version: str,
        normalized_notional: Decimal | None = None,
        hypothetical_intent: dict | None = None,
        hypothetical_order: dict | None = None,
        hypothetical_fills: list[dict] | None = None,
        gross_pnl: Decimal | None = None,
        fees: Decimal | None = None,
        net_pnl: Decimal | None = None,
        return_pct: Decimal | None = None,
        max_adverse_excursion: Decimal | None = None,
        max_favorable_excursion: Decimal | None = None,
        input_refs: list[str] | None = None,
    ) -> CounterfactualEvaluation:
        payload = {
            "subject_id": subject.subject_id,
            "mode": mode,
            "source_stage": subject.decision_stage,
            "comparison_stage": None,
            "status": status,
            "shadow_account_basis_id": (
                "normalized-notional-v1" if normalized_notional is not None else None
            ),
            "normalized_notional": normalized_notional,
            "hypothetical_intent": hypothetical_intent,
            "hypothetical_order": hypothetical_order,
            "hypothetical_fills": hypothetical_fills or [],
            "gross_pnl": gross_pnl,
            "fees": fees,
            "net_pnl": net_pnl,
            "return_pct": return_pct,
            "max_adverse_excursion": max_adverse_excursion,
            "max_favorable_excursion": max_favorable_excursion,
            "execution_rule_version": self.policy.counterfactual_version,
            "fee_version": fee_version,
            "matching_version": matching_version,
            "input_refs": sorted(set(input_refs or [])),
        }
        payload["input_hash"] = evaluation_hash(payload)
        return CounterfactualEvaluation(
            counterfactual_id=str(
                uuid5(
                    NAMESPACE_URL,
                    "alphaguard:counterfactual:"
                    f"{subject.subject_id}:{mode}:{self.policy.counterfactual_version}",
                )
            ),
            created_at=datetime.utcnow(),
            **payload,
        )
