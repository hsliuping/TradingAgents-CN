import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from tradingagents.config.database_manager import get_database_manager
from tradingagents.dataflows.hybrid_provider import HybridIndexDataProvider
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")

class DataSourceProbe:
    """
    数据源可用性探测器
    
    负责在 Workflow 执行前探测各个数据源（API 和 Cache）的可用性。
    支持并行异步探测，并实现"缓存优先"策略。
    """
    
    @staticmethod
    async def _check_mongodb_cache(collection_name: str, key_prefix: str, ttl_days: int) -> bool:
        """检查 MongoDB 缓存是否存在且在有效期内"""
        try:
            db_manager = get_database_manager()
            mongo_db = db_manager.get_mongodb_db()
            
            if mongo_db is None:
                return False
                
            collection = mongo_db[collection_name]
            
            # 构建查询条件
            # 注意：这里假设 key 是基于日期的，我们查找最近的一条记录
            # 或者我们需要具体的 key。但在探测阶段，我们可能不知道具体的 date 参数。
            # 策略：查找最近更新的一条记录，如果在 ttl 内，则认为缓存系统可用且有数据
            
            # 获取最新的一条记录
            # cursor = collection.find().sort("timestamp", -1).limit(1)
            # async for doc in cursor: # 如果是 motor 异步驱动
            #     # 但目前 db_manager 返回的是 pymongo 同步 client
            #     # 所以我们这里可能需要用 run_in_executor 或者直接调用（如果是快速查询）
            #     pass
            
            # 由于 pymongo 是同步的，我们在 executor 中运行
            loop = asyncio.get_running_loop()
            
            def check_sync():
                try:
                    doc = collection.find_one(sort=[("timestamp", -1)])
                    if doc:
                        timestamp = doc.get("timestamp")
                        if timestamp and (datetime.now() - timestamp) < timedelta(days=ttl_days):
                            return True
                    return False
                except Exception as e:
                    logger.warning(f"⚠️ [Probe] 缓存查询异常 ({collection_name}): {e}")
                    return False
                
            return await loop.run_in_executor(None, check_sync)
            
        except Exception as e:
            logger.warning(f"⚠️ [Probe] 缓存检查失败 ({collection_name}): {e}")
            return False

    @staticmethod
    async def probe_macro(index_code: str) -> Dict[str, Any]:
        """探测宏观数据源"""
        source = "macro"
        
        # 1. Check Cache First (7 days TTL)
        # 这里的 key 逻辑需要与 macro_analyst 保持一致
        # 但为了探测，只要确认缓存系统工作正常且有近期数据即可
        # 或者我们可以更精确地检查当天的缓存（如果 workflow 总是请求当天）
        # 考虑到 Macro 数据是低频的，只要有最近 7 天的都可以
        if await DataSourceProbe._check_mongodb_cache("macro_analysis_cache", "macro", 7):
            return {"available": True, "source": "cache", "latency": 0.001}
            
        # 2. Check API (Async)
        try:
            start = time.time()
            provider = HybridIndexDataProvider()
            # 尝试获取一个轻量级数据，或者直接调用 get_macro_data 但设置较短超时
            # 由于 get_macro_data 内部可能有重试，我们给它 5 秒
            await asyncio.wait_for(provider.get_macro_data(), timeout=5.0)
            return {"available": True, "source": "api", "latency": time.time() - start}
        except Exception as e:
            return {"available": False, "error": str(e), "latency": time.time() - start}

    @staticmethod
    async def probe_policy() -> Dict[str, Any]:
        """探测政策数据源"""
        # 1. Check Cache (30 days TTL)
        if await DataSourceProbe._check_mongodb_cache("policy_analysis_cache", "policy", 30):
            return {"available": True, "source": "cache", "latency": 0.001}
            
        # 2. Check API
        try:
            start = time.time()
            provider = HybridIndexDataProvider()
            # 获取最近 1 天的政策新闻作为探测
            await asyncio.wait_for(provider.get_policy_news_async(lookback_days=1), timeout=5.0)
            return {"available": True, "source": "api", "latency": time.time() - start}
        except Exception as e:
            return {"available": False, "error": str(e), "latency": time.time() - start}

    @staticmethod
    async def probe_news() -> Dict[str, Any]:
        """探测新闻数据源 (无缓存豁免)"""
        try:
            start = time.time()
            provider = HybridIndexDataProvider()
            # 尝试获取多源快讯
            await asyncio.wait_for(provider.get_multi_source_news_async(lookback_days=1), timeout=5.0)
            return {"available": True, "source": "api", "latency": time.time() - start}
        except Exception as e:
            return {"available": False, "error": str(e), "latency": time.time() - start}

    @staticmethod
    async def probe_sector() -> Dict[str, Any]:
        """探测板块数据源"""
        # 1. Check Cache (1 day TTL)
        if await DataSourceProbe._check_mongodb_cache("sector_analysis_cache", "sector", 1):
            return {"available": True, "source": "cache", "latency": 0.001}
            
        # 2. Check API
        try:
            start = time.time()
            provider = HybridIndexDataProvider()
            # 获取板块资金流
            await asyncio.wait_for(provider.get_sector_flows_async(), timeout=5.0)
            return {"available": True, "source": "api", "latency": time.time() - start}
        except Exception as e:
            return {"available": False, "error": str(e), "latency": time.time() - start}

    @staticmethod
    async def probe_technical(index_code: str) -> Dict[str, Any]:
        """探测技术分析数据源 (无缓存豁免，需要最新行情)"""
        try:
            start = time.time()
            provider = HybridIndexDataProvider()
            # 获取最近几天的日线数据
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
            # 注意：index_code 可能包含后缀，provider 需要处理
            data = await asyncio.wait_for(provider.get_index_daily_async(index_code, start_date=start_date, end_date=end_date), timeout=5.0)
            
            # 检查数据是否有效 (None 或 empty DataFrame)
            is_valid = data is not None and not (hasattr(data, 'empty') and data.empty)
            
            if is_valid:
                return {"available": True, "source": "api", "latency": time.time() - start}
            else:
                return {"available": False, "error": "Empty data returned", "latency": time.time() - start}
                
        except Exception as e:
            return {"available": False, "error": str(e), "latency": time.time() - start}

    @staticmethod
    async def run_all_probes(index_code: str, market_type: str = "A股") -> Dict[str, Any]:
        """
        并行执行所有探测任务
        """
        logger.info(f"🔍 [Probe] 开始数据源并行探测: {index_code} ({market_type})")
        start_time = time.time()
        
        tasks = {
            "macro_db": DataSourceProbe.probe_macro(index_code),
            "policy_db": DataSourceProbe.probe_policy(),
            "news_api": DataSourceProbe.probe_news(),
            "sector_data": DataSourceProbe.probe_sector(),
            "technical": DataSourceProbe.probe_technical(index_code)
        }
        
        # 过滤不必要的探测 (例如美股不需要 A股板块数据)
        # 暂时全量探测，因为 macro/news 可能是通用的
        
        # 并行执行
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # 组装结果
        status_map = {}
        details_map = {}
        
        for key, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"❌ [Probe] {key} 探测异常: {result}")
                status_map[key] = False
                details_map[key] = {"error": str(result)}
            else:
                is_available = result.get("available", False)
                status_map[key] = is_available
                details_map[key] = result
                if is_available:
                    source = result.get("source", "unknown")
                    latency = result.get("latency", 0)
                    logger.info(f"✅ [Probe] {key}: 可用 ({source}, {latency:.3f}s)")
                else:
                    logger.warning(f"⚠️ [Probe] {key}: 不可用 ({result.get('error')})")

        total_time = time.time() - start_time
        logger.info(f"🏁 [Probe] 探测完成，总耗时: {total_time:.3f}s")
        
        return {
            "status": status_map,
            "details": details_map
        }
