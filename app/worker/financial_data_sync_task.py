#!/usr/bin/env python3
"""
财务数据同步任务（调度器入口）

使用统一的财务数据同步服务，支持线程池并行处理
"""
import logging
from typing import Dict, Any

from app.worker.financial_data_sync_service import get_financial_sync_service
from app.services.scheduler_service import mark_job_completed, TaskCancelledException

logger = logging.getLogger(__name__)


async def run_financial_data_sync(**kwargs):
    """
    APScheduler任务：统一财务数据同步（使用线程池）
    
    支持多数据源并行同步，使用线程池实现真正的并行处理
    """
    job_id = kwargs.get("job_id", "financial_data_sync")
    
    logger.info(f"🚀 [财务数据同步] 开始执行任务 (job_id={job_id})")
    
    # 🔥 手动触发或强制执行时允许执行（即使有running记录）
    manual_trigger = kwargs.get("_manual_trigger", False)
    force_execute = kwargs.get("_force_execute", False)
    
    if not manual_trigger and not force_execute:
        # 🔥 检查是否已有实例在运行（非手动触发且非强制执行时才检查）
        from app.worker.tushare_sync_service import _check_task_running
        is_running, instance_id = await _check_task_running(job_id)
        if is_running:
            logger.warning(f"⚠️ 任务 {job_id} 已有实例在运行（_id={instance_id}），跳过本次执行")
            return {
                "skipped": True,
                "reason": "已有实例在运行",
                "running_instance_id": instance_id
            }
    else:
        if manual_trigger:
            logger.info(f"🔧 [APScheduler] 手动触发执行，允许执行（即使有running记录）")
        if force_execute:
            logger.info(f"🔧 [APScheduler] 强制执行，跳过并发检查")
    
    try:
        # 获取统一的财务数据同步服务
        service = await get_financial_sync_service()
        
        # 从kwargs获取参数
        data_sources = kwargs.get("data_sources", ["tushare", "akshare", "baostock"])
        report_types = kwargs.get("report_types", ["quarterly", "annual"])
        symbols = kwargs.get("symbols", None)  # None表示同步所有股票
        
        # 执行同步（使用线程池）
        results = await service.sync_financial_data(
            symbols=symbols,
            data_sources=data_sources,
            report_types=report_types,
            job_id=job_id
        )
        
        # 统计总体结果
        total_success = sum(stats.success_count for stats in results.values())
        total_symbols = sum(stats.total_symbols for stats in results.values())
        total_errors = sum(stats.error_count for stats in results.values())
        
        # 标记任务完成
        try:
            stats_dict = {
                "total_processed": total_symbols,
                "success_count": total_success,
                "error_count": total_errors,
                "errors": []
            }
            
            # 收集所有错误
            for source, stats in results.items():
                if stats.errors:
                    stats_dict["errors"].extend([
                        {"data_source": source, **error} 
                        for error in stats.errors[:5]  # 每个数据源最多5个错误
                    ])
            
            await mark_job_completed(job_id, stats_dict)
        except Exception as e:
            logger.warning(f"⚠️ 更新任务完成状态失败: {e}")
        
        logger.info(f"✅ [财务数据同步] 任务完成: job_id={job_id}, "
                   f"成功={total_success}/{total_symbols}, 失败={total_errors}")
        
        return {
            "success": True,
            "job_id": job_id,
            "total_symbols": total_symbols,
            "success_count": total_success,
            "error_count": total_errors,
            "results": {source: stats.to_dict() for source, stats in results.items()}
        }
        
    except TaskCancelledException:
        logger.info(f"ℹ️ [财务数据同步] 任务已被用户取消: job_id={job_id}")
        return {"cancelled": True, "message": "任务已被用户取消"}
    except Exception as e:
        logger.error(f"❌ [财务数据同步] 任务失败: job_id={job_id}, error={e}", exc_info=True)
        
        # 标记任务为失败
        try:
            await mark_job_completed(
                job_id=job_id,
                error_message=f"财务数据同步失败: {str(e)}"
            )
        except Exception as mark_error:
            logger.warning(f"⚠️ 标记任务失败状态失败: {mark_error}")
        
        raise
