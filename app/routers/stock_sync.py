"""
股票数据同步API路由
支持单个股票或批量股票的历史数据和财务数据同步
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.core.database import get_mongo_db
from app.worker.tushare_sync_service import get_tushare_sync_service
from app.worker.akshare_sync_service import get_akshare_sync_service
from app.worker.financial_data_sync_service import get_financial_sync_service
from app.worker.etf_sync_service import get_etf_sync_service
from app.services.data_validation_service import get_data_validation_service
import logging
import asyncio
from datetime import datetime, timedelta
from fastapi import Query

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/stock-sync", tags=["股票数据同步"])

STOCK_SYNC_TASKS_COLLECTION = "stock_sync_tasks"
TASK_TERMINAL_STATUSES = {"success", "success_with_errors", "failed"}


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _request_to_dict(request: BaseModel) -> Dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump()
    return request.dict()


def _serialize_task_doc(task_doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not task_doc:
        return None
    serialized = dict(task_doc)
    serialized.pop("_id", None)
    return serialized


def _get_single_task_message(symbol: str, result: Dict[str, Any]) -> str:
    if result.get("overall_success"):
        return f"股票 {symbol} 数据同步成功"
    return f"股票 {symbol} 数据同步部分失败"


def _get_batch_task_status(request: "BatchStockSyncRequest", result: Dict[str, Any]) -> str:
    total_symbols = len(request.symbols)
    if total_symbols <= 0:
        return "failed"

    section_success_flags: List[bool] = []
    section_has_success = False

    if request.sync_historical:
        success_count = (result.get("historical_sync") or {}).get("success_count", 0)
        section_success_flags.append(success_count >= total_symbols)
        section_has_success = section_has_success or success_count > 0

    if request.sync_financial:
        success_count = (result.get("financial_sync") or {}).get("success_count", 0)
        section_success_flags.append(success_count >= total_symbols)
        section_has_success = section_has_success or success_count > 0

    if request.sync_basic:
        success_count = (result.get("basic_sync") or {}).get("success_count", 0)
        section_success_flags.append(success_count >= total_symbols)
        section_has_success = section_has_success or success_count > 0

    if section_success_flags and all(section_success_flags):
        return "success"
    if section_has_success:
        return "success_with_errors"
    return "failed"


def _get_batch_task_message(result: Dict[str, Any]) -> str:
    total_symbols = result.get("total_symbols") or len(result.get("symbols") or [])
    total_success = result.get("total_success", 0)
    if total_success >= total_symbols and total_symbols > 0:
        return f"批量同步完成: {total_success}/{total_symbols} 只股票成功"
    if total_success > 0:
        return f"批量同步部分完成: {total_success}/{total_symbols} 只股票成功"
    return "批量同步失败"


async def _create_stock_sync_task(
    task_type: str,
    payload: Dict[str, Any],
    current_user: dict,
) -> Dict[str, Any]:
    db = get_mongo_db()
    task_id = uuid4().hex
    now_iso = _utc_now_iso()
    task_doc = {
        "task_id": task_id,
        "task_type": task_type,
        "status": "pending",
        "message": "同步任务已提交",
        "payload": payload,
        "symbol": payload.get("symbol"),
        "symbols": payload.get("symbols"),
        "created_at": now_iso,
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
        "submitted_by": str(
            current_user.get("username")
            or current_user.get("user_id")
            or current_user.get("id")
            or "unknown"
        ),
    }
    await db[STOCK_SYNC_TASKS_COLLECTION].insert_one(task_doc)
    return _serialize_task_doc(task_doc) or {}


async def _update_stock_sync_task(task_id: str, updates: Dict[str, Any]) -> None:
    db = get_mongo_db()
    await db[STOCK_SYNC_TASKS_COLLECTION].update_one(
        {"task_id": task_id},
        {"$set": updates},
        upsert=False,
    )


async def _get_stock_sync_task(task_id: str) -> Optional[Dict[str, Any]]:
    db = get_mongo_db()
    task_doc = await db[STOCK_SYNC_TASKS_COLLECTION].find_one({"task_id": task_id})
    return _serialize_task_doc(task_doc)


async def _execute_stock_sync_task(task_id: str, task_type: str, payload: Dict[str, Any]) -> None:
    await _update_stock_sync_task(
        task_id,
        {
            "status": "running",
            "message": "同步任务执行中",
            "started_at": _utc_now_iso(),
            "error": None,
        },
    )

    try:
        if task_type == "single":
            request = SingleStockSyncRequest(**payload)
            result = await run_single_stock_sync(request)
            status = "success" if result.get("overall_success") else "success_with_errors"
            message = _get_single_task_message(request.symbol, result)
        elif task_type == "batch":
            request = BatchStockSyncRequest(**payload)
            result = await run_batch_stock_sync(request)
            status = _get_batch_task_status(request, result)
            message = _get_batch_task_message(result)
        else:
            raise RuntimeError(f"未知同步任务类型: {task_type}")

        await _update_stock_sync_task(
            task_id,
            {
                "status": status,
                "message": message,
                "result": result,
                "finished_at": _utc_now_iso(),
                "error": None,
            },
        )
    except Exception as e:
        logger.error(f"❌ 同步任务 {task_id} 执行失败: {e}", exc_info=True)
        await _update_stock_sync_task(
            task_id,
            {
                "status": "failed",
                "message": f"同步失败: {str(e)}",
                "finished_at": _utc_now_iso(),
                "error": str(e),
            },
        )


ETF_CODE_PREFIXES = ("50", "51", "52", "56", "58", "15", "16", "18")


def _is_cn_etf_symbol(symbol: str) -> bool:
    text = str(symbol or "").strip()
    return len(text) == 6 and text.isdigit() and text.startswith(ETF_CODE_PREFIXES)


async def _sync_latest_to_market_quotes(symbol: str) -> None:
    """
    将 stock_daily_quotes 中的最新数据同步到 market_quotes

    智能判断逻辑：
    - 如果 market_quotes 中已有更新的数据（trade_date 更新），则不覆盖
    - 如果 market_quotes 中没有数据或数据较旧，则更新

    Args:
        symbol: 股票代码（6位）
    """
    db = get_mongo_db()
    symbol6 = str(symbol).zfill(6)

    # 从 stock_daily_quotes 获取最新数据
    latest_doc = await db.stock_daily_quotes.find_one(
        {"symbol": symbol6},
        sort=[("trade_date", -1)]
    )

    if not latest_doc:
        logger.warning(f"⚠️ {symbol6}: stock_daily_quotes 中没有数据")
        return

    historical_trade_date = latest_doc.get("trade_date")

    # 🔥 检查 market_quotes 中是否已有更新的数据
    existing_quote = await db.market_quotes.find_one({"code": symbol6})

    if existing_quote:
        existing_trade_date = existing_quote.get("trade_date")

        # 如果 market_quotes 中的数据日期更新或相同，则不覆盖
        if existing_trade_date and historical_trade_date:
            # 比较日期字符串（格式：YYYY-MM-DD 或 YYYYMMDD）
            existing_date_str = str(existing_trade_date).replace("-", "")
            historical_date_str = str(historical_trade_date).replace("-", "")

            if existing_date_str >= historical_date_str:
                # 🔥 日期相同或更新时，都不覆盖（避免用历史数据覆盖实时数据）
                logger.info(
                    f"⏭️ {symbol6}: market_quotes 中的数据日期 >= 历史数据日期 "
                    f"(market_quotes: {existing_trade_date}, historical: {historical_trade_date})，跳过覆盖"
                )
                return

    # 提取需要的字段
    quote_data = {
        "code": symbol6,
        "symbol": symbol6,
        "close": latest_doc.get("close"),
        "price": latest_doc.get("close"),
        "current_price": latest_doc.get("close"),
        "open": latest_doc.get("open"),
        "high": latest_doc.get("high"),
        "low": latest_doc.get("low"),
        "volume": latest_doc.get("volume"),  # 已经转换过单位
        "amount": latest_doc.get("amount"),  # 已经转换过单位
        "pct_chg": latest_doc.get("pct_chg"),
        "pre_close": latest_doc.get("pre_close"),
        "trade_date": latest_doc.get("trade_date"),
        "updated_at": datetime.utcnow()
    }

    # 🔥 日志：记录同步的成交量
    logger.info(
        f"📊 [同步到market_quotes] {symbol6} - "
        f"volume={quote_data['volume']}, amount={quote_data['amount']}, trade_date={quote_data['trade_date']}"
    )

    # 更新 market_quotes
    await db.market_quotes.update_one(
        {"code": symbol6},
        {"$set": quote_data},
        upsert=True
    )


class SingleStockSyncRequest(BaseModel):
    """单股票同步请求"""
    symbol: str = Field(..., description="股票代码（6位）")
    sync_realtime: bool = Field(False, description="是否同步实时行情")
    sync_historical: bool = Field(True, description="是否同步历史数据")
    sync_financial: bool = Field(True, description="是否同步财务数据")
    sync_basic: bool = Field(False, description="是否同步基础数据")
    data_source: str = Field("tushare", description="数据源: tushare/akshare/qmt")
    days: int = Field(30, description="历史数据天数", ge=1, le=3650)


class BatchStockSyncRequest(BaseModel):
    """批量股票同步请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    sync_historical: bool = Field(True, description="是否同步历史数据")
    sync_financial: bool = Field(True, description="是否同步财务数据")
    sync_basic: bool = Field(False, description="是否同步基础数据")
    data_source: str = Field("tushare", description="数据源: tushare/akshare/qmt")
    days: int = Field(30, description="历史数据天数", ge=1, le=3650)


async def run_single_stock_sync(request: SingleStockSyncRequest) -> dict:
    """执行单股票数据同步，返回原始同步结果字典。"""
    logger.info(f"📊 开始同步单个股票: {request.symbol} (数据源: {request.data_source})")
    is_etf = _is_cn_etf_symbol(request.symbol)
    if is_etf:
        logger.info(f"📈 {request.symbol} 识别为 ETF，历史/基础同步将走 ETF 专用同步服务")

    result = {
        "symbol": request.symbol,
        "realtime_sync": None,
        "historical_sync": None,
        "financial_sync": None,
        "basic_sync": None
    }

    # 同步实时行情
    if request.sync_realtime:
        try:
            # 🔥 单个股票实时行情同步：优先使用 AKShare（避免 Tushare 接口限制）
            actual_data_source = request.data_source
            if request.data_source == "tushare":
                logger.info(f"💡 单个股票实时行情同步，自动切换到 AKShare 数据源（避免 Tushare 接口限制）")
                actual_data_source = "akshare"

            if actual_data_source == "tushare":
                service = await get_tushare_sync_service()
            elif actual_data_source == "akshare":
                service = await get_akshare_sync_service()
            elif actual_data_source == "qmt":
                from app.worker.qmt_sync_service import get_qmt_sync_service

                service = await get_qmt_sync_service()
            else:
                raise ValueError(f"不支持的数据源: {actual_data_source}")

            # 同步实时行情（只同步指定的股票）
            if actual_data_source == "akshare":
                realtime_result = await service.sync_realtime_quotes(
                    symbols=[request.symbol],
                    force=True,
                    manual_mode=True  # 手动接口不应继承调度任务取消状态
                )
            elif actual_data_source == "qmt":
                realtime_result = await service.sync_realtime_quotes(
                    symbols=[str(request.symbol).zfill(6)],
                    force=True
                )
            else:
                realtime_result = await service.sync_realtime_quotes(
                    symbols=[request.symbol],
                    force=True  # 强制执行，跳过交易时间检查
                )

            success = realtime_result.get("success_count", 0) > 0

            message = f"实时行情同步{'成功' if success else '失败'}"
            if request.data_source == "tushare" and actual_data_source == "akshare":
                message += "（已自动切换到 AKShare 数据源）"

            result["realtime_sync"] = {
                "success": success,
                "message": message,
                "data_source_used": actual_data_source
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
            if is_etf:
                etf_service = await get_etf_sync_service()
                hist_result = await etf_service._sync_daily_by_source(
                    request.data_source,
                    [request.symbol],
                    request.days,
                    True
                )

                result["historical_sync"] = {
                    "success": hist_result.get("success_count", 0) > 0,
                    "records": hist_result.get("records_inserted", 0),
                    "message": f"同步了 {hist_result.get('records_inserted', 0)} 条 ETF 历史记录"
                }
                logger.info(f"✅ {request.symbol} ETF 历史数据同步完成: {hist_result.get('records_inserted', 0)} 条记录")
            else:
                if request.data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif request.data_source == "akshare":
                    service = await get_akshare_sync_service()
                elif request.data_source == "qmt":
                    from app.worker.qmt_sync_service import get_qmt_sync_service

                    service = await get_qmt_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {request.data_source}")

                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=request.days)).strftime('%Y-%m-%d')

                if request.data_source == "akshare":
                    hist_result = await service.sync_historical_data(
                        symbols=[request.symbol],
                        start_date=start_date,
                        end_date=end_date,
                        incremental=False,
                        manual_mode=True,
                    )
                elif request.data_source == "qmt":
                    hist_result = await service.sync_historical_data(
                        symbols=[str(request.symbol).zfill(6)],
                        days=request.days,
                        period="daily",
                        incremental=False,
                    )
                else:
                    hist_result = await service.sync_historical_data(
                        symbols=[request.symbol],
                        start_date=start_date,
                        end_date=end_date,
                        incremental=False
                    )

                result["historical_sync"] = {
                    "success": hist_result.get("success_count", 0) > 0,
                    "records": hist_result.get("total_records", hist_result.get("historical_records", 0)),
                    "message": (
                        f"同步了 {hist_result.get('total_records', hist_result.get('historical_records', 0))} 条历史记录"
                    )
                }
                logger.info(
                    f"✅ {request.symbol} 历史数据同步完成: "
                    f"{hist_result.get('total_records', hist_result.get('historical_records', 0))} 条记录"
                )

                if hist_result.get("success_count", 0) > 0:
                    try:
                        await _sync_latest_to_market_quotes(request.symbol)
                        logger.info(f"✅ {request.symbol} 最新数据已同步到 market_quotes")
                    except Exception as e:
                        logger.warning(f"⚠️ {request.symbol} 同步到 market_quotes 失败: {e}")

        except Exception as e:
            logger.error(f"❌ {request.symbol} 历史数据同步失败: {e}")
            result["historical_sync"] = {
                "success": False,
                "error": str(e)
            }

    # 同步财务数据
    if request.sync_financial:
        try:
            if request.data_source == "qmt":
                from app.worker.qmt_sync_service import get_qmt_sync_service

                qmt_service = await get_qmt_sync_service()
                fin_result = await qmt_service.sync_financial_data(symbols=[str(request.symbol).zfill(6)])
                success = fin_result.get("success_count", 0) > 0
            else:
                financial_service = await get_financial_sync_service()

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

    # 同步基础数据
    if request.sync_basic:
        try:
            # 🔥 同步单个股票的基础数据
            # 参考 basics_sync_service 的实现逻辑
            if is_etf:
                etf_service = await get_etf_sync_service()
                basic_result = await etf_service._sync_basic_by_source(
                    request.data_source,
                    True,
                    [request.symbol],
                )
                success = basic_result.get("success_count", 0) > 0
                result["basic_sync"] = {
                    "success": success,
                    "message": "ETF 基础数据同步成功" if success else "ETF 基础数据同步失败",
                    "error": None if success else "; ".join(item.get("error", "未知错误") for item in basic_result.get("errors", [])[:3])
                }
                logger.info(f"✅ {request.symbol} ETF 基础数据同步完成: {success}")
            elif request.data_source == "tushare":
                from app.services.basics_sync import (
                    fetch_stock_basic_df,
                    find_latest_trade_date,
                    fetch_daily_basic_mv_map,
                    fetch_latest_roe_map,
                )

                db = get_mongo_db()
                symbol6 = str(request.symbol).zfill(6)

                stock_df = await asyncio.to_thread(fetch_stock_basic_df)
                if stock_df is None or stock_df.empty:
                    result["basic_sync"] = {
                        "success": False,
                        "error": "Tushare 返回空数据"
                    }
                else:
                    stock_row = None
                    for _, row in stock_df.iterrows():
                        ts_code = row.get("ts_code", "")
                        if isinstance(ts_code, str) and ts_code.startswith(symbol6):
                            stock_row = row
                            break

                    if stock_row is None:
                        result["basic_sync"] = {
                            "success": False,
                            "error": f"未找到股票 {symbol6} 的基础信息"
                        }
                    else:
                        latest_trade_date = await asyncio.to_thread(find_latest_trade_date)
                        daily_data_map = await asyncio.to_thread(fetch_daily_basic_mv_map, latest_trade_date)
                        roe_map = await asyncio.to_thread(fetch_latest_roe_map)

                        now_iso = datetime.utcnow().isoformat()

                        name = stock_row.get("name") or ""
                        area = stock_row.get("area") or ""
                        industry = stock_row.get("industry") or ""
                        market = stock_row.get("market") or ""
                        list_date = stock_row.get("list_date") or ""
                        ts_code = stock_row.get("ts_code") or ""

                        if isinstance(ts_code, str) and "." in ts_code:
                            code = ts_code.split(".")[0]
                        else:
                            code = symbol6

                        if isinstance(ts_code, str):
                            if ts_code.endswith(".SH"):
                                sse = "上海证券交易所"
                            elif ts_code.endswith(".SZ"):
                                sse = "深圳证券交易所"
                            elif ts_code.endswith(".BJ"):
                                sse = "北京证券交易所"
                            else:
                                sse = "未知"
                        else:
                            sse = "未知"

                        full_symbol = ts_code

                        daily_metrics = {}
                        if isinstance(ts_code, str) and ts_code in daily_data_map:
                            daily_metrics = daily_data_map[ts_code]

                        total_mv_yi = None
                        circ_mv_yi = None
                        if "total_mv" in daily_metrics:
                            try:
                                total_mv_yi = float(daily_metrics["total_mv"]) / 10000.0
                            except Exception:
                                pass
                        if "circ_mv" in daily_metrics:
                            try:
                                circ_mv_yi = float(daily_metrics["circ_mv"]) / 10000.0
                            except Exception:
                                pass

                        doc = {
                            "code": code,
                            "symbol": code,
                            "name": name,
                            "area": area,
                            "industry": industry,
                            "market": market,
                            "list_date": list_date,
                            "sse": sse,
                            "sec": "stock_cn",
                            "source": "tushare",
                            "updated_at": now_iso,
                            "full_symbol": full_symbol,
                        }

                        if total_mv_yi is not None:
                            doc["total_mv"] = total_mv_yi
                        if circ_mv_yi is not None:
                            doc["circ_mv"] = circ_mv_yi

                        for field in ["pe", "pb", "ps", "pe_ttm", "pb_mrq", "ps_ttm"]:
                            if field in daily_metrics:
                                doc[field] = daily_metrics[field]

                        if isinstance(ts_code, str) and ts_code in roe_map:
                            roe_val = roe_map[ts_code].get("roe")
                            if roe_val is not None:
                                doc["roe"] = roe_val

                        for field in ["turnover_rate", "volume_ratio"]:
                            if field in daily_metrics:
                                doc[field] = daily_metrics[field]

                        for field in ["total_share", "float_share"]:
                            if field in daily_metrics:
                                doc[field] = daily_metrics[field]

                        await db.stock_basic_info.update_one(
                            {"code": code, "source": "tushare"},
                            {"$set": doc},
                            upsert=True
                        )

                        result["basic_sync"] = {
                            "success": True,
                            "message": "基础数据同步成功"
                        }
                        logger.info(f"✅ {request.symbol} 基础数据同步完成")

            elif request.data_source == "qmt":
                from app.worker.qmt_sync_service import get_qmt_sync_service

                qmt_service = await get_qmt_sync_service()
                sync_result = await qmt_service.sync_stock_basic_info(
                    force_update=True,
                    symbols=[request.symbol],
                )
                success_count = sync_result.get("success_count", 0)
                result["basic_sync"] = {
                    "success": success_count > 0,
                    "message": f"基础数据同步{'成功' if success_count > 0 else '失败'}" + (
                        f"（QMT 需交易终端运行）" if success_count == 0 else ""
                    ),
                }
                logger.info(f"✅ {request.symbol} 基础数据同步完成 (QMT): {success_count}")

            elif request.data_source == "akshare":
                db = get_mongo_db()
                symbol6 = str(request.symbol).zfill(6)

                existing_stock = await db.stock_basic_info.find_one(
                    {"code": symbol6},
                    {"name": 1}
                )
                fallback_name = existing_stock.get("name") if existing_stock and existing_stock.get("name") else f"股票{symbol6}"

                service = await get_akshare_sync_service()
                from app.services.official_industry_service import (
                    INDUSTRY_SOURCE_SYSTEM,
                    fetch_industry_mapping,
                )

                industry_mapping = await fetch_industry_mapping(refresh_if_empty=True)
                mapped_industry = industry_mapping.get(symbol6, "") if industry_mapping else ""

                # 单股同步允许组合多个接口，避免完全依赖东财详情接口。
                basic_info = await service.provider.get_stock_basic_info_for_single_sync(symbol6)
                if not basic_info:
                    basic_info = await service.provider.get_stock_basic_info(symbol6)

                if basic_info:
                    if hasattr(basic_info, 'model_dump'):
                        basic_data = basic_info.model_dump()
                    elif hasattr(basic_info, 'dict'):
                        basic_data = basic_info.dict()
                    else:
                        basic_data = basic_info

                    if basic_data.get("name") == f"股票{symbol6}" and fallback_name != f"股票{symbol6}":
                        basic_data["name"] = fallback_name
                        logger.debug(f"📝 使用数据库中的股票名称: {fallback_name}")

                    if mapped_industry:
                        raw_industry = str(basic_data.get("industry") or "").strip()
                        basic_data["industry"] = mapped_industry
                        basic_data["industry_source"] = INDUSTRY_SOURCE_SYSTEM
                        if raw_industry and raw_industry != mapped_industry:
                            logger.info(
                                f"🔁 {symbol6} AK 原始行业已替换为系统行业映射: {raw_industry} -> {mapped_industry}"
                            )

                    detail_fetch_error = basic_data.pop("detail_fetch_error", None)
                    detail_fetch_symbol = basic_data.pop("detail_fetch_symbol", None)
                    degraded_sync = basic_data.get("sync_status") == "degraded"

                    basic_data["code"] = symbol6
                    basic_data["symbol"] = symbol6
                    basic_data["source"] = "akshare"
                    basic_data["updated_at"] = datetime.utcnow().isoformat()

                    await db.stock_basic_info.update_one(
                        {"code": symbol6, "source": "akshare"},
                        {"$set": basic_data},
                        upsert=True
                    )

                    if degraded_sync:
                        result["basic_sync"] = {
                            "success": False,
                            "degraded": True,
                            "message": "基础数据已降级写入，AKShare 个股详情接口失败",
                            "error": detail_fetch_error or "AKShare 个股详情接口失败",
                            "detail_symbol": detail_fetch_symbol,
                        }
                        logger.warning(
                            f"⚠️ {request.symbol} 基础数据仅完成降级同步 (AKShare): {detail_fetch_error or '个股详情接口失败'}"
                        )
                    else:
                        result["basic_sync"] = {
                            "success": True,
                            "message": "基础数据同步成功"
                        }
                        logger.info(f"✅ {request.symbol} 基础数据同步完成 (AKShare)")
                else:
                    result["basic_sync"] = {
                        "success": False,
                        "error": "未获取到基础数据"
                    }
            else:
                result["basic_sync"] = {
                    "success": False,
                    "error": f"基础数据同步仅支持 Tushare/AKShare/QMT 数据源，当前数据源: {request.data_source}"
                }

        except Exception as e:
            logger.error(f"❌ {request.symbol} 基础数据同步失败: {e}")
            result["basic_sync"] = {
                "success": False,
                "error": str(e)
            }

    overall_success = (
        (not request.sync_realtime or result["realtime_sync"].get("success", False)) and
        (not request.sync_historical or result["historical_sync"].get("success", False)) and
        (not request.sync_financial or result["financial_sync"].get("success", False)) and
        (not request.sync_basic or result["basic_sync"].get("success", False))
    )

    result["overall_success"] = overall_success
    return result


@router.post("/single")
async def sync_single_stock(
    request: SingleStockSyncRequest,
    current_user: dict = Depends(get_current_user)
):
    """提交单股同步任务，立即返回任务状态。"""
    try:
        payload = _request_to_dict(request)
        task_doc = await _create_stock_sync_task("single", payload, current_user)
        asyncio.create_task(_execute_stock_sync_task(task_doc["task_id"], "single", payload))
        return ok(data=task_doc, message="股票同步任务已提交")
    except Exception as e:
        logger.error(f"❌ 提交单股同步任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交同步任务失败: {str(e)}")


async def run_batch_stock_sync(request: BatchStockSyncRequest) -> dict:
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
            "financial_sync": None,
            "basic_sync": None
        }

        if request.sync_historical:
            try:
                if request.data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif request.data_source == "akshare":
                    service = await get_akshare_sync_service()
                elif request.data_source == "qmt":
                    from app.worker.qmt_sync_service import get_qmt_sync_service

                    service = await get_qmt_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {request.data_source}")

                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=request.days)).strftime('%Y-%m-%d')

                if request.data_source == "qmt":
                    hist_result = await service.sync_historical_data(
                        symbols=[str(symbol).zfill(6) for symbol in request.symbols],
                        days=request.days,
                        period="daily",
                        incremental=False,
                    )
                else:
                    hist_result = await service.sync_historical_data(
                        symbols=request.symbols,
                        start_date=start_date,
                        end_date=end_date,
                        incremental=False
                    )

                result["historical_sync"] = {
                    "success_count": hist_result.get("success_count", 0),
                    "error_count": hist_result.get("error_count", 0),
                    "total_records": hist_result.get("total_records", hist_result.get("historical_records", 0)),
                    "message": (
                        f"成功同步 {hist_result.get('success_count', 0)}/{len(request.symbols)} 只股票，"
                        f"共 {hist_result.get('total_records', hist_result.get('historical_records', 0))} 条记录"
                    )
                }
                logger.info(f"✅ 批量历史数据同步完成: {hist_result.get('success_count', 0)}/{len(request.symbols)}")

            except Exception as e:
                logger.error(f"❌ 批量历史数据同步失败: {e}")
                result["historical_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e)
                }

        if request.sync_financial:
            try:
                if request.data_source == "qmt":
                    from app.worker.qmt_sync_service import get_qmt_sync_service

                    qmt_service = await get_qmt_sync_service()
                    fin_results = await qmt_service.sync_financial_data(
                        symbols=[str(symbol).zfill(6) for symbol in request.symbols]
                    )
                    result["financial_sync"] = {
                        "success_count": fin_results.get("success_count", 0),
                        "error_count": fin_results.get("error_count", 0),
                        "total_symbols": fin_results.get("total_symbols", len(request.symbols)),
                        "message": (
                            f"成功同步 {fin_results.get('success_count', 0)}/"
                            f"{fin_results.get('total_symbols', len(request.symbols))} 只股票的财务数据"
                        )
                    }
                else:
                    financial_service = await get_financial_sync_service()

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

        if request.sync_basic:
            try:
                if request.data_source == "tushare":
                    from tradingagents.dataflows.providers.china.tushare import TushareProvider

                    tushare_provider = TushareProvider()
                    if tushare_provider.is_available():
                        success_count = 0
                        error_count = 0

                        for symbol in request.symbols:
                            try:
                                basic_info = await tushare_provider.get_stock_basic_info(symbol)

                                if basic_info:
                                    db = get_mongo_db()
                                    symbol6 = str(symbol).zfill(6)

                                    basic_info["code"] = symbol6
                                    basic_info["source"] = "tushare"
                                    basic_info["updated_at"] = datetime.utcnow()

                                    await db.stock_basic_info.update_one(
                                        {"code": symbol6, "source": "tushare"},
                                        {"$set": basic_info},
                                        upsert=True
                                    )

                                    success_count += 1
                                    logger.info(f"✅ {symbol} 基础数据同步成功")
                                else:
                                    error_count += 1
                                    logger.warning(f"⚠️ {symbol} 未获取到基础数据")
                            except Exception as e:
                                error_count += 1
                                logger.error(f"❌ {symbol} 基础数据同步失败: {e}")

                        result["basic_sync"] = {
                            "success_count": success_count,
                            "error_count": error_count,
                            "total_symbols": len(request.symbols),
                            "message": f"成功同步 {success_count}/{len(request.symbols)} 只股票的基础数据"
                        }
                        logger.info(f"✅ 批量基础数据同步完成: {success_count}/{len(request.symbols)}")
                    else:
                        result["basic_sync"] = {
                            "success_count": 0,
                            "error_count": len(request.symbols),
                            "error": "Tushare 数据源不可用"
                        }
                elif request.data_source == "qmt":
                    from app.worker.qmt_sync_service import get_qmt_sync_service

                    qmt_service = await get_qmt_sync_service()
                    sync_result = await qmt_service.sync_stock_basic_info(
                        force_update=True,
                        symbols=request.symbols,
                    )
                    success_count = sync_result.get("success_count", 0)
                    error_count = sync_result.get("error_count", 0)
                    result["basic_sync"] = {
                        "success_count": success_count,
                        "error_count": error_count,
                        "total_symbols": len(request.symbols),
                        "message": f"成功同步 {success_count}/{len(request.symbols)} 只股票的基础数据（QMT）",
                    }
                    logger.info(f"✅ 批量基础数据同步完成 (QMT): {success_count}/{len(request.symbols)}")
                else:
                    result["basic_sync"] = {
                        "success_count": 0,
                        "error_count": len(request.symbols),
                        "error": f"基础数据同步仅支持 Tushare/QMT 数据源，当前数据源: {request.data_source}"
                    }

            except Exception as e:
                logger.error(f"❌ 批量基础数据同步失败: {e}")
                result["basic_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e)
                }

        hist_success = result["historical_sync"].get("success_count", 0) if request.sync_historical else 0
        fin_success = result["financial_sync"].get("success_count", 0) if request.sync_financial else 0
        basic_success = result["basic_sync"].get("success_count", 0) if request.sync_basic else 0
        total_success = max(hist_success, fin_success, basic_success)

        result["total_success"] = total_success
        result["total_symbols"] = len(request.symbols)

        return result

    except Exception as e:
        logger.error(f"❌ 批量同步失败: {e}")
        raise RuntimeError(f"批量同步失败: {str(e)}") from e


@router.post("/batch")
async def sync_batch_stocks(
    request: BatchStockSyncRequest,
    current_user: dict = Depends(get_current_user)
):
    """提交批量同步任务，立即返回任务状态。"""
    try:
        payload = _request_to_dict(request)
        task_doc = await _create_stock_sync_task("batch", payload, current_user)
        asyncio.create_task(_execute_stock_sync_task(task_doc["task_id"], "batch", payload))
        return ok(data=task_doc, message="批量同步任务已提交")
    except Exception as e:
        logger.error(f"❌ 提交批量同步任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交批量同步任务失败: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_stock_sync_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """查询手动股票同步任务状态与结果。"""
    try:
        task_doc = await _get_stock_sync_task(task_id)
        if not task_doc:
            raise HTTPException(status_code=404, detail="同步任务不存在")
        return ok(data=task_doc)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取同步任务状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取同步任务状态失败: {str(e)}")


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


@router.get("/validate", response_model=dict)
async def validate_stock_data(
    symbol: str = Query(..., description="股票代码（6位）"),
    analysis_date: Optional[str] = Query(None, description="分析日期（YYYY-MM-DD），默认为今天"),
    market_type: str = Query("cn", description="市场类型：cn/hk/us"),
    check_basic_info: bool = Query(True, description="是否检查基础信息"),
    check_historical_data: bool = Query(True, description="是否检查历史数据"),
    check_financial_data: bool = Query(False, description="是否检查财务数据"),
    check_realtime_quotes: bool = Query(False, description="是否检查实时行情"),
    current_user: dict = Depends(get_current_user)
):
    """
    数据校验接口
    校验股票数据的完整性和有效性
    
    Args:
        symbol: 股票代码
        analysis_date: 分析日期（YYYY-MM-DD），默认为今天
        market_type: 市场类型（cn/hk/us）
        check_basic_info: 是否检查基础信息
        check_historical_data: 是否检查历史数据
        check_financial_data: 是否检查财务数据
        check_realtime_quotes: 是否检查实时行情
        
    Returns:
        校验结果，包含 is_valid, message, missing_data, details
    """
    try:
        # 如果没有指定分析日期，使用今天
        if not analysis_date:
            analysis_date = datetime.now().strftime("%Y-%m-%d")
        
        # 获取数据校验服务
        validation_service = get_data_validation_service()
        
        # 执行校验
        result = await validation_service.validate_stock_data(
            symbol=symbol,
            analysis_date=analysis_date,
            market_type=market_type,
            check_basic_info=check_basic_info,
            check_historical_data=check_historical_data,
            check_financial_data=check_financial_data,
            check_realtime_quotes=check_realtime_quotes
        )
        
        return ok(data={
            "is_valid": result.is_valid,
            "message": result.message,
            "missing_data": result.missing_data,
            "details": result.details
        })
        
    except Exception as e:
        logger.error(f"❌ 数据校验失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"数据校验失败: {str(e)}")


@router.post("/industry-from-official", response_model=dict)
async def sync_industry_from_official(current_user: dict = Depends(get_current_user)):
    """
    从官网 URL 同步行业数据到 stock_basic_info
    需配置 OFFICIAL_INDUSTRY_DATA_URL，格式: {"600519":"白酒","000001":"银行"}
    """
    try:
        from app.services.official_industry_service import sync_industry_to_stock_basic_info, get_official_industry_url
        if not get_official_industry_url():
            raise HTTPException(
                status_code=400,
                detail="未配置 OFFICIAL_INDUSTRY_DATA_URL，请在 .env 中设置官网行业数据 JSON 的 URL"
            )
        result = await sync_industry_to_stock_basic_info()
        return ok(data=result, message=f"行业数据同步完成，更新 {result.get('updated', 0)} 条")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 行业数据同步失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"行业数据同步失败: {str(e)}")

