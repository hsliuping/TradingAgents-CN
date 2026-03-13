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
        check_historical_data: bool = False,  # 🔥 默认禁用历史数据检查（避免误报）
        check_financial_data: bool = False,
        check_realtime_quotes: bool = False,
        check_data_freshness: bool = False,  # 🔥 数据新鲜度检查：防止使用陈旧数据
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
            check_data_freshness: 是否检查数据新鲜度（防止用陈旧数据分析）
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
            
            # 将分析日期转换为字符串格式（供后续检查使用）
            analysis_date_str = analysis_dt.strftime('%Y-%m-%d')
            
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

            # 2. 检查数据新鲜度（防止分析时使用陈旧数据）
            if check_data_freshness:
                freshness_valid, freshness_msg, freshness_details = await self._check_data_freshness(
                    db, symbol6, market_type, analysis_date_str
                )
                details["data_freshness"] = freshness_details
                if not freshness_valid:
                    missing_data.append("最新行情数据")
                    logger.warning(f"⚠️ [数据新鲜度] 股票 {symbol6}: {freshness_msg}")
                    return DataValidationResult(
                        is_valid=False,
                        message=freshness_msg,
                        missing_data=missing_data,
                        details=details
                    )
                else:
                    logger.info(f"✅ [数据新鲜度] 股票 {symbol6}: {freshness_msg}")

            # 3. 检查历史数据
            if check_historical_data:
                # 计算需要检查的日期范围（确保都是字符串格式 YYYY-MM-DD）
                start_date = (analysis_dt - timedelta(days=historical_days)).strftime('%Y-%m-%d')
                end_date = analysis_date_str  # 使用已定义的 analysis_date_str

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
    
    async def _check_data_freshness(
        self,
        db,
        symbol: str,
        market_type: str,
        analysis_date: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        检查股票日行情数据的新鲜度，防止使用陈旧数据进行分析。

        规则：stock_daily_quotes（或同名集合）中该股票最新 trade_date 相对于
        分析日期（通常为今天）落后超过 2 个工作日，则认为数据陈旧。

        Returns:
            (is_valid, message, details)
        """
        try:
            # 根据市场类型选择日行情集合（优先级依次降低）
            collection_candidates = {
                "cn": ["stock_daily_quotes", "stock_daily_history", "market_quotes"],
                "hk": ["stock_daily_quotes_hk", "stock_daily_history_hk", "market_quotes_hk"],
                "us": ["stock_daily_quotes_us", "stock_daily_history_us", "market_quotes_us"],
            }
            candidates = collection_candidates.get(market_type, ["stock_daily_quotes", "market_quotes"])

            # 解析分析日期
            try:
                analysis_dt = datetime.strptime(analysis_date, '%Y-%m-%d')
            except ValueError:
                return True, "分析日期格式无法解析，跳过新鲜度检查", {"skipped": True}

            latest_dt = None
            used_collection = None

            for col_name in candidates:
                # 查询该股票最新的一条日行情记录
                doc = await db[col_name].find_one(
                    {"$or": [{"symbol": symbol}, {"code": symbol}, {"ts_code": {"$regex": f"^{symbol}"}}]},
                    {"_id": 0, "trade_date": 1, "date": 1, "updated_at": 1},
                    sort=[("trade_date", -1), ("date", -1), ("updated_at", -1)]
                )
                if not doc:
                    continue

                # 尝试从 trade_date / date 字段解析日期
                raw_date = doc.get("trade_date") or doc.get("date")
                if raw_date:
                    for fmt in ('%Y-%m-%d', '%Y%m%d', '%Y/%m/%d'):
                        try:
                            latest_dt = datetime.strptime(str(raw_date), fmt)
                            break
                        except ValueError:
                            continue

                # 如果没有 trade_date/date，退而检查 updated_at
                if latest_dt is None and doc.get("updated_at"):
                    try:
                        updated_at = doc["updated_at"]
                        if isinstance(updated_at, datetime):
                            latest_dt = updated_at.replace(tzinfo=None)
                        else:
                            latest_dt = datetime.fromisoformat(str(updated_at))
                    except Exception:
                        pass

                if latest_dt is not None:
                    used_collection = col_name
                    break

            # 如果完全没找到任何数据，视为数据缺失（返回 False）
            if latest_dt is None:
                return False, (
                    f"股票 {symbol} 在数据库中没有日行情数据，"
                    "请先完成数据同步再进行分析"
                ), {
                    "latest_trade_date": None,
                    "analysis_date": analysis_date,
                    "collections_checked": candidates
                }

            # 计算落后工作日数
            # 如果 latest_dt >= analysis_dt（历史分析），说明数据覆盖到位，直接通过
            if latest_dt.date() >= analysis_dt.date():
                return True, (
                    f"数据新鲜度正常（最新数据日期: {latest_dt.strftime('%Y-%m-%d')}）"
                ), {
                    "latest_trade_date": latest_dt.strftime('%Y-%m-%d'),
                    "analysis_date": analysis_date,
                    "collection": used_collection,
                    "days_behind": 0
                }

            # 计算 latest_dt → analysis_dt 之间的工作日数（周一到周五）
            missed_weekdays = 0
            cur = latest_dt.date()
            end = analysis_dt.date()
            while cur < end:
                cur_wd = cur.weekday()
                if cur_wd < 5:  # 0=Monday … 4=Friday
                    missed_weekdays += 1
                cur += timedelta(days=1)

            # 阈值：允许最多落后 2 个工作日（可覆盖周末 + 节假日 1 天）
            MAX_MISSED_WEEKDAYS = 2
            if missed_weekdays <= MAX_MISSED_WEEKDAYS:
                return True, (
                    f"数据新鲜度正常（最新数据日期: {latest_dt.strftime('%Y-%m-%d')}，"
                    f"落后 {missed_weekdays} 个工作日）"
                ), {
                    "latest_trade_date": latest_dt.strftime('%Y-%m-%d'),
                    "analysis_date": analysis_date,
                    "collection": used_collection,
                    "missed_weekdays": missed_weekdays
                }
            else:
                return False, (
                    f"股票 {symbol} 的行情数据已过期：数据库最新数据日期为 "
                    f"{latest_dt.strftime('%Y-%m-%d')}，"
                    f"距分析日期 {analysis_date} 落后了 {missed_weekdays} 个工作日。"
                    "请等待数据同步完成后再重新发起分析。"
                ), {
                    "latest_trade_date": latest_dt.strftime('%Y-%m-%d'),
                    "analysis_date": analysis_date,
                    "collection": used_collection,
                    "missed_weekdays": missed_weekdays,
                    "threshold": MAX_MISSED_WEEKDAYS
                }

        except Exception as e:
            # 新鲜度检查异常时，保守放行（不阻断分析），但记录错误
            logger.error(f"⚠️ 数据新鲜度检查异常: {e}", exc_info=True)
            return True, f"数据新鲜度检查异常（已跳过）: {str(e)}", {"error": str(e), "skipped": True}

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
                
                # 检查分析日期当天的数据是否存在
                # 如果分析日期当天的数据不存在，根据交易时间智能判断
                # 🔥 历史数据检查已按照集合优先级顺序（stock_daily_quotes > stock_daily_history > stock_daily_quotes）
                message = f"历史数据存在（共 {data_count} 条）"
                warning_flag = False  # 初始化警告标志
                is_in_trading_hours = False  # 标记是否在交易时间内
                
                if not analysis_date_data:
                    # 计算分析日期与最新数据日期的差距
                    if latest_date:
                        try:
                            from datetime import datetime, time as dtime
                            from zoneinfo import ZoneInfo
                            from app.core.config import settings
                            
                            latest_dt = datetime.strptime(str(latest_date), '%Y-%m-%d')
                            analysis_dt_check = datetime.strptime(analysis_date, '%Y-%m-%d')
                            days_diff = (analysis_dt_check - latest_dt).days
                            
                            # 判断分析日期是否是今天
                            tz = ZoneInfo(settings.TIMEZONE)
                            today = datetime.now(tz).date()
                            analysis_date_obj = analysis_dt_check.date()
                            is_today = (analysis_date_obj == today)
                            
                            # 🔥 如果分析日期是今天，无论days_diff是多少，都要检查交易时间
                            if is_today:
                                # 分析日期是今天，检查当前时间
                                current_time = datetime.now(tz).time()
                                market_open_time = dtime(9, 30)  # 开盘时间
                                market_close_time = dtime(16, 30)  # 收盘后缓冲期结束时间
                                
                                logger.info(f"🔍 [数据校验] 分析日期是今天，当前时间：{current_time.strftime('%H:%M:%S')}，开盘时间：09:30，收盘时间：16:30")
                                
                                # 判断当天是否是交易日（通过获取最后交易日期，使用优先级最高的数据源）
                                is_trading_day = False
                                try:
                                    from app.services.data_sources.manager import DataSourceManager
                                    manager = DataSourceManager()
                                    # 🔥 使用优先级最高的数据源获取最后交易日期
                                    latest_trade_date = manager.find_latest_trade_date_with_fallback()
                                    if latest_trade_date:
                                        latest_trade_dt = datetime.strptime(latest_trade_date, '%Y%m%d').date()
                                        is_trading_day = (latest_trade_dt == today)
                                        logger.info(f"🔍 [数据校验] 最后交易日期：{latest_trade_date} ({latest_trade_dt})，今天：{today}，是交易日：{is_trading_day}")
                                    else:
                                        logger.warning(f"⚠️ [数据校验] 无法获取最后交易日期，使用工作日判断")
                                        is_trading_day = today.weekday() < 5
                                except Exception as e:
                                    logger.warning(f"⚠️ [数据校验] 获取最后交易日期失败: {e}，使用工作日判断")
                                    # 如果获取失败，假设是交易日（工作日）
                                    is_trading_day = today.weekday() < 5
                                
                                logger.info(f"🔍 [数据校验] 是否交易日：{is_trading_day}")
                                
                                if is_trading_day:
                                    if current_time < market_open_time:
                                        # 还没到开盘时间，缺少当天数据是正常的
                                        message += f"，分析日期（{analysis_date}）是交易日但尚未开盘（当前时间：{current_time.strftime('%H:%M')}，开盘时间：09:30），缺少当天数据属正常情况"
                                        logger.info(f"ℹ️ 股票 {symbol} 分析日期 {analysis_date} 是交易日但尚未开盘，缺少当天数据属正常情况")
                                        warning_flag = False  # 开盘前不警告
                                    elif market_open_time <= current_time <= market_close_time:
                                        # 在交易时间内，尝试用实时数据补充（使用优先级最高的数据源）
                                        is_in_trading_hours = True  # 🔥 标记在交易时间内
                                        logger.info(f"🔄 股票 {symbol} 分析日期 {analysis_date} 在交易时间内（{current_time.strftime('%H:%M')}），尝试用实时数据补充（使用优先级最高的数据源）")
                                        supplemented = await self._supplement_with_realtime_data(
                                            db, symbol, analysis_date, market_type, coll_name
                                        )
                                        if supplemented:
                                            message += f"，已使用实时数据补充当天数据"
                                            analysis_date_data = True  # 标记为已补充
                                            warning_flag = False  # 已补充，不警告
                                            logger.info(f"✅ 股票 {symbol} 已使用实时数据补充当天数据，warning_flag=False")
                                        else:
                                            # 🔥 在交易时间内，即使补充失败也不应该显示警告，因为当天还没闭市
                                            message += f"，分析日期（{analysis_date}）在交易时间内，当天数据尚未生成（当前时间：{current_time.strftime('%H:%M')}），属正常情况"
                                            warning_flag = False  # 交易时间内不警告
                                            logger.info(f"ℹ️ 股票 {symbol} 分析日期 {analysis_date} 在交易时间内，当天数据尚未生成，属正常情况，warning_flag=False")
                                    else:
                                        # 已过收盘时间，应该已经有数据了
                                        message += f"，但分析日期（{analysis_date}）当天的数据不存在（最新数据日期：{latest_date}，相差 {days_diff} 天）"
                                        warning_flag = True  # 收盘后没有数据，需要警告
                                        logger.warning(f"⚠️ 股票 {symbol} 分析日期 {analysis_date} 的数据不存在，最新数据日期：{latest_date}，warning_flag=True")
                                else:
                                    # 不是交易日
                                    message += f"，分析日期（{analysis_date}）不是交易日，缺少当天数据属正常情况"
                                    warning_flag = False  # 非交易日不警告
                                    logger.info(f"ℹ️ 股票 {symbol} 分析日期 {analysis_date} 不是交易日，缺少当天数据属正常情况，warning_flag=False")
                            elif not is_today and days_diff > 0:
                                # 分析日期是未来日期或过去日期
                                message += f"，但分析日期（{analysis_date}）当天的数据不存在（最新数据日期：{latest_date}，相差 {days_diff} 天）"
                                warning_flag = True  # 未来或过去日期没有数据，需要警告
                                logger.warning(f"⚠️ 股票 {symbol} 分析日期 {analysis_date} 的数据不存在，最新数据日期：{latest_date}")
                            else:
                                # 分析日期不是今天，且days_diff <= 0
                                message += f"，但分析日期（{analysis_date}）当天的数据不存在"
                                warning_flag = True  # 没有数据，需要警告
                                logger.warning(f"⚠️ 股票 {symbol} 分析日期 {analysis_date} 的数据不存在")
                        except Exception as e:
                            logger.error(f"检查分析日期数据时出错: {e}", exc_info=True)
                            message += f"，但分析日期（{analysis_date}）当天的数据不存在"
                            warning_flag = True  # 检查出错，需要警告
                            logger.warning(f"⚠️ 股票 {symbol} 分析日期 {analysis_date} 的数据不存在")
                    else:
                        # 没有latest_date，无法判断
                        message += f"，但分析日期（{analysis_date}）当天的数据不存在"
                        warning_flag = True  # 没有数据，需要警告
                        logger.warning(f"⚠️ 股票 {symbol} 分析日期 {analysis_date} 的数据不存在")
                
                # 🔥 如果analysis_date_data为True，说明数据存在，不需要警告
                if analysis_date_data:
                    warning_flag = False
                    logger.info(f"✅ [数据校验] 分析日期数据存在，设置 warning_flag=False")
                
                # 🔥 如果在交易时间内，强制不警告（防止被其他逻辑覆盖）
                if is_in_trading_hours:
                    warning_flag = False
                    logger.info(f"✅ [数据校验] 在交易时间内，强制设置 warning_flag=False")
                
                # 🔥 最终日志：记录警告标志的最终值
                logger.info(f"📊 [数据校验] 最终 warning_flag={warning_flag}, analysis_date_data={analysis_date_data}, is_in_trading_hours={is_in_trading_hours}")
                
                return True, message, {
                    "exists": True,
                    "count": data_count,
                    "earliest_date": earliest_date,
                    "latest_date": latest_date,
                    "analysis_date_exists": analysis_date_data,
                    "date_range": f"{start_date} 至 {end_date}",
                    "warning": warning_flag  # 🔥 根据交易时间智能判断是否警告
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
    
    async def _supplement_with_realtime_data(
        self,
        db,
        symbol: str,
        analysis_date: str,
        market_type: str,
        collection_name: str
    ) -> bool:
        """
        使用实时数据补充当天的历史数据
        
        Args:
            db: 数据库连接
            symbol: 股票代码
            analysis_date: 分析日期（YYYY-MM-DD）
            market_type: 市场类型
            collection_name: 集合名称
            
        Returns:
            是否成功补充数据
        """
        try:
            # 只支持A股市场
            if market_type != "cn":
                return False
            
            # 🔥 使用数据源管理器获取完整的实时行情数据（按优先级顺序尝试）
            from app.services.data_sources.manager import DataSourceManager
            manager = DataSourceManager()
            # get_realtime_quotes_with_fallback 会按照优先级顺序尝试各个数据源
            quotes_dict, source_name = manager.get_realtime_quotes_with_fallback()
            logger.debug(f"📊 使用数据源 {source_name} 获取实时行情（优先级最高）")
            
            if not quotes_dict or symbol not in quotes_dict:
                logger.debug(f"无法获取 {symbol} 的实时行情")
                return False
            
            quote_data = quotes_dict[symbol]
            
            # 检查必要字段（至少需要close价格）
            if not quote_data or quote_data.get('close') is None:
                logger.debug(f"{symbol} 的实时行情数据缺少close价格")
                return False
            
            # 获取前收盘价（用于计算涨跌幅）
            pre_close = quote_data.get('pre_close')
            close = float(quote_data.get('close', 0))
            
            # 如果没有前收盘价，尝试从历史数据获取
            if pre_close is None:
                try:
                    latest_doc = await db[collection_name].find_one(
                        {"$or": [{"symbol": symbol}, {"code": symbol}]},
                        sort=[("trade_date", -1)]
                    )
                    if latest_doc:
                        pre_close = latest_doc.get("close")
                except Exception:
                    pass
            
            # 计算涨跌幅和涨跌额
            pct_chg = None
            change = None
            if pre_close and pre_close > 0:
                pct_chg = ((close - pre_close) / pre_close) * 100
                change = close - pre_close
            
            # 构建历史数据文档
            doc = {
                "symbol": symbol,
                "code": symbol,
                "trade_date": analysis_date,
                "open": float(quote_data.get('open', close)) if quote_data.get('open') is not None else close,
                "high": float(quote_data.get('high', close)) if quote_data.get('high') is not None else close,
                "low": float(quote_data.get('low', close)) if quote_data.get('low') is not None else close,
                "close": close,
                "volume": float(quote_data.get('volume', 0)) if quote_data.get('volume') is not None else 0,
                "amount": float(quote_data.get('amount', 0)) if quote_data.get('amount') is not None else None,
                "pre_close": float(pre_close) if pre_close is not None else None,
                "change": float(change) if change is not None else None,
                "pct_chg": float(pct_chg) if pct_chg is not None else None,
                "source": f"realtime_supplement_{source_name}",  # 标记为实时数据补充，包含数据源名称
                "supplemented_at": datetime.now().isoformat()
            }
            
            # 保存到数据库
            await db[collection_name].update_one(
                {
                    "$or": [{"symbol": symbol}, {"code": symbol}],
                    "trade_date": analysis_date
                },
                {"$set": doc},
                upsert=True
            )
            
            logger.info(f"✅ 已使用实时数据补充 {symbol} 在 {analysis_date} 的历史数据（数据源：{source_name}）")
            return True
            
        except Exception as e:
            logger.warning(f"使用实时数据补充历史数据失败: {e}", exc_info=True)
            return False
    
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
