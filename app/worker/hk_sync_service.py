#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
港股数据服务（按需获取+缓存模式）

功能：
1. 按需从数据源获取港股信息（yfinance/akshare）
2. 自动缓存到 MongoDB，避免重复请求
3. 支持多数据源：同一股票可有多个数据源记录
4. 使用 (code, source) 联合查询进行 upsert 操作

设计说明：
- 采用按需获取+缓存模式，避免批量同步触发速率限制
- 参考A股数据源管理方式（Tushare/AKShare/BaoStock）
- 缓存时长可配置（默认24小时）
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pymongo import UpdateOne

# 导入港股数据提供器
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.providers.hk.hk_stock import HKStockProvider
from tradingagents.dataflows.providers.hk.improved_hk import ImprovedHKStockProvider
from app.core.database import get_mongo_db
from app.core.config import settings

logger = logging.getLogger(__name__)


class HKDataService:
    """港股数据服务（按需获取+缓存模式）"""

    def __init__(self):
        self.db = get_mongo_db()
        self.settings = settings

        # 数据提供器映射
        self.providers = {
            "yfinance": HKStockProvider(),
            "akshare": ImprovedHKStockProvider(),
        }

        # 缓存配置
        self.cache_hours = getattr(settings, 'HK_DATA_CACHE_HOURS', 24)
        self.default_source = getattr(settings, 'HK_DEFAULT_DATA_SOURCE', 'yfinance')

        # 港股列表缓存（从 AKShare 动态获取）
        self.hk_stock_list = []
        self._stock_list_cache_time = None
        self._stock_list_cache_ttl = 3600 * 24  # 缓存24小时

    async def initialize(self):
        """初始化同步服务"""
        logger.info("✅ 港股同步服务初始化完成")

    def _get_hk_stock_list_from_akshare(self) -> List[str]:
        """
        从 AKShare 获取所有港股列表

        Returns:
            List[str]: 港股代码列表
        """
        try:
            import akshare as ak
            from datetime import datetime, timedelta

            # 检查缓存是否有效
            if (self.hk_stock_list and self._stock_list_cache_time and
                datetime.now() - self._stock_list_cache_time < timedelta(seconds=self._stock_list_cache_ttl)):
                logger.debug(f"📦 使用缓存的港股列表: {len(self.hk_stock_list)} 只")
                return self.hk_stock_list

            logger.info("🔄 从 AKShare 获取港股列表...")

            # 获取所有港股实时行情（包含代码和名称）
            # 使用新浪财经接口（更稳定）
            df = ak.stock_hk_spot()

            if df is None or df.empty:
                logger.warning("⚠️ AKShare 返回空数据，使用备用列表")
                return self._get_fallback_stock_list()

            # 提取股票代码列表
            stock_codes = df['代码'].tolist()

            # 标准化代码格式（确保是5位数字）
            stock_codes = [code.zfill(5) for code in stock_codes if code]

            logger.info(f"✅ 成功获取 {len(stock_codes)} 只港股")

            # 更新缓存
            self.hk_stock_list = stock_codes
            self._stock_list_cache_time = datetime.now()

            return stock_codes

        except Exception as e:
            logger.error(f"❌ 从 AKShare 获取港股列表失败: {e}")
            logger.info("📋 使用备用港股列表")
            return self._get_fallback_stock_list()

    def _get_fallback_stock_list(self) -> List[str]:
        """
        获取备用港股列表（主要港股标的）

        Returns:
            List[str]: 港股代码列表
        """
        return [
            "00700",  # 腾讯控股
            "09988",  # 阿里巴巴
            "03690",  # 美团
            "01810",  # 小米集团
            "00941",  # 中国移动
            "00762",  # 中国联通
            "00728",  # 中国电信
            "00939",  # 建设银行
            "01398",  # 工商银行
            "03988",  # 中国银行
            "00005",  # 汇丰控股
            "01299",  # 友邦保险
            "02318",  # 中国平安
            "02628",  # 中国人寿
            "00857",  # 中国石油
            "00386",  # 中国石化
            "01211",  # 比亚迪
            "02015",  # 理想汽车
            "09868",  # 小鹏汽车
            "09866",  # 蔚来汽车
        ]
    
    async def sync_basic_info_from_source(
        self,
        source: str,
        force_update: bool = False
    ) -> Dict[str, int]:
        """
        从指定数据源同步港股基础信息

        Args:
            source: 数据源名称 (yfinance/akshare)
            force_update: 是否强制更新（强制刷新股票列表）

        Returns:
            Dict: 同步统计信息 {updated: int, inserted: int, failed: int}
        """
        # AKShare 数据源使用批量同步
        if source == "akshare":
            return await self._sync_basic_info_from_akshare_batch(force_update)

        # yfinance 数据源使用逐个同步
        provider = self.providers.get(source)
        if not provider:
            logger.error(f"❌ 不支持的数据源: {source}")
            return {"updated": 0, "inserted": 0, "failed": 0}

        # 如果强制更新，清除缓存
        if force_update:
            self._stock_list_cache_time = None
            logger.info("🔄 强制刷新港股列表")

        # 获取港股列表（从 AKShare 或缓存）
        stock_list = self._get_hk_stock_list_from_akshare()

        if not stock_list:
            logger.error("❌ 无法获取港股列表")
            return {"updated": 0, "inserted": 0, "failed": 0}

        logger.info(f"🇭🇰 开始同步港股基础信息 (数据源: {source})")
        logger.info(f"📊 待同步股票数量: {len(stock_list)}")

        operations = []
        failed_count = 0

        for stock_code in stock_list:
            try:
                # 从数据源获取数据
                stock_info = provider.get_stock_info(stock_code)

                if not stock_info or not stock_info.get('name'):
                    logger.warning(f"⚠️ 跳过无效数据: {stock_code}")
                    failed_count += 1
                    continue

                # 标准化数据格式
                normalized_info = self._normalize_stock_info(stock_info, source)
                normalized_info["code"] = stock_code.lstrip('0').zfill(5)  # 标准化为5位代码
                normalized_info["source"] = source
                normalized_info["updated_at"] = datetime.now()

                # 批量更新操作
                operations.append(
                    UpdateOne(
                        {"code": normalized_info["code"], "source": source},  # 🔥 联合查询条件
                        {"$set": normalized_info},
                        upsert=True
                    )
                )

                logger.debug(f"✅ 准备同步: {stock_code} ({stock_info.get('name')}) from {source}")

            except Exception as e:
                logger.error(f"❌ 同步失败: {stock_code} from {source}: {e}")
                failed_count += 1

        # 执行批量操作
        result = {"updated": 0, "inserted": 0, "failed": failed_count}

        if operations:
            try:
                bulk_result = await self.db.stock_basic_info_hk.bulk_write(operations)
                result["updated"] = bulk_result.modified_count
                result["inserted"] = bulk_result.upserted_count

                logger.info(
                    f"✅ 港股基础信息同步完成 ({source}): "
                    f"更新 {result['updated']} 条, "
                    f"插入 {result['inserted']} 条, "
                    f"失败 {result['failed']} 条"
                )
            except Exception as e:
                logger.error(f"❌ 批量写入失败: {e}")
                result["failed"] += len(operations)

        return result

    async def _sync_basic_info_from_akshare_batch(self, force_update: bool = False) -> Dict[str, int]:
        """
        从 AKShare 批量同步港股基础信息（一次 API 调用获取所有数据）

        Args:
            force_update: 是否强制更新（强制刷新数据）

        Returns:
            Dict: 同步统计信息 {updated: int, inserted: int, failed: int}
        """
        try:
            import akshare as ak
            from datetime import datetime

            logger.info("🇭🇰 开始批量同步港股基础信息 (数据源: akshare)")

            # 获取所有港股实时行情（包含代码、名称等基础信息）
            # 使用新浪财经接口（更稳定）
            df = ak.stock_hk_spot()

            if df is None or df.empty:
                logger.error("❌ AKShare 返回空数据")
                return {"updated": 0, "inserted": 0, "failed": 0}

            logger.info(f"📊 获取到 {len(df)} 只港股数据")

            operations = []
            failed_count = 0

            for _, row in df.iterrows():
                try:
                    # 提取股票代码和名称
                    stock_code = str(row.get('代码', '')).strip()
                    # 新浪接口的列名是 '中文名称'
                    stock_name = str(row.get('中文名称', '')).strip()

                    if not stock_code or not stock_name:
                        failed_count += 1
                        continue

                    # 标准化代码格式（确保是5位数字）
                    normalized_code = stock_code.lstrip('0').zfill(5)

                    # 构建基础信息
                    stock_info = {
                        "code": normalized_code,
                        "name": stock_name,
                        "currency": "HKD",
                        "exchange": "HKG",
                        "market": "香港交易所",
                        "area": "香港",
                        "source": "akshare",
                        "updated_at": datetime.now()
                    }

                    # 可选字段：提取行情数据中的其他信息
                    if '最新价' in row and row['最新价']:
                        stock_info["latest_price"] = float(row['最新价'])

                    if '涨跌幅' in row and row['涨跌幅']:
                        stock_info["change_percent"] = float(row['涨跌幅'])

                    if '总市值' in row and row['总市值']:
                        # 转换为亿港币
                        stock_info["total_mv"] = float(row['总市值']) / 100000000

                    if '市盈率' in row and row['市盈率']:
                        stock_info["pe"] = float(row['市盈率'])

                    # 批量更新操作
                    operations.append(
                        UpdateOne(
                            {"code": normalized_code, "source": "akshare"},
                            {"$set": stock_info},
                            upsert=True
                        )
                    )

                except Exception as e:
                    logger.debug(f"⚠️ 处理股票数据失败: {stock_code}: {e}")
                    failed_count += 1

            # 执行批量操作
            result = {"updated": 0, "inserted": 0, "failed": failed_count}

            if operations:
                try:
                    bulk_result = await self.db.stock_basic_info_hk.bulk_write(operations)
                    result["updated"] = bulk_result.modified_count
                    result["inserted"] = bulk_result.upserted_count

                    logger.info(
                        f"✅ 港股基础信息批量同步完成 (akshare): "
                        f"更新 {result['updated']} 条, "
                        f"插入 {result['inserted']} 条, "
                        f"失败 {result['failed']} 条"
                    )
                except Exception as e:
                    logger.error(f"❌ 批量写入失败: {e}")
                    result["failed"] += len(operations)

            return result

        except Exception as e:
            logger.error(f"❌ AKShare 批量同步失败: {e}")
            return {"updated": 0, "inserted": 0, "failed": 0}

    def _normalize_stock_info(self, stock_info: Dict, source: str) -> Dict:
        """
        标准化股票信息格式
        
        Args:
            stock_info: 原始股票信息
            source: 数据源
        
        Returns:
            Dict: 标准化后的股票信息
        """
        # 提取通用字段
        normalized = {
            "name": stock_info.get("name", ""),
            "name_en": stock_info.get("name_en", ""),
            "currency": stock_info.get("currency", "HKD"),
            "exchange": stock_info.get("exchange", "HKG"),
            "market": "香港交易所",
            "area": "香港",
        }
        
        # 可选字段
        if "market_cap" in stock_info and stock_info["market_cap"]:
            # 转换为亿港币
            normalized["total_mv"] = stock_info["market_cap"] / 100000000
        
        if "sector" in stock_info:
            normalized["sector"] = stock_info["sector"]
        
        if "industry" in stock_info:
            normalized["industry"] = stock_info["industry"]
        
        return normalized
    
    async def sync_quotes_from_source(
        self,
        source: str = "yfinance"
    ) -> Dict[str, int]:
        """
        从指定数据源同步港股实时行情
        
        Args:
            source: 数据源名称 (默认 yfinance)
        
        Returns:
            Dict: 同步统计信息
        """
        provider = self.providers.get(source)
        if not provider:
            logger.error(f"❌ 不支持的数据源: {source}")
            return {"updated": 0, "inserted": 0, "failed": 0}
        
        logger.info(f"🇭🇰 开始同步港股实时行情 (数据源: {source})")
        
        operations = []
        failed_count = 0
        
        for stock_code in self.hk_stock_list:
            try:
                # 获取实时价格
                quote = provider.get_real_time_price(stock_code)
                
                if not quote or not quote.get('price'):
                    logger.warning(f"⚠️ 跳过无效行情: {stock_code}")
                    failed_count += 1
                    continue
                
                # 标准化行情数据
                normalized_quote = {
                    "code": stock_code.lstrip('0').zfill(5),
                    "close": float(quote.get('price', 0)),
                    "open": float(quote.get('open', 0)),
                    "high": float(quote.get('high', 0)),
                    "low": float(quote.get('low', 0)),
                    "volume": int(quote.get('volume', 0)),
                    "currency": "HKD",
                    "updated_at": datetime.now()
                }
                
                # 计算涨跌幅
                if normalized_quote["open"] > 0:
                    pct_chg = ((normalized_quote["close"] - normalized_quote["open"]) / normalized_quote["open"]) * 100
                    normalized_quote["pct_chg"] = round(pct_chg, 2)
                
                operations.append(
                    UpdateOne(
                        {"code": normalized_quote["code"]},
                        {"$set": normalized_quote},
                        upsert=True
                    )
                )
                
                logger.debug(f"✅ 准备同步行情: {stock_code} (价格: {normalized_quote['close']} HKD)")
                
            except Exception as e:
                logger.error(f"❌ 同步行情失败: {stock_code}: {e}")
                failed_count += 1
        
        # 执行批量操作
        result = {"updated": 0, "inserted": 0, "failed": failed_count}
        
        if operations:
            try:
                bulk_result = await self.db.market_quotes_hk.bulk_write(operations)
                result["updated"] = bulk_result.modified_count
                result["inserted"] = bulk_result.upserted_count
                
                logger.info(
                    f"✅ 港股行情同步完成: "
                    f"更新 {result['updated']} 条, "
                    f"插入 {result['inserted']} 条, "
                    f"失败 {result['failed']} 条"
                )
            except Exception as e:
                logger.error(f"❌ 批量写入失败: {e}")
                result["failed"] += len(operations)
        
        return result


# ==================== 全局服务实例 ====================

_hk_sync_service = None

async def get_hk_sync_service() -> HKSyncService:
    """获取港股同步服务实例"""
    global _hk_sync_service
    if _hk_sync_service is None:
        _hk_sync_service = HKSyncService()
        await _hk_sync_service.initialize()
    return _hk_sync_service


# ==================== APScheduler 兼容的任务函数 ====================

async def run_hk_yfinance_basic_info_sync(force_update: bool = False):
    """APScheduler任务：港股基础信息同步（yfinance）"""
    try:
        service = await get_hk_sync_service()
        result = await service.sync_basic_info_from_source("yfinance", force_update)
        logger.info(f"✅ 港股基础信息同步完成 (yfinance): {result}")
        return result
    except Exception as e:
        logger.error(f"❌ 港股基础信息同步失败 (yfinance): {e}")
        raise


async def run_hk_akshare_basic_info_sync(force_update: bool = False):
    """APScheduler任务：港股基础信息同步（akshare）"""
    try:
        service = await get_hk_sync_service()
        result = await service.sync_basic_info_from_source("akshare", force_update)
        logger.info(f"✅ 港股基础信息同步完成 (AKShare): {result}")
        return result
    except Exception as e:
        logger.error(f"❌ 港股基础信息同步失败 (AKShare): {e}")
        raise


async def run_hk_yfinance_quotes_sync():
    """APScheduler任务：港股实时行情同步（yfinance）"""
    try:
        service = await get_hk_sync_service()
        result = await service.sync_quotes_from_source("yfinance")
        logger.info(f"✅ 港股实时行情同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ 港股实时行情同步失败: {e}")
        raise


async def run_hk_status_check():
    """APScheduler任务：港股数据源状态检查"""
    try:
        service = await get_hk_sync_service()
        # 刷新股票列表（如果缓存过期）
        stock_list = service._get_hk_stock_list_from_akshare()

        # 简单的状态检查：返回股票列表数量
        result = {
            "status": "ok",
            "stock_count": len(stock_list),
            "data_sources": list(service.providers.keys()),
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"✅ 港股状态检查完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ 港股状态检查失败: {e}")
        return {"status": "error", "error": str(e)}

