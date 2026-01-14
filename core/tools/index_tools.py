"""
大盘/指数分析工具函数

提供指数走势分析、市场宽度分析、市场环境评估等功能
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd

logger = logging.getLogger(__name__)

# 缓存管理器
_cache = None

def _get_cache():
    """获取缓存管理器实例"""
    global _cache
    if _cache is None:
        try:
            from tradingagents.dataflows.cache import get_cache
            _cache = get_cache()
            logger.info("✅ 指数分析工具已启用缓存")
        except Exception as e:
            logger.warning(f"⚠️ 缓存系统不可用: {e}")
    return _cache

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
    trade_date_clean = trade_date.replace('-', '')

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

            logger.debug(f"🔍 获取到 {len(df)} 个交易日，最新: {latest_trade_date}, 请求: {trade_date_clean}")

            if latest_trade_date != trade_date_clean:
                logger.info(f"📅 {trade_date} 无数据，使用最近交易日 {latest_trade_date}")
            else:
                logger.debug(f"✅ {trade_date} 是有效交易日")

            return latest_trade_date

        # 如果都没有找到，返回原始日期
        logger.warning(f"⚠️ 无法找到有效交易日，使用原始日期 {trade_date_clean}")
        return trade_date_clean

    except Exception as e:
        logger.error(f"❌ 获取最新交易日失败: {e}")
        return trade_date_clean


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
        # 获取最新可用的交易日
        trade_date_clean = await _get_latest_trade_date(trade_date)
        trade_date_formatted = f"{trade_date_clean[:4]}-{trade_date_clean[4:6]}-{trade_date_clean[6:8]}"

        report_lines = [
            "",
            "📊 市场宽度分析",
            "=" * 50,
            f"📅 日期: {trade_date_formatted}",
            "",
        ]

        # 使用 daily_info API 获取市场整体统计
        daily_info = await provider.get_daily_info(trade_date=trade_date_clean)

        if daily_info is not None and not daily_info.empty:
            # 提取上海和深圳市场的数据
            sh_market = daily_info[daily_info['ts_code'] == 'SH_MARKET']
            sz_market = daily_info[daily_info['ts_code'] == 'SZ_MARKET']

            # 成交统计
            sh_amount = float(sh_market['amount'].iloc[0]) if len(sh_market) > 0 and 'amount' in sh_market.columns else 0
            sz_amount = float(sz_market['amount'].iloc[0]) if len(sz_market) > 0 and 'amount' in sz_market.columns else 0
            total_amount = sh_amount + sz_amount

            # 成交量（处理 NaN 值）
            import pandas as pd
            sh_vol = float(sh_market['vol'].iloc[0]) if len(sh_market) > 0 and 'vol' in sh_market.columns and pd.notna(sh_market['vol'].iloc[0]) else 0
            sz_vol = float(sz_market['vol'].iloc[0]) if len(sz_market) > 0 and 'vol' in sz_market.columns and pd.notna(sz_market['vol'].iloc[0]) else 0
            total_vol = sh_vol + sz_vol

            # 上市公司数量
            sh_count = int(sh_market['com_count'].iloc[0]) if len(sh_market) > 0 and 'com_count' in sh_market.columns else 0
            sz_count = int(sz_market['com_count'].iloc[0]) if len(sz_market) > 0 and 'com_count' in sz_market.columns else 0
            total_count = sh_count + sz_count

            report_lines.append("【市场规模】")
            report_lines.append(f"  • 上市公司总数: {total_count} 家")
            report_lines.append(f"    - 上海市场: {sh_count} 家")
            report_lines.append(f"    - 深圳市场: {sz_count} 家")

            report_lines.append("")
            report_lines.append("【成交统计】")
            report_lines.append(f"  • 总成交额: {total_amount:.2f} 亿元")
            report_lines.append(f"    - 上海市场: {sh_amount:.2f} 亿元 ({sh_amount/total_amount*100:.1f}%)" if total_amount > 0 else "    - 上海市场: 0.00 亿元")
            report_lines.append(f"    - 深圳市场: {sz_amount:.2f} 亿元 ({sz_amount/total_amount*100:.1f}%)" if total_amount > 0 else "    - 深圳市场: 0.00 亿元")
            if total_vol > 0:
                report_lines.append(f"  • 总成交量: {total_vol:.2f} 亿股")

            # 成交活跃度判断
            if total_amount > 0:
                avg_amount_per_stock = total_amount / total_count if total_count > 0 else 0
                if total_amount > 15000:
                    activity = "极度活跃 🔥"
                elif total_amount > 10000:
                    activity = "活跃 📈"
                elif total_amount > 7000:
                    activity = "正常 📊"
                elif total_amount > 5000:
                    activity = "偏冷清 📉"
                else:
                    activity = "清淡 ❄️"
                report_lines.append(f"  • 市场活跃度: {activity}")
                report_lines.append(f"  • 平均每股成交: {avg_amount_per_stock:.2f} 亿元")
        else:
            # 方案2: 使用 daily_basic API 获取市场整体数据
            daily_basic = await provider.get_daily_basic(trade_date=trade_date_clean)

            if daily_basic is not None and not daily_basic.empty:
                # 统计市值数据
                total_mv = daily_basic['total_mv'].sum() / 100000000 if 'total_mv' in daily_basic.columns else 0
                avg_turnover = daily_basic['turnover_rate'].mean() if 'turnover_rate' in daily_basic.columns else 0
                stock_count = len(daily_basic)

                report_lines.append("【市场概况】")
                report_lines.append(f"  • 在交易股票数: {stock_count}")
                report_lines.append(f"  • 总市值: {total_mv:.2f} 万亿")
                report_lines.append(f"  • 平均换手率: {avg_turnover:.2f}%")

                # 使用 PE 分布判断市场情绪
                if 'pe' in daily_basic.columns:
                    pe_median = daily_basic['pe'].dropna().median()
                    report_lines.append(f"  • 市场中位数PE: {pe_median:.2f}")
            else:
                report_lines.append("⚠️ 暂无市场统计数据（可能需要更高的 Tushare 积分）")

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
        # 首先获取最新可用的交易日
        actual_trade_date = await _get_latest_trade_date(trade_date)
        actual_trade_date_formatted = f"{actual_trade_date[:4]}-{actual_trade_date[4:6]}-{actual_trade_date[6:8]}"

        logger.info(f"📊 大盘分析使用交易日: {actual_trade_date_formatted}")

        # 并行获取四个分析结果
        trend_task = get_index_trend(actual_trade_date_formatted)
        breadth_task = get_market_breadth(actual_trade_date_formatted)
        env_task = get_market_environment(actual_trade_date_formatted)
        cycle_task = identify_market_cycle(actual_trade_date_formatted)

        trend_report, breadth_report, env_report, cycle_report = await asyncio.gather(
            trend_task, breadth_task, env_task, cycle_task
        )

        # 组合报告
        full_report = [
            "=" * 60,
            "🌐 大盘分析师综合报告",
            f"📅 分析日期: {actual_trade_date_formatted}",
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


# ==================== 新增大盘分析工具 ====================

async def get_north_flow(trade_date: str, lookback_days: int = 10) -> str:
    """
    获取北向资金流向分析

    Args:
        trade_date: 交易日期 (YYYY-MM-DD)
        lookback_days: 回看天数

    Returns:
        北向资金流向分析报告
    """
    provider = _get_tushare_provider()

    try:
        trade_date_clean = trade_date.replace('-', '')
        end_date = datetime.strptime(trade_date_clean, '%Y%m%d')
        start_date = end_date - timedelta(days=lookback_days + 10)

        df = await provider.get_hsgt_moneyflow(
            start_date=start_date.strftime('%Y%m%d'),
            end_date=trade_date_clean
        )

        report_lines = [
            "",
            "💰 北向资金流向分析",
            "=" * 50,
            f"📅 日期: {trade_date}",
            "",
        ]

        if df is None or df.empty:
            report_lines.append("⚠️ 暂无北向资金数据（可能需要更高的 Tushare 积分）")
            return "\n".join(report_lines)

        # 按日期排序
        df = df.sort_values('trade_date', ascending=False)

        # 🔑 确保数值列为数值类型（根据 Tushare 文档，这些字段应该是 float）
        # 参考文档：https://tushare.pro/document/2?doc_id=47
        # Tushare 返回的数据格式：hgt/sgt/north_money 都是 float 类型（百万元）
        numeric_cols = ['hgt', 'sgt', 'ggt_ss', 'ggt_sz', 'north_money', 'south_money']
        for col in numeric_cols:
            if col in df.columns:
                # 先尝试直接转换为数值类型
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except Exception:
                    # 如果直接转换失败，先清理格式错误
                    # 处理可能的格式错误：如果包含多个小数点或数字被错误连接
                    # 例如 "182490.64238444.93" -> 提取第一个有效数字 "182490.64"
                    def clean_numeric_value(val):
                        if pd.isna(val):
                            return 0.0
                        val_str = str(val).strip()
                        # 移除逗号和空格
                        val_str = val_str.replace(',', '').replace(' ', '')
                        # 如果包含多个小数点，提取第一个完整的数字
                        # 匹配模式：可选负号 + 数字 + 小数点 + 数字（第一个完整数字）
                        match = re.match(r'(-?\d+\.\d{1,2})', val_str)
                        if match:
                            return float(match.group(1))
                        # 如果没有小数点，尝试匹配整数
                        match = re.match(r'(-?\d+)', val_str)
                        if match:
                            return float(match.group(1))
                        return 0.0
                    
                    df[col] = df[col].apply(clean_numeric_value)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 重新计算 north_money 和 south_money（确保使用清理后的数值）
        if 'hgt' in df.columns and 'sgt' in df.columns:
            df['north_money'] = df['hgt'].fillna(0) + df['sgt'].fillna(0)
        if 'ggt_ss' in df.columns and 'ggt_sz' in df.columns:
            df['south_money'] = df['ggt_ss'].fillna(0) + df['ggt_sz'].fillna(0)

        # 最新一天数据
        latest = df.iloc[0]
        
        # 🔑 安全转换函数：从 DataFrame 中安全提取数值
        def safe_float(value, default=0.0):
            """安全转换为浮点数，处理可能的格式错误"""
            if value is None or pd.isna(value):
                return default
            try:
                # 如果已经是数值类型，直接返回
                if isinstance(value, (int, float)):
                    return float(value)
                # 如果是 pandas Series，取第一个值
                if isinstance(value, pd.Series):
                    value = value.iloc[0] if len(value) > 0 else default
                    if pd.isna(value):
                        return default
                    return float(value)
                # 如果是字符串，清理后转换
                if isinstance(value, str):
                    value = value.strip()
                    # 处理格式错误：移除多余的小数部分（如 "182490.64238444.93" -> "182490.64"）
                    value = re.sub(r'(\d+\.\d+)\.\d+', r'\1', value)
                    value = value.replace(',', '').replace(' ', '')
                return float(value)
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ 无法转换数值: {value} (类型: {type(value)}), 错误: {e}, 使用默认值 {default}")
                return default
        
        # 🔑 使用 .iloc[0] 确保获取单个值，而不是 Series
        hgt = safe_float(latest['hgt'] if 'hgt' in latest.index else 0)
        sgt = safe_float(latest['sgt'] if 'sgt' in latest.index else 0)
        north_money = safe_float(latest['north_money'] if 'north_money' in latest.index else 0)

        report_lines.append("【今日北向资金】")
        report_lines.append(f"  • 沪股通: {hgt/10000:.2f} 亿元")
        report_lines.append(f"  • 深股通: {sgt/10000:.2f} 亿元")
        flow_icon = "🔴" if north_money > 0 else "🟢"
        flow_text = "净流入" if north_money > 0 else "净流出"
        report_lines.append(f"  • 北向合计: {flow_icon} {abs(north_money)/10000:.2f} 亿元 ({flow_text})")

        # 近N日统计
        if len(df) >= 5:
            # 🔑 直接使用清理后的数值列（已经是 float 类型）
            recent_5 = df.head(5)['north_money'].sum()
            report_lines.append("")
            report_lines.append("【近期趋势】")
            report_lines.append(f"  • 近5日累计: {recent_5/10000:.2f} 亿元")

            if len(df) >= 10:
                recent_10 = df.head(10)['north_money'].sum()
                report_lines.append(f"  • 近10日累计: {recent_10/10000:.2f} 亿元")

            # 连续流入/流出天数
            consecutive = 0
            direction = "流入" if north_money > 0 else "流出"
            for _, row in df.iterrows():
                # 🔑 直接使用清理后的数值（已经是 float 类型）
                row_north_money = float(row['north_money']) if pd.notna(row['north_money']) else 0.0
                if (direction == "流入" and row_north_money > 0) or \
                   (direction == "流出" and row_north_money < 0):
                    consecutive += 1
                else:
                    break
            if consecutive > 1:
                report_lines.append(f"  • 连续{direction}: {consecutive} 天")

        # 资金情绪判断
        report_lines.append("")
        report_lines.append("【资金情绪】")
        if north_money > 5000000000:  # 50亿以上
            sentiment = "外资大幅加仓 🔥"
        elif north_money > 2000000000:  # 20亿以上
            sentiment = "外资积极流入 📈"
        elif north_money > 0:
            sentiment = "外资小幅流入 📊"
        elif north_money > -2000000000:
            sentiment = "外资小幅流出 📉"
        elif north_money > -5000000000:
            sentiment = "外资持续流出 ⚠️"
        else:
            sentiment = "外资大幅撤离 🔴"
        report_lines.append(f"  • {sentiment}")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"北向资金分析失败: {e}")
        return f"❌ 北向资金分析失败: {e}"


async def get_margin_trading(trade_date: str, lookback_days: int = 10) -> str:
    """
    获取两融余额分析

    Args:
        trade_date: 交易日期 (YYYY-MM-DD)
        lookback_days: 回看天数

    Returns:
        两融余额分析报告
    """
    provider = _get_tushare_provider()

    try:
        trade_date_clean = trade_date.replace('-', '')
        end_date = datetime.strptime(trade_date_clean, '%Y%m%d')
        start_date = end_date - timedelta(days=lookback_days + 10)

        df = await provider.get_margin_detail(
            start_date=start_date.strftime('%Y%m%d'),
            end_date=trade_date_clean
        )

        report_lines = [
            "",
            "📊 两融余额分析",
            "=" * 50,
            f"📅 日期: {trade_date}",
            "",
        ]

        if df is None or df.empty:
            report_lines.append("⚠️ 暂无两融数据（可能需要更高的 Tushare 积分）")
            return "\n".join(report_lines)

        # 按日期排序，汇总沪深两市
        df = df.sort_values('trade_date', ascending=False)
        latest_date = df.iloc[0]['trade_date']
        latest_data = df[df['trade_date'] == latest_date]

        # 汇总数据
        rzye = latest_data['rzye'].sum() / 100000000  # 融资余额（亿元）
        rqye = latest_data['rqye'].sum() / 100000000  # 融券余额（亿元）
        rzrqye = latest_data['rzrqye'].sum() / 100000000 if 'rzrqye' in latest_data.columns else rzye + rqye

        report_lines.append("【今日两融余额】")
        report_lines.append(f"  • 融资余额: {rzye:.2f} 亿元")
        report_lines.append(f"  • 融券余额: {rqye:.2f} 亿元")
        report_lines.append(f"  • 两融余额: {rzrqye:.2f} 亿元")

        # 计算变化
        unique_dates = df['trade_date'].unique()
        if len(unique_dates) >= 2:
            prev_date = unique_dates[1]
            prev_data = df[df['trade_date'] == prev_date]
            prev_rzye = prev_data['rzye'].sum() / 100000000
            change = rzye - prev_rzye
            change_icon = "🔴" if change > 0 else "🟢"
            change_text = "增加" if change > 0 else "减少"
            report_lines.append(f"  • 融资变化: {change_icon} {abs(change):.2f} 亿元 ({change_text})")

        # 近期趋势
        if len(unique_dates) >= 5:
            report_lines.append("")
            report_lines.append("【近期趋势】")
            first_date_data = df[df['trade_date'] == unique_dates[-1]]
            first_rzye = first_date_data['rzye'].sum() / 100000000
            total_change = rzye - first_rzye
            report_lines.append(f"  • 近{len(unique_dates)}日融资变化: {total_change:.2f} 亿元")

        # 杠杆情绪判断
        report_lines.append("")
        report_lines.append("【杠杆情绪】")
        if rzye > 17000:
            sentiment = "杠杆资金活跃 🔥"
        elif rzye > 15000:
            sentiment = "杠杆资金正常 📊"
        elif rzye > 13000:
            sentiment = "杠杆资金谨慎 📉"
        else:
            sentiment = "杠杆资金低迷 ❄️"
        report_lines.append(f"  • {sentiment}")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"两融余额分析失败: {e}")
        return f"❌ 两融余额分析失败: {e}"


async def get_limit_stats(trade_date: str) -> str:
    """
    获取涨跌停统计和涨跌家数分析

    Args:
        trade_date: 交易日期 (YYYY-MM-DD)

    Returns:
        涨跌停和涨跌家数分析报告
    """
    provider = _get_tushare_provider()

    try:
        trade_date_clean = trade_date.replace('-', '')

        # 获取最新可用交易日
        actual_date = await _get_latest_trade_date(trade_date)
        actual_date_formatted = f"{actual_date[:4]}-{actual_date[4:6]}-{actual_date[6:8]}"

        report_lines = [
            "",
            "📈 涨跌停与涨跌家数分析",
            "=" * 50,
            f"📅 日期: {actual_date_formatted}",
            "",
        ]

        # 获取涨跌家数统计
        stats = await provider.get_daily_stats(actual_date)

        if stats:
            report_lines.append("【涨跌家数】")
            report_lines.append(f"  • 上涨: {stats['up_count']} 家 ({stats['up_ratio']:.1f}%)")
            report_lines.append(f"  • 下跌: {stats['down_count']} 家 ({stats['down_ratio']:.1f}%)")
            report_lines.append(f"  • 平盘: {stats['flat_count']} 家")
            report_lines.append(f"  • 涨跌比: {stats['up_count']}:{stats['down_count']}")

            report_lines.append("")
            report_lines.append("【涨跌停统计】")
            report_lines.append(f"  • 涨停: {stats['limit_up']} 家")
            report_lines.append(f"  • 跌停: {stats['limit_down']} 家")

            report_lines.append("")
            report_lines.append("【涨跌幅分布】")
            report_lines.append(f"  • 涨幅>5%: {stats['up_gt5']} 家")
            report_lines.append(f"  • 涨幅3-5%: {stats['up_3_5']} 家")
            report_lines.append(f"  • 跌幅>5%: {stats['down_gt5']} 家")
            report_lines.append(f"  • 跌幅3-5%: {stats['down_3_5']} 家")

            # 市场情绪判断
            report_lines.append("")
            report_lines.append("【市场情绪】")
            up_ratio = stats['up_ratio']
            if up_ratio > 70:
                sentiment = "极度乐观 🔥"
            elif up_ratio > 55:
                sentiment = "偏向乐观 📈"
            elif up_ratio > 45:
                sentiment = "中性震荡 📊"
            elif up_ratio > 30:
                sentiment = "偏向悲观 📉"
            else:
                sentiment = "极度悲观 ❄️"
            report_lines.append(f"  • {sentiment} (涨跌比 {stats['up_count']}:{stats['down_count']})")

            # 赚钱效应
            profit_stocks = stats['up_gt5'] + stats['up_3_5']
            loss_stocks = stats['down_gt5'] + stats['down_3_5']
            if profit_stocks > loss_stocks * 2:
                effect = "赚钱效应强 💰"
            elif profit_stocks > loss_stocks:
                effect = "赚钱效应一般 📊"
            elif loss_stocks > profit_stocks * 2:
                effect = "亏钱效应强 ⚠️"
            else:
                effect = "亏钱效应一般 📉"
            report_lines.append(f"  • {effect}")
        else:
            report_lines.append("⚠️ 暂无涨跌家数数据")

        # 尝试获取涨跌停详情
        limit_df = await provider.get_limit_list(actual_date)
        if limit_df is not None and not limit_df.empty:
            limit_up_df = limit_df[limit_df['limit'] == 'U']
            limit_down_df = limit_df[limit_df['limit'] == 'D']

            if not limit_up_df.empty:
                report_lines.append("")
                report_lines.append("【涨停详情】")
                report_lines.append(f"  • 涨停家数: {len(limit_up_df)} 家")
                # 连板统计
                if 'up_stat' in limit_up_df.columns:
                    multi_board = limit_up_df[limit_up_df['up_stat'].str.contains('2|3|4|5|6|7|8|9', na=False)]
                    if len(multi_board) > 0:
                        report_lines.append(f"  • 连板: {len(multi_board)} 家")

            if not limit_down_df.empty:
                report_lines.append(f"  • 跌停家数: {len(limit_down_df)} 家")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"涨跌停统计失败: {e}")
        return f"❌ 涨跌停统计失败: {e}"


async def get_index_technical(trade_date: str, lookback_days: int = 60) -> str:
    """
    获取指数技术指标分析（MACD, RSI, KDJ）

    Args:
        trade_date: 交易日期 (YYYY-MM-DD)
        lookback_days: 回看天数

    Returns:
        指数技术指标分析报告
    """
    provider = _get_tushare_provider()

    try:
        trade_date_clean = trade_date.replace('-', '')
        end_date = datetime.strptime(trade_date_clean, '%Y%m%d')
        start_date = end_date - timedelta(days=lookback_days + 30)

        report_lines = [
            "",
            "📉 指数技术指标分析",
            "=" * 50,
            f"📅 日期: {trade_date}",
            "",
        ]

        # 分析上证指数的技术指标
        index_code = '000001.SH'
        index_name = '上证指数'

        df = await provider.get_index_daily(
            ts_code=index_code,
            start_date=start_date.strftime('%Y%m%d'),
            end_date=trade_date_clean
        )

        if df is None or len(df) < 30:
            report_lines.append("⚠️ 数据不足，无法计算技术指标")
            return "\n".join(report_lines)

        df = df.sort_values('trade_date').reset_index(drop=True)

        # 计算技术指标
        close = df['close']

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd = (dif - dea) * 2

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # KDJ
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        rsv = (close - low_min) / (high_max - low_min) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d

        # 获取最新值
        latest_dif = dif.iloc[-1]
        latest_dea = dea.iloc[-1]
        latest_macd = macd.iloc[-1]
        latest_rsi = rsi.iloc[-1]
        latest_k = k.iloc[-1]
        latest_d = d.iloc[-1]
        latest_j = j.iloc[-1]

        report_lines.append(f"【{index_name} 技术指标】")
        report_lines.append("")

        # MACD 分析
        report_lines.append("📊 MACD 指标:")
        report_lines.append(f"  • DIF: {latest_dif:.2f}")
        report_lines.append(f"  • DEA: {latest_dea:.2f}")
        report_lines.append(f"  • MACD柱: {latest_macd:.2f}")

        macd_signal = ""
        if latest_dif > latest_dea:
            if latest_dif > 0:
                macd_signal = "多头趋势，DIF在零轴上方 📈"
            else:
                macd_signal = "底部金叉形成，待确认 🔄"
        else:
            if latest_dif < 0:
                macd_signal = "空头趋势，DIF在零轴下方 📉"
            else:
                macd_signal = "顶部死叉形成，注意风险 ⚠️"
        report_lines.append(f"  • 信号: {macd_signal}")

        # RSI 分析
        report_lines.append("")
        report_lines.append("📊 RSI 指标:")
        report_lines.append(f"  • RSI(14): {latest_rsi:.2f}")

        if latest_rsi > 80:
            rsi_signal = "超买区域，注意回调风险 🔴"
        elif latest_rsi > 70:
            rsi_signal = "偏强，接近超买 📈"
        elif latest_rsi > 50:
            rsi_signal = "多方占优 📊"
        elif latest_rsi > 30:
            rsi_signal = "空方占优 📉"
        elif latest_rsi > 20:
            rsi_signal = "偏弱，接近超卖 📉"
        else:
            rsi_signal = "超卖区域，关注反弹机会 🟢"
        report_lines.append(f"  • 信号: {rsi_signal}")

        # KDJ 分析
        report_lines.append("")
        report_lines.append("📊 KDJ 指标:")
        report_lines.append(f"  • K: {latest_k:.2f}")
        report_lines.append(f"  • D: {latest_d:.2f}")
        report_lines.append(f"  • J: {latest_j:.2f}")

        if latest_k > latest_d and latest_j > 80:
            kdj_signal = "高位金叉，注意回调 ⚠️"
        elif latest_k > latest_d:
            kdj_signal = "金叉向上，多头信号 📈"
        elif latest_k < latest_d and latest_j < 20:
            kdj_signal = "低位死叉，关注反弹 🔄"
        else:
            kdj_signal = "死叉向下，空头信号 📉"
        report_lines.append(f"  • 信号: {kdj_signal}")

        # 综合判断
        report_lines.append("")
        report_lines.append("【技术面综合】")
        bull_signals = 0
        bear_signals = 0

        if latest_dif > latest_dea:
            bull_signals += 1
        else:
            bear_signals += 1

        if latest_rsi > 50:
            bull_signals += 1
        else:
            bear_signals += 1

        if latest_k > latest_d:
            bull_signals += 1
        else:
            bear_signals += 1

        if bull_signals >= 2:
            summary = f"技术面偏多 📈 ({bull_signals}/3 指标看多)"
        elif bear_signals >= 2:
            summary = f"技术面偏空 📉 ({bear_signals}/3 指标看空)"
        else:
            summary = "技术面中性 📊 (多空信号分歧)"
        report_lines.append(f"  • {summary}")

        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"指数技术指标分析失败: {e}")
        return f"❌ 指数技术指标分析失败: {e}"


# 同步包装函数
def get_north_flow_sync(trade_date: str, lookback_days: int = 10) -> str:
    """get_north_flow 的同步版本"""
    return asyncio.run(get_north_flow(trade_date, lookback_days))


def get_margin_trading_sync(trade_date: str, lookback_days: int = 10) -> str:
    """get_margin_trading 的同步版本"""
    return asyncio.run(get_margin_trading(trade_date, lookback_days))


def get_limit_stats_sync(trade_date: str) -> str:
    """get_limit_stats 的同步版本"""
    return asyncio.run(get_limit_stats(trade_date))


def get_index_technical_sync(trade_date: str, lookback_days: int = 60) -> str:
    """get_index_technical 的同步版本"""
    return asyncio.run(get_index_technical(trade_date, lookback_days))

