"""Authenticated read-only and cancel APIs for automatic paper trading."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.paper_order_service import (
    PaperOrderService,
    PaperOrderStateError,
)
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.paper_schemas import (
    DailyAccountSnapshot,
    PaperAccount,
    PaperEvent,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PositionLot,
)


router = APIRouter(prefix="/alphaguard/paper", tags=["alphaguard-paper"])


async def _account_ids(user_id: str) -> list[str]:
    documents = await get_mongo_db()["ag_paper_accounts"].find(
        {"user_id": str(user_id)}
    ).to_list(length=None)
    return [str(document["account_id"]) for document in documents]


async def _authorized_account(account_id: str, user_id: str) -> PaperAccount:
    document = clean_document(
        await get_mongo_db()["ag_paper_accounts"].find_one(
            {"account_id": account_id, "user_id": str(user_id)}
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="automatic paper account not found")
    return PaperAccount.model_validate(document)


def _items(models) -> dict:
    return {"items": [model.model_dump(mode="json") for model in models]}


@router.get("/accounts", response_model=dict)
async def list_accounts(current_user: dict = Depends(get_current_user)):
    documents = await get_mongo_db()["ag_paper_accounts"].find(
        {"user_id": str(current_user["id"])}
    ).sort("account_type", 1).to_list(length=None)
    return ok(
        _items(
            PaperAccount.model_validate(clean_document(document))
            for document in documents
        )
    )


@router.get("/accounts/{account_id}", response_model=dict)
async def get_account(
    account_id: str,
    current_user: dict = Depends(get_current_user),
):
    account = await _authorized_account(account_id, current_user["id"])
    return ok(account.model_dump(mode="json"))


@router.get("/positions", response_model=dict)
async def list_positions(
    account_id: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    ids = await _account_ids(current_user["id"])
    if account_id:
        await _authorized_account(account_id, current_user["id"])
        ids = [account_id]
    documents = await get_mongo_db()["ag_paper_positions"].find(
        {"account_id": {"$in": ids}}
    ).sort([("account_id", 1), ("symbol", 1)]).to_list(length=None)
    return ok(
        _items(
            PaperPosition.model_validate(clean_document(document))
            for document in documents
        )
    )


@router.get("/positions/{account_id}", response_model=dict)
async def get_account_positions(
    account_id: str,
    current_user: dict = Depends(get_current_user),
):
    return await list_positions(account_id, current_user)


@router.get("/position-lots", response_model=dict)
async def list_position_lots(
    account_id: str | None = None,
    symbol: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    ids = await _account_ids(current_user["id"])
    if account_id:
        await _authorized_account(account_id, current_user["id"])
        ids = [account_id]
    query = {"account_id": {"$in": ids}}
    if symbol:
        query["symbol"] = symbol
    documents = await get_mongo_db()["ag_paper_position_lots"].find(query).sort(
        [("acquired_trade_date", -1), ("created_at", -1)]
    ).to_list(length=None)
    return ok(
        _items(
            PositionLot.model_validate(clean_document(document))
            for document in documents
        )
    )


@router.get("/orders", response_model=dict)
async def list_orders(
    account_id: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    ids = await _account_ids(current_user["id"])
    if account_id:
        await _authorized_account(account_id, current_user["id"])
        ids = [account_id]
    query = {"account_id": {"$in": ids}}
    if status:
        query["status"] = status
    documents = await get_mongo_db()["ag_paper_orders"].find(query).sort(
        "created_at", -1
    ).limit(limit).to_list(length=limit)
    return ok(
        _items(
            PaperOrder.model_validate(clean_document(document))
            for document in documents
        )
    )


@router.get("/orders/{order_id}", response_model=dict)
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
):
    document = clean_document(
        await get_mongo_db()["ag_paper_orders"].find_one(
            {"order_id": order_id, "user_id": str(current_user["id"])}
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="automatic PaperOrder not found")
    return ok(PaperOrder.model_validate(document).model_dump(mode="json"))


@router.post("/orders/{order_id}/cancel", response_model=dict)
async def cancel_order(
    order_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        order = await PaperOrderService(get_mongo_db()).cancel(
            order_id,
            user_id=str(current_user["id"]),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaperOrderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    from app.services.alphaguard.paper_candidate_sync_service import (
        PaperCandidateSyncService,
    )

    await PaperCandidateSyncService(get_mongo_db()).sync_order(
        order,
        trace_id=getattr(request.state, "request_id", None),
    )
    return ok(order.model_dump(mode="json"), "automatic paper order cancelled")


@router.get("/fills", response_model=dict)
async def list_fills(
    account_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    ids = await _account_ids(current_user["id"])
    if account_id:
        await _authorized_account(account_id, current_user["id"])
        ids = [account_id]
    documents = await get_mongo_db()["ag_paper_fills"].find(
        {"account_id": {"$in": ids}}
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    return ok(
        _items(
            PaperFill.model_validate(clean_document(document))
            for document in documents
        )
    )


@router.get("/account-snapshots", response_model=dict)
async def list_account_snapshots(
    account_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    ids = await _account_ids(current_user["id"])
    if account_id:
        await _authorized_account(account_id, current_user["id"])
        ids = [account_id]
    documents = await get_mongo_db()["ag_paper_account_snapshots"].find(
        {"account_id": {"$in": ids}}
    ).sort("trade_date", -1).limit(limit).to_list(length=limit)
    return ok(
        _items(
            DailyAccountSnapshot.model_validate(clean_document(document))
            for document in documents
        )
    )


@router.get("/events", response_model=dict)
async def list_events(
    account_id: str | None = None,
    event_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    ids = await _account_ids(current_user["id"])
    if account_id:
        await _authorized_account(account_id, current_user["id"])
        ids = [account_id]
    query = {
        "$or": [
            {"account_id": {"$in": ids}},
            {"user_id": str(current_user["id"]), "account_id": None},
        ]
    }
    if event_type:
        query["event_type"] = event_type
    documents = await get_mongo_db()["ag_paper_events"].find(query).sort(
        "created_at", -1
    ).limit(limit).to_list(length=limit)
    return ok(
        _items(
            PaperEvent.model_validate(clean_document(document))
            for document in documents
        )
    )
