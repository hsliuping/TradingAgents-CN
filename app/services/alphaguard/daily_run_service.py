"""Dependency-aware, resumable AlphaGuard post-market daily orchestration."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Protocol
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.operations_schemas import operations_hash
from tradingagents.alphaguard.release_schemas import DailyRunSummary, DailyStageRun


@dataclass(frozen=True)
class DailyStageSpec:
    stage_id: str
    stage_name: str
    category: str
    dependencies: tuple[str, ...] = ()


DAILY_STAGE_SPECS: tuple[DailyStageSpec, ...] = (
    DailyStageSpec("TRADING_CALENDAR", "交易日历确认", "数据同步"),
    DailyStageSpec("SECURITY_MASTER_SYNC", "证券基础数据同步", "数据同步", ("TRADING_CALENDAR",)),
    DailyStageSpec("RAW_QFQ_PRICE_SYNC", "RAW/QFQ行情同步", "数据同步", ("SECURITY_MASTER_SYNC",)),
    DailyStageSpec("BENCHMARK_INDUSTRY_SYNC", "基准和行业数据同步", "数据同步", ("RAW_QFQ_PRICE_SYNC",)),
    DailyStageSpec("TRADING_STATUS_SYNC", "交易状态同步", "数据同步", ("BENCHMARK_INDUSTRY_SYNC",)),
    DailyStageSpec("DATA_QUALITY", "DataQuality检查", "数据同步", ("TRADING_STATUS_SYNC",)),
    DailyStageSpec("RECOMMENDATION_COVERAGE", "推荐数据覆盖检查", "推荐", ("DATA_QUALITY",)),
    DailyStageSpec("FULL_MARKET_RECOMMENDATION", "全市场推荐", "推荐", ("RECOMMENDATION_COVERAGE",)),
    DailyStageSpec("CANDIDATE_SNAPSHOT", "候选池Snapshot", "候选池", ("FULL_MARKET_RECOMMENDATION",)),
    DailyStageSpec("FACTOR_REGIME", "Factor与Regime", "决策", ("CANDIDATE_SNAPSHOT",)),
    DailyStageSpec("QUANT_PROPOSAL", "QuantProposal", "决策", ("FACTOR_REGIME",)),
    DailyStageSpec("MODEL_CHAIN", "TradingAgents与双模型链", "模型", ("QUANT_PROPOSAL",)),
    DailyStageSpec("ORDER_INTENT", "OrderIntent安全门", "风控", ("MODEL_CHAIN",)),
    DailyStageSpec("T1_ORDER_PROCESSING", "次交易日模拟订单处理", "订单", ("ORDER_INTENT",)),
    DailyStageSpec("MATCHING_SETTLEMENT", "成交与结算", "订单", ("T1_ORDER_PROCESSING",)),
    DailyStageSpec("EVALUATION", "Evaluation", "评价", ("MATCHING_SETTLEMENT",)),
    DailyStageSpec("ATTRIBUTION", "Attribution", "评价", ("EVALUATION",)),
    DailyStageSpec("CHALLENGER", "Challenger任务", "评价", ("ATTRIBUTION",)),
    DailyStageSpec("OPERATIONS_SUMMARY", "Operations汇总", "异常", ("CHALLENGER",)),
    DailyStageSpec("NOTIFICATION", "通知", "异常", ("OPERATIONS_SUMMARY",)),
)

STAGE_BY_ID = {item.stage_id: item for item in DAILY_STAGE_SPECS}
SUCCESS_STATUSES = {"SUCCESS", "REUSED", "SKIPPED"}


@dataclass(frozen=True)
class StageExecutionResult:
    output_count: int = 0
    result: dict[str, Any] | None = None
    status: str = "SUCCESS"
    message: str | None = None
    skip_remaining: bool = False


class DailyStageExecutor(Protocol):
    async def execute(
        self,
        stage: DailyStageSpec,
        *,
        trading_date: date,
        input_version: str,
        daily_run_id: str,
    ) -> StageExecutionResult | dict[str, Any] | int | None: ...


class CallbackStageExecutor:
    """Small adapter used by isolated acceptance scenarios and tests."""

    def __init__(self, callbacks: dict[str, Callable[..., Any]]):
        self.callbacks = callbacks

    async def execute(self, stage: DailyStageSpec, **kwargs):
        callback = self.callbacks.get(stage.stage_id)
        if callback is None:
            return StageExecutionResult(result={"action": "NOOP"})
        value = callback(stage=stage, **kwargs)
        return await value if inspect.isawaitable(value) else value


class DailyRunBlocked(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AlphaGuardDailyRunService:
    COLLECTION = "ag_daily_job_runs"

    def __init__(self, db, *, executor: DailyStageExecutor):
        self.db = db
        self.executor = executor

    async def _restore_executor_state(
        self,
        stage: DailyStageSpec,
        stage_run: DailyStageRun,
        *,
        trading_date: date,
        input_version: str,
        daily_run_id: str,
    ) -> None:
        restore = getattr(self.executor, "restore", None)
        if restore is None:
            return
        value = restore(
            stage,
            stage_run=stage_run,
            trading_date=trading_date,
            input_version=input_version,
            daily_run_id=daily_run_id,
        )
        if inspect.isawaitable(value):
            await value

    @staticmethod
    def daily_run_id(trading_date: date, input_version: str) -> str:
        identity = f"{trading_date.isoformat()}:{input_version}"
        return str(uuid5(NAMESPACE_URL, f"alphaguard:daily-run:{identity}"))

    @staticmethod
    def _identity(
        stage: DailyStageSpec, trading_date: date, input_version: str
    ) -> tuple[str, str, str]:
        input_hash = operations_hash(
            {
                "stage_id": stage.stage_id,
                "trading_date": trading_date.isoformat(),
                "input_version": input_version,
            }
        )
        idempotency_key = (
            f"alphaguard:daily:{trading_date.isoformat()}:"
            f"{input_version}:{stage.stage_id}:{input_hash}"
        )
        job_id = str(uuid5(NAMESPACE_URL, idempotency_key))
        return input_hash, idempotency_key, job_id

    @staticmethod
    def _range(from_stage: str | None, to_stage: str | None) -> tuple[int, int]:
        ids = [item.stage_id for item in DAILY_STAGE_SPECS]
        if from_stage and from_stage not in STAGE_BY_ID:
            raise ValueError(f"unknown --from-stage: {from_stage}")
        if to_stage and to_stage not in STAGE_BY_ID:
            raise ValueError(f"unknown --to-stage: {to_stage}")
        start = ids.index(from_stage) if from_stage else 0
        end = ids.index(to_stage) if to_stage else len(ids) - 1
        if start > end:
            raise ValueError("--from-stage must not be after --to-stage")
        return start, end

    async def status(
        self, *, trading_date: date, input_version: str
    ) -> DailyRunSummary:
        run_id = self.daily_run_id(trading_date, input_version)
        rows = await self.db[self.COLLECTION].find(
            {"daily_run_id": run_id}
        ).to_list(length=None)
        if not rows:
            return DailyRunSummary(
                daily_run_id=run_id,
                trading_date=trading_date,
                input_version=input_version,
                status="NOT_FOUND",
            )
        order = {item.stage_id: index for index, item in enumerate(DAILY_STAGE_SPECS)}
        stages = [DailyStageRun.model_validate(clean_document(row)) for row in rows]
        stages.sort(key=lambda item: order[item.stage_id])
        failed = next((item for item in stages if item.status == "FAILED"), None)
        blocked = next((item for item in stages if item.status == "BLOCKED"), None)
        status = "FAILED" if failed else "BLOCKED" if blocked else "SUCCESS"
        return DailyRunSummary(
            daily_run_id=run_id,
            trading_date=trading_date,
            input_version=input_version,
            status=status,
            stages=stages,
            created_count=sum(item.status == "SUCCESS" for item in stages),
            reused_count=sum(item.status == "REUSED" for item in stages),
            failed_stage_id=(failed or blocked).stage_id if (failed or blocked) else None,
            blocking_reason=(failed or blocked).sanitized_message if (failed or blocked) else None,
        )

    async def run(
        self,
        *,
        trading_date: date,
        input_version: str,
        dry_run: bool = False,
        resume: bool = False,
        from_stage: str | None = None,
        to_stage: str | None = None,
        interrupt_before_stage: str | None = None,
    ) -> DailyRunSummary:
        start, end = self._range(from_stage, to_stage)
        selected = DAILY_STAGE_SPECS[start : end + 1]
        run_id = self.daily_run_id(trading_date, input_version)
        if dry_run:
            planned = []
            for stage in selected:
                input_hash, key, job_id = self._identity(
                    stage, trading_date, input_version
                )
                planned.append(
                    DailyStageRun(
                        job_id=job_id,
                        daily_run_id=run_id,
                        stage_id=stage.stage_id,
                        stage_name=stage.stage_name,
                        trading_date=trading_date,
                        input_version=input_version,
                        input_hash=input_hash,
                        status="SKIPPED",
                        error_code="DRY_RUN",
                        sanitized_message="dry-run：仅展示计划，不写数据库或创建业务对象",
                        idempotency_key=key,
                        dependency_stage_ids=list(stage.dependencies),
                        result={"category": stage.category, "planned": True},
                    )
                )
            return DailyRunSummary(
                daily_run_id=run_id,
                trading_date=trading_date,
                input_version=input_version,
                status="DRY_RUN",
                stages=planned,
            )

        completed: dict[str, DailyStageRun] = {}
        output: list[DailyStageRun] = []
        skip_reason: str | None = None
        for stage in selected:
            input_hash, key, job_id = self._identity(stage, trading_date, input_version)
            existing_raw = await self.db[self.COLLECTION].find_one(
                {"idempotency_key": key}
            )
            existing = (
                DailyStageRun.model_validate(clean_document(existing_raw))
                if existing_raw
                else None
            )
            if existing and existing.status in SUCCESS_STATUSES:
                reused = existing.model_copy(
                    update={
                        "status": "REUSED",
                        "completed_at": datetime.utcnow(),
                        "reuse_count": existing.reuse_count + 1,
                        "error_code": None,
                        "sanitized_message": "相同交易日和输入版本已完成，复用既有结果",
                    }
                )
                await self.db[self.COLLECTION].replace_one(
                    {"idempotency_key": key}, model_document(reused)
                )
                await self._restore_executor_state(
                    stage,
                    reused,
                    trading_date=trading_date,
                    input_version=input_version,
                    daily_run_id=run_id,
                )
                completed[stage.stage_id] = reused
                output.append(reused)
                continue
            if existing and existing.status in {"FAILED", "BLOCKED", "RUNNING"} and not resume:
                blocked = existing.model_copy(
                    update={
                        "status": "BLOCKED",
                        "completed_at": datetime.utcnow(),
                        "error_code": "RESUME_REQUIRED",
                        "sanitized_message": "检测到未完成阶段；请使用 --resume 从安全断点恢复",
                    }
                )
                await self.db[self.COLLECTION].replace_one(
                    {"idempotency_key": key}, model_document(blocked)
                )
                output.append(blocked)
                return self._summary(run_id, trading_date, input_version, output, blocked)

            missing = []
            for dependency in stage.dependencies:
                candidate = completed.get(dependency)
                if candidate is None:
                    dependency_stage = STAGE_BY_ID[dependency]
                    _hash, dependency_key, _job = self._identity(
                        dependency_stage, trading_date, input_version
                    )
                    raw = await self.db[self.COLLECTION].find_one(
                        {"idempotency_key": dependency_key}
                    )
                    candidate = (
                        DailyStageRun.model_validate(clean_document(raw)) if raw else None
                    )
                    if candidate is not None and candidate.status in SUCCESS_STATUSES:
                        await self._restore_executor_state(
                            dependency_stage,
                            candidate,
                            trading_date=trading_date,
                            input_version=input_version,
                            daily_run_id=run_id,
                        )
                if candidate is None or candidate.status not in SUCCESS_STATUSES:
                    missing.append(dependency)
            if missing:
                blocked = DailyStageRun(
                    job_id=job_id,
                    daily_run_id=run_id,
                    stage_id=stage.stage_id,
                    stage_name=stage.stage_name,
                    trading_date=trading_date,
                    input_version=input_version,
                    input_hash=input_hash,
                    status="BLOCKED",
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    retry_count=(existing.retry_count + 1 if existing else 0),
                    error_code="DEPENDENCY_NOT_COMPLETED",
                    sanitized_message=f"依赖未完成：{','.join(missing)}",
                    idempotency_key=key,
                    dependency_stage_ids=list(stage.dependencies),
                )
                await self.db[self.COLLECTION].replace_one(
                    {"idempotency_key": key}, model_document(blocked), upsert=True
                )
                output.append(blocked)
                return self._summary(run_id, trading_date, input_version, output, blocked)

            if skip_reason:
                skipped = DailyStageRun(
                    job_id=job_id,
                    daily_run_id=run_id,
                    stage_id=stage.stage_id,
                    stage_name=stage.stage_name,
                    trading_date=trading_date,
                    input_version=input_version,
                    input_hash=input_hash,
                    status="SKIPPED",
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    error_code="UPSTREAM_SKIP",
                    sanitized_message=skip_reason,
                    idempotency_key=key,
                    dependency_stage_ids=list(stage.dependencies),
                )
                await self.db[self.COLLECTION].replace_one(
                    {"idempotency_key": key}, model_document(skipped), upsert=True
                )
                completed[stage.stage_id] = skipped
                output.append(skipped)
                continue

            if interrupt_before_stage == stage.stage_id:
                raise RuntimeError(f"simulated interruption before {stage.stage_id}")

            now = datetime.utcnow()
            running = DailyStageRun(
                job_id=job_id,
                daily_run_id=run_id,
                stage_id=stage.stage_id,
                stage_name=stage.stage_name,
                trading_date=trading_date,
                input_version=input_version,
                input_hash=input_hash,
                status="RUNNING",
                started_at=now,
                retry_count=(existing.retry_count + 1 if existing else 0),
                reuse_count=(existing.reuse_count if existing else 0),
                idempotency_key=key,
                dependency_stage_ids=list(stage.dependencies),
                result={"category": stage.category},
            )
            await self.db[self.COLLECTION].replace_one(
                {"idempotency_key": key}, model_document(running), upsert=True
            )
            try:
                raw_result = await self.executor.execute(
                    stage,
                    trading_date=trading_date,
                    input_version=input_version,
                    daily_run_id=run_id,
                )
                result = self._normalize_result(raw_result)
                if result.status not in SUCCESS_STATUSES:
                    raise DailyRunBlocked(
                        "STAGE_BLOCKED", result.message or "阶段未满足继续条件"
                    )
                terminal = running.model_copy(
                    update={
                        "status": result.status,
                        "completed_at": datetime.utcnow(),
                        "output_count": result.output_count,
                        "result": {"category": stage.category, **(result.result or {})},
                        "sanitized_message": result.message,
                    }
                )
                if result.skip_remaining:
                    skip_reason = result.message or "上游阶段要求安全停止"
            except Exception as exc:
                terminal = running.model_copy(
                    update={
                        "status": (
                            "BLOCKED" if isinstance(exc, DailyRunBlocked) else "FAILED"
                        ),
                        "completed_at": datetime.utcnow(),
                        "error_code": getattr(exc, "code", type(exc).__name__.upper()),
                        "sanitized_message": f"{type(exc).__name__}: {str(exc)}",
                    }
                )
            await self.db[self.COLLECTION].replace_one(
                {"idempotency_key": key}, model_document(terminal), upsert=True
            )
            completed[stage.stage_id] = terminal
            output.append(terminal)
            if terminal.status not in SUCCESS_STATUSES:
                output.extend(
                    await self._block_remaining(
                        selected=selected,
                        failed_stage=stage,
                        trading_date=trading_date,
                        input_version=input_version,
                        daily_run_id=run_id,
                        reason=terminal.sanitized_message or terminal.status,
                    )
                )
                return self._summary(run_id, trading_date, input_version, output, terminal)

        return self._summary(run_id, trading_date, input_version, output, None)

    async def _block_remaining(
        self,
        *,
        selected: tuple[DailyStageSpec, ...],
        failed_stage: DailyStageSpec,
        trading_date: date,
        input_version: str,
        daily_run_id: str,
        reason: str,
    ) -> list[DailyStageRun]:
        failed_index = selected.index(failed_stage)
        blocked_rows: list[DailyStageRun] = []
        for stage in selected[failed_index + 1 :]:
            input_hash, key, job_id = self._identity(
                stage, trading_date, input_version
            )
            existing_raw = await self.db[self.COLLECTION].find_one(
                {"idempotency_key": key}
            )
            existing = (
                DailyStageRun.model_validate(clean_document(existing_raw))
                if existing_raw
                else None
            )
            if existing and existing.status in SUCCESS_STATUSES:
                continue
            now = datetime.utcnow()
            blocked = DailyStageRun(
                job_id=job_id,
                daily_run_id=daily_run_id,
                stage_id=stage.stage_id,
                stage_name=stage.stage_name,
                trading_date=trading_date,
                input_version=input_version,
                input_hash=input_hash,
                status="BLOCKED",
                started_at=now,
                completed_at=now,
                retry_count=existing.retry_count if existing else 0,
                reuse_count=existing.reuse_count if existing else 0,
                error_code="UPSTREAM_NOT_COMPLETED",
                sanitized_message=(
                    f"上游阶段 {failed_stage.stage_id} 未完成：{reason}"
                ),
                idempotency_key=key,
                dependency_stage_ids=list(stage.dependencies),
                result={"category": stage.category},
            )
            await self.db[self.COLLECTION].replace_one(
                {"idempotency_key": key}, model_document(blocked), upsert=True
            )
            blocked_rows.append(blocked)
        return blocked_rows

    @staticmethod
    def _normalize_result(value: Any) -> StageExecutionResult:
        if isinstance(value, StageExecutionResult):
            return value
        if value is None:
            return StageExecutionResult()
        if isinstance(value, int):
            return StageExecutionResult(output_count=max(0, value))
        if isinstance(value, dict):
            return StageExecutionResult(
                output_count=max(0, int(value.get("output_count", 0))),
                result={key: item for key, item in value.items() if key != "output_count"},
            )
        raise TypeError(f"unsupported stage result: {type(value).__name__}")

    @staticmethod
    def _summary(run_id, trading_date, input_version, stages, terminal):
        failed = terminal if terminal and terminal.status == "FAILED" else None
        blocked = terminal if terminal and terminal.status == "BLOCKED" else None
        return DailyRunSummary(
            daily_run_id=run_id,
            trading_date=trading_date,
            input_version=input_version,
            status="FAILED" if failed else "BLOCKED" if blocked else "SUCCESS",
            stages=stages,
            created_count=sum(item.status == "SUCCESS" for item in stages),
            reused_count=sum(item.status == "REUSED" for item in stages),
            failed_stage_id=terminal.stage_id if terminal else None,
            blocking_reason=terminal.sanitized_message if terminal else None,
        )
