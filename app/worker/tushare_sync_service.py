"""
Tushare数据同步服务
负责将Tushare数据同步到MongoDB标准化集合
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from tradingagents.dataflows.providers.china.tushare import TushareProvider
from app.services.stock_data_service import get_stock_data_service
from app.services.historical_data_service import get_historical_data_service
from app.services.news_data_service import get_news_data_service
from app.core.database import get_mongo_db
from app.core.config import settings
from app.core.rate_limiter import get_tushare_rate_limiter

logger = logging.getLogger(__name__)


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
    
    async def sync_stock_basic_info(self, force_update: bool = False) -> Dict[str, Any]:
        """
        同步股票基础信息
        
        Args:
            force_update: 是否强制更新所有数据
            
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
                batch = stock_list[i:i + self.batch_size]
                batch_stats = await self._process_basic_info_batch(batch, force_update)
                
                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["skipped_count"] += batch_stats["skipped_count"]
                stats["errors"].extend(batch_stats["errors"])
                
                # 进度日志
                progress = min(i + self.batch_size, len(stock_list))
                logger.info(f"📈 基础信息同步进度: {progress}/{len(stock_list)} "
                           f"(成功: {stats['success_count']}, 错误: {stats['error_count']})")
                
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
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 股票基础信息同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_stock_basic_info"})
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

                # 更新到数据库
                success = await self.stock_service.update_stock_basic_info(code, stock_data)
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
    
    async def sync_realtime_quotes(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        同步实时行情数据
        使用 Tushare rt_k 接口批量获取全市场行情（一次性获取，避免限流）

        Args:
            symbols: 指定股票代码列表，为空则同步所有股票（实际会忽略此参数，直接获取全市场）

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步实时行情（使用 rt_k 批量接口）...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "start_time": datetime.utcnow(),
            "errors": [],
            "stopped_by_rate_limit": False,
            "skipped_non_trading_time": False
        }

        try:
            # 检查是否在交易时间
            if not self._is_trading_time():
                logger.info("⏸️ 当前不在交易时间，跳过实时行情同步")
                stats["skipped_non_trading_time"] = True
                return stats
            # 使用批量接口一次性获取全市场行情
            logger.info("📡 调用 rt_k 接口获取全市场实时行情...")
            quotes_map = await self.provider.get_realtime_quotes_batch()

            if not quotes_map:
                logger.warning("⚠️ 未获取到实时行情数据")
                return stats

            stats["total_processed"] = len(quotes_map)
            logger.info(f"✅ 获取到 {len(quotes_map)} 只股票的实时行情")

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
        period: str = "daily"
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
            # 1. 获取股票列表
            if symbols is None:
                cursor = self.db.stock_basic_info.find(
                    {"market_info.market": "CN"},
                    {"code": 1}
                )
                symbols = [doc["code"] async for doc in cursor]

            stats["total_processed"] = len(symbols)

            # 2. 确定日期范围
            if not start_date:
                if all_history:
                    # 全历史同步：从1990年开始
                    start_date = "1990-01-01"
                elif incremental:
                    # 增量同步：从最后更新日期开始
                    start_date = await self._get_last_sync_date()
                else:
                    # 默认同步：从一年前开始
                    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')

            logger.info(f"📊 历史数据同步范围: {start_date} 到 {end_date}, 股票数量: {len(symbols)}")

            # 3. 批量处理
            for i, symbol in enumerate(symbols):
                try:
                    # 速率限制
                    await self.rate_limiter.acquire()

                    # 获取历史数据（指定周期）
                    df = await self.provider.get_historical_data(symbol, start_date, end_date, period=period)

                    if df is not None and not df.empty:
                        # 保存到数据库（指定周期）
                        records_saved = await self._save_historical_data(symbol, df, period=period)
                        stats["success_count"] += 1
                        stats["total_records"] += records_saved

                        logger.debug(f"✅ {symbol}: 保存 {records_saved} 条{period_name}记录")
                    else:
                        logger.warning(f"⚠️ {symbol}: 无{period_name}数据")

                    # 进度日志
                    if (i + 1) % 50 == 0:
                        logger.info(f"📈 {period_name}数据同步进度: {i + 1}/{len(symbols)} "
                                   f"(成功: {stats['success_count']}, 记录: {stats['total_records']})")
                        # 输出速率限制器统计
                        limiter_stats = self.rate_limiter.get_stats()
                        logger.info(f"   速率限制: {limiter_stats['current_calls']}/{limiter_stats['max_calls']}次, "
                                   f"等待次数: {limiter_stats['total_waits']}, "
                                   f"总等待时间: {limiter_stats['total_wait_time']:.1f}秒")

                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "code": symbol,
                        "error": str(e),
                        "context": f"sync_historical_data_{period}"
                    })
                    logger.error(f"❌ {symbol} {period_name}数据同步失败: {e}")

            # 4. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"✅ {period_name}数据同步完成: "
                       f"股票 {stats['success_count']}/{stats['total_processed']}, "
                       f"记录 {stats['total_records']} 条, "
                       f"错误 {stats['error_count']} 个, "
                       f"耗时 {stats['duration']:.2f} 秒")

            return stats

        except Exception as e:
            logger.error(f"❌ 历史数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_historical_data"})
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

    async def _get_last_sync_date(self, symbol: str = None) -> str:
        """获取最后同步日期"""
        try:
            if self.historical_service is None:
                self.historical_service = await get_historical_data_service()

            if symbol:
                # 获取特定股票的最新日期
                latest_date = await self.historical_service.get_latest_date(symbol, "tushare")
                if latest_date:
                    return latest_date

            # 默认返回7天前
            return (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        except Exception as e:
            logger.error(f"❌ 获取最后同步日期失败: {e}")
            return (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    # ==================== 财务数据同步 ====================

    async def sync_financial_data(self, symbols: List[str] = None) -> Dict[str, Any]:
        """同步财务数据"""
        logger.info("🔄 开始同步财务数据...")

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
                cursor = self.db.stock_basic_info.find(
                    {"market_info.market": "CN"},
                    {"code": 1}
                )
                symbols = [doc["code"] async for doc in cursor]

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 需要同步 {len(symbols)} 只股票财务数据")

            # 批量处理
            for i, symbol in enumerate(symbols):
                try:
                    # 速率限制
                    await self.rate_limiter.acquire()

                    financial_data = await self.provider.get_financial_data(symbol)

                    if financial_data:
                        # 保存财务数据
                        success = await self._save_financial_data(symbol, financial_data)
                        if success:
                            stats["success_count"] += 1
                        else:
                            stats["error_count"] += 1
                    else:
                        logger.warning(f"⚠️ {symbol}: 无财务数据")

                    # 进度日志
                    if (i + 1) % 20 == 0:
                        logger.info(f"📈 财务数据同步进度: {i + 1}/{len(symbols)} "
                                   f"(成功: {stats['success_count']}, 错误: {stats['error_count']})")
                        # 输出速率限制器统计
                        limiter_stats = self.rate_limiter.get_stats()
                        logger.info(f"   速率限制: {limiter_stats['current_calls']}/{limiter_stats['max_calls']}次")

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

            return stats

        except Exception as e:
            logger.error(f"❌ 财务数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_financial_data"})
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
        force_update: bool = False
    ) -> Dict[str, Any]:
        """
        同步新闻数据

        Args:
            symbols: 股票代码列表，为None时获取所有股票
            hours_back: 回溯小时数，默认24小时
            max_news_per_stock: 每只股票最大新闻数量
            force_update: 是否强制更新

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
                batch = symbols[i:i + self.batch_size]
                batch_stats = await self._process_news_batch(
                    batch, hours_back, max_news_per_stock
                )

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["news_count"] += batch_stats["news_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志
                progress = min(i + self.batch_size, len(symbols))
                logger.info(f"📈 新闻同步进度: {progress}/{len(symbols)} "
                           f"(成功: {stats['success_count']}, 新闻: {stats['news_count']})")

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

            return stats

        except Exception as e:
            logger.error(f"❌ 新闻数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_news_data"})
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

                # API限流
                await asyncio.sleep(0.2)

            except Exception as e:
                batch_stats["error_count"] += 1
                error_msg = f"{symbol}: {str(e)}"
                batch_stats["errors"].append(error_msg)
                logger.error(f"❌ {symbol} 新闻同步失败: {e}")

        return batch_stats


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
async def run_tushare_basic_info_sync(force_update: bool = False):
    """APScheduler任务：同步股票基础信息"""
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_stock_basic_info(force_update)
        logger.info(f"✅ Tushare基础信息同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare基础信息同步失败: {e}")
        raise


async def run_tushare_quotes_sync():
    """APScheduler任务：同步实时行情"""
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_realtime_quotes()
        logger.info(f"✅ Tushare行情同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare行情同步失败: {e}")
        raise


async def run_tushare_historical_sync(incremental: bool = True):
    """APScheduler任务：同步历史数据"""
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_historical_data(incremental=incremental)
        logger.info(f"✅ Tushare历史数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare历史数据同步失败: {e}")
        raise


async def run_tushare_financial_sync():
    """APScheduler任务：同步财务数据"""
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_financial_data()
        logger.info(f"✅ Tushare财务数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare财务数据同步失败: {e}")
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


async def run_tushare_news_sync(hours_back: int = 24, max_news_per_stock: int = 20):
    """APScheduler任务：同步新闻数据"""
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_news_data(
            hours_back=hours_back,
            max_news_per_stock=max_news_per_stock
        )
        logger.info(f"✅ Tushare新闻数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare新闻数据同步失败: {e}")
        raise
