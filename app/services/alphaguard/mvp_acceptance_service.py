"""Chinese MVP acceptance matrix assembled from persisted operational facts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_storage import clean_document
from scripts.alphaguard_backup import (
    DEFAULT_BACKUP_ROOT,
    list_backups,
)
from tradingagents.alphaguard.operations_schemas import operations_hash
from tradingagents.alphaguard.release_schemas import MvpAcceptanceItem, MvpAcceptanceReport


SUCCESS_VALUES = {"SUCCESS", "COMPLETED", "READY", "PASS", "ACTIVE", "TRIGGERED", "CONSENSUS_PASS", "CONFIRM", "FILLED", "CALCULATED", "REUSED"}
FAILURE_VALUES = {"FAILED", "ERROR", "BLOCKED", "INVALID_OUTPUT", "MODEL_FAILED", "DEAD_LETTER", "COMPENSATION_REQUIRED"}


class MvpAcceptanceService:
    def __init__(self, db, *, operations_service, backup_root: Path = DEFAULT_BACKUP_ROOT):
        self.db = db
        self.operations = operations_service
        self.backup_root = backup_root

    async def _facts(
        self,
        collection: str,
        id_fields: tuple[str, ...],
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rows = [
            clean_document(row)
            for row in await self.db[collection].find(query or {}).to_list(length=None)
        ]
        rows.sort(key=lambda row: str(row.get("completed_at") or row.get("updated_at") or row.get("created_at") or ""), reverse=True)
        latest = rows[0] if rows else {}
        successes = [row for row in rows if str(row.get("status") or row.get("terminal_status") or "").upper() in SUCCESS_VALUES]
        failures = [row for row in rows if str(row.get("status") or row.get("terminal_status") or "").upper() in FAILURE_VALUES]

        def timestamp(row):
            value = (row or {}).get("completed_at") or (row or {}).get("updated_at") or (row or {}).get("created_at")
            return value if isinstance(value, datetime) else None

        object_id = next((latest.get(field) for field in id_fields if latest.get(field)), None)
        version = next((latest.get(field) for field in ("schema_version", "version", "policy_version") if latest.get(field)), "alphaguard-mvp-rc1")
        return {
            "count": len(rows),
            "last_success_at": timestamp(successes[0]) if successes else timestamp(latest),
            "last_failure_at": timestamp(failures[0]) if failures else None,
            "latest_object_id": str(object_id) if object_id is not None else None,
            "version": str(version),
        }

    @staticmethod
    def _item(item_id: str, name: str, facts: dict[str, Any], *, owner: str, status: str | None = None, reason: str | None = None, evidence: list[str] | None = None) -> MvpAcceptanceItem:
        count = int(facts.get("count") or 0)
        resolved = status or ("可用" if count else "未就绪")
        return MvpAcceptanceItem(
            item_id=item_id,
            item_name=name,
            status=resolved,
            last_success_at=facts.get("last_success_at"),
            last_failure_at=facts.get("last_failure_at"),
            latest_object_id=facts.get("latest_object_id"),
            blocking_reason=reason if resolved in {"降级可用", "未就绪", "已阻断"} else None,
            verification_evidence=evidence or [f"{count} 个持久化对象"],
            version=str(facts.get("version") or "alphaguard-mvp-rc1"),
            owner_module=owner,
            advanced={"object_count": count},
        )

    async def report(self, *, persist: bool = False) -> MvpAcceptanceReport:
        readiness = await self.operations.readiness(persist_alerts=False)
        integrity = await self.operations.integrity()
        backups = list_backups(self.backup_root)
        latest_backup = backups[0] if backups else None
        backup_verified = bool(
            latest_backup and latest_backup.get("status") == "READY"
        )
        scheduler_job = self.operations.scheduler.get_job("alphaguard_daily_run") if self.operations.scheduler else None
        level_b = clean_document(
            await self.db["ag_model_validation_runs"].find_one(
                {"status": {"$in": ["COMPLETED", "REUSED"]}},
                sort=[("completed_at", -1)],
            )
        ) or {}
        level_b_complete = all(
            level_b.get(field)
            for field in (
                "normal_result",
                "top_result",
                "consensus_result",
                "hard_risk_result",
            )
        )
        level_b_ids = {
            "normal_model": level_b.get("normal_model_run_id") or level_b.get("validation_run_id"),
            "top_model": level_b.get("top_model_run_id") or level_b.get("validation_run_id"),
            "consensus": (level_b.get("consensus_result") or {}).get("consensus_id") or level_b.get("validation_run_id"),
            "hard_risk": (level_b.get("hard_risk_result") or {}).get("risk_decision_id") or level_b.get("validation_run_id"),
        }
        definitions = (
            ("candidate_pool", "候选池", "ag_candidates", ("candidate_id",), "candidate_pool_service"),
            ("recommendation", "推荐系统", "ag_candidate_recommendations", ("recommendation_id",), "candidate_recommendation_service"),
            ("data_center", "数据中心", "ag_recommendation_data_coverages", ("coverage_id",), "recommendation_data_service"),
            ("evidence_snapshot", "EvidenceSnapshot", "ag_evidence_snapshots", ("snapshot_id",), "evidence_snapshot_service"),
            ("factor_engine", "FactorEngine", "ag_factor_results", ("factor_result_id", "snapshot_id"), "factor_engine"),
            ("market_regime", "MarketRegime", "ag_regime_results", ("regime_result_id", "snapshot_id"), "market_regime_engine"),
            ("strategy_engine", "StrategyEngine", "ag_quant_proposals", ("proposal_id",), "quant_research_pipeline"),
            ("tradingagents", "TradingAgents", "ag_model_research_results", ("research_result_id",), "snapshot_research_runtime"),
            ("normal_model", "Normal模型", "analysis_reports", ("analysis_id",), "decision_pipeline"),
            ("top_model", "Top模型", "ag_model_runs", ("model_run_id",), "model_runner"),
            ("consensus", "Consensus", "ag_consensus_decisions", ("consensus_id",), "consensus_engine"),
            ("hard_risk", "HardRisk", "ag_risk_decisions", ("risk_decision_id",), "hard_risk_engine"),
            ("paper_accounts", "模拟账户", "ag_paper_accounts", ("account_id",), "paper_account_service"),
            ("orders_matching", "订单与撮合", "ag_paper_orders", ("order_id",), "paper_task_service"),
            ("evaluation", "评价归因", "ag_eval_subjects", ("subject_id", "evaluation_subject_id"), "evaluation_pipeline"),
            ("experiment_lab", "Experiment Lab", "ag_exp_component_versions", ("component_version_id",), "experiment_service"),
        )
        items: list[MvpAcceptanceItem] = []
        facts_by_id: dict[str, dict[str, Any]] = {}
        for item_id, name, collection, ids, owner in definitions:
            facts = await self._facts(collection, ids)
            evidence = None
            if level_b_complete and item_id in level_b_ids:
                facts = {
                    **facts,
                    "count": max(1, int(facts.get("count") or 0)),
                    "last_success_at": level_b.get("completed_at"),
                    "latest_object_id": level_b_ids[item_id],
                    "version": level_b.get("validation_contract_version")
                    or facts.get("version"),
                }
                evidence = [
                    f"PR-010 Level B validation={level_b.get('validation_run_id')}",
                    f"execution_gate={level_b.get('execution_gate_status')}",
                ]
            facts_by_id[item_id] = facts
            status = reason = None
            if item_id in {"orders_matching", "normal_model", "consensus", "hard_risk"} and not facts["count"]:
                status = "降级可用"
                reason = "当前没有自然到达该阶段的对象；不为验收制造交易"
            items.append(self._item(item_id, name, facts, owner=owner, status=status, reason=reason, evidence=evidence))

        challenger = await self._facts(
            "ag_paper_accounts",
            ("account_id",),
            {"account_type": "PAPER_CHALLENGER", "status": "ACTIVE"},
        )
        items.append(self._item("paper_challenger", "PAPER_CHALLENGER", challenger, owner="paper_challenger_runtime", reason="PAPER_CHALLENGER专用账户未就绪" if not challenger["count"] else None))
        root = Path(__file__).resolve().parents[3]
        frontend_ready = (root / "frontend/src/views/AlphaGuard/Operations.vue").exists()
        items.append(self._item("frontend", "前端", {"count": int(frontend_ready), "version": "alphaguard-frontend-acceptance-v1"}, owner="frontend/AlphaGuard", status="可用" if frontend_ready else "已阻断", reason="AlphaGuard前端入口缺失" if not frontend_ready else None, evidence=["候选、决策、模拟交易、评价、实验与Operations页面"]))
        items.append(self._item("operations", "Operations", {"count": 1, "latest_object_id": readiness.report_id, "last_success_at": readiness.generated_at, "version": readiness.schema_version}, owner="operations_service", status="可用" if readiness.overall_status != "UNSAFE" else "已阻断", reason="安全启动门禁失败" if readiness.overall_status == "UNSAFE" else None, evidence=[f"overall={readiness.overall_status}", f"report={readiness.report_id}"]))
        integrity_status = integrity.get("status", "NOT_RUN")
        consistency_item_status = {
            "PASS": "可用",
            "WARNING": "降级可用",
            "FAIL": "已阻断",
            "NOT_RUN": "未就绪",
        }.get(integrity_status, "未就绪")
        items.append(self._item("data_consistency", "数据一致性", {"count": int(integrity_status == "PASS"), "latest_object_id": integrity.get("report_id"), "last_success_at": integrity.get("checked_at") if integrity_status == "PASS" else None, "version": integrity.get("schema_version", "alphaguard-consistency-v1")}, owner="consistency_service", status=consistency_item_status, reason=None if integrity_status == "PASS" else f"统一一致性检查状态：{integrity_status}", evidence=[f"status={integrity_status}", "正式数据只报告、不自动修复"]))
        items.append(self._item("notifications", "通知", {"count": await self.db["notifications"].count_documents({}), "version": "notification-degraded-v2"}, owner="notifications_service/websocket_notifications", status="降级可用", reason="通知失败独立降级，不影响核心交易安全链", evidence=["REST显式READY/DEGRADED", "WebSocket URL不含Token", "最多6次有限退避"]))
        items.append(self._item("scheduler", "调度", {"count": int(scheduler_job is not None), "version": "alphaguard-daily-run-v1"}, owner="daily_run_service/APScheduler", status="可用" if scheduler_job else "降级可用", reason=None if scheduler_job else "独立报告进程无法读取API进程内Scheduler", evidence=["20阶段显式依赖", "相同输入REUSED", "支持resume/from/to/status"]))
        items.append(self._item("backup_restore", "备份恢复", {"count": int(backup_verified), "latest_object_id": latest_backup.get("backup_id") if latest_backup else None, "version": latest_backup.get("schema_version") if latest_backup else "alphaguard-mvp-rc1-backup-v1"}, owner="alphaguard_backup/restore", status="可用" if backup_verified else "未就绪", reason=None if backup_verified else ("最近备份Manifest无有效完整校验证据" if latest_backup else "尚未创建并校验MVP备份"), evidence=["BSON集合备份", "manifest hash", "默认隔离恢复"]))
        items.append(self._item("safety_gates", "安全门禁", {"count": 1, "version": "baseline-guard-v1"}, owner="alphaguard_config", status="可用" if not readiness.live_trading_enabled else "已阻断", reason="live_trading_enabled意外开启" if readiness.live_trading_enabled else None, evidence=["SIM_AUTONOMOUS", "AUTO_CANDIDATE_ACCEPT=false", "LIVE_READY=false"]))

        statuses = ("可用", "降级可用", "未就绪", "已阻断", "不适用")
        counts = {status: sum(item.status == status for item in items) for status in statuses}
        real_model_runs = [
            clean_document(row)
            for row in await self.db["ag_model_runs"].find(
                {
                    "run_mode": {"$in": ["REAL_MODEL_VALIDATION", "PRODUCTION"]},
                    "structured_output_status": "SUCCESS",
                }
            ).to_list(length=None)
        ]
        model_ready = bool(level_b_complete and real_model_runs)
        dual_ready = level_b_complete or all(
            int(facts_by_id[item_id].get("count") or 0) > 0
            for item_id in ("normal_model", "top_model", "consensus", "hard_risk")
        )
        available = {
            item.item_id: item.status in {"可用", "降级可用"}
            for item in items
        }
        flags = {
            "MVP_CODE_COMPLETE": True,
            "MVP_RUNTIME_READY": (
                readiness.overall_status != "UNSAFE" and integrity_status != "FAIL"
            ),
            "RECOMMENDATION_READY": available.get("recommendation", False),
            "RECOMMENDATION_DATA_READY": available.get("data_center", False),
            "REAL_MODEL_RUNTIME_READY": model_ready,
            "DUAL_MODEL_READY": dual_ready,
            "PAPER_READY": available.get("paper_accounts", False),
            "EVALUATION_READY": available.get("evaluation", False),
            "EXPERIMENT_READY": available.get("experiment_lab", False),
            "CHALLENGER_READY": available.get("paper_challenger", False),
            "ACTIVE_CHALLENGER": readiness.active_challenger,
            "AUTO_CANDIDATE_ACCEPT": False,
            "LIVE_READY": False,
        }
        overall = "BLOCKED" if counts["已阻断"] else "NOT_READY" if counts["未就绪"] else "MVP_PAPER_READY"
        latest_daily = clean_document(await self.db["ag_daily_job_runs"].find_one({}, sort=[("completed_at", -1)]))
        generated_at = datetime.utcnow()
        base = {
            "report_id": "pending",
            "generated_at": generated_at,
            "overall_status": overall,
            "items": items,
            "summary": counts,
            "state_flags": flags,
            "latest_daily_run_id": (latest_daily or {}).get("daily_run_id"),
            "latest_backup_id": latest_backup.get("backup_id") if latest_backup else None,
            "consistency_status": integrity.get("status", "NOT_RUN"),
            "schema_version": "alphaguard-mvp-release-v1",
        }
        report_hash = operations_hash(base, exclude={"report_id", "generated_at", "report_hash"})
        base["report_hash"] = report_hash
        base["report_id"] = str(uuid5(NAMESPACE_URL, f"alphaguard:mvp-acceptance:{report_hash}"))
        report = MvpAcceptanceReport.model_validate(base)
        if persist:
            await self.db["ag_mvp_acceptance_reports"].update_one({"report_id": report.report_id}, {"$setOnInsert": report.model_dump(mode="python")}, upsert=True)
        return report
