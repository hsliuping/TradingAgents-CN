"""
新闻数据API路由
提供新闻数据查询、同步和管理接口
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query, status
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging
import akshare as ak

from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.services.news_data_service import get_news_data_service, NewsQueryParams
from app.worker.news_data_sync_service import get_news_data_sync_service
from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
from tradingagents.llm_adapters.openai_compatible_base import create_openai_compatible_llm
from langchain_core.prompts import ChatPromptTemplate

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


class NewsAnalysisRequest(BaseModel):
    title: str
    content: str
    model_name: Optional[str] = None


def _fetch_cls_news_stream(limit: int, hours_back: int, skip: int = 0) -> List[Dict[str, Any]]:
    try:
        df = ak.stock_info_global_cls()
    except Exception as e:
        logger.error(f"获取财联社新闻失败: {e}")
        return []

    now = datetime.utcnow()
    cutoff = now - timedelta(hours=hours_back)
    items: List[Dict[str, Any]] = []
    skipped = 0

    for idx, row in df.iterrows():
        try:
            date_str = str(row.get("发布日期") or "").strip()
            time_str = str(row.get("发布时间") or "").strip()
            title = str(row.get("标题") or "").strip()
            content = str(row.get("内容") or "").strip()
            url = (
                str(row.get("链接") or "").strip()
                or str(row.get("URL") or "").strip()
                or str(row.get("url") or "").strip()
            )

            if not title:
                continue

            dt_str = ""
            if date_str and time_str:
                dt_str = f"{date_str} {time_str}"
            elif date_str:
                dt_str = date_str

            publish_dt = None
            if dt_str:
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        publish_dt = datetime.strptime(dt_str, fmt)
                        break
                    except Exception:
                        continue
            if publish_dt is None:
                publish_dt = now

            if publish_dt < cutoff:
                continue

            if skipped < skip:
                skipped += 1
                continue

            item = {
                "id": f"cls_{idx}",
                "title": title,
                "content": content,
                "source": "财联社",
                "publish_time": publish_dt.isoformat(),
                "url": url or None,
                "symbol": None,
                "category": "macro",
                "data_source": "cls_akshare",
            }
            items.append(item)

            if len(items) >= limit:
                break
        except Exception as e:
            logger.error(f"处理财联社新闻行失败: {e}")
            continue

    return items


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
    skip: int = Query(0, description="跳过数量"),
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
        news_list = await service.get_latest_news(
            symbol=symbol,
            limit=limit,
            hours_back=hours_back,
            skip=skip
        )

        data_source = "database"

        if not news_list and symbol is None:
            logger.info("数据库中暂无市场新闻，使用财联社新闻流作为数据源")
            cls_items = _fetch_cls_news_stream(limit=limit, hours_back=hours_back, skip=skip)
            news_list = cls_items
            data_source = "cls_akshare"
            logger.info(f"财联社新闻流返回 {len(news_list)} 条记录")

        return ok(
            data={
                "symbol": symbol,
                "limit": limit,
                "hours_back": hours_back,
                "skip": skip,
                "total_count": len(news_list),
                "news": news_list,
                "data_source": data_source,
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


@router.post("/analyze", response_model=dict)
async def analyze_news(
    request: NewsAnalysisRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        model = request.model_name or "deepseek-chat"
        provider_info = get_provider_and_url_by_model_sync(model)
        provider = provider_info.get("provider")
        api_key = provider_info.get("api_key")
        backend_url = provider_info.get("backend_url")

        llm = create_openai_compatible_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=0.3,
            max_tokens=1200,
            base_url=backend_url,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位资深证券分析师，拥有10年以上A股/港股市场研究经验，熟悉中国证监会行业分类、"
                    "申万行业指数、产业链上下游关系及龙头公司基本面。请严格基于用户提供的新闻内容进行分析，"
                    "不得编造事实或引用外部知识。\n\n"
                    "【任务要求】\n"
                    "1. **概念识别**：\n"
                    "   - 仅提取新闻中**明确提及或强烈暗示**的产业链/技术/政策概念（如：低空经济、CPO光模块、创新药医保谈判）。\n"
                    "   - 概念必须属于以下范畴之一：\n"
                    "     • 新兴技术（如AI芯片、量子计算）\n"
                    "     • 政策驱动（如设备更新、以旧换新）\n"
                    "     • 行业事件（如OPEC+减产、苹果发布会）\n"
                    "     • 金融工具（如REITs、科创50ETF）\n"
                    "   - 排除泛泛而谈的词汇（如“经济复苏”、“市场波动”）。\n\n"
                    "2. **个股挖掘**：\n"
                    "   - 仅推荐**A股（60/00/30开头）或港股（00XXX.HK）** 的上市公司。\n"
                    "   - 必须满足以下任一条件：\n"
                    "     a) 公司在新闻中被直接点名；\n"
                    "     b) 公司是该概念公认的龙头（市值/市占率前3）；\n"
                    "     c) 公司主营业务与概念有直接且紧密的关联（需说明具体业务）。\n"
                    "   - **严禁推荐**：\n"
                    "     • 未上市企业（如“某独角兽”）\n"
                    "     • 模糊表述（如“相关概念股”）\n"
                    "     • 股票代码不完整（必须含交易所后缀，如 600519.SH）\n\n"
                    "【输出格式】\n"
                    "- 使用标准 Markdown\n"
                    "- 分为两个二级标题：`## 核心概念` 和 `## 相关个股`\n"
                    "- 概念用无序列表（`-`），每个概念不超过15字\n"
                    "- 个股用无序列表（`-`），格式：`[股票名称](股票代码)：关联理由（≤20字）`\n"
                    "- 若新闻无有效信息，输出：`无法从新闻中提取有效概念或个股。`\n\n"
                    "【重要原则】\n"
                    "❗ 宁可少说，不可错说！若不确定，请跳过该项。\n"
                    "❗ 所有结论必须严格基于新闻文本，禁止推测或补充背景知识。",
                ),
                (
                    "user",
                    "新闻标题：{title}\n\n新闻内容：{content}\n\n请开始分析。",
                ),
            ]
        )

        chain = prompt | llm
        result_msg = chain.invoke({"title": request.title, "content": request.content})
        content = getattr(result_msg, "content", "") or str(result_msg)

        return ok(
            data={
                "analysis": content,
                "model_name": model,
                "model_provider": provider,
            },
            message="新闻AI分析成功",
        )
    except Exception as e:
        logger.error(f"新闻AI分析失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"新闻AI分析失败: {str(e)}",
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
