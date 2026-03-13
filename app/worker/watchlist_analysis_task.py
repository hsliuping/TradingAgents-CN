"""
自选股定时分析任务

定时分析用户自选股列表中的股票，复用现有的分析服务。
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.database import get_mongo_db
from app.services.notifications_service import NotificationsService
from app.models.notification import NotificationCreate
from app.models.analysis import SingleAnalysisRequest

logger = logging.getLogger("app.worker.watchlist_analysis")

# 全局状态
_is_running = False


def _build_scheduled_email_attachments(results: List[Dict[str, Any]], analysis_time: str) -> List[tuple]:
    """为定时分析完成邮件构建附件。"""
    if not results:
        return []

    markdown_lines = [
        "# Scheduled Analysis Report",
        "",
        f"Analysis Time: {analysis_time}",
        f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    export_payload = []
    for item in results:
        stock_code = item.get("stock_code") or item.get("stock_symbol") or "unknown"
        stock_name = item.get("stock_name") or stock_code
        success = item.get("success", False)
        recommendation = item.get("recommendation") or "未知"
        confidence_score = item.get("confidence_score") or 0
        risk_level = item.get("risk_level") or "中等"
        summary = (item.get("summary") or "").strip()
        key_points = item.get("key_points") or []

        markdown_lines.append(f"## {stock_code} {stock_name}")
        markdown_lines.append("")
        markdown_lines.append(f"- Status: {'success' if success else 'failed'}")
        markdown_lines.append(f"- Recommendation: {recommendation}")
        markdown_lines.append(f"- Confidence: {confidence_score}")
        markdown_lines.append(f"- Risk Level: {risk_level}")
        if summary:
            markdown_lines.append(f"- Summary: {summary}")
        if key_points:
            markdown_lines.append("- Key Points:")
            for point in key_points[:5]:
                markdown_lines.append(f"  - {point}")
        markdown_lines.append("")

        export_payload.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "success": success,
            "recommendation": recommendation,
            "confidence_score": confidence_score,
            "risk_level": risk_level,
            "summary": summary,
            "key_points": key_points,
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    markdown_content = "\n".join(markdown_lines).encode("utf-8")
    json_content = json.dumps(export_payload, ensure_ascii=False, indent=2).encode("utf-8")

    return [
        (f"scheduled_analysis_{timestamp}.md", markdown_content, "text/markdown"),
        (f"scheduled_analysis_{timestamp}.json", json_content, "application/json"),
    ]


def _format_completed_task_result(task_id: str, task_doc: Dict[str, Any]) -> Dict[str, Any]:
    """将任务结果统一转换为邮件所需格式。"""
    result = task_doc.get("result") or {}
    task_params = task_doc.get("task_params") or {}
    stock_code = task_params.get("stock_code") or task_params.get("symbol") or result.get("stock_code") or result.get("stock_symbol") or ""

    return {
        "task_id": task_id,
        "stock_code": stock_code,
        "stock_name": result.get("stock_name") or stock_code,
        "summary": result.get("summary", ""),
        "recommendation": result.get("recommendation", ""),
        "confidence_score": result.get("confidence_score", 0),
        "risk_level": result.get("risk_level", "中等"),
        "key_points": result.get("key_points", []),
        "success": task_doc.get("status") == "completed",
    }


async def _wait_for_task_results(task_ids: List[str], timeout_seconds: int = 3600, poll_interval: int = 15) -> List[Dict[str, Any]]:
    """等待批次任务结束，并收集可用于邮件汇总的结果。"""
    if not task_ids:
        return []

    db = get_mongo_db()
    pending_ids = set(task_ids)
    completed_results: Dict[str, Dict[str, Any]] = {}
    started_at = datetime.now()

    while pending_ids and (datetime.now() - started_at).total_seconds() < timeout_seconds:
        cursor = db.unified_analysis_tasks.find(
            {"task_id": {"$in": list(pending_ids)}},
            {"task_id": 1, "status": 1, "result": 1, "task_params": 1}
        )
        docs = await cursor.to_list(length=len(pending_ids))

        for doc in docs:
            task_id = doc.get("task_id")
            if not task_id:
                continue

            status = doc.get("status")
            if status in {"completed", "failed", "cancelled"}:
                completed_results[task_id] = _format_completed_task_result(task_id, doc)
                pending_ids.discard(task_id)

        if pending_ids:
            await asyncio.sleep(poll_interval)

    if pending_ids:
        logger.warning(f"⚠️ 定时分析邮件等待超时，仍有 {len(pending_ids)} 个任务未完成")

    return [completed_results[task_id] for task_id in task_ids if task_id in completed_results]


async def _send_scheduled_completion_email_when_ready(
    user_id: str,
    task_ids: List[str],
    total: int,
    analysis_time: str,
) -> None:
    """等待任务结束后发送带附件的定时分析完成邮件。"""
    try:
        results = await _wait_for_task_results(task_ids)
        success = sum(1 for item in results if item.get("success"))
        failed = max(total - success, 0)
        await send_completion_notification(
            user_id=user_id,
            total=total,
            success=success,
            failed=failed,
            results=results,
            analysis_time=analysis_time,
            send_in_app_notification=True,
            send_email_notification=True,
        )
    except Exception as exc:
        logger.warning(f"⚠️ 发送定时分析完成邮件失败: {exc}", exc_info=True)


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
    submitted_task_ids = []
    submitted_count = 0
    failed_count = 0

    # 第一步：为所有股票创建任务（使用 v2.0 引擎）
    logger.info(f"  📝 [v2.0引擎] 开始创建 {len(stocks)} 个分析任务...")
    for idx, stock in enumerate(stocks, 1):
        stock_code = stock.get("stock_code")
        stock_name = stock.get("stock_name", stock_code)

        try:
            # 🔥 修复：根据股票代码自动识别市场类型
            from tradingagents.utils.stock_utils import StockUtils, StockMarket

            market = StockUtils.identify_stock_market(stock_code)
            market_type_mapping = {
                StockMarket.CHINA_A: "cn",
                StockMarket.HONG_KONG: "hk",
                StockMarket.US: "us",
                StockMarket.UNKNOWN: "cn"
            }
            market_type = market_type_mapping.get(market, "cn")

            logger.info(f"    📊 股票 {stock_code} 识别为市场: {market_type}")

            # 准备任务参数
            task_params = {
                "symbol": stock_code,
                "stock_code": stock_code,
                "market_type": market_type,  # 🔑 根据股票代码自动识别市场类型
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

    # 第二步：将任务提交到队列，由 Worker 统一管理并发
    if task_ids:
        logger.info(f"  🚀 [v2.0引擎] 开始提交 {len(task_ids)} 个分析任务到队列...")
        
        from app.services.queue_service import get_queue_service
        queue_service = get_queue_service()
        
        # 生成批次ID（用于定时分析批次）
        batch_id = str(uuid.uuid4())
        
        for item in task_mapping:
            if item.get("task_id"):
                task_id = item["task_id"]
                stock_code = item["stock_code"]
                
                # 准备队列参数
                queue_params = {
                    "task_id": task_id,
                    "symbol": stock_code,
                    "stock_code": stock_code,
                    "user_id": user_id,
                    "batch_id": batch_id,
                    "engine": "v2",  # v2 引擎
                    "analysis_date": analysis_date,
                    "research_depth": depth_mapping.get(analysis_depth, "标准"),
                    "quick_analysis_model": quick_analysis_model,
                    "deep_analysis_model": deep_analysis_model
                }
                
                try:
                    # 提交任务到队列（会自动检查并发限制）
                    await queue_service.enqueue_task(
                        user_id=user_id,
                        symbol=stock_code,
                        params=queue_params,
                        batch_id=batch_id,
                        task_id=task_id  # 使用已创建的任务ID
                    )
                    submitted_count += 1
                    submitted_task_ids.append(task_id)
                    logger.info(f"    ✅ [v2.0引擎] 任务已入队: {task_id} - {stock_code}")
                except ValueError as e:
                    # 并发限制错误
                    failed_count += 1
                    logger.warning(f"    ⚠️ [v2.0引擎] 任务入队失败（并发限制）: {task_id} - {stock_code}, 错误: {e}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"    ❌ [v2.0引擎] 任务入队失败: {task_id} - {stock_code}, 错误: {e}", exc_info=True)
        
        logger.info(f"  ✅ 已提交 {submitted_count} 个任务到队列，失败 {failed_count} 个")

    return {
        "total": len(stocks),
        "created": submitted_count,
        "failed": len(stocks) - submitted_count,
        "task_ids": submitted_task_ids,
        "task_mapping": task_mapping
    }


async def send_completion_notification(
    user_id: str,
    total: int,
    success: int,
    failed: int,
    results: List[Dict[str, Any]],
    analysis_time: Optional[str] = None,
    send_in_app_notification: bool = True,
    send_email_notification: bool = True,
):
    """发送分析完成通知"""
    notifications_service = NotificationsService()
    has_detailed_results = bool(results)
    analysis_time = analysis_time or datetime.now().strftime("%Y-%m-%d %H:%M")

    if has_detailed_results:
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
    else:
        severity = "info" if success > 0 else "error"
        title = "自选股定时分析已启动"
        content = f"已提交 {success}/{total} 只股票的分析任务"
        if failed > 0:
            content += f"，{failed} 只提交失败"

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
            "analysis_date": analysis_time,
            "has_detailed_results": has_detailed_results,
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

    if send_in_app_notification:
        try:
            await notifications_service.create_and_publish(notification)
            logger.info(f"📬 已发送分析通知给用户 {user_id}")
        except Exception as e:
            logger.error(f"❌ 发送通知失败: {e}")

    # 发送邮件通知（如果用户启用了邮件通知）
    if not send_email_notification or not has_detailed_results:
        return

    try:
        from app.services.email_service import get_email_service
        from app.models.email import EmailType
        email_service = get_email_service()

        # 统计推荐结果
        buy_count = sum(1 for r in results if r.get("recommendation") == "买入")
        hold_count = sum(1 for r in results if r.get("recommendation") == "持有")
        sell_count = sum(1 for r in results if r.get("recommendation") == "卖出")

        attachments = _build_scheduled_email_attachments(results, analysis_time)

        await email_service.send_analysis_email(
            user_id=user_id,
            email_type=EmailType.SCHEDULED_ANALYSIS,  # 🔥 修复：使用枚举而不是字符串
            template_name="scheduled_report",
            template_data={
                "task_name": "自选股定时分析",
                "analysis_date": analysis_time,
                "total_count": total,
                "success_count": success,
                "failed_count": failed,
                "buy_count": buy_count,
                "hold_count": hold_count,
                "sell_count": sell_count,
                "stocks": results[:10],  # 只发送前10只股票的详情
                "detail_url": "/analysis/history"
            },
            reference_id=f"scheduled_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            attachments=attachments,
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
        # 🔥 获取系统默认模型配置（从数据库）
        system_default_models = await get_system_default_models()
        default_quick_model = system_default_models.get("quick_analysis_model", "qwen-plus")
        default_deep_model = system_default_models.get("deep_analysis_model", "qwen-max")
        
        logger.info(f"📋 系统默认模型配置: 快速={default_quick_model}, 深度={default_deep_model}")
        
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

            # 使用批量分析方法（并发执行），使用系统默认模型
            batch_result = await analyze_user_watchlist_batch(
                user_id=user_id,
                stocks=stocks,
                analysis_date=analysis_date,
                quick_analysis_model=default_quick_model,
                deep_analysis_model=default_deep_model
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
                results=[],
                analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                send_in_app_notification=True,
                send_email_notification=False,
            )

            if batch_result.get("task_ids"):
                asyncio.create_task(
                    _send_scheduled_completion_email_when_ready(
                        user_id=user_id,
                        task_ids=batch_result["task_ids"],
                        total=user_total,
                        analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                    )
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


async def get_system_default_models() -> Dict[str, str]:
    """
    从数据库获取系统默认的分析模型配置
    
    Returns:
        包含 quick_analysis_model 和 deep_analysis_model 的字典
    """
    try:
        db = get_mongo_db()
        # 获取活动的系统配置
        system_config = await db.system_configs.find_one(
            {"is_active": True},
            sort=[("version", -1)]
        )
        
        if system_config and "system_settings" in system_config:
            system_settings = system_config["system_settings"]
            return {
                "quick_analysis_model": system_settings.get("quick_analysis_model", "qwen-plus"),
                "deep_analysis_model": system_settings.get("deep_analysis_model", "qwen-max")
            }
    except Exception as e:
        logger.warning(f"⚠️ 获取系统默认模型配置失败: {e}，使用代码默认值")
    
    # 如果获取失败，返回代码默认值
    return {
        "quick_analysis_model": "qwen-plus",
        "deep_analysis_model": "qwen-max"
    }


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
        # 🔥 获取系统默认模型配置（从数据库）
        system_default_models = await get_system_default_models()
        logger.info(f"📋 系统默认模型配置: 快速={system_default_models.get('quick_analysis_model', 'qwen-plus')}, 深度={system_default_models.get('deep_analysis_model', 'qwen-max')}")
        
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
            # 🔥 确定分析模型：直接使用系统默认值（前端界面没有配置这些字段的地方）
            quick_model = system_default_models.get("quick_analysis_model", "qwen-plus")
            deep_model = system_default_models.get("deep_analysis_model", "qwen-max")

            logger.info(f"     分析深度: {analysis_depth}")
            logger.info(f"     快速模型: {quick_model} (系统默认值)")
            logger.info(f"     深度模型: {deep_model} (系统默认值)")

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
            results=[],
            analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            send_in_app_notification=True,
            send_email_notification=False,
        )

        if all_task_ids:
            asyncio.create_task(
                _send_scheduled_completion_email_when_ready(
                    user_id=user_id,
                    task_ids=all_task_ids,
                    total=total_stocks,
                    analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                )
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

