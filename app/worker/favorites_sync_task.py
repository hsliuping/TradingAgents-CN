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
        
        # 🔥 优化：不同数据源可以并行执行（因为它们使用不同的API，互不影响）
        # 同一种数据源内部仍然是串行的（避免API限流）
        import asyncio
        
        tasks = []
        task_sources = []
        
        # 创建并发任务（只包含支持指定股票列表的数据源）
        for source in data_sources:
            source_lower = source.lower()
            
            # BaoStock 不支持指定股票列表，跳过
            if source_lower == "baostock":
                logger.debug("BaoStock 历史同步不支持指定股票列表，跳过")
                continue
            
            # 🔥 创建任务（使用闭包捕获变量，避免循环变量问题）
            if source_lower == "tushare":
                async def sync_tushare(codes=a_stock_codes):
                    service = await get_tushare_sync_service()
                    return await service.sync_historical_data(
                        symbols=codes,
                        incremental=True,
                        period="daily"
                    )
                tasks.append(sync_tushare())
                task_sources.append("tushare")
            elif source_lower == "akshare":
                async def sync_akshare(codes=a_stock_codes):
                    service = await get_akshare_sync_service()
                    return await service.sync_historical_data(
                        symbols=codes,
                        incremental=True,
                        period="daily"
                    )
                tasks.append(sync_akshare())
                task_sources.append("akshare")
        
        # 并行执行所有数据源的同步任务
        if tasks:
            logger.info(f"🚀 开始并行同步 {len(tasks)} 个数据源的历史数据: {task_sources}")
            
            # 使用 asyncio.gather 并行执行
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果：合并所有成功的数据源结果
            total_success_count = 0
            total_records = 0
            used_sources = []
            all_details = {}
            
            for i, (source, result) in enumerate(zip(task_sources, results)):
                if isinstance(result, Exception):
                    logger.warning(f"⚠️ {source} 历史数据同步失败: {result}")
                    all_details[source] = {"error": str(result)}
                else:
                    success_count = result.get("success_count", 0)
                    records = result.get("total_records", 0)
                    
                    total_success_count = max(total_success_count, success_count)  # 取最大值（因为不同数据源可能覆盖相同的股票）
                    total_records += records  # 累加记录数（不同数据源的数据会合并）
                    used_sources.append(source)
                    all_details[source] = result
                    
                    logger.info(f"✅ {source} 历史数据同步完成: 成功={success_count}, 记录={records}")
            
            if not used_sources:
                logger.warning("⚠️ 自选股历史数据同步：所有数据源都失败")
                return {
                    "success": False,
                    "message": "所有数据源同步失败",
                    "total_count": len(a_stock_codes),
                    "synced_count": 0,
                    "data_source": None,
                    "error": "所有数据源同步失败",
                    "details": all_details
                }
            
            logger.info(
                f"✅ 自选股A股历史数据同步完成（数据源: {', '.join(used_sources)}）: "
                f"股票数={len(a_stock_codes)}, 成功={total_success_count}, 记录数={total_records}"
            )
            
            return {
                "success": True,
                "message": "自选股A股历史数据同步完成",
                "total_count": len(a_stock_codes),
                "synced_count": total_success_count,
                "total_records": total_records,
                "data_source": ", ".join(used_sources) if used_sources else None,
                "data_sources": used_sources,  # 🔥 新增：返回所有成功的数据源列表
                "details": all_details  # 🔥 新增：返回所有数据源的详细结果
            }
        else:
            logger.warning("⚠️ 自选股历史数据同步：无可用数据源（已尝试 tushare/akshare）")
            return {
                "success": False,
                "message": "无可用数据源或全部失败",
                "total_count": len(a_stock_codes),
                "synced_count": 0,
                "data_source": None,
                "error": "无可用数据源"
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
            delay_seconds=1.0,
            job_id="favorites_financial_sync"  # 🔥 添加job_id用于进度跟踪
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
        
        # 🔥 优化：历史数据和财务数据可以并行执行（因为它们使用不同的API，互不影响）
        # 1. 并行执行历史数据和财务数据同步
        try:
            await update_job_progress(
                job_id=job_id,
                progress=10,
                message="正在并行同步历史数据和财务数据...",
                total_items=total_stocks if total_stocks > 0 else 1
            )
        except Exception:
            pass
        
        # 使用 asyncio.gather 并行执行历史数据和财务数据同步
        import asyncio
        hist_task = sync_favorites_historical_data()
        fin_task = sync_favorites_financial_data()
        
        hist_result, fin_result = await asyncio.gather(
            hist_task,
            fin_task,
            return_exceptions=True
        )
        
        # 处理异常结果
        if isinstance(hist_result, Exception):
            logger.error(f"❌ 历史数据同步失败: {hist_result}", exc_info=True)
            hist_result = {
                "success": False,
                "message": f"历史数据同步失败: {str(hist_result)}",
                "total_count": total_stocks,
                "synced_count": 0,
                "error": str(hist_result)
            }
        
        if isinstance(fin_result, Exception):
            logger.error(f"❌ 财务数据同步失败: {fin_result}", exc_info=True)
            fin_result = {
                "success": False,
                "message": f"财务数据同步失败: {str(fin_result)}",
                "total_count": total_stocks,
                "synced_count": 0,
                "error": str(fin_result)
            }
        
        # 更新进度：并行同步完成（90%）
        try:
            hist_synced = hist_result.get('synced_count', 0) if isinstance(hist_result, dict) else 0
            fin_synced = fin_result.get('synced_count', 0) if isinstance(fin_result, dict) else 0
            
            await update_job_progress(
                job_id=job_id,
                progress=90,
                message=f"并行同步完成: 历史数据 {hist_synced}/{total_stocks}, 财务数据 {fin_synced}/{total_stocks}",
                total_items=total_stocks if total_stocks > 0 else 1,
                processed_items=max(hist_synced, fin_synced)
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
