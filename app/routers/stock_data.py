"""
股票数据API路由 - 基于扩展数据模型
提供标准化的股票数据访问接口
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.core.permissions import require_pro
from app.services.stock_data_service import get_stock_data_service
from app.models import (
    StockBasicInfoResponse,
    MarketQuotesResponse,
    StockListResponse,
    StockBasicInfoExtended,
    MarketQuotesExtended,
    MarketType
)
from app.core.response import ok

router = APIRouter(prefix="/api/stock-data", tags=["股票数据"])


# ==================== 批量导入请求模型 ====================

class StockBasicInfoBatchRequest(BaseModel):
    """批量保存股票基本信息请求"""
    stocks: List[Dict[str, Any]] = Field(..., description="股票基本信息列表")
    data_source: str = Field("custom", description="数据来源标识")
    overwrite: bool = Field(False, description="是否覆盖已存在的数据")


class MarketQuotesBatchRequest(BaseModel):
    """批量保存实时行情请求"""
    quotes: List[Dict[str, Any]] = Field(..., description="行情数据列表")
    data_source: str = Field("custom", description="数据来源标识")
    overwrite: bool = Field(True, description="是否覆盖已存在的数据（行情默认覆盖）")


# ==================== 查询接口 ====================

@router.get("/basic-info/{symbol}", response_model=StockBasicInfoResponse)
async def get_stock_basic_info(
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票基础信息

    Args:
        symbol: 股票代码 (支持6位A股代码)

    Returns:
        StockBasicInfoResponse: 包含扩展字段的股票基础信息
    """
    try:
        service = get_stock_data_service()
        stock_info = await service.get_stock_basic_info(symbol)

        if not stock_info:
            return StockBasicInfoResponse(
                success=False,
                message=f"未找到股票代码 {symbol} 的基础信息"
            )

        return StockBasicInfoResponse(
            success=True,
            data=stock_info,
            message="获取成功"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取股票基础信息失败: {str(e)}"
        )


@router.get("/quotes/{symbol}", response_model=MarketQuotesResponse)
async def get_market_quotes(
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取实时行情数据

    Args:
        symbol: 股票代码 (支持6位A股代码)

    Returns:
        MarketQuotesResponse: 包含扩展字段的实时行情数据
    """
    try:
        service = get_stock_data_service()
        quotes = await service.get_market_quotes(symbol)

        if not quotes:
            return MarketQuotesResponse(
                success=False,
                message=f"未找到股票代码 {symbol} 的行情数据"
            )

        return MarketQuotesResponse(
            success=True,
            data=quotes,
            message="获取成功"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取实时行情失败: {str(e)}"
        )


@router.get("/list", response_model=StockListResponse)
async def get_stock_list(
    market: Optional[str] = Query(None, description="市场筛选"),
    industry: Optional[str] = Query(None, description="行业筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票列表
    
    Args:
        market: 市场筛选 (可选)
        industry: 行业筛选 (可选)
        page: 页码 (从1开始)
        page_size: 每页大小 (1-100)
        
    Returns:
        StockListResponse: 股票列表数据
    """
    try:
        service = get_stock_data_service()
        stock_list = await service.get_stock_list(
            market=market,
            industry=industry,
            page=page,
            page_size=page_size
        )
        
        # 计算总数 (简化实现，实际应该单独查询)
        total = len(stock_list)
        
        return StockListResponse(
            success=True,
            data=stock_list,
            total=total,
            page=page,
            page_size=page_size,
            message="获取成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取股票列表失败: {str(e)}"
        )


@router.get("/combined/{symbol}")
async def get_combined_stock_data(
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票综合数据 (基础信息 + 实时行情)

    Args:
        symbol: 股票代码

    Returns:
        dict: 包含基础信息和实时行情的综合数据
    """
    try:
        service = get_stock_data_service()

        # 并行获取基础信息和行情数据
        import asyncio
        basic_info_task = service.get_stock_basic_info(symbol)
        quotes_task = service.get_market_quotes(symbol)

        basic_info, quotes = await asyncio.gather(
            basic_info_task,
            quotes_task,
            return_exceptions=True
        )

        # 处理异常
        if isinstance(basic_info, Exception):
            basic_info = None
        if isinstance(quotes, Exception):
            quotes = None

        if not basic_info and not quotes:
            return {
                "success": False,
                "message": f"未找到股票代码 {symbol} 的任何数据"
            }

        return {
            "success": True,
            "data": {
                "basic_info": basic_info.dict() if basic_info else None,
                "quotes": quotes.dict() if quotes else None,
                "symbol": symbol,
                "timestamp": quotes.updated_at if quotes else None
            },
            "message": "获取成功"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取股票综合数据失败: {str(e)}"
        )


@router.get("/search")
async def search_stocks(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50, description="返回数量限制"),
    current_user: dict = Depends(get_current_user)
):
    """
    搜索股票
    
    Args:
        keyword: 搜索关键词 (股票代码或名称)
        limit: 返回数量限制
        
    Returns:
        dict: 搜索结果
    """
    try:
        from app.core.database import get_mongo_db
        from app.core.unified_config import UnifiedConfigManager

        db = get_mongo_db()
        collection = db.stock_basic_info

        # 🔥 获取数据源优先级配置
        config = UnifiedConfigManager()
        data_source_configs = await config.get_data_source_configs_async()

        # 提取启用的数据源，按优先级排序
        enabled_sources = [
            ds.type.lower() for ds in data_source_configs
            if ds.enabled and ds.type.lower() in ['tushare', 'akshare', 'baostock']
        ]

        if not enabled_sources:
            enabled_sources = ['tushare', 'akshare', 'baostock']

        preferred_source = enabled_sources[0] if enabled_sources else 'tushare'

        # 构建搜索条件
        search_conditions = []

        # 如果是6位数字，按代码精确匹配
        if keyword.isdigit() and len(keyword) == 6:
            search_conditions.append({"symbol": keyword})
        else:
            # 按名称模糊匹配
            search_conditions.append({"name": {"$regex": keyword, "$options": "i"}})
            # 如果包含数字，也尝试代码匹配
            if any(c.isdigit() for c in keyword):
                search_conditions.append({"symbol": {"$regex": keyword}})

        # 🔥 添加数据源筛选：只查询优先级最高的数据源
        query = {
            "$and": [
                {"$or": search_conditions},
                {"source": preferred_source}
            ]
        }

        # 执行搜索
        cursor = collection.find(query, {"_id": 0}).limit(limit)

        results = await cursor.to_list(length=limit)

        # 数据标准化
        service = get_stock_data_service()
        standardized_results = []
        for doc in results:
            standardized_doc = service._standardize_basic_info(doc)
            standardized_results.append(standardized_doc)

        return {
            "success": True,
            "data": standardized_results,
            "total": len(standardized_results),
            "keyword": keyword,
            "source": preferred_source,  # 🔥 返回数据来源
            "message": "搜索完成"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索股票失败: {str(e)}"
        )


@router.get("/markets")
async def get_market_summary(
    current_user: dict = Depends(get_current_user)
):
    """
    获取市场概览

    Returns:
        dict: 各市场的股票数量统计
    """
    try:
        from app.core.database import get_mongo_db

        db = get_mongo_db()
        collection = db.stock_basic_info

        # 统计各市场股票数量
        pipeline = [
            {
                "$group": {
                    "_id": "$market",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            }
        ]

        cursor = collection.aggregate(pipeline)
        market_stats = await cursor.to_list(length=None)

        # 总数统计
        total_count = await collection.count_documents({})

        return {
            "success": True,
            "data": {
                "total_stocks": total_count,
                "market_breakdown": market_stats,
                "supported_markets": ["CN"],  # 当前支持的市场
                "last_updated": None  # 可以从数据中获取最新更新时间
            },
            "message": "获取成功"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取市场概览失败: {str(e)}"
        )


@router.get("/sync-status/quotes")
async def get_quotes_sync_status(
    current_user: dict = Depends(get_current_user)
):
    """
    获取实时行情同步状态

    Returns:
        dict: {
            "success": True,
            "data": {
                "last_sync_time": "2025-10-28 15:06:00",
                "last_sync_time_iso": "2025-10-28T15:06:00+08:00",
                "interval_seconds": 360,
                "interval_minutes": 6,
                "data_source": "tushare",
                "success": True,
                "records_count": 5440,
                "error_message": None
            },
            "message": "获取成功"
        }
    """
    try:
        from app.services.quotes_ingestion_service import QuotesIngestionService

        service = QuotesIngestionService()
        status_data = await service.get_sync_status()

        return {
            "success": True,
            "data": status_data,
            "message": "获取成功"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取同步状态失败: {str(e)}"
        )


# ==================== 批量导入接口 ====================

@router.post("/save-basic-info", response_model=dict, dependencies=[Depends(require_pro)])
async def save_basic_info_batch(
    request: StockBasicInfoBatchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    批量保存股票基本信息（优化版）[PRO]

    允许用户通过 API 批量导入股票基本信息数据

    **权限要求**: 此功能为高级学员专属，需要 PRO 授权

    性能优化：
    - 使用批量查询减少数据库往返
    - 使用 bulk_write 批量操作
    - 数据验证前置

    Args:
        request: 批量保存请求，包含股票列表和数据源标识

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
        from datetime import datetime
        from pymongo import UpdateOne, InsertOne
        import logging

        logger = logging.getLogger(__name__)
        db = get_mongo_db()
        collection = db.stock_basic_info

        # 数据验证和预处理
        valid_stocks = []
        errors = []
        failed_count = 0

        for idx, stock_data in enumerate(request.stocks):
            try:
                # 验证必需字段
                if "symbol" not in stock_data or "name" not in stock_data:
                    errors.append({
                        "index": idx,
                        "error": "缺少必需字段: symbol 或 name"
                    })
                    failed_count += 1
                    continue

                # 验证 symbol 格式（6位数字）
                symbol = stock_data["symbol"]
                if not (isinstance(symbol, str) and symbol.isdigit() and len(symbol) == 6):
                    errors.append({
                        "index": idx,
                        "symbol": symbol,
                        "error": "symbol 必须是6位数字"
                    })
                    failed_count += 1
                    continue

                # 添加元数据
                stock_data["source"] = request.data_source
                stock_data["updated_at"] = datetime.utcnow()

                valid_stocks.append((idx, stock_data))

            except Exception as e:
                errors.append({
                    "index": idx,
                    "symbol": stock_data.get("symbol", "unknown"),
                    "error": f"数据验证失败: {str(e)}"
                })
                failed_count += 1

        if not valid_stocks:
            return ok(
                data={
                    "saved": 0,
                    "updated": 0,
                    "skipped": 0,
                    "failed": failed_count,
                    "total": len(request.stocks),
                    "errors": errors[:10]
                },
                message="所有数据验证失败"
            )

        # 批量查询已存在的数据
        symbols = [stock["symbol"] for _, stock in valid_stocks]
        existing_docs = await collection.find({
            "symbol": {"$in": symbols},
            "source": request.data_source
        }).to_list(length=None)

        existing_symbols = {doc["symbol"]: doc for doc in existing_docs}

        # 准备批量操作
        bulk_operations = []
        saved_count = 0
        updated_count = 0
        skipped_count = 0

        for idx, stock_data in valid_stocks:
            symbol = stock_data["symbol"]

            if symbol in existing_symbols:
                if request.overwrite:
                    # 批量更新
                    stock_data["created_at"] = existing_symbols[symbol].get("created_at", datetime.utcnow())
                    bulk_operations.append(
                        UpdateOne(
                            {"symbol": symbol, "source": request.data_source},
                            {"$set": stock_data}
                        )
                    )
                    updated_count += 1
                else:
                    # 跳过已存在的数据
                    skipped_count += 1
            else:
                # 批量插入
                stock_data["created_at"] = datetime.utcnow()
                bulk_operations.append(InsertOne(stock_data))
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

                for idx, stock_data in valid_stocks:
                    try:
                        symbol = stock_data["symbol"]
                        if symbol in existing_symbols and request.overwrite:
                            await collection.update_one(
                                {"symbol": symbol, "source": request.data_source},
                                {"$set": stock_data}
                            )
                            updated_count += 1
                        elif symbol not in existing_symbols:
                            await collection.insert_one(stock_data)
                            saved_count += 1
                    except Exception as e2:
                        errors.append({
                            "index": idx,
                            "symbol": stock_data.get("symbol", "unknown"),
                            "error": str(e2)
                        })
                        failed_count += 1

        return ok(
            data={
                "saved": saved_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "total": len(request.stocks),
                "errors": errors[:10]  # 只返回前10个错误
            },
            message=f"批量保存完成: 成功{saved_count}, 更新{updated_count}, 跳过{skipped_count}, 失败{failed_count}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量保存股票基本信息失败: {str(e)}"
        )


@router.post("/save-quotes", response_model=dict, dependencies=[Depends(require_pro)])
async def save_quotes_batch(
    request: MarketQuotesBatchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    批量保存实时行情数据（优化版）[PRO]

    允许用户通过 API 批量导入实时行情数据

    **权限要求**: 此功能为高级学员专属，需要 PRO 授权

    性能优化：
    - 使用批量查询减少数据库往返
    - 使用 bulk_write 批量操作
    - 数据验证前置

    Args:
        request: 批量保存请求，包含行情列表和数据源标识

    Returns:
        dict: {
            "saved": 成功保存数量,
            "updated": 更新数量,
            "failed": 失败数量,
            "errors": 错误列表
        }
    """
    try:
        from app.core.database import get_mongo_db
        from datetime import datetime
        from pymongo import UpdateOne, InsertOne
        import logging

        logger = logging.getLogger(__name__)
        db = get_mongo_db()
        collection = db.market_quotes

        # 数据验证和预处理
        valid_quotes = []
        errors = []
        failed_count = 0

        for idx, quote_data in enumerate(request.quotes):
            try:
                # 验证必需字段
                if "symbol" not in quote_data:
                    errors.append({
                        "index": idx,
                        "error": "缺少必需字段: symbol"
                    })
                    failed_count += 1
                    continue

                # 验证 symbol 格式（6位数字）
                symbol = quote_data["symbol"]
                if not (isinstance(symbol, str) and symbol.isdigit() and len(symbol) == 6):
                    errors.append({
                        "index": idx,
                        "symbol": symbol,
                        "error": "symbol 必须是6位数字"
                    })
                    failed_count += 1
                    continue

                # 添加元数据
                quote_data["data_source"] = request.data_source
                quote_data["updated_at"] = datetime.utcnow()

                valid_quotes.append((idx, quote_data))

            except Exception as e:
                errors.append({
                    "index": idx,
                    "symbol": quote_data.get("symbol", "unknown"),
                    "error": f"数据验证失败: {str(e)}"
                })
                failed_count += 1

        if not valid_quotes:
            return ok(
                data={
                    "saved": 0,
                    "updated": 0,
                    "failed": failed_count,
                    "total": len(request.quotes),
                    "errors": errors[:10]
                },
                message="所有数据验证失败"
            )

        # 批量查询已存在的数据
        symbols = [quote["symbol"] for _, quote in valid_quotes]
        existing_docs = await collection.find({
            "symbol": {"$in": symbols}
        }).to_list(length=None)

        existing_symbols = {doc["symbol"] for doc in existing_docs}

        # 准备批量操作
        bulk_operations = []
        saved_count = 0
        updated_count = 0

        for idx, quote_data in valid_quotes:
            symbol = quote_data["symbol"]

            if symbol in existing_symbols:
                # 批量更新
                bulk_operations.append(
                    UpdateOne(
                        {"symbol": symbol},
                        {"$set": quote_data}
                    )
                )
                updated_count += 1
            else:
                # 批量插入
                quote_data["created_at"] = datetime.utcnow()
                bulk_operations.append(InsertOne(quote_data))
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

                for idx, quote_data in valid_quotes:
                    try:
                        symbol = quote_data["symbol"]
                        result = await collection.update_one(
                            {"symbol": symbol},
                            {"$set": quote_data},
                            upsert=True
                        )
                        if result.upserted_id:
                            saved_count += 1
                        else:
                            updated_count += 1
                    except Exception as e2:
                        errors.append({
                            "index": idx,
                            "symbol": quote_data.get("symbol", "unknown"),
                            "error": str(e2)
                        })
                        failed_count += 1

        return ok(
            data={
                "saved": saved_count,
                "updated": updated_count,
                "failed": failed_count,
                "total": len(request.quotes),
                "errors": errors[:10]  # 只返回前10个错误
            },
            message=f"批量保存完成: 新增{saved_count}, 更新{updated_count}, 失败{failed_count}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量保存实时行情失败: {str(e)}"
        )
