#!/usr/bin/env python3
"""
历史数据查询API
提供统一的历史K线数据查询接口
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.historical_data_service import get_historical_data_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/historical-data", tags=["历史数据"])


class HistoricalDataQuery(BaseModel):
    """历史数据查询请求"""
    symbol: str = Field(..., description="股票代码")
    start_date: Optional[str] = Field(None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="结束日期 (YYYY-MM-DD)")
    data_source: Optional[str] = Field(None, description="数据源 (tushare/akshare/baostock)")
    period: Optional[str] = Field(None, description="数据周期 (daily/weekly/monthly)")
    limit: Optional[int] = Field(None, ge=1, le=1000, description="限制返回数量")


class HistoricalDataResponse(BaseModel):
    """历史数据响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


@router.get("/query/{symbol}", response_model=HistoricalDataResponse)
async def get_historical_data(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    data_source: Optional[str] = Query(None, description="数据源 (tushare/akshare/baostock)"),
    period: Optional[str] = Query(None, description="数据周期 (daily/weekly/monthly)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="限制返回数量")
):
    """
    查询股票历史数据
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        data_source: 数据源筛选
        period: 数据周期筛选
        limit: 限制返回数量
    """
    try:
        service = await get_historical_data_service()
        
        # 查询历史数据
        results = await service.get_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source,
            period=period,
            limit=limit
        )
        
        # 格式化响应
        response_data = {
            "symbol": symbol,
            "count": len(results),
            "query_params": {
                "start_date": start_date,
                "end_date": end_date,
                "data_source": data_source,
                "period": period,
                "limit": limit
            },
            "records": results
        }
        
        return HistoricalDataResponse(
            success=True,
            message=f"查询成功，返回 {len(results)} 条记录",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"查询历史数据失败 {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.post("/query", response_model=HistoricalDataResponse)
async def query_historical_data(request: HistoricalDataQuery):
    """
    POST方式查询历史数据
    """
    try:
        service = await get_historical_data_service()
        
        # 查询历史数据
        results = await service.get_historical_data(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            data_source=request.data_source,
            period=request.period,
            limit=request.limit
        )
        
        # 格式化响应
        response_data = {
            "symbol": request.symbol,
            "count": len(results),
            "query_params": request.dict(),
            "records": results
        }
        
        return HistoricalDataResponse(
            success=True,
            message=f"查询成功，返回 {len(results)} 条记录",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"查询历史数据失败 {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.get("/latest-date/{symbol}")
async def get_latest_date(
    symbol: str,
    data_source: str = Query(..., description="数据源 (tushare/akshare/baostock)")
):
    """获取股票最新数据日期"""
    try:
        service = await get_historical_data_service()
        latest_date = await service.get_latest_date(symbol, data_source)
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "data_source": data_source,
                "latest_date": latest_date
            },
            "message": "查询成功"
        }
        
    except Exception as e:
        logger.error(f"获取最新日期失败 {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.get("/statistics")
async def get_data_statistics():
    """获取历史数据统计信息"""
    try:
        service = await get_historical_data_service()
        stats = await service.get_data_statistics()
        
        return {
            "success": True,
            "data": stats,
            "message": "统计信息获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {e}")


@router.get("/compare/{symbol}")
async def compare_data_sources(
    symbol: str,
    trade_date: str = Query(..., description="交易日期 (YYYY-MM-DD)")
):
    """
    对比不同数据源的同一股票同一日期的数据
    """
    try:
        service = await get_historical_data_service()
        
        # 查询三个数据源的数据
        sources = ["tushare", "akshare", "baostock"]
        comparison = {}
        
        for source in sources:
            results = await service.get_historical_data(
                symbol=symbol,
                start_date=trade_date,
                end_date=trade_date,
                data_source=source,
                limit=1
            )
            
            if results:
                comparison[source] = results[0]
            else:
                comparison[source] = None
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "trade_date": trade_date,
                "comparison": comparison,
                "available_sources": [k for k, v in comparison.items() if v is not None]
            },
            "message": "数据对比完成"
        }
        
    except Exception as e:
        logger.error(f"数据对比失败 {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"数据对比失败: {e}")


@router.get("/health")
async def health_check():
    """健康检查"""
    try:
        service = await get_historical_data_service()
        stats = await service.get_data_statistics()
        
        return {
            "success": True,
            "data": {
                "service": "历史数据服务",
                "status": "healthy",
                "total_records": stats.get("total_records", 0),
                "total_symbols": stats.get("total_symbols", 0),
                "last_check": datetime.utcnow().isoformat()
            },
            "message": "服务正常"
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "success": False,
            "data": {
                "service": "历史数据服务",
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            },
            "message": "服务异常"
        }
