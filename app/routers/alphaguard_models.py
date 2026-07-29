"""Authenticated, non-secret PR-010 model runtime API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.model_capability_service import (
    ModelCapabilityService,
)
from app.services.alphaguard.model_profile_registry import ModelProfileRegistry
from app.services.alphaguard.model_runtime_repository import (
    ModelRuntimeRepository,
)
from app.services.alphaguard.model_runtime_status_service import (
    ModelRuntimeStatusService,
)
from app.services.alphaguard.prompt_profile_registry import PromptProfileRegistry
from app.services.alphaguard.real_model_validation_service import (
    RealModelValidationService,
)


router = APIRouter(prefix="/alphaguard/models", tags=["alphaguard-models"])


class _StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilityCheckBody(_StrictBody):
    profile_id: str = Field(min_length=1, max_length=100)
    profile_version: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=8, max_length=200)
    network: bool = False


class ValidationRunBody(_StrictBody):
    idempotency_key: str = Field(min_length=8, max_length=200)
    proposal_id: str | None = Field(default=None, min_length=1, max_length=200)
    user_id: str | None = Field(default=None, min_length=1, max_length=200)
    confirmation_text: str = Field(min_length=1, max_length=100)


def _require_admin(user: dict[str, Any]) -> None:
    if not user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="仅管理员可以执行模型能力检查或验证运行",
        )


def _actor(user: dict[str, Any]) -> str:
    return str(
        user.get("user_id")
        or user.get("id")
        or user.get("username")
        or "authenticated-user"
    )


@router.get("/profiles", response_model=dict)
async def model_profiles(
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    status = await ModelRuntimeStatusService(db).status(
        admin=bool(current_user.get("is_admin", False))
    )
    return ok({"items": status["profiles"], "status": status["status"]})


@router.get("/profiles/{profile_id}", response_model=dict)
async def model_profile(
    profile_id: str,
    profile_version: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user),
):
    status = await ModelRuntimeStatusService(get_mongo_db()).status(
        admin=bool(current_user.get("is_admin", False))
    )
    item = next(
        (
            value
            for value in status["profiles"]
            if value["profile_id"] == profile_id
            and value["profile_version"] == profile_version
        ),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="ModelProfile不存在")
    return ok(item)


@router.get("/status", response_model=dict)
async def model_status(
    current_user: dict = Depends(get_current_user),
):
    return ok(
        await ModelRuntimeStatusService(get_mongo_db()).status(
            admin=bool(current_user.get("is_admin", False))
        )
    )


@router.get("/runs", response_model=dict)
async def model_runs(
    limit: int = Query(default=100, ge=1, le=500),
    run_mode: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    query = {"run_mode": run_mode} if run_mode else {}
    items = await ModelRuntimeRepository(get_mongo_db()).list(
        "runs", query, sort=("created_at", -1), limit=limit
    )
    return ok({"items": items})


@router.get("/runs/{model_run_id}", response_model=dict)
async def model_run(
    model_run_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    item = await ModelRuntimeRepository(get_mongo_db()).get(
        "runs", {"model_run_id": model_run_id}
    )
    if item is None:
        raise HTTPException(status_code=404, detail="模型运行记录不存在")
    return ok(item)


@router.get("/snapshots/{snapshot_id}/runs", response_model=dict)
async def model_snapshot_runs(
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    snapshot = await db["ag_evidence_snapshots"].find_one(
        {"snapshot_id": snapshot_id}
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="EvidenceSnapshot不存在")
    if not current_user.get("is_admin", False):
        owner = str(snapshot.get("user_id") or "")
        if owner != _actor(current_user):
            raise HTTPException(status_code=403, detail="无权查看该模型链")
    repository = ModelRuntimeRepository(db)
    runs = await repository.list(
        "runs",
        {"snapshot_id": snapshot_id},
        sort=("created_at", 1),
        limit=200,
    )
    research = await repository.list(
        "research_results",
        {"snapshot_id": snapshot_id},
        sort=("created_at", 1),
        limit=50,
    )
    return ok({"runs": runs, "research": research})


@router.post("/capability-check", response_model=dict)
async def model_capability_check(
    body: CapabilityCheckBody,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await ModelCapabilityService(get_mongo_db()).check(
        profile_id=body.profile_id,
        profile_version=body.profile_version,
        checked_by=_actor(current_user),
        idempotency_key=body.idempotency_key,
        network=body.network,
    )
    return ok(
        result.model_dump(
            mode="json",
            exclude={
                "sanitized_message",
                "request_hash",
                "response_hash",
            },
        )
    )


@router.post("/validation-run", response_model=dict)
async def model_validation_run(
    body: ValidationRunBody,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    if body.confirmation_text != "RUN NON-EXECUTABLE MODEL VALIDATION":
        raise HTTPException(status_code=400, detail="验证确认文本不正确")
    result = await RealModelValidationService(get_mongo_db()).run(
        requested_by=_actor(current_user),
        idempotency_key=body.idempotency_key,
        proposal_id=body.proposal_id,
        user_id=body.user_id,
    )
    return ok(result.model_dump(mode="json"))
