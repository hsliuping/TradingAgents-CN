"""
自选股管理API路由
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import logging

from app.routers.auth_db import get_current_user
from app.routers.stock_sync import _delete_sync_history_for_symbol, _delete_synced_data_for_symbol
from app.models.user import User, FavoriteStock
from app.services.favorites_service import favorites_service
from app.core.response import ok
from app.core.database import get_mongo_db

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/favorites", tags=["自选股管理"])


class AddFavoriteRequest(BaseModel):
    """添加自选股请求"""
    stock_code: str
    stock_name: str
    market: str = "A股"
    tags: List[str] = []
    notes: str = ""
    alert_price_high: Optional[float] = None
    alert_price_low: Optional[float] = None


class UpdateFavoriteRequest(BaseModel):
    """更新自选股请求"""
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    alert_price_high: Optional[float] = None
    alert_price_low: Optional[float] = None


class FavoriteStockResponse(BaseModel):
    """自选股响应"""
    stock_code: str
    stock_name: str
    market: str
    currency: Optional[str] = None
    tags: List[str]
    notes: str
    alert_price_high: Optional[float]
    alert_price_low: Optional[float]
    # 实时数据
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    quote_trade_date: Optional[str] = None
    quote_updated_at: Optional[str] = None


@router.get("/", response_model=dict)
async def get_favorites(
    current_user: dict = Depends(get_current_user)
):
    """获取用户自选股列表"""
    try:
        favorites = await favorites_service.get_user_favorites(current_user["id"])
        return ok(favorites)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取自选股失败: {str(e)}"
        )


@router.post("/", response_model=dict)
async def add_favorite(
    request: AddFavoriteRequest,
    current_user: dict = Depends(get_current_user)
):
    """添加股票到自选股"""
    import logging
    logger = logging.getLogger("webapi")

    try:
        logger.info(f"📝 添加自选股请求: user_id={current_user['id']}, stock_code={request.stock_code}, stock_name={request.stock_name}")

        # 检查是否已存在
        is_fav = await favorites_service.is_favorite(current_user["id"], request.stock_code)
        logger.info(f"🔍 检查是否已存在: {is_fav}")

        if is_fav:
            logger.warning(f"⚠️ 股票已在自选股中: {request.stock_code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该股票已在自选股中"
            )

        # 添加到自选股
        logger.info(f"➕ 开始添加自选股...")
        success = await favorites_service.add_favorite(
            user_id=current_user["id"],
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            market=request.market,
            tags=request.tags,
            notes=request.notes,
            alert_price_high=request.alert_price_high,
            alert_price_low=request.alert_price_low
        )

        logger.info(f"✅ 添加结果: success={success}")

        if success:
            return ok({"stock_code": request.stock_code}, "添加成功")
        else:
            logger.error(f"❌ 添加失败: success=False")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="添加失败"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 添加自选股异常: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加自选股失败: {str(e)}"
        )


@router.put("/{stock_code}", response_model=dict)
async def update_favorite(
    stock_code: str,
    request: UpdateFavoriteRequest,
    current_user: dict = Depends(get_current_user)
):
    """更新自选股信息"""
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
                detail="自选股不存在"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新自选股失败: {str(e)}"
        )


@router.delete("/{stock_code}", response_model=dict)
async def remove_favorite(
    stock_code: str,
    cleanup_related: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """从自选股中移除股票"""
    try:
        success = await favorites_service.remove_favorite(current_user["id"], stock_code)

        if success:
            cleanup_result = None

            if cleanup_related:
                db = get_mongo_db()
                try:
                    history_deleted_count = await _delete_sync_history_for_symbol(
                        db,
                        current_user=current_user,
                        symbol=stock_code,
                    )
                    data_cleanup = await _delete_synced_data_for_symbol(
                        db,
                        symbol=stock_code,
                        delete_types=["historical", "financial", "basic", "realtime_cache"],
                        delete_display_cache=True,
                    )
                    cleanup_result = {
                        "success": True,
                        "history_deleted_count": history_deleted_count,
                        "data_deleted_count": data_cleanup["deleted_count"],
                        "data_details": data_cleanup["details"],
                    }
                    logger.info(
                        "🧹 删除自选股联动清理完成: user_id=%s, stock_code=%s, history_deleted=%s, data_deleted=%s",
                        current_user["id"],
                        stock_code,
                        history_deleted_count,
                        data_cleanup["deleted_count"],
                    )
                except Exception as cleanup_error:
                    logger.error(
                        "❌ 删除自选股后的联动清理失败: stock_code=%s, error=%s",
                        stock_code,
                        cleanup_error,
                        exc_info=True,
                    )
                    cleanup_result = {
                        "success": False,
                        "error": str(cleanup_error),
                    }

            message = "移除成功"
            if cleanup_related:
                if cleanup_result and cleanup_result.get("success"):
                    message = "移除成功，并已清理相关同步历史和数据"
                else:
                    message = "自选股已移除，但相关同步历史和数据清理失败，请稍后手动处理"

            return ok({
                "stock_code": stock_code,
                "cleanup_related": cleanup_related,
                "cleanup": cleanup_result,
            }, message)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="自选股不存在"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"移除自选股失败: {str(e)}"
        )


@router.get("/check/{stock_code}", response_model=dict)
async def check_favorite(
    stock_code: str,
    current_user: dict = Depends(get_current_user)
):
    """检查股票是否在自选股中"""
    try:
        is_favorite = await favorites_service.is_favorite(current_user["id"], stock_code)
        return ok({"stock_code": stock_code, "is_favorite": is_favorite})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查自选股状态失败: {str(e)}"
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
    """同步自选股实时行情请求"""
    data_source: str = "tushare"  # tushare/akshare


@router.post("/sync-realtime", response_model=dict)
async def sync_favorites_realtime(
    request: SyncFavoritesRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    同步自选股实时行情

    - **data_source**: 数据源（tushare/akshare）
    """
    try:
        logger.info(f"📊 开始同步自选股实时行情: user_id={current_user['id']}, data_source={request.data_source}")

        # 获取用户自选股列表
        favorites = await favorites_service.get_user_favorites(current_user["id"])

        if not favorites:
            logger.info("⚠️ 用户没有自选股")
            return ok({
                "total": 0,
                "success_count": 0,
                "failed_count": 0,
                "message": "没有自选股需要同步"
            })

        grouped_symbols: Dict[str, List[str]] = {
            "A股": [],
            "港股": [],
            "美股": [],
        }
        symbols: List[str] = []
        for fav in favorites:
            symbol = fav.get("stock_code") or fav.get("symbol")
            if not symbol:
                continue
            market = fav.get("market") or "A股"
            grouped_symbols.setdefault(market, []).append(symbol)
            symbols.append(symbol)

        logger.info(f"🎯 需要同步的股票: {len(symbols)} 只 - {symbols}")

        success_count = 0
        failed_count = 0
        details: Dict[str, Dict[str, int]] = {}

        a_share_symbols = grouped_symbols.get("A股", [])
        if a_share_symbols:
            if request.data_source == "tushare":
                from app.worker.tushare_sync_service import get_tushare_sync_service
                try:
                    service = await get_tushare_sync_service()
                except Exception as e:
                    logger.warning(f"⚠️ Tushare 服务不可用，自动回退到 AKShare: {e}")
                    from app.worker.akshare_sync_service import get_akshare_sync_service
                    service = await get_akshare_sync_service()
                    request.data_source = "akshare"
            elif request.data_source == "akshare":
                from app.worker.akshare_sync_service import get_akshare_sync_service
                service = await get_akshare_sync_service()
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的数据源: {request.data_source}"
                )

            if not service:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"{request.data_source} 服务不可用"
                )

            logger.info(f"🔄 调用 {request.data_source} 同步 A 股实时行情...")
            sync_result = await service.sync_realtime_quotes(
                symbols=a_share_symbols,
                force=True
            )
            a_share_success = sync_result.get("success_count", 0)
            a_share_failed = sync_result.get("failed_count", sync_result.get("error_count", 0))
            success_count += a_share_success
            failed_count += a_share_failed
            details["A股"] = {
                "total": len(a_share_symbols),
                "success_count": a_share_success,
                "failed_count": a_share_failed,
            }

        foreign_symbols = {
            "港股": ("HK", grouped_symbols.get("港股", [])),
            "美股": ("US", grouped_symbols.get("美股", [])),
        }
        if any(symbol_list for _, symbol_list in foreign_symbols.values()):
            from app.services.foreign_stock_service import ForeignStockService

            foreign_service = ForeignStockService(db=get_mongo_db())

            for market_label, (market_code, market_symbols) in foreign_symbols.items():
                if not market_symbols:
                    continue

                market_success = 0
                market_failed = 0
                for symbol in market_symbols:
                    try:
                        await foreign_service.get_quote(market_code, symbol, force_refresh=True)
                        market_success += 1
                    except Exception as exc:
                        logger.warning(
                            "⚠️ 自选股实时行情强制刷新失败，尝试回退缓存: market=%s, symbol=%s, error=%s",
                            market_label,
                            symbol,
                            exc,
                        )
                        try:
                            await foreign_service.get_quote(market_code, symbol, force_refresh=False)
                            market_success += 1
                            logger.info(
                                "✅ 自选股实时行情已回退缓存: market=%s, symbol=%s",
                                market_label,
                                symbol,
                            )
                        except Exception as cache_exc:
                            market_failed += 1
                            logger.warning(
                                "⚠️ 自选股实时行情刷新失败: market=%s, symbol=%s, refresh_error=%s, cache_error=%s",
                                market_label,
                                symbol,
                                exc,
                                cache_exc,
                            )

                success_count += market_success
                failed_count += market_failed
                details[market_label] = {
                    "total": len(market_symbols),
                    "success_count": market_success,
                    "failed_count": market_failed,
                }

        logger.info(f"✅ 自选股实时行情同步完成: 成功 {success_count}/{len(symbols)} 只")

        message_parts = []
        for market_label in ["A股", "港股", "美股"]:
            market_detail = details.get(market_label)
            if not market_detail:
                continue
            message_parts.append(f"{market_label}成功 {market_detail['success_count']} / {market_detail['total']}")

        return ok({
            "total": len(symbols),
            "success_count": success_count,
            "failed_count": failed_count,
            "symbols": symbols,
            "data_source": request.data_source,
            "details": details,
            "message": "；".join(message_parts) if message_parts else f"同步完成: 成功 {success_count} 只，失败 {failed_count} 只"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 同步自选股实时行情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步失败: {str(e)}"
        )
