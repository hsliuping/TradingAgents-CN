#!/usr/bin/env python3
"""
财务数据服务
统一管理三数据源的财务数据存储和查询
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd
from pymongo import ReplaceOne

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


class FinancialDataService:
    """财务数据统一管理服务"""
    
    def __init__(self):
        self.collection_name = "stock_financial_data"
        self.db = None
        
    async def initialize(self):
        """初始化服务"""
        try:
            self.db = get_mongo_db()
            if self.db is None:
                raise Exception("MongoDB数据库未初始化")

            # 🔥 确保索引存在（提升查询和 upsert 性能）
            await self._ensure_indexes()

            logger.info("✅ 财务数据服务初始化成功")

        except Exception as e:
            logger.error(f"❌ 财务数据服务初始化失败: {e}")
            raise

    async def _ensure_indexes(self):
        """确保必要的索引存在"""
        try:
            collection = self.db[self.collection_name]
            logger.info("📊 检查并创建财务数据索引...")

            # 1. 复合唯一索引：股票代码+报告期+数据源（用于 upsert）
            await collection.create_index([
                ("symbol", 1),
                ("report_period", 1),
                ("data_source", 1)
            ], unique=True, name="symbol_period_source_unique", background=True)

            # 2. 股票代码索引（查询单只股票的财务数据）
            await collection.create_index([("symbol", 1)], name="symbol_index", background=True)

            # 3. 报告期索引（按时间范围查询）
            await collection.create_index([("report_period", -1)], name="report_period_index", background=True)

            # 4. 复合索引：股票代码+报告期（常用查询）
            await collection.create_index([
                ("symbol", 1),
                ("report_period", -1)
            ], name="symbol_period_index", background=True)

            # 5. 报告类型索引（按季报/年报筛选）
            await collection.create_index([("report_type", 1)], name="report_type_index", background=True)

            # 6. 更新时间索引（数据维护）
            await collection.create_index([("updated_at", -1)], name="updated_at_index", background=True)

            logger.info("✅ 财务数据索引检查完成")
        except Exception as e:
            # 索引创建失败不应该阻止服务启动
            logger.warning(f"⚠️ 创建索引时出现警告（可能已存在）: {e}")
    
    async def save_financial_data(
        self,
        symbol: str,
        financial_data: Dict[str, Any],
        data_source: str,
        market: str = "CN",
        report_period: str = None,
        report_type: str = "quarterly"
    ) -> int:
        """
        保存财务数据到数据库
        
        Args:
            symbol: 股票代码
            financial_data: 财务数据字典
            data_source: 数据源 (tushare/akshare/baostock)
            market: 市场类型 (CN/HK/US)
            report_period: 报告期 (YYYYMMDD)
            report_type: 报告类型 (quarterly/annual)
            
        Returns:
            保存的记录数量
        """
        if self.db is None:
            await self.initialize()
        
        try:
            logger.info(f"💾 开始保存 {symbol} 财务数据 (数据源: {data_source})")
            
            collection = self.db[self.collection_name]
            
            # 标准化财务数据
            standardized_data = self._standardize_financial_data(
                symbol, financial_data, data_source, market, report_period, report_type
            )
            
            if not standardized_data:
                logger.warning(f"⚠️ {symbol} 财务数据标准化后为空")
                return 0
            
            # 批量操作
            operations = []
            saved_count = 0
            
            # 如果是多期数据，分别处理每期
            if isinstance(standardized_data, list):
                for data_item in standardized_data:
                    filter_doc = {
                        "symbol": data_item["symbol"],
                        "report_period": data_item["report_period"],
                        "data_source": data_item["data_source"]
                    }
                    
                    operations.append(ReplaceOne(
                        filter=filter_doc,
                        replacement=data_item,
                        upsert=True
                    ))
                    saved_count += 1
            else:
                # 单期数据
                filter_doc = {
                    "symbol": standardized_data["symbol"],
                    "report_period": standardized_data["report_period"],
                    "data_source": standardized_data["data_source"]
                }
                
                operations.append(ReplaceOne(
                    filter=filter_doc,
                    replacement=standardized_data,
                    upsert=True
                ))
                saved_count = 1
            
            # 执行批量操作
            if operations:
                result = await collection.bulk_write(operations)
                actual_saved = result.upserted_count + result.modified_count
                
                logger.info(f"✅ {symbol} 财务数据保存完成: {actual_saved}条记录")
                return actual_saved
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ 保存财务数据失败 {symbol}: {e}")
            return 0
    
    async def get_financial_data(
        self,
        symbol: str,
        report_period: str = None,
        data_source: str = None,
        report_type: str = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        查询财务数据
        
        Args:
            symbol: 股票代码
            report_period: 报告期筛选
            data_source: 数据源筛选
            report_type: 报告类型筛选
            limit: 限制返回数量
            
        Returns:
            财务数据列表
        """
        if self.db is None:
            await self.initialize()
        
        try:
            collection = self.db[self.collection_name]
            
            # 构建查询条件
            query = {"symbol": symbol}
            
            if report_period:
                query["report_period"] = report_period
            
            if data_source:
                query["data_source"] = data_source
            
            if report_type:
                query["report_type"] = report_type
            
            # 执行查询
            cursor = collection.find(query, {"_id": 0}).sort("report_period", -1)
            
            if limit:
                cursor = cursor.limit(limit)
            
            results = await cursor.to_list(length=None)
            
            logger.info(f"📊 查询财务数据: {symbol} 返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"❌ 查询财务数据失败 {symbol}: {e}")
            return []
    
    async def get_latest_financial_data(
        self,
        symbol: str,
        data_source: str = None
    ) -> Optional[Dict[str, Any]]:
        """获取最新财务数据"""
        results = await self.get_financial_data(
            symbol=symbol,
            data_source=data_source,
            limit=1
        )
        
        return results[0] if results else None
    
    async def get_financial_statistics(self) -> Dict[str, Any]:
        """获取财务数据统计信息"""
        if self.db is None:
            await self.initialize()
        
        try:
            collection = self.db[self.collection_name]
            
            # 按数据源统计
            pipeline = [
                {"$group": {
                    "_id": {
                        "data_source": "$data_source",
                        "report_type": "$report_type"
                    },
                    "count": {"$sum": 1},
                    "latest_period": {"$max": "$report_period"},
                    "symbols": {"$addToSet": "$symbol"}
                }}
            ]
            
            results = await collection.aggregate(pipeline).to_list(length=None)
            
            # 格式化统计结果
            stats = {}
            total_records = 0
            total_symbols = set()
            
            for result in results:
                source = result["_id"]["data_source"]
                report_type = result["_id"]["report_type"]
                count = result["count"]
                symbols = result["symbols"]
                
                if source not in stats:
                    stats[source] = {}
                
                stats[source][report_type] = {
                    "count": count,
                    "latest_period": result["latest_period"],
                    "symbol_count": len(symbols)
                }
                
                total_records += count
                total_symbols.update(symbols)
            
            return {
                "total_records": total_records,
                "total_symbols": len(total_symbols),
                "by_source": stats,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 获取财务数据统计失败: {e}")
            return {}
    
    def _standardize_financial_data(
        self,
        symbol: str,
        financial_data: Dict[str, Any],
        data_source: str,
        market: str,
        report_period: str = None,
        report_type: str = "quarterly"
    ) -> Optional[Dict[str, Any]]:
        """标准化财务数据"""
        try:
            now = datetime.now(timezone.utc)
            
            # 根据数据源进行不同的标准化处理
            if data_source == "tushare":
                return self._standardize_tushare_data(
                    symbol, financial_data, market, report_period, report_type, now
                )
            elif data_source == "akshare":
                return self._standardize_akshare_data(
                    symbol, financial_data, market, report_period, report_type, now
                )
            elif data_source == "baostock":
                return self._standardize_baostock_data(
                    symbol, financial_data, market, report_period, report_type, now
                )
            else:
                logger.warning(f"⚠️ 不支持的数据源: {data_source}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 标准化财务数据失败 {symbol}: {e}")
            return None
    
    def _standardize_tushare_data(
        self,
        symbol: str,
        financial_data: Dict[str, Any],
        market: str,
        report_period: str,
        report_type: str,
        now: datetime
    ) -> Dict[str, Any]:
        """标准化Tushare财务数据"""
        # Tushare数据已经在provider中进行了标准化，直接使用
        base_data = {
            "code": symbol,  # 添加 code 字段以兼容唯一索引
            "symbol": symbol,
            "full_symbol": self._get_full_symbol(symbol, market),
            "market": market,
            "report_period": report_period or financial_data.get("report_period"),
            "report_type": report_type or financial_data.get("report_type", "quarterly"),
            "data_source": "tushare",
            "created_at": now,
            "updated_at": now,
            "version": 1
        }

        # 合并Tushare标准化后的财务数据
        # 排除一些不需要重复的字段
        exclude_fields = {'symbol', 'data_source', 'updated_at'}
        for key, value in financial_data.items():
            if key not in exclude_fields:
                base_data[key] = value

        # 确保关键字段存在
        if 'ann_date' in financial_data:
            base_data['ann_date'] = financial_data['ann_date']

        return base_data
    
    def _standardize_akshare_data(
        self,
        symbol: str,
        financial_data: Dict[str, Any],
        market: str,
        report_period: str,
        report_type: str,
        now: datetime
    ) -> Dict[str, Any]:
        """标准化AKShare财务数据"""
        # AKShare数据需要从多个数据集中提取关键指标
        base_data = {
            "code": symbol,  # 添加 code 字段以兼容唯一索引
            "symbol": symbol,
            "full_symbol": self._get_full_symbol(symbol, market),
            "market": market,
            "report_period": report_period or self._extract_latest_period(financial_data),
            "report_type": report_type,
            "data_source": "akshare",
            "created_at": now,
            "updated_at": now,
            "version": 1
        }

        # 提取关键财务指标
        base_data.update(self._extract_akshare_indicators(financial_data))
        return base_data
    
    def _standardize_baostock_data(
        self,
        symbol: str,
        financial_data: Dict[str, Any],
        market: str,
        report_period: str,
        report_type: str,
        now: datetime
    ) -> Dict[str, Any]:
        """标准化BaoStock财务数据"""
        base_data = {
            "code": symbol,  # 添加 code 字段以兼容唯一索引
            "symbol": symbol,
            "full_symbol": self._get_full_symbol(symbol, market),
            "market": market,
            "report_period": report_period or self._generate_current_period(),
            "report_type": report_type,
            "data_source": "baostock",
            "created_at": now,
            "updated_at": now,
            "version": 1
        }

        # 合并BaoStock财务数据
        base_data.update(financial_data)
        return base_data
    
    def _get_full_symbol(self, symbol: str, market: str) -> str:
        """获取完整股票代码"""
        if market == "CN":
            if symbol.startswith("6"):
                return f"{symbol}.SH"
            else:
                return f"{symbol}.SZ"
        return symbol
    
    def _extract_latest_period(self, financial_data: Dict[str, Any]) -> str:
        """从AKShare数据中提取最新报告期"""
        # 尝试从各个数据集中提取报告期
        for key in ['main_indicators', 'balance_sheet', 'income_statement']:
            if key in financial_data and financial_data[key]:
                records = financial_data[key]
                if isinstance(records, list) and records:
                    # 假设第一条记录是最新的
                    first_record = records[0]
                    for date_field in ['报告期', '报告日期', 'date', '日期']:
                        if date_field in first_record:
                            return str(first_record[date_field]).replace('-', '')
        
        # 如果无法提取，使用当前季度
        return self._generate_current_period()
    
    def _extract_akshare_indicators(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """从AKShare数据中提取关键财务指标"""
        indicators = {}

        # 从主要财务指标中提取
        if 'main_indicators' in financial_data and financial_data['main_indicators']:
            main_data = financial_data['main_indicators'][0] if financial_data['main_indicators'] else {}
            indicators.update({
                "revenue": self._safe_float(main_data.get('营业收入')),
                "net_income": self._safe_float(main_data.get('净利润')),
                "total_assets": self._safe_float(main_data.get('总资产')),
                "total_equity": self._safe_float(main_data.get('股东权益合计')),
            })

            # 🔥 新增：提取 ROE（净资产收益率）
            roe = main_data.get('净资产收益率(ROE)') or main_data.get('净资产收益率')
            if roe is not None:
                indicators["roe"] = self._safe_float(roe)

            # 🔥 新增：提取负债率（资产负债率）
            debt_ratio = main_data.get('资产负债率') or main_data.get('负债率')
            if debt_ratio is not None:
                indicators["debt_to_assets"] = self._safe_float(debt_ratio)

        # 从资产负债表中提取
        if 'balance_sheet' in financial_data and financial_data['balance_sheet']:
            balance_data = financial_data['balance_sheet'][0] if financial_data['balance_sheet'] else {}
            indicators.update({
                "total_liab": self._safe_float(balance_data.get('负债合计')),
                "cash_and_equivalents": self._safe_float(balance_data.get('货币资金')),
            })

            # 🔥 如果主要指标中没有负债率，从资产负债表计算
            if "debt_to_assets" not in indicators:
                total_liab = indicators.get("total_liab")
                total_assets = indicators.get("total_assets")
                if total_liab is not None and total_assets is not None and total_assets > 0:
                    indicators["debt_to_assets"] = (total_liab / total_assets) * 100

        return indicators
    
    def _generate_current_period(self) -> str:
        """生成当前报告期"""
        now = datetime.now()
        year = now.year
        month = now.month
        
        # 根据月份确定季度
        if month <= 3:
            quarter = 1
        elif month <= 6:
            quarter = 2
        elif month <= 9:
            quarter = 3
        else:
            quarter = 4
        
        # 生成报告期格式 YYYYMMDD
        quarter_end_months = {1: "03", 2: "06", 3: "09", 4: "12"}
        quarter_end_days = {1: "31", 2: "30", 3: "30", 4: "31"}
        
        return f"{year}{quarter_end_months[quarter]}{quarter_end_days[quarter]}"
    
    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None:
            return None
        try:
            if isinstance(value, str):
                # 移除可能的单位和格式化字符
                value = value.replace(',', '').replace('万', '').replace('亿', '')
            return float(value)
        except (ValueError, TypeError):
            return None


# 全局服务实例
_financial_data_service = None


async def get_financial_data_service() -> FinancialDataService:
    """获取财务数据服务实例"""
    global _financial_data_service
    if _financial_data_service is None:
        _financial_data_service = FinancialDataService()
        await _financial_data_service.initialize()
    return _financial_data_service
