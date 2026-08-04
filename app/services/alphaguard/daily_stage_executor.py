"""Production stage executor used by the controlled AlphaGuard daily entry."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from app.services.alphaguard.candidate_recommendation_policy import (
    CandidateRecommendationPolicyRegistry,
)
from app.services.alphaguard.candidate_recommendation_service import (
    CandidateRecommendationService,
)
from app.services.alphaguard.akshare_market_context_provider import (
    AKShareTencentMarketContextProvider,
)
from app.services.alphaguard.daily_run_service import (
    DailyRunBlocked,
    DailyStageSpec,
    StageExecutionResult,
)
from app.services.alphaguard.evaluation_pipeline import EvaluationPipeline
from app.services.alphaguard.operations_service import AlphaGuardOperationsService
from app.services.alphaguard.model_runtime_status_service import (
    ModelRuntimeStatusService,
)
from app.services.alphaguard.paper_calendar_service import PaperTradingCalendarService
from app.services.alphaguard.paper_task_service import PaperTaskService
from app.services.alphaguard.production_market_context_service import (
    ProductionMarketContextService,
)
from app.services.alphaguard.production_observation_service import (
    ProductionObservationService,
)
from app.services.alphaguard.recommendation_data_service import (
    RecommendationDataService,
)
from app.services.alphaguard.paper_storage import clean_document


DAILY_MARKET_CONTEXT_TIMEOUT_SECONDS = 7200


class ProductionDailyStageExecutor:
    """Execute existing governed services without changing strategy semantics."""

    def __init__(self, db, *, redis_client=None, scheduler=None):
        self.db = db
        self.redis = redis_client
        self.scheduler = scheduler
        self.cache: dict[str, Any] = {}
        self._daily_run_id: str | None = None

    def _select_run(self, daily_run_id: str) -> None:
        if self._daily_run_id != daily_run_id:
            self.cache.clear()
            self._daily_run_id = daily_run_id

    async def execute(
        self,
        stage: DailyStageSpec,
        *,
        trading_date: date,
        input_version: str,
        daily_run_id: str,
    ) -> StageExecutionResult:
        self._select_run(daily_run_id)
        method = getattr(self, f"stage_{stage.stage_id.lower()}")
        return await method(
            trading_date=trading_date,
            input_version=input_version,
            daily_run_id=daily_run_id,
        )

    async def restore(
        self,
        stage: DailyStageSpec,
        *,
        stage_run,
        daily_run_id: str,
        **_,
    ) -> None:
        """Rehydrate non-business executor state after an idempotent reuse."""
        self._select_run(daily_run_id)
        self.cache.setdefault("stage_results", {})[stage.stage_id] = dict(
            stage_run.result or {}
        )

    def _stage_result(self, stage_id: str) -> dict[str, Any]:
        return dict(self.cache.get("stage_results", {}).get(stage_id) or {})

    async def stage_trading_calendar(self, *, trading_date: date, **_):
        is_open = await PaperTradingCalendarService(self.db).is_open_date(trading_date)
        if not is_open:
            return StageExecutionResult(
                status="SKIPPED",
                message="非交易日：后续盘后任务安全跳过",
                result={"is_open": False},
                skip_remaining=True,
            )
        return StageExecutionResult(output_count=1, result={"is_open": True})

    async def _recommendation_context(self, trading_date: date):
        if "recommendation" in self.cache:
            return self.cache["recommendation"]
        service = CandidateRecommendationService(self.db)
        policy = await CandidateRecommendationPolicyRegistry(self.db).get_active()
        now = datetime.utcnow()
        universe = await service.build_universe_manifest(
            universe_date=trading_date,
            policy=policy,
            now=now,
        )
        context = {
            "service": service,
            "policy": policy,
            "universe": universe,
            "now": now,
        }
        self.cache["recommendation"] = context
        return context

    async def stage_security_master_sync(self, *, trading_date: date, **_):
        context = await self._recommendation_context(trading_date)
        data = RecommendationDataService(self.db)
        summary = await data.sync_full_market(
            universe=context["universe"],
            trade_date=trading_date,
            execute=True,
            now=context["now"],
        )
        context["sync"] = summary
        return StageExecutionResult(
            output_count=int(summary.get("provider_supported_count") or 0),
            result={
                "sync_run_id": summary.get("sync_run_id"),
                "provider_supported_count": summary.get("provider_supported_count", 0),
                "processed_count": summary.get("processed_count", 0),
                "created_count": summary.get("created_count", 0),
                "reused_count": summary.get("reused_count", 0),
                "failed_count": len(summary.get("failed_symbols") or []),
                "retry_count": summary.get("retry_count", 0),
            },
        )

    async def stage_raw_qfq_price_sync(self, *, trading_date: date, **_):
        context = await self._recommendation_context(trading_date)
        summary = context.get("sync") or self._stage_result("SECURITY_MASTER_SYNC")
        if not summary:
            raise DailyRunBlocked("PRICE_SYNC_MISSING", "证券和行情同步摘要不存在")
        return StageExecutionResult(
            output_count=int(summary.get("processed_count") or 0),
            result={
                "processed_symbol_count": summary.get("processed_count", 0),
                "failed_count": summary.get(
                    "failed_count", len(summary.get("failed_symbols") or [])
                ),
                "retry_count": summary.get("retry_count", 0),
            },
        )

    async def stage_benchmark_industry_sync(self, *, trading_date: date, **_):
        market = await ProductionMarketContextService(self.db).sync(
            trade_date=trading_date,
            execute=True,
            # The existing production fallback keeps BaoStock as the exact-date
            # universe source while fetching daily histories with bounded
            # parallelism. The sequential BaoStock history path cannot finish a
            # 5,000+ symbol production day within the governed stage timeout.
            provider=AKShareTencentMarketContextProvider(),
            timeout_seconds=DAILY_MARKET_CONTEXT_TIMEOUT_SECONDS,
        )
        industry_count = await self.db["stock_basic_info"].count_documents(
            {"industry": {"$nin": [None, ""]}}
        )
        return StageExecutionResult(
            output_count=1 + int(industry_count),
            result={
                "market_context_status": market.get("calculation_status"),
                "market_context_action": market.get("context_action"),
                "market_context_provider": market.get("provider"),
                "industry_mapping_count": industry_count,
                "industry_status": "READY" if industry_count else "DEGRADED_OPTIONAL",
            },
            message=(
                None
                if industry_count
                else "行业映射暂缺；当前推荐合同不把行业作为硬门禁"
            ),
        )

    async def _coverage(self, trading_date: date):
        context = await self._recommendation_context(trading_date)
        if "coverage" in context:
            return context["coverage"]
        service: CandidateRecommendationService = context["service"]
        data = RecommendationDataService(self.db)
        universe = await service.build_universe_manifest(
            universe_date=trading_date,
            policy=context["policy"],
            now=context["now"],
        )
        securities = {
            str(row.get("code") or row.get("symbol")): row
            for row in await service._load_universe_rows()
        }
        coverage = await data.prepare_coverage(
            universe=universe,
            securities=securities,
            policy=context["policy"],
            trade_date=trading_date,
            execute=True,
            now=context["now"],
            sync_summary=(
                context.get("sync")
                or self._stage_result("SECURITY_MASTER_SYNC")
                or None
            ),
        )
        context["coverage"] = coverage
        return coverage

    async def stage_trading_status_sync(self, *, trading_date: date, **_):
        coverage = await self._coverage(trading_date)
        return StageExecutionResult(
            output_count=coverage.trade_status_ready_count,
            result={
                "coverage_id": coverage.coverage_id,
                "trade_status_ready_count": coverage.trade_status_ready_count,
            },
        )

    async def stage_data_quality(self, *, trading_date: date, **_):
        coverage = await self._coverage(trading_date)
        if not coverage.recommendation_data_ready:
            raise DailyRunBlocked(
                "DATA_QUALITY_NOT_READY",
                "推荐最低数据合同覆盖率未达到版本化门槛",
            )
        return StageExecutionResult(
            output_count=coverage.data_quality_pass_count,
            result={
                "data_quality_pass_count": coverage.data_quality_pass_count,
                "failed_symbol_count": coverage.failed_symbol_count,
                "coverage_percentage": str(coverage.coverage_percentage),
            },
        )

    async def stage_recommendation_coverage(self, *, trading_date: date, **_):
        coverage = await self._coverage(trading_date)
        return StageExecutionResult(
            output_count=coverage.minimum_contract_ready_count,
            result={
                "coverage_status": coverage.status,
                "recommendation_data_ready": coverage.recommendation_data_ready,
                "ready_symbol_count": coverage.minimum_contract_ready_count,
            },
        )

    async def stage_full_market_recommendation(self, *, trading_date: date, **_):
        users = await self.db["users"].find(
            {"is_active": {"$ne": False}}
        ).to_list(length=None)
        service = CandidateRecommendationService(self.db)
        created = reused = recommendations = 0
        run_ids = []
        for user in users:
            user_id = str(user.get("_id") or user.get("id") or "")
            if not user_id:
                continue
            run, was_created = await service.run(
                user_id=user_id, trade_date=trading_date
            )
            run_ids.append(run.recommendation_run_id)
            recommendations += run.recommended_securities
            created += int(was_created)
            reused += int(not was_created)
        self.cache["recommendation_runs"] = run_ids
        return StageExecutionResult(
            output_count=recommendations,
            result={"created_runs": created, "reused_runs": reused, "run_ids": run_ids},
        )

    async def stage_candidate_snapshot(self, *, trading_date: date, daily_run_id: str, **_):
        users = await self.db["users"].find(
            {"is_active": {"$ne": False}}
        ).to_list(length=None)
        summaries = []
        cutoff = datetime.combine(trading_date, time(18, 30))
        for user in users:
            user_id = str(user.get("_id") or user.get("id") or "")
            if not user_id:
                continue
            rows = await self.db["ag_candidates"].find(
                {"user_id": user_id, "status": {"$ne": "REMOVED"}}
            ).sort("priority", -1).limit(50).to_list(length=50)
            symbols = sorted({str(row.get("symbol") or "") for row in rows if row.get("symbol")})
            if not symbols:
                continue
            summary = await ProductionObservationService(self.db).run(
                user_id=user_id,
                symbols=symbols,
                trade_date=trading_date,
                cutoff_at=cutoff,
                execute=True,
                trace_id=daily_run_id,
                minimum_symbols=1,
                maximum_symbols=50,
                run_model_chain=False,
            )
            summaries.append(summary)
        self.cache["observations"] = summaries
        snapshot_count = sum(
            item.get("snapshot_id") is not None
            for summary in summaries
            for item in summary.get("results", [])
        )
        proposal_count = sum(
            len(item.get("proposal_ids") or [])
            for summary in summaries
            for item in summary.get("results", [])
        )
        triggered_count = sum(summary.get("triggered_count", 0) for summary in summaries)
        decisions = [
            item
            for summary in summaries
            for item in summary.get("decisions", [])
        ]
        triggered_proposals = [
            {
                "user_id": str(summary.get("user_id") or ""),
                "proposal_ids": list(
                    summary.get("triggered_proposal_ids") or []
                ),
            }
            for summary in summaries
            if summary.get("triggered_proposal_ids")
        ]
        return StageExecutionResult(
            output_count=snapshot_count,
            result={
                "user_runs": len(summaries),
                "snapshot_count": snapshot_count,
                "proposal_count": proposal_count,
                "triggered_count": triggered_count,
                "triggered_proposals": triggered_proposals,
                "decision_count": len(decisions),
                "terminal_statuses": [
                    item.get("terminal_status") for item in decisions
                ],
                "execution_note": (
                    "Snapshot、Factor、Regime、Proposal与受门禁模型链来自同一次受控观察运行"
                ),
            },
        )

    async def stage_factor_regime(self, **_):
        summaries = self.cache.get("observations", [])
        proposal_count = sum(
            len(item.get("proposal_ids") or [])
            for summary in summaries
            for item in summary.get("results", [])
        )
        if not summaries:
            proposal_count = int(
                self._stage_result("CANDIDATE_SNAPSHOT").get("proposal_count") or 0
            )
        return StageExecutionResult(
            output_count=proposal_count,
            result={"factor_regime_objects": proposal_count},
        )

    async def stage_quant_proposal(self, **_):
        summaries = self.cache.get("observations", [])
        proposals = sum(
            len(item.get("proposal_ids") or [])
            for summary in summaries
            for item in summary.get("results", [])
        )
        triggered = sum(summary.get("triggered_count", 0) for summary in summaries)
        if not summaries:
            candidate_result = self._stage_result("CANDIDATE_SNAPSHOT")
            proposals = int(candidate_result.get("proposal_count") or 0)
            triggered = int(candidate_result.get("triggered_count") or 0)
        return StageExecutionResult(
            output_count=proposals,
            result={"proposal_count": proposals, "triggered_count": triggered},
        )

    async def stage_model_chain(self, *, daily_run_id: str | None = None, **_):
        summaries = self.cache.get("observations", [])
        candidate_result = self._stage_result("CANDIDATE_SNAPSHOT")
        triggered = (
            [
                {
                    "user_id": str(summary.get("user_id") or ""),
                    "proposal_ids": list(
                        summary.get("triggered_proposal_ids") or []
                    ),
                }
                for summary in summaries
                if summary.get("triggered_proposal_ids")
            ]
            if summaries
            else list(candidate_result.get("triggered_proposals") or [])
        )
        if not triggered:
            legacy_count = int(candidate_result.get("decision_count") or 0)
            legacy_statuses = list(
                candidate_result.get("terminal_statuses") or []
            )
            return StageExecutionResult(
                output_count=legacy_count,
                result={
                    "decision_count": legacy_count,
                    "terminal_statuses": legacy_statuses,
                    "provider_check": "NOT_REQUIRED",
                },
                message=(
                    "没有自然触发样本，按策略门禁未检查或调用模型"
                    if not legacy_count
                    else None
                ),
            )

        runtime = await ModelRuntimeStatusService(self.db).status(admin=True)
        required = {
            item["role"]: item
            for item in runtime.get("profiles", [])
            if item.get("role")
            in {"RESEARCH_AGENT", "NORMAL_TRADER", "TOP_RISK_REVIEWER"}
        }
        budget = dict(runtime.get("budget") or {})
        if (
            runtime.get("status") != "READY"
            or len(required) != 3
            or any(
                not item.get("configured")
                or item.get("capability") != "READY"
                for item in required.values()
            )
            or int(budget.get("remaining_calls") or 0) <= 0
            or float(budget.get("remaining_cost") or 0) <= 0
        ):
            raise DailyRunBlocked(
                "MODEL_PROVIDER_UNAVAILABLE",
                "Research、Normal或Top Provider未就绪；"
                "MODEL_CHAIN安全阻断，overall_status=DEGRADED_PAPER",
            )

        decisions = []
        for item in triggered:
            user_id = str(item.get("user_id") or "")
            proposal_ids = [
                str(value) for value in item.get("proposal_ids") or []
            ]
            if not user_id or not proposal_ids:
                raise DailyRunBlocked(
                    "MODEL_STAGE_INPUT_INVALID",
                    "自然触发样本缺少模型阶段的精确用户或Proposal绑定",
                )
            current = await ProductionObservationService(
                self.db
            ).evaluate_triggered_proposals(
                user_id=user_id,
                proposal_ids=proposal_ids,
                trace_id=str(daily_run_id or "alphaguard-daily-model-stage"),
            )
            decisions.extend(current)
            failed = next(
                (
                    value
                    for value in current
                    if value.get("terminal_status")
                    in {
                        "NORMAL_MODEL_FAILED",
                        "TOP_MODEL_FAILED",
                        "CONSENSUS_INVALID",
                    }
                ),
                None,
            )
            if failed:
                raise DailyRunBlocked(
                    "MODEL_PROVIDER_UNAVAILABLE",
                    "模型调用未满足受控输出合同；"
                    "MODEL_CHAIN安全阻断，overall_status=DEGRADED_PAPER",
                )
        terminal_statuses = [
            item.get("terminal_status") for item in decisions
        ]
        return StageExecutionResult(
            output_count=len(decisions),
            result={
                "decision_count": len(decisions),
                "terminal_statuses": terminal_statuses,
                "provider_check": "READY",
            },
        )

    async def stage_order_intent(self, *, daily_run_id: str, **_):
        service = PaperTaskService(self.db)
        result = await service.run_once(
            job_type="process_execution_outbox",
            trade_date=None,
            idempotency_key=f"daily:{daily_run_id}:process_execution_outbox",
            operation=service.process_execution_outbox,
        )
        count = sum(int(value or 0) for value in result.values()) if isinstance(result, dict) else int(result or 0)
        return StageExecutionResult(output_count=count, result={"outbox": result})

    async def stage_t1_order_processing(self, *, trading_date: date, **_):
        service = PaperTaskService(self.db)
        unlocked = await service.run_once(
            job_type="roll_position_lot_availability",
            trade_date=trading_date,
            idempotency_key=f"daily:{trading_date}:roll_position_lot_availability",
            operation=lambda: service.roll_position_lot_availability(trading_date),
        )
        snapshots = await service.run_once(
            job_type="build_execution_market_snapshots",
            trade_date=trading_date,
            idempotency_key=f"daily:{trading_date}:build_execution_market_snapshots",
            operation=lambda: service.build_execution_market_snapshots(trading_date),
        )
        expired = await service.run_once(
            job_type="expire_orders",
            trade_date=trading_date,
            idempotency_key=f"daily:{trading_date}:expire_orders",
            operation=service.expire_orders,
        )
        released = await service.run_once(
            job_type="release_stale_reservations",
            trade_date=trading_date,
            idempotency_key=f"daily:{trading_date}:release_stale_reservations",
            operation=service.release_stale_reservations,
        )
        return StageExecutionResult(
            output_count=int(unlocked or 0) + int(expired or 0) + int(released or 0),
            result={
                "lots_unlocked": unlocked,
                "execution_snapshots": snapshots,
                "orders_expired": expired,
                "reservations_released": released,
            },
        )

    async def stage_matching_settlement(self, *, trading_date: date, **_):
        service = PaperTaskService(self.db)
        matched = await service.run_once(
            job_type="match_orders_for_trade_date",
            trade_date=trading_date,
            idempotency_key=f"daily:{trading_date}:match_orders_for_trade_date",
            operation=lambda: service.match_orders_for_trade_date(trading_date),
        )
        settled = await service.run_once(
            job_type="settle_pending_fills",
            trade_date=trading_date,
            idempotency_key=f"daily:{trading_date}:settle_pending_fills",
            operation=service.settle_pending_fills,
        )
        snapshots = await service.run_once(
            job_type="create_daily_account_snapshots",
            trade_date=trading_date,
            idempotency_key=f"daily:{trading_date}:create_daily_account_snapshots",
            operation=lambda: service.create_daily_account_snapshots(trading_date),
        )
        return StageExecutionResult(
            output_count=int((matched or {}).get("fills", 0)),
            result={"matching": matched, "settlement": settled, "account_snapshots": snapshots},
        )

    async def stage_evaluation(self, *, trading_date: date, **_):
        pipeline = EvaluationPipeline(self.db)
        run, created = await pipeline.schedule(
            as_of_trade_date=trading_date, user_id=None
        )
        evaluated = await pipeline.evaluate_trade_date(
            as_of_trade_date=trading_date, user_id=None
        )
        scheduled = {
            "evaluation_job_id": run.evaluation_job_id,
            "status": run.status,
            "created": created,
        }
        processed = {
            "completed": 1,
            "result": evaluated.model_dump(mode="python"),
        }
        return StageExecutionResult(
            output_count=int(processed.get("completed", 0)),
            result={"scheduled": scheduled, "processed": processed},
        )

    async def stage_attribution(self, **_):
        latest = clean_document(
            await self.db["ag_eval_runs"].find_one({}, sort=[("created_at", -1)])
        )
        return StageExecutionResult(
            output_count=await self.db["ag_eval_attributions"].count_documents({}),
            result={"evaluation_job_id": (latest or {}).get("evaluation_job_id")},
        )

    async def stage_challenger(self, *, trading_date: date, **_):
        from app.services.alphaguard.paper_challenger_scheduler_service import (
            PaperChallengerSchedulerService,
        )
        from app.services.alphaguard.experiment_task_service import ExperimentTaskService

        scheduled = await PaperChallengerSchedulerService(self.db).enqueue_for_trade_date(
            trading_date
        )
        processed = await ExperimentTaskService(self.db).process(
            job_types={"PAPER_CHALLENGER"}, limit=1
        )
        return StageExecutionResult(
            output_count=sum(int(value or 0) for value in processed.values()),
            result={"scheduled": scheduled, "processed": processed},
        )

    async def stage_operations_summary(self, **_):
        service = AlphaGuardOperationsService(
            self.db, redis_client=self.redis, scheduler=self.scheduler
        )
        readiness = await service.readiness()
        integrity = await service.integrity()
        reconciliation = await PaperTaskService(self.db).reconcile_paper_accounts()
        if integrity["status"] == "FAIL":
            raise DailyRunBlocked("INTEGRITY_FAILED", "一致性检查失败，通知前安全停止")
        return StageExecutionResult(
            output_count=len(readiness.job_health),
            result={
                "overall_status": readiness.overall_status,
                "integrity_status": integrity["status"],
                "reconciliation": reconciliation,
            },
        )

    async def stage_notification(self, *, trading_date: date, daily_run_id: str, **_):
        from app.routers.websocket_notifications import send_notification_via_websocket
        from app.utils.timezone import now_tz

        users = await self.db["users"].find(
            {"is_active": {"$ne": False}}
        ).to_list(length=None)
        sent = 0
        for user in users:
            user_id = str(user.get("_id") or user.get("id") or "")
            if not user_id:
                continue
            try:
                document = {
                    "user_id": user_id,
                    "type": "system",
                    "title": "AlphaGuard每日运行完成",
                    "content": f"{trading_date.isoformat()}盘后流程已完成。",
                    "link": "/alphaguard/operations",
                    "source": "alphaguard_daily_run",
                    "severity": "info",
                    "status": "unread",
                    "created_at": now_tz(),
                    "metadata": {"daily_run_id": daily_run_id},
                }
                inserted = await self.db["notifications"].insert_one(document)
                await send_notification_via_websocket(
                    user_id,
                    {
                        "id": str(inserted.inserted_id),
                        **{
                            key: document[key]
                            for key in ("type", "title", "content", "link", "source", "status")
                        },
                        "created_at": document["created_at"].isoformat(),
                    },
                )
                sent += 1
            except Exception:
                # Notifications are deliberately non-core and cannot change the
                # already completed decision, risk or order result.
                continue
        return StageExecutionResult(
            output_count=sent,
            result={"sent": sent, "degraded": sent < len(users)},
            message=("通知服务降级，不影响核心交易安全链" if sent < len(users) else None),
        )
