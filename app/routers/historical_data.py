#!/usr/bin/env python3
"""
历史数据查询API
提供统一的历史K线数据查询接口
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.services.historical_data_service import get_historical_data_service
from app.routers.auth_db import get_current_user
from app.core.permissions import require_pro
from app.core.response import ok

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


class HistoricalKLineRecord(BaseModel):
    """历史K线数据记录"""
    trade_date: str = Field(..., description="交易日期 (YYYYMMDD 或 YYYY-MM-DD)")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    close: float = Field(..., description="收盘价")
    volume: float = Field(..., description="成交量(股)")
    amount: Optional[float] = Field(None, description="成交额(元)")
    pre_close: Optional[float] = Field(None, description="前收盘价")
    change: Optional[float] = Field(None, description="涨跌额")
    pct_chg: Optional[float] = Field(None, description="涨跌幅(%)")
    turnover_rate: Optional[float] = Field(None, description="换手率(%)")
    volume_ratio: Optional[float] = Field(None, description="量比")


class HistoricalKLineBatchRequest(BaseModel):
    """批量导入历史K线数据请求"""
    symbol: str = Field(..., description="股票代码（6位代码，如 600036）")
    period: str = Field("daily", description="数据周期：daily(日线)/weekly(周线)/monthly(月线)/5min/15min/30min/60min")
    records: List[HistoricalKLineRecord] = Field(..., description="K线数据列表")
    overwrite: bool = Field(False, description="是否覆盖已存在的数据")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "600036",
                "period": "daily",
                "records": [
                    {
                        "trade_date": "20240115",
                        "open": 45.23,
                        "high": 46.78,
                        "low": 45.01,
                        "close": 46.50,
                        "volume": 12345678,
                        "amount": 567890123.45,
                        "pre_close": 45.42,
                        "change": 1.08,
                        "pct_chg": 2.38,
                        "turnover_rate": 1.23,
                        "volume_ratio": 1.05
                    }
                ]
            }
        }


@router.post("/batch-import", response_model=dict, dependencies=[Depends(require_pro)])
async def batch_import_historical_kline(
    request: HistoricalKLineBatchRequest,
    current_user: dict = Depends(get_current_user)
):
    """批量导入历史K线数据 [PRO]

    **权限要求**: 此功能为高级学员专属，需要 PRO 授权

    **功能说明**:
    - 支持批量导入股票的历史K线数据
    - 数据源固定为 "local"（本地数据）
    - 支持多种周期：日线、周线、月线、分钟线
    - 自动去重：相同股票、日期、周期的数据会被更新

    **请求参数**:
    - symbol: 股票代码（6位代码，如 600036）
    - period: 数据周期（daily/weekly/monthly/5min/15min/30min/60min）
    - records: K线数据列表

    **返回结果**:
    - total: 总记录数
    - inserted: 新增记录数
    - updated: 更新记录数
    - failed: 失败记录数
    """
    try:
        # ========== 数据格式验证 ==========
        import re

        # 1. 验证股票代码格式（6位数字）
        if not re.match(r'^\d{6}$', request.symbol):
            raise HTTPException(
                status_code=400,
                detail=f"股票代码格式错误: {request.symbol}，必须是6位数字（如 600036）"
            )

        # 2. 验证周期格式
        valid_periods = ["daily", "weekly", "monthly", "5min", "15min", "30min", "60min"]
        if request.period not in valid_periods:
            raise HTTPException(
                status_code=400,
                detail=f"数据周期格式错误: {request.period}，必须是以下之一: {', '.join(valid_periods)}"
            )

        # 3. 验证记录数量
        if len(request.records) == 0:
            raise HTTPException(status_code=400, detail="K线数据列表不能为空")

        if len(request.records) > 10000:
            raise HTTPException(
                status_code=400,
                detail=f"单次导入记录数过多: {len(request.records)} 条，最多支持 10000 条"
            )

        # 4. 验证每条记录的日期格式和数据有效性
        invalid_records = []
        for idx, record in enumerate(request.records):
            errors = []

            # 验证日期格式（支持 YYYYMMDD 或 YYYY-MM-DD）
            trade_date = record.trade_date
            if not re.match(r'^\d{8}$', trade_date) and not re.match(r'^\d{4}-\d{2}-\d{2}$', trade_date):
                errors.append(f"日期格式错误: {trade_date}，必须是 YYYYMMDD 或 YYYY-MM-DD")

            # 验证价格数据（必须 > 0）
            if record.open <= 0:
                errors.append(f"开盘价必须大于0: {record.open}")
            if record.high <= 0:
                errors.append(f"最高价必须大于0: {record.high}")
            if record.low <= 0:
                errors.append(f"最低价必须大于0: {record.low}")
            if record.close <= 0:
                errors.append(f"收盘价必须大于0: {record.close}")

            # 验证价格逻辑（最高价 >= 最低价）
            if record.high < record.low:
                errors.append(f"最高价({record.high})不能小于最低价({record.low})")

            # 验证成交量（必须 >= 0）
            if record.volume < 0:
                errors.append(f"成交量不能为负数: {record.volume}")

            # 验证成交额（如果有，必须 >= 0）
            if record.amount is not None and record.amount < 0:
                errors.append(f"成交额不能为负数: {record.amount}")

            if errors:
                invalid_records.append({
                    "index": idx,
                    "trade_date": trade_date,
                    "errors": errors
                })

        # 如果有无效记录，返回详细错误信息
        if invalid_records:
            error_details = []
            for rec in invalid_records[:5]:  # 只显示前5条错误
                error_details.append(f"第{rec['index']+1}条记录({rec['trade_date']}): {'; '.join(rec['errors'])}")

            error_msg = f"发现 {len(invalid_records)} 条无效记录:\n" + "\n".join(error_details)
            if len(invalid_records) > 5:
                error_msg += f"\n... 还有 {len(invalid_records) - 5} 条错误记录"

            raise HTTPException(status_code=400, detail=error_msg)

        # ========== 数据转换和保存 ==========
        service = await get_historical_data_service()

        # 转换数据格式
        import pandas as pd

        # 构建 DataFrame
        records_data = []
        for record in request.records:
            record_dict = record.dict()
            # 标准化日期格式（移除横杠，统一为 YYYYMMDD）
            trade_date = record_dict["trade_date"].replace("-", "")
            record_dict["trade_date"] = trade_date
            records_data.append(record_dict)

        df = pd.DataFrame(records_data)

        # 设置 trade_date 为索引
        df.set_index("trade_date", inplace=True)

        # 保存到数据库（数据源固定为 "local"）
        saved_count = await service.save_historical_data(
            symbol=request.symbol,
            data=df,
            data_source="local",  # 固定为 local
            market="CN",  # 默认为 A股
            period=request.period
        )

        return ok(
            data={
                "symbol": request.symbol,
                "period": request.period,
                "total": len(request.records),
                "saved": saved_count,
                "data_source": "local"
            },
            message=f"成功导入 {saved_count} 条历史K线数据"
        )

    except HTTPException:
        # 重新抛出 HTTPException（包含验证错误）
        raise
    except Exception as e:
        logger.error(f"批量导入历史K线数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量导入失败: {str(e)}")


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
