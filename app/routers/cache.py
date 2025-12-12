"""
缓存管理路由
提供缓存统计、清理等功能
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime, timedelta

from app.routers.auth_db import get_current_user
from app.core.response import ok
from tradingagents.utils.logging_manager import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats(current_user: dict = Depends(get_current_user)):
    """
    获取缓存统计信息
    
    Returns:
        dict: 缓存统计数据
    """
    try:
        from tradingagents.dataflows.cache import get_cache
        
        cache = get_cache()
        
        # 获取缓存统计
        stats = cache.get_cache_stats()
        
        logger.info(f"用户 {current_user['username']} 获取缓存统计")
        
        return ok(
            data={
                "totalFiles": stats.get('total_files', 0),
                "totalSize": stats.get('total_size', 0),  # 字节
                "maxSize": 1024 * 1024 * 1024,  # 1GB
                "stockDataCount": stats.get('stock_data_count', 0),
                "newsDataCount": stats.get('news_count', 0),
                "analysisDataCount": stats.get('fundamentals_count', 0)
            },
            message="获取缓存统计成功"
        )
        
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取缓存统计失败: {str(e)}"
        )


@router.delete("/cleanup")
async def cleanup_old_cache(
    days: int = Query(7, ge=1, le=30, description="清理多少天前的缓存"),
    current_user: dict = Depends(get_current_user)
):
    """
    清理过期缓存
    
    Args:
        days: 清理多少天前的缓存
        
    Returns:
        dict: 清理结果
    """
    try:
        from tradingagents.dataflows.cache import get_cache
        
        cache = get_cache()
        
        # 清理过期缓存
        cache.clear_old_cache(days)
        
        logger.info(f"用户 {current_user['username']} 清理了 {days} 天前的缓存")
        
        return ok(
            data={"days": days},
            message=f"已清理 {days} 天前的缓存"
        )
        
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清理缓存失败: {str(e)}"
        )


@router.delete("/clear")
async def clear_all_cache(current_user: dict = Depends(get_current_user)):
    """
    清空所有缓存

    Returns:
        dict: 清理结果
    """
    try:
        from tradingagents.dataflows.cache import get_cache

        cache = get_cache()

        # 清空所有缓存（清理所有过期和未过期的缓存）
        # 使用 clear_old_cache(0) 来清理所有缓存
        cache.clear_old_cache(0)

        logger.warning(f"用户 {current_user['username']} 清空了所有缓存")

        return ok(
            data={},
            message="所有缓存已清空"
        )

    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清空缓存失败: {str(e)}"
        )


@router.get("/details")
async def get_cache_details(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取缓存详情列表
    
    Args:
        page: 页码
        page_size: 每页数量
        
    Returns:
        dict: 缓存详情列表
    """
    try:
        from tradingagents.dataflows.cache import get_cache
        
        cache = get_cache()
        
        # 获取缓存详情
        # 注意：这个方法可能需要在缓存类中实现
        try:
            details = cache.get_cache_details(page=page, page_size=page_size)
        except AttributeError:
            # 如果缓存类没有实现这个方法，返回空列表
            details = {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size
            }
        
        logger.info(f"用户 {current_user['username']} 获取缓存详情 (页码: {page})")
        
        return ok(
            data=details,
            message="获取缓存详情成功"
        )
        
    except Exception as e:
        logger.error(f"获取缓存详情失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取缓存详情失败: {str(e)}"
        )


@router.get("/backend-info")
async def get_cache_backend_info(current_user: dict = Depends(get_current_user)):
    """
    获取缓存后端信息
    
    Returns:
        dict: 缓存后端配置信息
    """
    try:
        from tradingagents.dataflows.cache import get_cache
        
        cache = get_cache()
        
        # 获取后端信息
        try:
            backend_info = cache.get_cache_backend_info()
        except AttributeError:
            # 如果缓存类没有实现这个方法，返回基本信息
            backend_info = {
                "system": "file",
                "primary_backend": "file",
                "fallback_enabled": False
            }
        
        logger.info(f"用户 {current_user['username']} 获取缓存后端信息")
        
        return ok(
            data=backend_info,
            message="获取缓存后端信息成功"
        )
        
    except Exception as e:
        logger.error(f"获取缓存后端信息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取缓存后端信息失败: {str(e)}"
        )

