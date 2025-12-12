"""
多市场股票API路由
支持A股、港股、美股的统一查询接口

功能：
1. 跨市场股票信息查询
2. 多数据源优先级查询
3. 统一的响应格式

路径前缀: /api/markets
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
import logging

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.core.response import ok
from app.services.unified_stock_service import UnifiedStockService

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/markets", tags=["multi-market"])


@router.get("", response_model=dict)
async def get_supported_markets(current_user: dict = Depends(get_current_user)):
    """
    获取支持的市场列表
    
    Returns:
        {
            "success": true,
            "data": {
                "markets": [
                    {
                        "code": "CN",
                        "name": "A股",
                        "name_en": "China A-Shares",
                        "currency": "CNY",
                        "timezone": "Asia/Shanghai"
                    },
                    ...
                ]
            }
        }
    """
    markets = [
        {
            "code": "CN",
            "name": "A股",
            "name_en": "China A-Shares",
            "currency": "CNY",
            "timezone": "Asia/Shanghai",
            "trading_hours": "09:30-15:00"
        },
        {
            "code": "HK",
            "name": "港股",
            "name_en": "Hong Kong Stocks",
            "currency": "HKD",
            "timezone": "Asia/Hong_Kong",
            "trading_hours": "09:30-16:00"
        },
        {
            "code": "US",
            "name": "美股",
            "name_en": "US Stocks",
            "currency": "USD",
            "timezone": "America/New_York",
            "trading_hours": "09:30-16:00 EST"
        }
    ]
    
    return ok(data={"markets": markets})


@router.get("/{market}/stocks/search", response_model=dict)
async def search_stocks(
    market: str,
    q: str = Query(..., description="搜索关键词（代码或名称）"),
    limit: int = Query(20, ge=1, le=100, description="返回结果数量"),
    current_user: dict = Depends(get_current_user)
):
    """
    搜索股票（支持多市场）
    
    Args:
        market: 市场类型 (CN/HK/US)
        q: 搜索关键词
        limit: 返回结果数量
    
    Returns:
        {
            "success": true,
            "data": {
                "stocks": [
                    {
                        "code": "00700",
                        "name": "腾讯控股",
                        "name_en": "Tencent Holdings",
                        "market": "HK",
                        "source": "yfinance",
                        ...
                    }
                ],
                "total": 1
            }
        }
    """
    market = market.upper()
    if market not in ["CN", "HK", "US"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的市场类型: {market}"
        )
    
    db = get_mongo_db()
    service = UnifiedStockService(db)
    
    try:
        results = await service.search_stocks(market, q, limit)
        return ok(data={
            "stocks": results,
            "total": len(results)
        })
    except Exception as e:
        logger.error(f"❌ 搜索股票失败: market={market}, q={q}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )


@router.get("/{market}/stocks/{code}/info", response_model=dict)
async def get_stock_info(
    market: str,
    code: str,
    source: Optional[str] = Query(None, description="指定数据源（可选）"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票基础信息（支持多市场、多数据源）
    
    Args:
        market: 市场类型 (CN/HK/US)
        code: 股票代码
        source: 指定数据源（可选，不指定则按优先级自动选择）
    
    Returns:
        {
            "success": true,
            "data": {
                "code": "00700",
                "name": "腾讯控股",
                "name_en": "Tencent Holdings",
                "market": "HK",
                "source": "yfinance",
                "total_mv": 32000.0,
                "pe": 25.5,
                "pb": 4.2,
                "lot_size": 100,
                "currency": "HKD",
                ...
            }
        }
    """
    market = market.upper()
    if market not in ["CN", "HK", "US"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的市场类型: {market}"
        )
    
    db = get_mongo_db()
    service = UnifiedStockService(db)
    
    try:
        stock_info = await service.get_stock_info(market, code, source)
        
        if not stock_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到股票: {market}:{code}"
            )
        
        return ok(data=stock_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取股票信息失败: market={market}, code={code}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取股票信息失败: {str(e)}"
        )


@router.get("/{market}/stocks/{code}/quote", response_model=dict)
async def get_stock_quote(
    market: str,
    code: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票实时行情（支持多市场）
    
    Args:
        market: 市场类型 (CN/HK/US)
        code: 股票代码
    
    Returns:
        {
            "success": true,
            "data": {
                "code": "00700",
                "close": 320.50,
                "pct_chg": 2.15,
                "open": 315.00,
                "high": 325.00,
                "low": 312.00,
                "volume": 48500000,
                "amount": 15800000000,
                "trade_date": "2024-01-15",
                "currency": "HKD",
                ...
            }
        }
    """
    market = market.upper()
    if market not in ["CN", "HK", "US"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的市场类型: {market}"
        )
    
    db = get_mongo_db()
    service = UnifiedStockService(db)
    
    try:
        quote = await service.get_stock_quote(market, code)
        
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到股票行情: {market}:{code}"
            )
        
        return ok(data=quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取股票行情失败: market={market}, code={code}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取股票行情失败: {str(e)}"
        )


@router.get("/{market}/stocks/{code}/daily", response_model=dict)
async def get_stock_daily_quotes(
    market: str,
    code: str,
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票历史K线数据（支持多市场）
    
    Args:
        market: 市场类型 (CN/HK/US)
        code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回记录数
    
    Returns:
        {
            "success": true,
            "data": {
                "code": "00700",
                "market": "HK",
                "quotes": [
                    {
                        "trade_date": "2024-01-15",
                        "open": 315.00,
                        "high": 325.00,
                        "low": 312.00,
                        "close": 320.50,
                        "volume": 48500000,
                        "amount": 15800000000
                    },
                    ...
                ],
                "total": 100
            }
        }
    """
    market = market.upper()
    if market not in ["CN", "HK", "US"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的市场类型: {market}"
        )
    
    db = get_mongo_db()
    service = UnifiedStockService(db)
    
    try:
        quotes = await service.get_daily_quotes(
            market, code, start_date, end_date, limit
        )
        
        return ok(data={
            "code": code,
            "market": market,
            "quotes": quotes,
            "total": len(quotes)
        })
    except Exception as e:
        logger.error(f"❌ 获取历史K线失败: market={market}, code={code}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取历史K线失败: {str(e)}"
        )

