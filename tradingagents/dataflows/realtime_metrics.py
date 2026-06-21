"""
实时估值指标计算模块
基于实时行情和财务数据计算PE/PB等指标
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def calculate_realtime_pe_pb(
    symbol: str,
    db_client=None
) -> Optional[Dict[str, Any]]:
    """
    基于实时行情和 Tushare TTM 数据计算动态 PE/PB

    计算逻辑：
    1. 从 stock_basic_info 获取 Tushare 的 pe_ttm（基于昨日收盘价）
    2. 反推 TTM 净利润 = 总市值 / pe_ttm
    3. 使用实时股价计算实时市值
    4. 计算动态 PE_TTM = 实时市值 / TTM 净利润

    Args:
        symbol: 6位股票代码
        db_client: MongoDB客户端（可选，用于同步调用）

    Returns:
        {
            "pe": 22.5,              # 动态市盈率（基于 TTM）
            "pb": 3.2,               # 动态市净率
            "pe_ttm": 23.1,          # 动态市盈率（TTM）
            "price": 11.0,           # 当前价格
            "market_cap": 110.5,     # 实时市值（亿元）
            "ttm_net_profit": 4.8,   # TTM 净利润（亿元，从 Tushare 反推）
            "updated_at": "2025-10-14T10:30:00",
            "source": "realtime_calculated",
            "is_realtime": True
        }
        如果计算失败返回 None
    """
    try:
        # 获取数据库连接（确保是同步客户端）
        if db_client is None:
            from tradingagents.config.database_manager import get_database_manager
            db_manager = get_database_manager()
            if not db_manager.is_mongodb_available():
                logger.debug("MongoDB不可用，无法计算实时PE/PB")
                return None
            db_client = db_manager.get_mongodb_client()

        # 检查是否是异步客户端（AsyncIOMotorClient）
        # 如果是异步客户端，需要转换为同步客户端
        client_type = type(db_client).__name__
        if 'AsyncIOMotorClient' in client_type or 'Motor' in client_type:
            # 这是异步客户端，创建同步客户端
            from pymongo import MongoClient
            from app.core.config import settings
            logger.debug(f"检测到异步客户端 {client_type}，转换为同步客户端")
            db_client = MongoClient(settings.MONGO_URI)

        code6 = str(symbol).zfill(6)

        logger.info(f"🔍 [实时PE计算] 开始计算股票 {code6}")

        # 🔥 关键修复：stock_basic_info 可能在不同的数据库（历史遗留问题）
        # tradingagents 模块默认用 'tradingagents'，但 CN fork 的数据同步写到 'tradingagentscn_v0_admin'
        # 需要尝试多个数据库，避免查不到数据
        db_for_basic_info = None
        for candidate_db in ['tradingagentscn_v0_admin', 'tradingagents']:
            test_db = db_client[candidate_db]
            if 'stock_basic_info' in test_db.list_collection_names():
                if test_db.stock_basic_info.find_one({"code": code6}):
                    db_for_basic_info = test_db
                    logger.info(f"✅ [数据库选择] stock_basic_info 在 {candidate_db}")
                    break
        if db_for_basic_info is None:
            db_for_basic_info = db_client['tradingagents']
            logger.warning(f"⚠️ [数据库选择] 所有候选库都未找到 {code6} 的 stock_basic_info，使用默认 tradingagents")

        # 1. 获取实时行情（market_quotes）- 同样尝试多个库
        quote = None
        for candidate_db in ['tradingagentscn_v0_admin', 'tradingagents']:
            test_db = db_client[candidate_db]
            if 'market_quotes' in test_db.list_collection_names():
                quote = test_db.market_quotes.find_one({"code": code6})
                if quote:
                    break
        if not quote:
            logger.warning(f"⚠️ [实时PE计算-失败] 未找到股票 {code6} 的实时行情数据")
            return None

        realtime_price = quote.get("close")
        pre_close = quote.get("pre_close")  # 昨日收盘价
        quote_updated_at = quote.get("updated_at", "N/A")

        if not realtime_price or realtime_price <= 0:
            logger.warning(f"⚠️ [实时PE计算-失败] 股票 {code6} 的实时价格无效: {realtime_price}")
            return None

        logger.info(f"   ✓ 实时股价: {realtime_price}元 (更新时间: {quote_updated_at})")
        logger.info(f"   ✓ 昨日收盘价: {pre_close}元")

        # 2. 获取基础信息（stock_basic_info）- 获取 Tushare 的 pe_ttm 和市值数据
        # 🔥 优先查询 Tushare 数据源（因为只有 Tushare 有 pe_ttm、total_mv、total_share 等字段）
        logger.info(f"🔍 [MongoDB查询] 查询条件: code={code6}, source=tushare")
        basic_info = db_for_basic_info.stock_basic_info.find_one({"code": code6, "source": "tushare"})

        if not basic_info:
            # 🔥 诊断：查看 MongoDB 中有哪些数据源
            all_sources = list(db_for_basic_info.stock_basic_info.find({"code": code6}, {"source": 1, "_id": 0}))
            logger.warning(f"⚠️ [动态PE计算] 未找到 Tushare 数据")
            logger.warning(f"   MongoDB 中该股票的数据源: {[s.get('source') for s in all_sources]}")

            # 如果没有 Tushare 数据，尝试查询其他数据源
            basic_info = db_for_basic_info.stock_basic_info.find_one({"code": code6})
            if not basic_info:
                logger.warning(f"⚠️ [动态PE计算-失败] 未找到股票 {code6} 的基础信息")
                logger.warning(f"   建议: 运行 Tushare 数据同步任务，确保 stock_basic_info 集合有 Tushare 数据")
                return None
            else:
                logger.warning(f"⚠️ [动态PE计算] 使用其他数据源: {basic_info.get('source', 'unknown')}")
                # 如果不是 Tushare 数据，可能缺少关键字段，直接返回 None
                if basic_info.get('source') != 'tushare':
                    logger.warning(f"⚠️ [动态PE计算-失败] 数据源 {basic_info.get('source')} 不包含 pe_ttm 等字段")
                    logger.warning(f"   可用字段: {list(basic_info.keys())}")
                    return None

        # 获取 Tushare 的 pe_ttm（基于昨日收盘价）
        pe_ttm_tushare = basic_info.get("pe_ttm")
        pe_tushare = basic_info.get("pe")
        pb_tushare = basic_info.get("pb")
        total_mv_yi = basic_info.get("total_mv")  # 总市值（亿元）
        total_share = basic_info.get("total_share")  # 总股本（万股）
        basic_info_updated_at = basic_info.get("updated_at")  # 更新时间

        logger.info(f"   ✓ Tushare PE_TTM: {pe_ttm_tushare}倍")
        logger.info(f"   ✓ Tushare PE: {pe_tushare}倍")
        logger.info(f"   ✓ Tushare 总市值: {total_mv_yi}亿元")
        logger.info(f"   ✓ 总股本: {total_share}万股")
        logger.info(f"   ✓ stock_basic_info 更新时间: {basic_info_updated_at}")

        # 🔥 3. 判断是否需要重新计算市值
        # 如果 stock_basic_info 的更新时间在今天收盘后（15:00之后），说明数据已经是最新的
        from datetime import datetime, time as dtime
        from zoneinfo import ZoneInfo

        need_recalculate = True
        if basic_info_updated_at:
            # 确保时间带有时区信息
            if isinstance(basic_info_updated_at, datetime):
                if basic_info_updated_at.tzinfo is None:
                    basic_info_updated_at = basic_info_updated_at.replace(tzinfo=ZoneInfo("Asia/Shanghai"))

                # 获取今天的日期
                today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
                update_date = basic_info_updated_at.date()
                update_time = basic_info_updated_at.time()

                # 如果更新日期是今天，且更新时间在15:00之后，说明数据已经是今天收盘后的最新数据
                if update_date == today and update_time >= dtime(15, 0):
                    need_recalculate = False
                    logger.info(f"   💡 stock_basic_info 已在今天收盘后更新，直接使用其数据")

        if not need_recalculate:
            # 直接使用 stock_basic_info 的数据，不需要重新计算
            logger.info(f"   ✓ 使用 stock_basic_info 的最新数据（无需重新计算）")

            result = {
                "pe": round(pe_tushare, 2) if pe_tushare else None,
                "pb": round(pb_tushare, 2) if pb_tushare else None,
                "pe_ttm": round(pe_ttm_tushare, 2) if pe_ttm_tushare else None,
                "price": round(realtime_price, 2),
                "market_cap": round(total_mv_yi, 2) if total_mv_yi else None,
                "updated_at": quote.get("updated_at"),
                "source": "stock_basic_info_latest",
                "is_realtime": False,
                "note": "使用stock_basic_info收盘后最新数据",
            }

            logger.info(f"✅ [动态PE计算-成功] 股票 {code6}: PE_TTM={result['pe_ttm']}倍, PB={result['pb']}倍 (来自stock_basic_info)")
            return result

        # 4. 🔥 计算总股本（需要判断 stock_basic_info 的市值是昨天的还是今天的）
        total_shares_wan = None
        yesterday_mv_yi = None

        # 方案1：优先使用 stock_basic_info 中的 total_share（如果有）
        if total_share and total_share > 0:
            total_shares_wan = total_share
            logger.info(f"   ✓ 使用 stock_basic_info.total_share: {total_shares_wan:.2f}万股")

            # 计算昨日市值 = 总股本 × 昨日收盘价
            if pre_close and pre_close > 0:
                yesterday_mv_yi = (total_shares_wan * pre_close) / 10000
                logger.info(f"   ✓ 昨日市值: {total_shares_wan:.2f}万股 × {pre_close:.2f}元 / 10000 = {yesterday_mv_yi:.2f}亿元")
            elif total_mv_yi and total_mv_yi > 0:
                # 如果没有昨日收盘价，使用 stock_basic_info 的市值（假设是昨天的）
                yesterday_mv_yi = total_mv_yi
                logger.info(f"   ⚠️ market_quotes 中无 pre_close，使用 stock_basic_info 市值作为昨日市值: {yesterday_mv_yi:.2f}亿元")
            else:
                # 既没有 pre_close，也没有 total_mv_yi，无法计算
                logger.warning(f"⚠️ [动态PE计算-失败] 无法获取昨日市值: pre_close={pre_close}, total_mv={total_mv_yi}")
                return None

        # 方案2：使用 market_quotes 的 pre_close（昨日收盘价）反推股本
        elif pre_close and pre_close > 0 and total_mv_yi and total_mv_yi > 0:
            # 🔥 关键：判断 total_mv_yi 是昨天的还是今天的
            # 如果 stock_basic_info 更新时间在今天收盘前，说明 total_mv_yi 是昨天的市值
            # 如果更新时间在今天收盘后，说明 total_mv_yi 是今天的市值，需要用 realtime_price 反推

            # 判断 stock_basic_info 是否是昨天的数据
            is_yesterday_data = True
            if basic_info_updated_at and isinstance(basic_info_updated_at, datetime):
                if basic_info_updated_at.tzinfo is None:
                    basic_info_updated_at = basic_info_updated_at.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
                update_date = basic_info_updated_at.date()
                update_time = basic_info_updated_at.time()
                # 如果更新日期是今天，且更新时间在15:00之后，说明是今天的数据
                if update_date == today and update_time >= dtime(15, 0):
                    is_yesterday_data = False

            if is_yesterday_data:
                # total_mv_yi 是昨天的市值，用 pre_close 反推股本
                total_shares_wan = (total_mv_yi * 10000) / pre_close
                yesterday_mv_yi = total_mv_yi
                logger.info(f"   ✓ stock_basic_info 是昨天的数据，用 pre_close 反推总股本: {total_mv_yi:.2f}亿元 / {pre_close:.2f}元 = {total_shares_wan:.2f}万股")
            else:
                # total_mv_yi 是今天的市值，用 realtime_price 反推股本
                total_shares_wan = (total_mv_yi * 10000) / realtime_price
                yesterday_mv_yi = (total_shares_wan * pre_close) / 10000
                logger.info(f"   ✓ stock_basic_info 是今天的数据，用 realtime_price 反推总股本: {total_mv_yi:.2f}亿元 / {realtime_price:.2f}元 = {total_shares_wan:.2f}万股")
                logger.info(f"   ✓ 昨日市值: {total_shares_wan:.2f}万股 × {pre_close:.2f}元 / 10000 = {yesterday_mv_yi:.2f}亿元")

        # 方案3：只有 total_mv_yi，没有 pre_close（market_quotes 数据不完整）
        elif total_mv_yi and total_mv_yi > 0:
            # 使用 realtime_price 反推股本，假设 total_mv_yi 是昨天的市值
            total_shares_wan = (total_mv_yi * 10000) / realtime_price
            yesterday_mv_yi = total_mv_yi
            logger.warning(f"   ⚠️ market_quotes 中无 pre_close，假设 stock_basic_info.total_mv 是昨日市值")
            logger.info(f"   ✓ 用 realtime_price 反推总股本: {total_mv_yi:.2f}亿元 / {realtime_price:.2f}元 = {total_shares_wan:.2f}万股")
            logger.info(f"   ✓ 昨日市值（假设）: {yesterday_mv_yi:.2f}亿元")

        # 方案4：如果都没有，无法计算
        else:
            logger.warning(f"⚠️ [动态PE计算-失败] 无法获取总股本数据")
            logger.warning(f"   - total_share: {total_share}")
            logger.warning(f"   - pre_close: {pre_close}")
            logger.warning(f"   - total_mv: {total_mv_yi}")
            return None

        # 5. 从 Tushare pe_ttm 反推 TTM 净利润（使用昨日市值）

        if not pe_ttm_tushare or pe_ttm_tushare <= 0 or not yesterday_mv_yi or yesterday_mv_yi <= 0:
            logger.warning(f"⚠️ [动态PE计算-失败] 无法反推TTM净利润: pe_ttm={pe_ttm_tushare}, yesterday_mv={yesterday_mv_yi}")
            logger.warning(f"   💡 提示: 可能是亏损股票（PE为负或空）")
            return None

        # 反推 TTM 净利润（亿元）= 昨日市值 / PE_TTM
        ttm_net_profit_yi = yesterday_mv_yi / pe_ttm_tushare
        logger.info(f"   ✓ 反推 TTM净利润: {yesterday_mv_yi:.2f}亿元 / {pe_ttm_tushare:.2f}倍 = {ttm_net_profit_yi:.2f}亿元")

        # 6. 计算实时市值（亿元）= 总股本（万股）× 实时股价（元）/ 10000
        realtime_mv_yi = (realtime_price * total_shares_wan) / 10000
        logger.info(f"   ✓ 实时市值: {realtime_price:.2f}元 × {total_shares_wan:.2f}万股 / 10000 = {realtime_mv_yi:.2f}亿元")

        # 7. 计算动态 PE_TTM = 实时市值 / TTM净利润
        dynamic_pe_ttm = realtime_mv_yi / ttm_net_profit_yi
        logger.info(f"   ✓ 动态PE_TTM计算: {realtime_mv_yi:.2f}亿元 / {ttm_net_profit_yi:.2f}亿元 = {dynamic_pe_ttm:.2f}倍")

        # 8. 获取财务数据（用于计算 PB）- 同样尝试多个库
        financial_data = None
        for candidate_db in ['tradingagentscn_v0_admin', 'tradingagents']:
            test_db = db_client[candidate_db]
            if 'stock_financial_data' in test_db.list_collection_names():
                financial_data = test_db.stock_financial_data.find_one({"code": code6}, sort=[("report_period", -1)])
                if financial_data:
                    break
        pb = None
        total_equity_yi = None

        if financial_data:
            total_equity = financial_data.get("total_equity")  # 净资产（元）
            if total_equity and total_equity > 0:
                total_equity_yi = total_equity / 100000000  # 转换为亿元
                pb = realtime_mv_yi / total_equity_yi
                logger.info(f"   ✓ 动态PB计算: {realtime_mv_yi:.2f}亿元 / {total_equity_yi:.2f}亿元 = {pb:.2f}倍")
            else:
                logger.warning(f"   ⚠️ PB计算失败: 净资产无效 ({total_equity})")
        else:
            logger.warning(f"   ⚠️ 未找到财务数据，无法计算PB")
            # 使用 Tushare 的 PB 作为降级
            if pb_tushare:
                pb = pb_tushare
                logger.info(f"   ✓ 使用 Tushare PB: {pb}倍")

        # 9. 构建返回结果
        result = {
            "pe": round(dynamic_pe_ttm, 2),  # 动态PE（基于TTM）
            "pb": round(pb, 2) if pb else None,
            "pe_ttm": round(dynamic_pe_ttm, 2),  # 动态PE_TTM
            "price": round(realtime_price, 2),
            "market_cap": round(realtime_mv_yi, 2),  # 实时市值（亿元）
            "ttm_net_profit": round(ttm_net_profit_yi, 2),  # TTM净利润（亿元）
            "updated_at": quote.get("updated_at"),
            "source": "realtime_calculated_from_market_quotes",
            "is_realtime": True,
            "note": "基于market_quotes实时股价和pre_close计算",
            "total_shares": round(total_shares_wan, 2),  # 总股本（万股）
            "yesterday_close": round(pre_close, 2) if pre_close else None,  # 昨日收盘价（参考）
            "tushare_pe_ttm": round(pe_ttm_tushare, 2),  # Tushare PE_TTM（参考）
            "tushare_pe": round(pe_tushare, 2) if pe_tushare else None,  # Tushare PE（参考）
        }

        logger.info(f"✅ [动态PE计算-成功] 股票 {code6}: 动态PE_TTM={result['pe_ttm']}倍, PB={result['pb']}倍")
        return result
        
    except Exception as e:
        logger.error(f"计算股票 {symbol} 的实时PE/PB失败: {e}", exc_info=True)
        return None


def validate_pe_pb(pe: Optional[float], pb: Optional[float]) -> bool:
    """
    验证PE/PB是否在合理范围内
    
    Args:
        pe: 市盈率
        pb: 市净率
    
    Returns:
        bool: 是否合理
    """
    # PE合理范围：-100 到 1000（允许负值，因为亏损企业PE为负）
    if pe is not None and (pe < -100 or pe > 1000):
        logger.warning(f"PE异常: {pe}")
        return False
    
    # PB合理范围：0.1 到 100
    if pb is not None and (pb < 0.1 or pb > 100):
        logger.warning(f"PB异常: {pb}")
        return False
    
    return True


def get_pe_pb_with_fallback(
    symbol: str,
    db_client=None
) -> Dict[str, Any]:
    """
    获取PE/PB，智能降级策略

    策略：
    1. 优先使用动态 PE（基于实时股价 + Tushare TTM 净利润）
    2. 如果动态计算失败，降级到 Tushare 静态 PE（基于昨日收盘价）

    优势：
    - 动态 PE 能反映实时股价变化
    - 使用 Tushare 官方 TTM 净利润（反推），避免单季度数据错误
    - 计算准确，日志详细

    Args:
        symbol: 6位股票代码
        db_client: MongoDB客户端（可选）

    Returns:
        {
            "pe": 22.5,              # 市盈率
            "pb": 3.2,               # 市净率
            "pe_ttm": 23.1,          # 市盈率（TTM）
            "pb_mrq": 3.3,           # 市净率（MRQ）
            "source": "realtime_calculated_from_tushare_ttm" | "daily_basic",
            "is_realtime": True | False,
            "updated_at": "2025-10-14T10:30:00",
            "ttm_net_profit": 4.8    # TTM净利润（亿元，仅动态计算时有）
        }
    """
    logger.info(f"🔄 [PE智能策略] 开始获取股票 {symbol} 的PE/PB")

    # 准备数据库连接
    try:
        if db_client is None:
            from tradingagents.config.database_manager import get_database_manager
            db_manager = get_database_manager()
            if not db_manager.is_mongodb_available():
                logger.error("❌ [PE智能策略-失败] MongoDB不可用")
                return {}
            db_client = db_manager.get_mongodb_client()

        # 检查是否是异步客户端
        client_type = type(db_client).__name__
        if 'AsyncIOMotorClient' in client_type or 'Motor' in client_type:
            from pymongo import MongoClient
            from app.core.config import settings
            logger.debug(f"检测到异步客户端 {client_type}，转换为同步客户端")
            db_client = MongoClient(settings.MONGO_URI)

    except Exception as e:
        logger.error(f"❌ [PE智能策略-失败] 数据库连接失败: {e}")
        return {}

    # 1. 优先使用动态 PE 计算（基于实时股价 + Tushare TTM）
    logger.info("   → 尝试方案1: 动态PE计算 (实时股价 + Tushare TTM净利润)")
    logger.info("   💡 说明: 使用实时股价和Tushare官方TTM净利润，准确反映当前估值")

    realtime_metrics = calculate_realtime_pe_pb(symbol, db_client)
    if realtime_metrics:
        # 验证数据合理性
        pe = realtime_metrics.get('pe')
        pb = realtime_metrics.get('pb')
        if validate_pe_pb(pe, pb):
            logger.info(f"✅ [PE智能策略-成功] 使用动态PE: PE={pe}, PB={pb}")
            logger.info(f"   └─ 数据来源: {realtime_metrics.get('source')}")
            logger.info(f"   └─ TTM净利润: {realtime_metrics.get('ttm_net_profit')}亿元 (从Tushare反推)")
            return realtime_metrics
        else:
            logger.warning(f"⚠️ [PE智能策略-方案1异常] 动态PE/PB超出合理范围 (PE={pe}, PB={pb})")

    # 2. 降级到 Tushare 静态 PE（基于昨日收盘价）
    logger.info("   → 尝试方案2: Tushare静态PE (基于昨日收盘价)")
    logger.info("   💡 说明: 使用Tushare官方PE_TTM，基于昨日收盘价")

    try:
        code6 = str(symbol).zfill(6)

        # 🔥 同样尝试多个数据库
        db_for_basic_info = None
        for candidate_db in ['tradingagentscn_v0_admin', 'tradingagents']:
            test_db = db_client[candidate_db]
            if 'stock_basic_info' in test_db.list_collection_names():
                if test_db.stock_basic_info.find_one({"code": code6}):
                    db_for_basic_info = test_db
                    break
        if db_for_basic_info is None:
            db_for_basic_info = db_client['tradingagents']

        # 🔥 优先查询 Tushare 数据源
        basic_info = db_for_basic_info.stock_basic_info.find_one({"code": code6, "source": "tushare"})
        if not basic_info:
            # 如果没有 Tushare 数据，尝试查询其他数据源
            basic_info = db_for_basic_info.stock_basic_info.find_one({"code": code6})

        if basic_info:
            pe_static = basic_info.get("pe")
            pb_static = basic_info.get("pb")
            pe_ttm = basic_info.get("pe_ttm")
            pb_mrq = basic_info.get("pb_mrq")
            updated_at = basic_info.get("updated_at", "N/A")

            if pe_ttm or pe_static or pb_static:
                logger.info(f"✅ [PE智能策略-成功] 使用Tushare静态PE: PE={pe_static}, PE_TTM={pe_ttm}, PB={pb_static}")
                logger.info(f"   └─ 数据来源: stock_basic_info (更新时间: {updated_at})")

                return {
                    "pe": pe_static,
                    "pb": pb_static,
                    "pe_ttm": pe_ttm,
                    "pb_mrq": pb_mrq,
                    "source": "daily_basic",
                    "is_realtime": False,
                    "updated_at": updated_at,
                    "note": "使用Tushare最近一个交易日的数据（基于TTM）"
                }

        logger.warning("⚠️ [PE智能策略-方案2失败] Tushare静态数据不可用")

    except Exception as e:
        logger.warning(f"⚠️ [PE智能策略-方案2异常] {e}")

    logger.error(f"❌ [PE智能策略-全部失败] 无法获取股票 {symbol} 的PE/PB")
    return {}

