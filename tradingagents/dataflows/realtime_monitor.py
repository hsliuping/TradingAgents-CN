from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta, time
import asyncio

from tradingagents.dataflows.hybrid_provider import HybridIndexDataProvider
from tradingagents.utils.logging_manager import get_logger

logger = get_logger('agents')

class RealtimeMarketMonitor:
    """
    实时市场监控引擎 (Lazy Load Mode)
    
    负责提供早盘(Morning)和尾盘(Closing)的市场快照。
    采用按需加载和内存缓存机制，避免后台进程常驻。
    """
    
    def __init__(self, provider: HybridIndexDataProvider = None):
        self.provider = provider or HybridIndexDataProvider()
        self._memory_cache = {}  # {key: (timestamp, data)}
        self.CACHE_TTL = 300     # 5分钟
        
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """尝试从内存缓存获取"""
        if key in self._memory_cache:
            timestamp, data = self._memory_cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.CACHE_TTL:
                logger.info(f"⚡️ [Realtime] Hit Memory Cache: {key}")
                return data
            else:
                del self._memory_cache[key] # Expired
        return None

    def _set_cache(self, key: str, data: Dict[str, Any]):
        """写入内存缓存"""
        self._memory_cache[key] = (datetime.now(), data)

    def _is_market_open(self) -> bool:
        """检查当前是否为交易时间 (简单版)"""
        now = datetime.now().time()
        morning_start = time(9, 15)
        morning_end = time(11, 30)
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        
        return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

    async def get_morning_snapshot(self) -> Dict[str, Any]:
        """
        获取早盘快照 (09:15 - 10:00)
        包含: 隔夜外盘, 集合竞价(如有), 开盘资金流
        """
        cache_key = "morning_snapshot"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        logger.info("🔄 [Realtime] Generating Morning Snapshot...")
        
        # 1. 获取外盘/隔夜数据
        intl_news = await self.provider.get_international_news(lookback_days=1)
        
        # 2. 获取实时资金流 (Sector Flow)
        # Even if it's early, we try to get what's available
        sector_flows = await self.provider.get_sector_flows_async()
        
        # 3. Assemble Snapshot
        snapshot = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": "morning",
            "global_market_summary": intl_news[:3] if intl_news else [], # Top 3 news
            "opening_flow": {
                "top_inflow": sector_flows.get('top_sectors', [])[:3],
                "top_outflow": sector_flows.get('bottom_sectors', [])[:3]
            },
            "status": "generated"
        }
        
        self._set_cache(cache_key, snapshot)
        return snapshot

    async def get_closing_snapshot(self) -> Dict[str, Any]:
        """
        获取尾盘快照 (14:30 - 15:00)
        包含: 全天资金流, 尾盘异动
        """
        cache_key = "closing_snapshot"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        logger.info("🔄 [Realtime] Generating Closing Snapshot...")
        
        # 1. 获取全天资金流
        sector_flows = await self.provider.get_sector_flows_async()
        
        # 2. 获取宏观/消息面更新 (Policy News)
        # We assume general news includes policy news
        latest_news = await self.provider.get_latest_news_async(limit=10)
        policy_news = [n for n in latest_news if '政策' in str(n.get('title', '')) or '监管' in str(n.get('title', ''))]
        
        # 3. Assemble Snapshot
        snapshot = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": "closing",
            "sector_flow_summary": {
                "top_gainers": sector_flows.get('top_sectors', [])[:5],
                "top_losers": sector_flows.get('bottom_sectors', [])[:5]
            },
            "policy_alerts": policy_news[:3],
            "status": "generated"
        }
        
        self._set_cache(cache_key, snapshot)
        return snapshot

    async def get_market_status(self) -> Dict[str, Any]:
        """获取当前市场状态"""
        # Uses AKShare provider's market status check if available, or local check
        return {
            "is_open": self._is_market_open(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": "morning" if datetime.now().hour < 12 else "afternoon"
        }
