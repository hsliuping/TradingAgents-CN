"""Authenticated, non-secret AlphaGuard operations API."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_mongo_db, get_redis_client
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.operations_alert_service import OperationsAlertService
from app.services.alphaguard.operations_job_service import (
    ALLOWED_OPERATIONS_JOBS,
    OperationsJobService,
)
from app.services.alphaguard.operations_service import (
    AlphaGuardOperationsService,
)
from app.services.alphaguard.paper_storage import clean_document


router = APIRouter(prefix="/alphaguard/operations", tags=["alphaguard-operations"])


class _StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobRunBody(_StrictBody):
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
    as_of_trade_date: date | None = None


class AlertResolutionBody(_StrictBody):
    resolution_note: str = Field(min_length=3, max_length=1000)


def _require_admin(user: dict) -> None:
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="仅管理员可以执行系统运维写操作")


def get_operations_service() -> AlphaGuardOperationsService:
    from app.services.scheduler_service import _scheduler_instance

    return AlphaGuardOperationsService(
        get_mongo_db(),
        redis_client=get_redis_client(),
        scheduler=_scheduler_instance,
    )


def get_operations_job_service() -> OperationsJobService:
    from app.services.scheduler_service import _scheduler_instance

    return OperationsJobService(
        get_mongo_db(),
        redis_client=get_redis_client(),
        scheduler=_scheduler_instance,
    )


@router.get("/overview", response_model=dict)
async def operations_overview(
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    return ok(await service.overview(), "AlphaGuard 运维总览")


@router.get("/readiness", response_model=dict)
async def operations_readiness(
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    report = await service.readiness()
    return ok(report.model_dump(mode="json"), "AlphaGuard 业务准备度")


@router.get("/services", response_model=dict)
async def operations_services(
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    items = await service.service_health()
    return ok({"items": [item.model_dump(mode="json") for item in items]})


@router.get("/data-readiness", response_model=dict)
async def operations_data_readiness(
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    items = await service.data_readiness()
    return ok({"items": [item.model_dump(mode="json") for item in items]})


@router.get("/jobs", response_model=dict)
async def operations_jobs(
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    items = await service.job_health()
    return ok(
        {
            "items": [item.model_dump(mode="json") for item in items],
            "allowed_manual_jobs": (
                sorted(ALLOWED_OPERATIONS_JOBS)
                if current_user.get("is_admin")
                else []
            ),
        }
    )


@router.get("/jobs/{job_name}", response_model=dict)
async def operations_job(
    job_name: str,
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    jobs = await service.job_health()
    match = next(
        (item for item in jobs if item.job_name == job_name),
        None,
    )
    manual_name = job_name.upper()
    if match is None and manual_name not in ALLOWED_OPERATIONS_JOBS:
        raise HTTPException(status_code=404, detail="运维任务不存在")
    history = await get_mongo_db()["ag_ops_job_requests"].find(
        {"job_name": manual_name}
    ).sort("created_at", -1).limit(20).to_list(length=20)
    return ok(
        {
            "health": match.model_dump(mode="json") if match else None,
            "manual_job_name": (
                manual_name if manual_name in ALLOWED_OPERATIONS_JOBS else None
            ),
            "history": [clean_document(row) for row in history],
        }
    )


@router.get("/alerts", response_model=dict)
async def operations_alerts(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    items = await OperationsAlertService(get_mongo_db()).list(
        status=status,
        severity=severity,
        limit=limit,
    )
    return ok({"items": [item.model_dump(mode="json") for item in items]})


@router.get("/alerts/{alert_id}", response_model=dict)
async def operations_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        item = await OperationsAlertService(get_mongo_db()).get(alert_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item.model_dump(mode="json"))


@router.get("/audit", response_model=dict)
async def operations_audit(
    trace_id: str | None = None,
    snapshot_id: str | None = None,
    analysis_id: str | None = None,
    order_id: str | None = None,
    experiment_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    query = {
        key: value
        for key, value in {
            "trace_id": trace_id,
            "snapshot_id": snapshot_id,
            "analysis_id": analysis_id,
            "order_id": order_id,
            "experiment_id": experiment_id,
        }.items()
        if value
    }
    collections = (
        "ag_ops_events",
        "ag_candidate_events",
        "ag_quant_audit_events",
        "ag_decision_events",
        "ag_paper_events",
        "ag_eval_events",
        "ag_exp_events",
    )
    events: list[dict[str, Any]] = []
    db = get_mongo_db()
    for name in collections:
        rows = await db[name].find(query).sort("created_at", -1).limit(
            limit
        ).to_list(length=limit)
        for raw in rows:
            item = clean_document(raw)
            item["collection"] = name
            events.append(item)
    events.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return ok({"items": events[:limit]})


@router.get("/versions", response_model=dict)
async def operations_versions(
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    return ok(await service.versions())


@router.get("/integrity", response_model=dict)
async def operations_integrity(
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    return ok(await service.integrity())


@router.get("/mvp-acceptance", response_model=dict)
async def operations_mvp_acceptance(
    current_user: dict = Depends(get_current_user),
    service: AlphaGuardOperationsService = Depends(get_operations_service),
):
    from app.services.alphaguard.mvp_acceptance_service import MvpAcceptanceService

    report = await MvpAcceptanceService(
        get_mongo_db(), operations_service=service
    ).report(persist=False)
    return ok(report.model_dump(mode="json"), "AlphaGuard MVP验收状态")


@router.post("/check", response_model=dict)
async def operations_check(
    current_user: dict = Depends(get_current_user),
    jobs: OperationsJobService = Depends(get_operations_job_service),
):
    _require_admin(current_user)
    request, created = await jobs.enqueue(
        "HEALTH_CHECK", requested_by=str(current_user["id"])
    )
    return ok(
        {"job": request.model_dump(mode="json"), "created": created},
        "健康检查已进入幂等运维队列",
    )


@router.post("/jobs/{job_name}/run", response_model=dict)
async def operations_run_job(
    job_name: str,
    body: JobRunBody,
    current_user: dict = Depends(get_current_user),
    jobs: OperationsJobService = Depends(get_operations_job_service),
):
    _require_admin(current_user)
    payload = (
        {"as_of_trade_date": body.as_of_trade_date.isoformat()}
        if body.as_of_trade_date
        else {}
    )
    try:
        request, created = await jobs.enqueue(
            job_name,
            requested_by=str(current_user["id"]),
            idempotency_key=body.idempotency_key,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(
        {"job": request.model_dump(mode="json"), "created": created},
        "受控任务已进入幂等队列",
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=dict)
async def operations_acknowledge_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        alert = await OperationsAlertService(get_mongo_db()).acknowledge(
            alert_id, actor_id=str(current_user["id"])
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(alert.model_dump(mode="json"), "告警已确认并追加审计")


@router.post("/alerts/{alert_id}/resolve", response_model=dict)
async def operations_resolve_alert(
    alert_id: str,
    body: AlertResolutionBody,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        alert = await OperationsAlertService(get_mongo_db()).resolve(
            alert_id,
            actor_id=str(current_user["id"]),
            resolution_note=body.resolution_note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(alert.model_dump(mode="json"), "告警已解决并追加审计")


@router.post("/reconcile", response_model=dict)
async def operations_reconcile(
    current_user: dict = Depends(get_current_user),
    jobs: OperationsJobService = Depends(get_operations_job_service),
):
    _require_admin(current_user)
    request, created = await jobs.enqueue(
        "PAPER_RECONCILIATION",
        requested_by=str(current_user["id"]),
    )
    return ok(
        {"job": request.model_dump(mode="json"), "created": created},
        "账户完整性核对已进入幂等队列",
    )
