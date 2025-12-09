"""
大盘/指数分析工具函数

提供指数走势分析、市场宽度分析、市场环境评估等功能
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd

logger = logging.getLogger(__name__)

# 主要指数代码
MAIN_INDICES = {
    '000001.SH': '上证指数',
    '399001.SZ': '深证成指',
    '399006.SZ': '创业板指',
    '000300.SH': '沪深300',
    '000905.SH': '中证500',
}


def _get_tushare_provider():
    """延迟导入获取 Tushare Provider"""
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    return get_tushare_provider()


async def get_index_trend(
    trade_date: str,
    lookback_days: int = 60
) -> str:
    """
    分析主要指数走势
    
    Args:
        trade_date: 交易日期
        lookback_days: 回看天数
    
    Returns:
        指数走势分析报告
    """
    provider = _get_tushare_provider()
    
    try:
        # 计算日期范围
        trade_date_clean = trade_date.replace('-', '')
        end_date = datetime.strptime(trade_date_clean, '%Y%m%d')
        start_date = end_date - timedelta(days=lookback_days + 30)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = trade_date_clean
        
        report_lines = [
            "📈 主要指数走势分析",
            "=" * 50,
            f"📅 分析日期: {trade_date}",
            f"📆 回看周期: {lookback_days} 交易日",
            "",
            "【主要指数表现】",
        ]
        
        for index_code, index_name in MAIN_INDICES.items():
            daily_df = await provider.get_index_daily(
                ts_code=index_code,
                start_date=start_date_str,
                end_date=end_date_str
            )
            
            if daily_df is None or daily_df.empty:
                report_lines.append(f"  {index_name}: 暂无数据")
                continue
            
            # 按日期排序
            daily_df = daily_df.sort_values('trade_date')
            
            if len(daily_df) < 5:
                report_lines.append(f"  {index_name}: 数据不足")
                continue
            
            # 计算指标
            latest = daily_df.iloc[-1]
            today_pct = latest.get('pct_chg', 0)
            close_price = latest.get('close', 0)
            
            # 5日/20日/60日涨跌幅
            pct_5d = ((close_price / daily_df.iloc[-5]['close']) - 1) * 100 if len(daily_df) >= 5 else 0
            pct_20d = ((close_price / daily_df.iloc[-20]['close']) - 1) * 100 if len(daily_df) >= 20 else 0
            
            # 均线位置
            ma5 = daily_df['close'].tail(5).mean()
            ma20 = daily_df['close'].tail(20).mean() if len(daily_df) >= 20 else ma5
            ma60 = daily_df['close'].tail(60).mean() if len(daily_df) >= 60 else ma20
            
            # 趋势判断
            if close_price > ma5 > ma20 > ma60:
                trend = "📈 多头排列"
            elif close_price < ma5 < ma20 < ma60:
                trend = "📉 空头排列"
            else:
                trend = "📊 震荡整理"
            
            trend_icon = "🔴" if today_pct > 0 else "🟢" if today_pct < 0 else "⚪"
            
            report_lines.append(
                f"  {trend_icon} {index_name}({index_code}): {close_price:.2f}"
            )
            report_lines.append(
                f"      今日: {today_pct:+.2f}% | 5日: {pct_5d:+.2f}% | "
                f"20日: {pct_20d:+.2f}% | {trend}"
            )
        
        return "\n".join(report_lines)
        
    except Exception as e:
        logger.error(f"指数走势分析失败: {e}")
        return f"❌ 指数走势分析失败: {e}"


async def get_market_breadth(trade_date: str) -> str:
    """
    分析市场宽度（涨跌家数、涨停跌停等）
    
    Args:
        trade_date: 交易日期
    
    Returns:
        市场宽度分析报告
    """
    provider = _get_tushare_provider()
    
    try:
        trade_date_clean = trade_date.replace('-', '')
        
        # 获取市场交易统计
        daily_info = await provider.get_daily_info(trade_date=trade_date_clean)
        
        report_lines = [
            "",
            "📊 市场宽度分析",
            "=" * 50,
            f"📅 日期: {trade_date}",
            "",
        ]
        
        if daily_info is None or daily_info.empty:
            report_lines.append("⚠️ 暂无市场统计数据")
            return "\n".join(report_lines)
        
        # 汇总统计
        total_up = daily_info['up_count'].sum() if 'up_count' in daily_info.columns else 0
        total_down = daily_info['down_count'].sum() if 'down_count' in daily_info.columns else 0
        total_amount = daily_info['amount'].sum() / 100000000 if 'amount' in daily_info.columns else 0
        
        report_lines.append("【涨跌统计】")
        report_lines.append(f"  • 上涨家数: {int(total_up)}")
        report_lines.append(f"  • 下跌家数: {int(total_down)}")
        
        # 涨跌比
        if total_down > 0:
            ratio = total_up / total_down
            if ratio > 2:
                sentiment = "极度乐观 🔥"
            elif ratio > 1.5:
                sentiment = "偏多 📈"
            elif ratio > 0.67:
                sentiment = "中性 📊"
            elif ratio > 0.5:
                sentiment = "偏空 📉"
            else:
                sentiment = "极度悲观 ❄️"
            report_lines.append(f"  • 涨跌比: {ratio:.2f} ({sentiment})")
        
        report_lines.append("")
        report_lines.append("【成交统计】")
        report_lines.append(f"  • 总成交额: {total_amount:.2f} 亿元")
        
        return "\n".join(report_lines)
        
    except Exception as e:
        logger.error(f"市场宽度分析失败: {e}")
        return f"❌ 市场宽度分析失败: {e}"


async def get_market_environment(trade_date: str) -> str:
    """
    评估市场环境（估值、风险等）

    Args:
        trade_date: 交易日期

    Returns:
        市场环境评估报告
    """
    provider = _get_tushare_provider()

    try:
        trade_date_clean = trade_date.replace('-', '')

        report_lines = [
            "",
            "🌐 市场环境评估",
            "=" * 50,
            f"📅 日期: {trade_date}",
            "",
            "【指数估值水平】",
        ]

        # 获取主要指数估值
        for index_code, index_name in list(MAIN_INDICES.items())[:3]:
            basic_df = await provider.get_index_dailybasic(
                ts_code=index_code,
                trade_date=trade_date_clean
            )

            if basic_df is None or basic_df.empty:
                report_lines.append(f"  {index_name}: 暂无估值数据")
                continue

            row = basic_df.iloc[0]
            pe = row.get('pe', row.get('pe_ttm', 'N/A'))
            pb = row.get('pb', 'N/A')
            turnover = row.get('turnover_rate', 'N/A')
            total_mv = row.get('total_mv', 0)
            total_mv_wan_yi = total_mv / 100000000 if total_mv else 0

            report_lines.append(f"  {index_name}:")
            report_lines.append(f"      PE: {pe} | PB: {pb} | 换手率: {turnover}%")
            report_lines.append(f"      总市值: {total_mv_wan_yi:.2f} 万亿")

        # 风险评估
        report_lines.append("")
        report_lines.append("【风险评估】")

        # 获取上证指数近期数据计算波动率
        daily_df = await provider.get_index_daily(
            ts_code='000001.SH',
            start_date=(datetime.strptime(trade_date_clean, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d'),
            end_date=trade_date_clean
        )

        if daily_df is not None and len(daily_df) >= 20:
            # 计算20日波动率
            returns = daily_df['pct_chg'].dropna()
            volatility = returns.std() * (252 ** 0.5)  # 年化波动率

            if volatility > 30:
                risk_level = "高风险 🔴"
            elif volatility > 20:
                risk_level = "中等风险 🟡"
            else:
                risk_level = "低风险 🟢"

            report_lines.append(f"  • 20日年化波动率: {volatility:.2f}% ({risk_level})")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"市场环境评估失败: {e}")
        return f"❌ 市场环境评估失败: {e}"


async def identify_market_cycle(trade_date: str) -> str:
    """
    识别市场周期（牛市/熊市/震荡市）

    Args:
        trade_date: 交易日期

    Returns:
        市场周期判断报告
    """
    provider = _get_tushare_provider()

    try:
        trade_date_clean = trade_date.replace('-', '')
        end_date = datetime.strptime(trade_date_clean, '%Y%m%d')
        start_date = end_date - timedelta(days=365)  # 一年数据

        # 获取上证指数数据
        daily_df = await provider.get_index_daily(
            ts_code='000001.SH',
            start_date=start_date.strftime('%Y%m%d'),
            end_date=trade_date_clean
        )

        report_lines = [
            "",
            "🔄 市场周期判断",
            "=" * 50,
        ]

        if daily_df is None or len(daily_df) < 60:
            report_lines.append("⚠️ 数据不足，无法判断市场周期")
            return "\n".join(report_lines)

        daily_df = daily_df.sort_values('trade_date')

        current_close = daily_df.iloc[-1]['close']
        ma60 = daily_df['close'].tail(60).mean()
        ma120 = daily_df['close'].tail(120).mean() if len(daily_df) >= 120 else ma60
        ma250 = daily_df['close'].tail(250).mean() if len(daily_df) >= 250 else ma120

        # 计算年内高低点
        year_high = daily_df['high'].max()
        year_low = daily_df['low'].min()
        position = (current_close - year_low) / (year_high - year_low) * 100 if year_high != year_low else 50

        # 周期判断
        if current_close > ma60 > ma120 > ma250:
            cycle = "牛市阶段 🐂"
            advice = "趋势向上，可适度积极"
        elif current_close < ma60 < ma120 < ma250:
            cycle = "熊市阶段 🐻"
            advice = "趋势向下，建议防守"
        elif current_close > ma60 and current_close > ma120:
            cycle = "反弹阶段 📈"
            advice = "短期走强，关注持续性"
        elif current_close < ma60 and current_close < ma120:
            cycle = "调整阶段 📉"
            advice = "短期走弱，等待企稳"
        else:
            cycle = "震荡阶段 📊"
            advice = "方向不明，轻仓观望"

        report_lines.append(f"  🎯 市场周期: {cycle}")
        report_lines.append(f"  📍 年内位置: {position:.1f}% (0%=年内低点, 100%=年内高点)")
        report_lines.append(f"  💡 操作建议: {advice}")
        report_lines.append("")
        report_lines.append("【均线系统】")
        report_lines.append(f"  • 当前价格: {current_close:.2f}")
        report_lines.append(f"  • MA60: {ma60:.2f} ({'↑' if current_close > ma60 else '↓'})")
        report_lines.append(f"  • MA120: {ma120:.2f} ({'↑' if current_close > ma120 else '↓'})")
        report_lines.append(f"  • MA250: {ma250:.2f} ({'↑' if current_close > ma250 else '↓'})")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"市场周期判断失败: {e}")
        return f"❌ 市场周期判断失败: {e}"


async def analyze_index(trade_date: str) -> str:
    """
    综合大盘分析（IndexAnalyst 主入口）

    整合指数走势、市场宽度、市场环境、市场周期四个维度的分析

    Args:
        trade_date: 交易日期

    Returns:
        综合大盘分析报告
    """
    try:
        # 并行获取四个分析结果
        trend_task = get_index_trend(trade_date)
        breadth_task = get_market_breadth(trade_date)
        env_task = get_market_environment(trade_date)
        cycle_task = identify_market_cycle(trade_date)

        trend_report, breadth_report, env_report, cycle_report = await asyncio.gather(
            trend_task, breadth_task, env_task, cycle_task
        )

        # 组合报告
        full_report = [
            "=" * 60,
            "🌐 大盘分析师综合报告",
            "=" * 60,
            "",
            trend_report,
            breadth_report,
            env_report,
            cycle_report,
            "",
            "=" * 60,
        ]

        return "\n".join(full_report)

    except Exception as e:
        logger.error(f"综合大盘分析失败: {e}")
        return f"❌ 综合大盘分析失败: {e}"


# ==================== 同步包装函数 ====================

def analyze_index_sync(trade_date: str) -> str:
    """analyze_index 的同步版本"""
    return asyncio.run(analyze_index(trade_date))


def get_index_trend_sync(trade_date: str, lookback_days: int = 60) -> str:
    """get_index_trend 的同步版本"""
    return asyncio.run(get_index_trend(trade_date, lookback_days))


def get_market_breadth_sync(trade_date: str) -> str:
    """get_market_breadth 的同步版本"""
    return asyncio.run(get_market_breadth(trade_date))


def get_market_environment_sync(trade_date: str) -> str:
    """get_market_environment 的同步版本"""
    return asyncio.run(get_market_environment(trade_date))


def identify_market_cycle_sync(trade_date: str) -> str:
    """identify_market_cycle 的同步版本"""
    return asyncio.run(identify_market_cycle(trade_date))

