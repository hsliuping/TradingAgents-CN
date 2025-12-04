"""
交易复盘API路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
import logging

from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.services.trade_review_service import get_trade_review_service
from app.models.review import (
    CreateTradeReviewRequest, CreatePeriodicReviewRequest,
    SaveAsCaseRequest, ReviewType
)

router = APIRouter(prefix="/review", tags=["review"])
logger = logging.getLogger("webapi.review")


# ==================== 交易复盘 ====================

@router.post("/trade", response_model=Dict[str, Any])
async def create_trade_review(
    request: CreateTradeReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    创建交易复盘
    
    - **trade_ids**: 要复盘的交易ID列表
    - **review_type**: 复盘类型 (single_trade/complete_trade)
    - **code**: 股票代码（可选，不传则从交易记录推断）
    """
    try:
        service = get_trade_review_service()
        result = await service.create_trade_review(
            user_id=current_user["id"],
            request=request
        )
        return ok({
            "review_id": result.review_id,
            "status": result.status.value,
            "trade_info": result.trade_info.model_dump() if result.trade_info else None,
            "ai_review": result.ai_review.model_dump() if result.ai_review else None,
            "market_snapshot": result.market_snapshot.model_dump() if result.market_snapshot else None,
            "execution_time": result.execution_time,
            "created_at": result.created_at.isoformat() if result.created_at else None
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建交易复盘失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建复盘失败: {str(e)}")


@router.get("/trade/history", response_model=Dict[str, Any])
async def get_review_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """获取复盘历史列表"""
    try:
        service = get_trade_review_service()
        result = await service.get_review_history(
            user_id=current_user["id"],
            page=page,
            page_size=page_size
        )
        return ok(result)
    except Exception as e:
        logger.error(f"获取复盘历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade/{review_id}", response_model=Dict[str, Any])
async def get_review_detail(
    review_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取复盘详情"""
    try:
        service = get_trade_review_service()
        result = await service.get_review_detail(
            user_id=current_user["id"],
            review_id=review_id
        )
        if not result:
            raise HTTPException(status_code=404, detail="复盘报告不存在")
        
        return ok({
            "review_id": result.review_id,
            "review_type": result.review_type.value,
            "status": result.status.value,
            "trade_info": result.trade_info.model_dump(),
            "market_snapshot": result.market_snapshot.model_dump(),
            "ai_review": result.ai_review.model_dump(),
            "is_case_study": result.is_case_study,
            "tags": result.tags,
            "execution_time": result.execution_time,
            "created_at": result.created_at.isoformat() if result.created_at else None
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取复盘详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 案例库 ====================

@router.post("/case", response_model=Dict[str, Any])
async def save_as_case(
    request: SaveAsCaseRequest,
    current_user: dict = Depends(get_current_user)
):
    """保存为案例"""
    try:
        service = get_trade_review_service()
        success = await service.save_as_case(
            user_id=current_user["id"],
            review_id=request.review_id,
            tags=request.tags
        )
        if not success:
            raise HTTPException(status_code=404, detail="复盘报告不存在")
        return ok({"message": "已保存为案例"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存案例失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases", response_model=Dict[str, Any])
async def get_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """获取案例库"""
    try:
        service = get_trade_review_service()
        result = await service.get_cases(
            user_id=current_user["id"],
            page=page,
            page_size=page_size
        )
        return ok(result)
    except Exception as e:
        logger.error(f"获取案例库失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/case/{review_id}", response_model=Dict[str, Any])
async def delete_case(
    review_id: str,
    current_user: dict = Depends(get_current_user)
):
    """从案例库移除"""
    try:
        service = get_trade_review_service()
        success = await service.delete_case(
            user_id=current_user["id"],
            review_id=review_id
        )
        if not success:
            raise HTTPException(status_code=404, detail="案例不存在")
        return ok({"message": "已从案例库移除"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除案例失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 交易统计 ====================

@router.get("/statistics", response_model=Dict[str, Any])
async def get_trading_statistics(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user)
):
    """获取交易统计"""
    try:
        service = get_trade_review_service()
        stats = await service.get_trading_statistics(
            user_id=current_user["id"],
            start_date=start_date,
            end_date=end_date
        )
        return ok(stats.model_dump())
    except Exception as e:
        logger.error(f"获取交易统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 可复盘交易查询 ====================

@router.get("/reviewable-trades", response_model=Dict[str, Any])
async def get_reviewable_trades(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    获取可复盘的交易列表

    返回用户的卖出交易记录，可用于选择进行复盘
    """
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()

        # 构建查询条件
        query = {"user_id": current_user["id"]}
        if code:
            query["code"] = code

        skip = (page - 1) * page_size

        # 获取交易记录
        cursor = db["paper_trades"].find(query).sort("timestamp", -1).skip(skip).limit(page_size)
        trades = await cursor.to_list(None)
        total = await db["paper_trades"].count_documents(query)

        # 格式化结果
        items = []
        for t in trades:
            items.append({
                "trade_id": str(t.get("_id")),
                "code": t.get("code"),
                "market": t.get("market", "CN"),
                "side": t.get("side"),
                "quantity": t.get("quantity"),
                "price": t.get("price"),
                "amount": t.get("amount"),
                "pnl": t.get("pnl", 0),
                "timestamp": t.get("timestamp")
            })

        # 按股票分组统计
        code_stats = {}
        all_trades = await db["paper_trades"].find({"user_id": current_user["id"]}).to_list(None)
        for t in all_trades:
            c = t.get("code")
            if c not in code_stats:
                code_stats[c] = {"buy_count": 0, "sell_count": 0, "total_pnl": 0}
            if t.get("side") == "buy":
                code_stats[c]["buy_count"] += 1
            else:
                code_stats[c]["sell_count"] += 1
                code_stats[c]["total_pnl"] += t.get("pnl", 0)

        # 找出已完成交易（有买有卖）的股票
        completed_stocks = [
            {"code": c, **stats}
            for c, stats in code_stats.items()
            if stats["buy_count"] > 0 and stats["sell_count"] > 0
        ]

        return ok({
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "completed_stocks": completed_stocks
        })

    except Exception as e:
        logger.error(f"获取可复盘交易失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades-by-code/{code}", response_model=Dict[str, Any])
async def get_trades_by_code(
    code: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取某只股票的所有交易记录

    用于选择要复盘的交易
    """
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()

        cursor = db["paper_trades"].find({
            "user_id": current_user["id"],
            "code": code
        }).sort("timestamp", 1)

        trades = await cursor.to_list(None)

        items = []
        for t in trades:
            items.append({
                "trade_id": str(t.get("_id")),
                "code": t.get("code"),
                "market": t.get("market", "CN"),
                "side": t.get("side"),
                "quantity": t.get("quantity"),
                "price": t.get("price"),
                "amount": t.get("amount"),
                "pnl": t.get("pnl", 0),
                "commission": t.get("commission", 0),
                "timestamp": t.get("timestamp")
            })

        # 计算汇总
        total_buy_qty = sum(t["quantity"] for t in items if t["side"] == "buy")
        total_sell_qty = sum(t["quantity"] for t in items if t["side"] == "sell")
        total_pnl = sum(t["pnl"] for t in items)

        return ok({
            "code": code,
            "trades": items,
            "summary": {
                "total_trades": len(items),
                "total_buy_quantity": total_buy_qty,
                "total_sell_quantity": total_sell_qty,
                "total_pnl": round(total_pnl, 2),
                "is_closed": total_sell_qty >= total_buy_qty and total_buy_qty > 0
            }
        })

    except Exception as e:
        logger.error(f"获取股票交易记录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
