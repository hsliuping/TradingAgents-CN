"""
专项财务分析工具

提供 8 个细分财务工具：
1. get_income_analysis - 利润表分析（营收、利润趋势）
2. get_balance_sheet_analysis - 资产负债表分析（财务健康度）
3. get_cashflow_analysis - 现金流量表分析
4. get_goodwill_analysis - 商誉分析（估值、减值风险信号）
5. get_dupont_analysis - 杜邦分析（ROE 三因子/五因子拆解）
6. get_dividend_data - 分红送股数据
7. get_main_business - 主营业务构成
8. get_accounts_receivable_risk_analyzer - 应收账款风险三维分析（回收效率+收入质量+计提审慎性）
"""

import logging
import asyncio
from typing import Annotated, Optional, Dict, Any, List

from langchain_core.tools import tool
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _get_tushare_provider():
    """延迟导入获取 Tushare Provider"""
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    return get_tushare_provider()


def _get_mongodb_cache():
    """延迟导入获取 MongoDB 缓存适配器"""
    try:
        from tradingagents.dataflows.cache.mongodb_cache_adapter import get_mongodb_cache_adapter
        return get_mongodb_cache_adapter()
    except Exception:
        return None


def _safe_val(val, fmt: str = ",.2f") -> str:
    """安全格式化数值"""
    if val is None or val == "N/A":
        return "N/A"
    try:
        return f"{float(val):{fmt}}"
    except (ValueError, TypeError):
        return str(val)


def _safe_pct(val) -> str:
    """安全格式化百分比"""
    if val is None or val == "N/A":
        return "N/A"
    try:
        return f"{float(val):.2f}%"
    except (ValueError, TypeError):
        return str(val)


def _coerce_float(val) -> Optional[float]:
    if val is None or val in ("N/A", "", "--"):
        return None
    try:
        numeric = float(val)
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _resolve_gross_margin_percent(data: Dict[str, Any], indicator_list: List[Dict[str, Any]]) -> Optional[float]:
    for candidate in (data.get('grossprofit_margin'), data.get('gross_margin')):
        numeric = _coerce_float(candidate)
        if numeric is not None and -100 <= numeric <= 100:
            return numeric

    for record in indicator_list or []:
        for candidate in (record.get('grossprofit_margin'), record.get('gross_margin')):
            numeric = _coerce_float(candidate)
            if numeric is not None and -100 <= numeric <= 100:
                return numeric

    return None


def _wan_yi(val) -> str:
    """将数值转为 万/亿 显示"""
    if val is None or val == "N/A":
        return "N/A"
    try:
        v = float(val)
        if abs(v) >= 1e8:
            return f"{v / 1e8:.2f}亿"
        elif abs(v) >= 1e4:
            return f"{v / 1e4:.2f}万"
        else:
            return f"{v:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _run_async(coro):
    """
    在同步上下文中运行异步协程，兼容主线程和 worker 线程。

    - 如果当前线程有运行中的事件循环 → 在新线程中 asyncio.run()
    - 如果当前线程没有事件循环 → 直接 asyncio.run()
    """
    try:
        asyncio.get_running_loop()
        # 当前线程有运行中的事件循环，不能直接 asyncio.run()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result(timeout=30)
    except RuntimeError:
        # 当前线程没有运行中的事件循环，可以直接 asyncio.run()
        return asyncio.run(coro)


def _get_financial_data_from_cache_or_api(symbol: str, limit: int = 8) -> Optional[Dict[str, Any]]:
    """
    从 MongoDB 缓存或 Tushare API 获取完整财务数据（含 raw_data）

    优先读 MongoDB stock_financial_data 集合，如果没有则调 Tushare API。
    返回标准化后的数据（含 raw_data.income_statement 等列表）。
    """
    code6 = str(symbol).replace('.SH', '').replace('.SZ', '').replace('.BJ', '').zfill(6)

    # 1. 尝试 MongoDB 缓存
    cache = _get_mongodb_cache()
    if cache and cache.use_app_cache:
        doc = cache.get_financial_data(code6)
        if doc and doc.get('raw_data'):
            logger.info(f"💰 [专项财务] 使用 MongoDB 缓存: {symbol}")
            return doc

    # 2. 调 Tushare API
    try:
        provider = _get_tushare_provider()
        if provider and provider.is_available():
            logger.info(f"📊 [专项财务] 从 Tushare 获取数据: {symbol}, limit={limit}")
            data = _run_async(provider.get_financial_data(symbol, limit=limit))
            if data:
                return data
    except Exception as e:
        logger.warning(f"⚠️ [专项财务] Tushare 获取失败: {e}")

    return None


# ============================================================
# Tool 1: 利润表分析
# ============================================================
@tool
@register_tool(
    tool_id="get_income_analysis",
    name="利润表分析",
    description="分析股票利润表核心指标及多期增长趋势，结构化返回营收、净利润、毛利率、净利率、费用率等的多期序列数据",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_income_analysis(
    ticker: Annotated[str, "股票代码，6位数字（如 600519、000001）"],
    periods: Annotated[int, "分析期数（最近几个季度），默认8"] = 8
) -> str:
    """
    利润表分析工具 —— 获取股票的营收、利润及增长趋势

    分析内容包括：营业收入、净利润、毛利率、净利率、费用率等。
    支持多期（最近N个季度）趋势展示。

    Args:
        ticker: 股票代码（如 600519、000001）
        periods: 分析期数，默认8（最近8个季度）

    Returns:
        str: 利润表分析报告（Markdown格式）
    """
    logger.info(f"📊 [利润表分析] 分析股票: {ticker}, 期数: {periods}")
    try:
        data = _get_financial_data_from_cache_or_api(ticker, limit=periods)
        if not data:
            return f"❌ 未获取到 {ticker} 的财务数据，请确认股票代码正确"

        raw = data.get("raw_data", {})
        income_list = raw.get("income_statement", [])
        indicator_list = raw.get("financial_indicators", [])

        lines = [f"# {ticker} 利润表分析\n"]

        # 最新一期概览
        lines.append("## 📊 最新一期概览")
        lines.append(f"- **报告期**: {data.get('report_period', 'N/A')}")
        lines.append(f"- **营业收入**: {_wan_yi(data.get('revenue'))}")
        lines.append(f"- **营业收入(TTM)**: {_wan_yi(data.get('revenue_ttm'))}")
        lines.append(f"- **归母净利润**: {_wan_yi(data.get('net_profit'))}")
        lines.append(f"- **归母净利润(TTM)**: {_wan_yi(data.get('net_profit_ttm'))}")
        lines.append(f"- **营业利润**: {_wan_yi(data.get('oper_profit'))}")
        lines.append(f"- **营业成本**: {_wan_yi(data.get('oper_cost'))}")
        lines.append(f"- **毛利率**: {_safe_pct(_resolve_gross_margin_percent(data, indicator_list))}")
        lines.append(f"- **净利率**: {_safe_pct(data.get('netprofit_margin'))}")
        lines.append(f"- **研发费用**: {_wan_yi(data.get('rd_exp'))}")
        lines.append("")

        # 费用结构
        lines.append("## 💰 费用结构")
        lines.append(f"- **销售费用/营收**: {_safe_pct(data.get('saleexp_to_gr'))}")
        lines.append(f"- **管理费用/营收**: {_safe_pct(data.get('adminexp_of_gr'))}")
        lines.append(f"- **财务费用/营收**: {_safe_pct(data.get('finaexp_of_gr'))}")
        lines.append(f"- **销售成本率**: {_safe_pct(data.get('cogs_of_sales'))}")
        lines.append(f"- **期间费用率**: {_safe_pct(data.get('expense_of_sales'))}")
        lines.append("")

        # 多期趋势
        if income_list and len(income_list) > 1:
            lines.append("## 📈 多期趋势")
            lines.append("| 报告期 | 营业收入 | 归母净利润 | 营业利润 |")
            lines.append("|--------|----------|------------|----------|")
            for rec in income_list[:periods]:
                period = rec.get('end_date', 'N/A')
                rev = _wan_yi(rec.get('revenue'))
                np_ = _wan_yi(rec.get('n_income_attr_p'))
                op = _wan_yi(rec.get('oper_profit'))
                lines.append(f"| {period} | {rev} | {np_} | {op} |")
            lines.append("")

        # 盈利能力指标趋势
        if indicator_list and len(indicator_list) > 1:
            lines.append("## 📊 盈利能力趋势")
            lines.append("| 报告期 | 毛利率 | 净利率 | ROE |")
            lines.append("|--------|--------|--------|-----|")
            for rec in indicator_list[:periods]:
                period = rec.get('end_date', 'N/A')
                gm = _safe_pct(_resolve_gross_margin_percent({}, [rec]))
                nm = _safe_pct(rec.get('netprofit_margin'))
                roe = _safe_pct(rec.get('roe'))
                lines.append(f"| {period} | {gm} | {nm} | {roe} |")
            lines.append("")

        lines.append("---")
        lines.append("*数据来源: Tushare / MongoDB 缓存*")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ [利润表分析] 执行失败: {e}")
        return f"❌ 利润表分析执行失败: {e}"


# ============================================================
# Tool 2: 资产负债表分析
# ============================================================
@tool
@register_tool(
    tool_id="get_balance_sheet_analysis",
    name="资产负债表分析",
    description="分析股票资产负债结构、偿债能力与财务健康度，结构化返回资产负债率、流动比率、速动比率、权益乘数等指标",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_balance_sheet_analysis(
    ticker: Annotated[str, "股票代码，6位数字（如 600519、000001）"],
    periods: Annotated[int, "分析期数（最近几个季度），默认8"] = 8
) -> str:
    """
    资产负债表分析工具 —— 分析财务健康度

    分析内容：资产负债率、流动比率、速动比率、现金比率、资产结构等。

    Args:
        ticker: 股票代码
        periods: 分析期数，默认8

    Returns:
        str: 资产负债表分析报告
    """
    logger.info(f"📊 [资产负债表分析] 分析股票: {ticker}")
    try:
        data = _get_financial_data_from_cache_or_api(ticker, limit=periods)
        if not data:
            return f"❌ 未获取到 {ticker} 的财务数据"

        raw = data.get("raw_data", {})
        balance_list = raw.get("balance_sheet", [])
        indicator_list = raw.get("financial_indicators", [])

        lines = [f"# {ticker} 资产负债表分析\n"]

        # 最新一期
        lines.append("## 📊 最新资产负债状况")
        lines.append(f"- **报告期**: {data.get('report_period', 'N/A')}")
        lines.append(f"- **总资产**: {_wan_yi(data.get('total_assets'))}")
        lines.append(f"- **总负债**: {_wan_yi(data.get('total_liab'))}")
        lines.append(f"- **股东权益**: {_wan_yi(data.get('total_equity'))}")
        lines.append(f"- **货币资金**: {_wan_yi(data.get('money_cap'))}")
        lines.append(f"- **应收账款**: {_wan_yi(data.get('accounts_receiv'))}")
        lines.append(f"- **存货**: {_wan_yi(data.get('inventories'))}")
        lines.append(f"- **固定资产**: {_wan_yi(data.get('fix_assets'))}")

        # 商誉（仅在年报披露时有效值）
        goodwill = data.get('goodwill')
        if goodwill is not None and goodwill > 0:
            lines.append(f"- **商誉**: {_wan_yi(goodwill)} | 商誉/净资产: {_safe_pct(goodwill / data.get('total_equity') * 100 if data.get('total_equity') else None)}")
        else:
            lines.append(f"- **商誉**: 数据不足（季报通常不披露商誉明细，建议查询年报数据）")
        lines.append("")

        # 偿债能力
        lines.append("## 🏦 偿债能力指标")
        lines.append(f"- **资产负债率**: {_safe_pct(data.get('debt_to_assets'))}")
        lines.append(f"- **流动比率**: {_safe_val(data.get('current_ratio'))}")
        lines.append(f"- **速动比率**: {_safe_val(data.get('quick_ratio'))}")
        lines.append(f"- **现金比率**: {_safe_val(data.get('cash_ratio'))}")
        lines.append(f"- **权益乘数**: {_safe_val(data.get('assets_to_eqt'))}")
        lines.append("")

        # 资产结构
        lines.append("## 📊 资产结构")
        lines.append(f"- **流动资产**: {_wan_yi(data.get('total_cur_assets'))}")
        lines.append(f"- **非流动资产**: {_wan_yi(data.get('total_nca'))}")
        lines.append(f"- **流动资产占比**: {_safe_pct(data.get('ca_to_assets'))}")
        lines.append(f"- **非流动资产占比**: {_safe_pct(data.get('nca_to_assets'))}")
        lines.append(f"- **流动负债**: {_wan_yi(data.get('total_cur_liab'))}")
        lines.append(f"- **非流动负债**: {_wan_yi(data.get('total_ncl'))}")
        lines.append("")

        # 多期趋势
        if balance_list and len(balance_list) > 1:
            lines.append("## 📈 资产负债趋势")
            lines.append("| 报告期 | 总资产 | 总负债 | 股东权益 | 货币资金 | 商誉 |")
            lines.append("|--------|--------|--------|----------|----------|------|")
            for rec in balance_list[:periods]:
                period = rec.get('end_date', 'N/A')
                ta = _wan_yi(rec.get('total_assets'))
                tl = _wan_yi(rec.get('total_liab'))
                eq = _wan_yi(rec.get('total_hldr_eqy_exc_min_int'))
                mc = _wan_yi(rec.get('money_cap'))
                gw = _wan_yi(rec.get('goodwill'))
                lines.append(f"| {period} | {ta} | {tl} | {eq} | {mc} | {gw} |")
            lines.append("")

        # 偿债能力趋势
        if indicator_list and len(indicator_list) > 1:
            lines.append("## 📊 偿债能力趋势")
            lines.append("| 报告期 | 资产负债率 | 流动比率 | 速动比率 |")
            lines.append("|--------|-----------|---------|---------|")
            for rec in indicator_list[:periods]:
                period = rec.get('end_date', 'N/A')
                dta = _safe_pct(rec.get('debt_to_assets'))
                cr = _safe_val(rec.get('current_ratio'))
                qr = _safe_val(rec.get('quick_ratio'))
                lines.append(f"| {period} | {dta} | {cr} | {qr} |")
            lines.append("")

        lines.append("---")
        lines.append("*数据来源: Tushare / MongoDB 缓存*")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ [资产负债表分析] 执行失败: {e}")
        return f"❌ 资产负债表分析执行失败: {e}"


# ============================================================
# Tool 3: 现金流量表分析
# ============================================================
@tool
@register_tool(
    tool_id="get_cashflow_analysis",
    name="现金流量表分析",
    description=(
        "分析股票的经营/投资/筹资现金流，评估现金流健康度。"
        "适合现金流恶化分析、经营现金流持续下滑识别、自由现金流为负识别、现金收入质量判断、"
        "利润含金量评估和财务风险信号排查。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["cashflow_analysis", "cashflow_quality", "cashflow_deterioration", "operating_cashflow", "free_cashflow", "financial_risk"],
    tool_role_hint="specialized",
    output_shape="markdown_report",
    preferred_for=["cashflow_quality_analysis", "financial_risk_signal_detection", "financial_statement_analysis"],
    when_to_use="当需要解释财务报表口径的经营/投资/筹资现金流、多期现金流趋势、自由现金流、现金流健康度、现金流恶化风险和利润含金量时使用。",
    when_not_to_use="不用于主力资金流、北向资金、成交资金流向或短线交易资金面分析；这些是市场资金流，不是财报现金流。若需要结构化长期现金流质量指标，优先用 get_cashflow_quality_trend_tool。",
)
def get_cashflow_analysis(
    ticker: Annotated[str, "股票代码，6位数字（如 600519、000001）"],
    periods: Annotated[int, "分析期数（最近几个季度），默认8"] = 8
) -> str:
    """
    现金流量表分析工具 —— 评估现金流健康度

    分析内容：经营现金流、投资现金流、筹资现金流、自由现金流等。

    Args:
        ticker: 股票代码
        periods: 分析期数，默认8

    Returns:
        str: 现金流量表分析报告
    """
    logger.info(f"📊 [现金流分析] 分析股票: {ticker}")
    try:
        data = _get_financial_data_from_cache_or_api(ticker, limit=periods)
        if not data:
            return f"❌ 未获取到 {ticker} 的财务数据"

        raw = data.get("raw_data", {})
        cashflow_list = raw.get("cashflow_statement", [])

        lines = [f"# {ticker} 现金流量表分析\n"]

        # 最新一期
        lines.append("## 📊 最新现金流状况")
        lines.append(f"- **报告期**: {data.get('report_period', 'N/A')}")
        ocf = data.get('n_cashflow_act')
        icf = data.get('n_cashflow_inv_act')
        fcf_val = data.get('n_cashflow_fin_act')
        lines.append(f"- **经营活动现金流净额**: {_wan_yi(ocf)}")
        lines.append(f"- **投资活动现金流净额**: {_wan_yi(icf)}")
        lines.append(f"- **筹资活动现金流净额**: {_wan_yi(fcf_val)}")
        lines.append(f"- **期末现金及等价物**: {_wan_yi(data.get('c_cash_equ_end_period'))}")
        lines.append(f"- **期初现金及等价物**: {_wan_yi(data.get('c_cash_equ_beg_period'))}")
        lines.append("")

        # 简易自由现金流估算
        if ocf is not None and icf is not None:
            try:
                free_cf = float(ocf) + float(icf)
                lines.append(f"## 💡 自由现金流（简易估算）")
                lines.append(f"- **自由现金流 ≈ 经营现金流 + 投资现金流**: {_wan_yi(free_cf)}")
                if free_cf > 0:
                    lines.append(f"- **判断**: ✅ 自由现金流为正，公司造血能力良好")
                else:
                    lines.append(f"- **判断**: ⚠️ 自由现金流为负，需关注资金压力")
                lines.append("")
            except (ValueError, TypeError):
                pass

        # 现金流质量分析
        net_profit = data.get('net_profit')
        if ocf is not None and net_profit is not None:
            try:
                ocf_f = float(ocf)
                np_f = float(net_profit)
                if np_f != 0:
                    ratio = ocf_f / np_f
                    lines.append("## 🔍 现金流质量")
                    lines.append(f"- **经营现金流/归母净利润**: {ratio:.2f}")
                    if ratio > 1:
                        lines.append("- **判断**: ✅ 现金流质量优秀（>1），利润含金量高")
                    elif ratio > 0.5:
                        lines.append("- **判断**: 🟡 现金流质量一般（0.5~1），部分利润尚未回款")
                    else:
                        lines.append("- **判断**: ⚠️ 现金流质量偏弱（<0.5），利润含金量较低")
                    lines.append("")
            except (ValueError, TypeError):
                pass

        # 多期趋势
        if cashflow_list and len(cashflow_list) > 1:
            lines.append("## 📈 现金流趋势")
            lines.append("| 报告期 | 经营现金流 | 投资现金流 | 筹资现金流 | 期末现金 |")
            lines.append("|--------|-----------|-----------|-----------|---------|")
            for rec in cashflow_list[:periods]:
                period = rec.get('end_date', 'N/A')
                o = _wan_yi(rec.get('n_cashflow_act'))
                i = _wan_yi(rec.get('n_cashflow_inv_act'))
                f_ = _wan_yi(rec.get('n_cashflow_fin_act'))
                e = _wan_yi(rec.get('c_cash_equ_end_period'))
                lines.append(f"| {period} | {o} | {i} | {f_} | {e} |")
            lines.append("")

        lines.append("---")
        lines.append("*数据来源: Tushare / MongoDB 缓存*")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ [现金流分析] 执行失败: {e}")
        return f"❌ 现金流分析执行失败: {e}"


# ============================================================
# Tool 4: 商誉分析
# ============================================================
@tool
@register_tool(
    tool_id="get_goodwill_analysis",
    name="商誉分析",
    description="分析股票的商誉规模、占比及变动趋势，评估商誉减值风险。从年报资产负债表提取 goodwill 字段，计算商誉/净资产比率和同比变化。",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_goodwill_analysis(
    ticker: Annotated[str, "股票代码，6位数字（如 002230、600519、000001）"],
    years: Annotated[int, "回溯年数，默认5年"] = 5
) -> str:
    """
    商誉分析工具 —— 评估商誉规模与减值风险

    从资产负债表年报数据中提取商誉(goodwill)字段，计算：
    - 商誉账面金额
    - 商誉/净资产比率
    - 商誉/总资产比率
    - 同比变化趋势（识别减值信号）

    ⚠️ 商誉仅在年报（Q4）完整披露，本工具从 raw_data 中筛选年报数据，
    不会出现季报空值问题。

    Args:
        ticker: 股票代码（如 002230、600519）
        years: 回溯年数，默认5年

    Returns:
        str: 商誉分析报告
    """
    logger.info(f"📊 [商誉分析] 分析股票: {ticker}, 回溯{years}年")
    try:
        data = _get_financial_data_from_cache_or_api(ticker, limit=years * 4 + 4)
        if not data:
            return f"❌ 未获取到 {ticker} 的财务数据"

        raw = data.get("raw_data", {})
        balance_list = raw.get("balance_sheet", [])

        # 筛选年报：取每年最后一个报告期（end_date 含 -12-31 或按年度去重取最后一条）
        annual_records: List[Dict[str, Any]] = []
        seen_years: set = set()
        for rec in balance_list:
            end_date = str(rec.get('end_date', '') or rec.get('f_ann_date', ''))
            if not end_date:
                continue
            # 提取年份
            year = end_date[:4]
            if year not in seen_years:
                seen_years.add(year)
                annual_records.append(rec)

        # 取最近 years 年的年报
        annual_records = sorted(annual_records, key=lambda r: str(r.get('end_date', '')), reverse=True)[:years]

        if not annual_records:
            return f"📊 {ticker} 暂无商誉数据（资产负债表缓存中未找到年报记录，建议先拉取数据）"

        goodwill_by_year: Dict[str, Optional[float]] = {}
        equity_by_year: Dict[str, Optional[float]] = {}
        assets_by_year: Dict[str, Optional[float]] = {}

        for rec in annual_records:
            year = str(rec.get('end_date', ''))[:4] or 'N/A'
            goodwill_by_year[year] = rec.get('goodwill')
            equity_by_year[year] = rec.get('total_hldr_eqy_exc_min_int')
            assets_by_year[year] = rec.get('total_assets')

        lines = [f"# {ticker} 商誉分析\n"]

        # 最新一期商誉概况
        latest_year = list(goodwill_by_year.keys())[0]
        latest_gw = goodwill_by_year.get(latest_year)
        latest_equity = equity_by_year.get(latest_year)
        latest_assets = assets_by_year.get(latest_year)

        lines.append("## 📊 最新一期商誉概况")
        lines.append(f"- **报告年度**: {latest_year}")

        if latest_gw is not None and latest_gw > 0:
            lines.append(f"- **商誉账面金额**: {_wan_yi(latest_gw)}")
            if latest_equity:
                gw_to_equity = latest_gw / latest_equity * 100
                lines.append(f"- **商誉/净资产**: {gw_to_equity:.1f}%")
                risk_flag = "🔴 高风险（商誉占净资产比例过高，减值压力大）" if gw_to_equity > 20 else ("🟡 关注（商誉占比偏高）" if gw_to_equity > 10 else "🟢 正常")
                lines.append(f"- **风险信号**: {risk_flag}")
            if latest_assets:
                lines.append(f"- **商誉/总资产**: {latest_gw / latest_assets * 100:.1f}%")
        elif latest_gw is not None and latest_gw == 0:
            lines.append(f"- **商誉账面金额**: 0（该公司无商誉）")
            lines.append(f"- **风险信号**: 🟢 无商誉减值风险")
        else:
            lines.append(f"- **商誉账面金额**: 数据缺失（年报未披露 goodwill 字段）")
            lines.append(f"- **风险信号**: ⬜ 数据不足，无法判断")
        lines.append("")

        # 多年趋势
        if len(annual_records) > 1:
            lines.append("## 📈 商誉年度趋势")
            lines.append("| 报告年度 | 商誉 | 净资产 | 商誉/净资产 | 商誉/总资产 |")
            lines.append("|----------|------|--------|------------|------------|")
            sorted_years = sorted(goodwill_by_year.keys(), reverse=True)
            prev_gw = None
            for year in sorted_years:
                gw = goodwill_by_year.get(year)
                eq = equity_by_year.get(year)
                ta = assets_by_year.get(year)
                gwe = f"{gw / eq * 100:.1f}%" if (gw is not None and eq and eq > 0) else "-"
                gwt = f"{gw / ta * 100:.1f}%" if (gw is not None and ta and ta > 0) else "-"
                lines.append(f"| {year} | {_wan_yi(gw)} | {_wan_yi(eq)} | {gwe} | {gwt} |")

                # 检测同比大幅下降（减值信号）
                if prev_gw is not None and gw is not None and prev_gw > 0 and gw > 0:
                    change = (gw - prev_gw) / prev_gw * 100
                    if change < -20:
                        lines.append(f"  ⚠️ {year}年商誉同比下降 {abs(change):.0f}%，可能存在减值！")
                prev_gw = gw
            lines.append("")

        lines.append("## 🔍 减值风险判读")
        if latest_gw is not None and latest_gw > 0 and latest_equity:
            ratio = latest_gw / latest_equity * 100
            lines.append(f"- 商誉/净资产比率 = {ratio:.1f}%")
            if ratio > 20:
                lines.append(f"- ⚠️ 超过 20% 警戒线，减值对净资产的冲击显著")
                lines.append(f"- 建议关注：标的公司业绩承诺完成情况、行业景气度变化")
            elif ratio > 10:
                lines.append(f"- 处于 10%-20% 关注区间，需持续跟踪")
            else:
                lines.append(f"- 低于 10%，商誉减值对净资产影响有限")
        lines.append("")

        lines.append("---")
        lines.append("*数据来源: 年报资产负债表 (Tushare) | 商誉字段仅在年报中完整披露*")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ [商誉分析] 执行失败: {e}")
        return f"❌ 商誉分析执行失败: {e}"


# ============================================================
# Tool 5: 杜邦分析
# ============================================================
@tool
@register_tool(
    tool_id="get_dupont_analysis",
    name="杜邦分析",
    description="对股票进行杜邦分析，拆解ROE为三因子（净利率×资产周转率×权益乘数）和五因子（税负×利息负担×经营利润率×资产周转率×权益乘数），支持多年趋势对比。",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_dupont_analysis(
    ticker: Annotated[str, "股票代码，6位数字（如 600519、000001、002230）"],
    years: Annotated[int, "回溯年数，默认5年"] = 5
) -> str:
    """
    杜邦分析工具 — ROE 三因子 / 五因子拆解

    从缓存中读取 TTM 利润表和资产负债表数据，计算：

    **三因子拆解**：
    - 净利率 = 净利润(TTM) / 营业收入(TTM)
    - 资产周转率 = 营业收入(TTM) / 总资产
    - 权益乘数 = 总资产 / 净资产
    - ROE = 净利率 × 资产周转率 × 权益乘数

    **五因子拆解**（需要营业利润数据）：
    - 税负因子 = 净利润 / 利润总额
    - 利息负担 = 利润总额 / 营业利润
    - 经营利润率 = 营业利润 / 营业收入
    - 资产周转率 = 营业收入 / 总资产
    - 权益乘数 = 总资产 / 净资产

    Args:
        ticker: 股票代码（如 600519、002230）
        years: 回溯年数，默认5年

    Returns:
        str: 杜邦分析报告
    """
    logger.info(f"📊 [杜邦分析] 分析股票: {ticker}, 回溯{years}年")
    try:
        data = _get_financial_data_from_cache_or_api(ticker, limit=years * 4 + 4)
        if not data:
            return f"❌ 未获取到 {ticker} 的财务数据"

        lines = [f"# {ticker} 杜邦分析\n"]

        # ── 三因子杜邦 ──
        npm, at, em, roe_3f = None, None, None, None

        revenue = _coerce_float(data.get('revenue_ttm'))
        net_profit = _coerce_float(data.get('net_profit_ttm'))
        total_assets = _coerce_float(data.get('total_assets'))
        total_equity = _coerce_float(data.get('total_equity'))

        if all([net_profit, revenue, total_assets, total_equity]) and revenue != 0 and total_equity != 0:
            npm = net_profit / revenue  # 净利率（小数）
            at = revenue / total_assets   # 资产周转率
            em = total_assets / total_equity  # 权益乘数
            roe_3f = npm * at * em * 100     # 杜邦 ROE（百分比）
            roe_direct = net_profit / total_equity * 100

            lines.append("## 三因子拆解（标准杜邦）\n")
            lines.append(f"**ROE = 净利率 × 资产周转率 × 权益乘数**\n")
            lines.append("| 因子 | 含义 | 数值 |")
            lines.append("|------|------|------|")
            lines.append(f"| 净利率 | 净利润(TTM) / 营业收入(TTM) | {npm*100:.2f}% |")
            lines.append(f"| 资产周转率 | 营业收入(TTM) / 总资产 | {at:.3f} 次 |")
            lines.append(f"| 权益乘数 | 总资产 / 净资产 | {em:.2f} |")
            lines.append(f"| **ROE** | 三因子相乘 | **{roe_3f:.2f}%** |")
            lines.append("")
            lines.append(f"- 验证：直接 ROE = 净利润/净资产 = {roe_direct:.2f}%（{'✅ 一致' if abs(roe_3f - roe_direct) < 0.1 else '⚠️ 偏差（可能因四舍五入）'}）")
            lines.append("")

            # ROE 质量提示
            lines.append("### ROE 驱动因素判断\n")
            parts = []
            if npm and npm * 100 > 15:
                parts.append(f"- 🟢 **高利润率驱动**：净利率 {npm*100:.1f}%，产品/品牌壁垒强")
            elif npm and npm * 100 < 3:
                parts.append(f"- 🔴 **低利润率**：净利率仅 {npm*100:.1f}%，盈利空间薄")
            else:
                parts.append(f"- 🟡 **中等利润率**：净利率 {npm*100:.1f}%")
            if at and at > 1:
                parts.append(f"- 🟢 **高效资产周转**：周转率 {at:.2f} 次，轻资产模式或运营高效")
            elif at and at < 0.3:
                parts.append(f"- 🔴 **资产周转慢**：周转率仅 {at:.2f} 次，重资产或产能未充分利用")
            if em and em > 3:
                parts.append(f"- 🔴 **高杠杆**：权益乘数 {em:.1f}，财务杠杆放大收益也放大风险")
            elif em and em < 1.5:
                parts.append(f"- 🟢 **低杠杆**：权益乘数 {em:.1f}，财务结构稳健")
            lines.extend(parts)
            lines.append("")
        else:
            lines.append("## 三因子拆解（标准杜邦）\n")
            lines.append("⚠️ 数据不足，无法完成三因子拆解。")
            lines.append(f"  revenue_ttm={revenue}  net_profit_ttm={net_profit}  total_assets={total_assets}  total_equity={total_equity}")
            lines.append("")

        # ── 五因子杜邦 ──
        oper_profit = _coerce_float(data.get('oper_profit'))
        total_profit = _coerce_float(data.get('total_profit'))

        if all([net_profit, total_profit, oper_profit, revenue, total_assets, total_equity]) \
                and revenue != 0 and total_equity != 0 and oper_profit != 0:
            tb = net_profit / total_profit        # 税负因子
            ib = total_profit / oper_profit       # 利息负担
            om = oper_profit / revenue            # 经营利润率
            roe_5f = tb * ib * om * at * em * 100

            lines.append("## 五因子拆解（扩展杜邦）\n")
            lines.append(f"**ROE = 税负因子 × 利息负担 × 经营利润率 × 资产周转率 × 权益乘数**\n")
            lines.append("| 因子 | 含义 | 数值 |")
            lines.append("|------|------|------|")
            lines.append(f"| 税负因子 | 净利润 / 利润总额 | {tb:.3f}（{'所得税率 ' + str(int((1-tb)*100)) + '%' if 0 < tb <= 1 else '异常'}）|")
            lines.append(f"| 利息负担 | 利润总额 / 营业利润 | {ib:.3f}（{'利息侵蚀小' if 0.9 < ib < 1.1 else '利息/非经常损益影响显著'}）|")
            lines.append(f"| 经营利润率 | 营业利润 / 营业收入(TTM) | {om*100:.2f}% |")
            lines.append(f"| 资产周转率 | 营业收入(TTM) / 总资产 | {at:.3f} 次 |")
            lines.append(f"| 权益乘数 | 总资产 / 净资产 | {em:.2f} |")
            lines.append(f"| **ROE** | 五因子相乘 | **{roe_5f:.2f}%** |")
            lines.append("")

            # 评价
            qualifiers = []
            if 0.7 <= tb <= 0.9:
                qualifiers.append("税负水平正常")
            if ib > 1.1:
                qualifiers.append("⚠️ 利息负担因子 > 1，营业外收入对利润贡献大（非经营性收益）")
            elif ib < 0.9:
                qualifiers.append("⚠️ 利息负担因子 < 1，财务费用/非经常损失侵蚀营业利润")
            if om and om > 0.2:
                qualifiers.append("经营利润率优秀")
            if qualifiers:
                lines.append("### 评价\n")
                for q in qualifiers:
                    lines.append(f"- {q}")
                lines.append("")
        elif oper_profit is None:
            lines.append("## 五因子拆解（扩展杜邦）\n")
            lines.append("⚠️ 营业利润数据缺失，无法完成五因子拆解。")
            lines.append("*若数据源为 Tushare 且刚修复 `operate_profit` 字段映射，需重新拉取数据。*")
            lines.append("")
        else:
            lines.append("## 五因子拆解（扩展杜邦）\n")
            lines.append("⚠️ 五因子拆解所需字段异常（可能有零值或数据不完整）。")
            lines.append("")

        # ── 多年趋势 ──
        raw = data.get("raw_data", {})
        inc_list = raw.get("income_statement", [])
        bs_list = raw.get("balance_sheet", [])

        if inc_list and bs_list:
            # 取每年年报数据用于趋势
            annual_inc = {}
            for rec in inc_list:
                end = str(rec.get('end_date', ''))
                if not end:
                    continue
                year = end[:4]
                if year not in annual_inc:
                    annual_inc[year] = rec

            annual_bs = {}
            for rec in bs_list:
                end = str(rec.get('end_date', ''))
                if not end:
                    continue
                year = end[:4]
                if year not in annual_bs:
                    annual_bs[year] = rec

            # 交叉对齐
            common_years = sorted(set(annual_inc.keys()) & set(annual_bs.keys()), reverse=True)[:years]

            if len(common_years) >= 2:
                lines.append("## 杜邦因子年度趋势\n")
                lines.append("| 年度 | 净利率 | 资产周转率 | 权益乘数 | ROE |")
                lines.append("|------|--------|------------|----------|-----|")
                for yr in common_years:
                    inc = annual_inc[yr]
                    bs = annual_bs[yr]
                    r = _coerce_float(inc.get('total_revenue') or inc.get('revenue'))
                    n = _coerce_float(inc.get('n_income') or inc.get('n_income_attr_p'))
                    ta = _coerce_float(bs.get('total_assets'))
                    eq = _coerce_float(bs.get('total_hldr_eqy_exc_min_int'))
                    if all([n, r, ta, eq]) and r != 0 and eq != 0:
                        n_pm = n / r * 100
                        a_t = r / ta
                        e_m = ta / eq
                        r_oe = n / eq * 100
                        lines.append(f"| {yr} | {n_pm:.1f}% | {a_t:.3f} | {e_m:.2f} | {r_oe:.2f}% |")
                lines.append("")

        lines.append("---")
        lines.append("*杜邦分析 — ROE = 净利率 × 资产周转率 × 权益乘数*")
        lines.append(f"*数据来源：Tushare | 基于TTM数据计算*")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ [杜邦分析] 执行失败: {e}")
        return f"❌ 杜邦分析执行失败: {e}"


# ============================================================
# Tool 6: 分红送股数据
# ============================================================
@tool
@register_tool(
    tool_id="get_dividend_data",
    name="分红送股数据",
    description="获取股票的历史分红送股记录，包括每股分红、送转比例、股息率等",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_dividend_data(
    ticker: Annotated[str, "股票代码，6位数字（如 600519、000001）"],
    years: Annotated[int, "查询最近几年的分红记录，默认5"] = 5
) -> str:
    """
    分红送股数据工具 —— 获取历史分红记录和股息率

    分析内容：每股现金分红、送股转增比例、分红年度、实施进度等。
    需要 Tushare 2000+ 积分权限。

    Args:
        ticker: 股票代码（如 600519、000001）
        years: 查询最近几年的分红记录，默认5年

    Returns:
        str: 分红送股分析报告
    """
    logger.info(f"💰 [分红数据] 查询股票: {ticker}, 最近{years}年")
    try:
        provider = _get_tushare_provider()
        if not provider or not provider.is_available():
            return f"❌ Tushare 服务不可用，无法获取 {ticker} 的分红数据"

        # 调用 Tushare dividend API（使用 _run_async 兼容 worker 线程）
        try:
            records = _run_async(provider.get_dividend_data(ticker, limit=years * 3))
        except Exception as e:
            logger.warning(f"⚠️ [分红数据] Tushare 调用失败: {e}")
            return f"❌ 获取 {ticker} 分红数据失败: {e}（需要 Tushare 2000+ 积分权限）"

        if not records:
            return f"📊 {ticker} 暂无分红送股记录"

        lines = [f"# {ticker} 分红送股数据\n"]

        # 统计概览
        implemented = [r for r in records if r.get('div_proc') == '实施']
        total_cash_div = sum(float(r.get('cash_div_tax', 0) or 0) for r in implemented)

        lines.append("## 📊 分红概览")
        lines.append(f"- **总记录数**: {len(records)} 条")
        lines.append(f"- **已实施分红**: {len(implemented)} 次")
        lines.append(f"- **累计每股分红（税前）**: {total_cash_div:.4f} 元")
        lines.append("")

        # 分红明细表
        lines.append("## 💰 分红明细")
        lines.append("| 分红年度 | 进度 | 每股分红(税前) | 每股分红(税后) | 每股送股 | 每股转增 | 除权除息日 |")
        lines.append("|---------|------|---------------|---------------|---------|---------|-----------|")
        for rec in records:
            end_date = rec.get('end_date', 'N/A')
            proc = rec.get('div_proc', 'N/A')
            cash_tax = _safe_val(rec.get('cash_div_tax'), ".4f")
            cash_after = _safe_val(rec.get('cash_div'), ".4f")
            stk_bo = _safe_val(rec.get('stk_bo_rate'), ".2f")
            stk_co = _safe_val(rec.get('stk_co_rate'), ".2f")
            ex_date = rec.get('ex_date') or 'N/A'
            lines.append(f"| {end_date} | {proc} | {cash_tax} | {cash_after} | {stk_bo} | {stk_co} | {ex_date} |")
        lines.append("")

        # 分红趋势分析
        if len(implemented) >= 2:
            lines.append("## 📈 分红趋势")
            cash_vals = [float(r.get('cash_div_tax', 0) or 0) for r in implemented[:years]]
            if all(v > 0 for v in cash_vals):
                if cash_vals[0] >= cash_vals[-1]:
                    lines.append("- **趋势判断**: ✅ 分红金额整体上升或持平，股东回报意识良好")
                else:
                    lines.append("- **趋势判断**: 🟡 近期分红金额有所下降，需关注原因")
            elif any(v > 0 for v in cash_vals):
                lines.append("- **趋势判断**: 🟡 分红不连续，部分年度无现金分红")
            else:
                lines.append("- **趋势判断**: ⚠️ 近几年无现金分红记录")
            lines.append("")

        lines.append("---")
        lines.append("*数据来源: Tushare dividend API（需 2000+ 积分权限）*")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ [分红数据] 执行失败: {e}")
        return f"❌ 分红数据查询失败: {e}"


# ============================================================
# Tool 7: 主营业务构成
# ============================================================
@tool
@register_tool(
    tool_id="get_main_business",
    name="主营业务构成",
    description="获取股票主营业务构成并分析收入来源结构，结构化返回按产品/地区分部收入占比、毛利率、集中度等明细数据",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_main_business(
    ticker: Annotated[str, "股票代码，6位数字（如 600519、000001）"],
    periods: Annotated[int, "分析期数（最近几个报告期），默认4"] = 4
) -> str:
    """
    主营业务构成工具 —— 分析收入来源和业务结构

    展示按产品/地区维度的主营业务收入构成。

    Args:
        ticker: 股票代码（如 600519、000001）
        periods: 分析期数，默认4

    Returns:
        str: 主营业务构成分析报告
    """
    logger.info(f"📊 [主营业务] 分析股票: {ticker}")
    try:
        data = _get_financial_data_from_cache_or_api(ticker, limit=periods)
        if not data:
            return f"❌ 未获取到 {ticker} 的财务数据"

        raw = data.get("raw_data", {})
        mainbz_list = raw.get("main_business", [])

        if not mainbz_list:
            return f"📊 {ticker} 暂无主营业务构成数据（部分公司可能尚未披露）"

        lines = [f"# {ticker} 主营业务构成\n"]

        # 按报告期分组
        from collections import defaultdict
        period_groups = defaultdict(list)
        for rec in mainbz_list:
            period = rec.get('end_date', 'N/A')
            period_groups[period].append(rec)

        # 按报告期倒序展示
        sorted_periods = sorted(period_groups.keys(), reverse=True)

        for idx, period in enumerate(sorted_periods[:periods]):
            items = period_groups[period]
            # 按产品分类和地区分类
            products = [r for r in items if r.get('bz_item') and r.get('bz_sales') is not None]

            if not products:
                continue

            lines.append(f"## 📊 {period} 主营业务构成")

            # 计算总收入
            total_sales = sum(float(r.get('bz_sales', 0) or 0) for r in products)

            if total_sales > 0:
                lines.append(f"**总营业收入**: {_wan_yi(total_sales)}\n")
                lines.append("| 业务/产品 | 营业收入 | 营业成本 | 毛利率 | 收入占比 |")
                lines.append("|----------|---------|---------|--------|---------|")

                # 按收入排序
                sorted_items = sorted(products, key=lambda x: float(x.get('bz_sales', 0) or 0), reverse=True)
                for item in sorted_items:
                    name = item.get('bz_item', 'N/A')
                    sales = float(item.get('bz_sales', 0) or 0)
                    cost = float(item.get('bz_cost', 0) or 0)
                    profit = float(item.get('bz_profit', 0) or 0)

                    gm = f"{(profit / sales * 100):.1f}%" if sales > 0 else "N/A"
                    pct = f"{(sales / total_sales * 100):.1f}%" if total_sales > 0 else "N/A"

                    lines.append(f"| {name} | {_wan_yi(sales)} | {_wan_yi(cost)} | {gm} | {pct} |")

                lines.append("")
            else:
                lines.append("- 无有效数据\n")

        lines.append("---")
        lines.append("*数据来源: Tushare fina_mainbz / MongoDB 缓存*")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ [主营业务] 执行失败: {e}")
        return f"❌ 主营业务构成查询失败: {e}"


# ============================================================
# Tool 8: 应收账款风险分析
# ============================================================
@tool
@register_tool(
    tool_id="get_accounts_receivable_risk_analyzer",
    name="应收账款风险分析",
    description="三维评估应收账款风险：回收效率（周转天数）、收入质量（应收-营收增速偏离）、计提审慎性（信用减值损失趋势），交叉验证生成综合风险评级",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_accounts_receivable_risk_analyzer(
    ticker: Annotated[str, "股票代码，6位数字（如 600519、000001）"],
    years: Annotated[int, "回溯年数，默认4年"] = 4
) -> str:
    """
    应收账款风险分析工具 —— 三维交叉验证

    三个维度：
    1. 回收效率：应收账款周转天数及变化趋势
    2. 收入质量：应收账款增速 vs 营收增速的偏离度
    3. 计提审慎性：信用减值损失/应收账款的变动，交叉对比周转天数

    综合规则：
    - 三者正常 → 低风险
    - 单项恶化 → 关注
    - 周转恶化 + 计提下降 → 高风险（粉饰嫌疑）
    - 三者同时恶化 → 极高风险

    Args:
        ticker: 股票代码
        years: 回溯年数

    Returns:
        str: 应收账款风险分析报告
    """
    logger.info(f"📊 [应收账款风险分析] 分析股票: {ticker}, 回溯{years}年")
    try:
        data = _get_financial_data_from_cache_or_api(ticker, limit=years * 4 + 4)
        if not data:
            return f"❌ 未获取到 {ticker} 的财务数据"

        raw = data.get("raw_data", {})
        balance_list = raw.get("balance_sheet", [])
        income_list = raw.get("income_statement", [])
        indicator_list = raw.get("financial_indicators", [])

        # ---- 提取年报数据（每年取最后一条记录） ----
        def _extract_annual(records: list, fields: list) -> dict:
            """从季度列表中提取每年最后一条记录，返回 {year: {field: value}}"""
            by_year: Dict[str, Dict[str, Any]] = {}
            for rec in records:
                end_date = str(rec.get('end_date', '') or rec.get('f_ann_date', ''))
                if not end_date:
                    continue
                year = end_date[:4]
                # 同一年取 end_date 更大的（即年报）
                if year not in by_year or str(rec.get('end_date', '')) > str(by_year[year].get('end_date', '')):
                    by_year[year] = rec
            # 取最近 years 年，按年份降序
            sorted_years = sorted(by_year.keys(), reverse=True)[:years]
            result = {}
            for y in sorted_years:
                result[y] = {f: _coerce_float(by_year[y].get(f)) for f in fields}
            return result

        # 提取资产负债表年报：应收账款
        ar_annual = _extract_annual(balance_list, ['accounts_receiv'])
        # 提取利润表年报：营业收入、信用减值损失
        income_annual = _extract_annual(income_list, ['revenue', 'credit_impa_loss', 'assets_impair_loss'])
        # 提取财务指标年报：应收账款周转天数
        indicator_annual = _extract_annual(indicator_list, ['arturn_days'])

        year_keys = sorted(set(list(ar_annual.keys()) + list(income_annual.keys())), reverse=True)[:years]

        # ---- 跳转缺少数据 ----
        if len(year_keys) < 2:
            return f"📊 {ticker} 年报数据不足（需至少2年），无法进行趋势分析"

        # ---- 构建逐年数据表 ----
        records = []
        for y in year_keys:
            ar_val = _coerce_float(ar_annual.get(y, {}).get('accounts_receiv'))
            rev_val = _coerce_float(income_annual.get(y, {}).get('revenue'))
            impa_val = _coerce_float(income_annual.get(y, {}).get('credit_impa_loss'))
            arturn_days_val = _coerce_float(indicator_annual.get(y, {}).get('arturn_days'))

            records.append({
                'year': y,
                'accounts_receiv': ar_val,
                'revenue': rev_val,
                'credit_impa_loss': impa_val,
                'arturn_days': arturn_days_val,
            })

        # ---- 计算趋势指标 ----
        def _safe_ratio(curr, prev) -> Optional[float]:
            if curr is not None and prev is not None and prev != 0:
                return (curr - prev) / abs(prev)
            return None

        # 计算应收账款周转天数（自算，与 arturn_days 对照验证）
        for i, rec in enumerate(records):
            if rec['accounts_receiv'] and rec['revenue'] and rec['revenue'] != 0:
                rec['ar_turnover_days_self'] = 365 * rec['accounts_receiv'] / rec['revenue']
            else:
                rec['ar_turnover_days_self'] = None

        # 计算增速和偏离度
        for i in range(len(records) - 1):
            curr, prev = records[i], records[i + 1]
            curr['ar_growth'] = _safe_ratio(curr['accounts_receiv'], prev['accounts_receiv'])
            curr['rev_growth'] = _safe_ratio(curr['revenue'], prev['revenue'])
            if curr['ar_growth'] is not None and curr['rev_growth'] is not None:
                curr['deviation'] = curr['ar_growth'] - curr['rev_growth']
            else:
                curr['deviation'] = None
            # 计提比例
            if curr['credit_impa_loss'] is not None and curr['accounts_receiv'] is not None and curr['accounts_receiv'] != 0:
                curr['impa_ratio'] = curr['credit_impa_loss'] / curr['accounts_receiv']
            else:
                curr['impa_ratio'] = None

        # ---- 输出报告 ----
        lines = [f"# {ticker} 应收账款风险三维分析\n"]

        # 最新一期概览
        latest = records[0]
        lines.append("## 📊 最新一期快照")
        lines.append(f"- **报告年度**: {latest['year']}")
        lines.append(f"- **应收账款**: {_wan_yi(latest['accounts_receiv'])}")
        lines.append(f"- **营业收入**: {_wan_yi(latest['revenue'])}")
        if latest['arturn_days'] is not None:
            lines.append(f"- **应收账款周转天数** (数据源): {latest['arturn_days']:.1f} 天")
        if latest.get('ar_turnover_days_self') is not None:
            lines.append(f"- **应收账款周转天数** (自算): {latest['ar_turnover_days_self']:.1f} 天")
        if latest.get('ar_growth') is not None:
            lines.append(f"- **应收账款增速**: {latest['ar_growth'] * 100:+.1f}% (同比)")
        if latest.get('rev_growth') is not None:
            lines.append(f"- **营收增速**: {latest['rev_growth'] * 100:+.1f}% (同比)")
        if latest.get('deviation') is not None:
            lines.append(f"- **增速偏离度**: {latest['deviation'] * 100:+.1f} 百分点（正值 = 应收跑赢营收，虚胖信号）")
        if latest.get('impa_ratio') is not None:
            lines.append(f"- **信用减值损失/应收账款**: {latest['impa_ratio'] * 100:.2f}%")
        lines.append("")

        # 逐年趋势表
        lines.append("## 📈 逐年趋势")
        header = "| 年度 | 应收账款 | 营业收入 | 周转天数(源) | 周转天数(算) | 应收增速 | 营收增速 | 偏离度 | 减值/应收 |"
        lines.append(header)
        lines.append("|" + "|".join(["------"] * 9) + "|")
        for rec in records:
            ar = _wan_yi(rec['accounts_receiv'])
            rev = _wan_yi(rec['revenue'])
            atd = f"{rec['arturn_days']:.1f}" if rec['arturn_days'] is not None else "-"
            atds = f"{rec.get('ar_turnover_days_self'):.1f}" if rec.get('ar_turnover_days_self') is not None else "-"
            arg = f"{rec.get('ar_growth') * 100:+.1f}%" if rec.get('ar_growth') is not None else "-"
            revg = f"{rec.get('rev_growth') * 100:+.1f}%" if rec.get('rev_growth') is not None else "-"
            dev = f"{rec.get('deviation') * 100:+.1f}pp" if rec.get('deviation') is not None else "-"
            impa = f"{rec.get('impa_ratio') * 100:.2f}%" if rec.get('impa_ratio') is not None else "-"
            lines.append(f"| {rec['year']} | {ar} | {rev} | {atd} | {atds} | {arg} | {revg} | {dev} | {impa} |")
        lines.append("")

        # ---- 三维交叉风险评估 ----
        lines.append("## 🔍 三维风险评估")

        # 判定各维度状态
        def _assess_turnover(rec) -> tuple:
            """判定周转天数趋势：(方向, 程度)"""
            atd = rec.get('arturn_days')
            if atd is None:
                return ("unknown", "数据缺失")
            # 与上一期比较
            idx = records.index(rec)
            if idx < len(records) - 1:
                prev_atd = records[idx + 1].get('arturn_days')
                if prev_atd is not None:
                    change_pct = (atd - prev_atd) / prev_atd if prev_atd != 0 else 0
                    if change_pct > 0.15:
                        return ("worsening", f"大幅恶化 (+{change_pct * 100:.0f}%)")
                    elif change_pct > 0.05:
                        return ("worsening", f"轻微恶化 (+{change_pct * 100:.0f}%)")
                    elif change_pct < -0.05:
                        return ("improving", f"改善 ({change_pct * 100:.0f}%)")
                    else:
                        return ("stable", "基本稳定")
            # 绝对值判断
            if atd > 365:
                return ("worsening", f"严重: {atd:.0f}天 (>1年)")
            elif atd > 180:
                return ("worsening", f"偏高: {atd:.0f}天")
            elif atd > 90:
                return ("stable", f"正常偏高: {atd:.0f}天")
            else:
                return ("stable", f"健康: {atd:.0f}天")

        def _assess_deviation(rec) -> tuple:
            dev = rec.get('deviation')
            if dev is None:
                return ("unknown", "数据缺失")
            if dev > 0.2:
                return ("worsening", f"大幅偏离 (+{dev * 100:.0f}pp)")
            elif dev > 0.1:
                return ("worsening", f"明显偏离 (+{dev * 100:.0f}pp)")
            elif dev > 0.05:
                return ("stable", f"轻微偏离 (+{dev * 100:.0f}pp)")
            else:
                return ("stable", "正常")

        def _assess_provision(rec) -> tuple:
            """判定计提审慎性：如果周转恶化但计提比例反而下降 → 粉饰嫌疑"""
            impa = rec.get('impa_ratio')
            if impa is None:
                # 检查是否有 assets_impair_loss 作为替代
                return ("unknown", "信用减值损失数据缺失")
            idx = records.index(rec)
            # 当前计提比例
            curr_ratio = impa
            # 与上一期比较
            if idx < len(records) - 1:
                prev_rec = records[idx + 1]
                prev_ratio = prev_rec.get('impa_ratio')
                prev_atd = prev_rec.get('arturn_days')
                curr_atd = rec.get('arturn_days')
                if prev_ratio is not None and curr_atd is not None and prev_atd is not None:
                    ratio_change = (curr_ratio - prev_ratio) / prev_ratio if prev_ratio != 0 else 0
                    atd_change = (curr_atd - prev_atd) / prev_atd if prev_atd != 0 else 0
                    # 核心逻辑：周转恶化 + 计提下降 = 粉饰嫌疑
                    if atd_change > 0.05 and ratio_change < -0.1:
                        return ("worsening", f"⚠️ 粉饰嫌疑: 周转恶化({atd_change * 100:+.0f}%)但计提下降({ratio_change * 100:+.0f}%)")
                    elif atd_change > 0.05 and ratio_change > 0.1:
                        return ("stable", f"正常响应: 周转恶化({atd_change * 100:+.0f}%)→计提同步上升({ratio_change * 100:+.0f}%)")
                    elif atd_change < -0.05 and ratio_change < -0.1:
                        return ("stable", f"合理: 周转改善→计提下降")
                    else:
                        return ("stable", "基本稳定")
            return ("unknown", "缺少对比数据")

        # 最新一期评估
        turnover_status, turnover_detail = _assess_turnover(latest)
        dev_status, dev_detail = _assess_deviation(latest)
        provision_status, provision_detail = _assess_provision(latest)

        # 汇总信号
        signals = []
        if turnover_status == "worsening":
            signals.append(f"🔴 回收效率: {turnover_detail}")
        elif turnover_status == "stable":
            signals.append(f"🟡 回收效率: {turnover_detail}")
        else:
            signals.append(f"⬜ 回收效率: {turnover_detail}")

        if dev_status == "worsening":
            signals.append(f"🔴 收入质量: {dev_detail}")
        elif dev_status == "stable":
            signals.append(f"🟡 收入质量: {dev_detail}")
        else:
            signals.append(f"⬜ 收入质量: {dev_detail}")

        if provision_status == "worsening":
            signals.append(f"🔴 计提审慎性: {provision_detail}")
        elif provision_status == "stable":
            signals.append(f"🟢 计提审慎性: {provision_detail}")
        else:
            signals.append(f"⬜ 计提审慎性: {provision_detail}")

        for s in signals:
            lines.append(f"- {s}")

        # 综合评级
        worsening_count = sum(1 for status in [turnover_status, dev_status, provision_status] if status == "worsening")
        stable_count = sum(1 for status in [turnover_status, dev_status, provision_status] if status == "stable")
        unknown_count = sum(1 for status in [turnover_status, dev_status, provision_status] if status == "unknown")

        lines.append("")
        lines.append("## 🏷️ 综合风险评级")

        if worsening_count == 0 and unknown_count == 0:
            lines.append("> ✅ **低风险** — 三项指标均正常，应收账款质量健康")
        elif worsening_count == 1:
            if turnover_status == "worsening":
                lines.append("> ⚠️ **关注（回收恶化）** — 回款速度下降，关注客户回款能力和信用政策变化")
            elif dev_status == "worsening":
                lines.append("> ⚠️ **关注（收入质量问题）** — 应收账款膨胀速度超出营收增长，可能存在收入确认激进行为")
            else:
                lines.append("> ⚠️ **关注（计提问题）** — 计提行为异常")
        elif worsening_count == 2:
            if turnover_status == "worsening" and provision_status == "worsening":
                lines.append("> 🔴 **高风险 — 财务粉饰嫌疑** — 回款恶化 + 计提不升反降，公司可能在刻意压低减值以美化利润")
            elif turnover_status == "worsening" and dev_status == "worsening":
                lines.append("> 🔴 **高风险 — 双重恶化** — 收入质量下降同时回款困难，经营性现金流承压")
            elif dev_status == "worsening" and provision_status == "worsening":
                lines.append("> 🔴 **高风险 — 收入虚胖 + 计提不足** — 应收膨胀的同时减值准备不充分，利润表可信度存疑")
            else:
                lines.append("> 🔴 **高风险** — 两项指标恶化，需重点关注")
        elif worsening_count == 3:
            lines.append("> 🔴🔴 **极高风险 — 完美风暴** — 回收、收入质量、计提三者同时恶化，需高度警惕财务造假可能")
        elif unknown_count >= 2:
            lines.append("> ⬜ **数据不足** — 关键字段缺失，无法完成完整评估，建议检查数据源")
        else:
            lines.append("> 🟡 **无法判定** — 请结合具体指标手动评估")

        lines.append("")
        lines.append("---")
        lines.append("*说明: 增速偏离度 = 应收增速 - 营收增速，正值意味着应收账款膨胀快于收入增长，是'纸面富贵'信号*")
        lines.append("*计提审慎性 = 信用减值损失/应收账款，周转恶化时该比率应同步上升，若背离则存粉饰嫌疑*")
        lines.append("*数据来源: Tushare / MongoDB 缓存*")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ [应收账款风险分析] 执行失败: {e}", exc_info=True)
        return f"❌ 应收账款风险分析失败: {e}"