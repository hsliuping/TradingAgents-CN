"""
新闻数据API路由
提供新闻数据查询、同步和管理接口
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query, status
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

from app.routers.auth_db import get_current_user
from app.core.permissions import require_pro
from app.core.response import ok
from app.services.news_data_service import get_news_data_service, NewsQueryParams
from app.worker.news_data_sync_service import get_news_data_sync_service

router = APIRouter(prefix="/api/news-data", tags=["新闻数据"])
logger = logging.getLogger("webapi")


class NewsQueryRequest(BaseModel):
    """新闻查询请求"""
    symbol: Optional[str] = Field(None, description="股票代码")
    symbols: Optional[List[str]] = Field(None, description="多个股票代码")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    category: Optional[str] = Field(None, description="新闻类别")
    sentiment: Optional[str] = Field(None, description="情绪分析")
    importance: Optional[str] = Field(None, description="重要性")
    data_source: Optional[str] = Field(None, description="数据源")
    keywords: Optional[List[str]] = Field(None, description="关键词")
    limit: int = Field(50, description="返回数量限制")
    skip: int = Field(0, description="跳过数量")


class NewsSyncRequest(BaseModel):
    """新闻同步请求"""
    symbol: Optional[str] = Field(None, description="股票代码，为空则同步市场新闻")
    data_sources: Optional[List[str]] = Field(None, description="数据源列表")
    hours_back: int = Field(24, description="回溯小时数")
    max_news_per_source: int = Field(50, description="每个数据源最大新闻数量")


class NewsDataBatchRequest(BaseModel):
    """批量保存新闻数据请求"""
    symbol: Optional[str] = Field(None, description="主要相关股票代码")
    news_list: List[Dict[str, Any]] = Field(..., description="新闻数据列表")
    overwrite: bool = Field(False, description="是否覆盖已存在的数据")


@router.get("/query/{symbol}", response_model=dict)
async def query_stock_news(
    symbol: str,
    hours_back: int = Query(24, description="回溯小时数"),
    limit: int = Query(20, description="返回数量限制"),
    category: Optional[str] = Query(None, description="新闻类别"),
    sentiment: Optional[str] = Query(None, description="情绪分析"),
    current_user: dict = Depends(get_current_user)
):
    """
    查询股票新闻（智能获取：优先数据库，无数据时实时获取）

    Args:
        symbol: 股票代码
        hours_back: 回溯小时数
        limit: 返回数量限制
        category: 新闻类别过滤
        sentiment: 情绪分析过滤

    Returns:
        dict: 新闻数据列表
    """
    try:
        service = await get_news_data_service()

        # 构建查询参数
        start_time = datetime.utcnow() - timedelta(hours=hours_back)

        params = NewsQueryParams(
            symbol=symbol,
            start_time=start_time,
            category=category,
            sentiment=sentiment,
            limit=limit,
            sort_by="publish_time",
            sort_order=-1
        )

        # 1. 先从数据库查询
        news_list = await service.query_news(params)
        data_source = "database"

        # 2. 如果数据库没有数据，实时获取
        if not news_list:
            logger.info(f"📰 数据库无新闻数据，实时获取: {symbol}")
            try:
                from app.worker.akshare_sync_service import get_akshare_sync_service
                sync_service = await get_akshare_sync_service()

                # 实时获取新闻
                news_data = await sync_service.provider.get_stock_news(
                    symbol=symbol,
                    limit=limit
                )

                if news_data:
                    # 保存到数据库
                    saved_count = await service.save_news_data(
                        news_data=news_data,
                        data_source="akshare",
                        market="CN"
                    )
                    logger.info(f"✅ 实时获取并保存 {saved_count} 条新闻")

                    # 重新查询
                    news_list = await service.query_news(params)
                    data_source = "realtime"
                else:
                    logger.warning(f"⚠️ 实时获取新闻失败: {symbol}")

            except Exception as e:
                logger.error(f"❌ 实时获取新闻异常: {e}")

        return ok(data={
                "symbol": symbol,
                "hours_back": hours_back,
                "total_count": len(news_list),
                "news": news_list,
                "data_source": data_source
            },
            message=f"查询成功，返回 {len(news_list)} 条新闻（来源：{data_source}）"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询股票新闻失败: {str(e)}"
        )


@router.post("/query", response_model=dict)
async def query_news_advanced(
    request: NewsQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    高级新闻查询
    
    Args:
        request: 查询请求参数
        
    Returns:
        dict: 新闻数据列表
    """
    try:
        service = await get_news_data_service()
        
        # 构建查询参数
        params = NewsQueryParams(
            symbol=request.symbol,
            symbols=request.symbols,
            start_time=request.start_time,
            end_time=request.end_time,
            category=request.category,
            sentiment=request.sentiment,
            importance=request.importance,
            data_source=request.data_source,
            keywords=request.keywords,
            limit=request.limit,
            skip=request.skip
        )
        
        # 查询新闻
        news_list = await service.query_news(params)
        
        return ok(data={
                "query_params": request.dict(),
                "total_count": len(news_list),
                "news": news_list
            },
            message=f"高级查询成功，返回 {len(news_list)} 条新闻"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"高级新闻查询失败: {str(e)}"
        )


@router.get("/latest", response_model=dict)
async def get_latest_news(
    symbol: Optional[str] = Query(None, description="股票代码，为空则获取所有新闻"),
    limit: int = Query(10, description="返回数量限制"),
    hours_back: int = Query(24, description="回溯小时数"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取最新新闻
    
    Args:
        symbol: 股票代码，为空则获取所有新闻
        limit: 返回数量限制
        hours_back: 回溯小时数
        
    Returns:
        dict: 最新新闻列表
    """
    try:
        service = await get_news_data_service()
        
        # 获取最新新闻
        news_list = await service.get_latest_news(
            symbol=symbol,
            limit=limit,
            hours_back=hours_back
        )
        
        return ok(data={
                "symbol": symbol,
                "limit": limit,
                "hours_back": hours_back,
                "total_count": len(news_list),
                "news": news_list
            },
            message=f"获取最新新闻成功，返回 {len(news_list)} 条"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取最新新闻失败: {str(e)}"
        )


@router.get("/search", response_model=dict)
async def search_news(
    query: str = Query(..., description="搜索关键词"),
    symbol: Optional[str] = Query(None, description="股票代码过滤"),
    limit: int = Query(20, description="返回数量限制"),
    current_user: dict = Depends(get_current_user)
):
    """
    全文搜索新闻
    
    Args:
        query: 搜索关键词
        symbol: 股票代码过滤
        limit: 返回数量限制
        
    Returns:
        dict: 搜索结果列表
    """
    try:
        service = await get_news_data_service()
        
        # 全文搜索
        news_list = await service.search_news(
            query_text=query,
            symbol=symbol,
            limit=limit
        )
        
        return ok(data={
                "query": query,
                "symbol": symbol,
                "total_count": len(news_list),
                "news": news_list
            },
            message=f"搜索成功，返回 {len(news_list)} 条结果"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"新闻搜索失败: {str(e)}"
        )


@router.get("/statistics", response_model=dict)
async def get_news_statistics(
    symbol: Optional[str] = Query(None, description="股票代码"),
    days_back: int = Query(7, description="回溯天数"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取新闻统计信息
    
    Args:
        symbol: 股票代码
        days_back: 回溯天数
        
    Returns:
        dict: 新闻统计信息
    """
    try:
        service = await get_news_data_service()
        
        # 计算时间范围
        start_time = datetime.utcnow() - timedelta(days=days_back)
        
        # 获取统计信息
        stats = await service.get_news_statistics(
            symbol=symbol,
            start_time=start_time
        )
        
        return ok(data={
                "symbol": symbol,
                "days_back": days_back,
                "statistics": {
                    "total_count": stats.total_count,
                    "sentiment_distribution": {
                        "positive": stats.positive_count,
                        "negative": stats.negative_count,
                        "neutral": stats.neutral_count
                    },
                    "importance_distribution": {
                        "high": stats.high_importance_count,
                        "medium": stats.medium_importance_count,
                        "low": stats.low_importance_count
                    },
                    "categories": stats.categories,
                    "sources": stats.sources
                }
            },
            message="获取新闻统计成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取新闻统计失败: {str(e)}"
        )


@router.post("/sync/start", response_model=dict)
async def start_news_sync(
    request: NewsSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    启动新闻同步任务
    
    Args:
        request: 同步请求参数
        background_tasks: 后台任务
        
    Returns:
        dict: 任务启动结果
    """
    try:
        sync_service = await get_news_data_sync_service()
        
        # 添加后台同步任务
        if request.symbol:
            background_tasks.add_task(
                _execute_stock_news_sync,
                sync_service,
                request
            )
            message = f"股票 {request.symbol} 新闻同步任务已启动"
        else:
            background_tasks.add_task(
                _execute_market_news_sync,
                sync_service,
                request
            )
            message = "市场新闻同步任务已启动"
        
        return ok(data={
                "sync_type": "stock" if request.symbol else "market",
                "symbol": request.symbol,
                "data_sources": request.data_sources,
                "hours_back": request.hours_back,
                "max_news_per_source": request.max_news_per_source
            },
            message=message
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动新闻同步失败: {str(e)}"
        )


@router.post("/sync/single", response_model=dict)
async def sync_single_stock_news(
    symbol: str,
    data_sources: Optional[List[str]] = None,
    hours_back: int = 24,
    max_news_per_source: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    同步单只股票新闻（同步执行）
    
    Args:
        symbol: 股票代码
        data_sources: 数据源列表
        hours_back: 回溯小时数
        max_news_per_source: 每个数据源最大新闻数量
        
    Returns:
        dict: 同步结果
    """
    try:
        sync_service = await get_news_data_sync_service()
        
        # 执行同步
        stats = await sync_service.sync_stock_news(
            symbol=symbol,
            data_sources=data_sources,
            hours_back=hours_back,
            max_news_per_source=max_news_per_source
        )
        
        return ok(data={
                "symbol": symbol,
                "sync_stats": {
                    "total_processed": stats.total_processed,
                    "successful_saves": stats.successful_saves,
                    "failed_saves": stats.failed_saves,
                    "duplicate_skipped": stats.duplicate_skipped,
                    "sources_used": stats.sources_used,
                    "duration_seconds": stats.duration_seconds,
                    "success_rate": stats.success_rate
                }
            },
            message=f"股票 {symbol} 新闻同步完成，成功保存 {stats.successful_saves} 条"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步股票新闻失败: {str(e)}"
        )


@router.delete("/cleanup", response_model=dict)
async def cleanup_old_news(
    days_to_keep: int = Query(90, description="保留天数"),
    current_user: dict = Depends(get_current_user)
):
    """
    清理过期新闻
    
    Args:
        days_to_keep: 保留天数
        
    Returns:
        dict: 清理结果
    """
    try:
        service = await get_news_data_service()
        
        # 删除过期新闻
        deleted_count = await service.delete_old_news(days_to_keep)
        
        return ok(data={
                "days_to_keep": days_to_keep,
                "deleted_count": deleted_count
            },
            message=f"清理完成，删除 {deleted_count} 条过期新闻"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理过期新闻失败: {str(e)}"
        )


@router.get("/health", response_model=dict)
async def health_check():
    """健康检查"""
    try:
        service = await get_news_data_service()
        sync_service = await get_news_data_sync_service()
        
        return ok(data={
                "service_status": "healthy",
                "timestamp": datetime.utcnow().isoformat()
            },
            message="新闻数据服务运行正常"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"健康检查失败: {str(e)}"
        )


# 后台任务执行函数
async def _execute_stock_news_sync(sync_service, request: NewsSyncRequest):
    """执行股票新闻同步"""
    try:
        await sync_service.sync_stock_news(
            symbol=request.symbol,
            data_sources=request.data_sources,
            hours_back=request.hours_back,
            max_news_per_source=request.max_news_per_source
        )
    except Exception as e:
        logger.error(f"❌ 后台股票新闻同步失败: {e}")


async def _execute_market_news_sync(sync_service, request: NewsSyncRequest):
    """执行市场新闻同步"""
    try:
        await sync_service.sync_market_news(
            data_sources=request.data_sources,
            hours_back=request.hours_back,
            max_news_per_source=request.max_news_per_source
        )
    except Exception as e:
        logger.error(f"❌ 后台市场新闻同步失败: {e}")


# ==================== 批量导入接口 ====================

@router.post("/save", response_model=dict, dependencies=[Depends(require_pro)])
async def save_news_data_batch(
    request: NewsDataBatchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    批量保存新闻数据（优化版）[PRO]

    允许用户通过 API 批量导入新闻数据

    **权限要求**: 此功能为高级学员专属，需要 PRO 授权

    性能优化：
    - 使用批量查询减少数据库往返
    - 使用 bulk_write 批量操作
    - 数据验证前置

    Args:
        request: 批量保存请求，包含新闻列表和数据源标识

    Returns:
        dict: {
            "saved": 成功保存数量,
            "updated": 更新数量,
            "skipped": 跳过数量,
            "failed": 失败数量,
            "errors": 错误列表
        }
    """
    try:
        from app.core.database import get_mongo_db
        from pymongo import UpdateOne, InsertOne

        db = get_mongo_db()
        collection = db.stock_news

        # 数据验证和预处理
        valid_news = []
        errors = []
        failed_count = 0

        for idx, news_data in enumerate(request.news_list):
            try:
                # 验证必需字段
                required_fields = ["title", "url", "publish_time"]
                missing_fields = [f for f in required_fields if f not in news_data]

                if missing_fields:
                    errors.append({
                        "index": idx,
                        "error": f"缺少必需字段: {', '.join(missing_fields)}"
                    })
                    failed_count += 1
                    continue

                # 验证 URL 格式
                url = news_data["url"]
                if not (isinstance(url, str) and (url.startswith("http://") or url.startswith("https://"))):
                    errors.append({
                        "index": idx,
                        "url": url,
                        "error": "url 必须是有效的 HTTP/HTTPS 链接"
                    })
                    failed_count += 1
                    continue

                # 添加股票代码和元数据
                if request.symbol:
                    news_data["symbol"] = request.symbol
                    if "symbols" not in news_data:
                        news_data["symbols"] = [request.symbol]

                # 固定使用 custom 作为用户导入数据的标识
                news_data["data_source"] = "custom"
                news_data["updated_at"] = datetime.utcnow()

                # 转换 publish_time 为 datetime 对象（如果是字符串）
                if isinstance(news_data.get("publish_time"), str):
                    try:
                        news_data["publish_time"] = datetime.fromisoformat(
                            news_data["publish_time"].replace("Z", "+00:00")
                        )
                    except Exception as e:
                        errors.append({
                            "index": idx,
                            "error": f"无法解析 publish_time: {str(e)}"
                        })
                        failed_count += 1
                        continue

                valid_news.append((idx, news_data))

            except Exception as e:
                errors.append({
                    "index": idx,
                    "title": news_data.get("title", "unknown"),
                    "error": f"数据验证失败: {str(e)}"
                })
                failed_count += 1

        if not valid_news:
            return ok(
                data={
                    "saved": 0,
                    "updated": 0,
                    "skipped": 0,
                    "failed": failed_count,
                    "total": len(request.news_list),
                    "errors": errors[:10]
                },
                message="所有数据验证失败"
            )

        # 批量查询已存在的数据（基于 URL）
        urls = [news["url"] for _, news in valid_news]
        existing_docs = await collection.find({
            "url": {"$in": urls}
        }).to_list(length=None)

        existing_urls = {doc["url"]: doc for doc in existing_docs}

        # 准备批量操作
        bulk_operations = []
        saved_count = 0
        updated_count = 0
        skipped_count = 0

        for idx, news_data in valid_news:
            url = news_data["url"]

            if url in existing_urls:
                if request.overwrite:
                    # 批量更新
                    news_data["created_at"] = existing_urls[url].get("created_at", datetime.utcnow())
                    bulk_operations.append(
                        UpdateOne(
                            {"url": url},
                            {"$set": news_data}
                        )
                    )
                    updated_count += 1
                else:
                    # 跳过已存在的数据
                    skipped_count += 1
            else:
                # 批量插入
                news_data["created_at"] = datetime.utcnow()
                bulk_operations.append(InsertOne(news_data))
                saved_count += 1

        # 执行批量操作
        if bulk_operations:
            try:
                result = await collection.bulk_write(bulk_operations, ordered=False)
                logger.info(f"✅ 批量操作完成: 插入{result.inserted_count}, 更新{result.modified_count}")
            except Exception as e:
                logger.error(f"❌ 批量操作失败: {e}")
                # 如果批量操作失败，回退到逐条插入
                logger.warning("⚠️ 回退到逐条操作模式")
                saved_count = 0
                updated_count = 0

                for idx, news_data in valid_news:
                    try:
                        url = news_data["url"]
                        if url in existing_urls and request.overwrite:
                            await collection.update_one(
                                {"url": url},
                                {"$set": news_data}
                            )
                            updated_count += 1
                        elif url not in existing_urls:
                            await collection.insert_one(news_data)
                            saved_count += 1
                    except Exception as e2:
                        errors.append({
                            "index": idx,
                            "title": news_data.get("title", "unknown"),
                            "error": str(e2)
                        })
                        failed_count += 1

        return ok(
            data={
                "saved": saved_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "total": len(request.news_list),
                "errors": errors[:10]  # 只返回前10个错误
            },
            message=f"批量保存完成: 成功{saved_count}, 更新{updated_count}, 跳过{skipped_count}, 失败{failed_count}"
        )

    except Exception as e:
        logger.error(f"❌ 批量保存新闻数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量保存新闻数据失败: {str(e)}"
        )
