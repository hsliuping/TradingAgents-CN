"""Decimal account metrics from immutable PR-006 facts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.evaluation_audit_service import EvaluationAuditService
from app.services.alphaguard.evaluation_policy_registry import evaluation_policy
from app.services.alphaguard.evaluation_repository import EvaluationRepository
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.evaluation_schemas import (
    AccountPerformanceMetric,
    evaluation_hash,
)


def _record_date(record: dict, *fields: str) -> date | None:
    """Return the first trustworthy persisted business timestamp/date."""

    for field in fields:
        value = record.get(field)
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                continue
    return None


class AccountMetricService:
    def __init__(self, db):
        self.db = db
        self.repository = EvaluationRepository(db)
        self.audit = EvaluationAuditService(db)
        self.version = evaluation_policy().account_metric_version

    async def calculate_all(
        self,
        *,
        period_start: date,
        period_end: date,
        user_id: str | None = None,
        evaluation_job_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[AccountPerformanceMetric]:
        query = {"user_id": str(user_id)} if user_id is not None else {}
        accounts = await self.db["ag_paper_accounts"].find(query).to_list(length=None)
        results = []
        for raw in accounts:
            account = clean_document(raw)
            metric = await self.calculate(
                account,
                period_start=period_start,
                period_end=period_end,
            )
            stored, _ = await self.repository.save_immutable(
                "account_metrics",
                metric,
                identity={
                    "account_id": metric.account_id,
                    "period_start": metric.period_start,
                    "period_end": metric.period_end,
                    "metric_version": metric.metric_version,
                },
            )
            results.append(stored)
            await self.audit.record(
                (
                    "ACCOUNT_METRIC_CALCULATED"
                    if stored.status == "CALCULATED"
                    else "ACCOUNT_METRIC_INCOMPLETE"
                ),
                f"account metric status={stored.status}",
                evaluation_job_id=evaluation_job_id,
                trace_id=trace_id,
                account_id=stored.account_id,
                user_id=str(account.get("user_id") or ""),
                input_hash=stored.input_hash,
            )
        return results

    async def calculate(
        self,
        account: dict,
        *,
        period_start: date,
        period_end: date,
    ) -> AccountPerformanceMetric:
        account_id = str(account["account_id"])
        raw_snapshots = await self.db["ag_paper_account_snapshots"].find(
            {"account_id": account_id}
        ).to_list(length=None)
        snapshots = [
            clean_document(item)
            for item in raw_snapshots
            if period_start <= item["trade_date"] <= period_end
        ]
        snapshots.sort(key=lambda item: item["trade_date"])
        fills = [
            clean_document(item)
            for item in await self.db["ag_paper_fills"].find(
                {"account_id": account_id}
            ).to_list(length=None)
            if period_start <= item["trade_date"] <= period_end
        ]
        orders = [
            clean_document(item)
            for item in await self.db["ag_paper_orders"].find(
                {"account_id": account_id}
            ).to_list(length=None)
            if (
                (order_date := _record_date(
                    item,
                    "filled_at",
                    "last_matched_trade_date",
                    "trade_date",
                    "updated_at",
                    "created_at",
                ))
                is not None
                and period_start <= order_date <= period_end
            )
        ]
        settlements = [
            clean_document(item)
            for item in await self.db["ag_settlement_records"].find(
                {"account_id": account_id, "status": "COMMITTED"}
            ).to_list(length=None)
            if (
                (settlement_date := _record_date(
                    item,
                    "committed_at",
                    "updated_at",
                    "created_at",
                ))
                is not None
                and period_start <= settlement_date <= period_end
            )
        ]
        complete_days = sum(
            bool(item.get("valuation_complete")) for item in snapshots
        )
        incomplete_days = len(snapshots) - complete_days
        starting = (
            Decimal(str(snapshots[0]["total_equity"])) if snapshots else None
        )
        ending = (
            Decimal(str(snapshots[-1]["total_equity"])) if snapshots else None
        )
        total_return = (
            ending / starting - Decimal("1")
            if starting is not None and starting > 0 and ending is not None
            else None
        )
        max_drawdown = None
        if snapshots:
            peak = Decimal(str(snapshots[0]["total_equity"]))
            drawdowns = []
            for snapshot in snapshots:
                equity = Decimal(str(snapshot["total_equity"]))
                peak = max(peak, equity)
                drawdowns.append(
                    equity / peak - Decimal("1") if peak > 0 else Decimal("0")
                )
            max_drawdown = min(drawdowns)
        ending_snapshot = snapshots[-1] if snapshots else None
        total_fees = (
            Decimal(str(ending_snapshot.get("total_fees", "0")))
            if ending_snapshot
            else Decimal(str(account.get("total_fees", "0")))
        )
        average_equity = (
            sum(
                (Decimal(str(item["total_equity"])) for item in snapshots),
                Decimal("0"),
            )
            / len(snapshots)
            if snapshots
            else None
        )
        turnover_notional = sum(
            (Decimal(str(item["notional"])) for item in fills),
            Decimal("0"),
        )
        exposure = (
            sum(
                (
                    Decimal(str(item.get("gross_exposure_pct", "0")))
                    for item in snapshots
                ),
                Decimal("0"),
            )
            / len(snapshots)
            if snapshots
            else None
        )
        realized_values = [
            Decimal(str(item.get("realized_pnl", "0")))
            for item in settlements
        ]
        wins = [value for value in realized_values if value > 0]
        losses = [value for value in realized_values if value < 0]
        profit_factor = (
            sum(wins, Decimal("0")) / abs(sum(losses, Decimal("0")))
            if losses
            else None
        )
        status = (
            "INSUFFICIENT_HISTORY"
            if len(snapshots) < 2
            else "INCOMPLETE_VALUATION"
            if incomplete_days
            else "CALCULATED"
        )
        payload = {
            "account_id": account_id,
            "account_type": str(account["account_type"]),
            "market": str(account["market"]),
            "period_start": period_start,
            "period_end": period_end,
            "status": status,
            "starting_equity": starting,
            "ending_equity": ending,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "realized_pnl": (
                Decimal(str(ending_snapshot.get("realized_pnl", "0")))
                if ending_snapshot
                else Decimal(str(account.get("realized_pnl", "0")))
            ),
            "unrealized_pnl": (
                Decimal(str(ending_snapshot.get("unrealized_pnl", "0")))
                if ending_snapshot
                else None
            ),
            "total_fees": total_fees,
            "fee_drag_pct": (
                total_fees / starting
                if starting is not None and starting > 0
                else None
            ),
            "average_exposure_pct": exposure,
            "turnover": (
                turnover_notional / average_equity
                if average_equity is not None and average_equity > 0
                else None
            ),
            "filled_order_count": sum(
                item.get("status") == "FILLED" for item in orders
            ),
            "trade_count": len(fills),
            "win_rate": (
                Decimal(len(wins)) / Decimal(len(realized_values))
                if realized_values
                else None
            ),
            "profit_factor": profit_factor,
            "valuation_complete_days": complete_days,
            "valuation_incomplete_days": incomplete_days,
            "metric_version": self.version,
        }
        payload["input_hash"] = evaluation_hash(
            {
                **payload,
                "snapshot_ids": [
                    item.get("account_snapshot_id") for item in snapshots
                ],
                "fill_ids": [item.get("fill_id") for item in fills],
                "settlement_ids": [
                    item.get("settlement_id") for item in settlements
                ],
            }
        )
        return AccountPerformanceMetric(
            metric_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:account-metric:{account_id}:"
                    f"{period_start}:{period_end}:{self.version}",
                )
            ),
            calculated_at=datetime.utcnow(),
            **payload,
        )
