"""Authenticated PR-008 Experiment Lab and human promotion APIs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.challenger_assignment_service import (
    ChallengerAssignmentService,
)
from app.services.alphaguard.champion_promotion_service import (
    ChampionPromotionService,
)
from app.services.alphaguard.champion_rollback_service import (
    ChampionRollbackService,
)
from app.services.alphaguard.experiment_dataset_service import (
    ExperimentDatasetService,
)
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import (
    ExperimentIntegrityConflict,
    ExperimentRepository,
)
from app.services.alphaguard.experiment_task_service import ExperimentTaskService
from app.services.alphaguard.paper_storage import clean_document
from app.services.alphaguard.shadow_experiment_service import (
    ShadowExperimentService,
)
from app.services.alphaguard.walk_forward_validation import (
    TimeSeriesSplitService,
)


router = APIRouter(prefix="/alphaguard", tags=["alphaguard-experiments"])


class ExperimentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    user_id: str
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    component_type: str
    component_key: str
    market: str = "CN"
    baseline_version_ref: str
    challenger_version_ref: str
    primary_variable_path: str
    expected_improvement: list[str] = Field(default_factory=list)
    expected_risks: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    failure_criteria: list[str] = Field(default_factory=list)


class DatasetManifestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_ids: list[str] = Field(min_length=1)
    selection_rule: str = Field(min_length=1)
    candidate_source_filters: list[str] = Field(default_factory=list)
    data_quality_filters: list[str] = Field(default_factory=list)
    created_from_cutoff_at: datetime


class TimeSplitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal[
        "ANCHORED_HOLDOUT",
        "ROLLING_WALK_FORWARD",
        "EXPANDING_WALK_FORWARD",
    ]
    embargo_trading_days: int = Field(default=1, ge=0)
    train_size: int = Field(default=20, ge=1)
    validation_size: int = Field(default=5, ge=0)
    test_size: int = Field(default=10, ge=1)
    folds: int = Field(default=1, ge=1, le=50)


class ExperimentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_manifest_id: str
    split_id: str | None = None
    split_ids: list[str] = Field(default_factory=list)
    run_type: Literal[
        "HISTORICAL_REPLAY",
        "WALK_FORWARD",
        "LEAKAGE_AUDIT",
        "ROBUSTNESS",
        "COMPARISON",
    ] = "HISTORICAL_REPLAY"
    source_run_id: str | None = None


class ShadowStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_manifest_id: str


class ReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=1000)


class ChallengerActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    activation_trade_date: date


class RiskReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparison_report_id: str


class PromotionRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparison_report_id: str
    risk_review_id: str
    effective_from_trade_date: date


class PromotionApprovalBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision_reason: str = Field(min_length=3, max_length=1000)
    confirmation_text: str
    current_champion_hash: str
    proposed_champion_hash: str


class RollbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=1000)
    confirmation_text: str
    current_champion_hash: str
    effective_from_trade_date: date


def _require_admin(user: dict) -> None:
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="administrator permission required")


async def _authorized_experiment(experiment_id: str, user: dict):
    definition = await ExperimentRegistry(get_mongo_db()).get(experiment_id)
    if not user.get("is_admin", False) and definition.user_id != str(user["id"]):
        raise HTTPException(status_code=404, detail="experiment not found")
    return definition


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ExperimentIntegrityConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/experiments", response_model=dict)
async def list_experiments(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    items = await ExperimentRegistry(get_mongo_db()).list(
        user_id=None if current_user.get("is_admin") else str(current_user["id"]),
        status=status,
        limit=limit,
    )
    return ok({"items": jsonable_encoder(items)})


@router.post("/experiments", response_model=dict)
async def create_experiment(
    body: ExperimentCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        definition = await ExperimentRegistry(get_mongo_db()).create(
            **body.model_dump(),
            created_by=str(current_user["id"]),
        )
        return ok(jsonable_encoder(definition), "experiment created")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/experiments/{experiment_id}", response_model=dict)
async def get_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
):
    definition = await _authorized_experiment(experiment_id, current_user)
    db = get_mongo_db()
    related = {}
    for key, collection in {
        "variable_changes": "ag_exp_variable_changes",
        "dataset_manifests": "ag_exp_dataset_manifests",
        "runs": "ag_exp_runs",
        "shadow_runs": "ag_exp_shadow_runs",
        "challenger_assignments": "ag_exp_challenger_assignments",
        "comparison_reports": "ag_exp_comparison_reports",
        "risk_reviews": "ag_exp_risk_reviews",
        "promotion_requests": "ag_exp_promotion_requests",
        "events": "ag_exp_events",
    }.items():
        related[key] = [
            clean_document(item)
            for item in await db[collection].find(
                {"experiment_id": experiment_id}
            ).sort("created_at", -1).to_list(length=500)
        ]
    return ok(jsonable_encoder({"definition": definition, **related}))


@router.post("/experiments/{experiment_id}/validate", response_model=dict)
async def validate_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        registry = ExperimentRegistry(get_mongo_db())
        definition = await registry.validate(experiment_id)
        if definition.status == "DRAFT":
            definition = await registry.transition(
                experiment_id,
                "EXPERIMENT",
                reason="administrator validated immutable experiment definition",
            )
        return ok(jsonable_encoder(definition), "experiment validated")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/experiments/{experiment_id}/dataset-manifests", response_model=dict)
async def create_dataset_manifest(
    experiment_id: str,
    body: DatasetManifestRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        definition = await ExperimentRegistry(get_mongo_db()).get(experiment_id)
        manifest = await ExperimentDatasetService(get_mongo_db()).create_manifest(
            experiment_id=experiment_id,
            market=definition.market,
            snapshot_ids=body.snapshot_ids,
            selection_rule=body.selection_rule,
            candidate_source_filters=body.candidate_source_filters,
            data_quality_filters=body.data_quality_filters,
            created_from_cutoff_at=body.created_from_cutoff_at,
        )
        return ok(jsonable_encoder(manifest), "dataset manifest created")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/experiments/{experiment_id}/time-splits", response_model=dict)
async def create_time_splits(
    experiment_id: str,
    dataset_manifest_id: str,
    body: TimeSplitRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        manifest = await ExperimentDatasetService(get_mongo_db()).get(
            dataset_manifest_id
        )
        if manifest.experiment_id != experiment_id:
            raise ValueError("manifest belongs to another experiment")
        splits = await TimeSeriesSplitService(get_mongo_db()).create(
            dataset_manifest_id,
            method=body.method,
            embargo_trading_days=body.embargo_trading_days,
            train_size=body.train_size,
            validation_size=body.validation_size,
            test_size=body.test_size,
            folds=body.folds,
        )
        return ok(jsonable_encoder(splits), "time-series splits created")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/experiments/{experiment_id}/run", response_model=dict)
async def run_experiment(
    experiment_id: str,
    body: ExperimentRunRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    payload: dict[str, Any] = {"dataset_manifest_id": body.dataset_manifest_id}
    job_type = body.run_type
    if job_type == "HISTORICAL_REPLAY":
        payload["split_id"] = body.split_id
    elif job_type == "WALK_FORWARD":
        payload["split_ids"] = body.split_ids
    elif job_type in {"LEAKAGE_AUDIT", "ROBUSTNESS"}:
        if not body.source_run_id:
            raise HTTPException(status_code=400, detail="source_run_id is required")
        payload = {"run_id": body.source_run_id}
    elif job_type == "COMPARISON":
        payload = {}
    task = await ExperimentTaskService(get_mongo_db()).enqueue(
        job_type,
        experiment_id=experiment_id,
        payload=payload,
        requested_by=str(current_user["id"]),
    )
    return ok(jsonable_encoder(task), "experiment task queued")


@router.get("/experiments/{experiment_id}/runs", response_model=dict)
async def list_runs(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
):
    await _authorized_experiment(experiment_id, current_user)
    documents = await ExperimentRepository(get_mongo_db()).list(
        "runs", {"experiment_id": experiment_id}, sort=("created_at", -1)
    )
    return ok({"items": jsonable_encoder(documents)})


@router.get("/experiments/{experiment_id}/comparison", response_model=dict)
async def get_comparison(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
):
    await _authorized_experiment(experiment_id, current_user)
    document = clean_document(
        await get_mongo_db()["ag_exp_comparison_reports"].find_one(
            {"experiment_id": experiment_id}, sort=[("created_at", -1)]
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="comparison report not found")
    return ok(jsonable_encoder(document))


@router.post("/experiments/{experiment_id}/shadow/start", response_model=dict)
async def start_shadow(
    experiment_id: str,
    body: ShadowStartRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        value = await ShadowExperimentService(get_mongo_db()).start(
            experiment_id,
            dataset_manifest_id=body.dataset_manifest_id,
            created_by=str(current_user["id"]),
        )
        return ok(jsonable_encoder(value), "Shadow started")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/experiments/{experiment_id}/shadow/pause", response_model=dict)
async def pause_shadow(
    experiment_id: str,
    shadow_run_id: str,
    body: ReasonRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    await _authorized_experiment(experiment_id, current_user)
    try:
        value = await ShadowExperimentService(get_mongo_db()).pause(
            shadow_run_id, reason=body.reason
        )
        return ok(jsonable_encoder(value), "Shadow paused")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/experiments/{experiment_id}/shadow/complete", response_model=dict)
async def complete_shadow(
    experiment_id: str,
    shadow_run_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    await _authorized_experiment(experiment_id, current_user)
    try:
        value = await ShadowExperimentService(get_mongo_db()).complete(shadow_run_id)
        return ok(jsonable_encoder(value), "Shadow completed")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/experiments/{experiment_id}/challenger/activate", response_model=dict)
async def activate_challenger(
    experiment_id: str,
    body: ChallengerActivateRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        value = await ChallengerAssignmentService(get_mongo_db()).activate(
            experiment_id,
            user_id=body.user_id,
            activation_trade_date=body.activation_trade_date,
        )
        return ok(jsonable_encoder(value), "PAPER_CHALLENGER activated")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/experiments/{experiment_id}/challenger/deactivate", response_model=dict)
async def deactivate_challenger(
    experiment_id: str,
    body: ReasonRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        value = await ChallengerAssignmentService(get_mongo_db()).deactivate(
            experiment_id, reason=body.reason
        )
        return ok(jsonable_encoder(value), "PAPER_CHALLENGER deactivation started")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/experiments/{experiment_id}/risk-review", response_model=dict)
async def request_risk_review(
    experiment_id: str,
    body: RiskReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    task = await ExperimentTaskService(get_mongo_db()).enqueue(
        "RISK_REVIEW",
        experiment_id=experiment_id,
        payload={"comparison_report_id": body.comparison_report_id},
        requested_by=str(current_user["id"]),
    )
    return ok(jsonable_encoder(task), "experiment risk review queued")


@router.post("/experiments/{experiment_id}/promotion-requests", response_model=dict)
async def create_promotion_request(
    experiment_id: str,
    body: PromotionRequestBody,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        value = await ChampionPromotionService(get_mongo_db()).create_request(
            experiment_id,
            comparison_report_id=body.comparison_report_id,
            risk_review_id=body.risk_review_id,
            requested_by=str(current_user["id"]),
            effective_from_trade_date=body.effective_from_trade_date,
        )
        return ok(jsonable_encoder(value), "promotion request awaits explicit approval")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/promotion-requests/{request_id}/approve", response_model=dict)
async def approve_promotion(
    request_id: str,
    body: PromotionApprovalBody,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        approval, saga = await ChampionPromotionService(
            get_mongo_db()
        ).approve_request(
            request_id,
            approved_by=str(current_user["id"]),
            **body.model_dump(),
        )
        return ok(jsonable_encoder({"approval": approval, "saga": saga}))
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/promotion-requests/{request_id}/reject", response_model=dict)
async def reject_promotion(
    request_id: str,
    body: ReasonRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        value = await ChampionPromotionService(get_mongo_db()).reject_request(
            request_id,
            rejected_by=str(current_user["id"]),
            reason=body.reason,
        )
        return ok(jsonable_encoder(value), "promotion request rejected")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/champions", response_model=dict)
async def list_champions(current_user: dict = Depends(get_current_user)):
    documents = await get_mongo_db()["ag_exp_champion_assignments"].find({}).sort(
        "updated_at", -1
    ).to_list(length=None)
    return ok({"items": jsonable_encoder([clean_document(item) for item in documents])})


@router.get("/champions/{champion_slot_id}", response_model=dict)
async def get_champion(
    champion_slot_id: str,
    current_user: dict = Depends(get_current_user),
):
    document = clean_document(
        await get_mongo_db()["ag_exp_champion_assignments"].find_one(
            {"champion_slot_id": champion_slot_id}
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Champion slot not found")
    history = [
        clean_document(item)
        for item in await get_mongo_db()["ag_exp_champion_history"].find(
            {"champion_slot_id": champion_slot_id}
        ).sort("recorded_at", -1).to_list(length=100)
    ]
    return ok(jsonable_encoder({"assignment": document, "history": history}))


@router.post("/champions/{champion_slot_id}/rollback", response_model=dict)
async def rollback_champion(
    champion_slot_id: str,
    body: RollbackBody,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        record, saga = await ChampionRollbackService(get_mongo_db()).rollback(
            champion_slot_id,
            requested_by=str(current_user["id"]),
            approved_by=str(current_user["id"]),
            **body.model_dump(),
        )
        return ok(jsonable_encoder({"rollback": record, "saga": saga}))
    except Exception as exc:
        raise _http_error(exc) from exc
