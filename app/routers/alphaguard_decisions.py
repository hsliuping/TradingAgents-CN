"""Authenticated, create/evaluate/read-only PR-005 decision APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.decision_context_builder import DecisionContextError
from app.services.alphaguard.decision_pipeline import (
    DecisionIntegrityError,
    DecisionPipeline,
)


router = APIRouter(prefix="/alphaguard", tags=["alphaguard-decisions"])


class EvaluateDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    account_id: str | None = None


def get_decision_pipeline() -> DecisionPipeline:
    return DecisionPipeline(get_mongo_db())


def _clean(document):
    if document is None:
        return None
    value = dict(document)
    value.pop("_id", None)
    return value


@router.post("/decisions/evaluate/{quant_proposal_id}", response_model=dict)
async def evaluate_decision(
    quant_proposal_id: str,
    payload: EvaluateDecisionRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await get_decision_pipeline().evaluate_quant_proposal(
            quant_proposal_id,
            user_id=str(current_user["id"]),
            account_id=payload.account_id,
            trace_id=getattr(request.state, "request_id", None),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DecisionIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DecisionContextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(
        result.model_dump(mode="json"),
        "decision evaluation completed; no order was created",
    )


@router.get("/analyses/{analysis_id}", response_model=dict)
async def get_decision_analysis(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
):
    document = await get_mongo_db()["analysis_reports"].find_one(
        {"analysis_id": analysis_id, "user_id": str(current_user["id"])}
    )
    if document is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return ok(_clean(document))


@router.get("/decisions/{plan_id}", response_model=dict)
async def get_normal_plan(
    plan_id: str,
    current_user: dict = Depends(get_current_user),
):
    document = await get_mongo_db()["analysis_reports"].find_one(
        {
            "user_id": str(current_user["id"]),
            "$or": [
                {"normal_trade_plan.plan_id": plan_id},
                {"normal_trade_plan_history.plan_id": plan_id},
            ],
        }
    )
    if document is None:
        raise HTTPException(status_code=404, detail="NormalTradePlan not found")
    plans = document.get("normal_trade_plan_history") or [
        document.get("normal_trade_plan")
    ]
    plan = next(
        (item for item in plans if item and item.get("plan_id") == plan_id),
        None,
    )
    return ok(plan)


@router.get("/reviews/{review_id}", response_model=dict)
async def get_top_review(
    review_id: str,
    current_user: dict = Depends(get_current_user),
):
    document = await get_mongo_db()["analysis_reports"].find_one(
        {
            "user_id": str(current_user["id"]),
            "$or": [
                {"top_review_decision.review_id": review_id},
                {"top_review_history.review_id": review_id},
            ],
        }
    )
    if document is None:
        raise HTTPException(status_code=404, detail="TopReviewDecision not found")
    reviews = document.get("top_review_history") or [
        document.get("top_review_decision")
    ]
    review = next(
        (item for item in reviews if item and item.get("review_id") == review_id),
        None,
    )
    return ok(review)


async def _authorized_record(collection: str, query: dict, user_id: str):
    db = get_mongo_db()
    document = await db[collection].find_one(query)
    if document is None:
        return None
    context = await db["ag_decision_contexts"].find_one(
        {"analysis_id": document.get("analysis_id"), "user_id": str(user_id)}
    )
    return _clean(document) if context else None


@router.get("/consensus/{consensus_id}", response_model=dict)
async def get_consensus(
    consensus_id: str,
    current_user: dict = Depends(get_current_user),
):
    item = await _authorized_record(
        "ag_consensus_decisions",
        {"consensus_id": consensus_id},
        current_user["id"],
    )
    if item is None:
        raise HTTPException(status_code=404, detail="ConsensusDecision not found")
    return ok(item)


@router.get("/risk-decisions/{risk_decision_id}", response_model=dict)
async def get_risk_decision(
    risk_decision_id: str,
    current_user: dict = Depends(get_current_user),
):
    item = await _authorized_record(
        "ag_risk_decisions",
        {"risk_decision_id": risk_decision_id},
        current_user["id"],
    )
    if item is None:
        raise HTTPException(status_code=404, detail="RiskDecision not found")
    return ok(item)


@router.get("/decision-events", response_model=dict)
async def list_decision_events(
    analysis_id: str | None = None,
    snapshot_id: str | None = None,
    event_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    query = {"user_id": str(current_user["id"])}
    if analysis_id:
        query["analysis_id"] = analysis_id
    if snapshot_id:
        query["snapshot_id"] = snapshot_id
    if event_type:
        query["event_type"] = event_type
    documents = await (
        get_mongo_db()["ag_decision_events"]
        .find(query)
        .sort("created_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )
    items = [_clean(item) for item in documents]
    reprocess_query: dict = {"user_id": str(current_user["id"])}
    reprocess_runs = await (
        get_mongo_db()["ag_production_reprocess_runs"]
        .find(reprocess_query)
        .sort("created_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )
    for raw_run in reprocess_runs:
        run = _clean(raw_run)
        validation = run.get("model_validation") or {}
        if snapshot_id and validation.get("snapshot_id") != snapshot_id:
            continue
        reprocess_analysis_id = (
            f"alphaguard-production-reprocess:"
            f"{run.get('reprocess_run_id')}"
        )
        if analysis_id and analysis_id != reprocess_analysis_id:
            continue
        common = {
            "analysis_id": reprocess_analysis_id,
            "user_id": str(current_user["id"]),
            "snapshot_id": validation.get("snapshot_id"),
            "quant_proposal_id": validation.get("proposal_id"),
            "trace_id": (
                f"production-reprocess-model:"
                f"{run.get('reprocess_run_id')}"
            ),
            "run_mode": "PRODUCTION_REPROCESS",
            "original_realtime_run": False,
            "automated_execution_allowed": False,
            "created_at": run.get("created_at"),
        }
        event_rows = []
        normal = validation.get("normal")
        if normal:
            meta = normal.get("model_meta") or {}
            event_rows.append(
                {
                    **common,
                    "event_id": (
                        f"{run.get('reprocess_run_id')}:normal"
                    ),
                    "event_type": "NORMAL_MODEL_COMPLETED",
                    "plan_id": normal.get("plan_id"),
                    "status": normal.get("status"),
                    "reason": normal.get("thesis"),
                    "input_hash": meta.get("input_hash"),
                    "output_hash": meta.get("raw_output_hash"),
                    "component_version": (
                        f"{meta.get('model_name')}@"
                        f"{meta.get('model_version')}"
                    ),
                    "created_at": meta.get("finished_at")
                    or run.get("created_at"),
                }
            )
        elif validation.get("status") in {
            "MODEL_NOT_CONFIGURED",
            "MODEL_FAILED",
        }:
            event_rows.append(
                {
                    **common,
                    "event_id": (
                        f"{run.get('reprocess_run_id')}:normal-status"
                    ),
                    "event_type": "NORMAL_MODEL_FAILED",
                    "status": validation.get("status"),
                    "reason": validation.get("error")
                    or validation.get("status"),
                }
            )
        top = validation.get("top")
        if top:
            meta = top.get("model_meta") or {}
            event_rows.append(
                {
                    **common,
                    "event_id": f"{run.get('reprocess_run_id')}:top",
                    "event_type": "TOP_REVIEW_COMPLETED",
                    "review_id": top.get("review_id"),
                    "status": top.get("status"),
                    "reason": top.get("review_reason"),
                    "input_hash": meta.get("input_hash"),
                    "output_hash": meta.get("raw_output_hash"),
                    "component_version": (
                        f"{meta.get('model_name')}@"
                        f"{meta.get('model_version')}"
                    ),
                    "created_at": meta.get("finished_at")
                    or run.get("created_at"),
                }
            )
        consensus = validation.get("consensus")
        if consensus:
            event_rows.append(
                {
                    **common,
                    "event_id": (
                        f"{run.get('reprocess_run_id')}:consensus"
                    ),
                    "event_type": "CONSENSUS_COMPLETED",
                    "consensus_id": consensus.get("consensus_id"),
                    "status": consensus.get("status"),
                    "reason": "; ".join(consensus.get("reasons") or []),
                    "component_version": consensus.get(
                        "consensus_policy_version"
                    ),
                    "created_at": consensus.get("created_at"),
                }
            )
        risk = validation.get("hard_risk")
        if risk:
            event_rows.append(
                {
                    **common,
                    "event_id": f"{run.get('reprocess_run_id')}:risk",
                    "event_type": "HARD_RISK_COMPLETED",
                    "risk_decision_id": risk.get("risk_decision_id"),
                    "status": risk.get("status"),
                    "reason": "; ".join(risk.get("reasons") or []),
                    "input_hash": risk.get("input_hash"),
                    "component_version": risk.get("risk_policy_version"),
                    "created_at": risk.get("created_at"),
                }
            )
        if event_type:
            event_rows = [
                item
                for item in event_rows
                if item.get("event_type") == event_type
            ]
        items.extend(event_rows)
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return ok({"items": items[:limit]})
