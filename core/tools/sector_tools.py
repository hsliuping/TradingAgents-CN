"""
板块分析工具函数

提供板块表现分析、轮动识别、同业对比等功能
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ============================================================
# MongoDB 缓存配置 — 板块列表 & 成分股（TTL=30天）
# ============================================================

SECTOR_CACHE_COLLECTION = "ths_sector_cache"
SECTOR_CACHE_TTL_DAYS = 30

_sector_cache_db = None   # 延迟初始化


def _get_sector_cache_db():
    """获取同步 MongoDB 连接（用于缓存读写）"""
    global _sector_cache_db
    if _sector_cache_db is not None:
        return _sector_cache_db
    try:
        from app.core.database import get_mongo_db_sync
        _sector_cache_db = get_mongo_db_sync()
        return _sector_cache_db
    except Exception:
        return None


def _read_sector_cache(cache_key: str) -> Optional[pd.DataFrame]:
    """从 MongoDB 读取板块缓存，过期返回 None"""
    db = _get_sector_cache_db()
    if db is None:
        return None
    try:
        doc = db[SECTOR_CACHE_COLLECTION].find_one(
            {"cache_key": cache_key, "expires_at": {"$gt": datetime.now(timezone.utc)}}
        )
        if doc and doc.get("data"):
            df = pd.DataFrame(doc["data"])
            logger.debug(f"📦 板块缓存命中: {cache_key} ({len(df)} 条)")
            return df
    except Exception as e:
        logger.debug(f"读取板块缓存失败: {e}")
    return None


def _write_sector_cache(cache_key: str, cache_type: str, df: pd.DataFrame):
    """写入板块缓存到 MongoDB（upsert）"""
    db = _get_sector_cache_db()
    if db is None:
        return
    try:
        now = datetime.now(timezone.utc)
        db[SECTOR_CACHE_COLLECTION].update_one(
            {"cache_key": cache_key},
            {"$set": {
                "cache_type": cache_type,
                "data": df.to_dict("records"),
                "count": len(df),
                "updated_at": now,
                "expires_at": now + timedelta(days=SECTOR_CACHE_TTL_DAYS),
            }},
            upsert=True,
        )
        logger.info(f"✅ 板块缓存已更新: {cache_key} ({len(df)} 条, TTL={SECTOR_CACHE_TTL_DAYS}天)")
    except Exception as e:
        logger.debug(f"写入板块缓存失败: {e}")


async def _get_ths_index_list_cached(provider, index_type: str) -> Optional[pd.DataFrame]:
    """带 MongoDB 缓存的板块列表获取（缓存30天）"""
    cache_key = f"sector_list_{index_type}"

    # 1. 读缓存
    cached = _read_sector_cache(cache_key)
    if cached is not None:
        return cached

    # 2. 调 Tushare API
    df = await provider.get_ths_index_list(index_type=index_type)
    if df is not None and not df.empty:
        _write_sector_cache(cache_key, "sector_list", df)
    return df


async def _get_ths_member_cached(provider, ts_code: str) -> Optional[pd.DataFrame]:
    """带 MongoDB 缓存的板块成分股获取（正向：板块→成分股，缓存30天）"""
    cache_key = f"sector_member_{ts_code}"

    # 1. 读缓存
    cached = _read_sector_cache(cache_key)
    if cached is not None:
        return cached

    # 2. 调 Tushare API
    df = await provider.get_ths_member(ts_code=ts_code)
    if df is not None and not df.empty:
        _write_sector_cache(cache_key, "sector_member", df)
    return df


async def _get_ths_member_reverse_cached(provider, con_code: str) -> Optional[pd.DataFrame]:
    """带 MongoDB 缓存的个股所属板块获取（反向：个股→所属板块，缓存30天）"""
    cache_key = f"stock_sectors_{con_code}"

    # 1. 读缓存
    cached = _read_sector_cache(cache_key)
    if cached is not None:
        return cached

    # 2. 调 Tushare API
    df = await provider.get_ths_member(con_code=con_code)
    if df is not None and not df.empty:
        _write_sector_cache(cache_key, "stock_sectors", df)
    return df


def _get_tushare_provider():
    """延迟导入获取 Tushare Provider"""
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    return get_tushare_provider()


def _clean_date_string(date_str: str) -> str:
    """清理日期字符串，去掉可能的时间部分"""
    if not date_str:
        return date_str
    return date_str.split()[0] if ' ' in date_str else date_str


async def _get_latest_trade_date(trade_date: str) -> str:
    """
    获取最新可用的交易日期

    一次性获取最近8天的数据，取最后一条有效交易日

    Args:
        trade_date: 原始交易日期 (YYYY-MM-DD 或 YYYYMMDD)

    Returns:
        最新可用的交易日期 (YYYYMMDD格式)
    """
    provider = _get_tushare_provider()
    # 清理日期字符串，去掉可能的时间部分
    trade_date_clean = _clean_date_string(trade_date).replace('-', '')

    try:
        # 计算8天前的日期
        end_date = datetime.strptime(trade_date_clean, '%Y%m%d')
        start_date = end_date - timedelta(days=8)
        start_date_str = start_date.strftime('%Y%m%d')

        # 一次性获取最近8天的上证指数数据
        df = await provider.get_index_daily(
            ts_code='000001.SH',
            start_date=start_date_str,
            end_date=trade_date_clean,
            use_cache=False  # 不使用缓存，确保获取最新数据
        )

        if df is not None and not df.empty:
            # 按日期排序，取最后一条（最新的交易日）
            df = df.sort_values('trade_date', ascending=False)
            latest_trade_date = str(df.iloc[0]['trade_date'])

            if latest_trade_date != trade_date_clean:
                logger.info(f"📅 {trade_date} 无数据，使用最近交易日 {latest_trade_date}")

            return latest_trade_date

        # 如果都没有找到，返回原始日期
        logger.warning(f"⚠️ 无法找到有效交易日，使用原始日期 {trade_date_clean}")
        return trade_date_clean

    except Exception as e:
        logger.error(f"❌ 获取最新交易日失败: {e}")
        return trade_date_clean


async def get_stock_sector_info(ticker: str) -> Dict[str, Any]:
    """
    获取股票所属的板块信息
    
    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
    
    Returns:
        包含行业和所属板块列表的字典
    """
    provider = _get_tushare_provider()
    
    result = {
        "ticker": ticker,
        "industry": None,
        "sectors": [],
        "error": None
    }
    
    try:
        # 1. 获取行业分类
        industry = await provider.get_stock_industry(ticker)
        result["industry"] = industry
        
        # 2. 获取所属板块（同花顺概念/行业板块）— 带缓存
        ts_code = provider._normalize_ts_code(ticker)
        sectors_df = await _get_ths_member_reverse_cached(provider, con_code=ts_code)

        if sectors_df is not None and not sectors_df.empty:
            result["sectors"] = sectors_df.to_dict('records')
        
        return result
        
    except Exception as e:
        logger.error(f"获取股票板块信息失败: {e}")
        result["error"] = str(e)
        return result


async def get_sector_performance(
    ticker: str, 
    trade_date: str,
    lookback_days: int = 20
) -> str:
    """
    分析目标股票所属行业的整体表现
    
    Args:
        ticker: 股票代码
        trade_date: 交易日期 (YYYY-MM-DD 或 YYYYMMDD)
        lookback_days: 回看天数
    
    Returns:
        板块表现分析报告（字符串）
    """
    provider = _get_tushare_provider()
    
    try:
        # 1. 获取股票所属行业
        industry = await provider.get_stock_industry(ticker)
        if not industry:
            return f"⚠️ 无法获取股票 {ticker} 的行业信息"
        
        # 2. 获取股票所属板块 — 带缓存
        ts_code = provider._normalize_ts_code(ticker)
        sectors_df = await _get_ths_member_reverse_cached(provider, con_code=ts_code)
        
        # 3. 计算日期范围
        # 清理日期字符串，去掉可能的时间部分
        trade_date_clean = _clean_date_string(trade_date).replace('-', '')
        end_date = datetime.strptime(trade_date_clean, '%Y%m%d')
        start_date = end_date - timedelta(days=lookback_days + 10)  # 多取几天应对非交易日
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = trade_date_clean
        
        report_lines = [
            f"📊 板块表现分析报告",
            f"{'='*50}",
            f"🎯 目标股票: {ticker}",
            f"🏭 所属行业: {industry}",
            f"📅 分析日期: {trade_date}",
            f"📆 回看周期: {lookback_days} 交易日",
            "",
        ]
        
        # 4. 分析板块表现
        if sectors_df is not None and not sectors_df.empty:
            # ths_member 反查仅含板块代码，构建代码→名称映射（N行业板块 + I行业指数）
            name_map = {}
            for idx_type in ["N", "I"]:
                ldf = await _get_ths_index_list_cached(provider, idx_type)
                if ldf is not None and not ldf.empty:
                    for _, r in ldf.iterrows():
                        name_map[r['ts_code']] = r['name']

            sector_count = len(sectors_df)
            report_lines.append(f"📌 所属板块数: {sector_count} 个")
            report_lines.append("")
            report_lines.append("【板块涨跌幅排行】")
            
            # 获取每个板块的行情数据
            sector_performance = []
            for _, row in sectors_df.head(10).iterrows():  # 最多分析10个板块
                sector_code = row.get('ts_code')
                if not sector_code:
                    continue
                
                daily_df = await provider.get_ths_daily(
                    ts_code=sector_code,
                    start_date=start_date_str,
                    end_date=end_date_str
                )
                
                if daily_df is not None and not daily_df.empty:
                    # 计算累计涨跌幅
                    daily_df = daily_df.sort_values('trade_date')
                    if len(daily_df) >= 2:
                        first_close = daily_df.iloc[0]['close']
                        last_close = daily_df.iloc[-1]['close']
                        pct_change = ((last_close - first_close) / first_close) * 100
                        
                        # 获取最新一日涨跌
                        today_pct = daily_df.iloc[-1].get('pct_change', 0)
                        
                        sector_performance.append({
                            'code': sector_code,
                            'name': name_map.get(sector_code) or row.get('name', sector_code),
                            'period_pct': round(pct_change, 2),
                            'today_pct': round(today_pct, 2) if today_pct else 0
                        })
            
            # 按累计涨幅排序
            sector_performance.sort(key=lambda x: x['period_pct'], reverse=True)
            
            for i, sp in enumerate(sector_performance, 1):
                trend = "📈" if sp['period_pct'] > 0 else "📉"
                report_lines.append(
                    f"  {i}. {sp['name']}: {trend} {sp['period_pct']:+.2f}% "
                    f"(今日: {sp['today_pct']:+.2f}%)"
                )
        
        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"板块表现分析失败: {e}")
        return f"❌ 板块表现分析失败: {e}"


async def get_sector_rotation(trade_date: str, top_n: int = 10,
                              lookback_days: int = 1) -> str:
    """
    识别板块轮动趋势

    使用行业板块(moneyflow_ind_ths)和概念板块(moneyflow_cnt_ths)的资金流向数据，
    分析板块资金轮动方向。支持单日和多日（累计）两种模式。

    Args:
        trade_date: 截止交易日期
        top_n: 返回前N个板块
        lookback_days: 回溯天数，1=仅当天，>1=累计多天聚合

    Returns:
        板块轮动分析报告
    """
    provider = _get_tushare_provider()

    try:
        # 获取最新可用的交易日
        trade_date_clean = await _get_latest_trade_date(trade_date)
        trade_date_fmt = f"{trade_date_clean[:4]}-{trade_date_clean[4:6]}-{trade_date_clean[6:8]}"

        # ── 确定日期范围 ──
        is_multi_day = lookback_days > 1
        if is_multi_day:
            from datetime import datetime, timedelta
            end_dt = datetime.strptime(trade_date_clean, '%Y%m%d')
            start_dt = end_dt - timedelta(days=lookback_days)
            start_date_str = start_dt.strftime('%Y%m%d')
            end_date_str = trade_date_clean
            period_label = f"{start_dt.strftime('%Y-%m-%d')} ~ {trade_date_fmt}（约{lookback_days}天）"
        else:
            start_date_str = None
            end_date_str = None
            period_label = trade_date_fmt

        report_lines = [
            f"🔄 板块资金流向与轮动分析",
            f"{'='*50}",
            f"📅 分析周期: {period_label}",
            f"📊 模式: {'累计聚合' if is_multi_day else '单日快照'}",
            "",
        ]

        # ── 拉取数据 ──
        if is_multi_day:
            ind_df = await provider.get_moneyflow_ind_ths(
                start_date=start_date_str, end_date=end_date_str)
            cnt_df = await provider.get_moneyflow_cnt_ths(
                start_date=start_date_str, end_date=end_date_str)
        else:
            ind_df = await provider.get_moneyflow_ind_ths(
                trade_date=trade_date_clean)
            cnt_df = await provider.get_moneyflow_cnt_ths(
                trade_date=trade_date_clean)

        # ── 1. 行业板块资金流向 ──
        if ind_df is not None and not ind_df.empty:
            if is_multi_day:
                trade_days = ind_df['trade_date'].nunique()
                report_lines.append(f"  ℹ️ 行业板块数据覆盖 {trade_days} 个交易日")
                report_lines.append("")
                ind_agg = _aggregate_multi_day(ind_df, name_col='industry')
            else:
                ind_agg = None

            report_lines.append("【🏭 行业板块 — 资金净流入TOP】")
            if is_multi_day and ind_agg is not None:
                _append_multi_day_rows(report_lines, ind_agg, top_n, ascending=False)
            else:
                _append_single_day_rows(report_lines, ind_df, top_n,
                                        name_col='industry', ascending=False)

            report_lines.append("")
            report_lines.append("【🏭 行业板块 — 资金净流出TOP】")
            if is_multi_day and ind_agg is not None:
                _append_multi_day_rows(report_lines, ind_agg, top_n, ascending=True)
            else:
                _append_single_day_rows(report_lines, ind_df, top_n,
                                        name_col='industry', ascending=True)
            report_lines.append("")
        else:
            report_lines.append("⚠️ 暂无行业板块资金流向数据")
            report_lines.append("")

        # ── 2. 概念板块资金流向 ──
        if cnt_df is not None and not cnt_df.empty:
            if is_multi_day:
                trade_days = cnt_df['trade_date'].nunique()
                report_lines.append(f"  ℹ️ 概念板块数据覆盖 {trade_days} 个交易日")
                report_lines.append("")
                cnt_agg = _aggregate_multi_day(cnt_df, name_col='name')
            else:
                cnt_agg = None

            report_lines.append("【💡 概念板块 — 资金净流入TOP】")
            if is_multi_day and cnt_agg is not None:
                _append_multi_day_rows(report_lines, cnt_agg, top_n, ascending=False)
            else:
                _append_single_day_rows(report_lines, cnt_df, top_n,
                                        name_col='name', ascending=False)

            report_lines.append("")
            report_lines.append("【💡 概念板块 — 资金净流出TOP】")
            if is_multi_day and cnt_agg is not None:
                _append_multi_day_rows(report_lines, cnt_agg, top_n, ascending=True)
            else:
                _append_single_day_rows(report_lines, cnt_df, top_n,
                                        name_col='name', ascending=True)
            report_lines.append("")
        else:
            report_lines.append("⚠️ 暂无概念板块资金流向数据")
            report_lines.append("")

        # ── 3. 轮动判断 ──
        report_lines.append("【🎯 轮动判断】")
        if ind_df is not None and not ind_df.empty:
            if is_multi_day and ind_agg is not None:
                total_net = ind_agg['cum_net'].sum()
                inflow_count = (ind_agg['cum_net'] > 0).sum()
                outflow_count = (ind_agg['cum_net'] < 0).sum()
                label = "累计"
            else:
                total_net = ind_df['net_amount'].sum()
                inflow_count = (ind_df['net_amount'] > 0).sum()
                outflow_count = (ind_df['net_amount'] < 0).sum()
                label = "当日"

            if total_net > 0 and inflow_count > outflow_count * 1.5:
                report_lines.append(f"  • {label}行业资金面整体偏多，多数板块获得净流入")
            elif total_net < 0 and outflow_count > inflow_count * 1.5:
                report_lines.append(f"  • {label}行业资金面整体偏空，多数板块资金净流出")
            else:
                report_lines.append(f"  • {label}行业资金进出分化，板块轮动明显")
            report_lines.append(
                f"  • 行业板块{label}净流入: {inflow_count} 个 | 净流出: {outflow_count} 个 | "
                f"合计净额: {total_net:+.2f}亿"
            )

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"板块轮动分析失败: {e}")
        return f"❌ 板块轮动分析失败: {e}"


# ── 多日聚合辅助函数 ──

def _aggregate_multi_day(df, name_col: str):
    """
    将多日板块资金流向数据聚合为累计值。

    返回 DataFrame，按 cum_net 降序排列，包含:
    - name: 板块名称
    - cum_net: 累计净流入(亿元)
    - avg_net: 日均净流入(亿元)
    - inflow_days: 净流入天数
    - total_days: 总交易天数
    - avg_pct: 期间平均涨跌幅(%)
    """
    import pandas as pd

    total_days = df['trade_date'].nunique()

    agg = df.groupby(name_col).agg(
        cum_net=('net_amount', 'sum'),
        avg_net=('net_amount', 'mean'),
        inflow_days=('net_amount', lambda x: (x > 0).sum()),
        avg_pct=('pct_change', 'mean'),
    ).reset_index()

    agg = agg.rename(columns={name_col: 'name'})
    agg['total_days'] = total_days
    agg = agg.sort_values('cum_net', ascending=False)
    return agg


def _append_multi_day_rows(report_lines: list, agg_df, top_n: int,
                           ascending: bool):
    """向报告追加多日聚合排名行"""
    if ascending:
        rows = agg_df.tail(top_n).iloc[::-1]
    else:
        rows = agg_df.head(top_n)

    for i, row in enumerate(rows.itertuples(), 1):
        name = getattr(row, 'name', '')
        cum = getattr(row, 'cum_net', 0) or 0
        avg = getattr(row, 'avg_net', 0) or 0
        inflow_d = getattr(row, 'inflow_days', 0)
        total_d = getattr(row, 'total_days', 1)
        avg_pct = getattr(row, 'avg_pct', 0) or 0
        trend = "🔴" if cum > 0 else "🟢"
        report_lines.append(
            f"  {i}. {name}: {trend} 累计{cum:+.2f}亿 "
            f"(日均{avg:+.2f}亿, 净流入{inflow_d}/{total_d}天, "
            f"均涨跌幅{avg_pct:+.2f}%)"
        )


def _append_single_day_rows(report_lines: list, df, top_n: int,
                            name_col: str, ascending: bool):
    """向报告追加单日排名行"""
    sorted_df = df.sort_values('net_amount', ascending=ascending)
    if ascending:
        rows = sorted_df.head(top_n)
    else:
        rows = sorted_df.head(top_n)

    # 对于净流出 TOP，用 ascending=True 排序后取 head
    if ascending:
        sorted_df_asc = df.sort_values('net_amount', ascending=True)
        rows = sorted_df_asc.head(top_n)
    else:
        sorted_df_desc = df.sort_values('net_amount', ascending=False)
        rows = sorted_df_desc.head(top_n)

    for i, row in enumerate(rows.itertuples(), 1):
        name = getattr(row, name_col, getattr(row, 'ts_code', ''))
        net_amt = getattr(row, 'net_amount', 0) or 0
        pct = getattr(row, 'pct_change', 0) or 0
        lead = getattr(row, 'lead_stock', '')
        trend = "🔴" if net_amt > 0 else "🟢"
        lead_str = f" | 领涨: {lead}" if lead else ""
        report_lines.append(
            f"  {i}. {name}: {trend} {net_amt:+.2f}亿  涨跌幅: {pct:+.2f}%{lead_str}"
        )


async def get_peer_comparison(
    ticker: str,
    trade_date: str,
    top_n: int = 10
) -> str:
    """
    同业竞争对手对比分析

    对比目标股票与同行业其他股票的表现

    Args:
        ticker: 目标股票代码
        trade_date: 交易日期
        top_n: 对比的同业公司数量

    Returns:
        同业对比分析报告
    """
    provider = _get_tushare_provider()

    try:
        # 1. 获取股票所属行业
        industry = await provider.get_stock_industry(ticker)
        if not industry:
            return f"⚠️ 无法获取股票 {ticker} 的行业信息"

        # 2. 获取最新可用的交易日
        trade_date_clean = await _get_latest_trade_date(trade_date)
        trade_date_formatted = f"{trade_date_clean[:4]}-{trade_date_clean[4:6]}-{trade_date_clean[6:8]}"

        # 3. 获取同行业股票每日基础数据
        industry_df = await provider.get_sector_stocks_daily_basic(
            industry=industry,
            trade_date=trade_date_clean
        )

        report_lines = [
            f"📊 同业对比分析报告",
            f"{'='*50}",
            f"🎯 目标股票: {ticker}",
            f"🏭 所属行业: {industry}",
            f"📅 分析日期: {trade_date_formatted}",
            "",
        ]

        if industry_df is None or industry_df.empty:
            report_lines.append(f"⚠️ 暂无行业 {industry} 的对比数据")
            return "\n".join(report_lines)

        # 3. 按市值排序，取TOP N
        industry_df = industry_df.sort_values('total_mv', ascending=False)
        total_count = len(industry_df)
        report_lines.append(f"📌 行业内上市公司: {total_count} 家")
        report_lines.append("")

        # 4. 找到目标股票的数据
        ts_code = provider._normalize_ts_code(ticker)
        target_row = industry_df[industry_df['ts_code'] == ts_code]

        if not target_row.empty:
            target = target_row.iloc[0]
            target_rank = (industry_df['ts_code'] == ts_code).idxmax()
            target_rank_num = industry_df.index.get_loc(target_rank) + 1

            report_lines.append("【🎯 目标股票指标】")
            report_lines.append(f"  • 股票名称: {target.get('name', ticker)}")
            report_lines.append(f"  • 市值排名: {target_rank_num}/{total_count}")
            report_lines.append(f"  • 总市值: {target.get('total_mv', 0)/10000:.2f}亿")
            report_lines.append(f"  • PE(TTM): {target.get('pe_ttm', 'N/A')}")
            report_lines.append(f"  • PB: {target.get('pb', 'N/A')}")
            report_lines.append(f"  • 换手率: {target.get('turnover_rate', 'N/A')}%")
            report_lines.append("")

        # 5. 行业龙头对比
        report_lines.append(f"【🏆 行业龙头TOP{min(top_n, total_count)}】")
        for i, row in enumerate(industry_df.head(top_n).itertuples(), 1):
            name = getattr(row, 'name', getattr(row, 'ts_code', ''))
            total_mv = getattr(row, 'total_mv', 0) / 10000  # 转换为亿
            pe_ttm = getattr(row, 'pe_ttm', 'N/A')
            pb = getattr(row, 'pb', 'N/A')

            marker = "⭐" if getattr(row, 'ts_code', '') == ts_code else "  "
            report_lines.append(
                f"{marker}{i}. {name}: 市值{total_mv:.0f}亿 | "
                f"PE: {pe_ttm} | PB: {pb}"
            )

        # 6. 计算行业统计（过滤掉 NaN 值）
        import pandas as pd
        report_lines.append("")
        report_lines.append("【📈 行业统计】")

        pe_median = industry_df['pe_ttm'].dropna().median()
        pb_median = industry_df['pb'].dropna().median()
        pe_mean = industry_df['pe_ttm'].dropna().mean()
        pb_mean = industry_df['pb'].dropna().mean()

        if pd.notna(pe_median):
            report_lines.append(f"  • PE中位数: {pe_median:.2f} | PE均值: {pe_mean:.2f}")
        else:
            report_lines.append(f"  • PE数据: 暂无有效数据")

        if pd.notna(pb_median):
            report_lines.append(f"  • PB中位数: {pb_median:.2f} | PB均值: {pb_mean:.2f}")
        else:
            report_lines.append(f"  • PB数据: 暂无有效数据")

        # 7. 目标股票在行业中的估值位置
        if not target_row.empty:
            target_pe = target.get('pe_ttm')
            target_pb = target.get('pb')

            report_lines.append("")
            report_lines.append("【📊 估值评价】")

            # 处理 PE 估值（检查是否为 None 或 NaN）
            if pd.notna(target_pe) and pd.notna(pe_median):
                if target_pe < pe_median * 0.8:
                    report_lines.append(f"  • PE估值: {target_pe:.2f}，低于行业中位数({pe_median:.1f})，估值偏低")
                elif target_pe > pe_median * 1.2:
                    report_lines.append(f"  • PE估值: {target_pe:.2f}，高于行业中位数({pe_median:.1f})，估值偏高")
                else:
                    report_lines.append(f"  • PE估值: {target_pe:.2f}，接近行业中位数({pe_median:.1f})，估值合理")
            else:
                report_lines.append(f"  • PE估值: 数据缺失（可能亏损或数据未更新）")

            # 处理 PB 估值（检查是否为 None 或 NaN）
            if pd.notna(target_pb) and pd.notna(pb_median):
                if target_pb < pb_median * 0.8:
                    report_lines.append(f"  • PB估值: {target_pb:.2f}，低于行业中位数({pb_median:.1f})，估值偏低")
                elif target_pb > pb_median * 1.2:
                    report_lines.append(f"  • PB估值: {target_pb:.2f}，高于行业中位数({pb_median:.1f})，估值偏高")
                else:
                    report_lines.append(f"  • PB估值: {target_pb:.2f}，接近行业中位数({pb_median:.1f})，估值合理")
            else:
                report_lines.append(f"  • PB估值: 数据缺失")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"同业对比分析失败: {e}")
        return f"❌ 同业对比分析失败: {e}"


async def get_industry_top_companies(
    ticker: str,
    top_n: int = 5,
) -> str:
    """
    获取同行业 TOP N 公司列表（轻量版，自动取最新交易日）

    Args:
        ticker: 目标股票代码（如 600519 或 600519.SH）
        top_n: 返回前 N 家公司，默认 5

    Returns:
        同行业 TOP N 公司简表（代码、名称、市值、PE、PB）
    """
    provider = _get_tushare_provider()

    try:
        # 1. 获取股票所属行业
        industry = await provider.get_stock_industry(ticker)
        if not industry:
            return f"⚠️ 无法获取股票 {ticker} 的行业信息"

        # 2. 自动取最新交易日（用今天往前找）
        today_str = datetime.now().strftime('%Y-%m-%d')
        trade_date_clean = await _get_latest_trade_date(today_str)

        # 3. 获取同行业股票每日基础数据
        industry_df = await provider.get_sector_stocks_daily_basic(
            industry=industry,
            trade_date=trade_date_clean
        )

        if industry_df is None or industry_df.empty:
            return f"⚠️ 暂无行业「{industry}」在 {trade_date_clean} 的数据"

        # 4. 按市值排序
        industry_df = industry_df.sort_values('total_mv', ascending=False)
        total_count = len(industry_df)
        top_n_actual = min(top_n, total_count)

        # 5. 找目标股票的排名
        ts_code = provider._normalize_ts_code(ticker)
        target_rank = 0
        target_row = industry_df[industry_df['ts_code'] == ts_code]
        if not target_row.empty:
            target_rank = industry_df.index.get_loc(target_row.index[0]) + 1

        trade_date_formatted = f"{trade_date_clean[:4]}-{trade_date_clean[4:6]}-{trade_date_clean[6:8]}"

        # 6. 构建简表
        lines = [
            f"🏭 {industry} — 同行业 TOP {top_n_actual} 公司",
            f"📅 数据日期: {trade_date_formatted} | 行业共 {total_count} 家",
            "",
            f"{'排名':>4}  {'代码':<12} {'名称':<8} {'市值(亿)':>10} {'PE':>8} {'PB':>8}",
            f"{'─'*4}  {'─'*12} {'─'*8} {'─'*10} {'─'*8} {'─'*8}",
        ]

        for i, row in enumerate(industry_df.head(top_n_actual).itertuples(), 1):
            name = str(getattr(row, 'name', ''))[:6]  # 中文名截断对齐
            code = str(getattr(row, 'ts_code', ''))
            total_mv = getattr(row, 'total_mv', 0) or 0
            total_mv_yi = total_mv / 10000  # 万元 → 亿元
            pe = getattr(row, 'pe_ttm', None)
            pb = getattr(row, 'pb', None)
            pe_str = f"{pe:.1f}" if pe and pe == pe else "N/A"
            pb_str = f"{pb:.2f}" if pb and pb == pb else "N/A"
            marker = "◄" if code == ts_code else " "
            lines.append(
                f"{marker}{i:>3}  {code:<12} {name:<8} {total_mv_yi:>10.1f} {pe_str:>8} {pb_str:>8}"
            )

        # 7. 目标股票如果在 TOP N 之外，追加显示
        if target_rank > top_n_actual:
            target = target_row.iloc[0]
            name = str(target.get('name', ''))[:6]
            total_mv_yi = (target.get('total_mv', 0) or 0) / 10000
            pe = target.get('pe_ttm')
            pb = target.get('pb')
            pe_str = f"{pe:.1f}" if pe and pe == pe else "N/A"
            pb_str = f"{pb:.2f}" if pb and pb == pb else "N/A"
            lines.append(f"{'─'*4}  {'─'*12} {'─'*8} {'─'*10} {'─'*8} {'─'*8}")
            lines.append(
                f" {target_rank:>3}  {ts_code:<12} {name:<8} {total_mv_yi:>10.1f} {pe_str:>8} {pb_str:>8} (目标)"
            )

        lines.append("")
        lines.append("💡 提示: 使用 get_peer_comparison 可获取更详细的同业对比分析报告。")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"获取同行业 TOP 公司失败: {e}")
        return f"❌ 获取同行业 TOP 公司失败: {e}"


async def analyze_sector(ticker: str, trade_date: str) -> str:
    """
    综合板块分析（SectorAnalyst 主入口）

    整合板块表现、轮动趋势、同业对比三个维度的分析

    Args:
        ticker: 目标股票代码（如果是 "MARKET" 则分析整体板块情况）
        trade_date: 交易日期

    Returns:
        综合板块分析报告
    """
    try:
        # 判断是整体板块分析还是个股板块分析
        is_market_analysis = (ticker == "MARKET" or not ticker)

        if is_market_analysis:
            # 整体板块分析：只分析板块轮动
            rotation_report = await get_sector_rotation(trade_date)

            # 组合报告
            full_report = [
                "=" * 60,
                "🏭 板块分析师综合报告",
                "=" * 60,
                "",
                rotation_report,
                "",
                "=" * 60,
                "📋 分析结论",
                "=" * 60,
            ]

            full_report.append("请根据以上数据综合判断：")
            full_report.append("1. 当前市场热点板块和资金流向")
            full_report.append("2. 板块轮动的方向和强度")
            full_report.append("3. 市场整体的风险偏好")

        else:
            # 个股板块分析：分析目标股票所属板块
            performance_task = get_sector_performance(ticker, trade_date)
            rotation_task = get_sector_rotation(trade_date)
            peer_task = get_peer_comparison(ticker, trade_date)

            performance_report, rotation_report, peer_report = await asyncio.gather(
                performance_task, rotation_task, peer_task
            )

            # 组合报告
            full_report = [
                "=" * 60,
                "🏭 板块分析师综合报告",
                "=" * 60,
                "",
                performance_report,
                "",
                rotation_report,
                "",
                peer_report,
                "",
                "=" * 60,
                "📋 分析结论",
                "=" * 60,
            ]

            full_report.append("请根据以上数据综合判断：")
            full_report.append("1. 目标股票所属板块是否处于热点轮动中")
            full_report.append("2. 个股在行业中的地位和估值水平")
            full_report.append("3. 板块资金流向是否支持当前投资方向")

        return "\n".join(full_report)

    except Exception as e:
        logger.error(f"综合板块分析失败: {e}")
        return f"❌ 综合板块分析失败: {e}"


# ============================================================
# 板块级别工具函数（以板块名称/代码为入口）
# ============================================================

# 常见行业/概念别名 → 同花顺板块关键词
# 同花顺板块命名与常识叫法不一致时兜底（如"生猪养殖行业"在THS体系中叫"猪肉"）
# 注意：映射目标必须是THS体系中真实存在的板块名关键词
_SECTOR_SYNONYMS = {
    # 畜禽养殖：THS无"养殖/畜牧/生猪"板块，A股对应"猪肉"
    "养殖": "猪",
    "生猪": "猪",
    "养猪": "猪",
    "畜牧": "猪",
    "猪周期": "猪",
    "肉鸡": "鸡",
    # 金融：THS无"证券"板块，对应"参股券商/中资券商股"
    "证券": "券商",
    # 新能源
    "新能源车": "新能源汽车",
    "电动车": "新能源汽车",
    "锂电": "锂电池",
    "锂矿": "锂",
    # 军工航天：THS对应"军工"
    "国防": "军工",
    "船舶": "船",
    # 石化
    "石化": "石油",
    # 电子
    "封测": "集成电路",
    "面板": "OLED",
    # 汽车
    "汽车零部件": "汽车",
    "智能驾驶": "无人驾驶",
    # 农业
    "种业": "转基因",
    "渔业": "水产",
    # 消费
    "乳制品": "乳业",
    "奶牛": "乳",
    "零食": "休闲食品",
    "调味品": "调味",
    "家电": "家用电器",
    "中药": "中医药",
    "服装": "服饰",
    "造纸": "纸",
    # 基建物流
    "基建": "基础建设",
    "快递": "物流",
    "运营商": "电信运营",
    "水务": "污水",
    "机场": "航空",
}


def _synonym_keywords(keyword: str) -> List[str]:
    """扩展关键词：原词 + 命中的同义词映射目标（去重保序）。"""
    candidates = [keyword]
    for k, v in _SECTOR_SYNONYMS.items():
        if k in keyword and v not in candidates:
            candidates.append(v)
    return candidates


def _suggest_similar_sectors(df, keyword: str, top_n: int = 5) -> List[tuple]:
    """字符重叠模糊推荐：板块名与关键词至少重叠2个字符时按重叠数降序推荐。"""
    if df is None or df.empty:
        return []
    chars = set(keyword)
    scored = []
    for _, row in df.iterrows():
        name = str(row['name'])
        overlap = len(chars & set(name))
        if overlap >= 2:
            scored.append((overlap, str(row['ts_code']), name, row.get('count', 'N/A')))
    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]


async def _sector_not_found_hint(provider, keyword: str) -> str:
    """板块未命中时生成候选建议文本，帮助调用方（LLM）自我纠正板块名。"""
    # 1. 同义词重试提示
    synonym_names = []
    for idx_type in ["N", "I", "S"]:
        df = await _get_ths_index_list_cached(provider, idx_type)
        if df is None or df.empty:
            continue
        for kw in _synonym_keywords(keyword)[1:]:
            matched = df[df['name'].str.contains(kw, case=False, na=False)]
            for _, row in matched.head(3).iterrows():
                synonym_names.append(f"{row['name']} ({row['ts_code']})")
        if synonym_names:
            break
    # 2. 字符重叠候选
    if not synonym_names:
        for idx_type in ["N", "I", "S"]:
            df = await _get_ths_index_list_cached(provider, idx_type)
            if df is not None and not df.empty:
                synonym_names = [
                    f"{name} ({code})" for _o, code, name, _c in _suggest_similar_sectors(df, keyword)
                ]
                if synonym_names:
                    break
    hint = f"⚠️ 未找到包含 \"{keyword}\" 的板块。"
    if synonym_names:
        hint += f"相近板块：{'、'.join(synonym_names[:5])}。"
    hint += "建议：① 用上述板块名重试；② 调用 search_sector 搜索正确板块名；③ 若已知个股代码，改用 get_sector_performance(ticker) 按个股反查所属板块。"
    return hint


async def search_sector(
    keyword: str,
    sector_type: str = "N",
) -> str:
    """
    按名称关键词搜索同花顺板块

    Args:
        keyword: 板块名称关键词（如 "光伏"、"半导体"、"白酒"）
        sector_type: 板块类型 N=行业板块 I=行业指数 S=概念 R=地域，默认 N

    Returns:
        匹配的板块列表（含代码、名称、成分股数量）
    """
    provider = _get_tushare_provider()

    try:
        df = await _get_ths_index_list_cached(provider, sector_type)
        if df is None or df.empty:
            return f"⚠️ 暂无板块列表数据（类型={sector_type}）"

        # 模糊匹配
        matched = df[df['name'].str.contains(keyword, case=False, na=False)]

        if matched.empty:
            # 尝试其他类型（含I类行业指数：完整行业体系，"养殖/调味品"等仅存在于I类）
            for alt_type in ["I", "N", "S", "R"]:
                if alt_type == sector_type:
                    continue
                alt_df = await _get_ths_index_list_cached(provider, alt_type)
                if alt_df is not None and not alt_df.empty:
                    matched = alt_df[alt_df['name'].str.contains(keyword, case=False, na=False)]
                    if not matched.empty:
                        sector_type = alt_type
                        break

        matched_kw = keyword
        if matched.empty:
            # 同义词兜底：如"养殖"→"猪"（THS板块命名与常识叫法不一致）
            all_types = ["N", "I", "S", "R"]
            for kw in _synonym_keywords(keyword)[1:]:
                for t in all_types:
                    df_t = df if t == sector_type else await _get_ths_index_list_cached(provider, t)
                    if df_t is None or df_t.empty:
                        continue
                    hit = df_t[df_t['name'].str.contains(kw, case=False, na=False)]
                    if not hit.empty:
                        matched = hit
                        sector_type = t
                        matched_kw = kw
                        break
                if not matched.empty:
                    break

        if matched.empty:
            return await _sector_not_found_hint(provider, keyword)

        type_map = {"N": "行业", "S": "概念", "R": "地域", "I": "行业指数"}
        title_kw = f"\"{keyword}\"" if matched_kw == keyword else f"\"{keyword}\"（按同义词\"{matched_kw}\"匹配）"
        lines = [
            f"🔍 板块搜索结果：{title_kw}",
            f"类型: {type_map.get(sector_type, sector_type)}",
            f"匹配数量: {len(matched)} 个",
            "",
        ]
        for _, row in matched.head(15).iterrows():
            count = row.get('count', 'N/A')
            lines.append(f"  • {row['name']} ({row['ts_code']}) — 成分股 {count} 只")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"板块搜索失败: {e}")
        return f"❌ 板块搜索失败: {e}"


async def get_sector_daily(
    sector_name: str,
    trade_date: str,
    lookback_days: int = 20,
) -> str:
    """
    获取板块指数日线行情（按板块名称）

    Args:
        sector_name: 板块名称关键词（如 "光伏"、"半导体"）
        trade_date: 交易日期 YYYY-MM-DD
        lookback_days: 回看天数，默认 20

    Returns:
        板块指数行情报告
    """
    provider = _get_tushare_provider()

    try:
        # 1. 搜索板块代码
        sector_code = await _resolve_sector_code(provider, sector_name)
        if not sector_code:
            return await _sector_not_found_hint(provider, sector_name)

        sector_ts_code, sector_display_name = sector_code

        # 2. 获取日线数据
        trade_date_clean = _clean_date_string(trade_date).replace('-', '')
        end_date = datetime.strptime(trade_date_clean, '%Y%m%d')
        start_date = end_date - timedelta(days=lookback_days + 10)

        daily_df = await provider.get_ths_daily(
            ts_code=sector_ts_code,
            start_date=start_date.strftime('%Y%m%d'),
            end_date=trade_date_clean,
        )

        lines = [
            f"📊 板块行情报告",
            f"{'='*50}",
            f"🏷️ 板块: {sector_display_name} ({sector_ts_code})",
            f"📅 截至: {trade_date}",
            "",
        ]

        if daily_df is None or daily_df.empty:
            lines.append("⚠️ 暂无该板块的日线行情数据")
            return "\n".join(lines)

        daily_df = daily_df.sort_values('trade_date', ascending=True)

        # 最新一日
        latest = daily_df.iloc[-1]
        lines.append("【最新行情】")
        lines.append(f"  • 收盘: {latest.get('close', 'N/A')}")
        lines.append(f"  • 涨跌幅: {latest.get('pct_change', 0):+.2f}%")
        lines.append(f"  • 成交量: {latest.get('vol', 0):.0f}")
        lines.append(f"  • 换手率: {latest.get('turnover_rate', 0):.2f}%")
        if latest.get('total_mv'):
            lines.append(f"  • 总市值: {latest['total_mv']/10000:.0f}亿")
        lines.append("")

        # 区间统计
        if len(daily_df) >= 2:
            first_close = daily_df.iloc[0]['close']
            last_close = daily_df.iloc[-1]['close']
            period_pct = ((last_close - first_close) / first_close) * 100
            max_close = daily_df['close'].max()
            min_close = daily_df['close'].min()

            lines.append(f"【近 {len(daily_df)} 个交易日统计】")
            lines.append(f"  • 区间涨跌幅: {period_pct:+.2f}%")
            lines.append(f"  • 最高: {max_close}  最低: {min_close}")
            lines.append(f"  • 平均换手率: {daily_df['turnover_rate'].mean():.2f}%")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"板块行情获取失败: {e}")
        return f"❌ 板块行情获取失败: {e}"


async def get_sector_constituents(
    sector_name: str,
    trade_date: str,
    top_n: int = 15,
) -> str:
    """
    获取板块成分股列表及表现

    Args:
        sector_name: 板块名称关键词（如 "光伏"、"半导体"）
        trade_date: 交易日期 YYYY-MM-DD
        top_n: 返回前 N 只成分股，默认 15

    Returns:
        板块成分股列表及市值/估值排名
    """
    provider = _get_tushare_provider()

    try:
        # 1. 搜索板块代码
        sector_code = await _resolve_sector_code(provider, sector_name)
        if not sector_code:
            return await _sector_not_found_hint(provider, sector_name)

        sector_ts_code, sector_display_name = sector_code

        # 2. 获取成分股 — 带缓存
        members_df = await _get_ths_member_cached(provider, sector_ts_code)
        if members_df is None or members_df.empty:
            return f"⚠️ 板块 {sector_display_name} 暂无成分股数据"

        lines = [
            f"📋 板块成分股报告",
            f"{'='*50}",
            f"🏷️ 板块: {sector_display_name} ({sector_ts_code})",
            f"📅 日期: {trade_date}",
            f"📌 成分股总数: {len(members_df)} 只",
            "",
        ]

        # 3. 获取成分股的每日基础数据（市值、PE、PB 等）
        trade_date_clean = await _get_latest_trade_date(trade_date)
        daily_df = None
        try:
            daily_df = await asyncio.to_thread(
                provider.api.daily_basic,
                trade_date=trade_date_clean,
                fields='ts_code,close,pe_ttm,pb,total_mv,circ_mv,turnover_rate'
            )
        except Exception as e:
            logger.warning(f"获取 daily_basic 失败: {e}")

        if daily_df is not None and not daily_df.empty:
            # 合并成分股与每日数据
            member_codes = set(members_df['code'].tolist()) if 'code' in members_df.columns else set()
            if not member_codes:
                # 尝试用 con_code 字段
                member_codes = set(members_df['con_code'].tolist()) if 'con_code' in members_df.columns else set()

            # 匹配
            matched_daily = daily_df[daily_df['ts_code'].isin(member_codes)]
            if matched_daily.empty and member_codes:
                # 可能 code 格式不同，尝试不带后缀匹配
                member_codes_short = {c.split('.')[0] for c in member_codes}
                daily_df['code_short'] = daily_df['ts_code'].str.split('.').str[0]
                matched_daily = daily_df[daily_df['code_short'].isin(member_codes_short)]

            if not matched_daily.empty:
                # 按市值排序
                matched_daily = matched_daily.sort_values('total_mv', ascending=False)

                lines.append(f"【市值排名 TOP{min(top_n, len(matched_daily))}】")
                # 合并名称
                name_map = {}
                for _, row in members_df.iterrows():
                    code = row.get('code') or row.get('con_code', '')
                    name = row.get('name', code)
                    name_map[code] = name
                    # 也存短码
                    name_map[code.split('.')[0]] = name

                for i, row in enumerate(matched_daily.head(top_n).itertuples(), 1):
                    ts_code = getattr(row, 'ts_code', '')
                    name = name_map.get(ts_code, name_map.get(ts_code.split('.')[0], ts_code))
                    total_mv = getattr(row, 'total_mv', 0)
                    mv_yi = total_mv / 10000 if total_mv else 0
                    pe = getattr(row, 'pe_ttm', None)
                    pb = getattr(row, 'pb', None)
                    pe_str = f"{pe:.1f}" if pe and pe == pe else "N/A"
                    pb_str = f"{pb:.2f}" if pb and pb == pb else "N/A"

                    lines.append(
                        f"  {i:>2}. {name}({ts_code}): "
                        f"市值 {mv_yi:.0f}亿 | PE {pe_str} | PB {pb_str}"
                    )
            else:
                lines.append("⚠️ 无法获取成分股的市值/估值数据")
                lines.append("")
                lines.append("【成分股列表】")
                for i, row in enumerate(members_df.head(top_n).iterrows(), 1):
                    _, r = row
                    code = r.get('code') or r.get('con_code', '')
                    name = r.get('name', code)
                    lines.append(f"  {i:>2}. {name} ({code})")
        else:
            lines.append("【成分股列表】")
            for i, (_, r) in enumerate(members_df.head(top_n).iterrows(), 1):
                code = r.get('code') or r.get('con_code', '')
                name = r.get('name', code)
                lines.append(f"  {i:>2}. {name} ({code})")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"板块成分股获取失败: {e}")
        return f"❌ 板块成分股获取失败: {e}"


async def analyze_sector_by_name(
    sector_name: str,
    trade_date: str,
) -> str:
    """
    板块综合分析（以板块名称为入口）

    整合板块行情、成分股龙头、资金流向，一站式分析。

    Args:
        sector_name: 板块名称关键词（如 "光伏"、"半导体"、"白酒"）
        trade_date: 交易日期 YYYY-MM-DD

    Returns:
        板块综合分析报告
    """
    try:
        # 并行获取三个维度的数据
        daily_task = get_sector_daily(sector_name, trade_date)
        members_task = get_sector_constituents(sector_name, trade_date, top_n=10)
        rotation_task = get_sector_rotation(trade_date, top_n=10)

        daily_report, members_report, rotation_report = await asyncio.gather(
            daily_task, members_task, rotation_task
        )

        full_report = [
            "=" * 60,
            f"🏭 板块综合分析报告 — {sector_name}",
            "=" * 60,
            "",
            daily_report,
            "",
            members_report,
            "",
            rotation_report,
            "",
            "=" * 60,
            "📋 分析要点",
            "=" * 60,
            "请根据以上数据综合判断：",
            "1. 该板块近期走势和资金关注度",
            "2. 板块内龙头股的估值水平",
            "3. 板块在全市场资金流向中的位置",
        ]

        return "\n".join(full_report)

    except Exception as e:
        logger.error(f"板块综合分析失败: {e}")
        return f"❌ 板块综合分析失败: {e}"


# ============================================================
# 辅助函数
# ============================================================

async def _resolve_sector_code(
    provider, keyword: str
) -> Optional[tuple]:
    """
    根据关键词搜索板块，返回 (ts_code, name) 或 None。
    原词优先在 N(行业板块)/I(行业指数)/S(概念)/R(地域) 四类中查找，
    全部未命中再用同义词表重试（如"锂电"→"锂电池"）。
    注意：I类（881/884开头）是同花顺完整行业指数体系（约1100个），
    "养殖/生猪/调味品/港口"等行业仅在I类中存在，不可遗漏。
    """
    candidates = _synonym_keywords(keyword)
    for kw in candidates:  # 原词优先，同义词兜底
        for idx_type in ["N", "I", "S", "R"]:
            df = await _get_ths_index_list_cached(provider, idx_type)
            if df is None or df.empty:
                continue
            matched = df[df['name'].str.contains(kw, case=False, na=False)]
            if not matched.empty:
                # 取成分股最多的那个（通常是最主要的板块）
                if 'count' in matched.columns:
                    matched = matched.sort_values('count', ascending=False)
                top = matched.iloc[0]
                return (top['ts_code'], top['name'])
    return None


# ==================== 同步包装函数 ====================
# 为 LangGraph 工具提供同步接口

def analyze_sector_sync(ticker: str, trade_date: str) -> str:
    """analyze_sector 的同步版本"""
    return asyncio.run(analyze_sector(ticker, trade_date))


def get_sector_performance_sync(ticker: str, trade_date: str, lookback_days: int = 20) -> str:
    """get_sector_performance 的同步版本"""
    return asyncio.run(get_sector_performance(ticker, trade_date, lookback_days))


def get_sector_rotation_sync(trade_date: str, top_n: int = 10,
                             lookback_days: int = 1) -> str:
    """get_sector_rotation 的同步版本"""
    return asyncio.run(get_sector_rotation(trade_date, top_n, lookback_days))


def get_peer_comparison_sync(ticker: str, trade_date: str, top_n: int = 10) -> str:
    """get_peer_comparison 的同步版本"""
    return asyncio.run(get_peer_comparison(ticker, trade_date, top_n))


def get_industry_top_companies_sync(ticker: str, top_n: int = 5) -> str:
    """get_industry_top_companies 的同步版本"""
    return asyncio.run(get_industry_top_companies(ticker, top_n))


def search_sector_sync(keyword: str, sector_type: str = "N") -> str:
    """search_sector 的同步版本"""
    return asyncio.run(search_sector(keyword, sector_type))


def get_sector_daily_sync(sector_name: str, trade_date: str, lookback_days: int = 20) -> str:
    """get_sector_daily 的同步版本"""
    return asyncio.run(get_sector_daily(sector_name, trade_date, lookback_days))


def get_sector_constituents_sync(sector_name: str, trade_date: str, top_n: int = 15) -> str:
    """get_sector_constituents 的同步版本"""
    return asyncio.run(get_sector_constituents(sector_name, trade_date, top_n))


def analyze_sector_by_name_sync(sector_name: str, trade_date: str) -> str:
    """analyze_sector_by_name 的同步版本"""
    return asyncio.run(analyze_sector_by_name(sector_name, trade_date))

