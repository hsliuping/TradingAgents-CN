"""
板块分析工具函数

提供板块表现分析、轮动识别、同业对比等功能
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def _get_tushare_provider():
    """延迟导入获取 Tushare Provider"""
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    return get_tushare_provider()


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
        
        # 2. 获取所属板块（同花顺概念/行业板块）
        ts_code = provider._normalize_ts_code(ticker)
        sectors_df = await provider.get_ths_member(con_code=ts_code)
        
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
        
        # 2. 获取股票所属板块
        ts_code = provider._normalize_ts_code(ticker)
        sectors_df = await provider.get_ths_member(con_code=ts_code)
        
        # 3. 计算日期范围
        trade_date_clean = trade_date.replace('-', '')
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
                            'name': row.get('name', sector_code),
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


async def get_sector_rotation(trade_date: str, top_n: int = 10) -> str:
    """
    识别板块轮动趋势

    分析近期热门板块和资金流向，识别轮动方向

    Args:
        trade_date: 交易日期
        top_n: 返回前N个板块

    Returns:
        板块轮动分析报告
    """
    provider = _get_tushare_provider()

    try:
        trade_date_clean = trade_date.replace('-', '')

        # 获取板块资金流向数据
        moneyflow_df = await provider.get_moneyflow_ths(trade_date=trade_date_clean)

        report_lines = [
            f"🔄 板块轮动趋势分析",
            f"{'='*50}",
            f"📅 分析日期: {trade_date}",
            "",
        ]

        if moneyflow_df is None or moneyflow_df.empty:
            report_lines.append("⚠️ 暂无板块资金流向数据")
            return "\n".join(report_lines)

        # 按净流入金额排序
        moneyflow_df = moneyflow_df.sort_values('net_amount', ascending=False)

        # 资金流入TOP板块
        report_lines.append("【💰 资金净流入TOP板块】")
        inflow_df = moneyflow_df.head(top_n)
        for i, row in enumerate(inflow_df.itertuples(), 1):
            ts_code = getattr(row, 'ts_code', '')
            name = getattr(row, 'name', ts_code)
            net_amount = getattr(row, 'net_amount', 0)
            net_rate = getattr(row, 'net_amount_rate', 0)

            # 转换单位：万元 -> 亿元
            net_amount_yi = net_amount / 10000 if net_amount else 0
            trend = "🔴" if net_amount > 0 else "🟢"

            report_lines.append(
                f"  {i}. {name}: {trend} {net_amount_yi:+.2f}亿 "
                f"(占比: {net_rate:.2f}%)"
            )

        report_lines.append("")

        # 资金流出TOP板块
        report_lines.append("【💸 资金净流出TOP板块】")
        outflow_df = moneyflow_df.tail(top_n).iloc[::-1]
        for i, row in enumerate(outflow_df.itertuples(), 1):
            ts_code = getattr(row, 'ts_code', '')
            name = getattr(row, 'name', ts_code)
            net_amount = getattr(row, 'net_amount', 0)
            net_rate = getattr(row, 'net_amount_rate', 0)

            net_amount_yi = net_amount / 10000 if net_amount else 0

            report_lines.append(
                f"  {i}. {name}: 🟢 {net_amount_yi:+.2f}亿 "
                f"(占比: {net_rate:.2f}%)"
            )

        # 轮动判断
        report_lines.append("")
        report_lines.append("【🎯 轮动判断】")

        total_inflow = inflow_df['net_amount'].sum() / 10000
        total_outflow = abs(outflow_df['net_amount'].sum()) / 10000

        if total_inflow > total_outflow * 1.5:
            report_lines.append("  • 市场整体资金流入，偏多头氛围")
        elif total_outflow > total_inflow * 1.5:
            report_lines.append("  • 市场整体资金流出，偏空头氛围")
        else:
            report_lines.append("  • 市场资金进出均衡，板块轮动明显")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"板块轮动分析失败: {e}")
        return f"❌ 板块轮动分析失败: {e}"


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

        # 2. 获取同行业股票每日基础数据
        trade_date_clean = trade_date.replace('-', '')
        industry_df = await provider.get_sector_stocks_daily_basic(
            industry=industry,
            trade_date=trade_date_clean
        )

        report_lines = [
            f"📊 同业对比分析报告",
            f"{'='*50}",
            f"🎯 目标股票: {ticker}",
            f"🏭 所属行业: {industry}",
            f"📅 分析日期: {trade_date}",
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

        # 6. 计算行业统计
        report_lines.append("")
        report_lines.append("【📈 行业统计】")

        pe_median = industry_df['pe_ttm'].median()
        pb_median = industry_df['pb'].median()
        pe_mean = industry_df['pe_ttm'].mean()
        pb_mean = industry_df['pb'].mean()

        report_lines.append(f"  • PE中位数: {pe_median:.2f} | PE均值: {pe_mean:.2f}")
        report_lines.append(f"  • PB中位数: {pb_median:.2f} | PB均值: {pb_mean:.2f}")

        # 7. 目标股票在行业中的估值位置
        if not target_row.empty:
            target_pe = target.get('pe_ttm')
            target_pb = target.get('pb')

            report_lines.append("")
            report_lines.append("【📊 估值评价】")

            if target_pe and pe_median:
                if target_pe < pe_median * 0.8:
                    report_lines.append(f"  • PE估值: 低于行业中位数({pe_median:.1f})，估值偏低")
                elif target_pe > pe_median * 1.2:
                    report_lines.append(f"  • PE估值: 高于行业中位数({pe_median:.1f})，估值偏高")
                else:
                    report_lines.append(f"  • PE估值: 接近行业中位数({pe_median:.1f})，估值合理")

            if target_pb and pb_median:
                if target_pb < pb_median * 0.8:
                    report_lines.append(f"  • PB估值: 低于行业中位数({pb_median:.1f})，估值偏低")
                elif target_pb > pb_median * 1.2:
                    report_lines.append(f"  • PB估值: 高于行业中位数({pb_median:.1f})，估值偏高")
                else:
                    report_lines.append(f"  • PB估值: 接近行业中位数({pb_median:.1f})，估值合理")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"同业对比分析失败: {e}")
        return f"❌ 同业对比分析失败: {e}"


async def analyze_sector(ticker: str, trade_date: str) -> str:
    """
    综合板块分析（SectorAnalyst 主入口）

    整合板块表现、轮动趋势、同业对比三个维度的分析

    Args:
        ticker: 目标股票代码
        trade_date: 交易日期

    Returns:
        综合板块分析报告
    """
    try:
        # 并行获取三个分析结果
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

        # 添加简要结论（可以后续用 LLM 生成更智能的总结）
        full_report.append("请根据以上数据综合判断：")
        full_report.append("1. 目标股票所属板块是否处于热点轮动中")
        full_report.append("2. 个股在行业中的地位和估值水平")
        full_report.append("3. 板块资金流向是否支持当前投资方向")

        return "\n".join(full_report)

    except Exception as e:
        logger.error(f"综合板块分析失败: {e}")
        return f"❌ 综合板块分析失败: {e}"


# ==================== 同步包装函数 ====================
# 为 LangGraph 工具提供同步接口

def analyze_sector_sync(ticker: str, trade_date: str) -> str:
    """analyze_sector 的同步版本"""
    return asyncio.run(analyze_sector(ticker, trade_date))


def get_sector_performance_sync(ticker: str, trade_date: str, lookback_days: int = 20) -> str:
    """get_sector_performance 的同步版本"""
    return asyncio.run(get_sector_performance(ticker, trade_date, lookback_days))


def get_sector_rotation_sync(trade_date: str, top_n: int = 10) -> str:
    """get_sector_rotation 的同步版本"""
    return asyncio.run(get_sector_rotation(trade_date, top_n))


def get_peer_comparison_sync(ticker: str, trade_date: str, top_n: int = 10) -> str:
    """get_peer_comparison 的同步版本"""
    return asyncio.run(get_peer_comparison(ticker, trade_date, top_n))

