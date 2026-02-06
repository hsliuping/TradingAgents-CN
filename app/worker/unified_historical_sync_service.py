#!/usr/bin/env python3
"""
统一历史数据同步服务
支持并行执行多个数据源的历史数据同步任务
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.worker.tushare_sync_service import get_tushare_sync_service
from app.worker.akshare_sync_service import get_akshare_sync_service
from app.worker.baostock_sync_service import BaoStockSyncService

logger = logging.getLogger(__name__)


async def run_unified_historical_sync(
    data_sources: List[str] = None,
    incremental: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    统一历史数据同步任务：并行执行多个数据源的历史数据同步
    
    Args:
        data_sources: 要同步的数据源列表，如 ["tushare", "akshare", "baostock"]
                     如果为 None，则同步所有启用的数据源
        incremental: 是否增量同步
        **kwargs: 其他参数（传递给各个数据源的同步函数）
    
    Returns:
        同步结果统计
    """
    # 默认同步所有数据源
    if data_sources is None:
        data_sources = ["tushare", "akshare", "baostock"]
    
    logger.info(f"🚀 开始统一历史数据同步: 数据源={data_sources}, 增量同步={incremental}")
    
    # 准备任务列表
    tasks = []
    task_info = []
    
    # 🔥 为每个数据源创建并行任务
    for data_source in data_sources:
        if data_source == "tushare":
            task = _run_tushare_historical_sync_task(incremental, **kwargs)
            tasks.append(task)
            task_info.append("tushare")
        elif data_source == "akshare":
            task = _run_akshare_historical_sync_task(incremental, **kwargs)
            tasks.append(task)
            task_info.append("akshare")
        elif data_source == "baostock":
            task = _run_baostock_historical_sync_task(**kwargs)
            tasks.append(task)
            task_info.append("baostock")
        else:
            logger.warning(f"⚠️ 不支持的数据源: {data_source}，跳过")
    
    if not tasks:
        logger.warning("⚠️ 没有可用的数据源进行历史数据同步")
        return {
            "success": False,
            "message": "没有可用的数据源",
            "results": {}
        }
    
    # 🔥 并行执行所有数据源的同步任务
    logger.info(f"🚀 开始并行同步 {len(tasks)} 个数据源的历史数据: {task_info}")
    
    try:
        # 使用 asyncio.gather 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        final_results = {}
        success_count = 0
        error_count = 0
        
        for i, (data_source, result) in enumerate(zip(task_info, results)):
            if isinstance(result, Exception):
                logger.error(f"❌ {data_source} 历史数据同步失败: {result}", exc_info=True)
                final_results[data_source] = {
                    "success": False,
                    "error": str(result)
                }
                error_count += 1
            else:
                logger.info(f"✅ {data_source} 历史数据同步完成: {result}")
                final_results[data_source] = {
                    "success": True,
                    "result": result
                }
                success_count += 1
        
        logger.info(f"🎉 统一历史数据同步完成: 成功 {success_count}/{len(tasks)}, 失败 {error_count}/{len(tasks)}")
        
        return {
            "success": error_count == 0,
            "total_sources": len(tasks),
            "success_count": success_count,
            "error_count": error_count,
            "results": final_results
        }
        
    except Exception as e:
        logger.error(f"❌ 统一历史数据同步失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "results": {}
        }


async def _run_tushare_historical_sync_task(incremental: bool, **kwargs):
    """运行 Tushare 历史数据同步任务"""
    try:
        from app.worker.tushare_sync_service import run_tushare_historical_sync
        # 设置手动触发标记，允许并行执行
        kwargs["_manual_trigger"] = True
        result = await run_tushare_historical_sync(incremental=incremental, **kwargs)
        return result
    except Exception as e:
        logger.error(f"❌ Tushare 历史数据同步任务失败: {e}", exc_info=True)
        raise


async def _run_akshare_historical_sync_task(incremental: bool, **kwargs):
    """运行 AKShare 历史数据同步任务"""
    try:
        from app.worker.akshare_sync_service import run_akshare_historical_sync
        # 设置手动触发标记，允许并行执行
        kwargs["_manual_trigger"] = True
        result = await run_akshare_historical_sync(incremental=incremental, **kwargs)
        return result
    except Exception as e:
        logger.error(f"❌ AKShare 历史数据同步任务失败: {e}", exc_info=True)
        raise


async def _run_baostock_historical_sync_task(**kwargs):
    """运行 BaoStock 历史数据同步任务"""
    try:
        from app.worker.baostock_sync_service import run_baostock_historical_sync
        # 设置手动触发标记，允许并行执行
        kwargs["_manual_trigger"] = True
        result = await run_baostock_historical_sync(**kwargs)
        return result
    except Exception as e:
        logger.error(f"❌ BaoStock 历史数据同步任务失败: {e}", exc_info=True)
        raise
