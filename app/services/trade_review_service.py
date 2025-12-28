"""
交易复盘服务
提供交易复盘和阶段性复盘功能
"""

import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from bson import ObjectId

from app.core.database import get_mongo_db

# ==================== 特性开关 ====================
# 是否使用模板系统生成提示词（默认关闭，保持向后兼容）
# 注意：使用函数动态读取，确保 .env 文件已加载
def _use_template_prompts() -> bool:
    """动态读取 USE_TEMPLATE_PROMPTS 环境变量"""
    value = os.getenv("USE_TEMPLATE_PROMPTS", "false").lower() == "true"
    # 首次调用时打印日志
    if not hasattr(_use_template_prompts, '_logged'):
        _use_template_prompts._logged = True
        logging.getLogger("app.services.trade_review").info(
            f"📋 [特性开关] USE_TEMPLATE_PROMPTS = {value}"
        )
    return value

def _use_workflow_review() -> bool:
    """动态读取 USE_STOCK_ENGINE 环境变量（复用持仓分析的引擎开关）

    当 USE_STOCK_ENGINE=true 时，交易复盘也会使用工作流引擎进行多维度分析
    """
    value = os.getenv("USE_STOCK_ENGINE", "false").lower() == "true"
    if not hasattr(_use_workflow_review, '_logged'):
        _use_workflow_review._logged = True
        logging.getLogger("app.services.trade_review").info(
            f"📋 [特性开关] USE_STOCK_ENGINE (复盘工作流) = {value}"
        )
    return value

from app.models.review import (
    ReviewType, ReviewStatus, PeriodType,
    TradeRecord, TradeInfo, MarketSnapshot,
    AITradeReview, TradeReviewReport,
    TradingStatistics, AIPeriodicReview, TradeSummaryItem, PeriodicReviewReport,
    CreateTradeReviewRequest, CreatePeriodicReviewRequest,
    TradeReviewResponse, PeriodicReviewResponse, ReviewListItem
)
from app.utils.timezone import now_tz

# ==================== v2.0 工具导入 ====================
# 导入交易复盘工具集
try:
    from core.tools.implementations.trade_review import (
        get_trade_records as tool_get_trade_records,
        build_trade_info as tool_build_trade_info,
        get_account_info as tool_get_account_info,
        get_market_snapshot_for_review as tool_get_market_snapshot
    )
    TOOLS_AVAILABLE = True
except ImportError:
    logger = logging.getLogger("app.services.trade_review")
    logger.warning("⚠️ v2.0 交易复盘工具未加载，将使用传统方法")
    TOOLS_AVAILABLE = False

# 导入统一数据源工具
from tradingagents.utils.stock_utils import StockUtils
from tradingagents.dataflows.providers.hk.improved_hk import get_improved_hk_provider
from tradingagents.dataflows.providers.us.optimized import get_optimized_us_data_provider

logger = logging.getLogger("app.services.trade_review")


class TradeReviewService:
    """交易复盘服务"""

    def __init__(self):
        self.db = get_mongo_db()
        self.trade_reviews_collection = "trade_reviews"
        self.periodic_reviews_collection = "periodic_reviews"
        self.paper_trades_collection = "paper_trades"
        self.trading_systems_collection = "trading_systems"

    # ==================== 辅助方法 ====================

    async def _get_current_price(self, code: str) -> Optional[float]:
        """获取股票当前价格

        Args:
            code: 股票代码

        Returns:
            当前价格，如果获取失败则返回 None
        """
        try:
            from app.services.quotes_service import QuotesService

            quotes_service = QuotesService(ttl_seconds=30)
            quotes = await quotes_service.get_quotes([code])

            if code in quotes and quotes[code]:
                current_price = quotes[code].get('close')
                if current_price:
                    logger.info(f"✅ [获取当前价格] {code}: {current_price}")
                    return float(current_price)

            logger.warning(f"⚠️ [获取当前价格] 未找到 {code} 的行情数据")
            return None
        except Exception as e:
            logger.warning(f"❌ [获取当前价格] 获取失败: {e}")
            return None

    async def _calculate_unrealized_pnl(self, trade_info: TradeInfo) -> TradeInfo:
        """计算浮动盈亏（持仓中的交易）

        Args:
            trade_info: 交易信息

        Returns:
            更新后的交易信息（包含浮动盈亏）
        """
        if not trade_info.is_holding or trade_info.remaining_quantity <= 0:
            return trade_info

        # 获取当前价格
        current_price = await self._get_current_price(trade_info.code)
        if not current_price:
            logger.warning(f"⚠️ [计算浮动盈亏] 无法获取当前价格，跳过浮动盈亏计算")
            return trade_info

        # 计算浮动盈亏
        unrealized_pnl = (current_price - trade_info.avg_buy_price) * trade_info.remaining_quantity
        cost_basis = trade_info.avg_buy_price * trade_info.remaining_quantity
        unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0

        # 更新 trade_info
        trade_info.current_price = current_price
        trade_info.unrealized_pnl = round(unrealized_pnl, 2)
        trade_info.unrealized_pnl_pct = round(unrealized_pnl_pct, 2)

        logger.info(f"✅ [计算浮动盈亏] {trade_info.code}:")
        logger.info(f"   - 当前价格: {current_price}")
        logger.info(f"   - 成本价: {trade_info.avg_buy_price}")
        logger.info(f"   - 持仓数量: {trade_info.remaining_quantity}")
        logger.info(f"   - 浮动盈亏: {unrealized_pnl:.2f} 元 ({unrealized_pnl_pct:.2f}%)")

        return trade_info

    async def _get_trading_system(self, user_id: str, trading_system_id: str) -> Optional[Dict[str, Any]]:
        """获取交易计划信息"""
        try:
            from bson import ObjectId
            logger.info(f"📋 [获取交易计划] user_id={user_id}, trading_system_id={trading_system_id}")

            system = await self.db[self.trading_systems_collection].find_one({
                "_id": ObjectId(trading_system_id),
                "user_id": user_id
            })

            if system:
                logger.info(f"✅ [获取交易计划] 成功获取: {system.get('name', 'N/A')}")
                logger.info(f"   - 风格: {system.get('style', 'N/A')}")
                logger.info(f"   - 选股规则: {len(system.get('stock_selection', {}).get('must_have', []))} 条必须满足")
                logger.info(f"   - 择时规则: {len(system.get('timing', {}).get('entry_signals', []))} 条入场信号")
                logger.info(f"   - 纪律规则: {len(system.get('discipline', {}).get('must_do', []))} 条必须做到")
            else:
                logger.warning(f"⚠️ [获取交易计划] 未找到交易计划: {trading_system_id}")

            return system
        except Exception as e:
            logger.warning(f"❌ [获取交易计划] 获取失败: {e}")
            return None

    # ==================== 交易复盘 ====================

    async def create_trade_review(
        self,
        user_id: str,
        request: CreateTradeReviewRequest
    ) -> TradeReviewResponse:
        """创建交易复盘"""
        review_id = str(uuid.uuid4())

        # 1. 获取交易记录
        trade_records = await self._get_trade_records(user_id, request.trade_ids, request.source)
        if not trade_records:
            raise ValueError("未找到指定的交易记录")

        # 2. 构建交易信息
        trade_info = self._build_trade_info(trade_records, request.code)

        # 🆕 2.5. 如果是持仓中的交易，计算浮动盈亏
        if trade_info.is_holding:
            logger.info(f"📊 [创建复盘] 检测到持仓中交易，计算浮动盈亏...")
            trade_info = await self._calculate_unrealized_pnl(trade_info)

        # 3. 获取交易计划信息（如果关联了交易计划）
        trading_system_name = None
        if request.trading_system_id:
            trading_system = await self._get_trading_system(user_id, request.trading_system_id)
            if trading_system:
                trading_system_name = trading_system.get("name")

        # 4. 创建复盘报告
        # 统一 source 字段：real -> position, paper -> paper
        source = request.source or "paper"
        if source == "real":
            source = "position"  # 统一使用 position 表示持仓操作

        report = TradeReviewReport(
            review_id=review_id,
            user_id=user_id,
            review_type=request.review_type,
            trade_info=trade_info,
            source=source,  # 设置数据源
            trading_system_id=request.trading_system_id,
            trading_system_name=trading_system_name,
            status=ReviewStatus.PROCESSING
        )
        
        # 4. 保存初始报告
        report_dict = report.model_dump(by_alias=True, exclude={"id"})
        await self.db[self.trade_reviews_collection].insert_one(report_dict)
        
        try:
            start_time = datetime.now()
            
            # 5. 获取市场数据快照
            market_snapshot = await self._get_market_snapshot(
                code=trade_info.code,
                market=trade_info.market,
                first_buy_date=trade_info.first_buy_date,
                last_sell_date=trade_info.last_sell_date
            )
            
            # 6. 获取交易计划信息（如果关联了交易计划）
            trading_system = None
            if request.trading_system_id:
                trading_system = await self._get_trading_system(user_id, request.trading_system_id)

            # 7. 调用AI分析（传入 user_id、交易计划和分析版本）
            ai_review = await self._call_ai_trade_review(
                trade_info,
                market_snapshot,
                user_id=user_id,
                trading_system=trading_system,
                use_workflow=request.use_workflow
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()

            # 🔍 详细日志：检查 ai_review 对象
            logger.info(f"🔍 [创建复盘] ai_review 类型: {type(ai_review)}")
            logger.info(f"🔍 [创建复盘] ai_review.plan_adherence: {ai_review.plan_adherence}")
            logger.info(f"🔍 [创建复盘] ai_review.plan_deviation: {ai_review.plan_deviation}")

            ai_review_dict = ai_review.model_dump()
            logger.info(f"🔍 [创建复盘] ai_review_dict 键: {list(ai_review_dict.keys())}")
            logger.info(f"🔍 [创建复盘] ai_review_dict['plan_adherence']: {ai_review_dict.get('plan_adherence')}")
            logger.info(f"🔍 [创建复盘] ai_review_dict['plan_deviation']: {ai_review_dict.get('plan_deviation')}")

            # 8. 更新报告
            await self.db[self.trade_reviews_collection].update_one(
                {"review_id": review_id},
                {"$set": {
                    "market_snapshot": market_snapshot.model_dump(),
                    "ai_review": ai_review.model_dump(),
                    "status": ReviewStatus.COMPLETED.value,
                    "execution_time": execution_time
                }}
            )

            logger.info(f"✅ 交易复盘完成: {review_id}, 股票: {trade_info.code}")

            # 🔍 详细日志：检查返回的 TradeReviewResponse
            response = TradeReviewResponse(
                review_id=review_id,
                status=ReviewStatus.COMPLETED,
                trade_info=trade_info,
                ai_review=ai_review,
                market_snapshot=market_snapshot,
                execution_time=execution_time,
                created_at=report.created_at
            )

            logger.info(f"🔍 [创建复盘] response.ai_review 类型: {type(response.ai_review)}")
            logger.info(f"🔍 [创建复盘] response.ai_review.plan_adherence: {response.ai_review.plan_adherence}")
            logger.info(f"🔍 [创建复盘] response.ai_review.plan_deviation: {response.ai_review.plan_deviation}")

            return response
            
        except Exception as e:
            logger.error(f"❌ 交易复盘失败: {e}", exc_info=True)
            await self.db[self.trade_reviews_collection].update_one(
                {"review_id": review_id},
                {"$set": {
                    "status": ReviewStatus.FAILED.value,
                    "error_message": str(e)
                }}
            )
            return TradeReviewResponse(
                review_id=review_id,
                status=ReviewStatus.FAILED,
                trade_info=trade_info,
                created_at=report.created_at
            )

    async def create_trade_review_v2(
        self,
        user_id: str,
        request: CreateTradeReviewRequest
    ) -> TradeReviewResponse:
        """创建交易复盘 v2.0 - 使用统一任务引擎

        优势:
        - 支持多引擎切换（workflow/legacy/llm）
        - 统一的任务管理和进度跟踪
        - 自动选择最佳引擎
        - 任务可查询、可取消

        Args:
            user_id: 用户ID
            request: 复盘请求

        Returns:
            复盘报告响应
        """
        from app.services.task_analysis_service import get_task_analysis_service
        from app.models.analysis import AnalysisTaskType
        from app.models.user import PyObjectId

        review_id = str(uuid.uuid4())

        logger.info(f"🚀 [交易复盘v2.0] 使用统一任务引擎创建复盘: {review_id}")

        # 1. 获取交易记录
        trade_records = await self._get_trade_records(user_id, request.trade_ids, request.source)
        if not trade_records:
            raise ValueError("未找到指定的交易记录")

        # 2. 构建交易信息
        trade_info = self._build_trade_info(trade_records, request.code)

        # 2.5. 如果是持仓中的交易，计算浮动盈亏
        if trade_info.is_holding:
            logger.info(f"📊 [复盘v2.0] 检测到持仓中交易，计算浮动盈亏...")
            trade_info = await self._calculate_unrealized_pnl(trade_info)

        # 3. 获取交易计划信息
        trading_system_name = None
        trading_system = None
        if request.trading_system_id:
            trading_system = await self._get_trading_system(user_id, request.trading_system_id)
            if trading_system:
                trading_system_name = trading_system.get("name")

        # 4. 统一 source 字段
        source = request.source or "paper"
        if source == "real":
            source = "position"

        # 5. 创建初始报告
        report = TradeReviewReport(
            review_id=review_id,
            user_id=user_id,
            review_type=request.review_type,
            trade_info=trade_info,
            source=source,
            trading_system_id=request.trading_system_id,
            trading_system_name=trading_system_name,
            status=ReviewStatus.PROCESSING
        )

        # 保存初始报告
        report_dict = report.model_dump(by_alias=True, exclude={"id"})
        await self.db[self.trade_reviews_collection].insert_one(report_dict)

        try:
            # 6. 获取市场数据快照
            market_snapshot = await self._get_market_snapshot(
                code=trade_info.code,
                market=trade_info.market,
                first_buy_date=trade_info.first_buy_date,
                last_sell_date=trade_info.last_sell_date
            )

            # 7. 准备任务参数
            task_params = {
                "review_id": review_id,
                "code": trade_info.code,
                "market": trade_info.market,
                "trade_info": trade_info.model_dump(),
                "market_snapshot": market_snapshot.model_dump(),
                "trading_system": trading_system,
                "review_type": request.review_type
            }

            # 8. 使用统一任务引擎
            task_service = get_task_analysis_service()

            # 获取引擎类型和偏好
            engine_type = "workflow" if request.use_workflow else "auto"
            preference_type = getattr(request, "preference_type", "neutral")

            # 创建并执行任务
            task = await task_service.create_and_execute_task(
                user_id=PyObjectId(user_id),
                task_type=AnalysisTaskType.TRADE_REVIEW,
                task_params=task_params,
                engine_type=engine_type,
                preference_type=preference_type
            )

            # 9. 从任务结果中提取 AI 复盘
            if task.result and "ai_review" in task.result:
                ai_review = AITradeReview(**task.result["ai_review"])
            else:
                raise ValueError("任务结果中缺少 ai_review 数据")

            # 10. 更新报告
            await self.db[self.trade_reviews_collection].update_one(
                {"review_id": review_id},
                {"$set": {
                    "market_snapshot": market_snapshot.model_dump(),
                    "ai_review": ai_review.model_dump(),
                    "status": ReviewStatus.COMPLETED.value,
                    "execution_time": task.execution_time
                }}
            )

            logger.info(f"✅ [交易复盘v2.0] 复盘完成: {review_id}, 任务ID: {task.task_id}")

            # 11. 返回响应
            return TradeReviewResponse(
                review_id=review_id,
                status=ReviewStatus.COMPLETED,
                trade_info=trade_info,
                ai_review=ai_review,
                market_snapshot=market_snapshot,
                execution_time=task.execution_time,
                created_at=report.created_at
            )

        except Exception as e:
            logger.error(f"❌ [交易复盘v2.0] 复盘失败: {e}", exc_info=True)

            # 更新报告状态为失败
            await self.db[self.trade_reviews_collection].update_one(
                {"review_id": review_id},
                {"$set": {
                    "status": ReviewStatus.FAILED.value,
                    "error_message": str(e)
                }}
            )

            return TradeReviewResponse(
                review_id=review_id,
                status=ReviewStatus.FAILED,
                trade_info=trade_info,
                created_at=report.created_at
            )

    async def _get_trade_records(
        self,
        user_id: str,
        trade_ids: List[str],
        source: str = "paper"
    ) -> List[Dict[str, Any]]:
        """获取交易记录

        Args:
            user_id: 用户ID
            trade_ids: 交易ID列表
            source: 数据源 (real=真实持仓, paper=模拟持仓)
        """
        # 交易记录使用 ObjectId 作为 _id
        object_ids = []
        for tid in trade_ids:
            try:
                object_ids.append(ObjectId(tid))
            except Exception:
                logger.warning(f"无效的交易ID: {tid}")

        if not object_ids:
            return []

        # 根据 source 选择集合
        if source == "real":
            # 真实持仓：从 position_changes 获取并转换
            collection = "position_changes"
            logger.info(f"📊 从 position_changes 获取交易记录: {len(object_ids)} 条")
        else:
            # 模拟持仓：从 paper_trades 获取
            collection = self.paper_trades_collection
            logger.info(f"📊 从 paper_trades 获取交易记录: {len(object_ids)} 条")

        cursor = self.db[collection].find({
            "user_id": user_id,
            "_id": {"$in": object_ids}
        })
        records = await cursor.to_list(None)

        # 如果是真实持仓，需要转换格式
        if source == "real":
            converted_records = []
            for c in records:
                change_type = c.get("change_type")
                side = "buy" if change_type in ["buy", "add"] else "sell"
                quantity = abs(c.get("quantity_change", 0))
                price = c.get("trade_price") or c.get("cost_price_after", 0)

                # 处理 pnl：确保是数字
                pnl = c.get("realized_profit")
                if pnl is None:
                    pnl = 0.0

                # 处理 timestamp：转换为 ISO 格式字符串
                created_at = c.get("created_at")
                timestamp_str = created_at.isoformat() if created_at else ""

                # 处理 timestamp：优先使用 trade_time（实际交易时间），其次使用 created_at（记录创建时间）
                trade_time = c.get("trade_time")
                created_at = c.get("created_at")

                # 优先使用 trade_time，如果没有则使用 created_at
                if trade_time:
                    timestamp_str = trade_time.isoformat() if trade_time else ""
                else:
                    timestamp_str = created_at.isoformat() if created_at else ""

                converted_records.append({
                    "_id": c.get("_id"),
                    "code": c.get("code"),
                    "name": c.get("name"),  # 添加股票名称
                    "market": c.get("market", "CN"),
                    "side": side,
                    "quantity": quantity,
                    "price": float(price) if price else 0.0,
                    "amount": float(quantity * price) if price else 0.0,
                    "pnl": float(pnl),
                    "commission": 0.0,
                    "timestamp": timestamp_str  # ISO 格式字符串（使用交易时间）
                })
            return converted_records

        return records

    def _build_trade_info(
        self,
        trade_records: List[Dict[str, Any]],
        code: Optional[str] = None
    ) -> TradeInfo:
        """构建交易信息"""
        if not trade_records:
            return TradeInfo(code=code or "")

        # 打印输入的交易记录（调试用）
        logger.info(f"📊 [_build_trade_info] 收到 {len(trade_records)} 笔交易记录")
        for i, record in enumerate(trade_records):
            logger.info(f"  记录 {i+1}: side={record.get('side')}, qty={record.get('quantity')}, "
                       f"price={record.get('price')}, pnl={record.get('pnl')}, "
                       f"timestamp={record.get('timestamp')}")

        # 使用第一条记录的股票信息
        first_trade = trade_records[0]
        stock_code = code or first_trade.get("code", "")
        stock_name = first_trade.get("name") or first_trade.get("stock_name")  # 尝试从记录中获取股票名称
        market = first_trade.get("market", "CN")
        currency = first_trade.get("currency", "CNY")

        # 构建交易记录列表
        trades = []
        total_buy_qty = 0
        total_buy_amount = 0.0
        total_sell_qty = 0
        total_sell_amount = 0.0
        total_pnl = 0.0
        total_commission = 0.0

        timestamps = []

        for record in trade_records:
            trade = TradeRecord(
                trade_id=str(record.get("_id", "")),
                side=record.get("side", ""),
                quantity=record.get("quantity", 0),
                price=record.get("price", 0.0),
                amount=record.get("amount", 0.0),
                commission=record.get("commission", 0.0),
                timestamp=record.get("timestamp", ""),
                pnl=record.get("pnl", 0.0)
            )
            trades.append(trade)

            if trade.timestamp:
                timestamps.append(trade.timestamp)

            total_commission += trade.commission

            if trade.side == "buy":
                total_buy_qty += trade.quantity
                total_buy_amount += trade.amount
            else:
                total_sell_qty += trade.quantity
                total_sell_amount += trade.amount
                total_pnl += trade.pnl
                logger.info(f"  累加卖出 pnl: {trade.pnl}, 累计 total_pnl: {total_pnl}")

        # 计算平均价格
        avg_buy_price = total_buy_amount / total_buy_qty if total_buy_qty > 0 else 0.0
        avg_sell_price = total_sell_amount / total_sell_qty if total_sell_qty > 0 else 0.0

        # 计算盈亏百分比
        pnl_pct = (total_pnl / total_buy_amount * 100) if total_buy_amount > 0 else 0.0

        logger.info(f"📊 [_build_trade_info] 统计结果:")
        logger.info(f"  - total_buy_amount: {total_buy_amount}")
        logger.info(f"  - total_sell_amount: {total_sell_amount}")
        logger.info(f"  - total_pnl: {total_pnl}")
        logger.info(f"  - pnl_pct: {pnl_pct}%")

        # 计算持仓天数
        timestamps.sort()
        first_buy_date = timestamps[0] if timestamps else None
        last_sell_date = timestamps[-1] if timestamps else None
        holding_days = 0
        if first_buy_date and last_sell_date:
            try:
                first_dt = datetime.fromisoformat(first_buy_date.replace('Z', '+00:00').split('+')[0])
                last_dt = datetime.fromisoformat(last_sell_date.replace('Z', '+00:00').split('+')[0])
                holding_days = (last_dt - first_dt).days
            except Exception:
                pass

        # 🆕 计算持仓状态和浮动盈亏
        remaining_quantity = total_buy_qty - total_sell_qty
        is_holding = remaining_quantity > 0
        unrealized_pnl = 0.0
        unrealized_pnl_pct = 0.0
        current_price = None

        if is_holding:
            logger.info(f"📊 [_build_trade_info] 检测到持仓中: 剩余 {remaining_quantity} 股")
            # 获取当前价格（同步方法，需要在异步方法中调用）
            # 这里先标记为持仓中，实际价格在 create_trade_review 中异步获取

        logger.info(f"📊 [_build_trade_info] 持仓状态:")
        logger.info(f"  - is_holding: {is_holding}")
        logger.info(f"  - remaining_quantity: {remaining_quantity}")
        logger.info(f"  - realized_pnl: {total_pnl}")
        logger.info(f"  - unrealized_pnl: {unrealized_pnl} (待计算)")

        return TradeInfo(
            code=stock_code,
            name=stock_name,  # 添加股票名称
            market=market,
            currency=currency,
            trades=trades,
            total_buy_quantity=total_buy_qty,
            total_buy_amount=round(total_buy_amount, 2),
            avg_buy_price=round(avg_buy_price, 4),
            total_sell_quantity=total_sell_qty,
            total_sell_amount=round(total_sell_amount, 2),
            avg_sell_price=round(avg_sell_price, 4),
            realized_pnl=round(total_pnl, 2),
            realized_pnl_pct=round(pnl_pct, 2),
            unrealized_pnl=round(unrealized_pnl, 2),  # 🆕
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),  # 🆕
            total_commission=round(total_commission, 2),
            is_holding=is_holding,  # 🆕
            current_price=current_price,  # 🆕
            remaining_quantity=remaining_quantity,  # 🆕
            first_buy_date=first_buy_date,
            last_sell_date=last_sell_date,
            holding_days=holding_days
        )

    async def _build_trade_info_with_tools(
        self,
        trade_records: List[Dict[str, Any]],
        user_id: str,
        code: Optional[str] = None
    ) -> Dict[str, Any]:
        """使用 v2.0 工具构建完整的交易信息（包括账户信息）

        这个方法使用 v2.0 工具系统来获取数据，符合系统架构
        """
        if not TOOLS_AVAILABLE:
            logger.warning("⚠️ v2.0 工具不可用，使用传统方法")
            trade_info = self._build_trade_info(trade_records, code)
            return trade_info.model_dump()

        try:
            # 使用 v2.0 工具构建交易信息
            trade_info_result = tool_build_trade_info(trade_records, code)

            if not trade_info_result.get("success"):
                logger.warning(f"⚠️ 构建交易信息失败: {trade_info_result.get('error')}")
                trade_info = self._build_trade_info(trade_records, code)
                return trade_info.model_dump()

            trade_info_data = trade_info_result.get("data", {})

            # 使用 v2.0 工具获取账户信息
            account_result = await tool_get_account_info(user_id)

            if account_result.get("success"):
                account_info = account_result.get("data", {})
                trade_info_data["account_info"] = account_info
                logger.info(f"✅ 已添加账户信息到交易信息")
            else:
                logger.warning(f"⚠️ 获取账户信息失败: {account_result.get('error')}")

            return trade_info_data

        except Exception as e:
            logger.error(f"❌ 使用 v2.0 工具构建交易信息失败: {e}")
            trade_info = self._build_trade_info(trade_records, code)
            return trade_info.model_dump()

    async def _get_market_snapshot(
        self,
        code: str,
        market: str,
        first_buy_date: Optional[str],
        last_sell_date: Optional[str]
    ) -> MarketSnapshot:
        """获取市场数据快照"""
        snapshot = MarketSnapshot()

        if not first_buy_date:
            return snapshot

        try:
            # 解析日期
            start_date = datetime.fromisoformat(first_buy_date.replace('Z', '+00:00').split('+')[0])
            end_date = datetime.fromisoformat(last_sell_date.replace('Z', '+00:00').split('+')[0]) if last_sell_date else datetime.now()

            # 扩展日期范围（前后各10天）
            query_start = (start_date - timedelta(days=10)).strftime("%Y-%m-%d")
            query_end = (end_date + timedelta(days=10)).strftime("%Y-%m-%d")

            # 获取K线数据
            kline_data = await self._get_kline_data(code, market, query_start, query_end)

            if kline_data:
                snapshot.kline_data = kline_data

                # 查找持仓期间的最高最低价
                period_start = start_date.strftime("%Y-%m-%d")
                period_end = end_date.strftime("%Y-%m-%d")

                period_klines = [k for k in kline_data if period_start <= k.get("date", "") <= period_end]

                if period_klines:
                    # 找最高价
                    max_kline = max(period_klines, key=lambda x: x.get("high", 0))
                    snapshot.period_high = max_kline.get("high")
                    snapshot.period_high_date = max_kline.get("date")

                    # 找最低价
                    min_kline = min(period_klines, key=lambda x: x.get("low", float('inf')))
                    snapshot.period_low = min_kline.get("low")
                    snapshot.period_low_date = min_kline.get("date")

                    # 最优买卖点
                    snapshot.optimal_buy_price = snapshot.period_low
                    snapshot.optimal_sell_price = snapshot.period_high

                # 买入当日行情
                buy_date_str = start_date.strftime("%Y-%m-%d")
                buy_kline = next((k for k in kline_data if k.get("date") == buy_date_str), None)
                if buy_kline:
                    snapshot.buy_date_open = buy_kline.get("open")
                    snapshot.buy_date_high = buy_kline.get("high")
                    snapshot.buy_date_low = buy_kline.get("low")
                    snapshot.buy_date_close = buy_kline.get("close")

                # 卖出当日行情
                if last_sell_date:
                    sell_date_str = end_date.strftime("%Y-%m-%d")
                    sell_kline = next((k for k in kline_data if k.get("date") == sell_date_str), None)
                    if sell_kline:
                        snapshot.sell_date_open = sell_kline.get("open")
                        snapshot.sell_date_high = sell_kline.get("high")
                        snapshot.sell_date_low = sell_kline.get("low")
                        snapshot.sell_date_close = sell_kline.get("close")

        except Exception as e:
            logger.error(f"获取市场快照失败: {e}", exc_info=True)

        return snapshot

    async def _get_kline_data(
        self,
        code: str,
        market: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """获取K线数据"""
        try:
            # 从数据库获取历史K线
            cursor = self.db["stock_daily_history"].find({
                "code": code,
                "date": {"$gte": start_date, "$lte": end_date}
            }).sort("date", 1)

            klines = await cursor.to_list(None)

            if klines:
                return [
                    {
                        "date": k.get("date"),
                        "open": k.get("open"),
                        "high": k.get("high"),
                        "low": k.get("low"),
                        "close": k.get("close"),
                        "volume": k.get("volume")
                    }
                    for k in klines
                ]

            # 如果数据库没有，尝试使用统一接口获取
            logger.info(f"数据库无K线数据，尝试从统一接口获取: {code} ({market})")
            return await self._fetch_kline_unified(code, market, start_date, end_date)

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []

    async def _fetch_kline_unified(
        self,
        code: str,
        market: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """从统一接口获取K线数据（支持A股、港股、美股）"""
        try:
            # 自动识别市场
            market_info = StockUtils.get_market_info(code)
            is_hk = market_info['is_hk']
            is_us = market_info['is_us']
            is_china = market_info['is_china']
            
            logger.info(f"🔄 [统一K线获取] 股票: {code}, 市场识别: {market_info['market_name']}")

            df = None

            if is_hk:
                # 港股
                provider = get_improved_hk_provider()
                df = provider.get_daily_data(code, start_date, end_date)
            
            elif is_us:
                # 美股
                provider = get_optimized_us_data_provider()
                df = provider.get_daily_data(code, start_date, end_date)
                
            elif is_china or market == 'CN':
                # A股 (保持原有 akshare 逻辑)
                import akshare as ak
                start = start_date.replace("-", "")
                end = end_date.replace("-", "")
                
                # 尝试使用 akshare 获取
                try:
                    df_ak = ak.stock_zh_a_hist(
                        symbol=code,
                        period="daily",
                        start_date=start,
                        end_date=end,
                        adjust="qfq"
                    )
                    if df_ak is not None and not df_ak.empty:
                        # 统一列名
                        df = df_ak.rename(columns={
                            "日期": "date",
                            "开盘": "open",
                            "最高": "high",
                            "最低": "low",
                            "收盘": "close",
                            "成交量": "volume"
                        })
                        df['date'] = df['date'].astype(str)
                except Exception as e:
                    logger.error(f"akshare获取A股数据失败: {e}")
            
            # 处理返回的 DataFrame
            if df is not None and not df.empty:
                klines = []
                # 确保列名小写
                df.columns = [c.lower() for c in df.columns]
                
                for _, row in df.iterrows():
                    try:
                        kline = {
                            "date": str(row.get("date", "")),
                            "open": float(row.get("open", 0)),
                            "high": float(row.get("high", 0)),
                            "low": float(row.get("low", 0)),
                            "close": float(row.get("close", 0)),
                            "volume": float(row.get("volume", 0))
                        }
                        # 过滤无效日期
                        if len(kline["date"]) >= 10:
                            kline["date"] = kline["date"][:10]
                            klines.append(kline)
                    except Exception as row_e:
                        continue
                        
                logger.info(f"✅ [统一K线获取] 成功获取 {len(klines)} 条数据: {code}")
                return klines
                
        except Exception as e:
            logger.error(f"❌ [统一K线获取] 失败: {code} - {e}")

        return []

    async def _call_ai_trade_review(
        self,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot,
        user_id: Optional[str] = None,
        trading_system: Optional[Dict[str, Any]] = None,
        use_workflow: Optional[bool] = None
    ) -> AITradeReview:
        """调用AI进行交易复盘分析

        如果启用工作流引擎（USE_WORKFLOW_REVIEW=true 或 use_workflow=True），使用多Agent工作流分析
        否则使用单次LLM调用分析

        Args:
            trade_info: 交易信息
            market_snapshot: 市场快照
            user_id: 用户ID
            trading_system: 关联的交易计划（如果有）
            use_workflow: 是否使用工作流引擎。None表示使用环境变量设置
        """
        # 判断是否使用工作流引擎（请求参数优先于环境变量）
        should_use_workflow = use_workflow if use_workflow is not None else _use_workflow_review()

        if should_use_workflow:
            try:
                logger.info(f"🔄 [交易复盘] 使用工作流引擎进行多维度分析 (v2.0)")
                return await self._call_workflow_trade_review(
                    trade_info, market_snapshot, user_id, trading_system
                )
            except Exception as e:
                import traceback
                logger.warning(f"⚠️ [交易复盘] 工作流引擎执行失败，降级到单次LLM调用: {e}")
                logger.warning(f"⚠️ [交易复盘] 完整堆栈跟踪:\n{traceback.format_exc()}")
                # 降级到单次 LLM 调用

        logger.info(f"📝 [交易复盘] 使用传统分析方式 (v1.0)")

        try:
            # 如果启用模板系统，先获取大盘和行业基准数据
            benchmark_data = None
            if _use_template_prompts():
                try:
                    benchmark_data = await self._get_benchmark_data(
                        stock_code=trade_info.code,
                        market=trade_info.market,
                        start_date=trade_info.first_buy_date[:10] if trade_info.first_buy_date else "",
                        end_date=trade_info.last_sell_date[:10] if trade_info.last_sell_date else ""
                    )
                    logger.info(f"📊 [交易复盘] 获取基准数据完成")
                except Exception as e:
                    logger.warning(f"⚠️ [交易复盘] 获取基准数据失败: {e}")

            prompt = self._build_trade_review_prompt(
                trade_info, market_snapshot, user_id, benchmark_data, trading_system
            )

            # 使用统一的 LLM 适配器
            from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
            from tradingagents.graph.trading_graph import create_llm_by_provider

            model_name = "qwen-plus"
            provider_info = get_provider_and_url_by_model_sync(model_name)

            logger.info(f"🏭 [AI复盘] 模型供应商: {provider_info.get('provider', '未知')}")
            logger.info(f"🔗 [AI复盘] API地址: {provider_info.get('backend_url', '未配置')}")
            logger.info(f"🔑 [AI复盘] API Key: {'已配置' if provider_info.get('api_key') else '未配置'}")
            logger.info(f"📝 [AI复盘] Prompt长度: {len(prompt)} 字符")
            logger.info(f"📝 [AI复盘] Prompt前500字符:\n{prompt[:500]}")

            # 使用统一的 LLM 适配器创建实例
            logger.info(f"🔧 [AI复盘] 开始创建 LLM 实例...")
            llm = create_llm_by_provider(
                provider=provider_info.get("provider", "dashscope"),
                model=model_name,
                backend_url=provider_info.get("backend_url"),
                temperature=0.3,
                max_tokens=4000,
                timeout=120,
                api_key=provider_info.get("api_key")
            )
            logger.info(f"✅ [AI复盘] LLM 实例创建成功: {type(llm).__name__}")

            # 异步调用 LLM
            logger.info(f"🚀 [AI复盘] 开始调用 LLM API...")
            response = await llm.ainvoke(prompt)
            logger.info(f"✅ [AI复盘] LLM API 调用成功")
            logger.info(f"📦 [AI复盘] Response 类型: {type(response).__name__}")
            logger.info(f"📦 [AI复盘] Response 属性: {dir(response)}")

            content = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"📄 [AI复盘] 返回内容长度: {len(content)} 字符")
            logger.info(f"📄 [AI复盘] 返回内容前500字符:\n{content[:500]}")
            logger.info(f"📄 [AI复盘] 返回内容后500字符:\n{content[-500:]}")

            logger.info(f"🔍 [AI复盘] 开始解析 AI 响应...")
            result = self._parse_ai_trade_review(content, trade_info, market_snapshot)
            logger.info(f"✅ [AI复盘] 解析完成 - 总分: {result.overall_score}, 摘要长度: {len(result.summary)}")

            return result

        except Exception as e:
            logger.error(f"AI复盘分析失败: {e}", exc_info=True)
            return AITradeReview(
                summary=f"AI分析暂时不可用: {str(e)}",
                overall_score=50
            )



    def _build_trade_review_prompt(
        self,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot,
        user_id: Optional[str] = None,
        benchmark_data: Optional[Dict[str, Any]] = None,
        trading_system: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建交易复盘提示词

        支持模板系统（通过 USE_TEMPLATE_PROMPTS 特性开关控制）

        Args:
            trade_info: 交易信息
            market_snapshot: 市场快照
            user_id: 用户ID（用于模板系统）
            benchmark_data: 大盘和行业基准数据（来自 index_analyst + sector_analyst）
            trading_system: 关联的交易计划（如果有）
        """
        # 先构建硬编码版本作为降级兜底
        legacy_prompt = self._build_legacy_trade_review_prompt(
            trade_info, market_snapshot, benchmark_data, trading_system
        )

        # 如果启用模板系统，尝试使用模板生成提示词
        if _use_template_prompts():
            try:
                from tradingagents.utils.template_client import get_agent_prompt

                variables = self._build_trade_review_vars(trade_info, market_snapshot)

                # 如果有基准数据，填充到变量中
                if benchmark_data:
                    variables["market_benchmark"] = benchmark_data.get("market_benchmark", {})
                    variables["industry_benchmark"] = benchmark_data.get("industry_benchmark", {})
                    variables["attribution"] = benchmark_data.get("attribution", {})

                logger.info(f"📝 [交易复盘] 准备调用模板系统，变量数量: {len(variables)}")
                logger.info(f"📝 [交易复盘] 变量键: {list(variables.keys())}")

                prompt = get_agent_prompt(
                    agent_type="managers",
                    agent_name="trade_reviewer",
                    variables=variables,
                    user_id=user_id,
                    preference_id="neutral",  # 复盘分析默认使用中性风格
                    fallback_prompt=legacy_prompt
                )

                if prompt and prompt != legacy_prompt:
                    logger.info(f"✅ [交易复盘] 使用模板系统生成提示词 (长度: {len(prompt)})")
                    logger.info(f"📝 [交易复盘] 提示词前500字符:\n{prompt[:500]}")
                    logger.info(f"📝 [交易复盘] 提示词后500字符:\n{prompt[-500:]}")
                    return prompt

            except Exception as e:
                logger.warning(f"⚠️ [交易复盘] 模板系统调用失败，使用硬编码提示词: {e}")

        return legacy_prompt

    def _build_legacy_trade_review_prompt(
        self,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot,
        benchmark_data: Optional[Dict[str, Any]] = None,
        trading_system: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建硬编码交易复盘提示词（旧版，作为降级兜底）

        Args:
            trade_info: 交易信息
            market_snapshot: 市场快照
            benchmark_data: 大盘和行业基准数据（可选）
            trading_system: 关联的交易计划（可选）
        """
        # 交易记录明细
        trades_detail = ""
        for t in trade_info.trades:
            trades_detail += f"- {t.timestamp[:10]} {t.side.upper()} {t.quantity}股 @ {t.price}元"
            if t.pnl != 0:
                trades_detail += f" (盈亏: {t.pnl}元)"
            trades_detail += "\n"

        # K线数据摘要（最近10条）
        kline_summary = ""
        if market_snapshot.kline_data:
            recent_klines = market_snapshot.kline_data[-20:]
            for k in recent_klines:
                kline_summary += f"  {k['date']}: 开{k['open']:.2f} 高{k['high']:.2f} 低{k['low']:.2f} 收{k['close']:.2f}\n"

        # 构建大盘和行业基准信息（如果有）
        benchmark_section = ""
        if benchmark_data:
            market_bench = benchmark_data.get("market_benchmark", {})
            industry_bench = benchmark_data.get("industry_benchmark", {})
            attribution = benchmark_data.get("attribution", {})

            if market_bench.get("change_pct") is not None:
                benchmark_section += f"""
## 大盘与行业基准

### 大盘表现（{market_bench.get('index_name', '沪深300')}）
- 持仓期间涨跌幅: {market_bench.get('change_pct', 'N/A')}%
- 期间最高: {market_bench.get('period_high', 'N/A')}
- 期间最低: {market_bench.get('period_low', 'N/A')}
"""

            if industry_bench.get("industry_name"):
                benchmark_section += f"""
### 行业表现
- 所属行业: {industry_bench.get('industry_name', 'N/A')}
- 行业涨跌幅: {industry_bench.get('change_pct', 'N/A') or '暂无数据'}%
- 相对大盘超额: {industry_bench.get('vs_market', 'N/A') or '暂无数据'}%
"""

            if attribution.get("beta_contribution") is not None:
                benchmark_section += f"""
### 收益归因（初步）
- 大盘贡献(Beta): {attribution.get('beta_contribution', 'N/A')}%
- 行业超额: {attribution.get('industry_excess', 'N/A') or '待计算'}%
- 个股Alpha: {attribution.get('alpha', 'N/A') or '待计算'}%
"""

        # 构建交易计划规则部分
        trading_system_section = ""
        if trading_system:
            trading_system_section = f"""
## 关联的交易计划

本次交易关联了交易计划：**{trading_system.get('name', '未命名')}**

### 交易计划规则

"""
            # 添加选股规则
            stock_selection = trading_system.get('stock_selection', {})
            if stock_selection:
                trading_system_section += "**选股规则**:\n"
                must_meet = stock_selection.get('must_meet', [])
                if must_meet:
                    trading_system_section += "- 必须满足: " + "; ".join(must_meet) + "\n"
                exclude = stock_selection.get('exclude', [])
                if exclude:
                    trading_system_section += "- 排除条件: " + "; ".join(exclude) + "\n"
                trading_system_section += "\n"

            # 添加择时规则
            timing = trading_system.get('timing', {})
            if timing:
                trading_system_section += "**择时规则**:\n"
                entry_signals = timing.get('entry_signals', [])
                if entry_signals:
                    trading_system_section += "- 入场信号: " + "; ".join(entry_signals) + "\n"
                exit_signals = timing.get('exit_signals', [])
                if exit_signals:
                    trading_system_section += "- 出场信号: " + "; ".join(exit_signals) + "\n"
                trading_system_section += "\n"

            # 添加仓位规则
            position = trading_system.get('position', {})
            if position:
                trading_system_section += "**仓位规则**:\n"
                trading_system_section += f"- 单只股票上限: {position.get('single_stock_limit', 'N/A')}%\n"
                trading_system_section += f"- 最大持股数: {position.get('max_stocks', 'N/A')}只\n"
                trading_system_section += "\n"

            # 添加风险管理规则
            risk_management = trading_system.get('risk_management', {})
            if risk_management:
                trading_system_section += "**风险管理规则**:\n"
                stop_loss = risk_management.get('stop_loss', {})
                if stop_loss:
                    trading_system_section += f"- 止损: {stop_loss.get('type', 'N/A')} {stop_loss.get('value', 'N/A')}\n"
                take_profit = risk_management.get('take_profit', {})
                if take_profit:
                    trading_system_section += f"- 止盈: {take_profit.get('type', 'N/A')} {take_profit.get('value', 'N/A')}\n"
                trading_system_section += "\n"

            # 添加纪律规则
            discipline = trading_system.get('discipline', {})
            if discipline:
                trading_system_section += "**纪律规则**:\n"
                must_do = discipline.get('must_do', [])
                if must_do:
                    trading_system_section += "- 必须做到: " + "; ".join(must_do) + "\n"
                forbidden = discipline.get('forbidden', [])
                if forbidden:
                    trading_system_section += "- 严禁操作: " + "; ".join(forbidden) + "\n"
                trading_system_section += "\n"

            trading_system_section += "**请在复盘分析中，重点检查本次交易是否符合以上交易计划规则，指出违反规则的地方。**\n"

        prompt = f"""# 交易复盘分析任务

你是一位专业的交易复盘分析师，请对以下交易进行深入分析。

## 交易信息

- **股票代码**: {trade_info.code}
- **市场**: {trade_info.market}
- **持仓周期**: {trade_info.first_buy_date[:10] if trade_info.first_buy_date else '未知'} 至 {trade_info.last_sell_date[:10] if trade_info.last_sell_date else '未知'}
- **持仓天数**: {trade_info.holding_days} 天

### 交易明细
{trades_detail}

### 交易汇总
- 买入: {trade_info.total_buy_quantity}股，均价 {trade_info.avg_buy_price:.2f}元，金额 {trade_info.total_buy_amount:.2f}元
- 卖出: {trade_info.total_sell_quantity}股，均价 {trade_info.avg_sell_price:.2f}元，金额 {trade_info.total_sell_amount:.2f}元
- **实现盈亏**: {trade_info.realized_pnl:.2f}元 ({trade_info.realized_pnl_pct:.2f}%)
- 手续费: {trade_info.total_commission:.2f}元

## 交易期间行情数据

### 关键价格
- 持仓期间最高价: {market_snapshot.period_high or '未知'}元 (日期: {market_snapshot.period_high_date or '未知'})
- 持仓期间最低价: {market_snapshot.period_low or '未知'}元 (日期: {market_snapshot.period_low_date or '未知'})
- 买入当日: 开{market_snapshot.buy_date_open or '-'} 高{market_snapshot.buy_date_high or '-'} 低{market_snapshot.buy_date_low or '-'} 收{market_snapshot.buy_date_close or '-'}
- 卖出当日: 开{market_snapshot.sell_date_open or '-'} 高{market_snapshot.sell_date_high or '-'} 低{market_snapshot.sell_date_low or '-'} 收{market_snapshot.sell_date_close or '-'}

### K线数据
{kline_summary if kline_summary else '暂无K线数据'}
{benchmark_section}
{trading_system_section}
## 分析要求

请从以下维度分析这笔交易，以JSON格式输出：

```json
{{
    "overall_score": 0-100的整数（综合评分）,
    "timing_score": 0-100的整数（时机评分）,
    "position_score": 0-100的整数（仓位评分）,
    "discipline_score": 0-100的整数（纪律评分）,

    "summary": "50字以内的总体评价",
    "strengths": ["做得好的地方1", "做得好的地方2"],
    "weaknesses": ["需要改进的地方1", "需要改进的地方2"],
    "suggestions": ["具体建议1", "具体建议2"],

    "timing_analysis": "买入卖出时机的详细分析（100字以内）",
    "position_analysis": "仓位控制分析（50字以内）",
    "emotion_analysis": "是否存在情绪化操作（50字以内）",

    "market_analysis": "大盘环境对本次交易的影响（50字以内，如有大盘数据）",
    "industry_analysis": "行业因素对本次交易的影响（50字以内，如有行业数据）",

    "optimal_pnl": 理论最优收益金额（数字）,
    "missed_profit": 错失的收益金额（数字，如果亏损则为0）,
    "avoided_loss": 避免的亏损金额（数字，如果盈利则为0）
}}
```

**评分标准**：
- 90-100分：优秀，时机把握精准，纪律严明
- 70-89分：良好，整体操作合理，小有瑕疵
- 50-69分：一般，有明显改进空间
- 0-49分：较差，存在严重问题

**收益归因分析要点**：
- 如果个股涨幅 > 大盘涨幅 + 行业超额，说明选股能力较强
- 如果个股涨幅 ≈ 大盘涨幅，说明主要是跟随市场Beta
- 请在分析中区分"运气"（市场/行业贡献）和"能力"（选股/择时Alpha）
"""
        return prompt

    def _parse_ai_trade_review(
        self,
        content: str,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot
    ) -> AITradeReview:
        """解析AI复盘结果

        兼容两种 JSON 格式：
        1. 标准格式: overall_score, summary, strengths, weaknesses, suggestions 等
        2. 模板格式: analysis, improvement_recommendations, score_interpretation 等
        """
        import re
        import json

        logger.info(f"🔍 [解析AI响应] 开始解析，内容长度: {len(content)}")

        result = AITradeReview(actual_pnl=trade_info.realized_pnl)

        # 尝试提取JSON
        logger.info(f"🔍 [解析AI响应] 尝试提取 JSON 代码块...")
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)

        if json_match:
            logger.info(f"✅ [解析AI响应] 找到 JSON 代码块")
            json_str = json_match.group(1)
            logger.info(f"📄 [解析AI响应] JSON 内容长度: {len(json_str)}")
            logger.info(f"📄 [解析AI响应] JSON 内容前500字符:\n{json_str[:500]}")

            try:
                data = json.loads(json_str)
                logger.info(f"✅ [解析AI响应] JSON 解析成功")
                logger.info(f"📊 [解析AI响应] JSON 键: {list(data.keys())}")

                # 解析评分 - 兼容 0-100 和 1-10 两种评分体系
                def normalize_score(score_value, default=50):
                    """统一评分转换逻辑：1-10 → 0-100"""
                    if isinstance(score_value, (int, float)) and score_value <= 10:
                        return int(score_value * 10)
                    return int(score_value)

                result.overall_score = normalize_score(data.get("overall_score", 50))
                result.timing_score = normalize_score(data.get("timing_score", 50))
                result.position_score = normalize_score(data.get("position_score", 50))
                result.discipline_score = normalize_score(data.get("discipline_score", 50))

                # 解析摘要 - 兼容多种字段名
                result.summary = (
                    data.get("summary") or
                    data.get("score_interpretation") or
                    self._extract_nested_field(data, "analysis", "overall_assessment") or
                    ""
                )

                # 解析优点 - 兼容 strengths 和 analysis.strengths
                result.strengths = (
                    data.get("strengths") or
                    self._extract_nested_field(data, "analysis", "strengths") or
                    []
                )

                # 解析缺点 - 兼容 weaknesses 和 analysis.weaknesses
                result.weaknesses = (
                    data.get("weaknesses") or
                    self._extract_nested_field(data, "analysis", "weaknesses") or
                    []
                )

                # 解析建议 - 兼容 suggestions 和 improvement_recommendations
                result.suggestions = (
                    data.get("suggestions") or
                    data.get("improvement_recommendations") or
                    []
                )

                # 解析详细分析
                result.timing_analysis = (
                    data.get("timing_analysis") or
                    self._extract_nested_field(data, "analysis", "timing") or
                    ""
                )
                result.position_analysis = (
                    data.get("position_analysis") or
                    self._extract_nested_field(data, "analysis", "position") or
                    ""
                )
                result.emotion_analysis = (
                    data.get("emotion_analysis") or
                    self._extract_nested_field(data, "analysis", "emotion") or
                    ""
                )

                # 解析收益数据
                result.optimal_pnl = float(data.get("optimal_pnl", 0))
                result.missed_profit = float(data.get("missed_profit", 0))
                result.avoided_loss = float(data.get("avoided_loss", 0))

                # 🆕 解析交易计划执行情况（如果有）
                result.plan_adherence = data.get("plan_adherence")
                result.plan_deviation = data.get("plan_deviation")

                logger.info(f"✅ [解析AI响应] 解析完成 - 总分: {result.overall_score}, 摘要: {result.summary[:100] if result.summary else '空'}")
                if result.plan_adherence or result.plan_deviation:
                    logger.info(f"✅ [解析AI响应] 包含交易计划分析: adherence={bool(result.plan_adherence)}, deviation={bool(result.plan_deviation)}")
                return result

            except json.JSONDecodeError as e:
                logger.warning(f"❌ [解析AI响应] JSON解析失败: {e}")
                logger.warning(f"📄 [解析AI响应] 失败的JSON内容:\n{json_str}")
        else:
            logger.warning(f"⚠️ [解析AI响应] 未找到 JSON 代码块")
            logger.warning(f"📄 [解析AI响应] 完整内容:\n{content}")

        # 备用：计算理论最优收益
        logger.info(f"🔧 [解析AI响应] 使用备用方案，计算理论最优收益")
        if market_snapshot.optimal_buy_price and market_snapshot.optimal_sell_price:
            qty = trade_info.total_buy_quantity
            optimal_pnl = (market_snapshot.optimal_sell_price - market_snapshot.optimal_buy_price) * qty
            result.optimal_pnl = round(optimal_pnl, 2)

            if trade_info.realized_pnl >= 0:
                result.missed_profit = max(0, round(optimal_pnl - trade_info.realized_pnl, 2))
            else:
                result.avoided_loss = max(0, round(optimal_pnl - trade_info.realized_pnl, 2))

        result.summary = content[:200] if content else "AI分析完成"
        logger.info(f"⚠️ [解析AI响应] 使用备用方案完成 - 摘要: {result.summary}")
        return result

    def _extract_nested_field(self, data: Dict[str, Any], *keys) -> Any:
        """从嵌套字典中提取字段值

        Args:
            data: 数据字典
            *keys: 嵌套键路径，如 ("analysis", "strengths")

        Returns:
            找到的值，或 None
        """
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    # ==================== 复盘历史查询 ====================

    async def get_review_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        review_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取复盘历史列表，支持按股票代码、时间段、复盘类型筛选"""
        skip = (page - 1) * page_size

        # 构建查询条件
        query = {"user_id": user_id}

        # 股票代码筛选
        if code:
            query["trade_info.code"] = code

        # 复盘类型筛选
        if review_type:
            query["review_type"] = review_type

        # 时间段筛选
        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                from datetime import datetime
                query["created_at"]["$gte"] = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                from datetime import datetime
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                query["created_at"]["$lte"] = end_dt

        # 查询交易复盘
        cursor = self.db[self.trade_reviews_collection].find(
            query
        ).sort("created_at", -1).skip(skip).limit(page_size)

        items = await cursor.to_list(None)
        total = await self.db[self.trade_reviews_collection].count_documents(query)

        result = []
        for item in items:
            trade_info = item.get("trade_info", {})
            ai_review = item.get("ai_review", {})
            result.append(ReviewListItem(
                review_id=item.get("review_id", ""),
                review_type=item.get("review_type", "complete_trade"),
                code=trade_info.get("code"),
                name=trade_info.get("name"),
                realized_pnl=trade_info.get("realized_pnl", 0),
                overall_score=ai_review.get("overall_score", 0),
                status=item.get("status", "pending"),
                is_case_study=item.get("is_case_study", False),
                created_at=item.get("created_at")
            ))

        return {
            "items": [r.model_dump() for r in result],
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def get_review_detail(
        self,
        user_id: str,
        review_id: str
    ) -> Optional[TradeReviewReport]:
        """获取复盘详情"""
        doc = await self.db[self.trade_reviews_collection].find_one({
            "user_id": user_id,
            "review_id": review_id
        })

        if not doc:
            return None

        return TradeReviewReport(**doc)

    # ==================== 案例库功能 ====================

    async def save_as_case(
        self,
        user_id: str,
        review_id: str,
        tags: List[str] = None
    ) -> bool:
        """保存为案例"""
        result = await self.db[self.trade_reviews_collection].update_one(
            {"user_id": user_id, "review_id": review_id},
            {"$set": {
                "is_case_study": True,
                "tags": tags or []
            }}
        )
        return result.modified_count > 0

    async def get_cases(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取案例库

        Args:
            source: 数据源过滤, paper(模拟交易) 或 position(持仓操作), 为空则获取全部
        """
        skip = (page - 1) * page_size

        query = {
            "user_id": user_id,
            "is_case_study": True
        }
        if source:
            query["source"] = source

        cursor = self.db[self.trade_reviews_collection].find(query).sort("created_at", -1).skip(skip).limit(page_size)

        items = await cursor.to_list(None)
        total = await self.db[self.trade_reviews_collection].count_documents(query)

        result = []
        for item in items:
            trade_info = item.get("trade_info", {})
            ai_review = item.get("ai_review", {})
            result.append({
                "review_id": item.get("review_id", ""),
                "code": trade_info.get("code"),
                "name": trade_info.get("name"),
                "realized_pnl": trade_info.get("realized_pnl", 0),
                "overall_score": ai_review.get("overall_score", 0),
                "tags": item.get("tags", []),
                "source": item.get("source", "paper"),
                "created_at": item.get("created_at")
            })

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def delete_case(
        self,
        user_id: str,
        review_id: str
    ) -> bool:
        """从案例库移除"""
        result = await self.db[self.trade_reviews_collection].update_one(
            {"user_id": user_id, "review_id": review_id},
            {"$set": {"is_case_study": False}}
        )
        return result.modified_count > 0

    # ==================== 交易统计 ====================

    async def get_trading_statistics(
        self,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> TradingStatistics:
        """获取交易统计"""
        query = {"user_id": user_id, "side": "sell"}

        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date

        # 获取所有卖出交易
        cursor = self.db[self.paper_trades_collection].find(query)
        trades = await cursor.to_list(None)

        if not trades:
            return TradingStatistics()

        stats = TradingStatistics()
        stats.total_trades = len(trades)

        profits = []
        losses = []
        total_commission = 0.0

        for trade in trades:
            pnl = trade.get("pnl", 0)
            commission = trade.get("commission", 0)
            total_commission += commission

            if pnl > 0:
                stats.winning_trades += 1
                profits.append(pnl)
            elif pnl < 0:
                stats.losing_trades += 1
                losses.append(abs(pnl))

            stats.total_pnl += pnl

        # 计算统计指标
        if stats.total_trades > 0:
            stats.win_rate = round(stats.winning_trades / stats.total_trades * 100, 2)

        if profits:
            stats.avg_profit = round(sum(profits) / len(profits), 2)
            stats.max_single_profit = round(max(profits), 2)

        if losses:
            stats.avg_loss = round(sum(losses) / len(losses), 2)
            stats.max_single_loss = round(max(losses), 2)

        if stats.avg_loss > 0:
            stats.profit_loss_ratio = round(stats.avg_profit / stats.avg_loss, 2)

        stats.total_pnl = round(stats.total_pnl, 2)
        stats.total_commission = round(total_commission, 2)

        return stats

    # ==================== 阶段性复盘 ====================

    async def create_periodic_review(
        self,
        user_id: str,
        request: CreatePeriodicReviewRequest
    ) -> PeriodicReviewResponse:
        """创建阶段性复盘

        支持两种数据源:
        - paper: 模拟交易 (paper_trades)
        - position: 持仓操作 (position_changes)
        """
        import time
        start_time = time.time()

        review_id = str(uuid.uuid4())
        source = getattr(request, 'source', 'paper') or 'paper'

        # 解析日期
        period_start = datetime.strptime(request.start_date, "%Y-%m-%d")
        period_end = datetime.strptime(request.end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )

        # 根据数据源选择集合和查询条件
        if source == "position":
            # 持仓操作数据源
            collection = "position_changes"
            date_field = "created_at"
        else:
            # 模拟交易数据源
            collection = self.paper_trades_collection
            date_field = "timestamp"

        # 获取该时间段内的所有交易
        query = {
            "user_id": user_id,
            date_field: {
                "$gte": period_start,
                "$lte": period_end
            }
        }
        cursor = self.db[collection].find(query).sort(date_field, 1)
        trades = await cursor.to_list(None)

        source_name = "持仓操作" if source == "position" else "模拟交易"
        if not trades:
            raise ValueError(f"在 {request.start_date} 至 {request.end_date} 期间没有{source_name}记录")

        # 计算交易统计 (根据数据源使用不同的处理方法)
        if source == "position":
            statistics = await self._calculate_position_period_statistics(trades)
            trades_summary = self._build_position_trades_summary(trades)
        else:
            statistics = await self._calculate_period_statistics(trades)
            trades_summary = self._build_trades_summary(trades)

        # 调用AI进行阶段性分析
        ai_review = await self._call_ai_periodic_review(
            period_type=request.period_type.value,
            start_date=request.start_date,
            end_date=request.end_date,
            statistics=statistics,
            trades_summary=trades_summary
        )

        execution_time = time.time() - start_time

        # 保存复盘报告
        report = PeriodicReviewReport(
            review_id=review_id,
            user_id=user_id,
            period_type=request.period_type,
            period_start=period_start,
            period_end=period_end,
            source=source,
            statistics=statistics,
            trades_summary=trades_summary,
            ai_review=ai_review,
            status=ReviewStatus.COMPLETED,
            execution_time=execution_time,
            created_at=now_tz()
        )

        await self.db[self.periodic_reviews_collection].insert_one(
            report.model_dump(by_alias=True)
        )

        return PeriodicReviewResponse(
            review_id=review_id,
            status=ReviewStatus.COMPLETED,
            period_type=request.period_type,
            period_start=period_start,
            period_end=period_end,
            statistics=statistics,
            ai_review=ai_review,
            execution_time=execution_time,
            created_at=report.created_at
        )

    async def _calculate_period_statistics(
        self,
        trades: List[Dict[str, Any]]
    ) -> TradingStatistics:
        """计算阶段性交易统计"""
        stats = TradingStatistics()

        sell_trades = [t for t in trades if t.get("side") == "sell"]
        stats.total_trades = len(sell_trades)

        profits = []
        losses = []
        total_commission = 0.0

        for trade in sell_trades:
            pnl = trade.get("pnl", 0)
            commission = trade.get("commission", 0)
            total_commission += commission

            if pnl > 0:
                stats.winning_trades += 1
                profits.append(pnl)
            elif pnl < 0:
                stats.losing_trades += 1
                losses.append(abs(pnl))

            stats.total_pnl += pnl

        # 计算统计指标
        if stats.total_trades > 0:
            stats.win_rate = round(stats.winning_trades / stats.total_trades * 100, 2)

        if profits:
            stats.avg_profit = round(sum(profits) / len(profits), 2)
            stats.max_single_profit = round(max(profits), 2)

        if losses:
            stats.avg_loss = round(sum(losses) / len(losses), 2)
            stats.max_single_loss = round(max(losses), 2)

        if stats.avg_loss > 0:
            stats.profit_loss_ratio = round(stats.avg_profit / stats.avg_loss, 2)

        stats.total_pnl = round(stats.total_pnl, 2)
        stats.total_commission = round(total_commission, 2)

        return stats

    def _build_trades_summary(
        self,
        trades: List[Dict[str, Any]]
    ) -> List[TradeSummaryItem]:
        """构建交易摘要列表"""
        summary = []
        for trade in trades:
            if trade.get("side") == "sell":
                pnl = trade.get("pnl", 0)
                amount = trade.get("amount", 0)
                pnl_pct = (pnl / amount * 100) if amount > 0 else 0

                summary.append(TradeSummaryItem(
                    code=trade.get("code", ""),
                    name=trade.get("name", ""),
                    side=trade.get("side", ""),
                    quantity=trade.get("quantity", 0),
                    price=trade.get("price", 0),
                    pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct, 2),
                    timestamp=trade.get("timestamp", "").isoformat() if isinstance(trade.get("timestamp"), datetime) else str(trade.get("timestamp", ""))
                ))

        return summary

    async def _calculate_position_period_statistics(
        self,
        changes: List[Dict[str, Any]]
    ) -> TradingStatistics:
        """计算持仓操作的阶段性统计

        position_changes 数据结构:
        - change_type: BUY/SELL/ADJUST
        - quantity_before/quantity_after: 变动前后数量
        - cost_price_before/cost_price_after: 变动前后成本
        - price: 交易价格
        - realized_profit: 已实现盈亏 (卖出时有值)
        """
        stats = TradingStatistics()

        # 筛选出卖出操作
        sell_changes = [c for c in changes if c.get("change_type") == "SELL"]
        stats.total_trades = len(sell_changes)

        profits = []
        losses = []

        for change in sell_changes:
            pnl = change.get("realized_profit", 0) or 0

            if pnl > 0:
                stats.winning_trades += 1
                profits.append(pnl)
            elif pnl < 0:
                stats.losing_trades += 1
                losses.append(abs(pnl))

            stats.total_pnl += pnl

        # 计算统计指标
        if stats.total_trades > 0:
            stats.win_rate = round(stats.winning_trades / stats.total_trades * 100, 2)

        if profits:
            stats.avg_profit = round(sum(profits) / len(profits), 2)
            stats.max_single_profit = round(max(profits), 2)

        if losses:
            stats.avg_loss = round(sum(losses) / len(losses), 2)
            stats.max_single_loss = round(max(losses), 2)

        if stats.avg_loss > 0:
            stats.profit_loss_ratio = round(stats.avg_profit / stats.avg_loss, 2)

        stats.total_pnl = round(stats.total_pnl, 2)

        return stats

    def _build_position_trades_summary(
        self,
        changes: List[Dict[str, Any]]
    ) -> List[TradeSummaryItem]:
        """构建持仓操作交易摘要列表"""
        summary = []
        for change in changes:
            change_type = change.get("change_type", "")
            # 只显示买卖操作
            if change_type not in ["BUY", "SELL"]:
                continue

            pnl = change.get("realized_profit", 0) or 0
            price = change.get("price", 0) or 0
            qty_before = change.get("quantity_before", 0) or 0
            qty_after = change.get("quantity_after", 0) or 0
            quantity = abs(qty_after - qty_before)

            # 计算盈亏百分比
            cost_price = change.get("cost_price_before", 0) or 0
            pnl_pct = 0
            if cost_price > 0 and change_type == "SELL":
                pnl_pct = (price - cost_price) / cost_price * 100

            created_at = change.get("created_at")
            timestamp = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or "")

            summary.append(TradeSummaryItem(
                code=change.get("code", ""),
                name=change.get("name", ""),
                side="sell" if change_type == "SELL" else "buy",
                quantity=quantity,
                price=round(price, 2),
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct, 2),
                timestamp=timestamp
            ))

        return summary

    async def _call_ai_periodic_review(
        self,
        period_type: str,
        start_date: str,
        end_date: str,
        statistics: TradingStatistics,
        trades_summary: List[TradeSummaryItem]
    ) -> AIPeriodicReview:
        """调用AI进行阶段性复盘分析"""
        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
        import asyncio

        # 构建提示词
        period_names = {
            "week": "周度",
            "month": "月度",
            "quarter": "季度",
            "year": "年度"
        }
        period_name = period_names.get(period_type, "阶段性")

        # 构建交易明细
        trades_detail = "\n".join([
            f"- {t.code}: {t.side} {t.quantity}股 @ {t.price}, 盈亏: {t.pnl} ({t.pnl_pct}%)"
            for t in trades_summary[:20]  # 最多显示20条
        ])
        if len(trades_summary) > 20:
            trades_detail += f"\n... 还有 {len(trades_summary) - 20} 条交易记录"

        prompt = f"""# {period_name}交易复盘

## 复盘周期
{start_date} 至 {end_date}

## 交易统计
- 总交易次数: {statistics.total_trades}
- 盈利次数: {statistics.winning_trades} / 亏损次数: {statistics.losing_trades}
- 胜率: {statistics.win_rate}%
- 总盈亏: {statistics.total_pnl}
- 平均盈利: {statistics.avg_profit} / 平均亏损: {statistics.avg_loss}
- 盈亏比: {statistics.profit_loss_ratio}
- 最大单笔盈利: {statistics.max_single_profit}
- 最大单笔亏损: {statistics.max_single_loss}
- 总手续费: {statistics.total_commission}

## 交易明细
{trades_detail}

请对这段时间的交易进行全面复盘分析，包括：
1. 整体评分（0-100分）
2. 交易风格分析
3. 常见错误总结
4. 改进方向建议
5. 下阶段行动计划
6. 最佳交易分析
7. 最差交易分析

请以JSON格式输出，格式如下：
{{
    "overall_score": 75,
    "summary": "整体评价...",
    "trading_style": "交易风格分析...",
    "common_mistakes": ["错误1", "错误2"],
    "improvement_areas": ["改进方向1", "改进方向2"],
    "action_plan": ["行动计划1", "行动计划2"],
    "best_trade": "最佳交易分析...",
    "worst_trade": "最差交易分析..."
}}
"""

        try:
            model_name = "qwen-plus"
            provider_info = get_provider_and_url_by_model_sync(model_name)

            # 使用同步 requests 调用，避免异步 httpx 的代理问题
            content = await asyncio.get_event_loop().run_in_executor(
                None,
                self._call_llm_sync,
                prompt,
                model_name,
                provider_info.get("backend_url"),
                provider_info.get("api_key")
            )

            # 解析JSON响应
            import json
            import re

            # 尝试提取JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                return AIPeriodicReview(
                    overall_score=data.get("overall_score", 60),
                    summary=data.get("summary", ""),
                    trading_style=data.get("trading_style", ""),
                    common_mistakes=data.get("common_mistakes", []),
                    improvement_areas=data.get("improvement_areas", []),
                    action_plan=data.get("action_plan", []),
                    best_trade=data.get("best_trade"),
                    worst_trade=data.get("worst_trade")
                )
            else:
                # 如果无法解析JSON，返回默认结果
                return AIPeriodicReview(
                    overall_score=60,
                    summary=content[:500] if content else "AI分析完成"
                )

        except Exception as e:
            logger.error(f"AI阶段性复盘分析失败: {e}")
            return AIPeriodicReview(
                overall_score=0,
                summary=f"AI分析失败: {str(e)}"
            )

    async def get_periodic_review_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取阶段性复盘历史

        Args:
            source: 数据源过滤, paper(模拟交易) 或 position(持仓操作), 为空则获取全部
        """
        skip = (page - 1) * page_size

        query = {"user_id": user_id}
        if source:
            query["source"] = source

        cursor = self.db[self.periodic_reviews_collection].find(
            query
        ).sort("created_at", -1).skip(skip).limit(page_size)

        items = await cursor.to_list(None)
        total = await self.db[self.periodic_reviews_collection].count_documents(query)

        result = []
        for item in items:
            ai_review = item.get("ai_review", {})
            statistics = item.get("statistics", {})
            result.append({
                "review_id": item.get("review_id", ""),
                "period_type": item.get("period_type", "month"),
                "period_start": item.get("period_start"),
                "period_end": item.get("period_end"),
                "source": item.get("source", "paper"),
                "total_trades": statistics.get("total_trades", 0),
                "total_pnl": statistics.get("total_pnl", 0),
                "win_rate": statistics.get("win_rate", 0),
                "overall_score": ai_review.get("overall_score", 0),
                "status": item.get("status", "pending"),
                "created_at": item.get("created_at")
            })

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def get_periodic_review_detail(
        self,
        user_id: str,
        review_id: str
    ) -> Optional[PeriodicReviewReport]:
        """获取阶段性复盘详情"""
        doc = await self.db[self.periodic_reviews_collection].find_one({
            "user_id": user_id,
            "review_id": review_id
        })

        if not doc:
            return None

        return PeriodicReviewReport(**doc)

    def _build_trade_review_vars(
        self,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot
    ) -> Dict[str, Any]:
        """构建交易复盘模板变量

        Args:
            trade_info: 交易信息
            market_snapshot: 市场快照

        Returns:
            模板变量字典
        """
        # 构建交易记录明细
        trades_detail = []
        for t in trade_info.trades:
            trade_record = {
                "date": t.timestamp[:10] if t.timestamp else "",
                "side": t.side.upper(),
                "quantity": t.quantity,
                "price": t.price,
                "pnl": t.pnl
            }
            trades_detail.append(trade_record)

        # 构建K线数据摘要
        kline_data = []
        if market_snapshot.kline_data:
            for k in market_snapshot.kline_data[-20:]:
                kline_data.append({
                    "date": k.get("date", ""),
                    "open": k.get("open", 0),
                    "high": k.get("high", 0),
                    "low": k.get("low", 0),
                    "close": k.get("close", 0)
                })

        return {
            "trade": {
                "code": trade_info.code,
                "name": trade_info.name or trade_info.code,
                "market": trade_info.market,
                "first_buy_date": trade_info.first_buy_date[:10] if trade_info.first_buy_date else "",
                "last_sell_date": trade_info.last_sell_date[:10] if trade_info.last_sell_date else "",
                "holding_days": trade_info.holding_days,
                "trades": trades_detail,
                "total_buy_quantity": trade_info.total_buy_quantity,
                "total_sell_quantity": trade_info.total_sell_quantity,
                "avg_buy_price": trade_info.avg_buy_price,
                "avg_sell_price": trade_info.avg_sell_price,
                "total_buy_amount": trade_info.total_buy_amount,
                "total_sell_amount": trade_info.total_sell_amount,
                "realized_pnl": trade_info.realized_pnl,
                "realized_pnl_pct": trade_info.realized_pnl_pct,
                "total_commission": trade_info.total_commission
            },
            "market": {
                "period_high": market_snapshot.period_high,
                "period_high_date": market_snapshot.period_high_date,
                "period_low": market_snapshot.period_low,
                "period_low_date": market_snapshot.period_low_date,
                "buy_date": {
                    "open": market_snapshot.buy_date_open,
                    "high": market_snapshot.buy_date_high,
                    "low": market_snapshot.buy_date_low,
                    "close": market_snapshot.buy_date_close
                },
                "sell_date": {
                    "open": market_snapshot.sell_date_open,
                    "high": market_snapshot.sell_date_high,
                    "low": market_snapshot.sell_date_low,
                    "close": market_snapshot.sell_date_close
                },
                "kline_data": kline_data
            },
            # 大盘和行业基准数据（后续通过 _get_benchmark_data 填充）
            "market_benchmark": {},
            "industry_benchmark": {},
            "attribution": {}
        }

    async def _get_benchmark_data(
        self,
        stock_code: str,
        market: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """获取大盘和行业基准数据

        使用统一的数据源管理器获取数据，根据数据库配置自动选择数据源

        Args:
            stock_code: 股票代码
            market: 市场类型
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            包含大盘基准、行业基准、收益归因的字典
        """
        result = {
            "market_benchmark": {
                "index_code": "",
                "index_name": "",
                "start_price": None,
                "end_price": None,
                "change_pct": None,
                "period_high": None,
                "period_low": None
            },
            "industry_benchmark": {
                "industry_name": "",
                "index_code": "",
                "change_pct": None,
                "vs_market": None  # 相对大盘超额
            },
            "attribution": {
                "beta_contribution": None,
                "industry_excess": None,
                "alpha": None,
                "timing_score": None
            }
        }

        try:
            # 直接使用 tushare provider 获取指数数据（参考 index_tools.py 的实现）
            from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
            from core.tools.sector_tools import get_stock_sector_info

            provider = get_tushare_provider()

            # 1. 获取大盘基准数据（沪深300）
            benchmark_code = "000300.SH"
            benchmark_name = "沪深300"

            start_date_clean = start_date.replace('-', '')
            end_date_clean = end_date.replace('-', '')

            logger.info(f"📊 [复盘] 获取大盘数据: {benchmark_code}, {start_date_clean} ~ {end_date_clean}")

            # 使用 tushare provider 的 get_index_daily 方法
            index_df = await provider.get_index_daily(
                ts_code=benchmark_code,
                start_date=start_date_clean,
                end_date=end_date_clean
            )

            if index_df is not None and not index_df.empty:
                index_df = index_df.sort_values('trade_date')
                start_close = index_df.iloc[0]['close']
                end_close = index_df.iloc[-1]['close']
                market_change_pct = ((end_close - start_close) / start_close) * 100

                result["market_benchmark"] = {
                    "index_code": benchmark_code,
                    "index_name": benchmark_name,
                    "start_price": float(start_close),
                    "end_price": float(end_close),
                    "change_pct": round(market_change_pct, 2),
                    "period_high": float(index_df['high'].max()),
                    "period_low": float(index_df['low'].min())
                }
                logger.info(f"✅ [复盘] 从 tushare 获取大盘数据成功: {market_change_pct:.2f}%")
            else:
                logger.warning(f"⚠️ [复盘] 未获取到大盘数据")

            # 2. 获取行业基准数据（使用统一工具函数）
            sector_info = await get_stock_sector_info(stock_code)
            if sector_info and sector_info.get("industry"):
                result["industry_benchmark"]["industry_name"] = sector_info["industry"]
                logger.info(f"📊 [复盘] 股票 {stock_code} 所属行业: {sector_info['industry']}")

            # 3. 计算收益归因（简化版）
            if result["market_benchmark"]["change_pct"] is not None:
                result["attribution"]["beta_contribution"] = result["market_benchmark"]["change_pct"]

            logger.info(f"✅ [复盘] 基准数据获取完成: 大盘={result['market_benchmark']['change_pct']}%")

        except ImportError as e:
            logger.warning(f"⚠️ [复盘] 数据工具模块不可用: {e}")
        except Exception as e:
            logger.error(f"❌ [复盘] 获取基准数据失败: {e}", exc_info=True)

        return result

    def _format_trading_plan_for_workflow(self, trading_system: Dict[str, Any]) -> Dict[str, Any]:
        """格式化交易计划规则，用于工作流输入

        Args:
            trading_system: 交易计划数据

        Returns:
            格式化后的交易计划规则字典
        """
        # 🔧 适配实际的数据库结构
        # 数据库使用: stock_selection, timing, position, risk_management, discipline
        # 而不是: stock_selection_rules, timing_rules, position_rules, risk_rules, discipline_rules

        stock_selection = trading_system.get("stock_selection", {})
        timing = trading_system.get("timing", {})
        position = trading_system.get("position", {})
        risk_management = trading_system.get("risk_management", {})
        discipline = trading_system.get("discipline", {})

        return {
            "plan_id": trading_system.get("system_id", ""),
            "plan_name": trading_system.get("name", ""),
            "style": trading_system.get("style", ""),
            "rules": {
                "stock_selection": {
                    "must_meet": stock_selection.get("must_have", []),  # 🔧 must_have -> must_meet
                    "exclude": stock_selection.get("exclude", []),
                },
                "timing": {
                    "entry_signals": timing.get("entry_signals", []),
                    "exit_signals": timing.get("exit_signals", []),  # 可能为空
                },
                "position": {
                    "single_stock_limit": position.get("max_per_stock", 0),  # 🔧 max_per_stock -> single_stock_limit
                    "max_stocks": position.get("max_holdings", 0),  # 🔧 max_holdings -> max_stocks
                },
                "risk": {
                    "stop_loss": risk_management.get("stop_loss", {}),
                    "take_profit": risk_management.get("take_profit", {}),
                },
                "discipline": {
                    "must_do": discipline.get("must_do", []),
                    "forbidden": discipline.get("must_not", []),  # 🔧 must_not -> forbidden
                },
            },
            "rules_text": self._format_trading_plan_rules_text(trading_system),  # 文本格式，供提示词使用
        }

    def _format_trading_plan_rules_text(self, trading_system: Dict[str, Any]) -> str:
        """将交易计划规则格式化为文本，供提示词使用

        Args:
            trading_system: 交易计划数据

        Returns:
            格式化后的规则文本
        """
        rules_parts = []

        # 🔧 适配实际的数据库结构
        # 数据库使用: stock_selection, timing, position, risk_management, discipline

        # 选股规则
        stock_selection = trading_system.get("stock_selection", {})
        must_have = stock_selection.get("must_have", [])
        exclude = stock_selection.get("exclude", [])

        if must_have or exclude:
            rules_parts.append("**选股规则**:")
            if must_have:
                # must_have 是对象数组，每个对象有 rule 和 description
                must_have_texts = [f"{item.get('rule', '')} ({item.get('description', '')})" for item in must_have]
                rules_parts.append(f"- 必须满足: {'; '.join(must_have_texts)}")
            if exclude:
                # exclude 也是对象数组
                exclude_texts = [f"{item.get('rule', '')} ({item.get('description', '')})" for item in exclude]
                rules_parts.append(f"- 排除条件: {'; '.join(exclude_texts)}")

        # 择时规则
        timing = trading_system.get("timing", {})
        entry_signals = timing.get("entry_signals", [])
        exit_signals = timing.get("exit_signals", [])

        if entry_signals or exit_signals:
            rules_parts.append("\n**择时规则**:")
            if entry_signals:
                # entry_signals 是对象数组，每个对象有 signal 和 description
                entry_texts = [f"{item.get('signal', '')} ({item.get('description', '')})" for item in entry_signals]
                rules_parts.append(f"- 入场信号: {'; '.join(entry_texts)}")
            if exit_signals:
                exit_texts = [f"{item.get('signal', '')} ({item.get('description', '')})" for item in exit_signals]
                rules_parts.append(f"- 出场信号: {'; '.join(exit_texts)}")

        # 仓位规则
        position = trading_system.get("position", {})
        max_per_stock = position.get("max_per_stock")
        max_holdings = position.get("max_holdings")

        if max_per_stock or max_holdings:
            rules_parts.append("\n**仓位规则**:")
            if max_per_stock:
                rules_parts.append(f"- 单只股票上限: {max_per_stock * 100}%")
            if max_holdings:
                rules_parts.append(f"- 最大持股数: {max_holdings}只")

        # 风险管理规则
        risk_management = trading_system.get("risk_management", {})
        stop_loss = risk_management.get("stop_loss", {})
        take_profit = risk_management.get("take_profit", {})

        if stop_loss or take_profit:
            rules_parts.append("\n**风险管理规则**:")
            if stop_loss.get("type"):
                stop_loss_desc = stop_loss.get("description", "")
                if stop_loss.get("percentage"):
                    rules_parts.append(f"- 止损: {stop_loss.get('percentage') * 100}% ({stop_loss_desc})")
                else:
                    rules_parts.append(f"- 止损: {stop_loss_desc}")
            if take_profit.get("type"):
                take_profit_desc = take_profit.get("description", "")
                rules_parts.append(f"- 止盈: {take_profit_desc}")

        # 纪律规则
        discipline = trading_system.get("discipline", {})
        must_do = discipline.get("must_do", [])
        must_not = discipline.get("must_not", [])

        if must_do or must_not:
            rules_parts.append("\n**纪律规则**:")
            if must_do:
                # must_do 是对象数组，每个对象有 rule 和 description
                must_do_texts = [f"{item.get('rule', '')} ({item.get('description', '')})" for item in must_do]
                rules_parts.append(f"- 必须做到: {'; '.join(must_do_texts)}")
            if must_not:
                must_not_texts = [f"{item.get('rule', '')} ({item.get('description', '')})" for item in must_not]
                rules_parts.append(f"- 严禁操作: {'; '.join(must_not_texts)}")

        return "\n".join(rules_parts) if rules_parts else "无规则"

    async def _call_workflow_trade_review(
        self,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot,
        user_id: Optional[str] = None,
        trading_system: Optional[Dict[str, Any]] = None
    ) -> AITradeReview:
        """使用工作流引擎进行多维度交易复盘分析

        工作流包含:
        1. 时机分析师 - 分析买卖时机
        2. 仓位分析师 - 分析仓位管理
        3. 情绪分析师 - 分析情绪控制
        4. 归因分析师 - 分析收益来源
        5. 复盘总结师 - 综合总结报告

        Args:
            trade_info: 交易信息
            market_snapshot: 市场快照
            user_id: 用户ID
            trading_system: 关联的交易计划（如果有）
        """
        from core.workflow.engine import WorkflowEngine
        from core.workflow.default_workflow_provider import get_default_workflow_provider

        logger.info(f"🚀 [工作流复盘] 开始执行交易复盘工作流")

        # 🔍 调试：打印原始输入数据
        logger.info(f"🔍 [工作流复盘] 原始数据 - trade_info.code: {trade_info.code}")
        logger.info(f"🔍 [工作流复盘] 原始数据 - trade_info.name: {trade_info.name}")
        logger.info(f"🔍 [工作流复盘] 原始数据 - trade_info.trades 数量: {len(trade_info.trades) if trade_info.trades else 0}")
        if trade_info.trades:
            logger.info(f"🔍 [工作流复盘] 原始数据 - 第一笔交易: side={trade_info.trades[0].side}, quantity={trade_info.trades[0].quantity}, price={trade_info.trades[0].price}")
        logger.info(f"🔍 [工作流复盘] 原始数据 - trade_info 类型: {type(trade_info)}")
        logger.info(f"🔍 [工作流复盘] 原始数据 - trade_info 属性: {[attr for attr in dir(trade_info) if not attr.startswith('_')]}")

        # 1. 加载复盘工作流 (v2.0)
        provider = get_default_workflow_provider()
        workflow = provider.load_workflow("trade_review_v2")  # 🔧 改为 v2.0 工作流
        logger.info(f"✅ [工作流复盘] 加载工作流: {workflow.name}")

        # 2. 获取基准数据
        benchmark_data = {}
        try:
            benchmark_data = await self._get_benchmark_data(
                stock_code=trade_info.code,
                market=trade_info.market,
                start_date=trade_info.first_buy_date[:10] if trade_info.first_buy_date else "",
                end_date=trade_info.last_sell_date[:10] if trade_info.last_sell_date else ""
            )
            logger.info(f"📊 [工作流复盘] 获取基准数据完成")
        except Exception as e:
            logger.warning(f"⚠️ [工作流复盘] 获取基准数据失败: {e}")

        # 3. 准备工作流输入
        # 🆕 添加 user_id 和 trade_ids，供 Agent 通过工具获取完整数据
        inputs = {
            "user_id": user_id,  # 用户ID，供工具使用
            "trade_ids": [str(t.trade_id) for t in trade_info.trades] if trade_info.trades else [],  # 交易ID列表
            "trade_info": {
                "code": trade_info.code,
                "name": trade_info.name,
                "market": trade_info.market,
                # 🔧 修复字段名，与分析师期望的字段名一致
                "holding_days": trade_info.holding_days,  # 修改：holding_period -> holding_days
                "realized_pnl": trade_info.realized_pnl,  # 修改：pnl -> realized_pnl
                "realized_pnl_pct": trade_info.realized_pnl_pct,  # 新增：realized_pnl_pct
                # 保留旧字段名以兼容
                "holding_period": trade_info.holding_days,
                "return_rate": trade_info.realized_pnl_pct / 100.0 if trade_info.realized_pnl_pct else 0,
                "pnl": trade_info.realized_pnl,
                "avg_buy_price": trade_info.avg_buy_price,
                "avg_sell_price": trade_info.avg_sell_price,
                "max_profit": self._calculate_max_profit_pct(trade_info, market_snapshot),
                "max_loss": self._calculate_max_loss_pct(trade_info, market_snapshot),
                "trades": [
                    {
                        "date": t.timestamp[:10] if t.timestamp else "",
                        "side": t.side,
                        "quantity": t.quantity,
                        "price": t.price,
                        "pnl": t.pnl or 0,
                        "price_change_before": 0,  # TODO: 计算交易前价格变化
                    }
                    for t in trade_info.trades
                ],
            },
            "market_data": {
                "kline_data": market_snapshot.kline_data or [],
                "period_high": market_snapshot.period_high or 0.0,
                "period_low": market_snapshot.period_low or 0.0,
                "period_high_date": market_snapshot.period_high_date or "",
                "period_low_date": market_snapshot.period_low_date or "",
                "summary": f"持仓期间最高价: {market_snapshot.period_high or 'N/A'}, 最低价: {market_snapshot.period_low or 'N/A'}",
            },
            "benchmark_data": {
                "market_return": benchmark_data.get("market_benchmark", {}).get("change_pct", 0) / 100.0 if benchmark_data.get("market_benchmark", {}).get("change_pct") else 0,
                "industry_return": benchmark_data.get("industry_benchmark", {}).get("change_pct", 0) / 100.0 if benchmark_data.get("industry_benchmark", {}).get("change_pct") else 0,
                "industry_name": benchmark_data.get("industry_benchmark", {}).get("industry_name", ""),
            },
            "messages": [],
        }

        # 🆕 如果关联了交易计划，添加交易计划规则到输入中
        if trading_system:
            logger.info(f"📋 [工作流复盘] 关联交易计划: {trading_system.get('name', 'N/A')}")
            formatted_plan = self._format_trading_plan_for_workflow(trading_system)
            inputs["trading_plan"] = formatted_plan
            logger.info(f"✅ [工作流复盘] 已添加 trading_plan 到 inputs")
            logger.info(f"   - plan_name: {formatted_plan.get('plan_name', 'N/A')}")
            logger.info(f"   - rules_text 长度: {len(formatted_plan.get('rules_text', ''))}")
        else:
            logger.info(f"📋 [工作流复盘] 未关联交易计划")

        logger.info(f"📝 [工作流复盘] 工作流输入准备完成")
        logger.info(f"📋 [工作流复盘] 股票: {trade_info.code}, 持仓周期: {trade_info.holding_days}天")
        logger.info(f"📋 [工作流复盘] 收益率: {trade_info.realized_pnl_pct:.2f}%, 盈亏: {trade_info.realized_pnl:.2f}元")
        logger.info(f"📋 [工作流复盘] 交易记录数量: {len(trade_info.trades) if trade_info.trades else 0}")
        logger.info(f"📋 [工作流复盘] 基准数据: 大盘={benchmark_data.get('market_benchmark', {}).get('change_pct', 'N/A')}%, 行业={benchmark_data.get('industry_benchmark', {}).get('industry_name', 'N/A')}")

        # 🔍 调试：打印实际传入工作流的数据
        logger.info(f"🔍 [工作流复盘] 调试 - inputs['trade_info']['code']: {inputs['trade_info']['code']}")
        logger.info(f"🔍 [工作流复盘] 调试 - inputs['trade_info']['trades'] 长度: {len(inputs['trade_info']['trades'])}")
        if inputs['trade_info']['trades']:
            logger.info(f"🔍 [工作流复盘] 调试 - 第一笔交易: {inputs['trade_info']['trades'][0]}")

        # 4. 构建遗留配置
        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
        model_name = "qwen-plus"
        provider_info = get_provider_and_url_by_model_sync(model_name)

        legacy_config = {
            "llm_provider": provider_info.get("provider", "dashscope"),
            "quick_think_llm": model_name,
            "deep_think_llm": model_name,
            "backend_url": provider_info.get("backend_url"),
            "api_key": provider_info.get("api_key"),
        }
        logger.info(f"🔧 [工作流复盘] LLM配置: provider={legacy_config['llm_provider']}, model={model_name}")

        # 5. 创建并执行工作流引擎
        engine = WorkflowEngine(legacy_config=legacy_config)
        engine.load(workflow)
        logger.info(f"🔨 [工作流复盘] 工作流引擎已加载，节点数: {len(workflow.nodes)}, 边数: {len(workflow.edges)}")

        # 列出工作流节点
        for node in workflow.nodes:
            agent_info = f" (agent: {node.agent_id})" if node.agent_id else ""
            logger.info(f"   📍 节点: {node.id} [{node.type}]{agent_info}")

        def progress_callback(progress, message, **kwargs):
            step_name = kwargs.get("step_name", "")
            step_info = f" [{step_name}]" if step_name else ""
            logger.info(f"📊 [工作流复盘] 进度: {progress:.1f}%{step_info} - {message}")

        logger.info(f"🚀 [工作流复盘] 开始执行工作流...")
        result = engine.execute(inputs=inputs, progress_callback=progress_callback)

        logger.info(f"✅ [工作流复盘] 工作流执行完成")
        logger.info(f"📋 [工作流复盘] 输出字段: {list(result.keys())}")

        # 打印各维度分析结果摘要
        for key in ["timing_analysis", "position_analysis", "emotion_analysis", "attribution_analysis", "review_summary"]:
            if key in result:
                content = result[key]
                # 🔧 处理可能的字典格式（Agent 可能返回 {"content": "..."} 格式）
                if isinstance(content, dict):
                    content_str = content.get("content", "") or content.get("text", "") or str(content)
                elif isinstance(content, str):
                    content_str = content
                else:
                    content_str = str(content)

                content_len = len(content_str)
                preview = (content_str[:100] + "...") if content_len > 100 else content_str
                logger.info(f"   📄 {key}: {content_len}字符, 预览: {preview}")

        # 6. 解析工作流输出
        return self._parse_workflow_result(result, trade_info, market_snapshot)

    def _parse_workflow_result(
        self,
        workflow_result: Dict[str, Any],
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot
    ) -> AITradeReview:
        """解析工作流执行结果为 AITradeReview"""
        import re
        import json

        logger.info(f"🔍 [工作流复盘] 解析工作流结果")
        logger.info(f"📋 [工作流复盘] 结果键: {list(workflow_result.keys())}")

        # 🔍 打印各个分析师的具体输出
        analysis_fields = ['timing_analysis', 'position_analysis', 'emotion_analysis', 'attribution_analysis', 'review_summary']
        for field in analysis_fields:
            if field in workflow_result:
                content = workflow_result[field]
                logger.info(f"📊 [工作流复盘] {field}: {content[:200] if isinstance(content, str) else str(content)[:200]}...")
            else:
                logger.warning(f"⚠️ [工作流复盘] 缺失字段: {field}")

        result = AITradeReview(actual_pnl=trade_info.realized_pnl)

        # 提取各维度分析结果
        timing_analysis = workflow_result.get("timing_analysis", "")
        position_analysis = workflow_result.get("position_analysis", "")
        emotion_analysis = workflow_result.get("emotion_analysis", "")
        attribution_analysis = workflow_result.get("attribution_analysis", "")
        review_summary_raw = workflow_result.get("review_summary", "")

        # 🔧 处理 Agent 返回的字典格式（提取 content 字段）
        if isinstance(review_summary_raw, dict):
            review_summary = review_summary_raw.get("content", "") or review_summary_raw.get("text", "") or str(review_summary_raw)
            logger.info(f"📄 [AI复盘] review_summary 是字典，提取 content 字段")
        else:
            review_summary = review_summary_raw if isinstance(review_summary_raw, str) else str(review_summary_raw)

        # 设置分析结果（同样处理可能的字典格式）
        result.timing_analysis = timing_analysis.get("content", str(timing_analysis)) if isinstance(timing_analysis, dict) else (timing_analysis if isinstance(timing_analysis, str) else str(timing_analysis))
        result.position_analysis = position_analysis.get("content", str(position_analysis)) if isinstance(position_analysis, dict) else (position_analysis if isinstance(position_analysis, str) else str(position_analysis))
        result.emotion_analysis = emotion_analysis.get("content", str(emotion_analysis)) if isinstance(emotion_analysis, dict) else (emotion_analysis if isinstance(emotion_analysis, str) else str(emotion_analysis))
        result.attribution_analysis = attribution_analysis.get("content", str(attribution_analysis)) if isinstance(attribution_analysis, dict) else (attribution_analysis if isinstance(attribution_analysis, str) else str(attribution_analysis))

        # 从总结中提取评分和建议
        if review_summary:
            logger.info(f"📄 [AI复盘] review_summary 长度: {len(review_summary)}")
            logger.info(f"📄 [AI复盘] 前500字符: {review_summary[:500]}")
            logger.info(f"📄 [AI复盘] 后500字符: {review_summary[-500:]}")

            # 尝试从总结中提取 JSON（支持多种格式）
            json_match = re.search(r'```json\s*(.*?)\s*```', review_summary, re.DOTALL)
            if not json_match:
                # 尝试不带 json 标记的代码块
                json_match = re.search(r'```\s*(\{.*?\})\s*```', review_summary, re.DOTALL)
            if not json_match:
                # 尝试直接匹配 JSON 对象
                json_match = re.search(r'(\{[^{]*?"overall_score".*?\})', review_summary, re.DOTALL)

            if json_match:
                logger.info(f"✅ [AI复盘] 找到 JSON 匹配")
                try:
                    json_str = json_match.group(1)
                    logger.info(f"📄 [AI复盘] JSON 字符串前500字符: {json_str[:500]}")
                    logger.info(f"📄 [AI复盘] JSON 字符串后500字符: {json_str[-500:]}")
                    data = json.loads(json_str)
                    logger.info(f"📄 [AI复盘] JSON 解析成功，顶层键: {list(data.keys())}")

                    # 🔧 处理嵌套的 JSON 结构（如 {"复盘报告": {...}}）
                    if len(data) == 1 and isinstance(list(data.values())[0], dict):
                        logger.info(f"📄 [AI复盘] 检测到嵌套结构，提取内层数据")
                        data = list(data.values())[0]
                        logger.info(f"📄 [AI复盘] 内层键: {list(data.keys())}")

                    # 提取评分（支持多种字段名，统一转换 1-10 → 0-100）
                    def normalize_score(score_value, default=50):
                        """统一评分转换逻辑：1-10 → 0-100"""
                        if isinstance(score_value, (int, float)) and score_value <= 10:
                            return int(score_value * 10)
                        return int(score_value)

                    result.overall_score = normalize_score(data.get("overall_score") or data.get("综合评分") or data.get("总分") or 50)
                    result.timing_score = normalize_score(data.get("timing_score") or data.get("时机评分") or data.get("买卖时机评分") or 50)
                    result.position_score = normalize_score(data.get("position_score") or data.get("仓位评分") or data.get("仓位管理评分") or 50)
                    result.emotion_score = normalize_score(data.get("emotion_score") or data.get("情绪评分") or data.get("情绪控制评分") or 50)
                    result.attribution_score = normalize_score(data.get("attribution_score") or data.get("归因评分") or data.get("收益归因评分") or 50)
                    result.discipline_score = normalize_score(data.get("discipline_score") or data.get("纪律评分") or data.get("执行纪律评分") or 50)

                    # 提取文本字段（确保是字符串）
                    summary_raw = data.get("summary") or data.get("综合评价") or data.get("核心结论") or ""
                    result.summary = summary_raw if isinstance(summary_raw, str) else str(summary_raw) if summary_raw else ""

                    strengths_raw = data.get("strengths") or data.get("优点") or data.get("做得好的地方") or []
                    result.strengths = strengths_raw if isinstance(strengths_raw, list) else [str(strengths_raw)] if strengths_raw else []

                    weaknesses_raw = data.get("weaknesses") or data.get("不足") or data.get("需要改进的地方") or []
                    result.weaknesses = weaknesses_raw if isinstance(weaknesses_raw, list) else [str(weaknesses_raw)] if weaknesses_raw else []

                    suggestions_raw = data.get("suggestions") or data.get("建议") or data.get("改进建议") or []
                    result.suggestions = suggestions_raw if isinstance(suggestions_raw, list) else [str(suggestions_raw)] if suggestions_raw else []

                    # 🆕 提取交易计划执行情况（如果有）
                    result.plan_adherence = data.get("plan_adherence")
                    result.plan_deviation = data.get("plan_deviation")

                    logger.info(f"✅ [AI复盘] JSON 解析成功 - 总分: {result.overall_score}, 时机: {result.timing_score}, 仓位: {result.position_score}, 情绪: {result.emotion_score}, 归因: {result.attribution_score}, 纪律: {result.discipline_score}")
                    logger.info(f"✅ [AI复盘] 提取字段 - 摘要长度: {len(result.summary)}, 优点: {len(result.strengths)}, 不足: {len(result.weaknesses)}, 建议: {len(result.suggestions)}")
                    logger.info(f"✅ [AI复盘] 分析内容 - 时机: {len(result.timing_analysis)}字符, 仓位: {len(result.position_analysis)}字符, 情绪: {len(result.emotion_analysis)}字符, 归因: {len(result.attribution_analysis)}字符")
                    if result.plan_adherence or result.plan_deviation:
                        logger.info(f"✅ [AI复盘] 包含交易计划分析: adherence={bool(result.plan_adherence)}, deviation={bool(result.plan_deviation)}")
                except Exception as e:
                    import traceback
                    logger.warning(f"⚠️ [工作流复盘] 解析总结 JSON 失败: {e}")
                    logger.warning(f"⚠️ [工作流复盘] 完整堆栈:\n{traceback.format_exc()}")
                    logger.warning(f"⚠️ [工作流复盘] JSON 内容: {json_match.group(1)[:500]}")
            else:
                logger.warning(f"⚠️ [AI复盘] 未找到 JSON 匹配")

            # 如果没有提取到摘要，使用总结文本
            if not result.summary:
                result.summary = review_summary[:200] if len(review_summary) > 200 else review_summary

        # 计算理论最优收益
        if market_snapshot.period_high and trade_info.avg_buy_price:
            optimal_return = (market_snapshot.period_high - trade_info.avg_buy_price) / trade_info.avg_buy_price
            result.optimal_pnl = trade_info.total_buy_amount * optimal_return

        logger.info(f"✅ [工作流复盘] 解析完成 - 总分: {result.overall_score}")

        return result

    def _calculate_max_profit_pct(self, trade_info: TradeInfo, market_snapshot: MarketSnapshot) -> float:
        """计算最大可能盈利百分比"""
        if not market_snapshot.period_high or not trade_info.avg_buy_price:
            return 0.0
        return (market_snapshot.period_high - trade_info.avg_buy_price) / trade_info.avg_buy_price

    def _calculate_max_loss_pct(self, trade_info: TradeInfo, market_snapshot: MarketSnapshot) -> float:
        """计算最大可能亏损百分比"""
        if not market_snapshot.period_low or not trade_info.avg_buy_price:
            return 0.0
        return (market_snapshot.period_low - trade_info.avg_buy_price) / trade_info.avg_buy_price


# 单例模式
_trade_review_service: Optional[TradeReviewService] = None


def get_trade_review_service() -> TradeReviewService:
    """获取交易复盘服务实例"""
    global _trade_review_service
    if _trade_review_service is None:
        _trade_review_service = TradeReviewService()
    return _trade_review_service

