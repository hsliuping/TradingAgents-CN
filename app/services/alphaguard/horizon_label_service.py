"""Deterministic adjusted-price horizon labels for evaluation subjects."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.adjusted_price_resolver import (
    AdjustedPriceBar,
    AdjustedPriceResolver,
    AdjustedPriceUnavailable,
)
from app.services.alphaguard.evaluation_audit_service import EvaluationAuditService
from app.services.alphaguard.evaluation_policy_registry import evaluation_policy
from app.services.alphaguard.evaluation_repository import EvaluationRepository
from app.services.alphaguard.paper_calendar_service import PaperTradingCalendarService
from tradingagents.alphaguard.evaluation_schemas import (
    HorizonLabel,
    evaluation_hash,
)


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(value)
    except Exception:
        return None
    return result if result > 0 else None


class HorizonLabelService:
    def __init__(self, db):
        self.db = db
        self.prices = AdjustedPriceResolver(db)
        self.calendar = PaperTradingCalendarService(db)
        self.repository = EvaluationRepository(db)
        self.audit = EvaluationAuditService(db)
        self.policy = evaluation_policy()

    async def calculate_all(
        self,
        subject,
        *,
        as_of_trade_date: date,
        evaluation_job_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[HorizonLabel]:
        labels: list[HorizonLabel] = []
        for anchor in self._anchors(subject):
            sessions = await self.calendar.open_dates(after=anchor[1])
            for horizon, offset in self.policy.horizons.items():
                end = sessions[offset - 1] if len(sessions) >= offset else None
                status = (
                    "MISSING_CALENDAR"
                    if end is None
                    else "PENDING"
                    if end > as_of_trade_date
                    else "READY"
                )
                label = await self._calculate(
                    subject,
                    horizon=horizon,
                    horizon_end=end,
                    maturity_status=status,
                    anchor=anchor,
                )
                stored, created = await self.repository.save_horizon_label(label)
                labels.append(stored)
                await self.audit.record(
                    {
                        "CALCULATED": "HORIZON_LABEL_CALCULATED",
                        "PENDING": "HORIZON_LABEL_PENDING",
                        "INSUFFICIENT_DATA": "HORIZON_LABEL_INSUFFICIENT_DATA",
                        "INVALID_SOURCE": "HORIZON_LABEL_INSUFFICIENT_DATA",
                    }[stored.status],
                    (
                        f"{horizon}/{stored.anchor_type} label "
                        f"{'created' if created else 'reused'} "
                        f"with status={stored.status}"
                    ),
                    evaluation_job_id=evaluation_job_id,
                    trace_id=trace_id,
                    subject_id=subject.subject_id,
                    source_object_id=subject.source_object_id,
                    snapshot_id=subject.snapshot_id,
                    analysis_id=subject.analysis_id,
                    symbol=subject.symbol,
                    user_id=subject.user_id,
                    decision_trade_date=subject.decision_trade_date,
                    horizon=horizon,
                    input_hash=stored.input_hash,
                )
        return labels

    def _anchors(self, subject) -> list[tuple[str, date, Decimal | None]]:
        anchors: list[tuple[str, date, Decimal | None]] = [
            ("DECISION_CLOSE", subject.decision_trade_date, None)
        ]
        if subject.subject_type in {"PAPER_FILL", "POSITION_EXIT"}:
            fill_date = subject.lineage_ids.get("fill_trade_date")
            fill_price = _decimal(subject.lineage_ids.get("fill_price"))
            if fill_date and fill_price:
                anchors.append(
                    ("ACTUAL_FILL", date.fromisoformat(fill_date), fill_price)
                )
        if subject.entry_zone is not None and subject.action == "BUY":
            # Still a price-path label, not an executable fill claim.
            anchors.append(
                (
                    "PLANNED_ENTRY",
                    subject.decision_trade_date,
                    Decimal(str(subject.entry_zone.upper)),
                )
            )
        return anchors

    async def _calculate(
        self,
        subject,
        *,
        horizon: str,
        horizon_end: date | None,
        maturity_status: str,
        anchor: tuple[str, date, Decimal | None],
    ) -> HorizonLabel:
        anchor_type, anchor_date, explicit_anchor = anchor
        base_payload = {
            "subject_id": subject.subject_id,
            "horizon": horizon,
            "anchor_type": anchor_type,
            "anchor_date": anchor_date,
            "horizon_end_date": horizon_end,
            "price_adjustment_mode": self.policy.required_price_adjustment_mode,
            "price_data_version": "unavailable",
            "calculation_version": self.policy.label_calculation_version,
        }
        if maturity_status == "MISSING_CALENDAR":
            return self._result(
                base_payload,
                status="INVALID_SOURCE",
                data_refs=[],
            )
        if maturity_status == "PENDING":
            return self._result(
                base_payload,
                status="PENDING",
                data_refs=[],
            )
        assert horizon_end is not None
        try:
            bars = await self.prices.series(
                symbol=subject.symbol,
                market=subject.market,
                start=anchor_date,
                end=horizon_end,
                required_mode=self.policy.required_price_adjustment_mode,
            )
            by_date = {bar.trade_date: bar for bar in bars}
            anchor_bar = by_date.get(anchor_date)
            end_bar = by_date.get(horizon_end)
            if anchor_type == "PLANNED_ENTRY":
                anchor_price = explicit_anchor
            else:
                anchor_price = anchor_bar.close if anchor_bar else None
            if anchor_price is None or end_bar is None:
                raise AdjustedPriceUnavailable(
                    "adjusted anchor or horizon close is missing"
                )
            path = [
                bar
                for bar in bars
                if anchor_date < bar.trade_date <= horizon_end
            ]
            if not path:
                raise AdjustedPriceUnavailable(
                    "adjusted future path is empty"
                )
            raw_return = end_bar.close / anchor_price - Decimal("1")
            aligned = (
                raw_return
                if subject.action == "BUY"
                else -raw_return
                if subject.action in {"SELL", "REDUCE"}
                else None
            )
            mfe = max(bar.high for bar in path) / anchor_price - Decimal("1")
            mae = min(bar.low for bar in path) / anchor_price - Decimal("1")
            entry_touched = None
            entry_first = None
            if subject.entry_zone is not None:
                lower = Decimal(str(subject.entry_zone.lower))
                upper = Decimal(str(subject.entry_zone.upper))
                touched = [
                    bar
                    for bar in path
                    if bar.low <= upper and bar.high >= lower
                ]
                entry_touched = bool(touched)
                entry_first = touched[0].trade_date if touched else None
            benchmark_return = None
            benchmark_refs: list[str] = []
            benchmark_mode = None
            benchmark_version = None
            try:
                benchmark = await self.prices.series(
                    symbol=self.policy.benchmark_symbol,
                    market=subject.market,
                    start=anchor_date,
                    end=horizon_end,
                    required_mode=self.policy.required_price_adjustment_mode,
                    allow_index_unadjusted_equivalent=True,
                )
                benchmark_by_date = {bar.trade_date: bar for bar in benchmark}
                benchmark_anchor = benchmark_by_date.get(anchor_date)
                benchmark_end = benchmark_by_date.get(horizon_end)
                if benchmark_anchor and benchmark_end:
                    benchmark_return = (
                        benchmark_end.close / benchmark_anchor.close - Decimal("1")
                    )
                    benchmark_refs = [bar.data_ref for bar in benchmark]
                    benchmark_mode = benchmark[0].adjustment_mode
                    benchmark_version = benchmark[0].data_version
            except AdjustedPriceUnavailable:
                pass
            base_payload.update(
                {
                    "anchor_price": anchor_price,
                    "execution_anchor_price": (
                        explicit_anchor if anchor_type == "ACTUAL_FILL" else None
                    ),
                    "horizon_close_price": end_bar.close,
                    "raw_forward_return": raw_return,
                    "action_aligned_return": aligned,
                    "benchmark_symbol": self.policy.benchmark_symbol,
                    "benchmark_price_adjustment_mode": benchmark_mode,
                    "benchmark_data_version": benchmark_version,
                    "benchmark_return": benchmark_return,
                    "relative_benchmark_return": (
                        raw_return - benchmark_return
                        if benchmark_return is not None
                        else None
                    ),
                    "industry_id": subject.lineage_ids.get("industry_id"),
                    "industry_price_adjustment_mode": None,
                    "industry_data_version": None,
                    "industry_unavailable_reason": (
                        "snapshot-time industry benchmark mapping/data unavailable"
                    ),
                    "industry_benchmark_return": None,
                    "relative_industry_return": None,
                    "mfe": mfe,
                    "mae": mae,
                    "entry_zone_touched": entry_touched,
                    "entry_first_touch_date": entry_first,
                    "data_refs": sorted(
                        set([bar.data_ref for bar in bars] + benchmark_refs)
                    ),
                    "price_data_version": bars[0].data_version,
                    "calculated_at": datetime.utcnow(),
                }
            )
            return self._result(base_payload, status="CALCULATED")
        except (AdjustedPriceUnavailable, ValueError, ArithmeticError):
            return self._result(
                base_payload,
                status="INSUFFICIENT_DATA",
                data_refs=[],
            )

    @staticmethod
    def _result(
        payload: dict,
        *,
        status: str,
        data_refs: list[str] | None = None,
    ) -> HorizonLabel:
        full = {
            **payload,
            "status": status,
            "data_refs": data_refs if data_refs is not None else payload.get("data_refs", []),
        }
        input_hash = evaluation_hash(
            full,
            exclude={"input_hash", "label_id", "calculated_at"},
        )
        label_id = str(
            uuid5(
                NAMESPACE_URL,
                "alphaguard:label:"
                f"{full['subject_id']}:{full['horizon']}:{full['anchor_type']}:"
                f"{full['calculation_version']}",
            )
        )
        return HorizonLabel(
            label_id=label_id,
            input_hash=input_hash,
            **full,
        )
