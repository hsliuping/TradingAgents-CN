"""AlphaGuard PR-003 candidate and immutable evidence APIs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.response import fail, ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.candidate_pool_service import (
    get_candidate_pool_service,
)
from app.services.alphaguard.evidence_snapshot_service import (
    DataQualityBlockedError,
    SnapshotValidationError,
    get_evidence_snapshot_service,
)
from tradingagents.alphaguard.candidate_schemas import (
    CandidateSource,
    CandidateStatus,
)


router = APIRouter(prefix="/alphaguard", tags=["alphaguard"])


class RequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CandidateCreateRequest(RequestSchema):
    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    name: str | None = None
    priority: int = Field(default=50, ge=0, le=100)


class CandidatePatchRequest(RequestSchema):
    name: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    next_scan_at: datetime | None = None
    cooldown_until: datetime | None = None
    status: CandidateStatus | None = None


class EvidenceSnapshotCreateRequest(RequestSchema):
    analysis_id: str | None = None
    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    trade_date: date
    price_cutoff_at: datetime
    news_cutoff_at: datetime
    announcement_cutoff_at: datetime
    price_data_version: str = Field(min_length=1)
    financial_data_version: str = Field(min_length=1)
    news_data_version: str = Field(min_length=1)
    account_snapshot_id: str | None = None
    market_context_id: str | None = None
    raw_refs: dict[str, list[str]]
    required_sources: list[str] = Field(default_factory=lambda: ["prices"])
    normal_model_version: str | None = None
    top_model_version: str | None = None
    prompt_versions: dict[str, str] = Field(
        default_factory=lambda: {
            "normal_trade_plan": "normal_trade_plan_v1",
            "top_review_decision": "top_review_decision_v1",
        }
    )
    factor_version_set: dict[str, str] = Field(default_factory=dict)
    strategy_version: str | None = None

    @model_validator(mode="after")
    def enforce_version_lock(self) -> "EvidenceSnapshotCreateRequest":
        legacy_unversioned = not self.factor_version_set and self.strategy_version is None
        formal_quant = bool(self.factor_version_set) and bool(self.strategy_version)
        if not (legacy_unversioned or formal_quant):
            raise ValueError(
                "factor_version_set and strategy_version must be supplied together"
            )
        if any(
            not factor_id or not version or version.lower() == "latest"
            for factor_id, version in self.factor_version_set.items()
        ):
            raise ValueError("factor versions must use explicit non-latest identifiers")
        if self.strategy_version and self.strategy_version.lower() == "latest":
            raise ValueError("strategy_version must be explicit and not latest")
        if any(version.strip().lower() == "latest" for version in self.prompt_versions.values()):
            raise ValueError("prompt versions must be explicit and must not use latest")
        return self


def _trace_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/candidates", response_model=dict)
async def list_candidates(
    market: str | None = None,
    candidate_status: CandidateStatus | None = Query(None, alias="status"),
    source: CandidateSource | None = None,
    symbol: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    try:
        items = await get_candidate_pool_service().list_candidates(
            current_user["id"],
            market=market,
            status=candidate_status,
            source=source,
            symbol=symbol,
            limit=limit,
        )
        return ok({"items": [item.model_dump(mode="json") for item in items]})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/candidates", response_model=dict)
async def create_candidate(
    payload: CandidateCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        candidate = await get_candidate_pool_service().upsert_source(
            user_id=current_user["id"],
            symbol=payload.symbol,
            market=payload.market,
            source=CandidateSource.USER_SELECTED,
            name=payload.name,
            priority=payload.priority,
            trace_id=_trace_id(request),
            reason="candidate added through AlphaGuard API",
        )
        return ok(candidate.model_dump(mode="json"), "candidate source merged")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/candidates/reconcile", response_model=dict)
async def reconcile_candidates(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    stats = await get_candidate_pool_service().reconcile_user(
        current_user["id"],
        trace_id=_trace_id(request),
    )
    return ok(stats, "candidate reconciliation completed")


@router.get("/candidates/{candidate_id}", response_model=dict)
async def get_candidate(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
):
    candidate = await get_candidate_pool_service().get_candidate(
        candidate_id, current_user["id"]
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return ok(candidate.model_dump(mode="json"))


@router.patch("/candidates/{candidate_id}", response_model=dict)
async def patch_candidate(
    candidate_id: str,
    payload: CandidatePatchRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        changes: dict[str, Any] = payload.model_dump(exclude_unset=True)
        candidate = await get_candidate_pool_service().update_candidate(
            candidate_id,
            current_user["id"],
            changes,
            trace_id=_trace_id(request),
        )
        return ok(candidate.model_dump(mode="json"), "candidate updated")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/candidates/{candidate_id}", response_model=dict)
async def remove_candidate(
    candidate_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        candidate, reasons = await get_candidate_pool_service().request_removal(
            candidate_id,
            current_user["id"],
            trace_id=_trace_id(request),
        )
        return ok(
            {
                "candidate": candidate.model_dump(mode="json"),
                "monitoring_retained": bool(reasons),
                "retention_reasons": reasons,
                "physically_deleted": False,
            },
            "candidate removal request processed",
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evidence/snapshots", response_model=dict)
async def create_evidence_snapshot(
    payload: EvidenceSnapshotCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        snapshot = await get_evidence_snapshot_service().create(
            user_id=current_user["id"],
            payload=payload.model_dump(mode="python"),
        )
        return ok(snapshot.model_dump(mode="json"), "EvidenceSnapshot created")
    except DataQualityBlockedError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=fail(
                message="EvidenceSnapshot blocked by DataQuality FAIL",
                code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                data={
                    "snapshot_created": False,
                    "data_quality": exc.report.model_dump(mode="json"),
                },
            ),
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/evidence/snapshots/{snapshot_id}", response_model=dict)
async def get_evidence_snapshot(
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        snapshot = await get_evidence_snapshot_service().get(
            snapshot_id, current_user["id"]
        )
    except SnapshotValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail="EvidenceSnapshot not found")
    return ok(snapshot.model_dump(mode="json"))


@router.get("/evidence/snapshots/{snapshot_id}/quality", response_model=dict)
async def get_evidence_quality(
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    quality = await get_evidence_snapshot_service().get_quality(
        snapshot_id, current_user["id"]
    )
    if quality is None:
        raise HTTPException(status_code=404, detail="EvidenceSnapshot not found")
    return ok(quality.model_dump(mode="json"))


@router.post("/evidence/snapshots/{snapshot_id}/verify", response_model=dict)
async def verify_evidence_snapshot(
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        valid = await get_evidence_snapshot_service().verify_stored(
            snapshot_id, current_user["id"]
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SnapshotValidationError as exc:
        return ok(
            {"snapshot_id": snapshot_id, "integrity_valid": False, "error": str(exc)}
        )
    return ok({"snapshot_id": snapshot_id, "integrity_valid": valid})
