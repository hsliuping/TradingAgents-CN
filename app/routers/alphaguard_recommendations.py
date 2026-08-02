"""User-scoped governed candidate recommendation API."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.candidate_recommendation_service import (
    CandidatePoolLimitReached,
    CandidateRecommendationService,
    RecommendationIntegrityConflict,
    RecommendationReviewConflict,
)


router = APIRouter(
    prefix="/alphaguard/recommendations",
    tags=["alphaguard-recommendations"],
)


class _StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReviewBody(_StrictBody):
    review_note: str | None = Field(default=None, max_length=1000)


class BatchReviewBody(ReviewBody):
    recommendation_ids: list[str] = Field(min_length=1, max_length=50)


class RunBody(_StrictBody):
    trade_date: date | None = None


def _service() -> CandidateRecommendationService:
    return CandidateRecommendationService(get_mongo_db())


def _trace_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _require_admin(user: dict) -> None:
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="仅管理员可以运行候选推荐扫描")


@router.get("", response_model=dict)
async def list_recommendations(
    recommendation_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    items = await _service().list_recommendations(
        user_id=str(current_user["id"]),
        status=recommendation_status,
        limit=limit,
        skip=skip,
    )
    return ok({"items": items, "count": len(items)})


@router.get("/runs", response_model=dict)
async def list_recommendation_runs(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    items = await _service().list_runs(
        user_id=str(current_user["id"]),
        admin=bool(current_user.get("is_admin")),
        limit=limit,
    )
    return ok({"items": [item.model_dump(mode="json") for item in items]})


@router.get("/coverage", response_model=dict)
async def recommendation_data_coverage(
    trade_date: date | None = None,
    current_user: dict = Depends(get_current_user),
):
    return ok(await _service().coverage(trade_date=trade_date))


@router.get("/runs/{run_id}", response_model=dict)
async def get_recommendation_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = await _service().get_run(
            run_id=run_id,
            user_id=str(current_user["id"]),
            admin=bool(current_user.get("is_admin")),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.post("/run", response_model=dict)
async def run_recommendations(
    payload: RunBody,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        run, created = await _service().run(
            user_id=str(current_user["id"]),
            trade_date=payload.trade_date,
        )
    except (LookupError, RecommendationIntegrityConflict, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(
        {**run.model_dump(mode="json"), "run_action": "CREATED" if created else "REUSED"},
        "候选推荐扫描完成" if created else "相同输入已复用",
    )


@router.post("/batch-accept", response_model=dict)
async def batch_accept_recommendations(
    payload: BatchReviewBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _batch_review(payload, request, current_user, "ACCEPTED")


@router.post("/batch-reject", response_model=dict)
async def batch_reject_recommendations(
    payload: BatchReviewBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _batch_review(payload, request, current_user, "REJECTED")


async def _batch_review(
    payload: BatchReviewBody,
    request: Request,
    current_user: dict,
    action: str,
):
    try:
        result = await _service().batch_review(
            recommendation_ids=payload.recommendation_ids,
            user_id=str(current_user["id"]),
            action=action,
            review_note=payload.review_note,
            trace_id=_trace_id(request),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CandidatePoolLimitReached as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RecommendationReviewConflict, RecommendationIntegrityConflict, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(result, "批量审核完成")


@router.get("/{recommendation_id}", response_model=dict)
async def get_recommendation(
    recommendation_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = await _service().get_recommendation_detail(
            recommendation_id=recommendation_id,
            user_id=str(current_user["id"]),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.post("/{recommendation_id}/accept", response_model=dict)
async def accept_recommendation(
    recommendation_id: str,
    payload: ReviewBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _review(recommendation_id, payload, request, current_user, "ACCEPTED")


@router.post("/{recommendation_id}/reject", response_model=dict)
async def reject_recommendation(
    recommendation_id: str,
    payload: ReviewBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _review(recommendation_id, payload, request, current_user, "REJECTED")


@router.post("/{recommendation_id}/ignore", response_model=dict)
async def ignore_recommendation(
    recommendation_id: str,
    payload: ReviewBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _review(recommendation_id, payload, request, current_user, "IGNORED")


async def _review(
    recommendation_id: str,
    payload: ReviewBody,
    request: Request,
    current_user: dict,
    action: str,
):
    try:
        event, created = await _service().review(
            recommendation_id=recommendation_id,
            user_id=str(current_user["id"]),
            action=action,
            review_note=payload.review_note,
            trace_id=_trace_id(request),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CandidatePoolLimitReached as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RecommendationReviewConflict, RecommendationIntegrityConflict, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(
        {**event.model_dump(mode="json"), "review_action": "CREATED" if created else "REUSED"},
        "推荐审核已记录",
    )
