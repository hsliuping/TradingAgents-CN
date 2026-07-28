"""Mature only canonical backfill labels backed by persisted completed QFQ."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from app.services.alphaguard.horizon_label_service import HorizonLabelService
from app.services.alphaguard.adjusted_price_resolver import (
    AdjustedPriceUnavailable,
)
from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.evaluation_schemas import EvaluationSubject


class BackfillLabelMaturityError(RuntimeError):
    pass


def _business_timestamp(value: date, *, hour: int = 0) -> datetime:
    return datetime.combine(value, time(hour=hour))


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


class BackfillLabelMaturityService:
    def __init__(self, db):
        self.db = db
        self.labels = HorizonLabelService(db)

    async def _formal_price(
        self,
        *,
        symbol: str,
        trade_date: date,
        as_of_at: datetime,
        allow_index: bool = False,
    ) -> dict[str, Any] | None:
        modes = (
            ["QFQ", "INDEX_UNADJUSTED_EQUIVALENT"]
            if allow_index
            else ["QFQ"]
        )
        rows = await self.db["stock_daily_quotes"].find(
            {
                "symbol": symbol,
                "market": "CN",
                "period": "daily",
                "trade_date": _business_timestamp(trade_date),
                "price_adjustment_mode": {"$in": modes},
                "available_at": {"$lte": as_of_at},
                "collected_at": {"$lte": as_of_at},
            }
        ).to_list(length=2)
        if len(rows) != 1:
            return None
        row = clean_document(rows[0])
        required = (
            "adjusted_open",
            "adjusted_high",
            "adjusted_low",
            "adjusted_close",
            "price_data_version",
            "content_hash",
            "ref_id",
            "collected_at",
        )
        if any(row.get(field) in (None, "") for field in required):
            return None
        return row

    async def plan(
        self,
        *,
        backfill_run_id: str,
        as_of_trade_date: date,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now()
        if as_of_trade_date > now.date():
            raise BackfillLabelMaturityError(
                "evaluation as-of date cannot be in the future"
            )
        if (
            as_of_trade_date == now.date()
            and now.time() < time(15, 0)
        ):
            raise BackfillLabelMaturityError(
                "current trading day has not completed; labels remain PENDING"
            )
        subjects_raw = await self.db["ag_eval_subjects"].find(
            {"lineage_ids.backfill_run_id": backfill_run_id}
        ).to_list(length=None)
        subjects = {
            str(item["subject_id"]): EvaluationSubject.model_validate(
                clean_document(item)
            )
            for item in subjects_raw
        }
        if not subjects:
            raise BackfillLabelMaturityError(
                "canonical backfill has no EvaluationSubject rows"
            )
        pending = await self.db["ag_eval_horizon_labels"].find(
            {
                "subject_id": {"$in": sorted(subjects)},
                "horizon": "20D",
                "anchor_type": "DECISION_CLOSE",
                "status": "PENDING",
            }
        ).to_list(length=None)
        pending.sort(key=lambda item: str(item["label_id"]))
        blockers = []
        ready_subject_ids = []
        source_refs = set()
        as_of_at = _business_timestamp(as_of_trade_date, hour=23)
        for raw in pending:
            label = clean_document(raw)
            horizon_end = _as_date(label.get("horizon_end_date"))
            subject = subjects[str(label["subject_id"])]
            if horizon_end is None:
                blockers.append(
                    {
                        "label_id": label["label_id"],
                        "reason": "MISSING_HORIZON_END_DATE",
                    }
                )
                continue
            if horizon_end > as_of_trade_date:
                blockers.append(
                    {
                        "label_id": label["label_id"],
                        "reason": "HORIZON_NOT_MATURE",
                        "horizon_end_date": horizon_end,
                    }
                )
                continue
            price = await self._formal_price(
                symbol=subject.symbol,
                trade_date=horizon_end,
                as_of_at=as_of_at,
            )
            benchmark = await self._formal_price(
                symbol="000300",
                trade_date=horizon_end,
                as_of_at=as_of_at,
                allow_index=True,
            )
            if price is None or benchmark is None:
                blockers.append(
                    {
                        "label_id": label["label_id"],
                        "symbol": subject.symbol,
                        "horizon_end_date": horizon_end,
                        "reason": (
                            "FORMAL_QFQ_MISSING"
                            if price is None
                            else "FORMAL_BENCHMARK_MISSING"
                        ),
                    }
                )
                continue
            try:
                price_series = await self.labels.prices.series(
                    symbol=subject.symbol,
                    market=subject.market,
                    start=subject.decision_trade_date,
                    end=horizon_end,
                    required_mode=self.labels.policy.required_price_adjustment_mode,
                )
                benchmark_series = await self.labels.prices.series(
                    symbol=self.labels.policy.benchmark_symbol,
                    market=subject.market,
                    start=subject.decision_trade_date,
                    end=horizon_end,
                    required_mode=self.labels.policy.required_price_adjustment_mode,
                    allow_index_unadjusted_equivalent=True,
                )
                price_dates = {item.trade_date for item in price_series}
                benchmark_dates = {item.trade_date for item in benchmark_series}
                required_dates = {subject.decision_trade_date, horizon_end}
                if not required_dates.issubset(price_dates) or not required_dates.issubset(
                    benchmark_dates
                ):
                    raise AdjustedPriceUnavailable(
                        "version-locked series lacks anchor or horizon date"
                    )
            except AdjustedPriceUnavailable as exc:
                blockers.append(
                    {
                        "label_id": label["label_id"],
                        "symbol": subject.symbol,
                        "horizon_end_date": horizon_end,
                        "reason": "VERSION_LOCKED_QFQ_SERIES_UNAVAILABLE",
                        "detail": str(exc),
                    }
                )
                continue
            ready_subject_ids.append(subject.subject_id)
            source_refs.update(
                {
                    f"stock_daily_quotes:{price['ref_id']}",
                    f"stock_daily_quotes:{benchmark['ref_id']}",
                }
            )
        terminal_before = {
            str(item["label_id"]): str(item["input_hash"])
            for item in await self.db["ag_eval_horizon_labels"].find(
                {
                    "subject_id": {"$in": sorted(subjects)},
                    "status": {"$ne": "PENDING"},
                }
            ).to_list(length=None)
        }
        return {
            "backfill_run_id": backfill_run_id,
            "as_of_trade_date": as_of_trade_date,
            "canonical_subject_count": len(subjects),
            "pending_20d_count": len(pending),
            "ready_20d_count": len(ready_subject_ids),
            "blocked_20d_count": len(blockers),
            "ready_subject_ids": sorted(set(ready_subject_ids)),
            "blockers": blockers,
            "source_refs": sorted(source_refs),
            "terminal_label_hashes_before": terminal_before,
        }

    async def recover_invalid_incomplete_to_pending(
        self,
        *,
        backfill_run_id: str,
        as_of_trade_date: date,
        execute: bool,
    ) -> dict[str, Any]:
        """Recover only labels terminalized by the incomplete preflight bug.

        The repair is intentionally narrower than a general terminal-label
        update: it accepts only canonical 20D DECISION_CLOSE labels whose
        current INSUFFICIENT_DATA content exactly matches a deterministic
        recalculation with an unavailable version-locked price series.
        """

        subjects_raw = await self.db["ag_eval_subjects"].find(
            {"lineage_ids.backfill_run_id": backfill_run_id}
        ).to_list(length=None)
        subjects = {
            str(item["subject_id"]): EvaluationSubject.model_validate(
                clean_document(item)
            )
            for item in subjects_raw
        }
        rows = await self.db["ag_eval_horizon_labels"].find(
            {
                "subject_id": {"$in": sorted(subjects)},
                "horizon": "20D",
                "anchor_type": "DECISION_CLOSE",
                "status": "INSUFFICIENT_DATA",
            }
        ).to_list(length=None)
        repairs = []
        for raw in sorted(rows, key=lambda item: str(item["label_id"])):
            stored = clean_document(raw)
            if (
                stored.get("price_data_version") != "unavailable"
                or list(stored.get("data_refs") or []) != []
            ):
                continue
            subject = subjects[str(stored["subject_id"])]
            horizon_end = _as_date(stored.get("horizon_end_date"))
            if horizon_end is None or horizon_end > as_of_trade_date:
                raise BackfillLabelMaturityError(
                    "invalid incomplete label has an unexpected horizon end"
                )
            anchor = (
                "DECISION_CLOSE",
                subject.decision_trade_date,
                None,
            )
            recalculated = await self.labels._calculate(
                subject,
                horizon="20D",
                horizon_end=horizon_end,
                maturity_status="READY",
                anchor=anchor,
            )
            if (
                recalculated.status != "INSUFFICIENT_DATA"
                or recalculated.input_hash != stored.get("input_hash")
            ):
                raise BackfillLabelMaturityError(
                    "invalid incomplete label no longer matches deterministic "
                    "recalculation"
                )
            pending = await self.labels._calculate(
                subject,
                horizon="20D",
                horizon_end=horizon_end,
                maturity_status="PENDING",
                anchor=anchor,
            )
            repairs.append(
                {
                    "label_id": stored["label_id"],
                    "subject_id": subject.subject_id,
                    "from_input_hash": stored["input_hash"],
                    "to_input_hash": pending.input_hash,
                    "pending": pending,
                }
            )
        if execute:
            for repair in repairs:
                result = await self.db["ag_eval_horizon_labels"].replace_one(
                    {
                        "label_id": repair["label_id"],
                        "status": "INSUFFICIENT_DATA",
                        "input_hash": repair["from_input_hash"],
                    },
                    model_document(repair["pending"]),
                )
                if result.modified_count != 1:
                    raise BackfillLabelMaturityError(
                        "invalid incomplete label recovery lost compare-and-set"
                    )
                await self.labels.audit.record(
                    "HORIZON_LABEL_RECOVERED_PENDING",
                    "20D label restored to PENDING after version-lock "
                    "preflight defect",
                    trace_id=(
                        f"backfill-label-recovery:{backfill_run_id}"
                    ),
                    subject_id=repair["subject_id"],
                    horizon="20D",
                    input_hash=repair["to_input_hash"],
                )
        return {
            "backfill_run_id": backfill_run_id,
            "as_of_trade_date": as_of_trade_date,
            "write": execute,
            "eligible_recovery_count": len(repairs),
            "recovered_pending_count": len(repairs) if execute else 0,
            "label_ids": [item["label_id"] for item in repairs],
        }

    async def mature(
        self,
        *,
        backfill_run_id: str,
        as_of_trade_date: date,
        execute: bool,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        plan = await self.plan(
            backfill_run_id=backfill_run_id,
            as_of_trade_date=as_of_trade_date,
            now=now,
        )
        if not execute:
            return {**plan, "write": False, "matured_20d_count": 0}
        if plan["blocked_20d_count"]:
            raise BackfillLabelMaturityError(
                "one or more pending labels lack completed persisted QFQ"
            )
        if not plan["ready_subject_ids"]:
            return {**plan, "write": True, "matured_20d_count": 0}
        subjects_raw = await self.db["ag_eval_subjects"].find(
            {"subject_id": {"$in": plan["ready_subject_ids"]}}
        ).to_list(length=None)
        for raw in sorted(subjects_raw, key=lambda item: str(item["subject_id"])):
            subject = EvaluationSubject.model_validate(clean_document(raw))
            await self.labels.calculate_all(
                subject,
                as_of_trade_date=as_of_trade_date,
                trace_id=f"backfill-label-maturity:{backfill_run_id}",
            )
        remaining = await self.db["ag_eval_horizon_labels"].count_documents(
            {
                "subject_id": {"$in": plan["ready_subject_ids"]},
                "horizon": "20D",
                "anchor_type": "DECISION_CLOSE",
                "status": "PENDING",
            }
        )
        if remaining:
            raise BackfillLabelMaturityError(
                "eligible 20D labels remained PENDING after calculation"
            )
        terminal_after = {
            str(item["label_id"]): str(item["input_hash"])
            for item in await self.db["ag_eval_horizon_labels"].find(
                {
                    "subject_id": {
                        "$in": list(
                            {
                                str(item["subject_id"])
                                for item in await self.db["ag_eval_subjects"].find(
                                    {
                                        "lineage_ids.backfill_run_id": backfill_run_id
                                    }
                                ).to_list(length=None)
                            }
                        )
                    },
                    "status": {"$ne": "PENDING"},
                }
            ).to_list(length=None)
        }
        changed_terminal = {
            label_id
            for label_id, input_hash in plan["terminal_label_hashes_before"].items()
            if terminal_after.get(label_id) != input_hash
        }
        if changed_terminal:
            raise BackfillLabelMaturityError(
                "a previously mature HorizonLabel changed unexpectedly"
            )
        return {
            **plan,
            "write": True,
            "matured_20d_count": len(plan["ready_subject_ids"]),
            "previously_mature_labels_changed": 0,
        }
