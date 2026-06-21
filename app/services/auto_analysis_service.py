"""
收盘自动分析服务
在交易日20:00自动为启用了自动分析的自选股执行分析任务
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from app.core.database import get_mongo_db
from app.services.favorites_service import favorites_service
from app.services.simple_analysis_service import get_simple_analysis_service
from app.models.analysis import SingleAnalysisRequest, AnalysisParameters

logger = logging.getLogger("webapi")


class AutoAnalysisService:
    """收盘自动分析服务"""

    async def run_daily_auto_analysis(self):
        """每日收盘自动分析入口（工作日20:00调用）"""
        weekday = datetime.now().weekday()  # 0=Monday, 6=Sunday
        if weekday >= 5:
            logger.info("今日为周末，跳过自动分析")
            return

        logger.info("=" * 60)
        logger.info("开始执行收盘自动分析任务...")
        logger.info("=" * 60)

        # 获取所有启用自动分析的自选股
        auto_favorites = await favorites_service.get_auto_analyze_favorites()
        if not auto_favorites:
            logger.info("没有启用自动分析的自选股，跳过")
            return

        logger.info(f"共找到 {len(auto_favorites)} 只启用自动分析的自选股")

        # 按用户分组
        by_user: Dict[str, List[Dict[str, Any]]] = {}
        for fav in auto_favorites:
            uid = fav["user_id"]
            by_user.setdefault(uid, []).append(fav)

        # 串行逐个执行，避免并发压力
        total_success = 0
        total_skip = 0
        total_fail = 0

        for user_id, stocks in by_user.items():
            logger.info(f"开始处理用户 {user_id} 的 {len(stocks)} 只股票")
            for stock in stocks:
                try:
                    result = await self._analyze_stock(
                        user_id,
                        stock["stock_code"],
                        stock.get("market", "A股")
                    )
                    if result.get("success"):
                        total_success += 1
                    elif result.get("skipped"):
                        total_skip += 1
                    else:
                        total_fail += 1
                except Exception as e:
                    total_fail += 1
                    logger.error(f"自动分析异常: {stock.get('stock_code')}，错误: {e}")

        logger.info("=" * 60)
        logger.info(f"收盘自动分析完成: 成功={total_success}, 跳过={total_skip}, 失败={total_fail}")
        logger.info("=" * 60)

    async def _analyze_stock(
        self,
        user_id: str,
        stock_code: str,
        market: str = "A股"
    ) -> Dict[str, Any]:
        """为指定用户和股票执行自动分析"""
        try:
            # 防重复：检查是否已有正在进行中的分析任务
            if await self._has_running_task(user_id, stock_code):
                logger.info(f"跳过 {stock_code}（用户 {user_id}）：已有运行中的分析任务")
                return {"success": False, "skipped": True, "reason": "running_task_exists"}

            service = get_simple_analysis_service()
            params = AnalysisParameters(
                market_type=market,
                research_depth="全面",
                selected_analysts=["market", "fundamentals", "news", "social"],
            )
            request = SingleAnalysisRequest(
                symbol=stock_code,
                parameters=params,
            )

            # 创建任务记录
            result = await service.create_analysis_task(user_id, request)
            task_id = result["task_id"]
            logger.info(f"已为 {stock_code}（用户 {user_id}）创建分析任务: {task_id}")

            # 执行分析
            await service.execute_analysis_background(task_id, user_id, request)

            logger.info(f"自动分析完成: {stock_code}（用户 {user_id}），任务ID: {task_id}")
            return {"success": True, "task_id": task_id, "stock_code": stock_code}

        except Exception as e:
            logger.error(
                f"自动分析失败: {stock_code}（用户 {user_id}），错误: {e}",
                exc_info=True
            )
            return {"success": False, "error": str(e), "stock_code": stock_code}

    async def _has_running_task(self, user_id: str, stock_code: str) -> bool:
        """检查用户是否已有该股票的运行中任务（pending/processing）"""
        db = get_mongo_db()
        task = await db.analysis_tasks.find_one(
            {
                "user_id": user_id,
                "stock_code": stock_code,
                "status": {"$in": ["pending", "processing"]},
            },
            sort=[("created_at", -1)]
        )
        return task is not None


# 全局单例
_auto_analysis_service: AutoAnalysisService | None = None


def get_auto_analysis_service() -> AutoAnalysisService:
    global _auto_analysis_service
    if _auto_analysis_service is None:
        _auto_analysis_service = AutoAnalysisService()
    return _auto_analysis_service
