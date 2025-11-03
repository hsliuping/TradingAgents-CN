"""
股票数据同步API路由
支持单个股票或批量股票的历史数据和财务数据同步
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.worker.tushare_sync_service import get_tushare_sync_service
from app.worker.akshare_sync_service import get_akshare_sync_service
from app.worker.financial_data_sync_service import get_financial_sync_service
import logging

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/stock-sync", tags=["股票数据同步"])


class SingleStockSyncRequest(BaseModel):
    """单股票同步请求"""
    symbol: str = Field(..., description="股票代码（6位）")
    sync_realtime: bool = Field(False, description="是否同步实时行情")
    sync_historical: bool = Field(True, description="是否同步历史数据")
    sync_financial: bool = Field(True, description="是否同步财务数据")
    data_source: str = Field("tushare", description="数据源: tushare/akshare")
    days: int = Field(30, description="历史数据天数", ge=1, le=3650)


class BatchStockSyncRequest(BaseModel):
    """批量股票同步请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    sync_historical: bool = Field(True, description="是否同步历史数据")
    sync_financial: bool = Field(True, description="是否同步财务数据")
    data_source: str = Field("tushare", description="数据源: tushare/akshare")
    days: int = Field(30, description="历史数据天数", ge=1, le=3650)


@router.post("/single")
async def sync_single_stock(
    request: SingleStockSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    同步单个股票的历史数据、财务数据和实时行情

    - **symbol**: 股票代码（6位）
    - **sync_realtime**: 是否同步实时行情
    - **sync_historical**: 是否同步历史数据
    - **sync_financial**: 是否同步财务数据
    - **data_source**: 数据源（tushare/akshare）
    - **days**: 历史数据天数
    """
    try:
        logger.info(f"📊 开始同步单个股票: {request.symbol} (数据源: {request.data_source})")

        result = {
            "symbol": request.symbol,
            "realtime_sync": None,
            "historical_sync": None,
            "financial_sync": None
        }

        # 同步实时行情
        if request.sync_realtime:
            try:
                if request.data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif request.data_source == "akshare":
                    service = await get_akshare_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {request.data_source}")

                # 同步实时行情（只同步指定的股票）
                realtime_result = await service.sync_realtime_quotes(
                    symbols=[request.symbol],
                    force=True  # 强制执行，跳过交易时间检查
                )

                success = realtime_result.get("success_count", 0) > 0
                result["realtime_sync"] = {
                    "success": success,
                    "message": f"实时行情同步{'成功' if success else '失败'}"
                }
                logger.info(f"✅ {request.symbol} 实时行情同步完成: {success}")

            except Exception as e:
                logger.error(f"❌ {request.symbol} 实时行情同步失败: {e}")
                result["realtime_sync"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # 同步历史数据
        if request.sync_historical:
            try:
                if request.data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif request.data_source == "akshare":
                    service = await get_akshare_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {request.data_source}")
                
                # 计算日期范围
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=request.days)).strftime('%Y-%m-%d')
                
                # 同步历史数据
                hist_result = await service.sync_historical_data(
                    symbols=[request.symbol],
                    start_date=start_date,
                    end_date=end_date,
                    incremental=False
                )
                
                result["historical_sync"] = {
                    "success": hist_result.get("success_count", 0) > 0,
                    "records": hist_result.get("total_records", 0),
                    "message": f"同步了 {hist_result.get('total_records', 0)} 条历史记录"
                }
                logger.info(f"✅ {request.symbol} 历史数据同步完成: {hist_result.get('total_records', 0)} 条记录")
                
            except Exception as e:
                logger.error(f"❌ {request.symbol} 历史数据同步失败: {e}")
                result["historical_sync"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # 同步财务数据
        if request.sync_financial:
            try:
                financial_service = await get_financial_sync_service()
                
                # 同步财务数据
                fin_result = await financial_service.sync_single_stock(
                    symbol=request.symbol,
                    data_sources=[request.data_source]
                )
                
                success = fin_result.get(request.data_source, False)
                result["financial_sync"] = {
                    "success": success,
                    "message": "财务数据同步成功" if success else "财务数据同步失败"
                }
                logger.info(f"✅ {request.symbol} 财务数据同步完成: {success}")
                
            except Exception as e:
                logger.error(f"❌ {request.symbol} 财务数据同步失败: {e}")
                result["financial_sync"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # 判断整体是否成功
        overall_success = (
            (not request.sync_realtime or result["realtime_sync"].get("success", False)) and
            (not request.sync_historical or result["historical_sync"].get("success", False)) and
            (not request.sync_financial or result["financial_sync"].get("success", False))
        )

        # 添加整体成功标志到结果中
        result["overall_success"] = overall_success

        return ok(
            data=result,
            message=f"股票 {request.symbol} 数据同步{'成功' if overall_success else '部分失败'}"
        )
        
    except Exception as e:
        logger.error(f"❌ 同步单个股票失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/batch")
async def sync_batch_stocks(
    request: BatchStockSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    批量同步多个股票的历史数据和财务数据
    
    - **symbols**: 股票代码列表
    - **sync_historical**: 是否同步历史数据
    - **sync_financial**: 是否同步财务数据
    - **data_source**: 数据源（tushare/akshare）
    - **days**: 历史数据天数
    """
    try:
        logger.info(f"📊 开始批量同步 {len(request.symbols)} 只股票 (数据源: {request.data_source})")
        
        result = {
            "total": len(request.symbols),
            "symbols": request.symbols,
            "historical_sync": None,
            "financial_sync": None
        }
        
        # 同步历史数据
        if request.sync_historical:
            try:
                if request.data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif request.data_source == "akshare":
                    service = await get_akshare_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {request.data_source}")
                
                # 计算日期范围
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=request.days)).strftime('%Y-%m-%d')
                
                # 批量同步历史数据
                hist_result = await service.sync_historical_data(
                    symbols=request.symbols,
                    start_date=start_date,
                    end_date=end_date,
                    incremental=False
                )
                
                result["historical_sync"] = {
                    "success_count": hist_result.get("success_count", 0),
                    "error_count": hist_result.get("error_count", 0),
                    "total_records": hist_result.get("total_records", 0),
                    "message": f"成功同步 {hist_result.get('success_count', 0)}/{len(request.symbols)} 只股票，共 {hist_result.get('total_records', 0)} 条记录"
                }
                logger.info(f"✅ 批量历史数据同步完成: {hist_result.get('success_count', 0)}/{len(request.symbols)}")
                
            except Exception as e:
                logger.error(f"❌ 批量历史数据同步失败: {e}")
                result["historical_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e)
                }
        
        # 同步财务数据
        if request.sync_financial:
            try:
                financial_service = await get_financial_sync_service()
                
                # 批量同步财务数据
                fin_results = await financial_service.sync_financial_data(
                    symbols=request.symbols,
                    data_sources=[request.data_source],
                    batch_size=10
                )
                
                source_stats = fin_results.get(request.data_source)
                if source_stats:
                    result["financial_sync"] = {
                        "success_count": source_stats.success_count,
                        "error_count": source_stats.error_count,
                        "total_symbols": source_stats.total_symbols,
                        "message": f"成功同步 {source_stats.success_count}/{source_stats.total_symbols} 只股票的财务数据"
                    }
                else:
                    result["financial_sync"] = {
                        "success_count": 0,
                        "error_count": len(request.symbols),
                        "message": "财务数据同步失败"
                    }
                
                logger.info(f"✅ 批量财务数据同步完成: {result['financial_sync']['success_count']}/{len(request.symbols)}")
                
            except Exception as e:
                logger.error(f"❌ 批量财务数据同步失败: {e}")
                result["financial_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e)
                }
        
        # 判断整体是否成功
        hist_success = result["historical_sync"].get("success_count", 0) if request.sync_historical else 0
        fin_success = result["financial_sync"].get("success_count", 0) if request.sync_financial else 0
        total_success = max(hist_success, fin_success)

        # 添加统计信息到结果中
        result["total_success"] = total_success
        result["total_symbols"] = len(request.symbols)

        return ok(
            data=result,
            message=f"批量同步完成: {total_success}/{len(request.symbols)} 只股票成功"
        )
        
    except Exception as e:
        logger.error(f"❌ 批量同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量同步失败: {str(e)}")


@router.get("/status/{symbol}")
async def get_sync_status(
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票的同步状态
    
    返回最后同步时间、数据条数等信息
    """
    try:
        from app.core.database import get_mongo_db
        
        db = get_mongo_db()
        
        # 查询历史数据最后同步时间
        hist_doc = await db.historical_data.find_one(
            {"symbol": symbol},
            sort=[("date", -1)]
        )
        
        # 查询财务数据最后同步时间
        fin_doc = await db.stock_financial_data.find_one(
            {"symbol": symbol},
            sort=[("updated_at", -1)]
        )
        
        # 统计历史数据条数
        hist_count = await db.historical_data.count_documents({"symbol": symbol})
        
        # 统计财务数据条数
        fin_count = await db.stock_financial_data.count_documents({"symbol": symbol})
        
        return ok(data={
            "symbol": symbol,
            "historical_data": {
                "last_sync": hist_doc.get("updated_at") if hist_doc else None,
                "last_date": hist_doc.get("date") if hist_doc else None,
                "total_records": hist_count
            },
            "financial_data": {
                "last_sync": fin_doc.get("updated_at") if fin_doc else None,
                "last_report_period": fin_doc.get("report_period") if fin_doc else None,
                "total_records": fin_count
            }
        })
        
    except Exception as e:
        logger.error(f"❌ 获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取同步状态失败: {str(e)}")

