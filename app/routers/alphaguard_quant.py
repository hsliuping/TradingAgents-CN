"""Authenticated query and deterministic evaluation API for AlphaGuard PR-004."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.schemas.alphaguard import (
    FactorDefinition,
    FactorResult,
    MarketRegimeResult,
    QuantTradeProposal,
    StrategyDefinition,
)
from app.services.alphaguard.factor_registry import DefinitionConflictError
from app.services.alphaguard.quant_research_pipeline import QuantResearchPipeline
from app.services.alphaguard.snapshot_data_resolver import SnapshotResolutionError


router = APIRouter(prefix="/alphaguard", tags=["alphaguard-quant"])


class QuantEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str | None = None


def _clean(document):
    value = dict(document)
    value.pop("_id", None)
    return value


@router.get("/factors/definitions", response_model=dict)
async def list_factor_definitions(
    active_only: bool = True,
    current_user: dict = Depends(get_current_user),
):
    query = {"status": "ACTIVE"} if active_only else {}
    documents = await get_mongo_db()["ag_factor_definitions"].find(query).to_list(None)
    items = [FactorDefinition.model_validate(_clean(item)) for item in documents]
    return ok({"items": [item.model_dump(mode="json") for item in items]})


@router.get("/strategies/definitions", response_model=dict)
async def list_strategy_definitions(
    champion_only: bool = True,
    current_user: dict = Depends(get_current_user),
):
    query = {"status": "CHAMPION"} if champion_only else {}
    documents = await get_mongo_db()["ag_strategy_definitions"].find(query).to_list(None)
    items = [StrategyDefinition.model_validate(_clean(item)) for item in documents]
    return ok({"items": [item.model_dump(mode="json") for item in items]})


async def _authorized_factor_results(snapshot_id: str, user_id: str):
    db = get_mongo_db()
    snapshot = await db["ag_evidence_snapshots"].find_one(
        {"snapshot_id": snapshot_id, "user_id": str(user_id)}
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="EvidenceSnapshot not found")
    documents = await db["ag_factor_results"].find(
        {"snapshot_id": snapshot_id}
    ).to_list(None)
    return [FactorResult.model_validate(_clean(item)) for item in documents]


@router.get("/factors/results", response_model=dict)
async def list_factor_results(
    snapshot_id: str = Query(min_length=1),
    current_user: dict = Depends(get_current_user),
):
    items = await _authorized_factor_results(snapshot_id, current_user["id"])
    return ok({"items": [item.model_dump(mode="json") for item in items]})


@router.get("/factors/results/{snapshot_id}", response_model=dict)
async def get_snapshot_factors(
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    items = await _authorized_factor_results(snapshot_id, current_user["id"])
    return ok({"items": [item.model_dump(mode="json") for item in items]})


@router.get("/regimes/{snapshot_id}", response_model=dict)
async def get_snapshot_regime(
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    snapshot = await db["ag_evidence_snapshots"].find_one(
        {"snapshot_id": snapshot_id, "user_id": str(current_user["id"])}
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="EvidenceSnapshot not found")
    document = await db["ag_regime_results"].find_one({"snapshot_id": snapshot_id})
    if not document:
        raise HTTPException(status_code=404, detail="MarketRegimeResult not found")
    result = MarketRegimeResult.model_validate(_clean(document))
    return ok(result.model_dump(mode="json"))


@router.get("/quant-proposals", response_model=dict)
async def list_quant_proposals(
    snapshot_id: str | None = None,
    candidate_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    query = {"user_id": str(current_user["id"])}
    if snapshot_id:
        query["snapshot_id"] = snapshot_id
    if candidate_id:
        query["candidate_id"] = candidate_id
    documents = await (
        get_mongo_db()["ag_quant_proposals"]
        .find(query)
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    items = [QuantTradeProposal.model_validate(_clean(item)) for item in documents]
    return ok({"items": [item.model_dump(mode="json") for item in items]})


@router.post("/quant/evaluate/{snapshot_id}", response_model=dict)
async def evaluate_snapshot(
    snapshot_id: str,
    payload: QuantEvaluateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        proposals = await QuantResearchPipeline(get_mongo_db()).evaluate(
            snapshot_id,
            user_id=str(current_user["id"]),
            candidate_id=payload.candidate_id,
            trace_id=getattr(request.state, "request_id", None),
        )
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SnapshotResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DefinitionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(
        {"proposals": [item.model_dump(mode="json") for item in proposals]},
        "deterministic quant research completed; no order was created",
    )
