"""
统一股票基本面数据工具

自动识别股票类型（A股、港股、美股）并调用相应的数据源
"""

import asyncio
import concurrent.futures
import logging
import re
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _normalize_china_ticker(ticker: str) -> str:
    """标准化 A 股代码，兼容带交易所后缀的输入。"""
    return re.sub(r'\.(SZ|SH|BJ|sz|sh|bj)$', '', str(ticker).strip())


def _run_async_in_sync(coro):
    """在同步工具中安全运行异步 provider。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_runner)
        return future.result(timeout=120)


def _coerce_records(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, 'to_dict'):
        try:
            value = value.to_dict('records')
        except Exception:
            return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalize_financial_payload(raw_data: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """统一不同缓存/provider 的财务字段结构。"""
    normalized = {
        'income_statement': [],
        'balance_sheet': [],
        'cash_flow': [],
        'financial_indicators': [],
    }
    if not isinstance(raw_data, dict):
        return normalized

    payload = raw_data
    if isinstance(raw_data.get('raw_data'), dict):
        payload = raw_data['raw_data']
    elif isinstance(raw_data.get('financial_data'), dict):
        payload = raw_data['financial_data']

    normalized['income_statement'] = _coerce_records(payload.get('income_statement'))
    normalized['balance_sheet'] = _coerce_records(payload.get('balance_sheet'))
    normalized['cash_flow'] = _coerce_records(payload.get('cash_flow') or payload.get('cashflow_statement'))
    normalized['financial_indicators'] = _coerce_records(
        payload.get('financial_indicators') or payload.get('main_indicators')
    )
    return normalized


def _period_token(record: Dict[str, Any]) -> str:
    for field in ('end_date', 'report_period', 'period', 'ann_date', 'f_ann_date'):
        value = record.get(field)
        if value:
            token = re.sub(r'\D', '', str(value))
            if len(token) >= 8:
                return token[:8]
            return str(value)
    return 'unknown'


def _display_period(period_token: str) -> str:
    digits = re.sub(r'\D', '', str(period_token))
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    return str(period_token)


def _sort_and_trim_records(records: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    ordered = sorted(records, key=_period_token, reverse=True)
    return ordered[:limit]


def _load_recent_financial_data(ticker: str, limit: int = 4) -> Dict[str, Any]:
    """优先走缓存/持久化数据，缺失时再降级到在线 provider。"""
    from tradingagents.utils.stock_utils import StockUtils

    normalized_ticker = _normalize_china_ticker(ticker)
    market_info = StockUtils.get_market_info(ticker)
    payload = None
    data_source = 'unknown'

    try:
        from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider

        provider = OptimizedChinaDataProvider()
        if hasattr(provider, '_get_cached_raw_financial_data'):
            payload = _normalize_financial_payload(provider._get_cached_raw_financial_data(normalized_ticker))
            if any(payload.values()):
                data_source = 'optimized_cache'
    except Exception as exc:
        logger.warning(f"⚠️ 财务缓存读取失败: {exc}")

    if not payload or not any(payload.values()):
        try:
            from tradingagents.dataflows.providers.china.tushare import TushareProvider

            provider = TushareProvider()
            raw_data = _run_async_in_sync(
                provider.get_financial_data(normalized_ticker, report_type='quarterly', limit=limit)
            )
            payload = _normalize_financial_payload(raw_data)
            if any(payload.values()):
                data_source = 'tushare'
        except Exception as exc:
            logger.warning(f"⚠️ Tushare 财务数据获取失败: {exc}")

    if not payload or not any(payload.values()):
        try:
            from tradingagents.dataflows.providers.china.akshare import AKShareProvider

            provider = AKShareProvider()
            raw_data = _run_async_in_sync(provider.get_financial_data(normalized_ticker))
            payload = _normalize_financial_payload(raw_data)
            if any(payload.values()):
                data_source = 'akshare'
        except Exception as exc:
            logger.warning(f"⚠️ AKShare 财务数据获取失败: {exc}")

    payload = payload or _normalize_financial_payload(None)
    for key, records in payload.items():
        payload[key] = _sort_and_trim_records(records, limit)

    payload['ticker'] = normalized_ticker
    payload['market_info'] = market_info
    payload['data_source'] = data_source
    return payload


def _to_float(value: Any) -> Optional[float]:
    if value in (None, '', 'None', 'nan', 'NaN'):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(',', ''))
    except Exception:
        return None


def _format_value(value: Any, style: str = 'number') -> str:
    number = _to_float(value)
    if number is None:
        return str(value)
    if style == 'percent':
        return f"{number:.2f}%"
    if style == 'plain':
        return f"{number:.2f}"
    abs_number = abs(number)
    if abs_number >= 1e8:
        return f"{number / 1e8:,.2f}亿元"
    if abs_number >= 1e4:
        return f"{number / 1e4:,.2f}万元"
    return f"{number:,.2f}"


def _pick_value(record: Dict[str, Any], *fields: str) -> Any:
    for field in fields:
        value = record.get(field)
        if value not in (None, '', 'None', 'nan', 'NaN'):
            return value
    return None


def _metric_line(record: Dict[str, Any], label: str, fields: List[str], style: str = 'number') -> Optional[str]:
    value = _pick_value(record, *fields)
    if value is None:
        return None
    return f"- {label}: {_format_value(value, style)}"


def _index_by_period(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for record in records:
        indexed.setdefault(_period_token(record), record)
    return indexed


def _merge_recent_periods(*record_groups: List[Dict[str, Any]], limit: int = 4) -> List[str]:
    period_tokens = set()
    for records in record_groups:
        for record in records:
            period_tokens.add(_period_token(record))
    return sorted(period_tokens, reverse=True)[:limit]


@tool
@register_tool(
    tool_id="get_stock_fundamentals_unified",
    name="统一股票基本面数据",
    description="获取股票基本面分析数据，支持A股、港股、美股",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_stock_fundamentals_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    start_date: Annotated[Optional[str], "开始日期，格式：YYYY-MM-DD"] = None,
    end_date: Annotated[Optional[str], "结束日期，格式：YYYY-MM-DD"] = None,
    curr_date: Annotated[Optional[str], "当前日期，格式：YYYY-MM-DD"] = None
) -> str:
    """
    统一的股票基本面分析工具
    自动识别股票类型（A股、港股、美股）并调用相应的数据源
    支持基于分析级别的数据获取策略

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        start_date: 开始日期（可选，格式：YYYY-MM-DD）
        end_date: 结束日期（可选，格式：YYYY-MM-DD）
        curr_date: 当前日期（可选，格式：YYYY-MM-DD）

    Returns:
        str: 基本面分析数据和报告
    """
    logger.info(f"📊 [统一基本面工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"📊 [统一基本面工具] 股票类型: {market_info['market_name']}")

        # 设置默认日期
        if not curr_date:
            curr_date = datetime.now().strftime('%Y-%m-%d')

        # 基本面分析只需要最近的数据
        days_to_fetch = 10
        if not start_date:
            start_date = (datetime.now() - timedelta(days=days_to_fetch)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = curr_date

        result_data = []

        if is_china:
            # 中国A股
            logger.info(f"🇨🇳 [统一基本面工具] 处理A股数据...")

            try:
                # 获取最新股价信息
                recent_end_date = curr_date
                recent_start_date = (datetime.strptime(curr_date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')

                from tradingagents.dataflows.interface import get_china_stock_data_unified
                current_price_data = get_china_stock_data_unified(ticker, recent_start_date, recent_end_date)
                result_data.append(f"## A股当前价格信息\n{current_price_data}")
            except Exception as e:
                logger.error(f"❌ A股价格数据获取失败: {e}")
                result_data.append(f"## A股当前价格信息\n获取失败: {e}")

            try:
                # 获取基本面财务数据
                from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider
                analyzer = OptimizedChinaDataProvider()
                fundamentals_data = analyzer._generate_fundamentals_report(ticker, current_price_data if 'current_price_data' in locals() else "", "standard")
                result_data.append(f"## A股基本面财务数据\n{fundamentals_data}")
            except Exception as e:
                logger.error(f"❌ A股基本面数据获取失败: {e}")
                result_data.append(f"## A股基本面财务数据\n获取失败: {e}")

        elif is_hk:
            # 港股
            logger.info(f"🇭🇰 [统一基本面工具] 处理港股数据...")

            try:
                from tradingagents.dataflows.interface import get_hk_stock_data_unified
                hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)

                if hk_data and len(hk_data) > 100 and "❌" not in hk_data:
                    result_data.append(f"## 港股数据\n{hk_data}")
                else:
                    raise ValueError("港股数据质量不佳")
            except Exception as e:
                logger.error(f"❌ 港股数据获取失败: {e}")
                result_data.append(f"## 港股数据\n获取失败: {e}")

        else:
            # 美股
            logger.info(f"🇺🇸 [统一基本面工具] 处理美股数据...")

            try:
                from tradingagents.dataflows.interface import get_fundamentals_openai
                us_data = get_fundamentals_openai(ticker, curr_date)
                result_data.append(f"## 美股基本面数据\n{us_data}")
            except Exception as e:
                logger.error(f"❌ 美股数据获取失败: {e}")
                result_data.append(f"## 美股基本面数据\n获取失败: {e}")

        # 组合所有数据
        combined_result = f"""# {ticker} 基本面分析数据

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析日期**: {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""

        logger.info(f"📊 [统一基本面工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一基本面分析工具执行失败: {str(e)}"
        logger.error(f"❌ [统一基本面工具] {error_msg}")
        return error_msg


@tool
@register_tool(
    tool_id="get_financial_statements",
    name="最近季度财报明细",
    description="获取 A 股最近几个季度的利润表、资产负债表和核心财务指标明细",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_financial_statements(
    ticker: Annotated[str, "A股股票代码，支持 000001 或 000001.SZ 形式"],
    limit: Annotated[int, "返回最近几个季度，默认 4"] = 4
) -> str:
    """获取最近季度财报明细。"""
    try:
        limit = max(1, min(int(limit), 8))
        financial_data = _load_recent_financial_data(ticker, limit=limit)
        market_info = financial_data['market_info']

        if not market_info.get('is_china'):
            return f"{ticker} 当前仅支持中国A股财报明细查询，暂不支持 {market_info.get('market_name', '该市场')}。"

        income_records = financial_data['income_statement']
        balance_records = financial_data['balance_sheet']
        indicator_records = financial_data['financial_indicators']
        periods = _merge_recent_periods(income_records, balance_records, indicator_records, limit=limit)

        if not periods:
            return f"{financial_data['ticker']} 暂未获取到最近季度财报明细。"

        income_by_period = _index_by_period(income_records)
        balance_by_period = _index_by_period(balance_records)
        indicators_by_period = _index_by_period(indicator_records)

        result_lines = [
            f"# {financial_data['ticker']} 最近{len(periods)}个季度财报明细",
            "",
            f"**股票类型**: {market_info['market_name']}",
            f"**数据来源**: {financial_data['data_source']}",
            "",
        ]

        for period in periods:
            result_lines.append(f"## 报告期 {_display_period(period)}")

            income = income_by_period.get(period)
            if income:
                result_lines.append("### 利润表")
                for line in [
                    _metric_line(income, '营业总收入', ['total_revenue', 'revenue']),
                    _metric_line(income, '营业收入', ['revenue']),
                    _metric_line(income, '营业利润', ['operate_profit', 'oper_profit']),
                    _metric_line(income, '归母净利润', ['n_income_attr_p', 'net_profit']),
                    _metric_line(income, '净利润', ['n_income']),
                    _metric_line(income, '基本每股收益', ['basic_eps'], 'plain'),
                ]:
                    if line:
                        result_lines.append(line)

            balance = balance_by_period.get(period)
            if balance:
                result_lines.append("### 资产负债表")
                for line in [
                    _metric_line(balance, '资产总计', ['total_assets']),
                    _metric_line(balance, '负债合计', ['total_liab']),
                    _metric_line(balance, '股东权益合计', ['total_hldr_eqy_exc_min_int', 'total_equity']),
                    _metric_line(balance, '流动资产合计', ['total_cur_assets']),
                    _metric_line(balance, '流动负债合计', ['total_cur_liab']),
                    _metric_line(balance, '货币资金', ['money_cap', 'cash_and_equivalents']),
                ]:
                    if line:
                        result_lines.append(line)

            indicators = indicators_by_period.get(period)
            if indicators:
                result_lines.append("### 核心财务指标")
                for line in [
                    _metric_line(indicators, '净资产收益率 ROE', ['roe', 'roe_dt'], 'percent'),
                    _metric_line(indicators, '总资产收益率 ROA', ['roa'], 'percent'),
                    _metric_line(indicators, '毛利率', ['gross_margin', 'grossprofit_margin'], 'percent'),
                    _metric_line(indicators, '净利率', ['netprofit_margin', 'net_margin'], 'percent'),
                    _metric_line(indicators, '资产负债率', ['debt_to_assets', 'debt_to_asset'], 'percent'),
                    _metric_line(indicators, '流动比率', ['current_ratio'], 'plain'),
                ]:
                    if line:
                        result_lines.append(line)

            result_lines.append("")

        return "\n".join(result_lines).strip()

    except Exception as exc:
        logger.error(f"❌ [财报明细工具] 执行失败: {exc}", exc_info=True)
        return f"获取 {ticker} 最近季度财报明细失败: {exc}"


@tool
@register_tool(
    tool_id="get_cash_flow_statement",
    name="最近季度现金流量表",
    description="获取 A 股最近几个季度的现金流量表，并补充经营现金与利润匹配情况",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_cash_flow_statement(
    ticker: Annotated[str, "A股股票代码，支持 000001 或 000001.SZ 形式"],
    limit: Annotated[int, "返回最近几个季度，默认 4"] = 4
) -> str:
    """获取最近季度现金流量表。"""
    try:
        limit = max(1, min(int(limit), 8))
        financial_data = _load_recent_financial_data(ticker, limit=limit)
        market_info = financial_data['market_info']

        if not market_info.get('is_china'):
            return f"{ticker} 当前仅支持中国A股现金流量表查询，暂不支持 {market_info.get('market_name', '该市场')}。"

        cash_flow_records = financial_data['cash_flow']
        income_by_period = _index_by_period(financial_data['income_statement'])

        if not cash_flow_records:
            return f"{financial_data['ticker']} 暂未获取到最近季度现金流量表数据。"

        result_lines = [
            f"# {financial_data['ticker']} 最近{min(len(cash_flow_records), limit)}个季度现金流量表",
            "",
            f"**股票类型**: {market_info['market_name']}",
            f"**数据来源**: {financial_data['data_source']}",
            "",
        ]

        for cash_flow in cash_flow_records[:limit]:
            period = _period_token(cash_flow)
            result_lines.append(f"## 报告期 {_display_period(period)}")

            for line in [
                _metric_line(cash_flow, '经营活动现金流量净额', ['n_cashflow_act']),
                _metric_line(cash_flow, '投资活动现金流量净额', ['n_cashflow_inv_act']),
                _metric_line(cash_flow, '筹资活动现金流量净额', ['n_cash_flows_fnc_act', 'n_cashflow_fin_act']),
                _metric_line(cash_flow, '期初现金及现金等价物余额', ['c_cash_equ_beg_period']),
                _metric_line(cash_flow, '期末现金及现金等价物余额', ['c_cash_equ_end_period']),
            ]:
                if line:
                    result_lines.append(line)

            matched_income = income_by_period.get(period)
            operating_cash = _to_float(_pick_value(cash_flow, 'n_cashflow_act'))
            net_profit = None
            if matched_income:
                net_profit = _to_float(_pick_value(matched_income, 'n_income_attr_p', 'n_income', 'net_profit'))

            if operating_cash is not None and net_profit not in (None, 0):
                result_lines.append(f"- 经营现金净额/净利润: {operating_cash / net_profit:.2f} 倍")

            result_lines.append("")

        return "\n".join(result_lines).strip()

    except Exception as exc:
        logger.error(f"❌ [现金流工具] 执行失败: {exc}", exc_info=True)
        return f"获取 {ticker} 最近季度现金流量表失败: {exc}"

