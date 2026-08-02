"""Read models for the Chinese Challenger UI and Operations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.services.alphaguard.paper_storage import clean_document


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _metric_difference(values: dict[str, Any]) -> Decimal | None:
    champion = _optional_decimal(values.get("champion"))
    challenger = _optional_decimal(values.get("challenger"))
    if champion is None or challenger is None:
        return None
    return challenger - champion


def _return_drawdown_ratio(net_return: Any, max_drawdown: Any) -> Decimal | None:
    parsed_return = _optional_decimal(net_return)
    parsed_drawdown = _optional_decimal(max_drawdown)
    if parsed_return is None or parsed_drawdown is None or parsed_drawdown == 0:
        return None
    return parsed_return / abs(parsed_drawdown)


class PaperChallengerQueryService:
    def __init__(self, db):
        self.db = db

    async def list(self, *, user_id: str | None = None) -> list[dict[str, Any]]:
        query = {} if user_id is None else {"user_id": str(user_id)}
        definitions = await self.db["ag_exp_definitions"].find(query).sort(
            "created_at", -1
        ).to_list(length=500)
        return [
            await self.summary(str(item["experiment_id"]))
            for item in definitions
            if item.get("baseline_champion_id")
            and item.get("challenger_version_id")
            and item.get("config_hash")
        ]

    async def summary(self, experiment_id: str) -> dict[str, Any]:
        definition = clean_document(
            await self.db["ag_exp_definitions"].find_one(
                {"experiment_id": experiment_id}
            )
        )
        if definition is None:
            raise LookupError("Challenger experiment does not exist")
        assignment = clean_document(
            await self.db["ag_exp_challenger_assignments"].find_one(
                {"experiment_id": experiment_id}, sort=[("created_at", -1)]
            )
        )
        account = None
        positions: list[dict] = []
        if assignment:
            account = clean_document(
                await self.db["ag_paper_accounts"].find_one(
                    {"account_id": assignment["account_id"]}
                )
            )
            positions = [
                clean_document(item)
                for item in await self.db["ag_paper_positions"].find(
                    {"account_id": assignment["account_id"], "quantity": {"$gt": 0}}
                ).to_list(length=None)
            ]
        runs = await self.db["ag_exp_challenger_runs"].find(
            {"experiment_id": experiment_id}
        ).sort("created_at", -1).to_list(length=None)
        orders = await self.db["ag_paper_orders"].find(
            {"experiment_id": experiment_id}
        ).to_list(length=None)
        fills = await self.db["ag_paper_fills"].find(
            {"experiment_id": experiment_id}
        ).to_list(length=None)
        latest_snapshot = None
        if assignment:
            latest_snapshot = clean_document(
                await self.db["ag_paper_account_snapshots"].find_one(
                    {"account_id": assignment["account_id"]},
                    sort=[("trade_date", -1)],
                )
            )
        starting_equity = _decimal(
            (assignment or {}).get("starting_equity")
            or (account or {}).get("initial_cash")
        )
        latest_equity = _decimal(
            (latest_snapshot or {}).get("total_equity")
            or (account or {}).get("cash_available")
        )
        return {
            "experiment_id": experiment_id,
            "name": definition["name"],
            "status": definition["status"],
            "baseline_champion_id": definition.get("baseline_champion_id"),
            "baseline_champion_version": definition.get("baseline_champion_version"),
            "challenger_version_id": definition.get("challenger_version_id"),
            "change_type": definition.get("change_type"),
            "change_summary": definition.get("change_summary"),
            "primary_variable_path": definition.get("primary_variable_path"),
            "config_hash": definition.get("config_hash"),
            "validation_only": bool(definition.get("validation_only")),
            "promotion_eligible": bool(definition.get("promotion_eligible")),
            "assignment_id": (assignment or {}).get("assignment_id"),
            "assignment_status": (assignment or {}).get("status"),
            "account_id": (assignment or {}).get("account_id"),
            "cash_available": (account or {}).get("cash_available"),
            "cash_reserved": (account or {}).get("cash_reserved"),
            "position_count": len(positions),
            "order_count": len(orders),
            "fill_count": len(fills),
            "run_count": len(runs),
            "last_run_at": (runs[0] if runs else {}).get("updated_at"),
            "last_run_status": (runs[0] if runs else {}).get("status"),
            "last_failure_code": (runs[0] if runs else {}).get("failure_code"),
            "net_return": (
                (latest_equity - starting_equity) / starting_equity
                if starting_equity > 0
                else None
            ),
            "total_fees": (account or {}).get("total_fees"),
            "created_at": definition.get("created_at"),
        }

    async def runs(self, experiment_id: str) -> list[dict[str, Any]]:
        return [
            clean_document(item)
            for item in await self.db["ag_exp_challenger_runs"].find(
                {"experiment_id": experiment_id}
            ).sort("created_at", -1).to_list(length=500)
        ]

    async def decisions(self, experiment_id: str) -> list[dict[str, Any]]:
        decision_types = {
            "QUANT_PROPOSAL",
            "DECISION_CONTEXT",
            "RESEARCH_RESULT",
            "NORMAL_PLAN",
            "TOP_REVIEW",
            "CONSENSUS_DECISION",
            "HARD_RISK_DECISION",
        }
        rows = await self.db["ag_exp_challenger_objects"].find(
            {"experiment_id": experiment_id}
        ).sort("created_at", -1).to_list(length=1000)
        return [
            clean_document(item)
            for item in rows
            if item.get("object_type") in decision_types
        ]

    async def orders(self, experiment_id: str) -> dict[str, list[dict[str, Any]]]:
        intents = [
            clean_document(item)
            for item in await self.db["ag_order_intents"].find(
                {"experiment_id": experiment_id}
            ).sort("created_at", -1).to_list(length=500)
        ]
        orders = [
            clean_document(item)
            for item in await self.db["ag_paper_orders"].find(
                {"experiment_id": experiment_id}
            ).sort("created_at", -1).to_list(length=500)
        ]
        fills = [
            clean_document(item)
            for item in await self.db["ag_paper_fills"].find(
                {"experiment_id": experiment_id}
            ).sort("created_at", -1).to_list(length=500)
        ]
        return {"intents": intents, "orders": orders, "fills": fills}

    async def evaluation(self, experiment_id: str) -> dict[str, Any]:
        subjects = [
            clean_document(item)
            for item in await self.db["ag_eval_subjects"].find({}).to_list(length=None)
            if str((item.get("lineage_ids") or {}).get("experiment_id") or "")
            == experiment_id
        ]
        subject_ids = [item["subject_id"] for item in subjects]
        labels = [
            clean_document(item)
            for item in await self.db["ag_eval_horizon_labels"].find(
                {"subject_id": {"$in": subject_ids}}
            ).to_list(length=None)
        ] if subject_ids else []
        attributions = [
            clean_document(item)
            for item in await self.db["ag_eval_attributions"].find(
                {"subject_id": {"$in": subject_ids}}
            ).to_list(length=None)
        ] if subject_ids else []
        mature = sum(item.get("status") == "CALCULATED" for item in labels)
        return {
            "subjects": subjects,
            "labels": labels,
            "attributions": attributions,
            "mature_label_count": mature,
            "pending_label_count": len(labels) - mature,
        }

    async def comparison(self, experiment_id: str) -> dict[str, Any]:
        challenger = await self.summary(experiment_id)
        assignment = clean_document(
            await self.db["ag_exp_challenger_assignments"].find_one(
                {"experiment_id": experiment_id}, sort=[("created_at", -1)]
            )
        )
        champion_account = None
        if assignment:
            champion_account = clean_document(
                await self.db["ag_paper_accounts"].find_one(
                    {
                        "user_id": assignment["user_id"],
                        "account_type": "PAPER_TOP_CONFIRMED",
                        "market": "CN",
                    }
                )
            )
        report = clean_document(
            await self.db["ag_exp_comparison_reports"].find_one(
                {"experiment_id": experiment_id}, sort=[("created_at", -1)]
            )
        )
        champion_initial = _decimal((champion_account or {}).get("initial_cash"))
        champion_cash = _decimal((champion_account or {}).get("cash_available"))
        champion_return = (
            (champion_cash - champion_initial) / champion_initial
            if champion_initial > 0
            else None
        )
        challenger_return = challenger.get("net_return")
        return_comparison = (report or {}).get("return_comparison") or {}
        drawdown_comparison = (report or {}).get("drawdown_comparison") or {}
        cost_comparison = (report or {}).get("cost_comparison") or {}
        turnover_comparison = (report or {}).get("turnover_comparison") or {}
        champion_summary = (report or {}).get("champion_summary") or {}
        challenger_summary = (report or {}).get("challenger_summary") or {}

        if report:
            champion_return = _optional_decimal(return_comparison.get("champion"))
            challenger_return = _optional_decimal(return_comparison.get("challenger"))

        champion_ratio = _return_drawdown_ratio(
            champion_return,
            drawdown_comparison.get("champion"),
        )
        challenger_ratio = _return_drawdown_ratio(
            challenger_return,
            drawdown_comparison.get("challenger"),
        )
        trade_count_difference = _metric_difference(
            {
                "champion": champion_summary.get("trade_count"),
                "challenger": challenger_summary.get("trade_count"),
            }
        )
        return_difference = _metric_difference(
            {
                "champion": champion_return,
                "challenger": challenger_return,
            }
        )
        return {
            "experiment_id": experiment_id,
            "paper_champion_proxy": "PAPER_TOP_CONFIRMED",
            "comparison_report_id": (report or {}).get("comparison_report_id"),
            "comparison_status": (report or {}).get("status", "NOT_MATURE"),
            "challenger_return": challenger_return,
            "champion_return": champion_return,
            "return_difference": return_difference,
            "return_drawdown_ratio_difference": (
                challenger_ratio - champion_ratio
                if challenger_ratio is not None and champion_ratio is not None
                else None
            ),
            "trade_count_difference": trade_count_difference,
            "turnover_difference": _metric_difference(turnover_comparison),
            "cost_difference": (
                _metric_difference(cost_comparison)
                if report
                else _decimal(challenger.get("total_fees"))
                - _decimal((champion_account or {}).get("total_fees"))
            ),
            "drawdown_difference": (
                _optional_decimal(drawdown_comparison.get("worsening"))
                if report
                else None
            ),
            "regime_difference": (
                (report or {}).get("regime_stability_comparison") or {}
            ),
            "extreme_trade_dependency": (
                (report or {}).get("outlier_dependency_comparison")
                or "NOT_MATURE"
            ),
            "promotion_action": "MANUAL_REVIEW_ONLY",
            "policy_report": report,
            "generated_at": datetime.utcnow(),
        }
