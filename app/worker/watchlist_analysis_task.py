"""
自选股定时分析任务

定时分析用户自选股列表中的股票，复用现有的分析服务。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.database import get_mongo_db
from app.services.notifications_service import NotificationsService
from app.models.notification import NotificationCreate
from app.models.analysis import SingleAnalysisRequest

logger = logging.getLogger("app.worker.watchlist_analysis")

# 全局状态
_is_running = False


async def get_watchlist_stocks() -> List[Dict[str, Any]]:
    """获取所有有效用户的自选股列表

    只返回在 users 集合中存在的用户的自选股，过滤掉历史遗留的垃圾数据。

    Returns:
        包含 user_id 和 stocks 的字典列表
    """
    from bson import ObjectId

    db = get_mongo_db()

    # 第一步：获取所有有效用户的 ID
    users_cursor = db.users.find({}, {"_id": 1})
    valid_user_ids = set()
    async for user in users_cursor:
        user_id_str = str(user["_id"])
        valid_user_ids.add(user_id_str)

    logger.info(f"📊 数据库中共有 {len(valid_user_ids)} 个有效用户")

    # 第二步：从 user_favorites 集合查询有自选股的记录
    cursor = db.user_favorites.find(
        {"favorites": {"$exists": True, "$ne": []}}
    )

    result = []
    skipped_count = 0

    async for doc in cursor:
        user_id = doc.get("user_id", "unknown")
        favorites = doc.get("favorites", [])

        # 检查该 user_id 是否在有效用户列表中
        if user_id not in valid_user_ids:
            logger.warning(f"⚠️ 跳过无效用户的自选股: {user_id} (用户不存在于 users 集合)")
            skipped_count += 1
            continue

        if favorites:
            logger.info(f"📋 找到有效用户 {user_id} 的 {len(favorites)} 只自选股")
            result.append({
                "user_id": user_id,
                "stocks": favorites
            })

    if skipped_count > 0:
        logger.info(f"🗑️ 已跳过 {skipped_count} 条历史遗留的垃圾数据")

    if not result:
        logger.info("📭 没有找到任何有效用户的自选股数据")
    else:
        logger.info(f"✅ 共找到 {len(result)} 个有效用户有自选股")

    return result


async def analyze_user_watchlist_batch(
    user_id: str,
    stocks: List[Dict[str, Any]],
    analysis_date: str
) -> Dict[str, Any]:
    """
    批量分析用户的自选股（并发执行）

    参考批量分析API的实现方式：
    1. 先为所有股票创建任务
    2. 然后使用 asyncio.create_task 并发执行所有任务

    Args:
        user_id: 用户ID
        stocks: 自选股列表
        analysis_date: 分析日期

    Returns:
        包含任务ID列表和统计信息的字典
    """
    from app.services.simple_analysis_service import get_simple_analysis_service
    from app.models.analysis import AnalysisParameters

    service = get_simple_analysis_service()

    # 创建分析参数（使用标准分析配置 - 3级）
    # 注意：前端使用数字1-5表示深度，后端使用中文"快速/基础/标准/深度/全面"
    # 这里使用"标准"（对应前端的3级），平衡速度和质量
    parameters = AnalysisParameters(
        market_type="A股",
        research_depth="标准",  # 3级 - 标准分析（推荐）
        selected_analysts=["market", "fundamentals"]
    )

    task_ids = []
    task_mapping = []

    # 第一步：为所有股票创建任务（立即创建，不执行）
    logger.info(f"  📝 开始创建 {len(stocks)} 个分析任务...")
    for idx, stock in enumerate(stocks, 1):
        stock_code = stock.get("stock_code")
        stock_name = stock.get("stock_name", stock_code)

        try:
            request = SingleAnalysisRequest(
                symbol=stock_code,
                stock_code=stock_code,
                stock_name=stock_name,
                analysis_date=analysis_date,
                parameters=parameters
            )

            # 创建任务（不执行）
            task_info = await service.create_analysis_task(user_id, request)
            task_id = task_info.get("task_id")

            if not task_id:
                raise RuntimeError(f"创建任务失败：未返回task_id (stock={stock_code})")

            task_ids.append(task_id)
            task_mapping.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "task_id": task_id,
                "request": request
            })

            logger.info(f"    ✅ [{idx}/{len(stocks)}] 已创建任务: {task_id} - {stock_code} {stock_name}")

        except Exception as e:
            logger.error(f"    ❌ [{idx}/{len(stocks)}] 创建任务失败: {stock_code} {stock_name}, 错误: {e}")
            task_mapping.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "task_id": None,
                "error": str(e)
            })

    logger.info(f"  ✅ 任务创建完成: 成功 {len(task_ids)}/{len(stocks)}")

    # 第二步：并发执行所有任务
    if task_ids:
        logger.info(f"  🚀 开始并发执行 {len(task_ids)} 个分析任务...")

        async def run_concurrent_analysis():
            """并发执行所有分析任务"""
            tasks = []

            for item in task_mapping:
                if item.get("task_id"):
                    task_id = item["task_id"]
                    request = item["request"]
                    stock_code = item["stock_code"]

                    # 创建异步任务
                    async def run_single_analysis(tid: str, req: SingleAnalysisRequest, uid: str, code: str):
                        try:
                            logger.info(f"    🔄 开始执行: {tid} - {code}")
                            await service.execute_analysis_background(tid, uid, req)
                            logger.info(f"    ✅ 执行完成: {tid} - {code}")
                        except Exception as e:
                            logger.error(f"    ❌ 执行失败: {tid} - {code}, 错误: {e}", exc_info=True)

                    # 添加到任务列表
                    task = asyncio.create_task(run_single_analysis(task_id, request, user_id, stock_code))
                    tasks.append(task)

            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"  🎉 所有分析任务执行完成")

        # 在后台启动并发任务（不等待完成）
        asyncio.create_task(run_concurrent_analysis())
        logger.info(f"  ✅ 已启动 {len(task_ids)} 个并发分析任务")

    return {
        "total": len(stocks),
        "created": len(task_ids),
        "failed": len(stocks) - len(task_ids),
        "task_ids": task_ids,
        "task_mapping": task_mapping
    }


async def send_completion_notification(
    user_id: str,
    total: int,
    success: int,
    failed: int,
    results: List[Dict[str, Any]]
):
    """发送分析完成通知"""
    notifications_service = NotificationsService()
    
    if success > 0:
        severity = "success" if failed == 0 else "warning"
        title = "自选股定时分析完成"
        content = f"已完成 {success}/{total} 只股票的分析"
        if failed > 0:
            content += f"，{failed} 只分析失败"
    else:
        severity = "error"
        title = "自选股定时分析失败"
        content = f"全部 {total} 只股票分析失败"
    
    notification = NotificationCreate(
        user_id=user_id,
        type="analysis",
        title=title,
        content=content,
        link="/analysis/history",
        source="watchlist_scheduler",
        severity=severity,
        metadata={
            "total": total,
            "success": success,
            "failed": failed,
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "stocks": [
                {
                    "stock_code": r.get("stock_code"),
                    "stock_name": r.get("stock_name"),
                    "success": r.get("success", False)
                }
                for r in results
            ]
        }
    )
    
    try:
        await notifications_service.create_and_publish(notification)
        logger.info(f"📬 已发送分析完成通知给用户 {user_id}")
    except Exception as e:
        logger.error(f"❌ 发送通知失败: {e}")


async def run_watchlist_analysis():
    """
    定时分析自选股任务 - 主入口

    由 APScheduler 定时触发调用。
    遍历所有有自选股的用户，为每个用户分析其自选股。
    """
    global _is_running

    if _is_running:
        logger.warning("⚠️ 自选股定时分析任务正在运行中，跳过本次执行")
        return

    _is_running = True
    start_time = datetime.now()
    analysis_date = start_time.strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info("🚀 开始执行自选股定时分析任务")
    logger.info(f"   分析日期: {analysis_date}")
    logger.info("=" * 60)

    total_stocks = 0
    total_success = 0
    total_failed = 0

    try:
        # 获取所有用户的自选股列表
        watchlist_data = await get_watchlist_stocks()

        if not watchlist_data:
            logger.info("📭 没有找到任何用户的自选股，任务结束")
            return

        logger.info(f"📊 共 {len(watchlist_data)} 个用户有自选股")

        # 遍历每个用户
        for user_idx, user_data in enumerate(watchlist_data, 1):
            user_id = user_data["user_id"]
            stocks = user_data["stocks"]
            user_total = len(stocks)

            logger.info("-" * 40)
            logger.info(f"👤 [{user_idx}/{len(watchlist_data)}] 用户: {user_id}")
            logger.info(f"📊 待分析股票数: {user_total}")

            # 使用批量分析方法（并发执行）
            batch_result = await analyze_user_watchlist_batch(
                user_id=user_id,
                stocks=stocks,
                analysis_date=analysis_date
            )

            user_success = batch_result["created"]
            user_failed = batch_result["failed"]

            # 累计统计
            total_stocks += user_total
            total_success += user_success
            total_failed += user_failed

            # 发送通知给该用户
            # 注意：由于是并发执行，这里发送通知时任务可能还在执行中
            # 可以考虑在所有任务完成后再发送通知，或者在通知中说明"已启动分析"
            await send_completion_notification(
                user_id=user_id,
                total=user_total,
                success=user_success,
                failed=user_failed,
                results=[]  # 并发执行时无法立即获取结果
            )

            logger.info(f"  ✅ 用户 {user_id} 批量分析已启动: 成功创建 {user_success} 个任务, 失败 {user_failed} 个")

        # 计算总耗时
        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info("✅ 自选股定时分析任务全部完成")
        logger.info(f"   用户数: {len(watchlist_data)}")
        logger.info(f"   总分析股票数: {total_stocks}")
        logger.info(f"   总成功: {total_success}, 总失败: {total_failed}")
        logger.info(f"   总耗时: {elapsed:.2f} 秒")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 自选股定时分析任务执行失败: {e}", exc_info=True)
    finally:
        _is_running = False

