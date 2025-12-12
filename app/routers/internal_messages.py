"""
内部消息数据API路由
提供内部消息的查询、搜索和管理接口
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

from app.services.internal_message_service import (
    get_internal_message_service,
    InternalMessageQueryParams,
    InternalMessageStats
)
from app.core.response import ok

router = APIRouter(prefix="/api/internal-messages", tags=["internal-messages"])


class InternalMessage(BaseModel):
    """内部消息模型"""
    message_id: str
    message_type: str  # research_report/insider_info/analyst_note/meeting_minutes/internal_analysis
    title: str
    content: str
    summary: Optional[str] = ""
    source: Dict[str, Any]
    category: str
    subcategory: Optional[str] = ""
    tags: Optional[List[str]] = []
    importance: str = "medium"
    impact_scope: str = "stock_specific"
    time_sensitivity: str = "medium_term"
    confidence_level: float = Field(0.5, ge=0.0, le=1.0)
    sentiment: Optional[str] = "neutral"
    sentiment_score: Optional[float] = 0.0
    keywords: Optional[List[str]] = []
    risk_factors: Optional[List[str]] = []
    opportunities: Optional[List[str]] = []
    related_data: Optional[Dict[str, Any]] = {}
    access_level: str = "internal"
    permissions: Optional[List[str]] = []
    created_time: datetime
    effective_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    language: str = "zh-CN"
    data_source: str = "internal_system"


class InternalMessageBatchRequest(BaseModel):
    """批量保存内部消息请求"""
    symbol: str = Field(..., description="股票代码")
    messages: List[InternalMessage] = Field(..., description="内部消息列表")


class InternalMessageQueryRequest(BaseModel):
    """内部消息查询请求"""
    symbol: Optional[str] = None
    symbols: Optional[List[str]] = None
    message_type: Optional[str] = None
    category: Optional[str] = None
    source_type: Optional[str] = None
    department: Optional[str] = None
    author: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    importance: Optional[str] = None
    access_level: Optional[str] = None
    min_confidence: Optional[float] = None
    rating: Optional[str] = None
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    limit: int = Field(50, ge=1, le=1000)
    skip: int = Field(0, ge=0)


@router.post("/save", response_model=dict)
async def save_internal_messages(request: InternalMessageBatchRequest):
    """批量保存内部消息"""
    try:
        service = await get_internal_message_service()
        
        # 转换消息格式并添加股票代码
        messages = []
        for msg in request.messages:
            message_dict = msg.dict()
            message_dict["symbol"] = request.symbol
            messages.append(message_dict)
        
        # 保存消息
        result = await service.save_internal_messages(messages)
        
        return ok(data=result,
            message=f"成功保存 {result['saved']} 条内部消息"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存内部消息失败: {str(e)}")


@router.post("/query", response_model=dict)
async def query_internal_messages(request: InternalMessageQueryRequest):
    """查询内部消息"""
    try:
        service = await get_internal_message_service()
        
        # 构建查询参数
        params = InternalMessageQueryParams(
            symbol=request.symbol,
            symbols=request.symbols,
            message_type=request.message_type,
            category=request.category,
            source_type=request.source_type,
            department=request.department,
            author=request.author,
            start_time=request.start_time,
            end_time=request.end_time,
            importance=request.importance,
            access_level=request.access_level,
            min_confidence=request.min_confidence,
            rating=request.rating,
            keywords=request.keywords,
            tags=request.tags,
            limit=request.limit,
            skip=request.skip
        )
        
        # 执行查询
        messages = await service.query_internal_messages(params)
        
        return ok(data={
                "messages": messages,
                "count": len(messages),
                "params": request.dict()
            },
            message=f"查询到 {len(messages)} 条内部消息"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询内部消息失败: {str(e)}")


@router.get("/latest/{symbol}", response_model=dict)
async def get_latest_messages(
    symbol: str,
    message_type: Optional[str] = Query(None, description="消息类型"),
    access_level: Optional[str] = Query(None, description="访问级别"),
    limit: int = Query(20, ge=1, le=100, description="返回数量")
):
    """获取最新内部消息"""
    try:
        service = await get_internal_message_service()
        messages = await service.get_latest_messages(symbol, message_type, access_level, limit)
        
        return ok(data={
                "messages": messages,
                "count": len(messages),
                "symbol": symbol,
                "message_type": message_type,
                "access_level": access_level
            },
            message=f"获取到 {len(messages)} 条最新消息"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最新消息失败: {str(e)}")


@router.get("/search", response_model=dict)
async def search_messages(
    query: str = Query(..., description="搜索关键词"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    access_level: Optional[str] = Query(None, description="访问级别"),
    limit: int = Query(50, ge=1, le=200, description="返回数量")
):
    """全文搜索内部消息"""
    try:
        service = await get_internal_message_service()
        messages = await service.search_messages(query, symbol, access_level, limit)
        
        return ok(data={
                "messages": messages,
                "count": len(messages),
                "query": query,
                "symbol": symbol,
                "access_level": access_level
            },
            message=f"搜索到 {len(messages)} 条相关消息"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索消息失败: {str(e)}")


@router.get("/research-reports/{symbol}", response_model=dict)
async def get_research_reports(
    symbol: str,
    department: Optional[str] = Query(None, description="部门"),
    limit: int = Query(20, ge=1, le=100, description="返回数量")
):
    """获取研究报告"""
    try:
        service = await get_internal_message_service()
        reports = await service.get_research_reports(symbol, department, limit)
        
        return ok(data={
                "reports": reports,
                "count": len(reports),
                "symbol": symbol,
                "department": department
            },
            message=f"获取到 {len(reports)} 份研究报告"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取研究报告失败: {str(e)}")


@router.get("/analyst-notes/{symbol}", response_model=dict)
async def get_analyst_notes(
    symbol: str,
    author: Optional[str] = Query(None, description="分析师"),
    limit: int = Query(20, ge=1, le=100, description="返回数量")
):
    """获取分析师笔记"""
    try:
        service = await get_internal_message_service()
        notes = await service.get_analyst_notes(symbol, author, limit)
        
        return ok(data={
                "notes": notes,
                "count": len(notes),
                "symbol": symbol,
                "author": author
            },
            message=f"获取到 {len(notes)} 条分析师笔记"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分析师笔记失败: {str(e)}")


@router.get("/statistics", response_model=dict)
async def get_statistics(
    symbol: Optional[str] = Query(None, description="股票代码"),
    hours_back: int = Query(24, ge=1, le=168, description="回溯小时数")
):
    """获取内部消息统计信息"""
    try:
        service = await get_internal_message_service()
        
        # 计算时间范围
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        stats = await service.get_internal_statistics(symbol, start_time, end_time)
        
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


@router.get("/message-types", response_model=dict)
async def get_message_types():
    """获取支持的消息类型列表"""
    message_types = [
        {
            "code": "research_report",
            "name": "研究报告",
            "description": "深度研究分析报告"
        },
        {
            "code": "insider_info",
            "name": "内幕信息",
            "description": "内部获得的重要信息"
        },
        {
            "code": "analyst_note",
            "name": "分析师笔记",
            "description": "分析师的观点和笔记"
        },
        {
            "code": "meeting_minutes",
            "name": "会议纪要",
            "description": "重要会议的记录"
        },
        {
            "code": "internal_analysis",
            "name": "内部分析",
            "description": "内部团队的分析结果"
        }
    ]
    
    return ok(data={
            "message_types": message_types,
            "count": len(message_types)
        },
        message="消息类型列表获取成功"
    )


@router.get("/categories", response_model=dict)
async def get_categories():
    """获取支持的分类列表"""
    categories = [
        {
            "code": "fundamental_analysis",
            "name": "基本面分析",
            "description": "公司基本面相关分析"
        },
        {
            "code": "technical_analysis",
            "name": "技术分析",
            "description": "技术指标和图表分析"
        },
        {
            "code": "market_sentiment",
            "name": "市场情绪",
            "description": "市场情绪和投资者行为分析"
        },
        {
            "code": "risk_assessment",
            "name": "风险评估",
            "description": "投资风险评估和管理"
        }
    ]
    
    return ok(data={
            "categories": categories,
            "count": len(categories)
        },
        message="分类列表获取成功"
    )


@router.get("/health", response_model=dict)
async def health_check():
    """健康检查"""
    try:
        service = await get_internal_message_service()
        
        # 简单的连接测试
        collection = await service._get_collection()
        count = await collection.estimated_document_count()
        
        return ok(data={
                "status": "healthy",
                "total_messages": count,
                "service": "internal_message_service"
            },
            message="内部消息服务运行正常"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")
