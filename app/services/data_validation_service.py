"""
数据校验服务

在分析之前检查数据库中股票数据的完整性和有效性：
1. 股票基础信息是否存在
2. 历史数据是否存在且在分析时间范围内
3. 财务数据是否存在（可选）
4. 实时行情数据是否存在（可选）
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


@dataclass
class DataValidationResult:
    """数据校验结果"""
    is_valid: bool
    message: str
    missing_data: List[str]
    details: Dict[str, Any]


class DataValidationService:
    """数据校验服务"""
    
    def __init__(self):
        """初始化服务"""
        self.db = None
    
    def _get_db(self):
        """获取数据库连接（懒加载）"""
        if self.db is None:
            self.db = get_mongo_db()
        return self.db
    
    async def validate_stock_data(
        self,
        symbol: str,
        analysis_date: str,
        market_type: str = "cn",
        check_basic_info: bool = True,
        check_historical_data: bool = True,
        check_financial_data: bool = False,
        check_realtime_quotes: bool = False,
        historical_days: int = 365  # 默认检查近1年的历史数据
    ) -> DataValidationResult:
        """
        校验股票数据的完整性和有效性
        
        Args:
            symbol: 股票代码（6位）
            analysis_date: 分析日期（YYYY-MM-DD格式）
            market_type: 市场类型（cn/hk/us）
            check_basic_info: 是否检查基础信息
            check_historical_data: 是否检查历史数据
            check_financial_data: 是否检查财务数据（可选）
            check_realtime_quotes: 是否检查实时行情（可选）
            historical_days: 需要检查的历史数据天数（默认365天）
            
        Returns:
            DataValidationResult: 校验结果
        """
        db = self._get_db()
        symbol6 = str(symbol).zfill(6)
        missing_data = []
        details = {}
        
        try:
            # 解析分析日期（支持多种格式：YYYY-MM-DD 或 ISO 8601 格式，或已经是 datetime 对象）
            analysis_dt = None

            # 如果已经是 datetime 对象，直接使用
            if isinstance(analysis_date, datetime):
                analysis_dt = analysis_date
            else:
                # 如果是字符串，尝试解析
                date_formats = [
                    '%Y-%m-%d',  # YYYY-MM-DD
                    '%Y-%m-%dT%H:%M:%S',  # ISO 8601 with time
                    '%Y-%m-%dT%H:%M:%S.%f',  # ISO 8601 with microseconds
                    '%Y-%m-%d %H:%M:%S',  # 空格分隔的日期时间
                ]

                # 如果包含 'T'，先尝试提取日期部分
                if 'T' in analysis_date:
                    analysis_date_part = analysis_date.split('T')[0]
                    try:
                        analysis_dt = datetime.strptime(analysis_date_part, '%Y-%m-%d')
                    except ValueError:
                        pass

                # 如果还没有解析成功，尝试所有格式
                if analysis_dt is None:
                    for fmt in date_formats:
                        try:
                            analysis_dt = datetime.strptime(analysis_date, fmt)
                            break
                        except ValueError:
                            continue

            if analysis_dt is None:
                return DataValidationResult(
                    is_valid=False,
                    message=f"分析日期格式错误: {analysis_date}，应为 YYYY-MM-DD 格式或 ISO 8601 格式",
                    missing_data=["analysis_date_format"],
                    details={"error": "日期格式错误"}
                )
            
            # 1. 检查股票基础信息
            if check_basic_info:
                basic_info_valid, basic_info_msg, basic_info_details = await self._check_basic_info(
                    db, symbol6, market_type
                )
                details["basic_info"] = basic_info_details
                if not basic_info_valid:
                    missing_data.append("基础信息")
                    return DataValidationResult(
                        is_valid=False,
                        message=f"股票 {symbol6} 的基础信息不存在，请先同步股票基础数据",
                        missing_data=missing_data,
                        details=details
                    )
            
            # 2. 检查历史数据
            if check_historical_data:
                # 计算需要检查的日期范围（确保都是字符串格式 YYYY-MM-DD）
                start_date = (analysis_dt - timedelta(days=historical_days)).strftime('%Y-%m-%d')
                end_date = analysis_dt.strftime('%Y-%m-%d')  # 使用 analysis_dt 而不是 analysis_date
                analysis_date_str = analysis_dt.strftime('%Y-%m-%d')  # 分析日期字符串

                historical_valid, historical_msg, historical_details = await self._check_historical_data(
                    db, symbol6, market_type, start_date, end_date, analysis_date_str
                )
                details["historical_data"] = historical_details
                if not historical_valid:
                    missing_data.append("历史数据")
                    return DataValidationResult(
                        is_valid=False,
                        message=f"股票 {symbol6} 在 {start_date} 至 {end_date} 期间的历史数据不足，请先同步历史数据",
                        missing_data=missing_data,
                        details=details
                    )
            
            # 3. 检查财务数据（可选）
            if check_financial_data:
                financial_valid, financial_msg, financial_details = await self._check_financial_data(
                    db, symbol6, market_type, analysis_date_str
                )
                details["financial_data"] = financial_details
                if not financial_valid:
                    missing_data.append("财务数据")
                    # 财务数据缺失不阻止分析，只记录警告
                    logger.warning(f"⚠️ 股票 {symbol6} 的财务数据不存在: {financial_msg}")
            
            # 4. 检查实时行情（可选）
            if check_realtime_quotes:
                quotes_valid, quotes_msg, quotes_details = await self._check_realtime_quotes(
                    db, symbol6, market_type
                )
                details["realtime_quotes"] = quotes_details
                if not quotes_valid:
                    missing_data.append("实时行情")
                    # 实时行情缺失不阻止分析，只记录警告
                    logger.warning(f"⚠️ 股票 {symbol6} 的实时行情数据不存在: {quotes_msg}")
            
            # 所有必需数据都存在
            return DataValidationResult(
                is_valid=True,
                message=f"股票 {symbol6} 的数据校验通过",
                missing_data=[],
                details=details
            )
            
        except Exception as e:
            logger.error(f"❌ 数据校验过程出错: {e}", exc_info=True)
            return DataValidationResult(
                is_valid=False,
                message=f"数据校验过程出错: {str(e)}",
                missing_data=["validation_error"],
                details={"error": str(e)}
            )
    
    async def _check_basic_info(
        self,
        db,
        symbol: str,
        market_type: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        检查股票基础信息是否存在
        
        Returns:
            (is_valid, message, details)
        """
        try:
            # 根据市场类型选择集合
            collection_map = {
                "cn": "stock_basic_info",
                "hk": "stock_basic_info_hk",
                "us": "stock_basic_info_us"
            }
            collection_name = collection_map.get(market_type, "stock_basic_info")
            
            # 查询股票基础信息
            query = {"$or": [{"symbol": symbol}, {"code": symbol}]}
            doc = await db[collection_name].find_one(query, {"_id": 0, "symbol": 1, "code": 1, "name": 1, "list_date": 1})
            
            if doc:
                return True, f"股票 {symbol} 基础信息存在", {
                    "exists": True,
                    "name": doc.get("name"),
                    "list_date": doc.get("list_date")
                }
            else:
                return False, f"股票 {symbol} 基础信息不存在", {
                    "exists": False,
                    "collection": collection_name
                }
        except Exception as e:
            logger.error(f"检查基础信息时出错: {e}")
            return False, f"检查基础信息时出错: {str(e)}", {"error": str(e)}
    
    async def _check_historical_data(
        self,
        db,
        symbol: str,
        market_type: str,
        start_date: str,
        end_date: str,
        analysis_date: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        检查历史数据是否存在且在分析时间范围内
        
        Returns:
            (is_valid, message, details)
        """
        try:
            # 根据市场类型选择集合
            collection_map = {
                "cn": "stock_daily_quotes",  # 统一历史数据集合
                "hk": "stock_daily_quotes_hk",
                "us": "stock_daily_quotes_us"
            }
            # 如果没有对应的集合，尝试使用通用集合
            collection_name = collection_map.get(market_type, "stock_daily_quotes")
            
            # 如果集合不存在，尝试使用旧的历史数据集合
            collections_to_try = [
                collection_name,
                "stock_daily_history",  # 旧的历史数据集合
                "stock_daily_quotes"  # 通用集合
            ]
            
            data_found = False
            data_count = 0
            earliest_date = None
            latest_date = None
            analysis_date_data = None
            
            for coll_name in collections_to_try:
                try:
                    # 检查集合是否存在
                    collection_names = await db.list_collection_names()
                    if coll_name not in collection_names:
                        continue
                    
                    # 查询历史数据总数
                    total_count = await db[coll_name].count_documents({
                        "$or": [{"symbol": symbol}, {"code": symbol}],
                        "trade_date": {"$gte": start_date, "$lte": end_date}
                    })
                    
                    if total_count > 0:
                        data_found = True
                        data_count = total_count
                        
                        # 查询最早和最晚的日期
                        earliest_doc = await db[coll_name].find_one(
                            {"$or": [{"symbol": symbol}, {"code": symbol}], "trade_date": {"$gte": start_date}},
                            sort=[("trade_date", 1)]
                        )
                        latest_doc = await db[coll_name].find_one(
                            {"$or": [{"symbol": symbol}, {"code": symbol}], "trade_date": {"$lte": end_date}},
                            sort=[("trade_date", -1)]
                        )
                        
                        if earliest_doc:
                            earliest_date = earliest_doc.get("trade_date")
                        if latest_doc:
                            latest_date = latest_doc.get("trade_date")
                        
                        # 检查分析日期当天的数据是否存在
                        analysis_doc = await db[coll_name].find_one({
                            "$or": [{"symbol": symbol}, {"code": symbol}],
                            "trade_date": analysis_date
                        })
                        analysis_date_data = analysis_doc is not None
                        
                        break  # 找到数据后退出循环
                except Exception as e:
                    logger.debug(f"查询集合 {coll_name} 时出错: {e}")
                    continue
            
            if data_found:
                # 检查数据是否足够（至少需要一定数量的交易日）
                min_required_days = 30  # 至少需要30个交易日
                if data_count < min_required_days:
                    return False, f"历史数据不足（仅 {data_count} 条，需要至少 {min_required_days} 条）", {
                        "exists": True,
                        "count": data_count,
                        "min_required": min_required_days,
                        "earliest_date": earliest_date,
                        "latest_date": latest_date,
                        "analysis_date_exists": analysis_date_data
                    }
                
                return True, f"历史数据存在（共 {data_count} 条）", {
                    "exists": True,
                    "count": data_count,
                    "earliest_date": earliest_date,
                    "latest_date": latest_date,
                    "analysis_date_exists": analysis_date_data,
                    "date_range": f"{start_date} 至 {end_date}"
                }
            else:
                return False, f"历史数据不存在（日期范围: {start_date} 至 {end_date}）", {
                    "exists": False,
                    "date_range": f"{start_date} 至 {end_date}",
                    "collections_checked": collections_to_try
                }
        except Exception as e:
            logger.error(f"检查历史数据时出错: {e}")
            return False, f"检查历史数据时出错: {str(e)}", {"error": str(e)}
    
    async def _check_financial_data(
        self,
        db,
        symbol: str,
        market_type: str,
        analysis_date: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        检查财务数据是否存在
        
        Returns:
            (is_valid, message, details)
        """
        try:
            # 根据市场类型选择集合
            collection_map = {
                "cn": "stock_financial_data",
                "hk": "stock_financial_data_hk",
                "us": "stock_financial_data_us"
            }
            collection_name = collection_map.get(market_type, "stock_financial_data")
            
            # 查询最新的财务数据（不限制日期，因为财务数据是定期更新的）
            doc = await db[collection_name].find_one(
                {"$or": [{"symbol": symbol}, {"code": symbol}]},
                sort=[("report_period", -1)],
                projection={"_id": 0, "symbol": 1, "report_period": 1, "report_type": 1}
            )
            
            if doc:
                return True, f"财务数据存在（最新报告期: {doc.get('report_period')}）", {
                    "exists": True,
                    "latest_report_period": doc.get("report_period"),
                    "report_type": doc.get("report_type")
                }
            else:
                return False, f"财务数据不存在", {
                    "exists": False,
                    "collection": collection_name
                }
        except Exception as e:
            logger.error(f"检查财务数据时出错: {e}")
            return False, f"检查财务数据时出错: {str(e)}", {"error": str(e)}
    
    async def _check_realtime_quotes(
        self,
        db,
        symbol: str,
        market_type: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        检查实时行情数据是否存在
        
        Returns:
            (is_valid, message, details)
        """
        try:
            # 根据市场类型选择集合
            collection_map = {
                "cn": "market_quotes",
                "hk": "market_quotes_hk",
                "us": "market_quotes_us"
            }
            collection_name = collection_map.get(market_type, "market_quotes")
            
            # 查询实时行情
            doc = await db[collection_name].find_one(
                {"$or": [{"symbol": symbol}, {"code": symbol}]},
                projection={"_id": 0, "symbol": 1, "code": 1, "close": 1, "update_time": 1}
            )
            
            if doc:
                return True, f"实时行情存在", {
                    "exists": True,
                    "current_price": doc.get("close"),
                    "update_time": doc.get("update_time")
                }
            else:
                return False, f"实时行情不存在", {
                    "exists": False,
                    "collection": collection_name
                }
        except Exception as e:
            logger.error(f"检查实时行情时出错: {e}")
            return False, f"检查实时行情时出错: {str(e)}", {"error": str(e)}


# 单例实例
_validation_service = None


def get_data_validation_service() -> DataValidationService:
    """获取数据校验服务单例"""
    global _validation_service
    if _validation_service is None:
        _validation_service = DataValidationService()
    return _validation_service
