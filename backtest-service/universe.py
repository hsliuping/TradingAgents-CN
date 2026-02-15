"""
股票池解析
支持 DSL 格式 (universe 在顶层) 和 config 格式 (universe 或 symbols)
支持动态获取：
1. 指数历史成分股（避免生存者偏差）
2. 行业分类 + 历史市值排序（动态龙头选股）
"""
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Tushare 配置
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# 行业分类映射（用户友好名称 -> Tushare industry 字段值）
INDUSTRY_MAPPING = {
    # 消费类
    "白酒": ["白酒", "酿酒行业"],
    "食品": ["食品饮料", "乳品", "食品加工"],
    "家电": ["家用电器", "白色家电", "小家电"],
    "消费": ["白酒", "酿酒行业", "食品饮料", "乳品", "家用电器", "白色家电", "零售"],
    # 金融类
    "银行": ["银行"],
    "保险": ["保险"],
    "券商": ["证券"],
    "金融": ["银行", "保险", "证券", "多元金融"],
    # 科技类
    "半导体": ["半导体", "电子元件"],
    "软件": ["软件服务", "互联网", "计算机应用"],
    "通信": ["通信设备", "通信服务"],
    "科技": ["半导体", "电子元件", "软件服务", "互联网", "通信设备"],
    # 新能源
    "光伏": ["光伏设备", "电气设备"],
    "锂电": ["电池", "锂电池"],
    "新能源": ["光伏设备", "电气设备", "电池", "新能源汽车"],
    "新能源车": ["新能源汽车", "汽车整车"],
    # 医药
    "医药": ["化学制药", "中药", "生物制品", "医疗器械", "医疗服务"],
    # 其他
    "房地产": ["房地产开发", "房地产服务"],
    "建材": ["水泥建材", "建筑材料"],
    "钢铁": ["钢铁"],
    "化工": ["化工原料", "化学制品"],
}


def _get_tushare_api():
    """获取 Tushare API 实例"""
    if not TUSHARE_TOKEN:
        logger.warning("[universe] TUSHARE_TOKEN 未配置")
        return None
    try:
        import tushare as ts
        ts.set_token(TUSHARE_TOKEN)
        return ts.pro_api()
    except Exception as e:
        logger.error(f"[universe] Tushare 初始化失败: {e}")
        return None


def _get_index_constituents(
    index_code: str,
    trade_date: Optional[str] = None,
    max_symbols: int = 30
) -> List[str]:
    """
    获取指数成分股（支持历史日期）

    Args:
        index_code: 指数代码，如 000932.SH（中证消费）
        trade_date: 交易日期 YYYYMMDD，None 则获取最新
        max_symbols: 最大返回数量（按权重排序取前N只）
    """
    pro = _get_tushare_api()
    if not pro:
        return []

    try:
        params = {"index_code": index_code}
        if trade_date:
            params["trade_date"] = trade_date

        df = pro.index_weight(**params)

        if df is None or df.empty:
            logger.warning(f"[universe] 指数 {index_code} 成分股为空 (trade_date={trade_date})")
            return []

        df = df.sort_values("weight", ascending=False)
        if len(df) > max_symbols:
            df = df.head(max_symbols)

        symbols = []
        for code in df["con_code"].unique():
            clean_code = code.split(".")[0] if "." in code else code
            symbols.append(clean_code)

        logger.info(f"[universe] 指数 {index_code} 成分股: {len(symbols)} 只 (date={trade_date})")
        return symbols

    except Exception as e:
        logger.error(f"[universe] 获取指数成分股失败: {e}")
        return []


def _get_industry_leaders_by_market_cap(
    industry: str,
    trade_date: Optional[str] = None,
    max_symbols: int = 15
) -> List[str]:
    """
    获取指定行业的市值龙头股（支持历史日期）

    这是解决生存者偏差的核心方法：
    1. 获取该行业的所有股票（基于 stock_basic 的 industry 字段）
    2. 获取指定日期的市值数据（daily_basic 的 total_mv）
    3. 按市值排序，取前N只

    Args:
        industry: 行业名称（如 "白酒"、"消费"、"金融"）
        trade_date: 交易日期 YYYYMMDD，用于获取当时的市值排名
        max_symbols: 返回数量

    Returns:
        股票代码列表（6位纯数字）
    """
    pro = _get_tushare_api()
    if not pro:
        return []

    try:
        # 1. 解析行业关键词
        industry_keywords = INDUSTRY_MAPPING.get(industry, [industry])
        logger.info(f"[universe] 行业 '{industry}' 映射到: {industry_keywords}")

        # 2. 获取所有 A 股基础信息
        stock_df = pro.stock_basic(
            list_status='L',  # 上市中
            fields='ts_code,name,industry,list_date'
        )

        if stock_df is None or stock_df.empty:
            logger.warning("[universe] 无法获取股票基础信息")
            return []

        # 3. 筛选指定行业的股票
        # 使用 isin 匹配多个行业关键词
        industry_stocks = stock_df[stock_df['industry'].isin(industry_keywords)]

        if industry_stocks.empty:
            # 尝试模糊匹配
            mask = stock_df['industry'].str.contains('|'.join(industry_keywords), na=False)
            industry_stocks = stock_df[mask]

        if industry_stocks.empty:
            logger.warning(f"[universe] 行业 '{industry}' 未找到股票")
            return []

        logger.info(f"[universe] 行业 '{industry}' 找到 {len(industry_stocks)} 只股票")

        # 4. 如果指定了日期，过滤掉当时还未上市的股票
        if trade_date:
            # list_date 格式是 YYYYMMDD
            industry_stocks = industry_stocks[
                industry_stocks['list_date'].fillna('99999999') <= trade_date
            ]
            logger.info(f"[universe] 过滤后（{trade_date}前上市）: {len(industry_stocks)} 只")

        if industry_stocks.empty:
            logger.warning(f"[universe] {trade_date} 时该行业无上市股票")
            return []

        # 5. 获取市值数据
        ts_codes = industry_stocks['ts_code'].tolist()

        # daily_basic 需要指定 trade_date
        if trade_date:
            mv_df = pro.daily_basic(
                trade_date=trade_date,
                fields='ts_code,total_mv,circ_mv'
            )
        else:
            # 获取最近交易日的数据
            import datetime
            today = datetime.date.today().strftime('%Y%m%d')
            mv_df = pro.daily_basic(
                trade_date=today,
                fields='ts_code,total_mv,circ_mv'
            )

        if mv_df is None or mv_df.empty:
            logger.warning(f"[universe] 无法获取 {trade_date} 的市值数据")
            # 回退：不按市值排序，随机取
            symbols = [c.split('.')[0] for c in ts_codes[:max_symbols]]
            return symbols

        # 6. 合并并按市值排序
        merged = industry_stocks.merge(mv_df, on='ts_code', how='left')
        merged = merged.dropna(subset=['total_mv'])  # 去掉没有市值数据的
        merged = merged.sort_values('total_mv', ascending=False)

        # 7. 取前 N 只
        top_stocks = merged.head(max_symbols)
        symbols = [c.split('.')[0] for c in top_stocks['ts_code'].tolist()]

        logger.info(
            f"[universe] 行业 '{industry}' 市值龙头 (date={trade_date}): "
            f"{len(symbols)} 只 - {symbols[:5]}..."
        )

        return symbols

    except Exception as e:
        logger.error(f"[universe] 获取行业龙头失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_universe_symbols(
    dsl_or_config: Dict[str, Any],
    backtest_start_date: Optional[str] = None
) -> List[str]:
    """
    从 DSL 或 config 解析股票池

    Args:
        dsl_or_config: DSL 或 config 字典
        backtest_start_date: 回测开始日期 (YYYY-MM-DD)，用于获取历史成分股/市值

    支持格式:
    1. static: {"universe": {"type": "static", "symbols": ["600519", ...]}}
       - 静态股票池，直接使用指定股票

    2. index: {"universe": {"type": "index", "index_code": "000932.SH"}}
       - 使用指数成分股（支持历史日期）

    3. industry: {"universe": {"type": "industry", "industry": "白酒", "max_symbols": 10}}
       - 🆕 动态行业龙头：按回测开始日期的市值排序选股
       - 避免生存者偏差：选的是当时的龙头，而非现在的龙头
       - 支持的行业：白酒、消费、金融、银行、科技、新能源、医药等

    重要：type=index/industry 时会获取回测开始日期的数据，避免生存者偏差
    """
    # 顶层 symbols（config 格式）
    symbols = dsl_or_config.get("symbols")
    if symbols:
        return symbols

    uni = dsl_or_config.get("universe") or {}
    if not isinstance(uni, dict):
        return []

    t = uni.get("type", "static")

    # 转换日期格式
    trade_date = None
    if backtest_start_date:
        trade_date = backtest_start_date.replace("-", "")

    # ========== type: static ==========
    if t == "static":
        return uni.get("symbols", []) or []

    # ========== type: index ==========
    if t == "index":
        prefilled = uni.get("symbols", [])
        if prefilled:
            return prefilled

        index_code = uni.get("index_code", "")
        if not index_code:
            logger.warning("[universe] type=index 但未指定 index_code")
            return []

        max_symbols = uni.get("max_symbols", 30)
        return _get_index_constituents(index_code, trade_date, max_symbols)

    # ========== type: industry（新增：按市值动态选龙头）==========
    if t == "industry":
        prefilled = uni.get("symbols", [])
        if prefilled:
            return prefilled

        industry = uni.get("industry", "")
        if not industry:
            logger.warning("[universe] type=industry 但未指定 industry")
            return []

        max_symbols = uni.get("max_symbols", 15)
        return _get_industry_leaders_by_market_cap(industry, trade_date, max_symbols)

    # 其他类型暂不支持
    logger.warning(f"[universe] 不支持的 universe.type: {t}")
    return []
