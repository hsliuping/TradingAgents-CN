"""
社媒消息数据API路由
提供社媒消息的查询、搜索和统计接口
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

from app.services.social_media_service import (
    get_social_media_service,
    SocialMediaQueryParams,
    SocialMediaStats
)
from app.core.response import ok

router = APIRouter(prefix="/api/social-media", tags=["social-media"])


class SocialMediaMessage(BaseModel):
    """社媒消息模型"""
    message_id: str
    platform: str
    message_type: str = "post"
    content: str
    media_urls: Optional[List[str]] = []
    hashtags: Optional[List[str]] = []
    author: Dict[str, Any]
    engagement: Dict[str, Any]
    publish_time: datetime
    sentiment: Optional[str] = "neutral"
    sentiment_score: Optional[float] = 0.0
    keywords: Optional[List[str]] = []
    topics: Optional[List[str]] = []
    importance: Optional[str] = "low"
    credibility: Optional[str] = "medium"
    location: Optional[Dict[str, str]] = None
    language: str = "zh-CN"
    data_source: str
    crawler_version: str = "1.0"


class SocialMediaBatchRequest(BaseModel):
    """批量保存社媒消息请求"""
    symbol: str = Field(..., description="股票代码")
    messages: List[SocialMediaMessage] = Field(..., description="社媒消息列表")


class SocialMediaQueryRequest(BaseModel):
    """社媒消息查询请求"""
    symbol: Optional[str] = None
    symbols: Optional[List[str]] = None
    platform: Optional[str] = None
    message_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    sentiment: Optional[str] = None
    importance: Optional[str] = None
    min_influence_score: Optional[float] = None
    min_engagement_rate: Optional[float] = None
    verified_only: bool = False
    keywords: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    limit: int = Field(50, ge=1, le=1000)
    skip: int = Field(0, ge=0)


@router.post("/save", response_model=dict)
async def save_social_media_messages(request: SocialMediaBatchRequest):
    """批量保存社媒消息"""
    try:
        service = await get_social_media_service()

        # 转换消息格式并添加股票代码
        messages = []
        for msg in request.messages:
            message_dict = msg.dict()
            message_dict["symbol"] = request.symbol
            messages.append(message_dict)

        # 保存消息
        result = await service.save_social_media_messages(messages)

        return ok(
            data=result,
            message=f"成功保存 {result['saved']} 条社媒消息"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存社媒消息失败: {str(e)}")


@router.post("/query", response_model=dict)
async def query_social_media_messages(request: SocialMediaQueryRequest):
    """查询社媒消息"""
    try:
        service = await get_social_media_service()

        # 构建查询参数
        params = SocialMediaQueryParams(
            symbol=request.symbol,
            symbols=request.symbols,
            platform=request.platform,
            message_type=request.message_type,
            start_time=request.start_time,
            end_time=request.end_time,
            sentiment=request.sentiment,
            importance=request.importance,
            min_influence_score=request.min_influence_score,
            min_engagement_rate=request.min_engagement_rate,
            verified_only=request.verified_only,
            keywords=request.keywords,
            hashtags=request.hashtags,
            limit=request.limit,
            skip=request.skip
        )

        # 执行查询
        messages = await service.query_social_media_messages(params)

        return ok(
            data={
                "messages": messages,
                "count": len(messages),
                "params": request.dict()
            },
            message=f"查询到 {len(messages)} 条社媒消息"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询社媒消息失败: {str(e)}")


@router.get("/latest/{symbol}", response_model=dict)
async def get_latest_messages(
    symbol: str,
    platform: Optional[str] = Query(None, description="平台类型"),
    limit: int = Query(20, ge=1, le=100, description="返回数量")
):
    """获取最新社媒消息"""
    try:
        service = await get_social_media_service()
        messages = await service.get_latest_messages(symbol, platform, limit)
        
        return ok(data={
                "messages": messages,
                "count": len(messages),
                "symbol": symbol,
                "platform": platform
            },
            message=f"获取到 {len(messages)} 条最新消息"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最新消息失败: {str(e)}")


@router.get("/search", response_model=dict)
async def search_messages(
    query: str = Query(..., description="搜索关键词"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    platform: Optional[str] = Query(None, description="平台类型"),
    limit: int = Query(50, ge=1, le=200, description="返回数量")
):
    """全文搜索社媒消息"""
    try:
        service = await get_social_media_service()
        messages = await service.search_messages(query, symbol, platform, limit)

        return ok(
            data={
                "messages": messages,
                "count": len(messages),
                "query": query,
                "symbol": symbol,
                "platform": platform
            },
            message=f"搜索到 {len(messages)} 条相关消息"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索消息失败: {str(e)}")


@router.get("/statistics", response_model=dict)
async def get_statistics(
    symbol: Optional[str] = Query(None, description="股票代码"),
    hours_back: int = Query(24, ge=1, le=168, description="回溯小时数")
):
    """获取社媒消息统计信息"""
    try:
        service = await get_social_media_service()
        
        # 计算时间范围
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        stats = await service.get_social_media_statistics(symbol, start_time, end_time)
        
        return ok(data={
                "statistics": stats.__dict__,
                "symbol": symbol,
                "time_range": {
                    "start_time": start_time,
                    "end_time": end_time,
                    "hours_back": hours_back
                }
            },
            message="统计信息获取成功"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/platforms", response_model=dict)
async def get_supported_platforms():
    """获取支持的社媒平台列表"""
    platforms = [
        {
            "code": "weibo",
            "name": "微博",
            "description": "新浪微博社交平台"
        },
        {
            "code": "wechat",
            "name": "微信",
            "description": "微信公众号和朋友圈"
        },
        {
            "code": "douyin",
            "name": "抖音",
            "description": "字节跳动短视频平台"
        },
        {
            "code": "xiaohongshu",
            "name": "小红书",
            "description": "生活方式分享平台"
        },
        {
            "code": "zhihu",
            "name": "知乎",
            "description": "知识问答社区"
        },
        {
            "code": "twitter",
            "name": "Twitter",
            "description": "国际社交媒体平台"
        },
        {
            "code": "reddit",
            "name": "Reddit",
            "description": "国际论坛社区"
        }
    ]
    
    return ok(data={
            "platforms": platforms,
            "count": len(platforms)
        },
        message="支持的平台列表获取成功"
    )


@router.get("/sentiment-analysis/{symbol}", response_model=dict)
async def get_sentiment_analysis(
    symbol: str,
    platform: Optional[str] = Query(None, description="平台类型"),
    hours_back: int = Query(24, ge=1, le=168, description="回溯小时数")
):
    """获取股票的社媒情绪分析"""
    try:
        service = await get_social_media_service()
        
        # 计算时间范围
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        # 查询消息
        params = SocialMediaQueryParams(
            symbol=symbol,
            platform=platform,
            start_time=start_time,
            end_time=end_time,
            limit=1000
        )
        
        messages = await service.query_social_media_messages(params)
        
        # 分析情绪分布
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        platform_sentiment = {}
        hourly_sentiment = {}
        
        for msg in messages:
            sentiment = msg.get("sentiment", "neutral")
            sentiment_counts[sentiment] += 1
            
            # 按平台统计
            msg_platform = msg.get("platform", "unknown")
            if msg_platform not in platform_sentiment:
                platform_sentiment[msg_platform] = {"positive": 0, "negative": 0, "neutral": 0}
            platform_sentiment[msg_platform][sentiment] += 1
            
            # 按小时统计
            publish_time = msg.get("publish_time")
            if publish_time:
                hour_key = publish_time.strftime("%Y-%m-%d %H:00")
                if hour_key not in hourly_sentiment:
                    hourly_sentiment[hour_key] = {"positive": 0, "negative": 0, "neutral": 0}
                hourly_sentiment[hour_key][sentiment] += 1
        
        # 计算情绪指数 (positive: +1, neutral: 0, negative: -1)
        total_messages = len(messages)
        sentiment_score = 0
        if total_messages > 0:
            sentiment_score = (sentiment_counts["positive"] - sentiment_counts["negative"]) / total_messages
        
        return ok(data={
                "symbol": symbol,
                "total_messages": total_messages,
                "sentiment_distribution": sentiment_counts,
                "sentiment_score": sentiment_score,
                "platform_sentiment": platform_sentiment,
                "hourly_sentiment": hourly_sentiment,
                "time_range": {
                    "start_time": start_time,
                    "end_time": end_time,
                    "hours_back": hours_back
                }
            },
            message=f"情绪分析完成，共分析 {total_messages} 条消息"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"情绪分析失败: {str(e)}")


@router.get("/health", response_model=dict)
async def health_check():
    """健康检查"""
    try:
        service = await get_social_media_service()
        
        # 简单的连接测试
        collection = await service._get_collection()
        count = await collection.estimated_document_count()
        
        return ok(data={
                "status": "healthy",
                "total_messages": count,
                "service": "social_media_service"
            },
            message="社媒消息服务运行正常"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")
