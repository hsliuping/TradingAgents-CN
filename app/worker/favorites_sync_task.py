"""
自选股A股历史数据和财务数据同步任务

同步时按项目统一的数据源优先级（get_enabled_data_sources_async）顺序执行。
"""

import logging
from typing import List, Set, Dict, Any
from datetime import datetime

from app.core.database import get_mongo_db
from app.core.data_source_priority import get_enabled_data_sources_async
from app.worker.tushare_sync_service import get_tushare_sync_service
from app.worker.akshare_sync_service import get_akshare_sync_service
from app.worker.financial_data_sync_service import FinancialDataSyncService

logger = logging.getLogger("webapi")


def _get_sync_data_sources(enabled_sources: List[str]) -> List[str]:
    """从启用的数据源中排除 local，得到用于同步的数据源列表（按优先级顺序）。"""
    sync_sources = [s for s in enabled_sources if s and s.lower() != "local"]
    return sync_sources if sync_sources else ["tushare", "akshare", "baostock"]


async def get_all_favorite_a_stocks() -> List[str]:
    """
    获取所有用户自选股中的A股股票代码列表
    
    Returns:
        A股股票代码列表（去重）
    """
    db = get_mongo_db()
    
    try:
        # 从 user_favorites 集合中获取所有用户的自选股
        cursor = db.user_favorites.find({}, {"favorites": 1})
        
        a_stock_codes: Set[str] = set()
        
        async for doc in cursor:
            favorites = doc.get("favorites", [])
            for favorite in favorites:
                # 只获取A股股票
                market = favorite.get("market", "A股")
                if market == "A股":
                    stock_code = favorite.get("stock_code")
                    if stock_code:
                        # 确保股票代码是6位数字格式
                        stock_code = str(stock_code).zfill(6)
                        a_stock_codes.add(stock_code)
        
        codes_list = sorted(list(a_stock_codes))
        logger.info(f"📊 获取到 {len(codes_list)} 只A股自选股需要同步")
        
        return codes_list
        
    except Exception as e:
        logger.error(f"❌ 获取自选股A股列表失败: {e}")
        return []


async def sync_favorites_historical_data():
    """
    同步自选股中A股的历史数据。
    按数据源优先级（get_enabled_data_sources_async）顺序，使用第一个支持指定股票列表的数据源。
    
    Returns:
        同步结果统计
    """
    logger.info("🔄 开始同步自选股A股历史数据...")
    
    try:
        # 1. 获取所有自选股中的A股代码
        a_stock_codes = await get_all_favorite_a_stocks()
        
        if not a_stock_codes:
            logger.info("ℹ️ 没有A股自选股需要同步历史数据")
            return {
                "success": True,
                "message": "没有A股自选股需要同步",
                "total_count": 0,
                "synced_count": 0,
                "data_source": None
            }
        
        # 2. 按数据源优先级获取同步数据源列表（排除 local）
        enabled_sources = await get_enabled_data_sources_async("a_shares")
        data_sources = _get_sync_data_sources(enabled_sources)
        logger.info(f"📊 自选股历史数据同步数据源优先级: {data_sources}")
        
        result = None
        used_source = None
        
        # 3. 按优先级依次尝试：Tushare、AKShare 支持 symbols；BaoStock 从库取列表，不限定自选股，此处仅用 tushare/akshare
        for source in data_sources:
            source_lower = source.lower()
            try:
                if source_lower == "tushare":
                    service = await get_tushare_sync_service()
                    result = await service.sync_historical_data(
                        symbols=a_stock_codes,
                        incremental=True,
                        period="daily"
                    )
                    used_source = "tushare"
                    break
                elif source_lower == "akshare":
                    service = await get_akshare_sync_service()
                    result = await service.sync_historical_data(
                        symbols=a_stock_codes,
                        incremental=True,
                        period="daily"
                    )
                    used_source = "akshare"
                    break
                elif source_lower == "baostock":
                    # BaoStock 的 sync_historical_data 从数据库取股票列表，无法限定为自选股，跳过
                    logger.debug("BaoStock 历史同步不支持指定股票列表，跳过")
                    continue
            except Exception as e:
                logger.warning(f"⚠️ 自选股历史数据同步使用 {source} 失败: {e}，尝试下一数据源")
                continue
        
        if result is None or used_source is None:
            logger.warning("⚠️ 自选股历史数据同步：无可用数据源（已尝试 tushare/akshare）")
            return {
                "success": False,
                "message": "无可用数据源或全部失败",
                "total_count": len(a_stock_codes),
                "synced_count": 0,
                "data_source": None,
                "error": "无可用数据源"
            }
        
        success_count = result.get("success_count", 0)
        total_records = result.get("total_records", 0)
        
        logger.info(
            f"✅ 自选股A股历史数据同步完成（数据源: {used_source}）: "
            f"股票数={len(a_stock_codes)}, 成功={success_count}, 记录数={total_records}"
        )
        
        return {
            "success": True,
            "message": "自选股A股历史数据同步完成",
            "total_count": len(a_stock_codes),
            "synced_count": success_count,
            "total_records": total_records,
            "data_source": used_source,
            "details": result
        }
        
    except Exception as e:
        logger.error(f"❌ 自选股A股历史数据同步失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"同步失败: {str(e)}",
            "total_count": 0,
            "synced_count": 0,
            "error": str(e)
        }


async def sync_favorites_financial_data():
    """
    同步自选股中A股的财务数据。
    按数据源优先级（get_enabled_data_sources_async）顺序同步。
    
    Returns:
        同步结果统计
    """
    logger.info("💰 开始同步自选股A股财务数据...")
    
    try:
        # 1. 获取所有自选股中的A股代码
        a_stock_codes = await get_all_favorite_a_stocks()
        
        if not a_stock_codes:
            logger.info("ℹ️ 没有A股自选股需要同步财务数据")
            return {
                "success": True,
                "message": "没有A股自选股需要同步",
                "total_count": 0,
                "synced_count": 0
            }
        
        # 2. 按数据源优先级获取同步数据源列表（排除 local）
        enabled_sources = await get_enabled_data_sources_async("a_shares")
        data_sources = _get_sync_data_sources(enabled_sources)
        logger.info(f"📊 自选股财务数据同步数据源优先级: {data_sources}")
        
        # 3. 使用财务数据同步服务，按优先级顺序同步
        financial_service = FinancialDataSyncService()
        await financial_service.initialize()
        
        # 同步财务数据（获取最近20期，约5年），数据源按优先级顺序
        result = await financial_service.sync_financial_data(
            symbols=a_stock_codes,
            data_sources=data_sources,
            report_types=["quarterly", "annual"],  # 季报和年报
            batch_size=50,
            delay_seconds=1.0
        )
        
        # 统计同步结果
        total_synced = 0
        total_errors = 0
        for source, stats in result.items():
            total_synced += stats.success_count
            total_errors += stats.error_count
        
        logger.info(
            f"✅ 自选股A股财务数据同步完成: "
            f"股票数={len(a_stock_codes)}, "
            f"成功同步={total_synced}, "
            f"失败={total_errors}"
        )
        
        return {
            "success": True,
            "message": "自选股A股财务数据同步完成",
            "total_count": len(a_stock_codes),
            "synced_count": total_synced,
            "error_count": total_errors,
            "details": {source: {
                "success_count": stats.success_count,
                "error_count": stats.error_count,
                "skipped_count": stats.skipped_count,
                "total_symbols": stats.total_symbols
            } for source, stats in result.items()}
        }
        
    except Exception as e:
        logger.error(f"❌ 自选股A股财务数据同步失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"同步失败: {str(e)}",
            "total_count": 0,
            "synced_count": 0,
            "error": str(e)
        }


async def run_favorites_data_sync():
    """
    APScheduler任务：同步自选股中A股的历史数据和财务数据
    
    这个任务会：
    1. 获取所有用户自选股中的A股股票代码
    2. 同步这些股票的历史数据（增量同步）
    3. 同步这些股票的财务数据（最近20期）
    """
    job_id = "favorites_data_sync"
    logger.info("🚀 [APScheduler] 开始执行自选股A股数据同步任务")
    
    start_time = datetime.now()
    
    try:
        # 导入进度更新函数
        from app.services.scheduler_service import update_job_progress
        
        # 获取自选股数量（用于进度计算）
        a_stock_codes = await get_all_favorite_a_stocks()
        total_stocks = len(a_stock_codes)
        
        # 更新进度：开始（0%）
        try:
            await update_job_progress(
                job_id=job_id,
                progress=0,
                message="开始同步自选股A股数据...",
                total_items=total_stocks if total_stocks > 0 else 1
            )
        except Exception as e:
            logger.warning(f"⚠️ 更新任务进度失败: {e}")
        
        # 1. 同步历史数据（进度：0-50%）
        try:
            await update_job_progress(
                job_id=job_id,
                progress=10,
                message="正在同步历史数据...",
                total_items=total_stocks if total_stocks > 0 else 1
            )
        except Exception:
            pass
        
        hist_result = await sync_favorites_historical_data()
        
        # 更新进度：历史数据完成（50%）
        try:
            await update_job_progress(
                job_id=job_id,
                progress=50,
                message=f"历史数据同步完成: {hist_result.get('synced_count', 0)}/{hist_result.get('total_count', 0)} 只股票",
                total_items=total_stocks if total_stocks > 0 else 1,
                processed_items=hist_result.get('synced_count', 0)
            )
        except Exception:
            pass
        
        # 2. 同步财务数据（进度：50-90%）
        try:
            await update_job_progress(
                job_id=job_id,
                progress=60,
                message="正在同步财务数据...",
                total_items=total_stocks if total_stocks > 0 else 1
            )
        except Exception:
            pass
        
        fin_result = await sync_favorites_financial_data()
        
        # 更新进度：财务数据完成（90%）
        try:
            await update_job_progress(
                job_id=job_id,
                progress=90,
                message=f"财务数据同步完成: {fin_result.get('synced_count', 0)}/{fin_result.get('total_count', 0)} 只股票",
                total_items=total_stocks if total_stocks > 0 else 1,
                processed_items=fin_result.get('synced_count', 0)
            )
        except Exception:
            pass
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 更新进度：完成（100%）
        try:
            await update_job_progress(
                job_id=job_id,
                progress=100,
                message=f"任务完成（耗时: {duration:.2f}秒）",
                total_items=total_stocks if total_stocks > 0 else 1,
                processed_items=total_stocks if total_stocks > 0 else 1
            )
        except Exception:
            pass
        
        logger.info(
            f"✅ [APScheduler] 自选股A股数据同步任务完成 "
            f"(耗时: {duration:.2f}秒)\n"
            f"   历史数据: {hist_result.get('synced_count', 0)}/{hist_result.get('total_count', 0)} 只股票\n"
            f"   财务数据: {fin_result.get('synced_count', 0)}/{fin_result.get('total_count', 0)} 只股票"
        )
        
        return {
            "success": True,
            "duration_seconds": duration,
            "historical_data": hist_result,
            "financial_data": fin_result
        }
        
    except Exception as e:
        logger.error(f"❌ [APScheduler] 自选股A股数据同步任务失败: {e}", exc_info=True)
        
        # 更新进度：失败
        try:
            from app.services.scheduler_service import update_job_progress
            await update_job_progress(
                job_id=job_id,
                progress=0,
                message=f"任务失败: {str(e)}"
            )
        except Exception:
            pass
        
        return {
            "success": False,
            "error": str(e)
        }
