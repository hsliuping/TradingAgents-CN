"""
Tushare数据同步服务
负责将Tushare数据同步到MongoDB标准化集合
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
import logging

from tradingagents.dataflows.providers.china.tushare import TushareProvider
from app.services.stock_data_service import get_stock_data_service
from app.services.historical_data_service import get_historical_data_service
from app.services.news_data_service import get_news_data_service
from app.core.database import get_mongo_db
from app.core.config import settings
from app.core.rate_limiter import get_tushare_rate_limiter
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)

# UTC+8 时区
UTC_8 = timezone(timedelta(hours=8))


def get_utc8_now():
    """
    获取 UTC+8 当前时间（naive datetime）

    注意：返回 naive datetime（不带时区信息），MongoDB 会按原样存储本地时间值
    这样前端可以直接添加 +08:00 后缀显示
    """
    return now_tz().replace(tzinfo=None)


class TushareSyncService:
    """
    Tushare数据同步服务
    负责将Tushare数据同步到MongoDB标准化集合
    """
    
    def __init__(self):
        self.provider = TushareProvider()
        self.stock_service = get_stock_data_service()
        self.historical_service = None  # 延迟初始化
        self.news_service = None  # 延迟初始化
        self.db = get_mongo_db()
        self.settings = settings

        # 同步配置
        self.batch_size = 100  # 批量处理大小
        self.rate_limit_delay = 0.1  # API调用间隔(秒) - 已弃用，使用rate_limiter
        self.max_retries = 3  # 最大重试次数

        # 速率限制器（从环境变量读取配置）
        tushare_tier = getattr(settings, "TUSHARE_TIER", "standard")  # free/basic/standard/premium/vip
        safety_margin = float(getattr(settings, "TUSHARE_RATE_LIMIT_SAFETY_MARGIN", "0.8"))
        self.rate_limiter = get_tushare_rate_limiter(tier=tushare_tier, safety_margin=safety_margin)
    
    async def initialize(self):
        """初始化同步服务"""
        success = await self.provider.connect()
        if not success:
            raise RuntimeError("❌ Tushare连接失败，无法启动同步服务")

        # 初始化历史数据服务
        self.historical_service = await get_historical_data_service()

        # 初始化新闻数据服务
        self.news_service = await get_news_data_service()

        logger.info("✅ Tushare同步服务初始化完成")
    
    # ==================== 基础信息同步 ====================
    
    async def sync_stock_basic_info(self, force_update: bool = False, job_id: str = None) -> Dict[str, Any]:
        """
        同步股票基础信息

        Args:
            force_update: 是否强制更新所有数据
            job_id: 任务ID（用于进度跟踪）

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步股票基础信息...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "start_time": datetime.utcnow(),
            "errors": []
        }
        
        try:
            # 1. 从Tushare获取股票列表
            stock_list = await self.provider.get_stock_list(market="CN")
            if not stock_list:
                logger.error("❌ 无法获取股票列表")
                return stats
            
            stats["total_processed"] = len(stock_list)
            logger.info(f"📊 获取到 {len(stock_list)} 只股票信息")

            # 2. 批量处理
            for i in range(0, len(stock_list), self.batch_size):
                # 检查是否需要退出
                if job_id and await self._should_stop(job_id):
                    logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出...")
                    stats["stopped"] = True
                    break

                batch = stock_list[i:i + self.batch_size]
                batch_stats = await self._process_basic_info_batch(batch, force_update)

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["skipped_count"] += batch_stats["skipped_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志和进度更新
                progress = min(i + self.batch_size, len(stock_list))
                progress_percent = int((progress / len(stock_list)) * 100)
                logger.info(f"📈 基础信息同步进度: {progress}/{len(stock_list)} ({progress_percent}%) "
                           f"(成功: {stats['success_count']}, 错误: {stats['error_count']})")

                # 更新任务进度
                if job_id:
                    await self._update_progress(
                        job_id,
                        progress_percent,
                        f"已处理 {progress}/{len(stock_list)} 只股票"
                    )

                # API限流
                if i + self.batch_size < len(stock_list):
                    await asyncio.sleep(self.rate_limit_delay)
            
            # 3. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info(f"✅ 股票基础信息同步完成: "
                       f"总计 {stats['total_processed']} 只, "
                       f"成功 {stats['success_count']} 只, "
                       f"错误 {stats['error_count']} 只, "
                       f"跳过 {stats['skipped_count']} 只, "
                       f"耗时 {stats['duration']:.2f} 秒")
            
            # 🔥 更新任务状态为已完成（进度100%）
            if job_id:
                await self._update_progress(
                    job_id,
                    100,
                    f"同步完成：成功 {stats['success_count']}/{stats['total_processed']} 只股票"
                )
                # 显式更新状态为 completed
                await self._mark_task_completed(job_id, stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 股票基础信息同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_stock_basic_info"})
            
            # 🔥 更新任务状态为失败
            if job_id:
                try:
                    await self._mark_task_failed(job_id, str(e))
                except Exception as update_error:
                    logger.error(f"❌ 更新任务失败状态时出错: {update_error}")
            
            return stats
    
    async def _process_basic_info_batch(self, batch: List[Dict[str, Any]], force_update: bool) -> Dict[str, Any]:
        """处理基础信息批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "errors": []
        }
        
        for stock_info in batch:
            try:
                # 🔥 先转换为字典格式（如果是Pydantic模型）
                if hasattr(stock_info, 'model_dump'):
                    stock_data = stock_info.model_dump()
                elif hasattr(stock_info, 'dict'):
                    stock_data = stock_info.dict()
                else:
                    stock_data = stock_info

                code = stock_data["code"]

                # 检查是否需要更新
                if not force_update:
                    existing = await self.stock_service.get_stock_basic_info(code)
                    if existing:
                        # 🔥 existing 也可能是 Pydantic 模型，需要安全获取属性
                        existing_dict = existing.model_dump() if hasattr(existing, 'model_dump') else (existing.dict() if hasattr(existing, 'dict') else existing)
                        if self._is_data_fresh(existing_dict.get("updated_at"), hours=24):
                            batch_stats["skipped_count"] += 1
                            continue

                # 更新到数据库（指定数据源为 tushare）
                success = await self.stock_service.update_stock_basic_info(code, stock_data, source="tushare")
                if success:
                    batch_stats["success_count"] += 1
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": code,
                        "error": "数据库更新失败",
                        "context": "update_stock_basic_info"
                    })

            except Exception as e:
                batch_stats["error_count"] += 1
                # 🔥 安全获取 code（处理 Pydantic 模型和字典）
                try:
                    if hasattr(stock_info, 'code'):
                        code = stock_info.code
                    elif hasattr(stock_info, 'model_dump'):
                        code = stock_info.model_dump().get("code", "unknown")
                    elif hasattr(stock_info, 'dict'):
                        code = stock_info.dict().get("code", "unknown")
                    else:
                        code = stock_info.get("code", "unknown")
                except:
                    code = "unknown"

                batch_stats["errors"].append({
                    "code": code,
                    "error": str(e),
                    "context": "_process_basic_info_batch"
                })
        
        return batch_stats
    
    # ==================== 实时行情同步 ====================
    
    async def sync_realtime_quotes(self, symbols: List[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        同步实时行情数据

        策略：
        - 如果指定了少量股票（≤10只），自动切换到 AKShare 接口（避免浪费 Tushare rt_k 配额）
        - 如果指定了大量股票或全市场，使用 Tushare 批量接口一次性获取

        Args:
            symbols: 指定股票代码列表，为空则同步所有股票；如果指定了股票列表，则只保存这些股票的数据
            force: 是否强制执行（跳过交易时间检查），默认 False

        Returns:
            同步结果统计
        """
        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "start_time": datetime.utcnow(),
            "errors": [],
            "stopped_by_rate_limit": False,
            "skipped_non_trading_time": False,
            "switched_to_akshare": False  # 是否切换到 AKShare
        }

        try:
            # 检查是否在交易时间（手动同步时可以跳过检查）
            if not force and not self._is_trading_time():
                logger.info("⏸️ 当前不在交易时间，跳过实时行情同步（使用 force=True 可强制执行）")
                stats["skipped_non_trading_time"] = True
                return stats

            # 🔥 策略选择：少量股票切换到 AKShare，大量股票或全市场用 Tushare 批量接口
            USE_AKSHARE_THRESHOLD = 10  # 少于等于10只股票时切换到 AKShare

            if symbols and len(symbols) <= USE_AKSHARE_THRESHOLD:
                # 🔥 自动切换到 AKShare（避免浪费 Tushare rt_k 配额，每小时只能调用2次）
                logger.info(
                    f"💡 股票数量 ≤{USE_AKSHARE_THRESHOLD} 只，自动切换到 AKShare 接口"
                    f"（避免浪费 Tushare rt_k 配额，每小时只能调用2次）"
                )
                logger.info(f"🎯 使用 AKShare 同步 {len(symbols)} 只股票的实时行情: {symbols}")

                # 调用 AKShare 服务
                from app.worker.akshare_sync_service import get_akshare_sync_service
                akshare_service = await get_akshare_sync_service()

                if not akshare_service:
                    logger.error("❌ AKShare 服务不可用，回退到 Tushare 批量接口")
                    # 回退到 Tushare 批量接口
                    quotes_map = await self.provider.get_realtime_quotes_batch()
                    if quotes_map and symbols:
                        quotes_map = {symbol: quotes_map[symbol] for symbol in symbols if symbol in quotes_map}
                else:
                    # 使用 AKShare 同步
                    akshare_result = await akshare_service.sync_realtime_quotes(
                        symbols=symbols,
                        force=force
                    )
                    stats["switched_to_akshare"] = True
                    stats["success_count"] = akshare_result.get("success_count", 0)
                    stats["error_count"] = akshare_result.get("error_count", 0)
                    stats["total_processed"] = akshare_result.get("total_processed", 0)
                    stats["errors"] = akshare_result.get("errors", [])
                    stats["end_time"] = datetime.utcnow()
                    stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

                    logger.info(
                        f"✅ AKShare 实时行情同步完成: "
                        f"总计 {stats['total_processed']} 只, "
                        f"成功 {stats['success_count']} 只, "
                        f"错误 {stats['error_count']} 只, "
                        f"耗时 {stats['duration']:.2f} 秒"
                    )
                    return stats
            else:
                # 使用 Tushare 批量接口一次性获取全市场行情
                if symbols:
                    logger.info(f"📊 使用 Tushare 批量接口同步 {len(symbols)} 只股票的实时行情（从全市场数据中筛选）")
                else:
                    logger.info("📊 使用 Tushare 批量接口同步全市场实时行情...")

                logger.info("📡 调用 rt_k 批量接口获取全市场实时行情...")
                quotes_map = await self.provider.get_realtime_quotes_batch()

                if not quotes_map:
                    logger.warning("⚠️ 未获取到实时行情数据")
                    return stats

                logger.info(f"✅ 获取到 {len(quotes_map)} 只股票的实时行情")

                # 🔥 如果指定了股票列表，只处理这些股票
                if symbols:
                    # 过滤出指定的股票
                    filtered_quotes_map = {symbol: quotes_map[symbol] for symbol in symbols if symbol in quotes_map}

                    # 检查是否有股票未找到
                    missing_symbols = [s for s in symbols if s not in quotes_map]
                    if missing_symbols:
                        logger.warning(f"⚠️ 以下股票未在实时行情中找到: {missing_symbols}")

                    quotes_map = filtered_quotes_map
                    logger.info(f"🔍 过滤后保留 {len(quotes_map)} 只指定股票的行情")

            if not quotes_map:
                logger.warning("⚠️ 未获取到任何实时行情数据")
                return stats

            stats["total_processed"] = len(quotes_map)

            # 批量保存到数据库
            success_count = 0
            error_count = 0

            for symbol, quote_data in quotes_map.items():
                try:
                    # 保存到数据库
                    result = await self.stock_service.update_market_quotes(symbol, quote_data)
                    if result:
                        success_count += 1
                    else:
                        error_count += 1
                        stats["errors"].append({
                            "code": symbol,
                            "error": "更新数据库失败",
                            "context": "sync_realtime_quotes"
                        })
                except Exception as e:
                    error_count += 1
                    stats["errors"].append({
                        "code": symbol,
                        "error": str(e),
                        "context": "sync_realtime_quotes"
                    })

            stats["success_count"] = success_count
            stats["error_count"] = error_count

            # 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"✅ 实时行情同步完成: "
                      f"总计 {stats['total_processed']} 只, "
                      f"成功 {stats['success_count']} 只, "
                      f"错误 {stats['error_count']} 只, "
                      f"耗时 {stats['duration']:.2f} 秒")

            return stats

        except Exception as e:
            # 检查是否为限流错误
            error_msg = str(e)
            if self._is_rate_limit_error(error_msg):
                stats["stopped_by_rate_limit"] = True
                logger.error(f"❌ 实时行情同步失败（API限流）: {e}")
            else:
                logger.error(f"❌ 实时行情同步失败: {e}")

            stats["errors"].append({"error": str(e), "context": "sync_realtime_quotes"})
            return stats

    # 🔥 已废弃：不再使用 Tushare 单只接口（rt_k 每小时只能调用2次，太宝贵）
    # 少量股票（≤10只）自动切换到 AKShare 接口
    # async def _get_quotes_individually(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    #     """
    #     使用单只接口逐个获取股票实时行情（已废弃）
    #
    #     Args:
    #         symbols: 股票代码列表
    #
    #     Returns:
    #         Dict[symbol, quote_data]
    #     """
    #     quotes_map = {}
    #
    #     for symbol in symbols:
    #         try:
    #             quote_data = await self.provider.get_stock_quotes(symbol)
    #             if quote_data:
    #                 quotes_map[symbol] = quote_data
    #                 logger.info(f"✅ 获取 {symbol} 实时行情成功")
    #             else:
    #                 logger.warning(f"⚠️ 未获取到 {symbol} 的实时行情")
    #         except Exception as e:
    #             logger.error(f"❌ 获取 {symbol} 实时行情失败: {e}")
    #             continue
    #
    #     logger.info(f"✅ 单只接口获取完成，成功 {len(quotes_map)}/{len(symbols)} 只")
    #     return quotes_map

    async def _process_quotes_batch(self, batch: List[str]) -> Dict[str, Any]:
        """处理行情批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "rate_limit_hit": False
        }

        # 并发获取行情数据
        tasks = []
        for symbol in batch:
            task = self._get_and_save_quotes(symbol)
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = str(result)
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": batch[i],
                    "error": error_msg,
                    "context": "_process_quotes_batch"
                })

                # 检测 API 限流错误
                if self._is_rate_limit_error(error_msg):
                    batch_stats["rate_limit_hit"] = True
                    logger.warning(f"⚠️ 检测到 API 限流错误: {error_msg}")

            elif result:
                batch_stats["success_count"] += 1
            else:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": batch[i],
                    "error": "获取行情数据失败",
                    "context": "_process_quotes_batch"
                })

        return batch_stats

    def _is_rate_limit_error(self, error_msg: str) -> bool:
        """检测是否为 API 限流错误"""
        rate_limit_keywords = [
            "每分钟最多访问",
            "每分钟最多",
            "rate limit",
            "too many requests",
            "访问频率",
            "请求过于频繁"
        ]
        error_msg_lower = error_msg.lower()
        return any(keyword in error_msg_lower for keyword in rate_limit_keywords)

    def _is_trading_time(self) -> bool:
        """
        判断当前是否在交易时间
        A股交易时间：
        - 周一到周五（排除节假日）
        - 上午：9:30-11:30
        - 下午：13:00-15:00

        注意：此方法不检查节假日，仅检查时间段
        """
        from datetime import datetime
        import pytz

        # 使用上海时区
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)

        # 检查是否是周末
        if now.weekday() >= 5:  # 5=周六, 6=周日
            return False

        # 检查时间段
        current_time = now.time()

        # 上午交易时间：9:30-11:30
        morning_start = datetime.strptime("09:30", "%H:%M").time()
        morning_end = datetime.strptime("11:30", "%H:%M").time()

        # 下午交易时间：13:00-15:00
        afternoon_start = datetime.strptime("13:00", "%H:%M").time()
        afternoon_end = datetime.strptime("15:00", "%H:%M").time()

        # 判断是否在交易时间段内
        is_morning = morning_start <= current_time <= morning_end
        is_afternoon = afternoon_start <= current_time <= afternoon_end

        return is_morning or is_afternoon

    async def _get_and_save_quotes(self, symbol: str) -> bool:
        """获取并保存单个股票行情"""
        try:
            quotes = await self.provider.get_stock_quotes(symbol)
            if quotes:
                # 转换为字典格式（如果是Pydantic模型）
                if hasattr(quotes, 'model_dump'):
                    quotes_data = quotes.model_dump()
                elif hasattr(quotes, 'dict'):
                    quotes_data = quotes.dict()
                else:
                    quotes_data = quotes

                return await self.stock_service.update_market_quotes(symbol, quotes_data)
            return False
        except Exception as e:
            error_msg = str(e)
            # 检测限流错误，直接抛出让上层处理
            if self._is_rate_limit_error(error_msg):
                logger.error(f"❌ 获取 {symbol} 行情失败（限流）: {e}")
                raise  # 抛出限流错误
            logger.error(f"❌ 获取 {symbol} 行情失败: {e}")
            return False

    # ==================== 历史数据同步 ====================

    async def sync_historical_data(
        self,
        symbols: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        incremental: bool = True,
        all_history: bool = False,
        period: str = "daily",
        job_id: str = None,
        auto_retry: bool = True,  # 🔥 新增：是否自动重试失败的股票（默认开启）
        max_auto_retries: int = 1,  # 🔥 新增：最大自动重试次数（默认1次，避免无限重试）
        **kwargs  # 🔥 接收额外的kwargs，包括恢复位置信息
    ) -> Dict[str, Any]:
        """
        同步历史数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            incremental: 是否增量同步
            all_history: 是否同步所有历史数据
            period: 数据周期 (daily/weekly/monthly)
            job_id: 任务ID（用于进度跟踪）
            auto_retry: 是否自动重试失败的股票（默认True）
                       - True: 全部数据同步完成后，自动检查并重试可重试的错误
                       - False: 不自动重试，需要手动调用重试API
            max_auto_retries: 最大自动重试次数（默认1次，避免无限重试）
                            - 重试策略：全部数据同步完成后，自动重试可重试的错误
                            - 只重试标记为"可重试"的错误（网络错误、API超时等）
                            - 跳过无数据的错误（股票不存在、日期范围不合理等）
                            - 如果某一轮重试没有成功，停止重试
                            - 如果所有可重试的错误都已解决，停止重试

        Returns:
            同步结果统计
        """
        period_name = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(period, period)
        logger.info(f"🔄 开始同步{period_name}历史数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "start_time": datetime.utcnow(),
            "errors": []
        }

        try:
            # 1. 获取股票列表（排除退市股票）
            if symbols is None:
                try:
                    # 🔥 使用聚合查询去重，确保每个股票代码只计算一次
                    # 因为同一个股票可能来自多个数据源（tushare、akshare、baostock），会有重复记录
                    pipeline = [
                        {
                            "$match": {
                                "$and": [
                                    {
                                        "$or": [
                                            {"market_info.market": "CN"},  # 新数据结构
                                            {"category": "stock_cn"},      # 旧数据结构
                                            {"market": {"$in": ["主板", "创业板", "科创板", "北交所"]}}  # 按市场类型
                                        ]
                                    },
                                    # 排除退市股票
                                    {
                                        "$or": [
                                            {"status": {"$ne": "D"}},  # status 不是 D（退市）
                                            {"status": {"$exists": False}}  # 或者 status 字段不存在
                                        ]
                                    }
                                ]
                            }
                        },
                        {
                            "$group": {
                                "_id": "$code"  # 按股票代码分组去重
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "code": "$_id"
                            }
                        }
                    ]
                    cursor = self.db.stock_basic_info.aggregate(pipeline)
                    symbols = [doc["code"] async for doc in cursor]
                    logger.info(f"📋 从 stock_basic_info 获取到 {len(symbols)} 只唯一股票（已去重，已排除退市股票）")
                except Exception as e:
                    logger.error(f"❌ 获取股票列表失败，使用备用方法: {e}", exc_info=True)
                    # 备用方法：使用 find() 查询（可能包含重复）
                    cursor = self.db.stock_basic_info.find(
                        {
                            "$and": [
                                {
                                    "$or": [
                                        {"market_info.market": "CN"},
                                        {"category": "stock_cn"},
                                        {"market": {"$in": ["主板", "创业板", "科创板", "北交所"]}}
                                    ]
                                },
                                {
                                    "$or": [
                                        {"status": {"$ne": "D"}},
                                        {"status": {"$exists": False}}
                                    ]
                                }
                            ]
                        },
                        {"code": 1}
                    )
                    symbols = list(set([doc["code"] async for doc in cursor]))  # 使用 set 去重
                    logger.warning(f"⚠️ 使用备用方法获取到 {len(symbols)} 只股票（已去重）")

            stats["total_processed"] = len(symbols)

            # 2. 确定全局结束日期
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')

            # 🔥 增量同步时间检查：如果增量同步且结束日期是今天，且当前时间在18:00之前，则跳过同步
            if incremental and end_date == datetime.now().strftime('%Y-%m-%d'):
                current_time = datetime.now()
                cutoff_time = current_time.replace(hour=18, minute=0, second=0, microsecond=0)
                
                if current_time < cutoff_time:
                    skip_message = (
                        f"⏰ 增量同步跳过：当前时间 {current_time.strftime('%H:%M:%S')} 早于 18:00，"
                        f"数据源可能还没有当天的数据。建议在 18:00 之后执行增量同步。"
                    )
                    logger.info(skip_message)
                    stats["skipped"] = True
                    stats["skip_reason"] = skip_message
                    return {
                        "success": True,
                        "skipped": True,
                        "message": skip_message,
                        "stats": stats
                    }

            # 3. 确定全局起始日期（仅用于日志显示）
            global_start_date = start_date
            if not global_start_date:
                if all_history:
                    global_start_date = "1990-01-01"
                elif incremental:
                    global_start_date = "各股票最后日期"
                else:
                    global_start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            logger.info(f"📊 历史数据同步: 结束日期={end_date}, 股票数量={len(symbols)}, 模式={'增量' if incremental else '全量'}")

            # 🔥 检查是否有挂起的执行记录，如果有则从上次的进度位置继续
            resume_from_index = 0
            
            # 🔥 方法1：优先从kwargs中读取恢复位置（恢复操作时传递的）
            if kwargs and "_resume_from_index" in kwargs:
                resume_from_index = kwargs.get("_resume_from_index", 0)
                logger.info(f"🔄 从kwargs中读取恢复位置: {resume_from_index}")
            
            # 🔥 方法2：如果没有从kwargs获取到，则查找执行记录（兼容旧逻辑）
            if resume_from_index == 0 and job_id:
                try:
                    # 查找挂起或运行中的执行记录
                    suspended_execution = await self.db.scheduler_executions.find_one(
                        {"job_id": job_id, "status": {"$in": ["suspended", "running"]}},
                        sort=[("timestamp", -1)]
                    )
                    
                    if suspended_execution:
                        processed_items = suspended_execution.get("processed_items")
                        logger.info(f"📊 查找执行记录: execution_id={suspended_execution.get('_id')}, status={suspended_execution.get('status')}, processed_items={processed_items}, total_items={suspended_execution.get('total_items')}")
                        
                        if processed_items is not None and processed_items > 0:
                            resume_from_index = processed_items
                            logger.info(f"🔄 从执行记录中读取恢复位置: {resume_from_index}（已处理 {processed_items}/{len(symbols)}）")
                        else:
                            logger.warning(f"⚠️ 执行记录中没有有效的 processed_items ({processed_items})，将从0开始执行")
                    else:
                        logger.info(f"📊 未找到挂起或运行中的执行记录，将从0开始执行")
                except Exception as e:
                    logger.warning(f"⚠️ 检查挂起任务失败，从开始执行: {e}", exc_info=True)
            
            logger.info(f"🚀 历史数据同步开始: 总股票数={len(symbols)}, 从第 {resume_from_index} 个开始, 将处理 {len(symbols) - resume_from_index} 个股票")
            
            # 4. 批量处理（从上次的进度位置继续）
            for i in range(resume_from_index, len(symbols)):
                symbol = symbols[i]
                # 记录单个股票开始时间
                stock_start_time = datetime.now()

                try:
                    # 检查是否需要退出
                    if job_id and await self._should_stop(job_id):
                        logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出...")
                        stats["stopped"] = True
                        break

                    # 速率限制
                    await self.rate_limiter.acquire()

                    # 确定该股票的起始日期
                    symbol_start_date = start_date
                    if not symbol_start_date:
                        if all_history:
                            symbol_start_date = "1990-01-01"
                        elif incremental:
                            # 增量同步：获取该股票的最后日期
                            symbol_start_date = await self._get_last_sync_date(symbol)
                            logger.debug(f"📅 {symbol}: 从 {symbol_start_date} 开始同步")
                            
                            # 🔥 检查 start_date 是否大于 end_date（避免无效的日期范围）
                            if symbol_start_date > end_date:
                                logger.warning(
                                    f"⚠️ {symbol}: 开始日期 {symbol_start_date} 大于结束日期 {end_date}，"
                                    f"可能数据库中的最新日期已经是今天或更晚，跳过该股票"
                                )
                                stats["skipped_count"] = stats.get("skipped_count", 0) + 1
                                continue
                        else:
                            symbol_start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

                    # 🔥 再次检查 start_date 是否大于 end_date（双重保险）
                    if symbol_start_date > end_date:
                        logger.warning(
                            f"⚠️ {symbol}: 开始日期 {symbol_start_date} 大于结束日期 {end_date}，跳过该股票"
                        )
                        stats["skipped_count"] = stats.get("skipped_count", 0) + 1
                        continue

                    # 记录请求参数
                    logger.debug(
                        f"🔍 {symbol}: 请求{period_name}数据 "
                        f"start={symbol_start_date}, end={end_date}, period={period}"
                    )

                    # 🔍 检查 Tushare 连接状态，如果不可用则尝试重新连接
                    if not self.provider.is_available():
                        logger.warning(f"⚠️ {symbol}: Tushare连接不可用，尝试重新连接...")
                        try:
                            reconnect_success = await self.provider.connect()
                            if reconnect_success:
                                logger.info(f"✅ {symbol}: Tushare重新连接成功")
                            else:
                                logger.error(f"❌ {symbol}: Tushare重新连接失败，跳过该股票")
                                stats["error_count"] += 1
                                continue
                        except Exception as reconnect_error:
                            logger.error(f"❌ {symbol}: Tushare重新连接异常: {reconnect_error}")
                            stats["error_count"] += 1
                            continue

                    # ⏱️ 性能监控：API 调用
                    api_start = datetime.now()
                    try:
                        logger.debug(f"🔍 [sync_historical_data] 准备调用 get_historical_data: symbol={symbol}, start={symbol_start_date}, end={end_date}, period={period}")
                        df = await self.provider.get_historical_data(symbol, symbol_start_date, end_date, period=period)
                        api_duration = (datetime.now() - api_start).total_seconds()
                        logger.debug(f"🔍 [sync_historical_data] get_historical_data 返回: df={'None' if df is None else ('空' if df.empty else f'{len(df)}行')}, 耗时={api_duration:.3f}秒")
                    except Exception as api_error:
                        api_duration = (datetime.now() - api_start).total_seconds()
                        import traceback
                        error_details = traceback.format_exc()
                        stock_duration = (datetime.now() - stock_start_time).total_seconds()
                        
                        # 详细记录 API 调用异常
                        logger.error(
                            f"❌ {symbol}: Tushare API 调用异常\n"
                            f"   请求参数:\n"
                            f"     - symbol: {symbol}\n"
                            f"     - ts_code: {self._get_ts_code(symbol)}\n"
                            f"     - start_date: {symbol_start_date}\n"
                            f"     - end_date: {end_date}\n"
                            f"     - period: {period}\n"
                            f"   错误类型: {type(api_error).__name__}\n"
                            f"   错误信息: {str(api_error)}\n"
                            f"   API 调用耗时: {api_duration:.2f}秒\n"
                            f"   总耗时: {stock_duration:.2f}秒\n"
                            f"   堆栈跟踪:\n{error_details}"
                        )
                        
                        stats["error_count"] += 1
                        stats["errors"].append({
                            "code": symbol,
                            "error": str(api_error),
                            "error_type": type(api_error).__name__,
                            "context": f"tushare_api_call_{period}",
                            "traceback": error_details,
                            "api_params": {
                                "symbol": symbol,
                                "start_date": symbol_start_date,
                                "end_date": end_date,
                                "period": period
                            }
                        })
                        continue

                    if df is not None and not df.empty:
                        # ⏱️ 性能监控：数据保存
                        save_start = datetime.now()
                        records_saved = await self._save_historical_data(symbol, df, period=period)
                        save_duration = (datetime.now() - save_start).total_seconds()

                        stats["success_count"] += 1
                        stats["total_records"] += records_saved

                        # 计算单个股票耗时
                        stock_duration = (datetime.now() - stock_start_time).total_seconds()
                        logger.info(
                            f"✅ {symbol}: 保存 {records_saved} 条{period_name}记录，"
                            f"总耗时 {stock_duration:.2f}秒 "
                            f"(API: {api_duration:.2f}秒, 保存: {save_duration:.2f}秒)"
                        )
                    else:
                        stock_duration = (datetime.now() - stock_start_time).total_seconds()
                        
                        # 详细记录无数据的原因
                        ts_code = self._get_ts_code(symbol)
                        list_date = self._get_list_date(symbol)
                        
                        # 🔍 检查股票是否存在于数据库中
                        stock_exists = await self._check_stock_exists(symbol)
                        
                        # 🔥 判断是否为"无数据"（不应该重试）还是"真正失败"（可以重试）
                        is_no_data = False  # 默认为可以重试
                        likely_reason = ""
                        
                        # 根据API调用耗时判断可能的原因
                        if api_duration < 0.01:
                            # API调用耗时极短（<10ms），可能是快速失败
                            likely_reason = "Tushare API 快速失败（可能是参数验证失败或股票代码不存在）"
                            # 这种情况可能是真正失败，也可能是无数据，需要进一步判断
                            if not stock_exists:
                                is_no_data = True  # 股票不存在，可能是无数据
                        elif not stock_exists:
                            likely_reason = "股票代码在数据库中不存在（可能已退市或代码错误）"
                            is_no_data = True  # 股票不存在，应该是无数据
                        elif list_date == "未知":
                            likely_reason = "无法获取股票上市日期，可能股票信息不完整"
                            # 这种情况可能是真正失败，也可能是无数据
                        else:
                            # 检查日期范围是否合理
                            try:
                                from datetime import datetime as dt
                                start_dt = dt.strptime(symbol_start_date, '%Y-%m-%d')
                                end_dt = dt.strptime(end_date, '%Y-%m-%d')
                                list_dt = dt.strptime(list_date, '%Y-%m-%d') if list_date != "未知" else None
                                
                                if list_dt and start_dt < list_dt:
                                    likely_reason = f"开始日期({symbol_start_date})早于上市日期({list_date})"
                                    is_no_data = True  # 日期范围不合理，应该是无数据
                                elif end_dt < start_dt:
                                    likely_reason = f"结束日期({end_date})早于开始日期({symbol_start_date})"
                                    is_no_data = True  # 日期范围不合理，应该是无数据
                                else:
                                    # 检查是否是北交所股票（9字开头），这些股票可能确实没有数据
                                    if symbol.startswith('9') or symbol.startswith('8'):
                                        likely_reason = f"北交所/新三板股票({symbol})，可能在此期间无交易数据"
                                        is_no_data = True  # 北交所股票，可能是无数据
                                    else:
                                        likely_reason = "该股票在此期间无交易数据（可能停牌、退市或数据源问题）"
                                        # 其他情况，可能是真正失败，也可能是无数据，保守判断为无数据
                                        is_no_data = True
                            except:
                                likely_reason = "日期范围可能有问题"
                                is_no_data = True  # 日期解析失败，可能是无数据
                        
                        # 🔥 记录错误信息，标记错误类型
                        error_info = {
                            "code": symbol,
                            "error": f"无{period_name}数据: {likely_reason}",
                            "error_type": "no_data" if is_no_data else "api_error",
                            "error_category": "no_data" if is_no_data else "retryable_error",  # 🔥 新增：错误分类
                            "context": f"sync_historical_data_{period}_no_data",
                            "api_duration": api_duration,
                            "likely_reason": likely_reason,
                            "stock_exists": stock_exists,
                            "list_date": list_date
                        }
                        
                        # 只有真正失败的情况才计入 error_count（可以重试）
                        # 无数据的情况不计入 error_count，但记录在 errors 中用于统计
                        if not is_no_data:
                            stats["error_count"] += 1
                        
                        stats["errors"].append(error_info)
                        
                        logger.warning(
                            f"⚠️ {symbol}: 无{period_name}数据 ({'无数据，不重试' if is_no_data else 'API错误，可重试'})\n"
                            f"   请求参数:\n"
                            f"     - symbol: {symbol}\n"
                            f"     - ts_code: {ts_code}\n"
                            f"     - start_date: {symbol_start_date}\n"
                            f"     - end_date: {end_date}\n"
                            f"     - period: {period}\n"
                            f"   API 返回: {'None' if df is None else '空 DataFrame'}\n"
                            f"   API 调用耗时: {api_duration:.2f}秒\n"
                            f"   总耗时: {stock_duration:.2f}秒\n"
                            f"   股票状态: {'✅ 存在于数据库' if stock_exists else '❌ 数据库中不存在'}\n"
                            f"   上市日期: {list_date}\n"
                            f"   🔍 最可能的原因: {likely_reason}\n"
                            f"   💡 其他可能原因:\n"
                            f"     1) 该股票在此期间无交易数据（停牌、退市、未上市）\n"
                            f"     2) 日期范围超出股票交易历史\n"
                            f"     3) 股票代码格式错误或 Tushare 中不存在\n"
                            f"     4) Tushare API 限制或积分不足\n"
                            f"     5) 网络连接问题或 API 服务异常"
                        )

                    # 每个股票都更新进度（考虑从上次位置继续的情况）
                    # i 是当前索引（从resume_from_index开始），需要转换为实际进度
                    actual_index = i + 1  # 实际处理的索引（从1开始）
                    
                    # 🔥 修复：进度应该反映"已处理的股票数"，而不是"成功同步的股票数"
                    # 这样用户可以看到处理进度，即使某些股票失败
                    # 但最终完成时，mark_job_completed 会根据 success_count 计算最终进度
                    processed_count = actual_index  # 已处理的股票数（包括成功和失败的）
                    progress_percent = int((processed_count / len(symbols)) * 100)

                    # 更新任务进度
                    if job_id:
                        from app.services.scheduler_service import update_job_progress, TaskCancelledException
                        try:
                            await update_job_progress(
                                job_id=job_id,
                                progress=progress_percent,
                                message=f"正在同步 {symbol} ({processed_count}/{len(symbols)}, 成功: {stats['success_count']})",
                                current_item=symbol,
                                total_items=len(symbols),
                                processed_items=processed_count  # 已处理的（包括成功和失败的）
                            )
                        except TaskCancelledException:
                            # 任务被取消，记录并退出
                            logger.warning(f"⚠️ 历史数据同步任务被用户取消 (已处理 {i + 1}/{len(symbols)})")
                            stats["end_time"] = datetime.utcnow()
                            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
                            stats["cancelled"] = True
                            raise

                    # 每50个股票输出一次详细日志
                    if actual_index % 50 == 0 or actual_index == len(symbols):
                        logger.info(f"📈 {period_name}数据同步进度: {actual_index}/{len(symbols)} ({progress_percent}%) "
                                   f"(成功: {stats['success_count']}, 记录: {stats['total_records']})")

                        # 输出速率限制器统计
                        limiter_stats = self.rate_limiter.get_stats()
                        logger.info(f"   速率限制: {limiter_stats['current_calls']}/{limiter_stats['max_calls']}次, "
                                   f"等待次数: {limiter_stats['total_waits']}, "
                                   f"总等待时间: {limiter_stats['total_wait_time']:.1f}秒")

                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    
                    # 🔥 判断异常类型，区分"真正失败"（可重试）和"无数据"（不重试）
                    error_type_name = type(e).__name__
                    error_message = str(e)
                    
                    # 判断是否为可重试的错误
                    is_retryable = True  # 默认可重试
                    error_category = "retryable_error"
                    
                    # 某些异常类型通常表示真正失败，可以重试
                    retryable_exceptions = [
                        "ConnectionError", "TimeoutError", "HTTPError", 
                        "RequestException", "APIError", "RateLimitError"
                    ]
                    
                    # 某些错误消息可能表示无数据，不应该重试
                    no_data_keywords = [
                        "no data", "无数据", "empty", "不存在", 
                        "not found", "invalid", "参数错误"
                    ]
                    
                    if any(keyword in error_message.lower() for keyword in no_data_keywords):
                        is_retryable = False
                        error_category = "no_data"
                    elif error_type_name not in retryable_exceptions:
                        # 如果不是常见的网络/API错误，可能是数据问题，保守判断为无数据
                        is_retryable = False
                        error_category = "no_data"
                    
                    stats["error_count"] += 1  # 异常情况都计入 error_count
                    stats["errors"].append({
                        "code": symbol,
                        "error": error_message,
                        "error_type": error_type_name,
                        "error_category": error_category,  # 🔥 新增：错误分类
                        "is_retryable": is_retryable,  # 🔥 新增：是否可重试
                        "context": f"sync_historical_data_{period}",
                        "traceback": error_details
                    })
                    logger.error(
                        f"❌ {symbol} {period_name}数据同步失败 ({'可重试' if is_retryable else '无数据，不重试'})\n"
                        f"   参数: start={symbol_start_date if 'symbol_start_date' in locals() else 'N/A'}, "
                        f"end={end_date}, period={period}\n"
                        f"   错误类型: {error_type_name}\n"
                        f"   错误信息: {error_message}\n"
                        f"   堆栈跟踪:\n{error_details}"
                    )

            # 4. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"✅ {period_name}数据同步完成: "
                       f"股票 {stats['success_count']}/{stats['total_processed']}, "
                       f"记录 {stats['total_records']} 条, "
                       f"错误 {stats['error_count']} 个, "
                       f"耗时 {stats['duration']:.2f} 秒")

            # 🔥 自动重试失败的股票（如果启用且不是重试任务本身）
            # 策略：全部数据同步完成后，自动检查并重试可重试的错误
            if auto_retry and max_auto_retries > 0 and not kwargs.get("_is_retry", False):
                retryable_errors = [
                    error for error in stats.get("errors", [])
                    if error.get("error_category") == "retryable_error" 
                    or error.get("is_retryable", False)
                ]
                
                if retryable_errors:
                    logger.info(f"🔄 检测到 {len(retryable_errors)} 个可重试的错误，开始自动重试（最多 {max_auto_retries} 次）...")
                    
                    # 记录重试前的统计
                    initial_success_count = stats["success_count"]
                    initial_error_count = len(retryable_errors)
                    
                    # 执行自动重试（最多 max_auto_retries 次）
                    for retry_round in range(1, max_auto_retries + 1):
                        # 获取当前可重试的错误（只重试标记为可重试的错误）
                        current_retryable = [
                            error for error in stats.get("errors", [])
                            if error.get("error_category") == "retryable_error" 
                            or error.get("is_retryable", False)
                        ]
                        
                        if not current_retryable:
                            logger.info(f"✅ 第 {retry_round} 轮重试：没有可重试的错误了")
                            break
                        
                        logger.info(f"🔄 第 {retry_round}/{max_auto_retries} 轮自动重试：{len(current_retryable)} 只股票")
                        
                        # 调用重试方法（标记为自动重试，避免递归）
                        retry_result = await self.retry_failed_symbols(
                            errors=current_retryable,
                            start_date=start_date,
                            end_date=end_date,
                            period=period,
                            job_id=f"{job_id}_auto_retry_{retry_round}" if job_id else None,
                            _is_retry=True  # 标记为重试任务，避免再次自动重试
                        )
                        
                        # 更新主统计信息：累加重试成功的股票数和记录数
                        stats["success_count"] += retry_result.get("success_count", 0)
                        stats["total_records"] += retry_result.get("total_records", 0)
                        
                        # 更新错误列表：移除已成功的股票的错误，保留仍然失败的
                        # 重试成功的股票会从 errors 中移除（因为 retry_result 中不会包含它们的错误）
                        retry_symbols = set([e["code"] for e in current_retryable])
                        successful_symbols = set()
                        
                        # 从重试结果推断成功的股票（如果重试成功，该股票不会出现在新的错误列表中）
                        # 简化处理：如果重试成功数 > 0，说明有股票成功了
                        # 但由于无法精确知道哪些股票成功，我们保留所有错误，让下一轮重试时自然过滤
                        
                        # 如果这轮重试没有新的成功，停止重试
                        if retry_result.get("success_count", 0) == 0:
                            logger.info(f"⚠️ 第 {retry_round} 轮重试没有成功，停止自动重试")
                            break
                        
                        # 更新错误列表：移除重试成功的股票的错误
                        # 由于 retry_result 会返回新的错误列表，我们需要合并
                        # 简化处理：保留原有的无数据错误，移除已重试成功的股票的错误
                        updated_errors = []
                        retry_success_count = retry_result.get("success_count", 0)
                        retry_failed_symbols = set()
                        
                        # 从重试结果中提取失败的股票（如果有错误列表）
                        if retry_result.get("errors"):
                            retry_failed_symbols = set([e.get("code") for e in retry_result.get("errors", [])])
                        
                        # 更新错误列表
                        for error in stats.get("errors", []):
                            error_code = error.get("code")
                            # 如果是可重试的错误，且不在重试失败的列表中，说明重试成功了，移除它
                            if (error.get("error_category") == "retryable_error" or error.get("is_retryable", False)):
                                if error_code not in retry_failed_symbols and error_code in retry_symbols:
                                    # 重试成功，移除错误
                                    continue
                            # 其他错误（无数据等）保留
                            updated_errors.append(error)
                        
                        # 添加重试后仍然失败的错误
                        if retry_result.get("errors"):
                            updated_errors.extend(retry_result.get("errors", []))
                        
                        stats["errors"] = updated_errors
                        
                        # 如果所有可重试的错误都已解决，停止重试
                        remaining_retryable = [
                            error for error in stats.get("errors", [])
                            if error.get("error_category") == "retryable_error" 
                            or error.get("is_retryable", False)
                        ]
                        if not remaining_retryable:
                            logger.info(f"✅ 所有可重试的错误已解决，停止自动重试")
                            break
                    
                    # 记录自动重试统计
                    final_success_count = stats["success_count"]
                    retry_success_count = final_success_count - initial_success_count
                    logger.info(f"✅ 自动重试完成: 共 {retry_round} 轮，"
                               f"重试 {initial_error_count} 只股票，"
                               f"成功 {retry_success_count} 只，"
                               f"剩余可重试错误 {len([e for e in stats.get('errors', []) if e.get('error_category') == 'retryable_error' or e.get('is_retryable', False)])} 个")
                    
                    # 更新最终统计
                    stats["auto_retry_stats"] = {
                        "retry_rounds": retry_round,
                        "initial_retryable_errors": initial_error_count,
                        "retry_success_count": retry_success_count
                    }

            # 🔥 更新任务状态为已完成（如果有 job_id）
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed, update_job_progress
                    
                    # 🔥 在调用 mark_job_completed 之前，先更新一次进度
                    # 使用成功同步的股票数来计算最终进度，而不是已处理的股票数
                    if stats.get("total_processed", 0) > 0:
                        success_count = stats.get("success_count", 0)
                        total_processed = stats.get("total_processed", 0)
                        final_progress = int((success_count / total_processed) * 100)
                        final_progress = max(0, min(100, final_progress))
                        
                        # 更新进度为实际成功进度
                        try:
                            await update_job_progress(
                                job_id=job_id,
                                progress=final_progress,
                                message=f"同步完成：成功 {success_count}/{total_processed} 只股票",
                                total_items=total_processed,
                                processed_items=total_processed  # 已处理的（包括成功和失败的）
                            )
                        except Exception as progress_error:
                            logger.warning(f"⚠️ 更新最终进度时出错: {progress_error}")
                    
                    error_message = None
                    if stats.get("error_count", 0) > 0:
                        error_messages = [e.get("error", "") for e in stats.get("errors", [])[:5]]
                        error_message = f"同步完成但有 {stats.get('error_count', 0)} 个错误: {', '.join(error_messages)}"
                    await mark_job_completed(job_id, stats, error_message)
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务完成状态时出错: {update_error}")

            return stats

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(
                f"❌ 历史数据同步失败（外层异常）\n"
                f"   错误类型: {type(e).__name__}\n"
                f"   错误信息: {str(e)}\n"
                f"   堆栈跟踪:\n{error_details}"
            )
            stats["errors"].append({
                "error": str(e),
                "error_type": type(e).__name__,
                "context": "sync_historical_data",
                "traceback": error_details
            })
            
            # 🔥 更新任务状态为失败（如果有 job_id）
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    await mark_job_completed(job_id, None, str(e))
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务失败状态时出错: {update_error}")
            
            return stats

    async def _save_historical_data(self, symbol: str, df, period: str = "daily") -> int:
        """保存历史数据到数据库"""
        try:
            if self.historical_service is None:
                self.historical_service = await get_historical_data_service()

            # 使用统一历史数据服务保存（指定周期）
            saved_count = await self.historical_service.save_historical_data(
                symbol=symbol,
                data=df,
                data_source="tushare",
                market="CN",
                period=period
            )

            return saved_count

        except Exception as e:
            logger.error(f"❌ 保存{period}数据失败 {symbol}: {e}")
            return 0

    def _get_ts_code(self, symbol: str) -> str:
        """
        获取 Tushare 格式的股票代码（ts_code）
        
        Args:
            symbol: 股票代码（如 300750）
            
        Returns:
            Tushare 格式代码（如 300750.SZ）
        """
        try:
            # 简单的转换逻辑：根据代码前缀判断市场
            if symbol.startswith(('60', '68')):
                return f"{symbol}.SH"
            elif symbol.startswith(('00', '30')):
                return f"{symbol}.SZ"
            elif symbol.startswith('8'):
                return f"{symbol}.BJ"  # 北交所
            else:
                return f"{symbol}.SZ"  # 默认深交所
        except:
            return f"{symbol}.SZ"
    
    def _get_list_date(self, symbol: str) -> str:
        """
        获取股票上市日期
        
        Args:
            symbol: 股票代码
            
        Returns:
            上市日期字符串，如果未找到则返回 "未知"
        """
        try:
            # 尝试从数据库查询上市日期（同步查询，因为这是辅助方法）
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用同步客户端
                    from pymongo import MongoClient
                    from app.core.config import settings
                    sync_client = MongoClient(settings.MONGO_URI)
                    sync_db = sync_client[settings.MONGODB_DATABASE]
                    stock_info = sync_db.stock_basic_info.find_one(
                        {"code": symbol},
                        {"list_date": 1}
                    )
                    sync_client.close()
                    if stock_info and stock_info.get("list_date"):
                        list_date = stock_info["list_date"]
                        if isinstance(list_date, str):
                            if len(list_date) == 8 and list_date.isdigit():
                                return f"{list_date[:4]}-{list_date[4:6]}-{list_date[6:]}"
                            return list_date
                        else:
                            return list_date.strftime('%Y-%m-%d')
            except:
                pass
            return "未知"
        except:
            return "未知"
    
    async def _check_stock_exists(self, symbol: str) -> bool:
        """
        检查股票是否存在于数据库中
        
        Args:
            symbol: 股票代码
            
        Returns:
            True 如果股票存在，False 否则
        """
        try:
            stock_info = await self.db.stock_basic_info.find_one(
                {"code": symbol},
                {"code": 1}  # 只查询 code 字段，提高性能
            )
            return stock_info is not None
        except Exception as e:
            logger.debug(f"检查股票 {symbol} 是否存在时出错: {e}")
            return False  # 出错时返回 False，不影响主流程
    
    async def _get_last_sync_date(self, symbol: str = None) -> str:
        """
        获取最后同步日期

        Args:
            symbol: 股票代码，如果提供则返回该股票的最后日期+1天

        Returns:
            日期字符串 (YYYY-MM-DD)
        """
        try:
            if self.historical_service is None:
                self.historical_service = await get_historical_data_service()

            if symbol:
                # 获取特定股票的最新日期
                latest_date = await self.historical_service.get_latest_date(symbol, "tushare")
                if latest_date:
                    # 返回最后日期的下一天（避免重复同步）
                    try:
                        last_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
                        next_date = last_date_obj + timedelta(days=1)
                        next_date_str = next_date.strftime('%Y-%m-%d')
                        
                        # 🔥 如果加1天后的日期已经超过今天，则返回今天（避免 start_date > end_date）
                        today_str = datetime.now().strftime('%Y-%m-%d')
                        if next_date_str > today_str:
                            logger.debug(
                                f"📅 {symbol}: 数据库最新日期 {latest_date} +1天 = {next_date_str} "
                                f"已超过今天 {today_str}，返回今天作为开始日期"
                            )
                            return today_str
                        
                        return next_date_str
                    except:
                        # 如果日期格式不对，直接返回
                        return latest_date
                else:
                    # 🔥 没有历史数据时，从上市日期开始全量同步
                    stock_info = await self.db.stock_basic_info.find_one(
                        {"code": symbol},
                        {"list_date": 1}
                    )
                    if stock_info and stock_info.get("list_date"):
                        list_date = stock_info["list_date"]
                        # 处理不同的日期格式
                        if isinstance(list_date, str):
                            # 格式可能是 "20100101" 或 "2010-01-01"
                            if len(list_date) == 8 and list_date.isdigit():
                                return f"{list_date[:4]}-{list_date[4:6]}-{list_date[6:]}"
                            else:
                                return list_date
                        else:
                            return list_date.strftime('%Y-%m-%d')

                    # 如果没有上市日期，从1990年开始
                    logger.warning(f"⚠️ {symbol}: 未找到上市日期，从1990-01-01开始同步")
                    return "1990-01-01"

            # 默认返回30天前（确保不漏数据）
            return (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        except Exception as e:
            logger.error(f"❌ 获取最后同步日期失败 {symbol}: {e}")
            # 出错时返回30天前，确保不漏数据
            return (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    # ==================== 财务数据同步 ====================

    async def sync_financial_data(self, symbols: List[str] = None, limit: int = 20, job_id: str = None) -> Dict[str, Any]:
        """
        同步财务数据

        Args:
            symbols: 股票代码列表，None表示同步所有股票
            limit: 获取财报期数，默认20期（约5年数据）
            job_id: 任务ID（用于进度跟踪）
        """
        logger.info(f"🔄 开始同步财务数据 (获取最近 {limit} 期)...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "start_time": datetime.utcnow(),
            "errors": []
        }

        try:
            # 获取股票列表
            if symbols is None:
                # 🔥 使用聚合查询去重，确保每个股票代码只计算一次
                pipeline = [
                    {
                        "$match": {
                            "$or": [
                                {"market_info.market": "CN"},  # 新数据结构
                                {"category": "stock_cn"},      # 旧数据结构
                                {"market": {"$in": ["主板", "创业板", "科创板", "北交所"]}}  # 按市场类型
                            ]
                        }
                    },
                    {
                        "$group": {
                            "_id": "$code"  # 按股票代码分组去重
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "code": "$_id"
                        }
                    }
                ]
                cursor = self.db.stock_basic_info.aggregate(pipeline)
                symbols = [doc["code"] async for doc in cursor]
                logger.info(f"📋 从 stock_basic_info 获取到 {len(symbols)} 只唯一股票（已去重）")

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 需要同步 {len(symbols)} 只股票财务数据")

            # 批量处理
            for i, symbol in enumerate(symbols):
                try:
                    # 🔥 检查任务是否应该停止
                    if job_id and await self._should_stop(job_id):
                        logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出...")
                        stats["stopped"] = True
                        break

                    # 速率限制
                    await self.rate_limiter.acquire()

                    # 获取财务数据（指定获取期数）
                    financial_data = await self.provider.get_financial_data(symbol, limit=limit)

                    if financial_data:
                        # 保存财务数据
                        success = await self._save_financial_data(symbol, financial_data)
                        if success:
                            stats["success_count"] += 1
                        else:
                            stats["error_count"] += 1
                    else:
                        logger.warning(f"⚠️ {symbol}: 无财务数据")

                    # 进度日志和进度跟踪
                    if (i + 1) % 20 == 0:
                        progress = int((i + 1) / len(symbols) * 100)
                        logger.info(f"📈 财务数据同步进度: {i + 1}/{len(symbols)} ({progress}%) "
                                   f"(成功: {stats['success_count']}, 错误: {stats['error_count']})")
                        # 输出速率限制器统计
                        limiter_stats = self.rate_limiter.get_stats()
                        logger.info(f"   速率限制: {limiter_stats['current_calls']}/{limiter_stats['max_calls']}次")

                        # 更新任务进度
                        if job_id:
                            from app.services.scheduler_service import update_job_progress, TaskCancelledException
                            try:
                                await update_job_progress(
                                    job_id=job_id,
                                    progress=progress,
                                    message=f"正在同步 {symbol} 财务数据",
                                    current_item=symbol,
                                    total_items=len(symbols),
                                    processed_items=i + 1
                                )
                            except TaskCancelledException:
                                # 任务被取消，记录并退出
                                logger.warning(f"⚠️ 财务数据同步任务被用户取消 (已处理 {i + 1}/{len(symbols)})")
                                stats["end_time"] = datetime.utcnow()
                                stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
                                stats["cancelled"] = True
                                raise

                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "code": symbol,
                        "error": str(e),
                        "context": "sync_financial_data"
                    })
                    logger.error(f"❌ {symbol} 财务数据同步失败: {e}")

            # 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"✅ 财务数据同步完成: "
                       f"成功 {stats['success_count']}/{stats['total_processed']}, "
                       f"错误 {stats['error_count']} 个, "
                       f"耗时 {stats['duration']:.2f} 秒")

            # 🔥 更新任务状态为已完成（如果有 job_id）
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    error_message = None
                    if stats.get("error_count", 0) > 0:
                        error_messages = [e.get("error", "") for e in stats.get("errors", [])[:5]]
                        error_message = f"同步完成但有 {stats.get('error_count', 0)} 个错误: {', '.join(error_messages)}"
                    await mark_job_completed(job_id, stats, error_message)
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务完成状态时出错: {update_error}")

            return stats

        except Exception as e:
            logger.error(f"❌ 财务数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_financial_data"})
            
            # 🔥 更新任务状态为失败（如果有 job_id）
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    await mark_job_completed(job_id, None, str(e))
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务失败状态时出错: {update_error}")
            
            return stats

    async def _save_financial_data(self, symbol: str, financial_data: Dict[str, Any]) -> bool:
        """保存财务数据"""
        try:
            # 使用统一的财务数据服务
            from app.services.financial_data_service import get_financial_data_service

            financial_service = await get_financial_data_service()

            # 保存财务数据
            saved_count = await financial_service.save_financial_data(
                symbol=symbol,
                financial_data=financial_data,
                data_source="tushare",
                market="CN",
                report_period=financial_data.get("report_period"),
                report_type=financial_data.get("report_type", "quarterly")
            )

            return saved_count > 0

        except Exception as e:
            logger.error(f"❌ 保存 {symbol} 财务数据失败: {e}")
            return False

    # ==================== 辅助方法 ====================

    def _is_data_fresh(self, updated_at: datetime, hours: int = 24) -> bool:
        """检查数据是否新鲜"""
        if not updated_at:
            return False

        threshold = datetime.utcnow() - timedelta(hours=hours)
        return updated_at > threshold

    async def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        try:
            # 统计各集合的数据量
            basic_info_count = await self.db.stock_basic_info.count_documents({})
            quotes_count = await self.db.market_quotes.count_documents({})

            # 获取最新更新时间
            latest_basic = await self.db.stock_basic_info.find_one(
                {},
                sort=[("updated_at", -1)]
            )
            latest_quotes = await self.db.market_quotes.find_one(
                {},
                sort=[("updated_at", -1)]
            )

            return {
                "provider_connected": self.provider.is_available(),
                "collections": {
                    "stock_basic_info": {
                        "count": basic_info_count,
                        "latest_update": latest_basic.get("updated_at") if (latest_basic and isinstance(latest_basic, dict)) else None
                    },
                    "market_quotes": {
                        "count": quotes_count,
                        "latest_update": latest_quotes.get("updated_at") if (latest_quotes and isinstance(latest_quotes, dict)) else None
                    }
                },
                "status_time": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"❌ 获取同步状态失败: {e}")
            return {"error": str(e)}

    # ==================== 新闻数据同步 ====================

    async def sync_news_data(
        self,
        symbols: List[str] = None,
        hours_back: int = 24,
        max_news_per_stock: int = 20,
        force_update: bool = False,
        job_id: str = None
    ) -> Dict[str, Any]:
        """
        同步新闻数据

        Args:
            symbols: 股票代码列表，为None时获取所有股票
            hours_back: 回溯小时数，默认24小时
            max_news_per_stock: 每只股票最大新闻数量
            force_update: 是否强制更新
            job_id: 任务ID（用于进度跟踪）

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步新闻数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "news_count": 0,
            "start_time": datetime.utcnow(),
            "errors": []
        }

        try:
            # 1. 获取股票列表
            if symbols is None:
                stock_list = await self.stock_service.get_all_stocks()
                symbols = [stock["code"] for stock in stock_list]

            if not symbols:
                logger.warning("⚠️ 没有找到需要同步新闻的股票")
                return stats

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 需要同步 {len(symbols)} 只股票的新闻")

            # 2. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                # 检查是否需要退出
                if job_id and await self._should_stop(job_id):
                    logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出...")
                    stats["stopped"] = True
                    break

                batch = symbols[i:i + self.batch_size]
                batch_stats = await self._process_news_batch(
                    batch, hours_back, max_news_per_stock
                )

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["news_count"] += batch_stats["news_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志和进度更新
                progress = min(i + self.batch_size, len(symbols))
                progress_percent = int((progress / len(symbols)) * 100)
                logger.info(f"📈 新闻同步进度: {progress}/{len(symbols)} ({progress_percent}%) "
                           f"(成功: {stats['success_count']}, 新闻: {stats['news_count']})")

                # 更新任务进度
                if job_id:
                    await self._update_progress(
                        job_id,
                        progress_percent,
                        f"已处理 {progress}/{len(symbols)} 只股票，获取 {stats['news_count']} 条新闻"
                    )

                # API限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(self.rate_limit_delay)

            # 3. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"✅ 新闻数据同步完成: "
                       f"总计 {stats['total_processed']} 只股票, "
                       f"成功 {stats['success_count']} 只, "
                       f"获取 {stats['news_count']} 条新闻, "
                       f"错误 {stats['error_count']} 只, "
                       f"耗时 {stats['duration']:.2f} 秒")

            # 🔥 更新任务状态为已完成（如果有 job_id）
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    error_message = None
                    if stats.get("error_count", 0) > 0:
                        error_messages = [e.get("error", "") for e in stats.get("errors", [])[:5]]
                        error_message = f"同步完成但有 {stats.get('error_count', 0)} 个错误: {', '.join(error_messages)}"
                    await mark_job_completed(job_id, stats, error_message)
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务完成状态时出错: {update_error}")

            return stats

        except Exception as e:
            logger.error(f"❌ 新闻数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_news_data"})
            
            # 🔥 更新任务状态为失败（如果有 job_id）
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    await mark_job_completed(job_id, None, str(e))
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务失败状态时出错: {update_error}")
            
            return stats

    async def _process_news_batch(
        self,
        batch: List[str],
        hours_back: int,
        max_news_per_stock: int
    ) -> Dict[str, Any]:
        """处理新闻批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "news_count": 0,
            "errors": []
        }

        for symbol in batch:
            try:
                # 从Tushare获取新闻数据
                news_data = await self.provider.get_stock_news(
                    symbol=symbol,
                    limit=max_news_per_stock,
                    hours_back=hours_back
                )

                if news_data:
                    # 保存新闻数据
                    saved_count = await self.news_service.save_news_data(
                        news_data=news_data,
                        data_source="tushare",
                        market="CN"
                    )

                    batch_stats["success_count"] += 1
                    batch_stats["news_count"] += saved_count

                    logger.debug(f"✅ {symbol} 新闻同步成功: {saved_count}条")
                else:
                    logger.debug(f"⚠️ {symbol} 未获取到新闻数据")
                    batch_stats["success_count"] += 1  # 没有新闻也算成功

                # 🔥 API限流：成功后休眠
                await asyncio.sleep(0.2)

            except Exception as e:
                batch_stats["error_count"] += 1
                error_msg = f"{symbol}: {str(e)}"
                batch_stats["errors"].append(error_msg)
                logger.error(f"❌ {symbol} 新闻同步失败: {e}")

                # 🔥 失败后也要休眠，避免"失败雪崩"
                # 失败时休眠更长时间，给API服务器恢复的机会
                await asyncio.sleep(1.0)

        return batch_stats

    # ==================== 进度跟踪辅助方法 ====================

    async def _should_stop(self, job_id: str) -> bool:
        """
        检查任务是否应该停止

        Args:
            job_id: 任务ID

        Returns:
            是否应该停止
        """
        try:
            # 🔥 查询执行记录，检查 cancel_requested 标记和任务状态
            # 不仅检查 running 状态，也检查 failed/cancelled 状态（可能用户手动标记为失败）
            execution = await self.db.scheduler_executions.find_one(
                {"job_id": job_id},
                sort=[("timestamp", -1)]
            )

            if not execution:
                return False

            # 检查取消请求标记
            if execution.get("cancel_requested"):
                logger.info(f"🛑 任务 {job_id} 收到取消请求，应停止执行")
                return True

            # 🔥 检查任务状态：如果任务已被标记为失败或取消，也应该停止
            status = execution.get("status")
            if status in ["failed", "cancelled"]:
                logger.info(f"🛑 任务 {job_id} 状态为 {status}，应停止执行")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 检查任务停止标记失败: {e}")
            return False

    async def _update_progress(self, job_id: str, progress: int, message: str):
        """
        更新任务进度

        Args:
            job_id: 任务ID
            progress: 进度百分比 (0-100)
            message: 进度消息
        """
        try:
            from app.services.scheduler_service import TaskCancelledException
            from pymongo import MongoClient
            from app.core.config import settings

            logger.info(f"📊 [进度更新] 开始更新任务 {job_id} 进度: {progress}% - {message}")

            # 使用同步 PyMongo 客户端（避免事件循环冲突）
            sync_client = MongoClient(settings.MONGO_URI)
            sync_db = sync_client[settings.MONGODB_DATABASE]

            # 查找最新的 running 记录
            execution = sync_db.scheduler_executions.find_one(
                {"job_id": job_id, "status": "running"},
                sort=[("timestamp", -1)]
            )

            if not execution:
                logger.warning(f"⚠️ 未找到任务 {job_id} 的执行记录")
                sync_client.close()
                return

            logger.info(f"📊 [进度更新] 找到执行记录: _id={execution['_id']}, 当前进度={execution.get('progress', 0)}%")

            # 检查是否收到取消请求
            if execution.get("cancel_requested"):
                sync_client.close()
                raise TaskCancelledException(f"任务 {job_id} 已被用户取消")

            # 更新进度（使用 UTC+8 时间）
            result = sync_db.scheduler_executions.update_one(
                {"_id": execution["_id"]},
                {
                    "$set": {
                        "progress": progress,
                        "progress_message": message,
                        "updated_at": get_utc8_now()
                    }
                }
            )

            logger.info(f"📊 [进度更新] 更新结果: matched={result.matched_count}, modified={result.modified_count}")

            sync_client.close()
            logger.info(f"✅ 任务 {job_id} 进度更新成功: {progress}% - {message}")

        except Exception as e:
            if "TaskCancelledException" in str(type(e).__name__):
                raise
            logger.error(f"❌ 更新任务进度失败: {e}", exc_info=True)

    async def _mark_task_completed(self, job_id: str, stats: Dict[str, Any]):
        """
        标记任务为已完成状态
        
        Args:
            job_id: 任务ID
            stats: 同步统计信息
        """
        # 🔥 统一使用 mark_job_completed 函数，确保 MongoDB 和 Redis 都正确更新
        try:
            from app.services.scheduler_service import mark_job_completed
            error_message = None
            if stats.get("error_count", 0) > 0:
                error_messages = [e.get("error", "") for e in stats.get("errors", [])[:5]]
                error_message = f"同步完成但有 {stats.get('error_count', 0)} 个错误: {', '.join(error_messages)}"
            await mark_job_completed(job_id, stats, error_message)
        except Exception as e:
            logger.error(f"❌ 标记任务完成失败: {e}", exc_info=True)

    async def _mark_task_failed(self, job_id: str, error_message: str):
        """
        标记任务为失败状态
        
        Args:
            job_id: 任务ID
            error_message: 错误消息
        """
        # 🔥 统一使用 mark_job_completed 函数，确保 MongoDB 和 Redis 都正确更新
        try:
            from app.services.scheduler_service import mark_job_completed
            await mark_job_completed(job_id, None, error_message)
        except Exception as e:
            logger.error(f"❌ 标记任务失败状态时出错: {e}", exc_info=True)

    async def retry_failed_symbols(
        self,
        errors: List[Dict[str, Any]],
        start_date: str = None,
        end_date: str = None,
        period: str = "daily",
        job_id: str = None,
        _is_retry: bool = False  # 🔥 内部标记，表示这是重试任务，避免再次自动重试
    ) -> Dict[str, Any]:
        """
        重试失败的股票（只重试可重试的错误，跳过无数据的错误）
        
        Args:
            errors: 错误列表（从之前的同步结果中获取）
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期 (daily/weekly/monthly)
            job_id: 任务ID（用于进度跟踪）
            
        Returns:
            重试结果统计
        """
        period_name = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(period, period)
        
        # 🔥 过滤出可重试的错误
        retryable_errors = [
            error for error in errors
            if error.get("error_category") == "retryable_error" 
            or error.get("is_retryable", False)
        ]
        
        no_data_errors = [
            error for error in errors
            if error.get("error_category") == "no_data"
            or (not error.get("is_retryable", True) and error.get("error_category") != "retryable_error")
        ]
        
        logger.info(f"🔄 开始重试失败的股票...")
        logger.info(f"   可重试的错误: {len(retryable_errors)} 个")
        logger.info(f"   无数据的错误（跳过）: {len(no_data_errors)} 个")
        
        if not retryable_errors:
            logger.info("✅ 没有可重试的错误，所有失败都是无数据的情况")
            return {
                "total_retried": 0,
                "success_count": 0,
                "error_count": 0,
                "no_data_count": len(no_data_errors),
                "errors": []
            }
        
        # 提取可重试的股票代码
        retry_symbols = [error["code"] for error in retryable_errors]
        
        logger.info(f"📋 将重试以下 {len(retry_symbols)} 只股票: {', '.join(retry_symbols[:10])}{'...' if len(retry_symbols) > 10 else ''}")
        
        # 调用同步方法，只同步这些失败的股票
        retry_result = await self.sync_historical_data(
            symbols=retry_symbols,
            start_date=start_date,
            end_date=end_date,
            incremental=False,  # 重试时使用全量同步
            all_history=False,
            period=period,
            job_id=job_id,
            auto_retry=False,  # 🔥 重试任务本身不再自动重试，避免无限循环
            _is_retry=True  # 🔥 标记为重试任务
        )
        
        # 合并结果
        retry_result["total_retried"] = len(retry_symbols)
        retry_result["no_data_count"] = len(no_data_errors)
        retry_result["retryable_errors_count"] = len(retryable_errors)
        
        logger.info(f"✅ 重试完成: 成功 {retry_result['success_count']}/{retry_result['total_retried']}, "
                   f"失败 {retry_result['error_count']}, 无数据 {retry_result['no_data_count']}（已跳过）")
        
        return retry_result


# 全局同步服务实例
_tushare_sync_service = None

async def get_tushare_sync_service() -> TushareSyncService:
    """获取Tushare同步服务实例"""
    global _tushare_sync_service
    if _tushare_sync_service is None:
        _tushare_sync_service = TushareSyncService()
        await _tushare_sync_service.initialize()
    return _tushare_sync_service


# APScheduler兼容的任务函数

async def _check_task_running(job_id: str, resume_execution_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    检查任务是否已有实例在运行
    
    Args:
        job_id: 任务ID
        resume_execution_id: 如果是恢复执行，传入要恢复的执行记录ID（此时允许执行，即使有running记录）
        
    Returns:
        (is_running, running_instance_id): 是否在运行，运行实例的ID
    """
    try:
        from pymongo import MongoClient
        from app.core.config import settings
        from datetime import timedelta
        from app.services.scheduler_service import get_utc8_now
        
        sync_client = MongoClient(settings.MONGO_URI)
        sync_db = sync_client[settings.MONGODB_DATABASE]
        
        # 🔥 如果是恢复执行，检查是否是恢复同一个执行记录
        if resume_execution_id:
            try:
                from bson import ObjectId
                resume_record = sync_db.scheduler_executions.find_one({"_id": ObjectId(resume_execution_id)})
                if resume_record:
                    # 如果是恢复同一个执行记录，允许执行（即使状态是running）
                    # 因为这是用户主动恢复的，应该允许继续执行
                    logger.info(f"✅ 恢复执行记录 {resume_execution_id}，允许执行")
                    sync_client.close()
                    return False, None  # 允许执行
            except Exception as e:
                logger.warning(f"⚠️ 检查恢复执行记录失败: {e}")
        
        # 🔥 查找是否有正在运行的实例（排除超时的任务）
        # 如果任务运行超过30分钟，认为是僵尸任务，不阻止新任务执行
        threshold_time = get_utc8_now() - timedelta(minutes=30)
        
        running_instance = sync_db.scheduler_executions.find_one(
            {
                "job_id": job_id, 
                "status": "running",
                "timestamp": {"$gte": threshold_time}  # 只考虑最近30分钟内的running任务
            },
            sort=[("timestamp", -1)]
        )
        
        # 🔥 如果找到超时的running任务，自动标记为失败
        if not running_instance:
            # 检查是否有超时的running任务
            zombie_instance = sync_db.scheduler_executions.find_one(
                {
                    "job_id": job_id,
                    "status": "running",
                    "timestamp": {"$lt": threshold_time}
                },
                sort=[("timestamp", -1)]
            )
            
            if zombie_instance:
                # 自动标记为失败
                sync_db.scheduler_executions.update_one(
                    {"_id": zombie_instance["_id"]},
                    {
                        "$set": {
                            "status": "failed",
                            "error_message": "任务执行超时或进程异常终止（自动检测）",
                            "updated_at": get_utc8_now()
                        }
                    }
                )
                logger.warning(f"⚠️ 检测到超时任务并自动标记为失败: {job_id} (开始时间: {zombie_instance.get('timestamp')})")
        
        sync_client.close()
        
        if running_instance:
            return True, str(running_instance["_id"])
        return False, None
    except Exception as e:
        logger.warning(f"⚠️ 检查任务运行状态失败: {e}")
        return False, None


async def run_tushare_basic_info_sync(force_update: bool = False, **kwargs):
    """APScheduler任务：同步股票基础信息"""
    job_id = "tushare_basic_info_sync"
    
    # 🔥 手动触发或强制执行时允许执行（即使有running记录）
    manual_trigger = kwargs.get("_manual_trigger", False)
    force_execute = kwargs.get("_force_execute", False)
    if not manual_trigger and not force_execute:
        # 🔥 检查是否已有实例在运行（非手动触发且非强制执行时才检查）
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
        service = await get_tushare_sync_service()
        result = await service.sync_stock_basic_info(force_update, job_id=job_id)
        logger.info(f"✅ Tushare基础信息同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare基础信息同步失败: {e}")
        raise


async def run_tushare_quotes_sync(force: bool = False):
    """
    APScheduler任务：同步实时行情

    Args:
        force: 是否强制执行（跳过交易时间检查），默认 False
    """
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_realtime_quotes(force=force)
        logger.info(f"✅ Tushare行情同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare行情同步失败: {e}")
        raise


async def run_tushare_realtime_quotes_hourly(**kwargs):
    """
    APScheduler任务：每小时31分同步Tushare实时行情
    
    特殊处理：
    - 如果超过下午3点（15:00），调用成功后更新到历史数据
    - 如果不超过15:00，正常更新实时行情
    
    注意：免费用户每小时只能调用一次 rt_k 接口，所以选择每小时31分执行
    """
    from datetime import datetime
    from app.utils.timezone import now_tz
    from app.core.database import get_mongo_db
    from app.services.historical_data_service import get_historical_data_service
    import pandas as pd
    
    job_id = "tushare_realtime_quotes_hourly"
    
    # 🔥 手动触发或强制执行时允许执行（即使有running记录）
    manual_trigger = kwargs.get("_manual_trigger", False)
    force_execute = kwargs.get("_force_execute", False)
    if not manual_trigger and not force_execute:
        # 🔥 检查是否已有实例在运行（非手动触发且非强制执行时才检查）
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
        current_time = now_tz()
        current_hour = current_time.hour
        
        logger.info(f"🕐 [Tushare实时行情每小时同步] 开始执行，当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 调用实时行情同步
        service = await get_tushare_sync_service()
        result = await service.sync_realtime_quotes(force=True)  # 强制同步，跳过交易时间检查
        
        if not result.get("success_count", 0) > 0:
            logger.warning(f"⚠️ [Tushare实时行情每小时同步] 同步失败或未获取到数据")
            
            # 🔥 更新任务状态为失败
            job_id = "tushare_realtime_quotes_hourly"
            error_message = "同步失败：未获取到数据"
            if result.get("errors"):
                error_messages = [e.get("error", "") for e in result.get("errors", [])[:3]]
                error_message = f"同步失败: {', '.join(error_messages)}"
            
            try:
                from app.services.scheduler_service import mark_job_completed
                await mark_job_completed(job_id, result, error_message)
            except Exception as update_error:
                logger.warning(f"⚠️ 更新任务失败状态时出错: {update_error}")
            
            return result
        
        logger.info(f"✅ [Tushare实时行情每小时同步] 实时行情同步成功: 成功 {result.get('success_count', 0)} 只")
        
        # 如果超过下午3点（15:00），将实时行情保存到历史数据
        if current_hour >= 15:
            logger.info(f"📊 [Tushare实时行情每小时同步] 当前时间超过15:00，开始将实时行情保存到历史数据...")
            
            try:
                db = get_mongo_db()
                historical_service = await get_historical_data_service()
                
                # 获取今天的日期（YYYYMMDD格式）
                today_str = current_time.strftime('%Y%m%d')
                
                # 从 market_quotes 集合读取所有实时行情数据
                market_quotes_collection = db["market_quotes"]
                cursor = market_quotes_collection.find({})
                
                quotes_list = await cursor.to_list(length=None)
                
                if not quotes_list:
                    logger.warning(f"⚠️ [Tushare实时行情每小时同步] market_quotes 集合为空，无法保存历史数据")
                    # 🔥 虽然实时行情同步成功，但历史数据保存失败，标记为部分失败
                    job_id = "tushare_realtime_quotes_hourly"
                    try:
                        from app.services.scheduler_service import mark_job_completed
                        result["error_count"] = result.get("error_count", 0) + 1
                        result["errors"] = result.get("errors", [])
                        result["errors"].append({"error": "market_quotes 集合为空，无法保存历史数据"})
                        await mark_job_completed(job_id, result)
                    except Exception as update_error:
                        logger.warning(f"⚠️ 更新任务状态时出错: {update_error}")
                    return result
                
                logger.info(f"📊 [Tushare实时行情每小时同步] 从 market_quotes 读取到 {len(quotes_list)} 条实时行情数据")
                
                # 批量转换为历史数据格式并保存
                saved_count = 0
                error_count = 0
                
                for quote_doc in quotes_list:
                    try:
                        symbol = quote_doc.get("symbol") or quote_doc.get("code", "")
                        if not symbol:
                            continue
                        
                        # 构建历史数据记录（单条记录DataFrame）
                        # 注意：market_quotes 中的数据格式取决于数据来源
                        # - 如果来自 get_realtime_quotes_batch()：volume（股，rt_k返回vol）、amount（元，rt_k返回amount）
                        # - 如果来自 standardize_quotes()：volume（股，已转换）、amount（元，已转换）
                        # 历史数据服务期望 tushare 数据源格式是：volume（手）、amount（千元）
                        # 所以需要反向转换：volume / 100（股转手），amount / 1000（元转千元）
                        
                        # 获取原始数据
                        volume_gu = float(quote_doc.get("volume", 0) or 0)  # 股
                        amount_yuan = float(quote_doc.get("amount", 0) or 0)  # 元
                        pre_close = float(quote_doc.get("pre_close", 0) or 0)
                        
                        # 转换为历史数据格式（手、千元）
                        volume_shou = volume_gu / 100.0 if volume_gu > 0 else 0  # 股转手
                        amount_qian = amount_yuan / 1000.0 if amount_yuan > 0 else 0  # 元转千元
                        
                        # 如果没有 pre_close，尝试从 change 和 close 计算
                        if not pre_close and quote_doc.get("close") and quote_doc.get("change"):
                            try:
                                close = float(quote_doc.get("close", 0))
                                change = float(quote_doc.get("change", 0))
                                pre_close = close - change
                            except (ValueError, TypeError):
                                pass
                        
                        historical_data = {
                            "trade_date": today_str,  # YYYYMMDD 格式
                            "open": float(quote_doc.get("open", 0) or 0),
                            "high": float(quote_doc.get("high", 0) or 0),
                            "low": float(quote_doc.get("low", 0) or 0),
                            "close": float(quote_doc.get("close", 0) or 0),
                            "pre_close": pre_close,  # 前收盘价（重要字段）
                            "volume": volume_shou,  # 手，历史数据服务会自动转换为股
                            "amount": amount_qian,  # 千元，历史数据服务会自动转换为元
                            "pct_chg": float(quote_doc.get("pct_chg", 0) or 0),
                        }
                        
                        # 创建DataFrame（单行数据）
                        # 索引使用日期，方便 historical_data_service 处理
                        df = pd.DataFrame([historical_data])
                        df.index = pd.to_datetime([today_str], format='%Y%m%d')
                        
                        # 保存到历史数据集合
                        count = await historical_service.save_historical_data(
                            symbol=symbol,
                            data=df,
                            data_source="tushare",
                            market="CN",
                            period="daily"
                        )
                        
                        if count > 0:
                            saved_count += 1
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        symbol = quote_doc.get("symbol") or quote_doc.get("code", "unknown")
                        logger.error(f"❌ [Tushare实时行情每小时同步] 保存 {symbol} 历史数据失败: {e}")
                
                logger.info(
                    f"✅ [Tushare实时行情每小时同步] 历史数据保存完成: "
                    f"总计 {len(quotes_list)} 只, "
                    f"成功 {saved_count} 只, "
                    f"失败 {error_count} 只"
                )
                
                result["historical_saved_count"] = saved_count
                result["historical_error_count"] = error_count
                
            except Exception as e:
                logger.error(f"❌ [Tushare实时行情每小时同步] 保存历史数据失败: {e}", exc_info=True)
                result["historical_save_error"] = str(e)
        else:
            logger.info(f"📊 [Tushare实时行情每小时同步] 当前时间未超过15:00，仅更新实时行情")
        
        # 🔥 更新任务状态为已完成（成功）
        job_id = "tushare_realtime_quotes_hourly"
        try:
            from app.services.scheduler_service import mark_job_completed
            await mark_job_completed(job_id, result)
        except Exception as update_error:
            logger.warning(f"⚠️ 更新任务完成状态时出错: {update_error}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [Tushare实时行情每小时同步] 执行失败: {e}", exc_info=True)
        
        # 🔥 更新任务状态为失败
        job_id = "tushare_realtime_quotes_hourly"
        try:
            from app.services.scheduler_service import mark_job_completed
            await mark_job_completed(job_id, None, str(e))
        except Exception as update_error:
            logger.warning(f"⚠️ 更新任务失败状态时出错: {update_error}")
        
        raise


async def run_tushare_historical_sync(incremental: bool = True, **kwargs):
    """APScheduler任务：同步历史数据"""
    job_id = "tushare_historical_sync"
    
    # 🔥 从kwargs中提取恢复位置信息、手动触发标记和强制执行标记
    resume_from_index = kwargs.get("_resume_from_index")
    resume_execution_id = kwargs.get("_resume_execution_id")  # 恢复执行时的执行记录ID
    manual_trigger = kwargs.get("_manual_trigger", False)  # 手动触发标记
    force_execute = kwargs.get("_force_execute", False)  # 强制执行标记
    
    # 🔥 如果是恢复执行、手动触发或强制执行，允许执行（即使有running记录）
    # 因为恢复执行、手动触发和强制执行都是用户主动触发的，应该允许继续执行
    if resume_from_index is not None or resume_execution_id is not None or manual_trigger or force_execute:
        if resume_from_index is not None or resume_execution_id is not None:
            logger.info(f"🔄 [APScheduler] 恢复执行，从第 {resume_from_index} 个位置继续 (execution_id={resume_execution_id})")
        if manual_trigger:
            logger.info(f"🔧 [APScheduler] 手动触发执行，允许执行（即使有running记录）")
        if force_execute:
            logger.info(f"🔧 [APScheduler] 强制执行，跳过并发检查")
        # 恢复执行、手动触发或强制执行时，不检查并发，直接允许执行
    else:
        # 🔥 检查是否已有实例在运行（非恢复执行且非手动触发且非强制执行时才检查）
        is_running, instance_id = await _check_task_running(job_id)
        if is_running:
            logger.warning(f"⚠️ 任务 {job_id} 已有实例在运行（_id={instance_id}），跳过本次执行")
            return {
                "skipped": True,
                "reason": "已有实例在运行",
                "running_instance_id": instance_id
            }
    
    # 🔥 清理内部标记（这些不应该传递给sync_historical_data）
    clean_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_") or k == "_resume_from_index"}
    
    logger.info(f"🚀 [APScheduler] 开始执行 Tushare 历史数据同步任务 (incremental={incremental}, kwargs={clean_kwargs})")
    try:
        # 🔥 使用统一的线程池同步服务
        from app.worker.unified_thread_pool_sync_service import get_unified_thread_pool_sync_service
        
        unified_service = await get_unified_thread_pool_sync_service()
        
        # 🔥 获取Tushare数据源服务实例
        service = await get_tushare_sync_service()
        logger.info(f"✅ [APScheduler] Tushare 同步服务已初始化")
        
        # 🔥 在线程池中执行同步方法
        sync_result = await unified_service.execute_sync_method(
            sync_method=service.sync_historical_data,
            method_kwargs={
                "incremental": incremental,
                "period": clean_kwargs.get("period", "daily"),
                "start_date": clean_kwargs.get("start_date"),
                "end_date": clean_kwargs.get("end_date"),
                "symbols": clean_kwargs.get("symbols"),
                "job_id": "tushare_historical_sync",
                **{k: v for k, v in clean_kwargs.items() if k not in ["period", "start_date", "end_date", "symbols"]}
            },
            job_id=job_id,
            rate_limit_per_minute=kwargs.get("rate_limit_per_minute", 200),  # Tushare速率限制
            resume_from_index=resume_from_index
        )
        
        if sync_result.success:
            result = sync_result.result
            logger.info(f"✅ [APScheduler] Tushare历史数据同步完成: {result}")
            return result
        else:
            # 🔥 检查是否是任务取消
            if "取消" in sync_result.error or "cancelled" in sync_result.error.lower():
                logger.info(f"ℹ️ [APScheduler] Tushare历史数据同步任务已被用户取消")
                return {"cancelled": True, "message": sync_result.error}
            else:
                logger.error(f"❌ [APScheduler] Tushare历史数据同步失败: {sync_result.error}")
                raise RuntimeError(sync_result.error)
                
    except Exception as e:
        # 检查是否是任务取消异常（用户主动取消，不应该记录为错误）
        from app.services.scheduler_service import TaskCancelledException
        if isinstance(e, TaskCancelledException):
            logger.info(f"ℹ️ [APScheduler] Tushare历史数据同步任务已被用户取消")
            return {"cancelled": True, "message": "任务已被用户取消"}
        # 其他异常才记录为错误
        logger.error(f"❌ [APScheduler] Tushare历史数据同步失败: {e}", exc_info=True)
        raise


async def run_tushare_financial_sync(**kwargs):
    """
    APScheduler任务：同步财务数据（使用线程池版本）
    
    🔥 已更新为使用统一的财务数据同步服务（线程池版本）
    """
    job_id = "tushare_financial_sync"
    
    # 🔥 手动触发或强制执行时允许执行（即使有running记录）
    manual_trigger = kwargs.get("_manual_trigger", False)
    force_execute = kwargs.get("_force_execute", False)
    if not manual_trigger and not force_execute:
        # 🔥 检查是否已有实例在运行（非手动触发且非强制执行时才检查）
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
        # 🔥 使用统一的财务数据同步服务（线程池版本）
        from app.worker.financial_data_sync_service import get_financial_sync_service
        
        service = await get_financial_sync_service()
        
        # 🔥 检查是否是恢复执行，从kwargs中读取恢复位置
        resume_from_index = kwargs.get("_resume_from_index")
        if resume_from_index is not None:
            logger.info(f"🔄 [恢复执行] 将从第 {resume_from_index} 个股票位置继续同步")
        
        results = await service.sync_financial_data(
            symbols=None,  # None表示同步所有股票
            data_sources=["tushare"],  # 只同步Tushare数据源
            report_types=["quarterly", "annual"],
            job_id=job_id,
            _resume_from_index=resume_from_index  # 🔥 传递恢复位置参数
        )
        
        # 转换为旧格式以保持兼容性
        if "tushare" in results:
            stats = results["tushare"]
            result = {
                "success": True,
                "total_symbols": stats.total_symbols,
                "success_count": stats.success_count,
                "error_count": stats.error_count,
                "duration": stats.duration
            }
        else:
            result = {"success": False, "message": "Tushare数据源同步失败"}
        
        logger.info(f"✅ Tushare财务数据同步完成（线程池版本）: {result}")
        return result
    except Exception as e:
        # 检查是否是任务取消异常（用户主动取消，不应该记录为错误）
        from app.services.scheduler_service import TaskCancelledException
        if isinstance(e, TaskCancelledException):
            logger.info(f"ℹ️ Tushare财务数据同步任务已被用户取消")
            return {"cancelled": True, "message": "任务已被用户取消"}
        # 其他异常才记录为错误
        logger.error(f"❌ Tushare财务数据同步失败: {e}", exc_info=True)
        raise


async def run_tushare_status_check():
    """APScheduler任务：检查同步状态"""
    try:
        service = await get_tushare_sync_service()
        result = await service.get_sync_status()
        logger.info(f"✅ Tushare状态检查完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare状态检查失败: {e}")
        return {"error": str(e)}


async def run_tushare_news_sync(hours_back: int = 24, max_news_per_stock: int = 20, **kwargs):
    """APScheduler任务：同步新闻数据"""
    job_id = "tushare_news_sync"
    
    # 🔥 手动触发或强制执行时允许执行（即使有running记录）
    manual_trigger = kwargs.get("_manual_trigger", False)
    force_execute = kwargs.get("_force_execute", False)
    if not manual_trigger and not force_execute:
        # 🔥 检查是否已有实例在运行（非手动触发且非强制执行时才检查）
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
        service = await get_tushare_sync_service()
        result = await service.sync_news_data(
            hours_back=hours_back,
            max_news_per_stock=max_news_per_stock,
            job_id="tushare_news_sync"
        )
        logger.info(f"✅ Tushare新闻数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare新闻数据同步失败: {e}")
        raise
