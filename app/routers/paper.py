from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any, List
from datetime import datetime

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.core.response import ok

router = APIRouter(prefix="/paper", tags=["paper"])


INITIAL_CASH = 1_000_000.0


class PlaceOrderRequest(BaseModel):
    code: str = Field(..., description="6位股票代码")
    side: Literal["buy", "sell"]
    quantity: int = Field(..., gt=0)
    # 可选：关联的分析ID，便于从分析页面一键下单后追踪
    analysis_id: Optional[str] = None


async def _get_or_create_account(user_id: str) -> Dict[str, Any]:
    db = get_mongo_db()
    acc = await db["paper_accounts"].find_one({"user_id": user_id})
    if not acc:
        now = datetime.utcnow().isoformat()
        acc = {
            "user_id": user_id,
            "cash": INITIAL_CASH,
            "realized_pnl": 0.0,
            "created_at": now,
            "updated_at": now,
        }
        await db["paper_accounts"].insert_one(acc)
    return acc


async def _get_last_price(code6: str) -> Optional[float]:
    db = get_mongo_db()
    q = await db["market_quotes"].find_one({"code": code6}, {"_id": 0, "close": 1})
    if q and q.get("close") is not None:
        try:
            return float(q["close"])
        except Exception:
            return None
    return None


def _zfill_code(code: str) -> str:
    s = str(code).strip()
    if len(s) == 6 and s.isdigit():
        return s
    return s.zfill(6)


@router.get("/account", response_model=dict)
async def get_account(current_user: dict = Depends(get_current_user)):
    """获取或创建纸上账户，返回资金与持仓估值汇总"""
    db = get_mongo_db()
    acc = await _get_or_create_account(current_user["id"])

    # 聚合持仓估值
    positions = await db["paper_positions"].find({"user_id": current_user["id"]}).to_list(None)
    total_mkt_value = 0.0
    detailed_positions: List[Dict[str, Any]] = []
    for p in positions:
        code6 = p.get("code")
        qty = int(p.get("quantity", 0))
        avg_cost = float(p.get("avg_cost", 0.0))
        last = await _get_last_price(code6)
        mkt = round((last or 0.0) * qty, 2)
        total_mkt_value += mkt
        detailed_positions.append({
            "code": code6,
            "quantity": qty,
            "avg_cost": avg_cost,
            "last_price": last,
            "market_value": mkt,
            "unrealized_pnl": None if last is None else round((last - avg_cost) * qty, 2)
        })

    summary = {
        "cash": round(float(acc.get("cash", 0.0)), 2),
        "realized_pnl": round(float(acc.get("realized_pnl", 0.0)), 2),
        "positions_value": round(total_mkt_value, 2),
        "equity": round(float(acc.get("cash", 0.0)) + total_mkt_value, 2),
        "updated_at": acc.get("updated_at"),
    }

    return ok({"account": summary, "positions": detailed_positions})


@router.post("/order", response_model=dict)
async def place_order(payload: PlaceOrderRequest, current_user: dict = Depends(get_current_user)):
    """提交市价单，按最新价即时成交（MVP）"""
    db = get_mongo_db()
    code6 = _zfill_code(payload.code)
    side = payload.side
    qty = int(payload.quantity)
    analysis_id = getattr(payload, "analysis_id", None)

    # 获取账户
    acc = await _get_or_create_account(current_user["id"])

    # 价格
    price = await _get_last_price(code6)
    if price is None or price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法获取最新价格，暂不能下单")

    notional = round(price * qty, 2)

    # 获取持仓
    pos = await db["paper_positions"].find_one({"user_id": current_user["id"], "code": code6})

    now_iso = datetime.utcnow().isoformat()
    realized_pnl_delta = 0.0

    if side == "buy":
        if float(acc.get("cash", 0.0)) < notional:
            raise HTTPException(status_code=400, detail="可用现金不足")
        new_cash = round(float(acc.get("cash", 0.0)) - notional, 2)
        # 更新/创建持仓：加权平均成本
        if not pos:
            new_pos = {"user_id": current_user["id"], "code": code6, "quantity": qty, "avg_cost": price, "updated_at": now_iso}
            await db["paper_positions"].insert_one(new_pos)
        else:
            old_qty = int(pos.get("quantity", 0))
            old_cost = float(pos.get("avg_cost", 0.0))
            new_qty = old_qty + qty
            new_avg = round((old_cost * old_qty + price * qty) / new_qty, 4) if new_qty > 0 else price
            await db["paper_positions"].update_one(
                {"_id": pos["_id"]},
                {"$set": {"quantity": new_qty, "avg_cost": new_avg, "updated_at": now_iso}}
            )
        # 更新账户
        await db["paper_accounts"].update_one(
            {"user_id": current_user["id"]},
            {"$set": {"cash": new_cash, "updated_at": now_iso}}
        )
    else:  # sell
        if not pos or int(pos.get("quantity", 0)) < qty:
            raise HTTPException(status_code=400, detail="可用持仓不足")
        old_qty = int(pos.get("quantity", 0))
        avg_cost = float(pos.get("avg_cost", 0.0))
        new_qty = old_qty - qty
        pnl = round((price - avg_cost) * qty, 2)
        realized_pnl_delta = pnl
        new_cash = round(float(acc.get("cash", 0.0)) + notional, 2)
        if new_qty == 0:
            await db["paper_positions"].delete_one({"_id": pos["_id"]})
        else:
            await db["paper_positions"].update_one(
                {"_id": pos["_id"]},
                {"$set": {"quantity": new_qty, "updated_at": now_iso}}
            )
        await db["paper_accounts"].update_one(
            {"user_id": current_user["id"]},
            {"$inc": {"realized_pnl": realized_pnl_delta}, "$set": {"cash": new_cash, "updated_at": now_iso}}
        )

    # 记录订单与成交（即成）
    order_doc = {
        "user_id": current_user["id"],
        "code": code6,
        "side": side,
        "quantity": qty,
        "price": price,
        "amount": notional,
        "status": "filled",
        "created_at": now_iso,
        "filled_at": now_iso,
    }
    if analysis_id:
        order_doc["analysis_id"] = analysis_id
    await db["paper_orders"].insert_one(order_doc)

    trade_doc = {
        "user_id": current_user["id"],
        "code": code6,
        "side": side,
        "quantity": qty,
        "price": price,
        "amount": notional,
        "pnl": realized_pnl_delta if side == "sell" else 0.0,
        "timestamp": now_iso,
    }
    if analysis_id:
        trade_doc["analysis_id"] = analysis_id
    await db["paper_trades"].insert_one(trade_doc)

    return ok({"order": {k: v for k, v in order_doc.items() if k != "_id"}})


@router.get("/positions", response_model=dict)
async def list_positions(current_user: dict = Depends(get_current_user)):
    db = get_mongo_db()
    items = await db["paper_positions"].find({"user_id": current_user["id"]}).to_list(None)
    enriched: List[Dict[str, Any]] = []
    for p in items:
        code6 = p.get("code")
        qty = int(p.get("quantity", 0))
        avg_cost = float(p.get("avg_cost", 0.0))
        last = await _get_last_price(code6)
        mkt = round((last or 0.0) * qty, 2)
        enriched.append({
            "code": code6,
            "quantity": qty,
            "avg_cost": avg_cost,
            "last_price": last,
            "market_value": mkt,
            "unrealized_pnl": None if last is None else round((last - avg_cost) * qty, 2)
        })
    return ok({"items": enriched})


@router.get("/orders", response_model=dict)
async def list_orders(limit: int = Query(50, ge=1, le=200), current_user: dict = Depends(get_current_user)):
    db = get_mongo_db()
    cursor = db["paper_orders"].find({"user_id": current_user["id"]}).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(None)
    # 去除 _id
    cleaned = [{k: v for k, v in it.items() if k != "_id"} for it in items]
    return ok({"items": cleaned})


@router.post("/reset", response_model=dict)
async def reset_account(confirm: bool = Query(False), current_user: dict = Depends(get_current_user)):
    if not confirm:
        raise HTTPException(status_code=400, detail="请设置 confirm=true 以确认重置")
    db = get_mongo_db()
    await db["paper_accounts"].delete_many({"user_id": current_user["id"]})
    await db["paper_positions"].delete_many({"user_id": current_user["id"]})
    await db["paper_orders"].delete_many({"user_id": current_user["id"]})
    await db["paper_trades"].delete_many({"user_id": current_user["id"]})
    # 重新创建账户
    acc = await _get_or_create_account(current_user["id"])
    return ok({"message": "账户已重置", "cash": acc.get("cash", 0.0)})