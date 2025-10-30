#!/usr/bin/env python3
"""
统一历史数据管理服务
为三数据源提供统一的历史数据存储和查询接口
"""
import asyncio
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Union
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database

logger = logging.getLogger(__name__)


class HistoricalDataService:
    """统一历史数据管理服务"""
    
    def __init__(self):
        """初始化服务"""
        self.db = None
        self.collection = None
        
    async def initialize(self):
        """初始化数据库连接"""
        try:
            self.db = get_database()
            self.collection = self.db.stock_daily_quotes
            logger.info("✅ 历史数据服务初始化成功")
        except Exception as e:
            logger.error(f"❌ 历史数据服务初始化失败: {e}")
            raise
    
    async def save_historical_data(
        self,
        symbol: str,
        data: pd.DataFrame,
        data_source: str,
        market: str = "CN",
        period: str = "daily"
    ) -> int:
        """
        保存历史数据到数据库

        Args:
            symbol: 股票代码
            data: 历史数据DataFrame
            data_source: 数据源 (tushare/akshare/baostock)
            market: 市场类型 (CN/HK/US)
            period: 数据周期 (daily/weekly/monthly)

        Returns:
            保存的记录数量
        """
        if self.collection is None:
            await self.initialize()
        
        try:
            if data is None or data.empty:
                logger.warning(f"⚠️ {symbol} 历史数据为空，跳过保存")
                return 0
            
            logger.info(f"💾 开始保存 {symbol} 历史数据: {len(data)}条记录 (数据源: {data_source})")

            # 准备批量操作
            operations = []
            saved_count = 0
            batch_size = 500  # 减小批量大小，避免超时

            for date_index, row in data.iterrows():
                try:
                    # 标准化数据（传递日期索引）
                    doc = self._standardize_record(symbol, row, data_source, market, period, date_index)

                    # 创建upsert操作
                    filter_doc = {
                        "symbol": doc["symbol"],
                        "trade_date": doc["trade_date"],
                        "data_source": doc["data_source"],
                        "period": doc["period"]
                    }

                    from pymongo import ReplaceOne
                    operations.append(ReplaceOne(
                        filter=filter_doc,
                        replacement=doc,
                        upsert=True
                    ))

                    # 批量执行（每500条）
                    if len(operations) >= batch_size:
                        try:
                            result = await self.collection.bulk_write(operations, ordered=False)
                            saved_count += result.upserted_count + result.modified_count
                            logger.debug(f"✅ {symbol} 批量保存 {len(operations)} 条记录成功")
                            operations = []
                        except Exception as bulk_error:
                            logger.error(f"❌ {symbol} 批量写入失败: {bulk_error}")
                            # 清空操作列表，继续处理后续数据
                            operations = []

                except Exception as e:
                    # 获取日期信息用于错误日志
                    date_str = str(date_index) if hasattr(date_index, '__str__') else 'unknown'
                    logger.error(f"❌ 处理记录失败 {symbol} {date_str}: {e}")
                    continue

            # 执行剩余操作
            if operations:
                try:
                    result = await self.collection.bulk_write(operations, ordered=False)
                    saved_count += result.upserted_count + result.modified_count
                    logger.debug(f"✅ {symbol} 最后批次保存 {len(operations)} 条记录成功")
                except Exception as bulk_error:
                    logger.error(f"❌ {symbol} 最后批次写入失败: {bulk_error}")
            
            logger.info(f"✅ {symbol} 历史数据保存完成: {saved_count}条记录")
            return saved_count
            
        except Exception as e:
            logger.error(f"❌ 保存历史数据失败 {symbol}: {e}")
            return 0
    
    def _standardize_record(
        self,
        symbol: str,
        row: pd.Series,
        data_source: str,
        market: str,
        period: str = "daily",
        date_index = None
    ) -> Dict[str, Any]:
        """标准化单条记录"""
        now = datetime.utcnow()

        # 获取日期 - 优先从列中获取，如果索引是日期类型才使用索引
        trade_date = None

        # 先尝试从列中获取日期
        date_from_column = row.get('date') or row.get('trade_date')

        # 如果列中有日期，优先使用列中的日期
        if date_from_column is not None:
            trade_date = self._format_date(date_from_column)
        # 如果列中没有日期，且索引是日期类型，才使用索引
        elif date_index is not None and isinstance(date_index, (date, datetime, pd.Timestamp)):
            trade_date = self._format_date(date_index)
        # 否则使用当前日期
        else:
            trade_date = self._format_date(None)

        # 基础字段映射
        doc = {
            "symbol": symbol,
            "code": symbol,  # 添加 code 字段，与 symbol 保持一致（向后兼容）
            "full_symbol": self._get_full_symbol(symbol, market),
            "market": market,
            "trade_date": trade_date,
            "period": period,
            "data_source": data_source,
            "created_at": now,
            "updated_at": now,
            "version": 1
        }
        
        # OHLCV数据
        doc.update({
            "open": self._safe_float(row.get('open')),
            "high": self._safe_float(row.get('high')),
            "low": self._safe_float(row.get('low')),
            "close": self._safe_float(row.get('close')),
            "pre_close": self._safe_float(row.get('pre_close') or row.get('preclose')),
            "volume": self._safe_float(row.get('volume') or row.get('vol')),
            "amount": self._safe_float(row.get('amount') or row.get('turnover'))
        })
        
        # 计算涨跌数据
        if doc["close"] and doc["pre_close"]:
            doc["change"] = round(doc["close"] - doc["pre_close"], 4)
            doc["pct_chg"] = round((doc["change"] / doc["pre_close"]) * 100, 4)
        else:
            doc["change"] = self._safe_float(row.get('change'))
            doc["pct_chg"] = self._safe_float(row.get('pct_chg') or row.get('change_percent'))
        
        # 可选字段
        optional_fields = {
            "turnover_rate": row.get('turnover_rate') or row.get('turn'),
            "volume_ratio": row.get('volume_ratio'),
            "pe": row.get('pe'),
            "pb": row.get('pb'),
            "ps": row.get('ps'),
            "adjustflag": row.get('adjustflag') or row.get('adj_factor'),
            "tradestatus": row.get('tradestatus'),
            "isST": row.get('isST')
        }
        
        for key, value in optional_fields.items():
            if value is not None:
                doc[key] = self._safe_float(value)
        
        return doc
    
    def _get_full_symbol(self, symbol: str, market: str) -> str:
        """生成完整股票代码"""
        if market == "CN":
            if symbol.startswith('6'):
                return f"{symbol}.SH"
            elif symbol.startswith(('0', '3')):
                return f"{symbol}.SZ"
            else:
                return f"{symbol}.SZ"  # 默认深圳
        elif market == "HK":
            return f"{symbol}.HK"
        elif market == "US":
            return symbol
        else:
            return symbol
    
    def _format_date(self, date_value) -> str:
        """格式化日期"""
        if date_value is None:
            return datetime.now().strftime('%Y-%m-%d')
        
        if isinstance(date_value, str):
            # 处理不同的日期格式
            if len(date_value) == 8:  # YYYYMMDD
                return f"{date_value[:4]}-{date_value[4:6]}-{date_value[6:8]}"
            elif len(date_value) == 10:  # YYYY-MM-DD
                return date_value
            else:
                return date_value
        elif isinstance(date_value, (date, datetime)):
            return date_value.strftime('%Y-%m-%d')
        else:
            return str(date_value)
    
    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None or value == '' or pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    async def get_historical_data(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        data_source: str = None,
        period: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        查询历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            data_source: 数据源筛选
            period: 数据周期筛选 (daily/weekly/monthly)
            limit: 限制返回数量

        Returns:
            历史数据列表
        """
        if self.collection is None:
            await self.initialize()
        
        try:
            # 构建查询条件
            query = {"symbol": symbol}
            
            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter["$gte"] = start_date
                if end_date:
                    date_filter["$lte"] = end_date
                query["trade_date"] = date_filter
            
            if data_source:
                query["data_source"] = data_source

            if period:
                query["period"] = period
            
            # 执行查询
            cursor = self.collection.find(query).sort("trade_date", -1)
            
            if limit:
                cursor = cursor.limit(limit)
            
            results = await cursor.to_list(length=None)
            
            logger.info(f"📊 查询历史数据: {symbol} 返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"❌ 查询历史数据失败 {symbol}: {e}")
            return []
    
    async def get_latest_date(self, symbol: str, data_source: str) -> Optional[str]:
        """获取最新数据日期"""
        if self.collection is None:
            await self.initialize()
        
        try:
            result = await self.collection.find_one(
                {"symbol": symbol, "data_source": data_source},
                sort=[("trade_date", -1)]
            )
            
            if result:
                return result["trade_date"]
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取最新日期失败 {symbol}: {e}")
            return None
    
    async def get_data_statistics(self) -> Dict[str, Any]:
        """获取数据统计信息"""
        if self.collection is None:
            await self.initialize()
        
        try:
            # 总记录数
            total_count = await self.collection.count_documents({})
            
            # 按数据源统计
            source_stats = await self.collection.aggregate([
                {"$group": {
                    "_id": "$data_source",
                    "count": {"$sum": 1},
                    "latest_date": {"$max": "$trade_date"}
                }}
            ]).to_list(length=None)
            
            # 按市场统计
            market_stats = await self.collection.aggregate([
                {"$group": {
                    "_id": "$market",
                    "count": {"$sum": 1}
                }}
            ]).to_list(length=None)
            
            # 股票数量统计
            symbol_count = len(await self.collection.distinct("symbol"))
            
            return {
                "total_records": total_count,
                "total_symbols": symbol_count,
                "by_source": {item["_id"]: {
                    "count": item["count"],
                    "latest_date": item.get("latest_date")
                } for item in source_stats},
                "by_market": {item["_id"]: item["count"] for item in market_stats},
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {}


# 全局服务实例
_historical_data_service = None


async def get_historical_data_service() -> HistoricalDataService:
    """获取历史数据服务实例"""
    global _historical_data_service
    if _historical_data_service is None:
        _historical_data_service = HistoricalDataService()
        await _historical_data_service.initialize()
    return _historical_data_service
