#!/usr/bin/env python3
"""
多周期数据同步API
提供日线、周线、月线数据的同步管理接口
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.worker.multi_period_sync_service import get_multi_period_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/multi-period-sync", tags=["多周期同步"])


class MultiPeriodSyncRequest(BaseModel):
    """多周期同步请求"""
    symbols: Optional[List[str]] = Field(None, description="股票代码列表，None表示所有股票")
    periods: Optional[List[str]] = Field(["daily"], description="周期列表 (daily/weekly/monthly)")
    data_sources: Optional[List[str]] = Field(["tushare", "akshare", "baostock"], description="数据源列表")
    start_date: Optional[str] = Field(None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="结束日期 (YYYY-MM-DD)")
    all_history: Optional[bool] = Field(False, description="是否同步所有历史数据（忽略时间范围）")


class MultiPeriodSyncResponse(BaseModel):
    """多周期同步响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


@router.post("/start", response_model=MultiPeriodSyncResponse)
async def start_multi_period_sync(
    request: MultiPeriodSyncRequest,
    background_tasks: BackgroundTasks
):
    """
    启动多周期数据同步
    """
    try:
        service = await get_multi_period_sync_service()
        
        # 后台任务执行同步
        background_tasks.add_task(
            service.sync_multi_period_data,
            symbols=request.symbols,
            periods=request.periods,
            data_sources=request.data_sources,
            start_date=request.start_date,
            end_date=request.end_date,
            all_history=request.all_history
        )
        
        return MultiPeriodSyncResponse(
            success=True,
            message="多周期数据同步已启动",
            data={
                "request_params": request.dict(),
                "start_time": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"启动多周期同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动同步失败: {e}")


@router.post("/start-daily", response_model=MultiPeriodSyncResponse)
async def start_daily_sync(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None,
    data_sources: Optional[List[str]] = None
):
    """启动日线数据同步"""
    try:
        service = await get_multi_period_sync_service()
        
        background_tasks.add_task(
            service.sync_multi_period_data,
            symbols=symbols,
            periods=["daily"],
            data_sources=data_sources or ["tushare", "akshare", "baostock"]
        )
        
        return MultiPeriodSyncResponse(
            success=True,
            message="日线数据同步已启动",
            data={
                "period": "daily",
                "start_time": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"启动日线同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动日线同步失败: {e}")


@router.post("/start-weekly", response_model=MultiPeriodSyncResponse)
async def start_weekly_sync(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None,
    data_sources: Optional[List[str]] = None
):
    """启动周线数据同步"""
    try:
        service = await get_multi_period_sync_service()
        
        background_tasks.add_task(
            service.sync_multi_period_data,
            symbols=symbols,
            periods=["weekly"],
            data_sources=data_sources or ["tushare", "akshare", "baostock"]
        )
        
        return MultiPeriodSyncResponse(
            success=True,
            message="周线数据同步已启动",
            data={
                "period": "weekly",
                "start_time": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"启动周线同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动周线同步失败: {e}")


@router.post("/start-monthly", response_model=MultiPeriodSyncResponse)
async def start_monthly_sync(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None,
    data_sources: Optional[List[str]] = None
):
    """启动月线数据同步"""
    try:
        service = await get_multi_period_sync_service()

        background_tasks.add_task(
            service.sync_multi_period_data,
            symbols=symbols,
            periods=["monthly"],
            data_sources=data_sources or ["tushare", "akshare", "baostock"]
        )

        return MultiPeriodSyncResponse(
            success=True,
            message="月线数据同步已启动",
            data={
                "period": "monthly",
                "start_time": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        logger.error(f"启动月线同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动月线同步失败: {e}")


@router.post("/start-all-history", response_model=MultiPeriodSyncResponse)
async def start_all_history_sync(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None,
    periods: Optional[List[str]] = None,
    data_sources: Optional[List[str]] = None
):
    """启动全历史数据同步（从1990年开始）"""
    try:
        service = await get_multi_period_sync_service()

        background_tasks.add_task(
            service.sync_multi_period_data,
            symbols=symbols,
            periods=periods or ["daily", "weekly", "monthly"],
            data_sources=data_sources or ["tushare", "akshare", "baostock"],
            all_history=True
        )

        return MultiPeriodSyncResponse(
            success=True,
            message="全历史数据同步已启动（从1990年开始）",
            data={
                "sync_type": "all_history",
                "periods": periods or ["daily", "weekly", "monthly"],
                "data_sources": data_sources or ["tushare", "akshare", "baostock"],
                "date_range": "1990-01-01 到 今天",
                "start_time": datetime.utcnow().isoformat(),
                "warning": "全历史数据同步可能需要很长时间，请耐心等待"
            }
        )

    except Exception as e:
        logger.error(f"启动全历史同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动全历史同步失败: {e}")


@router.post("/start-incremental", response_model=MultiPeriodSyncResponse)
async def start_incremental_sync(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None,
    periods: Optional[List[str]] = None,
    data_sources: Optional[List[str]] = None,
    days_back: Optional[int] = 30
):
    """启动增量数据同步（最近N天）"""
    try:
        from datetime import datetime, timedelta

        service = await get_multi_period_sync_service()

        # 计算增量同步的日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        background_tasks.add_task(
            service.sync_multi_period_data,
            symbols=symbols,
            periods=periods or ["daily"],
            data_sources=data_sources or ["tushare", "akshare", "baostock"],
            start_date=start_date,
            end_date=end_date
        )

        return MultiPeriodSyncResponse(
            success=True,
            message=f"增量数据同步已启动（最近{days_back}天）",
            data={
                "sync_type": "incremental",
                "periods": periods or ["daily"],
                "data_sources": data_sources or ["tushare", "akshare", "baostock"],
                "date_range": f"{start_date} 到 {end_date}",
                "days_back": days_back,
                "start_time": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        logger.error(f"启动增量同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动增量同步失败: {e}")


@router.get("/statistics")
async def get_sync_statistics():
    """获取多周期同步统计信息"""
    try:
        service = await get_multi_period_sync_service()
        stats = await service.get_sync_statistics()
        
        return {
            "success": True,
            "data": stats,
            "message": "统计信息获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取同步统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {e}")


@router.get("/period-comparison/{symbol}")
async def compare_period_data(
    symbol: str,
    trade_date: str,
    data_source: str = "tushare"
):
    """
    对比同一股票不同周期的数据
    """
    try:
        from app.services.historical_data_service import get_historical_data_service
        service = await get_historical_data_service()
        
        periods = ["daily", "weekly", "monthly"]
        comparison = {}
        
        for period in periods:
            results = await service.get_historical_data(
                symbol=symbol,
                start_date=trade_date,
                end_date=trade_date,
                data_source=data_source,
                period=period,
                limit=1
            )
            
            if results:
                comparison[period] = results[0]
            else:
                comparison[period] = None
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "trade_date": trade_date,
                "data_source": data_source,
                "comparison": comparison,
                "available_periods": [k for k, v in comparison.items() if v is not None]
            },
            "message": "周期数据对比完成"
        }
        
    except Exception as e:
        logger.error(f"周期数据对比失败 {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"周期数据对比失败: {e}")


@router.get("/supported-periods")
async def get_supported_periods():
    """获取支持的数据周期"""
    return {
        "success": True,
        "data": {
            "periods": [
                {
                    "code": "daily",
                    "name": "日线",
                    "description": "每日交易数据",
                    "supported_sources": ["tushare", "akshare", "baostock"]
                },
                {
                    "code": "weekly",
                    "name": "周线",
                    "description": "每周交易数据",
                    "supported_sources": ["tushare", "akshare", "baostock"]
                },
                {
                    "code": "monthly",
                    "name": "月线",
                    "description": "每月交易数据",
                    "supported_sources": ["tushare", "akshare", "baostock"]
                }
            ],
            "data_sources": [
                {
                    "code": "tushare",
                    "name": "Tushare",
                    "description": "专业金融数据服务",
                    "supported_periods": ["daily", "weekly", "monthly"]
                },
                {
                    "code": "akshare",
                    "name": "AKShare",
                    "description": "免费开源金融数据",
                    "supported_periods": ["daily", "weekly", "monthly"]
                },
                {
                    "code": "baostock",
                    "name": "BaoStock",
                    "description": "免费证券数据平台",
                    "supported_periods": ["daily", "weekly", "monthly"]
                }
            ]
        },
        "message": "支持的周期信息获取成功"
    }


@router.get("/health")
async def health_check():
    """健康检查"""
    try:
        service = await get_multi_period_sync_service()
        stats = await service.get_sync_statistics()
        
        return {
            "success": True,
            "data": {
                "service": "多周期同步服务",
                "status": "healthy",
                "statistics": stats,
                "last_check": datetime.utcnow().isoformat()
            },
            "message": "服务正常"
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "success": False,
            "data": {
                "service": "多周期同步服务",
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            },
            "message": "服务异常"
        }
