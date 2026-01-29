#!/usr/bin/env python3
"""
财务数据同步服务
统一管理三数据源的财务数据同步
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from app.core.database import get_mongo_db
from app.services.financial_data_service import get_financial_data_service
from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
from tradingagents.dataflows.providers.china.akshare import get_akshare_provider
from tradingagents.dataflows.providers.china.baostock import get_baostock_provider

logger = logging.getLogger(__name__)


@dataclass
class FinancialSyncStats:
    """财务数据同步统计"""
    total_symbols: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_symbols": self.total_symbols,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "success_rate": round(self.success_count / max(self.total_symbols, 1) * 100, 2),
            "errors": self.errors[:10]  # 只返回前10个错误
        }


class FinancialDataSyncService:
    """财务数据同步服务"""
    
    def __init__(self):
        self.db = None
        self.financial_service = None
        self.providers = {}
        
    async def initialize(self):
        """初始化服务"""
        try:
            self.db = get_mongo_db()
            self.financial_service = await get_financial_data_service()
            
            # 初始化数据源提供者
            self.providers = {
                "tushare": get_tushare_provider(),
                "akshare": get_akshare_provider(),
                "baostock": get_baostock_provider()
            }
            
            logger.info("✅ 财务数据同步服务初始化成功")
            
        except Exception as e:
            logger.error(f"❌ 财务数据同步服务初始化失败: {e}")
            raise
    
    async def sync_financial_data(
        self,
        symbols: List[str] = None,
        data_sources: List[str] = None,
        report_types: List[str] = None,
        batch_size: int = 50,
        delay_seconds: float = 1.0
    ) -> Dict[str, FinancialSyncStats]:
        """
        同步财务数据
        
        Args:
            symbols: 股票代码列表，None表示同步所有股票
            data_sources: 数据源列表 ["tushare", "akshare", "baostock"]
            report_types: 报告类型列表 ["quarterly", "annual"]
            batch_size: 批处理大小
            delay_seconds: API调用延迟
            
        Returns:
            各数据源的同步统计结果
        """
        if self.db is None:
            await self.initialize()
        
        # 默认参数
        if data_sources is None:
            data_sources = ["tushare", "akshare", "baostock"]
        if report_types is None:
            report_types = ["quarterly", "annual"]  # 同时同步季报和年报
        
        logger.info(f"🔄 开始财务数据同步: 数据源={data_sources}, 报告类型={report_types}")
        
        # 获取股票列表
        if symbols is None:
            symbols = await self._get_stock_symbols()
        
        if not symbols:
            logger.warning("⚠️ 没有找到要同步的股票")
            return {}
        
        logger.info(f"📊 准备同步 {len(symbols)} 只股票的财务数据")
        
        # 为每个数据源执行同步
        results = {}
        
        for data_source in data_sources:
            if data_source not in self.providers:
                logger.warning(f"⚠️ 不支持的数据源: {data_source}")
                continue
            
            logger.info(f"🚀 开始 {data_source} 财务数据同步...")
            
            stats = await self._sync_source_financial_data(
                data_source=data_source,
                symbols=symbols,
                report_types=report_types,
                batch_size=batch_size,
                delay_seconds=delay_seconds
            )
            
            results[data_source] = stats
            
            logger.info(f"✅ {data_source} 财务数据同步完成: "
                       f"成功 {stats.success_count}/{stats.total_symbols} "
                       f"({stats.success_count/max(stats.total_symbols,1)*100:.1f}%)")
        
        return results
    
    async def _sync_source_financial_data(
        self,
        data_source: str,
        symbols: List[str],
        report_types: List[str],
        batch_size: int,
        delay_seconds: float
    ) -> FinancialSyncStats:
        """同步单个数据源的财务数据"""
        stats = FinancialSyncStats()
        stats.total_symbols = len(symbols)
        stats.start_time = datetime.now(timezone.utc)
        
        provider = self.providers[data_source]
        
        # 检查数据源可用性
        if not provider.is_available():
            logger.warning(f"⚠️ {data_source} 数据源不可用")
            stats.skipped_count = len(symbols)
            stats.end_time = datetime.now(timezone.utc)
            return stats
        
        # 批量处理股票
        for i in range(0, len(symbols), batch_size):
            batch_symbols = symbols[i:i + batch_size]
            
            logger.info(f"📈 {data_source} 处理批次 {i//batch_size + 1}: "
                       f"{len(batch_symbols)} 只股票")
            
            # 并发处理批次内的股票
            tasks = []
            for symbol in batch_symbols:
                task = self._sync_symbol_financial_data(
                    symbol=symbol,
                    data_source=data_source,
                    provider=provider,
                    report_types=report_types
                )
                tasks.append(task)
            
            # 执行并发任务
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计批次结果
            for j, result in enumerate(batch_results):
                symbol = batch_symbols[j]
                
                if isinstance(result, Exception):
                    stats.error_count += 1
                    stats.errors.append({
                        "symbol": symbol,
                        "data_source": data_source,
                        "error": str(result),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    logger.error(f"❌ {symbol} 财务数据同步失败 ({data_source}): {result}")
                elif result:
                    stats.success_count += 1
                    logger.debug(f"✅ {symbol} 财务数据同步成功 ({data_source})")
                else:
                    stats.skipped_count += 1
                    logger.debug(f"⏭️ {symbol} 财务数据跳过 ({data_source})")
            
            # API限流延迟
            if i + batch_size < len(symbols):
                await asyncio.sleep(delay_seconds)
        
        stats.end_time = datetime.now(timezone.utc)
        stats.duration = (stats.end_time - stats.start_time).total_seconds()
        
        return stats
    
    async def _sync_symbol_financial_data(
        self,
        symbol: str,
        data_source: str,
        provider: Any,
        report_types: List[str]
    ) -> bool:
        """同步单只股票的财务数据"""
        try:
            # 获取财务数据
            financial_data = await provider.get_financial_data(symbol)
            
            if not financial_data:
                logger.debug(f"⚠️ {symbol} 无财务数据 ({data_source})")
                return False
            
            # 为每种报告类型保存数据
            saved_count = 0
            for report_type in report_types:
                count = await self.financial_service.save_financial_data(
                    symbol=symbol,
                    financial_data=financial_data,
                    data_source=data_source,
                    report_type=report_type
                )
                saved_count += count
            
            return saved_count > 0
            
        except Exception as e:
            logger.error(f"❌ {symbol} 财务数据同步异常 ({data_source}): {e}")
            raise
    
    async def _get_stock_symbols(self) -> List[str]:
        """获取股票代码列表（去重）"""
        try:
            # 🔥 使用聚合查询去重，确保每个股票代码只计算一次
            # 因为同一个股票可能来自多个数据源（tushare、akshare、baostock），会有重复记录
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
            logger.info(f"📋 从 stock_basic_info 获取到 {len(symbols)} 只唯一股票代码（已去重）")

            return symbols

        except Exception as e:
            logger.error(f"❌ 获取股票代码列表失败: {e}")
            return []
    
    async def get_sync_statistics(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        try:
            if self.financial_service is None:
                await self.initialize()
            
            return await self.financial_service.get_financial_statistics()
            
        except Exception as e:
            logger.error(f"❌ 获取同步统计失败: {e}")
            return {}
    
    async def sync_single_stock(
        self,
        symbol: str,
        data_sources: List[str] = None
    ) -> Dict[str, bool]:
        """同步单只股票的财务数据"""
        if self.db is None:
            await self.initialize()
        
        if data_sources is None:
            data_sources = ["tushare", "akshare", "baostock"]
        
        results = {}
        
        for data_source in data_sources:
            if data_source not in self.providers:
                results[data_source] = False
                continue
            
            try:
                provider = self.providers[data_source]
                
                if not provider.is_available():
                    results[data_source] = False
                    continue
                
                result = await self._sync_symbol_financial_data(
                    symbol=symbol,
                    data_source=data_source,
                    provider=provider,
                    report_types=["quarterly"]
                )
                
                results[data_source] = result
                
            except Exception as e:
                logger.error(f"❌ {symbol} 单股票财务数据同步失败 ({data_source}): {e}")
                results[data_source] = False
        
        return results


# 全局服务实例
_financial_sync_service = None


async def get_financial_sync_service() -> FinancialDataSyncService:
    """获取财务数据同步服务实例"""
    global _financial_sync_service
    if _financial_sync_service is None:
        _financial_sync_service = FinancialDataSyncService()
        await _financial_sync_service.initialize()
    return _financial_sync_service
