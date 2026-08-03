"""Read-only cross-collection consistency checks for AlphaGuard."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS
from tradingagents.alphaguard.operations_schemas import operations_hash


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


class AlphaGuardConsistencyService:
    """Generate evidence and suggestions; never repairs production data."""

    def __init__(self, db):
        self.db = db

    async def _rows(self, collection: str, query: dict | None = None) -> list[dict]:
        return [
            clean_document(row)
            for row in await self.db[collection].find(query or {}).to_list(length=None)
        ]

    @staticmethod
    def _check(
        check_id: str,
        name: str,
        count: int,
        *,
        warning: bool = False,
        evidence: list[str] | None = None,
        suggestion: str,
    ) -> dict[str, Any]:
        return {
            "check_id": check_id,
            "check": check_id,
            "name": name,
            "status": "WARNING" if count and warning else "FAIL" if count else "PASS",
            "count": int(count),
            "evidence": (evidence or [])[:50],
            "suggestion": suggestion if count else "无需处理",
        }

    async def run(self, *, persist: bool = False) -> dict[str, Any]:
        accounts = await self._rows("ag_paper_accounts")
        positions = await self._rows("ag_paper_positions")
        orders = await self._rows("ag_paper_orders")
        fills = await self._rows("ag_paper_fills")
        settlements = await self._rows("ag_settlement_records")
        ledger = await self._rows("ag_paper_ledger_entries")
        reservations = await self._rows("ag_paper_reservations")
        snapshots = await self._rows("ag_evidence_snapshots")
        validation_snapshots = await self._rows("ag_model_validation_evidence_snapshots")
        model_runs = await self._rows("ag_model_runs")
        model_validation_runs = await self._rows("ag_model_validation_runs")
        model_capability_checks = await self._rows("ag_model_capability_checks")
        model_contract_checks = await self._rows("ag_model_contract_checks")
        model_research_results = await self._rows("ag_model_research_results")
        contexts = await self._rows("ag_decision_contexts")
        analyses = await self._rows("analysis_reports")
        consensus = await self._rows("ag_consensus_decisions")
        risks = await self._rows("ag_risk_decisions")
        recommendations = await self._rows("ag_candidate_recommendations")
        candidates = await self._rows("ag_candidates")
        champions = await self._rows("ag_exp_champion_assignments")

        checks: list[dict[str, Any]] = []
        negative_cash = [
            str(row.get("account_id"))
            for row in accounts
            if _decimal(row.get("cash_available")) < 0
        ]
        checks.append(self._check(
            "negative_cash", "可用现金非负", len(negative_cash), evidence=negative_cash,
            suggestion="停止订单处理并核对最近结算与现金Ledger。",
        ))
        negative_reserved = [
            str(row.get("account_id"))
            for row in accounts
            if _decimal(row.get("cash_reserved")) < 0
        ]
        checks.append(self._check(
            "negative_reserved_cash", "冻结资金非负", len(negative_reserved), evidence=negative_reserved,
            suggestion="核对Reservation释放与结算补偿状态。",
        ))
        negative_positions = [
            f"{row.get('account_id')}:{row.get('symbol')}"
            for row in positions
            if int(row.get("quantity") or 0) < 0
            or int(row.get("available_quantity") or 0) < 0
            or int(row.get("reserved_quantity") or 0) < 0
        ]
        checks.append(self._check(
            "negative_position", "持仓数量非负", len(negative_positions), evidence=negative_positions,
            suggestion="停止撮合并从PositionLot重建该账户持仓。",
        ))

        committed_fill_ids = {
            str(row.get("fill_id"))
            for row in settlements
            if row.get("status") == "COMMITTED"
        }
        cash_effect_by_account: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for fill in fills:
            if str(fill.get("fill_id")) in committed_fill_ids:
                cash_effect_by_account[str(fill.get("account_id"))] += _decimal(
                    fill.get("net_cash_effect")
                )
        asset_conflicts = []
        for account in accounts:
            account_id = str(account.get("account_id"))
            observed = _decimal(account.get("cash_available")) + _decimal(
                account.get("cash_reserved")
            )
            expected = _decimal(account.get("initial_cash")) + cash_effect_by_account[account_id]
            if abs(observed - expected) > Decimal("0.01"):
                asset_conflicts.append(
                    f"{account_id}:cash={observed}:expected={expected}"
                )
        checks.append(self._check(
            "account_asset_conservation", "账户现金与已结算成交守恒", len(asset_conflicts), evidence=asset_conflicts,
            suggestion="按已提交Settlement逐笔重放现金影响，不要自动修改正式账户。",
        ))

        fills_by_order: dict[str, int] = defaultdict(int)
        for fill in fills:
            fills_by_order[str(fill.get("order_id"))] += int(fill.get("quantity") or 0)
        quantity_conflicts = []
        for order in orders:
            order_id = str(order.get("order_id"))
            filled = int(order.get("filled_quantity") or 0)
            requested = int(order.get("requested_quantity") or 0)
            remaining = int(order.get("remaining_quantity") or 0)
            if filled != fills_by_order[order_id] or requested != filled + remaining:
                quantity_conflicts.append(order_id)
        checks.append(self._check(
            "order_fill_quantity", "订单与成交数量一致", len(quantity_conflicts), evidence=quantity_conflicts,
            suggestion="核对匹配幂等键、订单版本和Fill汇总。",
        ))

        ledger_conflicts = []
        ledger_by_account: dict[str, list[dict]] = defaultdict(list)
        for row in ledger:
            if row.get("entry_type") == "CASH_CHANGE":
                ledger_by_account[str(row.get("account_id"))].append(row)
        for account in accounts:
            account_id = str(account.get("account_id"))
            entries = sorted(ledger_by_account[account_id], key=lambda row: str(row.get("created_at") or ""))
            if not entries:
                if committed_fill_ids and any(str(fill.get("account_id")) == account_id for fill in fills):
                    ledger_conflicts.append(f"{account_id}:missing-ledger")
                continue
            previous_after = None
            for entry in entries:
                before = entry.get("balance_before")
                after = entry.get("balance_after")
                if previous_after is not None and before is not None and _decimal(before) != previous_after:
                    ledger_conflicts.append(f"{account_id}:broken-chain")
                    break
                if after is not None:
                    previous_after = _decimal(after)
            if previous_after is not None and abs(previous_after - _decimal(account.get("cash_available"))) > Decimal("0.01"):
                ledger_conflicts.append(f"{account_id}:balance-mismatch")
        checks.append(self._check(
            "ledger_rebuild", "Ledger可重建账户余额", len(set(ledger_conflicts)), evidence=sorted(set(ledger_conflicts)),
            suggestion="生成Ledger重放报告并人工确认，不在正式库自动修复。",
        ))

        snapshot_ids = {
            str(row.get("snapshot_id")) for row in [*snapshots, *validation_snapshots] if row.get("snapshot_id")
        }
        missing_snapshot_refs = []
        for collection, rows in (
            ("ag_order_intents", await self._rows("ag_order_intents")),
            ("ag_paper_fills", fills),
            ("ag_decision_contexts", contexts),
            ("ag_quant_proposals", await self._rows("ag_quant_proposals")),
        ):
            for row in rows:
                snapshot_id = row.get("snapshot_id")
                if snapshot_id and str(snapshot_id) not in snapshot_ids:
                    missing_snapshot_refs.append(f"{collection}:{snapshot_id}")
        checks.append(self._check(
            "snapshot_references", "Snapshot引用存在", len(missing_snapshot_refs), evidence=missing_snapshot_refs,
            suggestion="阻断相关决策或订单并核对不可变Snapshot备份。",
        ))

        context_analysis = {
            str(row.get("analysis_id"))
            for row in contexts
            if row.get("analysis_id")
        }
        context_analysis.update(
            str(row.get("analysis_id"))
            for row in analyses
            if row.get("analysis_id")
        )
        context_analysis.update(
            str(row.get("analysis_id"))
            for row in model_research_results
            if row.get("analysis_id")
        )
        validation_ids = {
            str(row.get("validation_run_id"))
            for row in model_validation_runs
            if row.get("validation_run_id")
        }
        capability_ids = {
            str(row.get("capability_check_id"))
            for row in model_capability_checks
            if row.get("capability_check_id")
        }
        contract_ids = {
            str(row.get("contract_check_id"))
            for row in model_contract_checks
            if row.get("contract_check_id")
        }
        missing_model_refs = []
        for row in model_runs:
            model_run_id = str(row.get("model_run_id"))
            analysis_id = str(row.get("analysis_id") or "")
            run_mode = str(row.get("run_mode") or "")
            valid_analysis = not analysis_id or analysis_id in context_analysis
            if run_mode == "REAL_MODEL_VALIDATION":
                valid_analysis = (
                    analysis_id.startswith("real-model-validation:")
                    and analysis_id.split(":", 1)[1] in validation_ids
                )
            elif run_mode == "MODEL_CAPABILITY_CHECK":
                suffix = analysis_id.rsplit(":", 1)[-1]
                valid_analysis = suffix in capability_ids or suffix in contract_ids
            snapshot_id = row.get("snapshot_id")
            valid_snapshot = (
                run_mode == "MODEL_CAPABILITY_CHECK"
                or not snapshot_id
                or str(snapshot_id) in snapshot_ids
            )
            if not valid_analysis or not valid_snapshot:
                missing_model_refs.append(model_run_id)
        checks.append(self._check(
            "model_call_references", "模型调用引用存在", len(missing_model_refs), evidence=missing_model_refs,
            suggestion="保留模型审计并阻断缺少DecisionContext的结果。",
        ))

        plan_ids = {
            str((row.get("normal_trade_plan") or {}).get("plan_id"))
            for row in analyses
            if (row.get("normal_trade_plan") or {}).get("plan_id")
        }
        review_ids = {
            str((row.get("top_review_decision") or {}).get("review_id"))
            for row in analyses
            if (row.get("top_review_decision") or {}).get("review_id")
        }
        consensus_ids = {str(row.get("consensus_id")) for row in consensus if row.get("consensus_id")}
        chain_conflicts = []
        for row in consensus:
            if str(row.get("plan_id")) not in plan_ids or str(row.get("review_id")) not in review_ids:
                chain_conflicts.append(str(row.get("consensus_id")))
        for row in risks:
            if str(row.get("consensus_id")) not in consensus_ids:
                chain_conflicts.append(str(row.get("risk_decision_id")))
        checks.append(self._check(
            "decision_chain_references", "决策链引用完整", len(chain_conflicts), evidence=chain_conflicts,
            suggestion="阻断不完整链路，按analysis_id核对Normal、Top、Consensus和HardRisk。",
        ))

        candidate_keys = {
            (str(row.get("user_id")), str(row.get("symbol"))) for row in candidates
        }
        accepted_missing = [
            str(row.get("recommendation_id"))
            for row in recommendations
            if row.get("status") == "ACCEPTED"
            and (str(row.get("user_id")), str(row.get("symbol"))) not in candidate_keys
        ]
        checks.append(self._check(
            "recommendation_candidate_link", "推荐接受记录与CandidateEntry一致", len(accepted_missing), evidence=accepted_missing,
            suggestion="核对接受审计事件与候选池幂等写入。",
        ))

        account_types = {str(row.get("account_id")): str(row.get("account_type")) for row in accounts}
        challenger_conflicts = []
        for collection, rows in (
            ("position", positions), ("order", orders), ("fill", fills),
            ("reservation", reservations), ("ledger", ledger),
        ):
            for row in rows:
                is_challenger = account_types.get(str(row.get("account_id"))) == "PAPER_CHALLENGER"
                has_lineage = row.get("run_mode") == "PAPER_CHALLENGER" or bool(row.get("experiment_id"))
                if is_challenger != has_lineage:
                    challenger_conflicts.append(f"{collection}:{row.get('account_id')}")
        checks.append(self._check(
            "challenger_account_isolation", "Challenger对象账户隔离", len(challenger_conflicts), evidence=challenger_conflicts,
            suggestion="暂停Challenger任务并核对experiment lineage与专用账户。",
        ))

        champion_conflicts = [
            str(row.get("champion_slot_id"))
            for row in champions
            if row.get("status") == "ACTIVE" and not row.get("current_version_ref")
        ]
        active_slots = [str(row.get("champion_slot_id")) for row in champions if row.get("status") == "ACTIVE"]
        champion_conflicts.extend(
            slot for slot, count in Counter(active_slots).items() if count > 1
        )
        checks.append(self._check(
            "champion_pointer", "Champion指针有效", len(set(champion_conflicts)), evidence=sorted(set(champion_conflicts)),
            suggestion="阻断晋升并恢复最后一个人工确认的唯一Champion指针。",
        ))

        missing_indexes = []
        for collection_name, specs in ALPHAGUARD_INDEX_SPECS.items():
            existing = {
                item["name"]
                for item in await self.db[collection_name].list_indexes().to_list(length=None)
            }
            missing_indexes.extend(
                f"{collection_name}.{spec['name']}"
                for spec in specs
                if spec["name"] not in existing
            )
        checks.append(self._check(
            "required_indexes_missing", "唯一索引和必要索引正常", len(missing_indexes), evidence=missing_indexes,
            suggestion="仅运行create-only索引初始化，不删除现有索引或数据。",
        ))

        order_by_id = {str(row.get("order_id")): row for row in orders}
        orphan_reservations = []
        for row in reservations:
            if row.get("status") not in {"ACTIVE", "PARTIALLY_CONSUMED", "CONSUMED"}:
                continue
            order = order_by_id.get(str(row.get("order_id")))
            if order is None or order.get("status") in {"FILLED", "CANCELLED", "REJECTED", "EXPIRED"}:
                orphan_reservations.append(str(row.get("reservation_id")))
        checks.append(self._check(
            "orphan_reservation", "无孤立Reservation", len(orphan_reservations), evidence=orphan_reservations,
            suggestion="使用受控Reservation核对任务释放，不直接删除。",
        ))

        duplicate_fill_keys = []
        for key_name in ("fill_id", "idempotency_key"):
            counts = Counter(str(row.get(key_name)) for row in fills if row.get(key_name))
            duplicate_fill_keys.extend(f"{key_name}:{key}" for key, count in counts.items() if count > 1)
        order_date_counts = Counter(
            (str(row.get("order_id")), str(row.get("trade_date"))) for row in fills
        )
        duplicate_fill_keys.extend(
            f"order_date:{key[0]}:{key[1]}" for key, count in order_date_counts.items() if count > 1
        )
        checks.append(self._check(
            "duplicate_fill", "无重复Fill", len(duplicate_fill_keys), evidence=duplicate_fill_keys,
            suggestion="阻断撮合并核对Fill唯一键；不得自动删除正式成交。",
        ))

        account_ids = set(account_types)
        cross_account_positions = [
            str(row.get("position_id"))
            for row in positions
            if str(row.get("account_id")) not in account_ids
        ]
        checks.append(self._check(
            "cross_account_position", "无跨账户或孤立Position", len(cross_account_positions), evidence=cross_account_positions,
            suggestion="核对Position的account_id与账户类型，禁止跨账户迁移。",
        ))

        stuck_settlement = [
            str(row.get("settlement_id"))
            for row in settlements
            if row.get("status") in {
                "PREPARED", "ACCOUNT_APPLIED", "POSITION_APPLIED", "LEDGER_APPLIED", "COMPENSATION_REQUIRED"
            }
        ]
        checks.append(self._check(
            "settlement_saga_stuck", "无卡住的结算Saga", len(stuck_settlement), warning=True, evidence=stuck_settlement,
            suggestion="运行幂等结算恢复并再次生成一致性报告。",
        ))
        promotion_stuck = await self.db["ag_exp_promotion_sagas"].count_documents(
            {"status": {"$nin": ["COMMITTED", "ROLLED_BACK", "FAILED"]}}
        )
        checks.append(self._check(
            "promotion_saga_stuck", "无卡住的晋升Saga", promotion_stuck, warning=True,
            suggestion="运行晋升Saga恢复；不得自动修改Champion。",
        ))
        dead_letter = await self.db["ag_execution_outbox"].count_documents(
            {"status": "DEAD_LETTER"}
        )
        checks.append(self._check(
            "outbox_dead_letter", "执行Outbox无死信", dead_letter, warning=True,
            suggestion="人工检查脱敏错误后通过受控任务重试。",
        ))

        failed = sum(item["status"] == "FAIL" for item in checks)
        warnings = sum(item["status"] == "WARNING" for item in checks)
        status = "FAIL" if failed else "WARNING" if warnings else "PASS"
        checked_at = datetime.utcnow()
        payload = {
            "status": status,
            "checks": checks,
            "summary": {"passed": len(checks) - failed - warnings, "warnings": warnings, "failed": failed},
            "checked_at": checked_at,
            "auto_repair_performed": False,
            "missing_indexes": missing_indexes,
            "schema_version": "alphaguard-consistency-v1",
        }
        payload["report_hash"] = operations_hash(payload, exclude={"checked_at", "report_hash"})
        payload["report_id"] = str(
            uuid5(NAMESPACE_URL, f"alphaguard:consistency:{payload['report_hash']}")
        )
        if persist:
            await self.db["ag_consistency_reports"].update_one(
                {"report_id": payload["report_id"]}, {"$setOnInsert": payload}, upsert=True
            )
        return payload
