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
    analysis_date: str,
    analysis_depth: int = 3,
    quick_analysis_model: str = "qwen-plus",
    deep_analysis_model: str = "qwen-max"
) -> Dict[str, Any]:
    """
    批量分析用户的自选股（并发执行）- 使用 v2.0 引擎

    参考批量分析API的实现方式：
    1. 先为所有股票创建任务（使用 v2.0 统一任务引擎）
    2. 然后使用 asyncio.create_task 并发执行所有任务

    Args:
        user_id: 用户ID
        stocks: 自选股列表
        analysis_date: 分析日期
        analysis_depth: 分析深度 (1-5)
        quick_analysis_model: 快速分析模型
        deep_analysis_model: 深度分析模型

    Returns:
        包含任务ID列表和统计信息的字典
    """
    from app.services.task_analysis_service import get_task_analysis_service
    from app.models.analysis import AnalysisTaskType
    from app.models.user import PyObjectId

    task_service = get_task_analysis_service()

    # 将数字深度转换为中文描述
    depth_mapping = {
        1: "快速",
        2: "基础",
        3: "标准",
        4: "深度",
        5: "全面"
    }
    research_depth = depth_mapping.get(analysis_depth, "标准")

    task_ids = []
    task_mapping = []

    # 第一步：为所有股票创建任务（使用 v2.0 引擎）
    logger.info(f"  📝 [v2.0引擎] 开始创建 {len(stocks)} 个分析任务...")
    for idx, stock in enumerate(stocks, 1):
        stock_code = stock.get("stock_code")
        stock_name = stock.get("stock_name", stock_code)

        try:
            # 准备任务参数
            task_params = {
                "symbol": stock_code,
                "stock_code": stock_code,
                "market_type": "cn",
                "analysis_date": analysis_date,
                "research_depth": research_depth,
                "quick_analysis_model": quick_analysis_model,
                "deep_analysis_model": deep_analysis_model
            }

            # 使用 v2.0 统一任务引擎创建任务
            task = await task_service.create_task(
                user_id=PyObjectId(user_id),
                task_type=AnalysisTaskType.STOCK_ANALYSIS,
                task_params=task_params,
                engine_type="auto",  # 自动选择引擎
                preference_type="neutral"
            )

            task_id = task.task_id

            task_ids.append(task_id)
            task_mapping.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "task_id": task_id,
                "task": task
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

    # 第二步：并发执行所有任务（使用 v2.0 引擎）
    if task_ids:
        logger.info(f"  🚀 [v2.0引擎] 开始并发执行 {len(task_ids)} 个分析任务...")

        async def run_concurrent_analysis():
            """并发执行所有分析任务"""
            tasks = []

            for item in task_mapping:
                if item.get("task_id"):
                    task_id = item["task_id"]
                    stock_code = item["stock_code"]

                    # 创建异步任务
                    async def run_single_analysis(tid: str, code: str):
                        try:
                            logger.info(f"    🔄 [v2.0引擎] 开始执行: {tid} - {code}")
                            # 使用 v2.0 统一任务引擎执行
                            await task_service.execute_task(tid)
                            logger.info(f"    ✅ [v2.0引擎] 执行完成: {tid} - {code}")
                        except Exception as e:
                            logger.error(f"    ❌ [v2.0引擎] 执行失败: {tid} - {code}, 错误: {e}", exc_info=True)

                    # 添加到任务列表
                    task = asyncio.create_task(run_single_analysis(task_id, stock_code))
                    tasks.append(task)

            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("  🎉 所有分析任务执行完成")

        # 在后台启动并发任务（不等待完成）
        _background_task = asyncio.create_task(run_concurrent_analysis())
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

    # 发送邮件通知（如果用户启用了邮件通知）
    try:
        from app.services.email_service import get_email_service
        email_service = get_email_service()

        # 统计推荐结果
        buy_count = sum(1 for r in results if r.get("recommendation") == "买入")
        hold_count = sum(1 for r in results if r.get("recommendation") == "持有")
        sell_count = sum(1 for r in results if r.get("recommendation") == "卖出")

        await email_service.send_analysis_email(
            user_id=user_id,
            email_type="scheduled_analysis",
            template_name="scheduled_report",
            template_data={
                "task_name": "自选股定时分析",
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total_count": total,
                "success_count": success,
                "failed_count": failed,
                "buy_count": buy_count,
                "hold_count": hold_count,
                "sell_count": sell_count,
                "stocks": results[:10],  # 只发送前10只股票的详情
                "detail_url": "/analysis/history"
            },
            reference_id=f"scheduled_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        logger.info(f"📧 已尝试发送定时分析完成邮件给用户 {user_id}")
    except Exception as email_err:
        logger.warning(f"⚠️ 发送邮件通知失败(忽略): {email_err}")


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


async def run_scheduled_analysis_slot(config_id: str, user_id: str, slot_index: int):
    """
    执行定时分析时间段任务 - 新版（支持分组和自定义参数）

    Args:
        config_id: 配置ID
        user_id: 用户ID
        slot_index: 时间段索引
    """
    logger.info("=" * 70)
    logger.info(f"🚀 开始执行定时分析时间段任务")
    logger.info(f"   配置ID: {config_id}")
    logger.info(f"   用户ID: {user_id}")
    logger.info(f"   时间段索引: {slot_index}")
    logger.info("=" * 70)

    try:
        # 获取配置
        from bson import ObjectId
        config = await get_mongo_db().scheduled_analysis_configs.find_one({
            "_id": ObjectId(config_id),
            "user_id": user_id
        })

        if not config:
            logger.error(f"❌ 配置不存在: {config_id}")
            return

        if not config.get("enabled"):
            logger.warning(f"⚠️ 配置已禁用: {config_id}")
            return

        time_slots = config.get("time_slots", [])
        if slot_index >= len(time_slots):
            logger.error(f"❌ 时间段索引超出范围: {slot_index}")
            return

        slot = time_slots[slot_index]
        if not slot.get("enabled", True):
            logger.warning(f"⚠️ 时间段已禁用: {slot.get('name')}")
            return

        logger.info(f"📅 时间段: {slot.get('name')}")
        logger.info(f"📋 分组数量: {len(slot.get('group_ids', []))}")

        # 获取要分析的分组ID列表
        group_ids = slot.get("group_ids", [])
        
        # 如果没有指定分组，尝试使用配置的默认分组
        if not group_ids:
            group_ids = config.get("default_group_ids", [])
            
        # 如果仍然没有指定分组，则跳过
        if not group_ids:
            logger.warning(f"⚠️ 时间段未配置分组: {slot.get('name')}")
            return

        # 获取分组信息
        db = get_mongo_db()
        groups = []
        for group_id in group_ids:
            try:
                group = await db.watchlist_groups.find_one({
                    "_id": ObjectId(group_id),
                    "user_id": user_id,
                    "is_active": True
                })
                if group:
                    groups.append(group)
            except Exception as e:
                logger.error(f"❌ 获取分组失败: {group_id} - {e}")

        if not groups:
            logger.warning(f"⚠️ 没有找到有效的分组")
            return

        logger.info(f"✅ 找到 {len(groups)} 个有效分组")

        # 统计
        total_stocks = 0
        total_success = 0
        total_failed = 0
        all_task_ids = []

        # 为每个分组执行分析
        for group in groups:
            group_name = group.get("name", "未命名")
            stock_codes = group.get("stock_codes", [])

            if not stock_codes:
                logger.info(f"  📁 分组 [{group_name}] 没有股票，跳过")
                continue

            logger.info(f"  📁 分组 [{group_name}]: {len(stock_codes)} 只股票")

            # 确定分析参数（优先级：时间段 > 分组 > 配置默认值）
            analysis_depth = (
                slot.get("analysis_depth") or
                group.get("analysis_depth") or
                config.get("default_analysis_depth", 3)
            )
            quick_model = (
                slot.get("quick_analysis_model") or
                group.get("quick_analysis_model") or
                config.get("default_quick_analysis_model", "qwen-plus")
            )
            deep_model = (
                slot.get("deep_analysis_model") or
                group.get("deep_analysis_model") or
                config.get("default_deep_analysis_model", "qwen-max")
            )

            logger.info(f"     分析深度: {analysis_depth}")
            logger.info(f"     快速模型: {quick_model}")
            logger.info(f"     深度模型: {deep_model}")

            # 构建股票列表
            stocks = [{"stock_code": code} for code in stock_codes]

            # 执行批量分析
            batch_result = await analyze_user_watchlist_batch(
                user_id=user_id,
                stocks=stocks,
                analysis_date=datetime.now().strftime("%Y-%m-%d"),
                analysis_depth=analysis_depth,
                quick_analysis_model=quick_model,
                deep_analysis_model=deep_model
            )

            group_success = batch_result["created"]
            group_failed = batch_result["failed"]

            total_stocks += len(stock_codes)
            total_success += group_success
            total_failed += group_failed
            
            if batch_result.get("task_ids"):
                all_task_ids.extend(batch_result["task_ids"])

            logger.info(f"     ✅ 成功: {group_success}, 失败: {group_failed}")

        # 发送通知
        await send_completion_notification(
            user_id=user_id,
            total=total_stocks,
            success=total_success,
            failed=total_failed,
            results=[]
        )

        # 更新配置的最后运行时间
        from app.utils.timezone import now_tz
        await db.scheduled_analysis_configs.update_one(
            {"_id": ObjectId(config_id)},
            {"$set": {"last_run_at": now_tz()}}
        )
        
        # 记录执行历史
        try:
            history_doc = {
                "config_id": config_id,
                "config_name": config.get("name", "未命名"),
                "time_slot_name": slot.get("name", "未命名"),
                "created_at": now_tz(),
                "status": "success" if total_failed == 0 else ("failed" if total_success == 0 else "partial"),
                "total_count": total_stocks,
                "success_count": total_success,
                "failed_count": total_failed,
                "task_ids": all_task_ids,
                "result_summary": None
            }
            await db.scheduled_analysis_history.insert_one(history_doc)
        except Exception as e:
            logger.error(f"❌ 记录执行历史失败: {e}")

        logger.info("=" * 70)
        logger.info(f"✅ 定时分析时间段任务完成")
        logger.info(f"   总股票数: {total_stocks}")
        logger.info(f"   成功启动: {total_success} 个分析任务")
        logger.info(f"   失败: {total_failed} 个")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"❌ 定时分析时间段任务执行失败: {e}", exc_info=True)

