"""QMT 驱动的大盘与板块分析辅助函数。"""

from __future__ import annotations

import logging
from datetime import datetime
from statistics import median
from typing import Any, Dict, List, Optional

from app.core.database import get_mongo_db_sync
from app.services.data_sources.qmt_adapter import QMTAdapter

logger = logging.getLogger(__name__)

_INDEX_LABELS = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "000300.SH": "沪深300",
    "000905.SH": "中证500",
}


def _normalize_trade_date(trade_date: str) -> str:
    text = str(trade_date or "").strip()
    if not text:
        return datetime.now().strftime("%Y-%m-%d")
    text = text.split()[0].split("T")[0]
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _compact_trade_date(trade_date: str) -> str:
    return _normalize_trade_date(trade_date).replace("-", "")


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}%"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_period_pct(closes: List[float], days: int) -> Optional[float]:
    if len(closes) <= days or closes[-1] in (None, 0) or closes[-days - 1] in (None, 0):
        return None
    base = closes[-days - 1]
    if not base:
        return None
    return (closes[-1] / base - 1) * 100


def _compute_ma(closes: List[float], days: int) -> Optional[float]:
    if len(closes) < days:
        return None
    window = [value for value in closes[-days:] if value is not None]
    if len(window) < days:
        return None
    return sum(window) / len(window)


def _resolve_trend(close_price: Optional[float], ma5: Optional[float], ma20: Optional[float], ma60: Optional[float]) -> str:
    if None in (close_price, ma5, ma20, ma60):
        return "数据不足"
    if close_price > ma5 > ma20 > ma60:
        return "多头排列"
    if close_price < ma5 < ma20 < ma60:
        return "空头排列"
    return "震荡整理"


def _get_qmt_adapter() -> Optional[QMTAdapter]:
    adapter = QMTAdapter()
    if not adapter.is_available():
        return None
    return adapter


def get_market_overview_qmt_sync(trade_date: str, lookback_days: int = 60) -> str:
    adapter = _get_qmt_adapter()
    if adapter is None:
        return "❌ QMT 不可用，无法执行 QMT 大盘分析。"

    normalized_trade_date = _normalize_trade_date(trade_date)
    latest_trade_date = adapter.find_latest_trade_date() or _compact_trade_date(normalized_trade_date)
    latest_trade_date_display = _normalize_trade_date(latest_trade_date)

    report_lines = [
        "# QMT 大盘分析概览",
        f"- 请求日期: {normalized_trade_date}",
        f"- QMT 最近交易日: {latest_trade_date_display}",
        "- 分析口径: 基于 QMT 指数行情、全市场快照与成交活跃度代理指标",
        "- 缺失口径: 北向资金、两融、指数估值快照",
        "",
        "## 主要指数趋势",
    ]

    style_reference: Dict[str, Optional[float]] = {}
    for code, name in _INDEX_LABELS.items():
        items = adapter.get_kline(code, period="day", limit=max(lookback_days, 60) + 5)
        if not items:
            report_lines.append(f"- {name}: 暂无数据")
            continue

        closes = [_safe_float(item.get("close")) for item in items if _safe_float(item.get("close")) is not None]
        if len(closes) < 5:
            report_lines.append(f"- {name}: 数据不足")
            continue

        latest_close = closes[-1]
        pct_5d = _compute_period_pct(closes, 5)
        pct_20d = _compute_period_pct(closes, 20)
        ma5 = _compute_ma(closes, 5)
        ma20 = _compute_ma(closes, 20)
        ma60 = _compute_ma(closes, 60)
        trend = _resolve_trend(latest_close, ma5, ma20, ma60)
        style_reference[code] = pct_20d
        report_lines.append(
            f"- {name}({code}): {latest_close:.2f} | 5日 {_format_pct(pct_5d)} | 20日 {_format_pct(pct_20d)} | {trend}"
        )

    quotes = adapter.get_realtime_quotes() or {}
    pct_values = [
        _safe_float(item.get("pct_chg"))
        for item in quotes.values()
        if _safe_float(item.get("pct_chg")) is not None
    ]
    amount_values = [
        _safe_float(item.get("amount"))
        for item in quotes.values()
        if _safe_float(item.get("amount")) is not None
    ]

    report_lines.append("")
    report_lines.append("## 市场快照代理指标")
    if pct_values:
        up_count = sum(1 for value in pct_values if value > 0)
        down_count = sum(1 for value in pct_values if value < 0)
        flat_count = len(pct_values) - up_count - down_count
        strong_count = sum(1 for value in pct_values if value >= 3)
        weak_count = sum(1 for value in pct_values if value <= -3)
        median_pct = median(pct_values)
        total_amount = sum(value for value in amount_values if value is not None)
        report_lines.extend([
            f"- 上涨家数代理: {up_count}",
            f"- 下跌家数代理: {down_count}",
            f"- 平盘家数代理: {flat_count}",
            f"- 强势股占比代理(>=3%): {strong_count}/{len(pct_values)}",
            f"- 弱势股占比代理(<=-3%): {weak_count}/{len(pct_values)}",
            f"- 涨跌幅中位数代理: {_format_pct(median_pct)}",
            f"- 全市场成交额代理: {total_amount / 100000000:.2f} 亿元" if total_amount else "- 全市场成交额代理: 0.00 亿元",
        ])
    else:
        report_lines.append("- 当前无法从 QMT 获取有效全市场快照，市场扩散度代理指标缺失")

    report_lines.append("")
    report_lines.append("## 涨跌停统计（QMT 快照代理）")
    limit_stats = adapter.get_limit_stats(trade_date=normalized_trade_date)
    if limit_stats:
        source_tag = "实时快照" if limit_stats.get("source") == "realtime" else "历史日线回算"
        report_lines.extend([
            f"- 涨停: {limit_stats['up_limit']} 家",
            f"- 跌停: {limit_stats['down_limit']} 家",
            f"- 数据来源: {source_tag}",
        ])
        if limit_stats["up_limit_stocks"]:
            names = ", ".join(f"{n}({c})" for c, n, _ in limit_stats["up_limit_stocks"][:10])
            report_lines.append(f"- 涨停股（前10）: {names}")
        if limit_stats["down_limit_stocks"]:
            names = ", ".join(f"{n}({c})" for c, n, _ in limit_stats["down_limit_stocks"][:10])
            report_lines.append(f"- 跌停股（前10）: {names}")
    else:
        report_lines.append("- 暂无涨跌停统计数据")

    report_lines.append("")
    report_lines.append("## 成交额排名（QMT 快照代理）")
    amount_ranking = adapter.get_amount_ranking(10, trade_date=normalized_trade_date)
    if amount_ranking:
        for i, row in enumerate(amount_ranking, 1):
            amt_yi = row["amount"] / 100000000 if row["amount"] else 0
            pct_str = f"{row['pct_chg']:+.2f}%" if row["pct_chg"] is not None else "-"
            report_lines.append(f"  {i:2d}. {row['name']}({row['code']}): {amt_yi:.2f} 亿 | {pct_str}")
    else:
        report_lines.append("- 暂无成交额排名数据")

    report_lines.append("")
    report_lines.append("## 风格与结构判断")
    hs300_20d = style_reference.get("000300.SH")
    zz500_20d = style_reference.get("000905.SH")
    cyb_20d = style_reference.get("399006.SZ")
    if hs300_20d is not None and zz500_20d is not None:
        if zz500_20d > hs300_20d:
            report_lines.append(f"- 中小盘相对占优: 中证500 20日 {_format_pct(zz500_20d)} 强于沪深300 20日 {_format_pct(hs300_20d)}")
        elif hs300_20d > zz500_20d:
            report_lines.append(f"- 大盘核心资产相对占优: 沪深300 20日 {_format_pct(hs300_20d)} 强于中证500 20日 {_format_pct(zz500_20d)}")
        else:
            report_lines.append("- 大小盘风格接近，暂未出现明显切换")
    if cyb_20d is not None and hs300_20d is not None:
        if cyb_20d > hs300_20d:
            report_lines.append(f"- 成长风格活跃: 创业板 20日 {_format_pct(cyb_20d)} 强于沪深300 {_format_pct(hs300_20d)}")
        else:
            report_lines.append(f"- 成长风格未显著占优: 创业板 20日 {_format_pct(cyb_20d)}，沪深300 {_format_pct(hs300_20d)}")

    report_lines.append("")
    report_lines.append("## 使用建议")
    report_lines.append("- 本报告适合用于趋势、扩散、活跃度与风格切换判断，不适合替代北向资金或两融等官方统计口径。")
    report_lines.append("- 当 Tushare 不可用但 QMT 可用时，应优先依据该报告进行交易盘面型大盘分析。")
    return "\n".join(report_lines)


def get_sector_analysis_qmt_sync(ticker: str, trade_date: str, lookback_days: int = 20, top_n: int = 10) -> str:
    adapter = _get_qmt_adapter()
    if adapter is None:
        return "❌ QMT 不可用，无法执行 QMT 板块分析。"

    code = "".join(ch for ch in str(ticker) if ch.isdigit()).zfill(6)
    if len(code) != 6:
        return f"❌ 无效股票代码: {ticker}"

    db = get_mongo_db_sync()
    if db is None:
        return "❌ 无法连接数据库，无法获取行业映射。"

    target_doc = db.stock_basic_info.find_one(
        {"code": code},
        sort=[("updated_at", -1)],
    )
    if not target_doc:
        return f"❌ 本地未找到 {code} 的基础信息，无法构建 QMT 板块分析。"

    industry = target_doc.get("industry") or ""
    target_name = target_doc.get("name") or code
    if not industry or industry == "未知":
        return f"❌ {code} 缺少可用行业映射，当前 QMT 板块分析依赖本地 stock_basic_info 的行业字段。"

    peer_cursor = db.stock_basic_info.find(
        {"industry": industry, "code": {"$exists": True}},
        {"code": 1, "name": 1, "industry": 1},
    ).limit(max(top_n * 3, 20))
    peers = list(peer_cursor)
    peer_codes = []
    seen_codes = set()
    for doc in peers:
        peer_code = str(doc.get("code", "")).zfill(6)
        if len(peer_code) != 6 or peer_code in seen_codes:
            continue
        seen_codes.add(peer_code)
        peer_codes.append({"code": peer_code, "name": doc.get("name") or peer_code})

    if not peer_codes:
        return f"❌ 行业 {industry} 没有可用成分股，无法进行 QMT 板块分析。"

    quotes = adapter.get_realtime_quotes() or {}
    rows: List[Dict[str, Any]] = []
    for peer in peer_codes:
        items = adapter.get_kline(peer["code"], period="day", limit=max(lookback_days, 20) + 5)
        if not items:
            continue
        closes = [_safe_float(item.get("close")) for item in items if _safe_float(item.get("close")) is not None]
        if len(closes) < 5:
            continue
        period_pct = _compute_period_pct(closes, min(lookback_days, len(closes) - 2))
        latest_close = closes[-1]
        quote = quotes.get(peer["code"], {})
        amount = _safe_float(quote.get("amount"))
        intraday_pct = _safe_float(quote.get("pct_chg"))
        rows.append({
            "code": peer["code"],
            "name": peer["name"],
            "period_pct": period_pct,
            "intraday_pct": intraday_pct,
            "amount": amount,
            "close": latest_close,
        })

    if not rows:
        return f"❌ 行业 {industry} 未获取到足够的 QMT 行情数据。"

    valid_period = [row["period_pct"] for row in rows if row["period_pct"] is not None]
    rising_count = sum(1 for value in valid_period if value > 0)
    avg_period = sum(valid_period) / len(valid_period) if valid_period else None
    median_period = median(valid_period) if valid_period else None
    leaders = sorted(
        [row for row in rows if row["period_pct"] is not None],
        key=lambda item: item["period_pct"],
        reverse=True,
    )[:top_n]
    active_names = sorted(
        [row for row in rows if row["amount"] is not None],
        key=lambda item: item["amount"],
        reverse=True,
    )[:min(5, len(rows))]

    report_lines = [
        "# QMT 板块分析概览",
        f"- 目标股票: {target_name}({code})",
        f"- 行业映射: {industry}",
        f"- 分析日期: {_normalize_trade_date(trade_date)}",
        "- 行情口径: QMT K线 + QMT 实时快照",
        "- 行业口径: 本地 stock_basic_info 行业字段",
        "- 缺失口径: 同花顺板块资金流、概念板块官方排名",
        "",
        "## 板块整体强弱",
        f"- 可分析成分股数: {len(rows)}",
        f"- 上涨成分占比(周期口径): {rising_count}/{len(valid_period)}" if valid_period else "- 上涨成分占比: 数据不足",
        f"- 周期平均涨跌幅: {_format_pct(avg_period)}" if avg_period is not None else "- 周期平均涨跌幅: 数据不足",
        f"- 周期中位涨跌幅: {_format_pct(median_period)}" if median_period is not None else "- 周期中位涨跌幅: 数据不足",
        "",
        "## 龙头与扩散",
    ]

    if leaders:
        for row in leaders[:top_n]:
            report_lines.append(
                f"- {row['name']}({row['code']}): 周期 {_format_pct(row['period_pct'])} | 最新价 {row['close']:.2f}"
            )
    else:
        report_lines.append("- 暂无可用龙头强度数据")

    report_lines.append("")
    report_lines.append("## 活跃度代理")
    if active_names:
        for row in active_names:
            amount_text = f"{row['amount'] / 100000000:.2f} 亿元" if row['amount'] else "-"
            report_lines.append(
                f"- {row['name']}({row['code']}): 成交额代理 {amount_text} | 当日涨跌 {_format_pct(row['intraday_pct'])}"
            )
    else:
        report_lines.append("- 暂无可用成交活跃度快照")

    report_lines.append("")
    report_lines.append("## 解释口径")
    report_lines.append("- 该分析适合判断行业内部强弱分层、龙头带动和扩散程度。")
    report_lines.append("- 该分析不等价于同花顺板块资金流统计，不能直接替代 Tushare 的板块资金工具。")
    return "\n".join(report_lines)


# ==================== 增强版板块分析 ====================

def get_sector_analysis_qmt_enhanced(ticker: str, trade_date: str, lookback_days: int = 20, top_n: int = 10) -> str:
    """QMT 增强版板块分析：增加板块资金流向代理、板块强弱对比、技术指标。"""
    adapter = _get_qmt_adapter()
    if adapter is None:
        return "❌ QMT 不可用，无法执行 QMT 板块分析。"

    code = "".join(ch for ch in str(ticker) if ch.isdigit()).zfill(6)
    if len(code) != 6:
        return f"❌ 无效股票代码: {ticker}"

    db = get_mongo_db_sync()
    if db is None:
        return "❌ 无法连接数据库，无法获取行业映射。"

    target_doc = db.stock_basic_info.find_one(
        {"code": code},
        sort=[("updated_at", -1)],
    )
    if not target_doc:
        return f"❌ 本地未找到 {code} 的基础信息，无法构建 QMT 板块分析。"

    industry = target_doc.get("industry") or ""
    target_name = target_doc.get("name") or code
    if not industry or industry == "未知":
        return f"❌ {code} 缺少可用行业映射，当前 QMT 板块分析依赖本地 stock_basic_info 的行业字段。"

    peer_cursor = db.stock_basic_info.find(
        {"industry": industry, "code": {"$exists": True}},
        {"code": 1, "name": 1, "industry": 1},
    ).limit(max(top_n * 3, 30))
    peers = list(peer_cursor)
    peer_codes = []
    seen_codes = set()
    for doc in peers:
        peer_code = str(doc.get("code", "")).zfill(6)
        if len(peer_code) != 6 or peer_code in seen_codes:
            continue
        seen_codes.add(peer_code)
        peer_codes.append({"code": peer_code, "name": doc.get("name") or peer_code})

    if not peer_codes:
        return f"❌ 行业 {industry} 没有可用成分股，无法进行 QMT 板块分析。"

    quotes = adapter.get_realtime_quotes() or {}
    rows: List[Dict[str, Any]] = []
    for peer in peer_codes:
        items = adapter.get_kline(peer["code"], period="day", limit=max(lookback_days, 20) + 5)
        if not items:
            continue
        closes = [_safe_float(item.get("close")) for item in items if _safe_float(item.get("close")) is not None]
        if len(closes) < 5:
            continue
        period_pct = _compute_period_pct(closes, min(lookback_days, len(closes) - 2))
        latest_close = closes[-1]
        quote = quotes.get(peer["code"], {})
        amount = _safe_float(quote.get("amount"))
        intraday_pct = _safe_float(quote.get("pct_chg"))
        turnover = _safe_float(quote.get("turnover"))

        # 计算 RSI
        rsi = None
        if len(closes) >= 15:
            gains, losses = [], []
            for i in range(-14, 0):
                diff = closes[i] - closes[i - 1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14
            rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100

        # 计算 MACD
        macd_r = _compute_macd(closes)

        # 计算量比（今日成交额 / 近5日均量）
        vol_ratio = None
        if amount and len(items) >= 5:
            recent_amounts = []
            for item in items[-5:]:
                a = _safe_float(item.get("amount"))
                if a:
                    recent_amounts.append(a)
            if recent_amounts:
                avg_amount = sum(recent_amounts) / len(recent_amounts)
                if avg_amount > 0:
                    vol_ratio = amount / avg_amount

        rows.append({
            "code": peer["code"],
            "name": peer["name"],
            "period_pct": period_pct,
            "intraday_pct": intraday_pct,
            "amount": amount,
            "close": latest_close,
            "turnover": turnover,
            "rsi": rsi,
            "macd": macd_r.get("macd"),
            "macd_hist": macd_r.get("histogram"),
            "vol_ratio": vol_ratio,
        })

    if not rows:
        return f"❌ 行业 {industry} 未获取到足够的 QMT 行情数据。"

    valid_period = [row["period_pct"] for row in rows if row["period_pct"] is not None]
    rising_count = sum(1 for v in valid_period if v > 0)
    avg_period = sum(valid_period) / len(valid_period) if valid_period else None
    median_period = median(valid_period) if valid_period else None
    leaders = sorted(
        [row for row in rows if row["period_pct"] is not None],
        key=lambda item: item["period_pct"],
        reverse=True,
    )[:top_n]
    active_names = sorted(
        [row for row in rows if row["amount"] is not None],
        key=lambda item: item["amount"],
        reverse=True,
    )[:min(5, len(rows))]

    # === 板块资金流向代理 ===
    total_amount = sum(row["amount"] for row in rows if row["amount"] is not None)
    rising_amount = sum(row["amount"] for row in rows if row["amount"] is not None and (row["intraday_pct"] or 0) > 0)
    falling_amount = sum(row["amount"] for row in rows if row["amount"] is not None and (row["intraday_pct"] or 0) < 0)

    # === 板块强弱对比（与大盘对比） ===
    sh_items = adapter.get_kline("000001.SH", period="day", limit=max(lookback_days, 20) + 5)
    sh_pct = None
    if sh_items:
        sh_closes = [_safe_float(item.get("close")) for item in sh_items if _safe_float(item.get("close")) is not None]
        if len(sh_closes) > lookback_days:
            sh_pct = _compute_period_pct(sh_closes, lookback_days)

    report_lines = [
        "# QMT 板块分析概览（增强版）",
        f"- 目标股票: {target_name}({code})",
        f"- 行业映射: {industry}",
        f"- 分析日期: {_normalize_trade_date(trade_date)}",
        "- 行情口径: QMT K线 + QMT 实时快照",
        "- 行业口径: 本地 stock_basic_info 行业字段",
        "- 缺失口径: 同花顺板块资金流、概念板块官方排名",
        "",
        "## 板块整体强弱",
        f"- 可分析成分股数: {len(rows)}",
        f"- 上涨成分占比(周期口径): {rising_count}/{len(valid_period)}" if valid_period else "- 上涨成分占比: 数据不足",
        f"- 周期平均涨跌幅: {_format_pct(avg_period)}" if avg_period is not None else "- 周期平均涨跌幅: 数据不足",
        f"- 周期中位涨跌幅: {_format_pct(median_period)}" if median_period is not None else "- 周期中位涨跌幅: 数据不足",
    ]

    # 板块 vs 大盘
    if avg_period is not None and sh_pct is not None:
        excess = avg_period - sh_pct
        if excess > 2:
            report_lines.append(f"- 板块相对大盘超额收益: {_format_pct(excess)} → 板块明显跑赢大盘")
        elif excess < -2:
            report_lines.append(f"- 板块相对大盘超额收益: {_format_pct(excess)} → 板块明显跑输大盘")
        else:
            report_lines.append(f"- 板块相对大盘超额收益: {_format_pct(excess)} → 板块与大盘基本同步")

    report_lines.extend([
        "",
        "## 龙头与扩散",
    ])

    if leaders:
        for row in leaders[:top_n]:
            rsi_str = f"RSI={row['rsi']:.0f}" if row["rsi"] else ""
            macd_str = f"MACD={'多' if (row['macd_hist'] or 0) > 0 else '空'}" if row["macd_hist"] is not None else ""
            report_lines.append(
                f"- {row['name']}({row['code']}): 周期 {_format_pct(row['period_pct'])} | 最新价 {row['close']:.2f} {rsi_str} {macd_str}"
            )
    else:
        report_lines.append("- 暂无可用龙头强度数据")

    # === 板块资金流向代理 ===
    report_lines.append("")
    report_lines.append("## 板块资金流向代理")
    if total_amount > 0:
        net_flow_pct = (rising_amount - falling_amount) / total_amount * 100
        flow_label = "净流入" if net_flow_pct > 0 else "净流出"
        report_lines.extend([
            f"- 板块总成交额: {total_amount / 100000000:.2f} 亿元",
            f"- 上涨股成交额: {rising_amount / 100000000:.2f} 亿元",
            f"- 下跌股成交额: {falling_amount / 100000000:.2f} 亿元",
            f"- 资金流向代理: {flow_label} ({_format_pct(net_flow_pct)})",
        ])
        if net_flow_pct > 10:
            report_lines.append("- 资金明显流入该板块，市场关注度较高")
        elif net_flow_pct < -10:
            report_lines.append("- 资金明显流出该板块，需警惕风险")
    else:
        report_lines.append("- 暂无可用成交额数据")

    # === 活跃度代理（增强：量比） ===
    report_lines.append("")
    report_lines.append("## 活跃度代理")
    if active_names:
        for row in active_names:
            amount_text = f"{row['amount'] / 100000000:.2f} 亿元" if row['amount'] else "-"
            vol_ratio_text = f"量比={row['vol_ratio']:.1f}" if row['vol_ratio'] else ""
            report_lines.append(
                f"- {row['name']}({row['code']}): 成交额 {amount_text} | 当日涨跌 {_format_pct(row['intraday_pct'])} {vol_ratio_text}"
            )
    else:
        report_lines.append("- 暂无可用成交活跃度快照")

    # === 技术指标汇总 ===
    report_lines.append("")
    report_lines.append("## 板块技术指标汇总")
    rsi_values = [row["rsi"] for row in rows if row["rsi"] is not None]
    macd_bull = sum(1 for row in rows if (row["macd_hist"] or 0) > 0)
    macd_bear = sum(1 for row in rows if (row["macd_hist"] or 0) < 0)
    if rsi_values:
        avg_rsi = sum(rsi_values) / len(rsi_values)
        rsi_label = "超买" if avg_rsi > 70 else "偏强" if avg_rsi > 55 else "中性" if avg_rsi > 45 else "偏弱" if avg_rsi > 30 else "超卖"
        report_lines.extend([
            f"- 板块平均 RSI(14): {avg_rsi:.1f} ({rsi_label})",
            f"- MACD 多头: {macd_bull} | MACD 空头: {macd_bear}",
        ])
    else:
        report_lines.append("- 技术指标数据不足")

    report_lines.append("")
    report_lines.append("## 解释口径")
    report_lines.append("- 该分析适合判断行业内部强弱分层、龙头带动、资金流向和扩散程度。")
    report_lines.append("- 资金流向代理基于上涨/下跌股的成交额拆分，不等价于同花顺板块资金流统计。")
    report_lines.append("- 量比基于今日成交额与近5日均量的比值，>1.5 为放量，<0.7 为缩量。")
    return "\n".join(report_lines)


# ==================== 涨跌停统计（QMT 降级） ====================

def get_limit_stats_qmt_sync(trade_date: str) -> str:
    """QMT 降级：统计涨跌停和涨跌家数（盘中用实时快照，盘后用历史日线）。"""
    adapter = _get_qmt_adapter()
    if adapter is None:
        return "❌ QMT 不可用，无法获取涨跌停统计。"

    stats = adapter.get_limit_stats(trade_date=trade_date)
    if stats is None:
        return "⚠️ QMT 未返回涨跌停统计数据。"

    source_tag = "实时快照" if stats.get("source") == "realtime" else "历史日线回算"
    lines = [
        f"📊 涨跌停与涨跌家数统计（基于 QMT {source_tag}，Tushare 不可用时的降级数据）",
        "",
        f"- 涨停: {stats['up_limit']} 家",
        f"- 跌停: {stats['down_limit']} 家",
        f"- 上涨: {stats['rising']} 家",
        f"- 下跌: {stats['falling']} 家",
        f"- 平盘: {stats['flat']} 家",
        f"- 合计: {stats['total']} 家",
        "",
    ]

    if stats["up_limit_stocks"]:
        lines.append("## 涨停股（前20）")
        for code, name, pct in stats["up_limit_stocks"]:
            lines.append(f"- {name}({code}): {pct:+.2f}%")
        lines.append("")

    if stats["down_limit_stocks"]:
        lines.append("## 跌停股（前20）")
        for code, name, pct in stats["down_limit_stocks"]:
            lines.append(f"- {name}({code}): {pct:+.2f}%")
        lines.append("")

    lines.append("## 口径说明")
    lines.append("- 涨跌停判断基于 QMT 行情数据，盘中用实时快照涨跌停价，盘后用历史日线回算，非交易所官方统计。")
    lines.append("- 科创板/创业板涨跌幅阈值 20%，北交所 30%，主板 10%。")

    return "\n".join(lines)


# ==================== 成交额排名（QMT 降级） ====================

def get_amount_ranking_qmt_sync(top_n: int = 20, trade_date: Optional[str] = None) -> str:
    """QMT 降级：成交额排名（盘中用实时快照，盘后用历史日线）。"""
    adapter = _get_qmt_adapter()
    if adapter is None:
        return "❌ QMT 不可用，无法获取成交额排名。"

    ranking = adapter.get_amount_ranking(top_n, trade_date=trade_date)
    if ranking is None:
        return "⚠️ QMT 未返回成交额排名数据。"

    lines = [
        "📊 成交额排名（基于 QMT 行情数据，Tushare 不可用时的降级数据）",
        "",
    ]

    for i, row in enumerate(ranking, 1):
        amt_yi = row["amount"] / 100000000 if row["amount"] else 0
        pct_str = f"{row['pct_chg']:+.2f}%" if row["pct_chg"] is not None else "-"
        lines.append(f"{i:2d}. {row['name']}({row['code']}): 成交额 {amt_yi:.2f} 亿 | 涨跌 {pct_str}")

    lines.append("")
    lines.append("## 口径说明")
    lines.append("- 成交额基于 QMT 行情数据，盘中为实时快照，盘后为历史日线。")

    return "\n".join(lines)


# ==================== MACD / KDJ 计算 ====================

def _compute_macd(
    closes: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Dict[str, Optional[float]]:
    """计算 MACD 指标。

    Returns:
        {"macd": float, "signal": float, "histogram": float}
    """
    if len(closes) < slow + signal:
        return {"macd": None, "signal": None, "histogram": None}

    # EMA 计算
    def ema(data: List[float], period: int) -> List[float]:
        k = 2 / (period + 1)
        result = [data[0]]
        for price in data[1:]:
            result.append(price * k + result[-1] * (1 - k))
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = ema(dif, signal)
    macd_hist = [(d - e) * 2 for d, e in zip(dif, dea)]

    return {
        "macd": round(dif[-1], 4),
        "signal": round(dea[-1], 4),
        "histogram": round(macd_hist[-1], 4),
    }


def _compute_kdj(
    items: List[Dict[str, Any]],
    n: int = 9,
) -> Dict[str, Optional[float]]:
    """计算 KDJ 指标。

    Args:
        items: K线数据列表，需包含 high/low/close 字段

    Returns:
        {"k": float, "d": float, "j": float}
    """
    if len(items) < n:
        return {"k": None, "d": None, "j": None}

    k_val, d_val = 50.0, 50.0
    for i in range(n - 1, len(items)):
        window = items[i - n + 1: i + 1]
        highs = [_safe_float(w.get("high")) for w in window]
        lows = [_safe_float(w.get("low")) for w in window]
        closes_w = [_safe_float(w.get("close")) for w in window]
        if None in highs or None in lows or None in closes_w:
            continue
        hn = max(highs)
        ln = min(lows)
        cn = closes_w[-1]
        if hn == ln:
            rsv = 50.0
        else:
            rsv = (cn - ln) / (hn - ln) * 100
        k_val = 2 / 3 * k_val + 1 / 3 * rsv
        d_val = 2 / 3 * d_val + 1 / 3 * k_val

    j_val = 3 * k_val - 2 * d_val
    return {
        "k": round(k_val, 2),
        "d": round(d_val, 2),
        "j": round(j_val, 2),
    }


# ==================== 增强版大盘分析 ====================

def get_market_overview_qmt_enhanced(trade_date: str, lookback_days: int = 60) -> str:
    """QMT 增强版大盘分析：在原有基础上增加 MACD/KDJ、市场周期识别、涨跌幅分档统计。"""
    adapter = _get_qmt_adapter()
    if adapter is None:
        return "❌ QMT 不可用，无法执行 QMT 大盘分析。"

    normalized_trade_date = _normalize_trade_date(trade_date)
    latest_trade_date = adapter.find_latest_trade_date() or _compact_trade_date(normalized_trade_date)
    latest_trade_date_display = _normalize_trade_date(latest_trade_date)

    report_lines = [
        "# QMT 大盘分析概览（增强版）",
        f"- 请求日期: {normalized_trade_date}",
        f"- QMT 最近交易日: {latest_trade_date_display}",
        "- 分析口径: 基于 QMT 指数行情、全市场快照与技术指标计算",
        "- 缺失口径: 北向资金、两融、指数估值快照",
        "",
    ]

    # === 1. 主要指数趋势 + 技术指标 ===
    report_lines.append("## 主要指数趋势与技术指标")
    style_reference: Dict[str, Optional[float]] = {}
    for code, name in _INDEX_LABELS.items():
        items = adapter.get_kline(code, period="day", limit=max(lookback_days, 60) + 5)
        if not items:
            report_lines.append(f"- {name}: 暂无数据")
            continue

        closes = [_safe_float(item.get("close")) for item in items if _safe_float(item.get("close")) is not None]
        if len(closes) < 5:
            report_lines.append(f"- {name}: 数据不足")
            continue

        latest_close = closes[-1]
        pct_5d = _compute_period_pct(closes, 5)
        pct_20d = _compute_period_pct(closes, 20)
        ma5 = _compute_ma(closes, 5)
        ma20 = _compute_ma(closes, 20)
        ma60 = _compute_ma(closes, 60)
        trend = _resolve_trend(latest_close, ma5, ma20, ma60)
        style_reference[code] = pct_20d

        # MACD
        macd_result = _compute_macd(closes)
        macd_str = f"MACD={macd_result['macd']}" if macd_result["macd"] is not None else "MACD=-"

        # KDJ
        kdj_result = _compute_kdj(items)
        kdj_str = f"K={kdj_result['k']} D={kdj_result['d']} J={kdj_result['j']}" if kdj_result["k"] is not None else "KDJ=-"

        # RSI
        rsi = None
        if len(closes) >= 15:
            gains, losses = [], []
            for i in range(-14, 0):
                diff = closes[i] - closes[i - 1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14
            rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100
        rsi_str = f"RSI(14)={rsi:.1f}" if rsi is not None else "RSI=-"

        report_lines.append(
            f"- {name}({code}): {latest_close:.2f} | 5日 {_format_pct(pct_5d)} | 20日 {_format_pct(pct_20d)} | {trend}"
        )
        report_lines.append(
            f"  {macd_str} | {kdj_str} | {rsi_str}"
        )

    # === 2. 市场宽度（增强：涨跌幅分档统计） ===
    report_lines.append("")
    report_lines.append("## 市场宽度与涨跌幅分布")

    quotes = adapter.get_realtime_quotes() or {}
    pct_values = [
        _safe_float(item.get("pct_chg"))
        for item in quotes.values()
        if _safe_float(item.get("pct_chg")) is not None
    ]
    amount_values = [
        _safe_float(item.get("amount"))
        for item in quotes.values()
        if _safe_float(item.get("amount")) is not None
    ]

    if pct_values:
        up_count = sum(1 for v in pct_values if v > 0)
        down_count = sum(1 for v in pct_values if v < 0)
        flat_count = len(pct_values) - up_count - down_count
        median_pct = median(pct_values)
        total_amount = sum(v for v in amount_values if v is not None)

        # 涨跌幅分档
        buckets = {
            "涨停(≥9.9%)": 0,
            "大涨(5%~9.9%)": 0,
            "上涨(2%~5%)": 0,
            "微涨(0%~2%)": 0,
            "微跌(0%~-2%)": 0,
            "下跌(-2%~-5%)": 0,
            "大跌(-5%~-9.9%)": 0,
            "跌停(≤-9.9%)": 0,
        }
        for v in pct_values:
            if v >= 9.9:
                buckets["涨停(≥9.9%)"] += 1
            elif v >= 5:
                buckets["大涨(5%~9.9%)"] += 1
            elif v >= 2:
                buckets["上涨(2%~5%)"] += 1
            elif v > 0:
                buckets["微涨(0%~2%)"] += 1
            elif v > -2:
                buckets["微跌(0%~-2%)"] += 1
            elif v > -5:
                buckets["下跌(-2%~-5%)"] += 1
            elif v > -9.9:
                buckets["大跌(-5%~-9.9%)"] += 1
            else:
                buckets["跌停(≤-9.9%)"] += 1

        report_lines.extend([
            f"- 上涨: {up_count} | 下跌: {down_count} | 平盘: {flat_count}",
            f"- 涨跌幅中位数: {_format_pct(median_pct)}",
            f"- 全市场成交额: {total_amount / 100000000:.2f} 亿元" if total_amount else "- 全市场成交额: 0.00 亿元",
            "",
            "### 涨跌幅分档分布",
        ])
        for label, count in buckets.items():
            pct_of_total = count / len(pct_values) * 100 if pct_values else 0
            bar = "█" * int(pct_of_total / 2)
            report_lines.append(f"- {label}: {count} 家 ({pct_of_total:.1f}%) {bar}")

        # 市场宽度指标
        advance_decline_ratio = up_count / down_count if down_count > 0 else float("inf")
        breadth_pct = up_count / len(pct_values) * 100 if pct_values else 0
        report_lines.extend([
            "",
            "### 市场宽度指标",
            f"- 涨跌比: {advance_decline_ratio:.2f}",
            f"- 上涨占比: {breadth_pct:.1f}%",
            f"- 市场宽度评估: {'广谱上涨' if breadth_pct > 65 else '分化行情' if breadth_pct > 40 else '普跌格局'}",
        ])
    else:
        report_lines.append("- 当前无法从 QMT 获取有效全市场快照，市场宽度数据缺失")

    # === 3. 涨跌停统计 ===
    report_lines.append("")
    report_lines.append("## 涨跌停统计（QMT 快照代理）")
    limit_stats = adapter.get_limit_stats(trade_date=normalized_trade_date)
    if limit_stats:
        source_tag = "实时快照" if limit_stats.get("source") == "realtime" else "历史日线回算"
        report_lines.extend([
            f"- 涨停: {limit_stats['up_limit']} 家",
            f"- 跌停: {limit_stats['down_limit']} 家",
            f"- 数据来源: {source_tag}",
        ])
        if limit_stats["up_limit_stocks"]:
            names = ", ".join(f"{n}({c})" for c, n, _ in limit_stats["up_limit_stocks"][:10])
            report_lines.append(f"- 涨停股（前10）: {names}")
        if limit_stats["down_limit_stocks"]:
            names = ", ".join(f"{n}({c})" for c, n, _ in limit_stats["down_limit_stocks"][:10])
            report_lines.append(f"- 跌停股（前10）: {names}")
    else:
        report_lines.append("- 暂无涨跌停统计数据")

    # === 4. 成交额排名 ===
    report_lines.append("")
    report_lines.append("## 成交额排名（QMT 快照代理）")
    amount_ranking = adapter.get_amount_ranking(10, trade_date=normalized_trade_date)
    if amount_ranking:
        for i, row in enumerate(amount_ranking, 1):
            amt_yi = row["amount"] / 100000000 if row["amount"] else 0
            pct_str = f"{row['pct_chg']:+.2f}%" if row["pct_chg"] is not None else "-"
            report_lines.append(f"  {i:2d}. {row['name']}({row['code']}): {amt_yi:.2f} 亿 | {pct_str}")
    else:
        report_lines.append("- 暂无成交额排名数据")

    # === 5. 风格与结构判断 ===
    report_lines.append("")
    report_lines.append("## 风格与结构判断")
    hs300_20d = style_reference.get("000300.SH")
    zz500_20d = style_reference.get("000905.SH")
    cyb_20d = style_reference.get("399006.SZ")
    if hs300_20d is not None and zz500_20d is not None:
        if zz500_20d > hs300_20d:
            report_lines.append(f"- 中小盘相对占优: 中证500 20日 {_format_pct(zz500_20d)} 强于沪深300 20日 {_format_pct(hs300_20d)}")
        elif hs300_20d > zz500_20d:
            report_lines.append(f"- 大盘核心资产相对占优: 沪深300 20日 {_format_pct(hs300_20d)} 强于中证500 20日 {_format_pct(zz500_20d)}")
        else:
            report_lines.append("- 大小盘风格接近，暂未出现明显切换")
    if cyb_20d is not None and hs300_20d is not None:
        if cyb_20d > hs300_20d:
            report_lines.append(f"- 成长风格活跃: 创业板 20日 {_format_pct(cyb_20d)} 强于沪深300 {_format_pct(hs300_20d)}")
        else:
            report_lines.append(f"- 成长风格未显著占优: 创业板 20日 {_format_pct(cyb_20d)}，沪深300 {_format_pct(hs300_20d)}")

    # === 6. 市场周期识别（新增） ===
    report_lines.append("")
    report_lines.append("## 市场周期识别")

    # 基于上证指数判断周期
    sh_items = adapter.get_kline("000001.SH", period="day", limit=max(lookback_days, 120) + 5)
    if sh_items:
        sh_closes = [_safe_float(item.get("close")) for item in sh_items if _safe_float(item.get("close")) is not None]
        if len(sh_closes) >= 60:
            latest = sh_closes[-1]
            ma20_val = _compute_ma(sh_closes, 20)
            ma60_val = _compute_ma(sh_closes, 60)
            ma120_val = _compute_ma(sh_closes, 120) if len(sh_closes) >= 120 else None

            # 计算 20 日新高/新低
            high_20 = max(sh_closes[-20:])
            low_20 = min(sh_closes[-20:])
            near_high = latest >= high_20 * 0.98
            near_low = latest <= low_20 * 1.02

            # 趋势强度
            pct_20 = _compute_period_pct(sh_closes, 20)
            pct_60 = _compute_period_pct(sh_closes, 60)

            # MACD 趋势
            macd_r = _compute_macd(sh_closes)

            cycle_signals = []
            if ma20_val and ma60_val and ma120_val:
                if latest > ma20_val > ma60_val > ma120_val:
                    cycle_signals.append("均线多头排列 → 牛市特征")
                elif latest < ma20_val < ma60_val < ma120_val:
                    cycle_signals.append("均线空头排列 → 熊市特征")
                else:
                    cycle_signals.append("均线交织 → 震荡市特征")

            if pct_20 is not None and pct_60 is not None:
                if pct_20 > 5 and pct_60 > 10:
                    cycle_signals.append("中短期强势上涨 → 牛市信号")
                elif pct_20 < -5 and pct_60 < -10:
                    cycle_signals.append("中短期持续下跌 → 熊市信号")

            if near_high:
                cycle_signals.append("接近20日新高 → 多头动能")
            elif near_low:
                cycle_signals.append("接近20日新低 → 空头主导")

            if macd_r["histogram"] is not None:
                if macd_r["histogram"] > 0:
                    cycle_signals.append("MACD柱状线为正 → 多头动能")
                else:
                    cycle_signals.append("MACD柱状线为负 → 空头动能")

            # 综合判断
            bull_count = sum(1 for s in cycle_signals if "牛" in s or "多" in s or "强" in s)
            bear_count = sum(1 for s in cycle_signals if "熊" in s or "空" in s)

            if bull_count >= 3 and bear_count == 0:
                cycle_label = "牛市周期"
            elif bear_count >= 3 and bull_count == 0:
                cycle_label = "熊市周期"
            elif bull_count > bear_count:
                cycle_label = "偏多震荡"
            elif bear_count > bull_count:
                cycle_label = "偏空震荡"
            else:
                cycle_label = "中性震荡"

            report_lines.extend([
                f"- 周期判断: **{cycle_label}**",
                f"- 判断依据:",
            ])
            for s in cycle_signals:
                report_lines.append(f"  - {s}")
        else:
            report_lines.append("- 数据不足（需至少60根K线），无法判断市场周期")
    else:
        report_lines.append("- 未获取到上证指数数据，无法判断市场周期")

    # === 7. 使用建议 ===
    report_lines.append("")
    report_lines.append("## 使用建议")
    report_lines.append("- 本报告适合用于趋势、扩散、活跃度、风格切换与周期判断。")
    report_lines.append("- 北向资金和两融数据仅 Tushare 提供，QMT 不支持此维度。")
    report_lines.append("- 当 Tushare 不可用但 QMT 可用时，应优先依据该报告进行大盘分析。")
    return "\n".join(report_lines)
