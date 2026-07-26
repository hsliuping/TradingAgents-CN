"""Authenticated PR-007 evaluation and append-only attribution APIs."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.attribution_engine import AttributionEngine
from app.services.alphaguard.evaluation_pipeline import EvaluationPipeline
from app.services.alphaguard.evaluation_repository import (
    EvaluationIntegrityConflict,
)
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.evaluation_schemas import AttributionRecord


router = APIRouter(
    prefix="/alphaguard",
    tags=["alphaguard-evaluations"],
)


class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of_trade_date: date
    all_users: bool = False


class AttributionOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    primary_category: str = Field(min_length=1)
    reason: str = Field(min_length=5, max_length=1000)


def _clean_items(documents):
    return [clean_document(item) for item in documents]


async def _subject_ids(user_id: str) -> list[str]:
    documents = await get_mongo_db()["ag_eval_subjects"].find(
        {"user_id": str(user_id)}
    ).to_list(length=None)
    return [str(item["subject_id"]) for item in documents]


async def _authorized_subject(subject_id: str, user_id: str):
    document = clean_document(
        await get_mongo_db()["ag_eval_subjects"].find_one(
            {"subject_id": subject_id, "user_id": str(user_id)}
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="EvaluationSubject not found")
    return document


@router.get("/evaluations/overview", response_model=dict)
async def evaluation_overview(
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    subjects = _clean_items(
        await db["ag_eval_subjects"].find(
            {"user_id": str(current_user["id"])}
        ).to_list(length=None)
    )
    subject_ids = [item["subject_id"] for item in subjects]
    labels = _clean_items(
        await db["ag_eval_horizon_labels"].find(
            {"subject_id": {"$in": subject_ids}}
        ).to_list(length=None)
    )
    counterfactuals = _clean_items(
        await db["ag_eval_counterfactuals"].find(
            {"subject_id": {"$in": subject_ids}}
        ).to_list(length=None)
    )
    attributions = _clean_items(
        await db["ag_eval_attributions"].find(
            {"subject_id": {"$in": subject_ids}}
        ).to_list(length=None)
    )
    data = {
        "evaluated_subjects": len(subjects),
        "pending_horizon_labels": sum(item["status"] == "PENDING" for item in labels),
        "insufficient_data_labels": sum(
            item["status"] in {"INSUFFICIENT_DATA", "INVALID_SOURCE"}
            for item in labels
        ),
        "traded_subjects": sum(item["actual_execution_exists"] for item in subjects),
        "untraded_subjects": sum(
            not item["actual_execution_exists"] for item in subjects
        ),
        "counterfactual_samples": len(counterfactuals),
        "attribution_completion_rate": (
            sum(item["status"] == "ATTRIBUTED" for item in attributions)
            / len(attributions)
            if attributions
            else None
        ),
        "diagnostic_notice": "规则化诊断，不代表严格因果",
    }
    return ok(jsonable_encoder(data))


@router.get("/evaluations/subjects", response_model=dict)
async def list_evaluation_subjects(
    decision_stage: str | None = None,
    decision_status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    query = {"user_id": str(current_user["id"])}
    if decision_stage:
        query["decision_stage"] = decision_stage
    if decision_status:
        query["decision_status"] = decision_status
    documents = await get_mongo_db()["ag_eval_subjects"].find(query).sort(
        "decision_trade_date", -1
    ).limit(limit).to_list(length=limit)
    return ok({"items": jsonable_encoder(_clean_items(documents))})


@router.get("/evaluations/subjects/{subject_id}", response_model=dict)
async def get_evaluation_subject(
    subject_id: str,
    current_user: dict = Depends(get_current_user),
):
    subject = await _authorized_subject(subject_id, current_user["id"])
    db = get_mongo_db()
    labels = await db["ag_eval_horizon_labels"].find(
        {"subject_id": subject_id}
    ).to_list(length=None)
    counterfactuals = await db["ag_eval_counterfactuals"].find(
        {"subject_id": subject_id}
    ).to_list(length=None)
    attribution = clean_document(
        await db["ag_eval_attributions"].find_one({"subject_id": subject_id})
    )
    return ok(
        jsonable_encoder(
            {
                "subject": subject,
                "horizon_labels": _clean_items(labels),
                "counterfactuals": _clean_items(counterfactuals),
                "attribution": attribution,
            }
        )
    )


@router.get("/evaluations/decisions/{source_object_id}", response_model=dict)
async def get_source_evaluations(
    source_object_id: str,
    current_user: dict = Depends(get_current_user),
):
    documents = await get_mongo_db()["ag_eval_subjects"].find(
        {
            "source_object_id": source_object_id,
            "user_id": str(current_user["id"]),
        }
    ).to_list(length=None)
    if not documents:
        raise HTTPException(status_code=404, detail="evaluation source not found")
    return ok({"items": jsonable_encoder(_clean_items(documents))})


@router.get("/evaluations/accounts", response_model=dict)
async def list_account_evaluations(
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    accounts = await db["ag_paper_accounts"].find(
        {"user_id": str(current_user["id"])}
    ).to_list(length=None)
    ids = [str(item["account_id"]) for item in accounts]
    metrics = await db["ag_eval_account_metrics"].find(
        {"account_id": {"$in": ids}}
    ).sort("period_end", -1).to_list(length=None)
    return ok({"items": jsonable_encoder(_clean_items(metrics))})


@router.get("/evaluations/accounts/compare", response_model=dict)
async def compare_accounts(
    current_user: dict = Depends(get_current_user),
):
    return await list_account_evaluations(current_user)


@router.get("/evaluations/model-value", response_model=dict)
async def model_value(
    limit: int = Query(200, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    ids = await _subject_ids(current_user["id"])
    documents = await get_mongo_db()["ag_eval_paired_comparisons"].find(
        {"left_subject_id": {"$in": ids}}
    ).sort("calculated_at", -1).limit(limit).to_list(length=limit)
    return ok({"items": jsonable_encoder(_clean_items(documents))})


async def _module_metrics(collection: str, user_id: str):
    documents = await get_mongo_db()[collection].find(
        {"scope_user_id": str(user_id)}
    ).sort(
        "period_end", -1
    ).limit(500).to_list(length=500)
    return ok({"items": jsonable_encoder(_clean_items(documents))})


@router.get("/evaluations/factors", response_model=dict)
async def factor_evaluations(current_user: dict = Depends(get_current_user)):
    return await _module_metrics("ag_eval_factor_metrics", current_user["id"])


@router.get("/evaluations/regimes", response_model=dict)
async def regime_evaluations(current_user: dict = Depends(get_current_user)):
    return await _module_metrics("ag_eval_regime_metrics", current_user["id"])


@router.get("/evaluations/strategies", response_model=dict)
async def strategy_evaluations(current_user: dict = Depends(get_current_user)):
    return await _module_metrics("ag_eval_strategy_metrics", current_user["id"])


@router.get("/evaluations/execution", response_model=dict)
async def execution_evaluations(current_user: dict = Depends(get_current_user)):
    return await _module_metrics("ag_eval_execution_metrics", current_user["id"])


@router.get("/evaluations/counterfactuals", response_model=dict)
async def list_counterfactuals(
    status: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    ids = await _subject_ids(current_user["id"])
    query = {"subject_id": {"$in": ids}}
    if status:
        query["status"] = status
    documents = await get_mongo_db()["ag_eval_counterfactuals"].find(query).sort(
        "created_at", -1
    ).limit(500).to_list(length=500)
    return ok({"items": jsonable_encoder(_clean_items(documents))})


@router.get("/attributions", response_model=dict)
async def list_attributions(
    primary_category: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    ids = await _subject_ids(current_user["id"])
    query = {"subject_id": {"$in": ids}}
    if primary_category:
        query["primary_category"] = primary_category
    documents = await get_mongo_db()["ag_eval_attributions"].find(query).sort(
        "calculated_at", -1
    ).limit(500).to_list(length=500)
    cleaned = _clean_items(documents)
    attribution_ids = [item["attribution_id"] for item in cleaned]
    overrides = _clean_items(
        await get_mongo_db()["ag_eval_attribution_overrides"].find(
            {"attribution_id": {"$in": attribution_ids}}
        ).sort("created_at", 1).to_list(length=None)
    )
    overrides_by_attribution: dict[str, list[dict]] = {}
    for override in overrides:
        overrides_by_attribution.setdefault(
            str(override["attribution_id"]), []
        ).append(override)
    for item in cleaned:
        item["overrides"] = overrides_by_attribution.get(
            str(item["attribution_id"]), []
        )
    return ok(
        {
            "items": jsonable_encoder(cleaned),
            "notice": "规则化诊断，不代表严格因果",
        }
    )


@router.post("/evaluations/run", response_model=dict)
async def schedule_evaluation(
    payload: EvaluationRunRequest,
    current_user: dict = Depends(get_current_user),
):
    if payload.all_users and not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="admin required for full backfill")
    run, created = await EvaluationPipeline(get_mongo_db()).schedule(
        as_of_trade_date=payload.as_of_trade_date,
        user_id=None if payload.all_users else str(current_user["id"]),
    )
    return ok(
        jsonable_encoder(
            {
                "evaluation_job_id": run.evaluation_job_id,
                "status": run.status,
                "created": created,
                "background": True,
            }
        ),
        "evaluation run scheduled idempotently",
    )


@router.post("/attributions/{attribution_id}/overrides", response_model=dict)
async def create_attribution_override(
    attribution_id: str,
    payload: AttributionOverrideRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    raw = clean_document(
        await get_mongo_db()["ag_eval_attributions"].find_one(
            {"attribution_id": attribution_id}
        )
    )
    if raw is None:
        raise HTTPException(status_code=404, detail="AttributionRecord not found")
    attribution = AttributionRecord.model_validate(raw)
    await _authorized_subject(attribution.subject_id, current_user["id"])
    try:
        override = await AttributionEngine(get_mongo_db()).append_override(
            attribution=attribution,
            user_id=str(current_user["id"]),
            category=payload.primary_category,
            reason=payload.reason,
            trace_id=getattr(request.state, "request_id", None),
        )
    except EvaluationIntegrityConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(
        override.model_dump(mode="json"),
        "append-only attribution override created",
    )
