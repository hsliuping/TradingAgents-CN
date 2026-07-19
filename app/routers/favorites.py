"""
股票关注列表管理API路由
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import logging

from app.routers.auth_db import get_current_user
from app.models.user import User, FavoriteStock
from app.services.favorites_service import favorites_service
from app.core.response import ok

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/favorites", tags=["股票关注列表管理"], redirect_slashes=False)

FAVORITES_SYNC_TASKS_COLLECTION = "favorites_sync_tasks"


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


async def _create_favorites_sync_task(current_user: dict, payload: Dict[str, Any]) -> Dict[str, Any]:
    db = favorites_service.db
    task_doc = {
        "task_id": uuid4().hex,
        "task_type": "favorites_realtime",
        "status": "pending",
        "message": "股票关注列表实时行情同步任务已提交",
        "payload": payload,
        "user_id": current_user["id"],
        "submitted_by": str(current_user.get("username") or current_user.get("id") or "unknown"),
        "created_at": _utc_now_iso(),
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    await db[FAVORITES_SYNC_TASKS_COLLECTION].insert_one(task_doc)
    task_doc.pop("_id", None)
    return task_doc


async def _update_favorites_sync_task(task_id: str, updates: Dict[str, Any]) -> None:
    db = favorites_service.db
    await db[FAVORITES_SYNC_TASKS_COLLECTION].update_one(
        {"task_id": task_id},
        {"$set": updates},
        upsert=False,
    )


async def _get_favorites_sync_task(task_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    db = favorites_service.db
    task_doc = await db[FAVORITES_SYNC_TASKS_COLLECTION].find_one({"task_id": task_id, "user_id": user_id})
    if task_doc:
        task_doc.pop("_id", None)
    return task_doc


async def _run_favorites_realtime_sync_task(task_id: str, user_id: str, data_source: str) -> None:
    try:
        await _update_favorites_sync_task(
            task_id,
            {
                "status": "running",
                "message": "股票关注列表实时行情同步执行中",
                "started_at": _utc_now_iso(),
                "error": None,
            },
        )

        favorites = await favorites_service.get_user_favorites(user_id)

        if not favorites:
            result = {
                "total": 0,
                "success_count": 0,
                "failed_count": 0,
                "message": "没有股票关注列表需要同步",
                "symbols": [],
                "data_source": data_source,
            }
            await _update_favorites_sync_task(
                task_id,
                {
                    "status": "success",
                    "message": result["message"],
                    "finished_at": _utc_now_iso(),
                    "result": result,
                },
            )
            return

        symbols = [fav.get("stock_code") or fav.get("symbol") for fav in favorites]
        symbols = [s for s in symbols if s]

        if data_source == "tushare":
            from app.worker.tushare_sync_service import get_tushare_sync_service
            service = await get_tushare_sync_service()
        elif data_source == "akshare":
            from app.worker.akshare_sync_service import get_akshare_sync_service
            service = await get_akshare_sync_service()
        else:
            raise RuntimeError(f"不支持的数据源: {data_source}")

        if not service:
            raise RuntimeError(f"{data_source} 服务不可用")

        if data_source == "akshare":
            sync_result = await service.sync_realtime_quotes(
                symbols=symbols,
                force=True,
                manual_mode=True,
            )
        else:
            sync_result = await service.sync_realtime_quotes(
                symbols=symbols,
                force=True,
            )

        success_count = sync_result.get("success_count", 0)
        failed_count = sync_result.get("failed_count", 0)
        result = {
            "total": len(symbols),
            "success_count": success_count,
            "failed_count": failed_count,
            "symbols": symbols,
            "data_source": data_source,
            "message": f"同步完成: 成功 {success_count} 只，失败 {failed_count} 只",
        }

        await _update_favorites_sync_task(
            task_id,
            {
                "status": "success" if failed_count == 0 else "success_with_errors",
                "message": result["message"],
                "finished_at": _utc_now_iso(),
                "result": result,
            },
        )
    except Exception as e:
        logger.error(f"❌ 股票关注列表实时行情同步任务失败: {e}", exc_info=True)
        await _update_favorites_sync_task(
            task_id,
            {
                "status": "failed",
                "message": f"同步失败: {str(e)}",
                "finished_at": _utc_now_iso(),
                "error": str(e),
            },
        )


class AddFavoriteRequest(BaseModel):
    """添加到研究列表请求"""
    stock_code: Optional[str] = None
    symbol: Optional[str] = None
    stock_name: str
    market: str = "A股"
    tags: List[str] = []
    notes: str = ""
    alert_price_high: Optional[float] = None
    alert_price_low: Optional[float] = None


class UpdateFavoriteRequest(BaseModel):
    """更新股票关注列表请求"""
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    alert_price_high: Optional[float] = None
    alert_price_low: Optional[float] = None


class FavoriteStockResponse(BaseModel):
    """股票关注列表响应"""
    stock_code: str
    stock_name: str
    market: str
    added_at: str
    tags: List[str]
    notes: str
    alert_price_high: Optional[float]
    alert_price_low: Optional[float]
    # 实时数据
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None


@router.get("", response_model=dict)
async def get_favorites(
    current_user: dict = Depends(get_current_user)
):
    """获取用户股票关注列表列表"""
    try:
        favorites = await favorites_service.get_user_favorites(current_user["id"])
        return ok(favorites)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取股票关注列表失败: {str(e)}"
        )


@router.post("", response_model=dict)
async def add_favorite(
    request: AddFavoriteRequest,
    current_user: dict = Depends(get_current_user)
):
    """添加股票到股票关注列表"""
    import logging
    logger = logging.getLogger("webapi")

    try:
        stock_code = (request.stock_code or request.symbol or "").strip()
        if not stock_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="股票代码不能为空"
            )

        logger.info(f"📝 添加到研究列表请求: user_id={current_user['id']}, stock_code={stock_code}, stock_name={request.stock_name}")

        # 检查是否已存在
        is_fav = await favorites_service.is_favorite(current_user["id"], stock_code)
        logger.info(f"🔍 检查是否已存在: {is_fav}")

        if is_fav:
            logger.warning(f"⚠️ 股票已在股票关注列表中: {stock_code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该股票已在股票关注列表中"
            )

        # 添加到股票关注列表
        logger.info(f"➕ 开始添加到研究列表...")
        success = await favorites_service.add_favorite(
            user_id=current_user["id"],
            stock_code=stock_code,
            stock_name=request.stock_name,
            market=request.market,
            tags=request.tags,
            notes=request.notes,
            alert_price_high=request.alert_price_high,
            alert_price_low=request.alert_price_low
        )

        logger.info(f"✅ 添加结果: success={success}")

        if success:
            return ok({"stock_code": stock_code}, "添加成功")
        else:
            logger.error(f"❌ 添加失败: success=False")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="添加失败"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 添加到研究列表异常: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加到研究列表失败: {str(e)}"
        )


@router.put("/{stock_code}", response_model=dict)
async def update_favorite(
    stock_code: str,
    request: UpdateFavoriteRequest,
    current_user: dict = Depends(get_current_user)
):
    """更新股票关注列表信息"""
    try:
        success = await favorites_service.update_favorite(
            user_id=current_user["id"],
            stock_code=stock_code,
            tags=request.tags,
            notes=request.notes,
            alert_price_high=request.alert_price_high,
            alert_price_low=request.alert_price_low
        )

        if success:
            return ok({"stock_code": stock_code}, "更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="股票关注列表不存在"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新股票关注列表失败: {str(e)}"
        )


@router.delete("/{stock_code}", response_model=dict)
async def remove_favorite(
    stock_code: str,
    current_user: dict = Depends(get_current_user)
):
    """从股票关注列表中移除股票"""
    try:
        success = await favorites_service.remove_favorite(current_user["id"], stock_code)

        if success:
            return ok({"stock_code": stock_code}, "移除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="股票关注列表不存在"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"移除股票关注列表失败: {str(e)}"
        )


@router.get("/check/{stock_code}", response_model=dict)
async def check_favorite(
    stock_code: str,
    current_user: dict = Depends(get_current_user)
):
    """检查股票是否在股票关注列表中"""
    try:
        is_favorite = await favorites_service.is_favorite(current_user["id"], stock_code)
        return ok({"stock_code": stock_code, "is_favorite": is_favorite})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查股票关注列表状态失败: {str(e)}"
        )


@router.get("/tags", response_model=dict)
async def get_user_tags(
    current_user: dict = Depends(get_current_user)
):
    """获取用户使用的所有标签"""
    try:
        tags = await favorites_service.get_user_tags(current_user["id"])
        return ok(tags)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取标签失败: {str(e)}"
        )


class SyncFavoritesRequest(BaseModel):
    """同步股票关注列表实时行情请求"""
    data_source: str = "tushare"  # tushare/akshare


@router.post("/sync-realtime", response_model=dict)
async def sync_favorites_realtime(
    request: SyncFavoritesRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    同步股票关注列表实时行情

    - **data_source**: 数据源（tushare/akshare）
    """
    try:
        logger.info(f"📊 提交股票关注列表实时行情同步任务: user_id={current_user['id']}, data_source={request.data_source}")

        task_doc = await _create_favorites_sync_task(
            current_user,
            {"data_source": request.data_source},
        )
        asyncio.create_task(
            _run_favorites_realtime_sync_task(
                task_doc["task_id"],
                current_user["id"],
                request.data_source,
            )
        )

        return ok(task_doc, "股票关注列表实时行情同步任务已提交")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 同步股票关注列表实时行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步失败: {str(e)}"
        )


@router.get("/sync-realtime/tasks/{task_id}", response_model=dict)
async def get_favorites_realtime_sync_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取股票关注列表实时行情同步任务状态。"""
    try:
        task_doc = await _get_favorites_sync_task(task_id, current_user["id"])
        if not task_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="同步任务不存在"
            )
        return ok(task_doc)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取股票关注列表实时行情同步任务失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取同步任务失败: {str(e)}"
        )
