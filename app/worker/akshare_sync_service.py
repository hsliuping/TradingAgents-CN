"""
AKShare数据同步服务
基于AKShare提供器的统一数据同步方案
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pymongo

from app.core.database import get_mongo_db
from app.services.historical_data_service import get_historical_data_service
from app.services.news_data_service import get_news_data_service
from tradingagents.dataflows.providers.china.akshare import get_akshare_provider

logger = logging.getLogger(__name__)


class AKShareSyncService:
    """
    AKShare数据同步服务
    
    提供完整的数据同步功能：
    - 股票基础信息同步
    - 实时行情同步
    - 历史数据同步
    - 财务数据同步
    """
    
    def __init__(self):
        self.provider = None
        self.historical_service = None  # 延迟初始化
        self.news_service = None  # 延迟初始化
        self.db = None
        self.batch_size = 100
        self.rate_limit_delay = 0.2  # AKShare建议的延迟
    
    async def initialize(self):
        """初始化同步服务"""
        try:
            # 初始化数据库连接
            self.db = get_mongo_db()

            # 初始化历史数据服务
            self.historical_service = await get_historical_data_service()

            # 初始化新闻数据服务
            self.news_service = await get_news_data_service()

            # 初始化AKShare提供器（使用全局单例，确保monkey patch生效）
            self.provider = get_akshare_provider()

            # 测试连接
            if not await self.provider.test_connection():
                raise RuntimeError("❌ AKShare连接失败，无法启动同步服务")

            logger.info("✅ AKShare同步服务初始化完成")
            
        except Exception as e:
            logger.error(f"❌ AKShare同步服务初始化失败: {e}")
            raise
    
    async def sync_stock_basic_info(self, force_update: bool = False) -> Dict[str, Any]:
        """
        同步股票基础信息
        
        Args:
            force_update: 是否强制更新
            
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
            "end_time": None,
            "duration": 0,
            "errors": []
        }
        
        try:
            # 1. 获取股票列表
            stock_list = await self.provider.get_stock_list()
            if not stock_list:
                logger.warning("⚠️ 未获取到股票列表")
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
            
            logger.info(f"🎉 股票基础信息同步完成！")
            logger.info(f"📊 总计: {stats['total_processed']}只, "
                       f"成功: {stats['success_count']}, "
                       f"错误: {stats['error_count']}, "
                       f"跳过: {stats['skipped_count']}, "
                       f"耗时: {stats['duration']:.2f}秒")
            
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
                code = stock_info["code"]
                
                # 检查是否需要更新
                if not force_update:
                    existing = await self.db.stock_basic_info.find_one({"code": code})
                    if existing and self._is_data_fresh(existing.get("updated_at"), hours=24):
                        batch_stats["skipped_count"] += 1
                        continue
                
                # 获取详细基础信息
                basic_info = await self.provider.get_stock_basic_info(code)
                
                if basic_info:
                    # 转换为字典格式
                    if hasattr(basic_info, 'model_dump'):
                        basic_data = basic_info.model_dump()
                    elif hasattr(basic_info, 'dict'):
                        basic_data = basic_info.dict()
                    else:
                        basic_data = basic_info
                    
                    # 🔥 确保 source 字段存在
                    if "source" not in basic_data:
                        basic_data["source"] = "akshare"

                    # 🔥 确保 symbol 字段存在
                    if "symbol" not in basic_data:
                        basic_data["symbol"] = code

                    # 更新到数据库（使用 code + source 联合查询）
                    try:
                        await self.db.stock_basic_info.update_one(
                            {"code": code, "source": "akshare"},
                            {"$set": basic_data},
                            upsert=True
                        )
                        batch_stats["success_count"] += 1
                    except Exception as e:
                        batch_stats["error_count"] += 1
                        batch_stats["errors"].append({
                            "code": code,
                            "error": f"数据库更新失败: {str(e)}",
                            "context": "update_stock_basic_info"
                        })
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": code,
                        "error": "获取基础信息失败",
                        "context": "get_stock_basic_info"
                    })
                
            except Exception as e:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": stock_info.get("code", "unknown"),
                    "error": str(e),
                    "context": "_process_basic_info_batch"
                })
        
        return batch_stats
    
    def _is_data_fresh(self, updated_at: Any, hours: int = 24, minutes: int = None) -> bool:
        """
        检查数据是否新鲜
        
        Args:
            updated_at: 更新时间
            hours: 小时数（默认24小时）
            minutes: 分钟数（如果指定，会覆盖hours参数）
        
        Returns:
            bool: 数据是否新鲜
        """
        if not updated_at:
            return False
        
        try:
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            elif isinstance(updated_at, datetime):
                pass
            else:
                return False
            
            # 转换为UTC时间进行比较
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=None)
            else:
                updated_at = updated_at.replace(tzinfo=None)
            
            now = datetime.utcnow()
            time_diff = now - updated_at
            
            # 如果指定了分钟数，使用分钟数；否则使用小时数
            if minutes is not None:
                return time_diff.total_seconds() < (minutes * 60)
            else:
                return time_diff.total_seconds() < (hours * 3600)
            
        except Exception as e:
            logger.debug(f"检查数据新鲜度失败: {e}")
            return False
    
    async def sync_realtime_quotes(self, symbols: List[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        同步实时行情数据

        Args:
            symbols: 指定股票代码列表，为空则同步所有股票
            force: 是否强制执行（跳过交易时间检查），默认 False

        Returns:
            同步结果统计
        """
        # 🔥 如果指定了股票列表，记录日志
        if symbols:
            logger.info(f"🔄 开始同步指定股票的实时行情（共 {len(symbols)} 只）: {symbols}")
        else:
            logger.info("🔄 开始同步全市场实时行情...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "duration": 0,
            "errors": []
        }

        try:
            # 1. 确定要同步的股票列表
            if symbols is None:
                # 从数据库获取所有上市状态的股票代码（排除退市股票）
                basic_info_cursor = self.db.stock_basic_info.find(
                    {"list_status": "L"},  # 只获取上市状态的股票
                    {"code": 1}
                )
                symbols = [doc["code"] async for doc in basic_info_cursor]

            if not symbols:
                logger.warning("⚠️ 没有找到要同步的股票")
                return stats

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 准备同步 {len(symbols)} 只股票的行情")

            # 🔥 优化：如果只同步1只股票，直接调用单个股票接口，不走批量接口
            if len(symbols) == 1:
                logger.info(f"📈 单个股票同步，直接使用 get_stock_quotes 接口")
                symbol = symbols[0]
                
                # 🔥 先检查数据新鲜度（15分钟内）
                try:
                    existing = await self.db.market_quotes.find_one(
                        {"code": symbol},
                        {"updated_at": 1}
                    )
                    
                    if existing and self._is_data_fresh(existing.get("updated_at"), minutes=15):
                        logger.info(f"✅ {symbol} 数据新鲜（15分钟内），跳过同步")
                        stats["success_count"] = 1
                    else:
                        # 数据超过15分钟或不存在，进行同步
                        success = await self._get_and_save_quotes(symbol)
                        if success:
                            stats["success_count"] = 1
                        else:
                            # 🔥 个股同步失败，回退到全量同步接口
                            logger.warning(f"⚠️ {symbol} 个股同步失败，尝试使用全量同步接口...")
                            all_symbols = await self._get_all_listed_symbols()
                            if all_symbols:
                                quotes_map = await self.provider.get_batch_stock_quotes(all_symbols)
                                if quotes_map:
                                    # 🔥 全量同步成功，批量更新所有数据到数据库
                                    logger.info(f"✅ 全量同步成功，获取到 {len(quotes_map)} 只股票数据，开始批量更新到数据库...")
                                    updated_count = await self._batch_update_quotes_to_db(quotes_map)
                                    logger.info(f"✅ 批量更新完成，共更新 {updated_count} 只股票数据")
                                    
                                    # 检查目标股票是否在更新结果中
                                    if symbol in quotes_map:
                                        stats["success_count"] = 1
                                    else:
                                        stats["error_count"] = 1
                                        stats["errors"].append({
                                            "code": symbol,
                                            "error": "全量同步中未找到该股票数据",
                                            "context": "sync_realtime_quotes_single_fallback"
                                        })
                                else:
                                    stats["error_count"] = 1
                                    stats["errors"].append({
                                        "code": symbol,
                                        "error": "全量同步接口也失败",
                                        "context": "sync_realtime_quotes_single_fallback"
                                    })
                            else:
                                stats["error_count"] = 1
                                stats["errors"].append({
                                    "code": symbol,
                                    "error": "无法获取股票列表",
                                    "context": "sync_realtime_quotes_single_fallback"
                                })
                except Exception as e:
                    logger.error(f"❌ 检查 {symbol} 数据新鲜度失败: {e}，尝试同步")
                    success = await self._get_and_save_quotes(symbol)
                    if success:
                        stats["success_count"] = 1
                    else:
                        stats["error_count"] = 1
                        stats["errors"].append({
                            "code": symbol,
                            "error": f"同步失败: {str(e)}",
                            "context": "sync_realtime_quotes_single"
                        })

                logger.info(f"📈 行情同步进度: 1/1 (成功: {stats['success_count']}, 错误: {stats['error_count']})")
            else:
                # 2. 批量同步：先检查数据新鲜度，只同步需要更新的股票
                logger.info("🔍 检查数据新鲜度（15分钟内）...")
                
                # 检查哪些股票需要同步（数据超过15分钟）
                symbols_to_sync = []
                fresh_quotes_map = {}  # 存储15分钟内的数据
                
                for symbol in symbols:
                    try:
                        # 查询数据库中的最新数据
                        existing = await self.db.market_quotes.find_one(
                            {"code": symbol},
                            {"updated_at": 1, "code": 1, "symbol": 1, "price": 1, "close": 1, 
                             "change_percent": 1, "volume": 1, "amount": 1, "open": 1, "high": 1, 
                             "low": 1, "pre_close": 1, "trade_date": 1}
                        )
                        
                        if existing and self._is_data_fresh(existing.get("updated_at"), minutes=15):  # 15分钟内
                            # 数据在15分钟内，直接使用数据库中的数据
                            fresh_quotes_map[symbol] = existing
                            stats["success_count"] += 1
                            logger.debug(f"✅ {symbol} 数据新鲜（15分钟内），跳过同步")
                        else:
                            # 数据超过15分钟或不存在，需要同步
                            symbols_to_sync.append(symbol)
                    except Exception as e:
                        logger.debug(f"⚠️ 检查 {symbol} 数据新鲜度失败: {e}，将进行同步")
                        symbols_to_sync.append(symbol)
                
                fresh_count = len(fresh_quotes_map)
                sync_count = len(symbols_to_sync)
                logger.info(f"📊 数据检查完成: {fresh_count} 只股票数据新鲜（跳过同步），{sync_count} 只股票需要同步")
                
                # 3. 只同步需要更新的股票
                if symbols_to_sync:
                    logger.info(f"📡 获取 {sync_count} 只股票的实时行情快照...")
                    quotes_map = await self.provider.get_batch_stock_quotes(symbols_to_sync)

                    if not quotes_map:
                        logger.warning("⚠️ 获取全市场快照失败，回退到逐个获取模式")
                        # 回退到逐个获取模式
                        for i in range(0, len(symbols_to_sync), self.batch_size):
                            batch = symbols_to_sync[i:i + self.batch_size]
                            batch_stats = await self._process_quotes_batch_fallback(batch)

                            # 更新统计
                            stats["success_count"] += batch_stats["success_count"]
                            stats["error_count"] += batch_stats["error_count"]
                            stats["errors"].extend(batch_stats["errors"])

                            # 进度日志
                            progress = min(i + self.batch_size, len(symbols_to_sync))
                            logger.info(f"📈 行情同步进度: {progress}/{len(symbols_to_sync)} "
                                       f"(成功: {stats['success_count']}, 错误: {stats['error_count']})")

                            # API限流
                            if i + self.batch_size < len(symbols_to_sync):
                                await asyncio.sleep(self.rate_limit_delay)
                    else:
                        # 4. 使用获取到的全市场数据，分批保存到数据库
                        logger.info(f"✅ 获取到 {len(quotes_map)} 只股票的行情数据，开始保存...")

                        for i in range(0, len(symbols_to_sync), self.batch_size):
                            batch = symbols_to_sync[i:i + self.batch_size]

                            # 从全市场数据中提取当前批次的数据并保存
                            for symbol in batch:
                                try:
                                    quotes = quotes_map.get(symbol)
                                    if quotes:
                                        # 转换为字典格式
                                        if hasattr(quotes, 'model_dump'):
                                            quotes_data = quotes.model_dump()
                                        elif hasattr(quotes, 'dict'):
                                            quotes_data = quotes.dict()
                                        else:
                                            quotes_data = quotes

                                        # 确保 symbol 和 code 字段存在
                                        if "symbol" not in quotes_data:
                                            quotes_data["symbol"] = symbol
                                        if "code" not in quotes_data:
                                            quotes_data["code"] = symbol

                                        # 更新到数据库
                                        await self.db.market_quotes.update_one(
                                            {"code": symbol},
                                            {"$set": quotes_data},
                                            upsert=True
                                        )
                                        stats["success_count"] += 1
                                    else:
                                        stats["error_count"] += 1
                                        stats["errors"].append({
                                            "code": symbol,
                                            "error": "未找到行情数据",
                                            "context": "sync_realtime_quotes"
                                        })
                                except Exception as e:
                                    stats["error_count"] += 1
                                    stats["errors"].append({
                                        "code": symbol,
                                        "error": str(e),
                                        "context": "sync_realtime_quotes"
                                    })

                            # 进度日志
                            progress = min(i + self.batch_size, len(symbols_to_sync))
                            logger.info(f"📈 行情保存进度: {progress}/{len(symbols_to_sync)} "
                                       f"(成功: {stats['success_count']}, 错误: {stats['error_count']})")
                else:
                    logger.info("✅ 所有股票数据都在15分钟内，无需同步")

            # 4. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"🎉 实时行情同步完成！")
            logger.info(f"📊 总计: {stats['total_processed']}只, "
                       f"成功: {stats['success_count']}, "
                       f"错误: {stats['error_count']}, "
                       f"耗时: {stats['duration']:.2f}秒")

            return stats

        except Exception as e:
            logger.error(f"❌ 实时行情同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_realtime_quotes"})
            return stats
    
    async def _process_quotes_batch(self, batch: List[str]) -> Dict[str, Any]:
        """处理行情批次 - 优化版：一次获取全市场快照"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }

        try:
            # 一次性获取全市场快照（避免频繁调用接口）
            logger.debug(f"📊 获取全市场快照以处理 {len(batch)} 只股票...")
            quotes_map = await self.provider.get_batch_stock_quotes(batch)

            if not quotes_map:
                logger.warning("⚠️ 获取全市场快照失败，回退到逐个获取")
                # 回退到原来的逐个获取方式
                return await self._process_quotes_batch_fallback(batch)

            # 批量保存到数据库
            for symbol in batch:
                try:
                    quotes = quotes_map.get(symbol)
                    if quotes:
                        # 转换为字典格式
                        if hasattr(quotes, 'model_dump'):
                            quotes_data = quotes.model_dump()
                        elif hasattr(quotes, 'dict'):
                            quotes_data = quotes.dict()
                        else:
                            quotes_data = quotes

                        # 确保 symbol 和 code 字段存在
                        if "symbol" not in quotes_data:
                            quotes_data["symbol"] = symbol
                        if "code" not in quotes_data:
                            quotes_data["code"] = symbol

                        # 更新到数据库
                        await self.db.market_quotes.update_one(
                            {"code": symbol},
                            {"$set": quotes_data},
                            upsert=True
                        )
                        batch_stats["success_count"] += 1
                    else:
                        batch_stats["error_count"] += 1
                        batch_stats["errors"].append({
                            "code": symbol,
                            "error": "未找到行情数据",
                            "context": "_process_quotes_batch"
                        })
                except Exception as e:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": symbol,
                        "error": str(e),
                        "context": "_process_quotes_batch"
                    })

            return batch_stats

        except Exception as e:
            logger.error(f"❌ 批量处理行情失败: {e}")
            # 回退到原来的逐个获取方式
            return await self._process_quotes_batch_fallback(batch)

    async def _process_quotes_batch_fallback(self, batch: List[str]) -> Dict[str, Any]:
        """处理行情批次 - 回退方案：逐个获取"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }

        # 逐个获取行情数据（添加延迟避免频率限制）
        for symbol in batch:
            try:
                success = await self._get_and_save_quotes(symbol)
                if success:
                    batch_stats["success_count"] += 1
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": symbol,
                        "error": "获取行情数据失败",
                        "context": "_process_quotes_batch_fallback"
                    })

                # 添加延迟避免频率限制
                await asyncio.sleep(0.1)

            except Exception as e:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": symbol,
                    "error": str(e),
                    "context": "_process_quotes_batch_fallback"
                })

        return batch_stats
    
    async def _get_all_listed_symbols(self) -> List[str]:
        """获取所有上市状态的股票代码列表"""
        try:
            basic_info_cursor = self.db.stock_basic_info.find(
                {"list_status": "L"},  # 只获取上市状态的股票
                {"code": 1}
            )
            symbols = [doc["code"] async for doc in basic_info_cursor]
            return symbols
        except Exception as e:
            logger.error(f"❌ 获取股票列表失败: {e}")
            return []
    
    async def _batch_update_quotes_to_db(self, quotes_map: Dict[str, Dict[str, Any]]) -> int:
        """
        批量更新行情数据到数据库
        
        Args:
            quotes_map: 股票代码到行情数据的映射字典
            
        Returns:
            成功更新的股票数量
        """
        updated_count = 0
        batch_size = 100  # 每批处理100只股票
        
        try:
            symbols_list = list(quotes_map.keys())
            
            for i in range(0, len(symbols_list), batch_size):
                batch = symbols_list[i:i + batch_size]
                operations = []
                
                for symbol in batch:
                    quotes = quotes_map.get(symbol)
                    if quotes:
                        # 转换为字典格式
                        if hasattr(quotes, 'model_dump'):
                            quotes_data = quotes.model_dump()
                        elif hasattr(quotes, 'dict'):
                            quotes_data = quotes.dict()
                        else:
                            quotes_data = quotes
                        
                        # 确保 symbol 和 code 字段存在
                        if "symbol" not in quotes_data:
                            quotes_data["symbol"] = symbol
                        if "code" not in quotes_data:
                            quotes_data["code"] = symbol
                        
                        # 构建批量更新操作
                        operations.append(
                            pymongo.UpdateOne(
                                {"code": symbol},
                                {"$set": quotes_data},
                                upsert=True
                            )
                        )
                
                if operations:
                    # 批量执行更新操作
                    result = await self.db.market_quotes.bulk_write(operations, ordered=False)
                    updated_count += result.modified_count + result.upserted_count
                    logger.debug(f"📊 批量更新进度: {min(i + batch_size, len(symbols_list))}/{len(symbols_list)} (已更新: {updated_count})")
            
            return updated_count
        except Exception as e:
            logger.error(f"❌ 批量更新行情数据失败: {e}", exc_info=True)
            return updated_count
    
    async def _get_and_save_quotes(self, symbol: str) -> bool:
        """获取并保存单个股票行情"""
        try:
            # 🔥 先检查数据新鲜度（15分钟内）
            existing = await self.db.market_quotes.find_one(
                {"code": symbol},
                {"updated_at": 1}
            )
            
            if existing and self._is_data_fresh(existing.get("updated_at"), minutes=15):
                logger.debug(f"✅ {symbol} 数据新鲜（15分钟内），跳过同步")
                return True
            
            # 数据超过15分钟或不存在，进行同步
            quotes = await self.provider.get_stock_quotes(symbol)
            if quotes:
                # 转换为字典格式
                if hasattr(quotes, 'model_dump'):
                    quotes_data = quotes.model_dump()
                elif hasattr(quotes, 'dict'):
                    quotes_data = quotes.dict()
                else:
                    quotes_data = quotes

                # 🔥 检查是否通过批量接口获取的，如果是，批量更新全市场数据
                batch_data = quotes_data.pop('_batch_data', None)
                from_batch = quotes_data.pop('_from_batch', False)
                
                if from_batch and batch_data:
                    # 🔥 通过批量接口获取的，批量更新全市场数据到数据库
                    logger.info(f"📊 检测到批量接口数据，开始批量更新 {len(batch_data)} 只股票的行情到数据库...")
                    updated_count = await self._batch_update_quotes_to_db(batch_data)
                    logger.info(f"✅ 批量更新完成，共更新 {updated_count} 只股票数据")
                else:
                    # 单个股票数据，单独保存
                    # 确保 symbol 字段存在
                    if "symbol" not in quotes_data:
                        quotes_data["symbol"] = symbol

                    # 🔥 打印即将保存到数据库的数据
                    logger.info(f"💾 准备保存 {symbol} 行情到数据库:")
                    logger.info(f"   - 最新价(price): {quotes_data.get('price')}")
                    logger.info(f"   - 最高价(high): {quotes_data.get('high')}")
                    logger.info(f"   - 最低价(low): {quotes_data.get('low')}")
                    logger.info(f"   - 开盘价(open): {quotes_data.get('open')}")
                    logger.info(f"   - 昨收价(pre_close): {quotes_data.get('pre_close')}")
                    logger.info(f"   - 成交量(volume): {quotes_data.get('volume')}")
                    logger.info(f"   - 成交额(amount): {quotes_data.get('amount')}")
                    logger.info(f"   - 涨跌幅(change_percent): {quotes_data.get('change_percent')}%")

                    # 更新到数据库
                    result = await self.db.market_quotes.update_one(
                        {"code": symbol},
                        {"$set": quotes_data},
                        upsert=True
                    )

                    logger.info(f"✅ {symbol} 行情已保存到数据库 (matched={result.matched_count}, modified={result.modified_count}, upserted_id={result.upserted_id})")
                
                return True
            return False
        except Exception as e:
            logger.error(f"❌ 获取 {symbol} 行情失败: {e}", exc_info=True)
            return False

    async def sync_historical_data(
        self,
        start_date: str = None,
        end_date: str = None,
        symbols: List[str] = None,
        incremental: bool = True,
        period: str = "daily"
    ) -> Dict[str, Any]:
        """
        同步历史数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 指定股票代码列表
            incremental: 是否增量同步
            period: 数据周期 (daily/weekly/monthly)

        Returns:
            同步结果统计
        """
        period_name = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(period, "日线")
        logger.info(f"🔄 开始同步{period_name}历史数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "duration": 0,
            "errors": []
        }

        try:
            # 1. 确定全局结束日期
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

            # 2. 确定要同步的股票列表
            if symbols is None:
                # 🔥 使用聚合查询去重，确保每个股票代码只计算一次
                # 因为同一个股票可能来自多个数据源（tushare、akshare、baostock），会有重复记录
                pipeline = [
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

            if not symbols:
                logger.warning("⚠️ 没有找到要同步的股票")
                return stats

            stats["total_processed"] = len(symbols)

            # 3. 确定全局起始日期（仅用于日志显示）
            global_start_date = start_date
            if not global_start_date:
                if incremental:
                    global_start_date = "各股票最后日期"
                else:
                    global_start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            logger.info(f"📊 历史数据同步: 结束日期={end_date}, 股票数量={len(symbols)}, 模式={'增量' if incremental else '全量'}")

            # 4. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                batch = symbols[i:i + self.batch_size]
                batch_stats = await self._process_historical_batch(
                    batch, start_date, end_date, period, incremental
                )

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["total_records"] += batch_stats["total_records"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志
                progress = min(i + self.batch_size, len(symbols))
                logger.info(f"📈 历史数据同步进度: {progress}/{len(symbols)} "
                           f"(成功: {stats['success_count']}, 记录: {stats['total_records']})")

                # API限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(self.rate_limit_delay)

            # 4. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"🎉 历史数据同步完成！")
            logger.info(f"📊 总计: {stats['total_processed']}只股票, "
                       f"成功: {stats['success_count']}, "
                       f"记录: {stats['total_records']}条, "
                       f"耗时: {stats['duration']:.2f}秒")

            return stats

        except Exception as e:
            logger.error(f"❌ 历史数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_historical_data"})
            return stats

    async def _process_historical_batch(
        self,
        batch: List[str],
        start_date: str,
        end_date: str,
        period: str = "daily",
        incremental: bool = False
    ) -> Dict[str, Any]:
        """处理历史数据批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "errors": []
        }

        for symbol in batch:
            try:
                # 确定该股票的起始日期
                symbol_start_date = start_date
                if not symbol_start_date:
                    if incremental:
                        # 增量同步：获取该股票的最后日期
                        symbol_start_date = await self._get_last_sync_date(symbol)
                        logger.debug(f"📅 {symbol}: 从 {symbol_start_date} 开始同步")
                    else:
                        # 全量同步：最近1年
                        symbol_start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

                # 获取历史数据
                hist_data = await self.provider.get_historical_data(symbol, symbol_start_date, end_date, period)

                if hist_data is not None and not hist_data.empty:
                    # 保存到统一历史数据集合
                    if self.historical_service is None:
                        self.historical_service = await get_historical_data_service()

                    saved_count = await self.historical_service.save_historical_data(
                        symbol=symbol,
                        data=hist_data,
                        data_source="akshare",
                        market="CN",
                        period=period
                    )

                    batch_stats["success_count"] += 1
                    batch_stats["total_records"] += saved_count
                    logger.debug(f"✅ {symbol}历史数据同步成功: {saved_count}条记录")
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": symbol,
                        "error": "历史数据为空",
                        "context": "_process_historical_batch"
                    })

            except Exception as e:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": symbol,
                    "error": str(e),
                    "context": "_process_historical_batch"
                })

        return batch_stats

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
                latest_date = await self.historical_service.get_latest_date(symbol, "akshare")
                if latest_date:
                    # 返回最后日期的下一天（避免重复同步）
                    try:
                        last_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
                        next_date = last_date_obj + timedelta(days=1)
                        return next_date.strftime('%Y-%m-%d')
                    except ValueError:
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

                    # 如果没有上市日期，只同步最近10年的数据（避免数据量过大导致超时）
                    ten_years_ago = (datetime.now() - timedelta(days=3650)).strftime('%Y-%m-%d')
                    logger.warning(f"⚠️ {symbol}: 未找到上市日期，从 {ten_years_ago} 开始同步（最近10年）")
                    return ten_years_ago

            # 默认返回30天前（确保不漏数据）
            return (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        except Exception as e:
            logger.error(f"❌ 获取最后同步日期失败 {symbol}: {e}")
            # 出错时返回30天前，确保不漏数据
            return (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    async def sync_financial_data(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        同步财务数据

        Args:
            symbols: 指定股票代码列表

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步财务数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "duration": 0,
            "errors": []
        }

        try:
            # 1. 确定要同步的股票列表
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
                logger.info(f"📋 从 stock_basic_info 获取到 {len(symbols)} 只股票")

            if not symbols:
                logger.warning("⚠️ 没有找到要同步的股票")
                return stats

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 准备同步 {len(symbols)} 只股票的财务数据")

            # 2. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                batch = symbols[i:i + self.batch_size]
                batch_stats = await self._process_financial_batch(batch)

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志
                progress = min(i + self.batch_size, len(symbols))
                logger.info(f"📈 财务数据同步进度: {progress}/{len(symbols)} "
                           f"(成功: {stats['success_count']}, 错误: {stats['error_count']})")

                # API限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(self.rate_limit_delay)

            # 3. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"🎉 财务数据同步完成！")
            logger.info(f"📊 总计: {stats['total_processed']}只股票, "
                       f"成功: {stats['success_count']}, "
                       f"错误: {stats['error_count']}, "
                       f"耗时: {stats['duration']:.2f}秒")

            return stats

        except Exception as e:
            logger.error(f"❌ 财务数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_financial_data"})
            return stats

    async def _process_financial_batch(self, batch: List[str]) -> Dict[str, Any]:
        """处理财务数据批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }

        for symbol in batch:
            try:
                # 获取财务数据
                financial_data = await self.provider.get_financial_data(symbol)

                if financial_data:
                    # 使用统一的财务数据服务保存数据
                    success = await self._save_financial_data(symbol, financial_data)
                    if success:
                        batch_stats["success_count"] += 1
                        logger.debug(f"✅ {symbol}财务数据保存成功")
                    else:
                        batch_stats["error_count"] += 1
                        batch_stats["errors"].append({
                            "code": symbol,
                            "error": "财务数据保存失败",
                            "context": "_process_financial_batch"
                        })
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": symbol,
                        "error": "财务数据为空",
                        "context": "_process_financial_batch"
                    })

            except Exception as e:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": symbol,
                    "error": str(e),
                    "context": "_process_financial_batch"
                })

        return batch_stats

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
                data_source="akshare",
                market="CN",
                report_type="quarterly"
            )

            return saved_count > 0

        except Exception as e:
            logger.error(f"❌ 保存 {symbol} 财务数据失败: {e}")
            return False

    async def run_status_check(self) -> Dict[str, Any]:
        """运行状态检查"""
        try:
            logger.info("🔍 开始AKShare状态检查...")

            # 检查提供器连接
            provider_connected = await self.provider.test_connection()

            # 检查数据库集合状态
            collections_status = {}

            # 检查基础信息集合
            basic_count = await self.db.stock_basic_info.count_documents({})
            latest_basic = await self.db.stock_basic_info.find_one(
                {}, sort=[("updated_at", -1)]
            )
            collections_status["stock_basic_info"] = {
                "count": basic_count,
                "latest_update": latest_basic.get("updated_at") if latest_basic else None
            }

            # 检查行情数据集合
            quotes_count = await self.db.market_quotes.count_documents({})
            latest_quotes = await self.db.market_quotes.find_one(
                {}, sort=[("updated_at", -1)]
            )
            collections_status["market_quotes"] = {
                "count": quotes_count,
                "latest_update": latest_quotes.get("updated_at") if latest_quotes else None
            }

            status_result = {
                "provider_connected": provider_connected,
                "collections": collections_status,
                "status_time": datetime.utcnow()
            }

            logger.info(f"✅ AKShare状态检查完成: {status_result}")
            return status_result

        except Exception as e:
            logger.error(f"❌ AKShare状态检查失败: {e}")
            return {
                "provider_connected": False,
                "error": str(e),
                "status_time": datetime.utcnow()
            }

    # ==================== 新闻数据同步 ====================

    async def _get_favorite_stocks(self) -> List[str]:
        """
        获取所有用户的自选股列表（去重）
        注意：只获取最新的文档，避免获取历史旧数据

        Returns:
            自选股代码列表
        """
        try:
            favorite_codes = set()

            # 方法1：从 users 集合的 favorite_stocks 字段获取
            users_cursor = self.db.users.find(
                {"favorite_stocks": {"$exists": True, "$ne": []}},
                {"favorite_stocks.stock_code": 1, "_id": 0}
            )

            async for user in users_cursor:
                for fav in user.get("favorite_stocks", []):
                    code = fav.get("stock_code")
                    if code:
                        favorite_codes.add(code)

            # 方法2：从 user_favorites 集合获取（兼容旧数据结构）
            # 🔥 只获取最新的一个文档（按 updated_at 降序排序）
            latest_doc = await self.db.user_favorites.find_one(
                {"favorites": {"$exists": True, "$ne": []}},
                {"favorites.stock_code": 1, "_id": 0},
                sort=[("updated_at", -1)]  # 按更新时间降序，获取最新的
            )

            if latest_doc:
                logger.info(f"📌 从 user_favorites 获取最新文档的自选股")
                for fav in latest_doc.get("favorites", []):
                    code = fav.get("stock_code")
                    if code:
                        favorite_codes.add(code)

            result = sorted(list(favorite_codes))
            logger.info(f"📌 获取到 {len(result)} 只自选股")
            return result

        except Exception as e:
            logger.error(f"❌ 获取自选股列表失败: {e}")
            return []

    async def sync_news_data(
        self,
        symbols: List[str] = None,
        max_news_per_stock: int = 20,
        force_update: bool = False,
        favorites_only: bool = True
    ) -> Dict[str, Any]:
        """
        同步新闻数据

        Args:
            symbols: 股票代码列表，为None时根据favorites_only决定同步范围
            max_news_per_stock: 每只股票最大新闻数量
            force_update: 是否强制更新
            favorites_only: 是否只同步自选股（默认True）

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步AKShare新闻数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "news_count": 0,
            "start_time": datetime.utcnow(),
            "favorites_only": favorites_only,
            "errors": []
        }

        try:
            # 1. 获取股票列表
            if symbols is None:
                if favorites_only:
                    # 只同步自选股
                    symbols = await self._get_favorite_stocks()
                    logger.info(f"📌 只同步自选股，共 {len(symbols)} 只")
                else:
                    # 获取所有股票（不限制数据源）
                    # 🔥 使用聚合查询去重，确保每个股票代码只计算一次
                    pipeline = [
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
                    logger.info(f"📊 同步所有股票，共 {len(symbols)} 只唯一股票（已去重）")

            if not symbols:
                logger.warning("⚠️ 没有找到需要同步新闻的股票")
                return stats

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 需要同步 {len(symbols)} 只股票的新闻")

            # 2. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                batch = symbols[i:i + self.batch_size]
                batch_stats = await self._process_news_batch(
                    batch, max_news_per_stock
                )

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["news_count"] += batch_stats["news_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志和更新
                progress = min(i + self.batch_size, len(symbols))
                progress_percent = int((progress / len(symbols)) * 100) if len(symbols) > 0 else 0
                logger.info(f"📈 新闻同步进度: {progress}/{len(symbols)} ({progress_percent}%) "
                           f"(成功: {stats['success_count']}, 新闻: {stats['news_count']})")
                
                # 🔥 更新任务进度
                job_id = getattr(self, '_current_job_id', None) or "akshare_news_sync"
                if job_id:
                    try:
                        from app.services.scheduler_service import update_job_progress
                        await update_job_progress(
                            job_id=job_id,
                            progress=progress_percent,
                            message=f"正在同步新闻 ({progress}/{len(symbols)})",
                            total_items=len(symbols),
                            processed_items=progress
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ 更新任务进度失败: {e}")

                # API限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(self.rate_limit_delay)

            # 3. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"✅ AKShare新闻数据同步完成: "
                       f"总计 {stats['total_processed']} 只股票, "
                       f"成功 {stats['success_count']} 只, "
                       f"获取 {stats['news_count']} 条新闻, "
                       f"错误 {stats['error_count']} 只, "
                       f"耗时 {stats['duration']:.2f} 秒")

            return stats

        except Exception as e:
            logger.error(f"❌ AKShare新闻数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_news_data"})
            return stats

    async def _process_news_batch(
        self,
        batch: List[str],
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
                # 从AKShare获取新闻数据
                news_data = await self.provider.get_stock_news(
                    symbol=symbol,
                    limit=max_news_per_stock
                )

                if news_data:
                    # 保存新闻数据
                    saved_count = await self.news_service.save_news_data(
                        news_data=news_data,
                        data_source="akshare",
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


# 全局同步服务实例
_akshare_sync_service = None

async def get_akshare_sync_service() -> AKShareSyncService:
    """获取AKShare同步服务实例"""
    global _akshare_sync_service
    if _akshare_sync_service is None:
        _akshare_sync_service = AKShareSyncService()
        await _akshare_sync_service.initialize()
    return _akshare_sync_service


# APScheduler兼容的任务函数
async def run_akshare_basic_info_sync(force_update: bool = False):
    """APScheduler任务：同步股票基础信息"""
    try:
        service = await get_akshare_sync_service()
        result = await service.sync_stock_basic_info(force_update=force_update)
        logger.info(f"✅ AKShare基础信息同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare基础信息同步失败: {e}")
        raise


async def run_akshare_quotes_sync(force: bool = False):
    """
    APScheduler任务：同步实时行情

    Args:
        force: 是否强制执行（跳过交易时间检查），默认 False
    """
    try:
        service = await get_akshare_sync_service()
        # 注意：AKShare 没有交易时间检查逻辑，force 参数仅用于接口一致性
        result = await service.sync_realtime_quotes(force=force)
        logger.info(f"✅ AKShare行情同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare行情同步失败: {e}")
        raise


async def run_akshare_historical_sync(incremental: bool = True):
    """APScheduler任务：同步历史数据"""
    try:
        service = await get_akshare_sync_service()
        result = await service.sync_historical_data(incremental=incremental)
        logger.info(f"✅ AKShare历史数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare历史数据同步失败: {e}")
        raise


async def run_akshare_financial_sync():
    """APScheduler任务：同步财务数据"""
    try:
        service = await get_akshare_sync_service()
        result = await service.sync_financial_data()
        logger.info(f"✅ AKShare财务数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare财务数据同步失败: {e}")
        raise


async def run_akshare_status_check():
    """APScheduler任务：状态检查"""
    try:
        service = await get_akshare_sync_service()
        result = await service.run_status_check()
        logger.info(f"✅ AKShare状态检查完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare状态检查失败: {e}")
        raise


async def run_akshare_news_sync(max_news_per_stock: int = 20, **kwargs):
    """APScheduler任务：同步新闻数据"""
    job_id = kwargs.get("job_id", "akshare_news_sync")
    try:
        service = await get_akshare_sync_service()
        # 🔥 设置当前任务ID，供sync_news_data使用
        service._current_job_id = job_id
        result = await service.sync_news_data(
            max_news_per_stock=max_news_per_stock
        )
        logger.info(f"✅ AKShare新闻数据同步完成: {result}")
        return result
    except Exception as e:
        # 🔥 任务失败时，更新状态为failed
        try:
            from app.services.scheduler_service import update_job_progress
            await update_job_progress(
                job_id=job_id,
                progress=0,
                message=f"任务失败: {str(e)}"
            )
        except:
            pass
        logger.error(f"❌ AKShare新闻数据同步失败: {e}")
        raise
