"""
统一股票基本面数据工具

自动识别股票类型（A股、港股、美股）并调用相应的数据源
"""

import asyncio
import concurrent.futures
import logging
import re
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool
import pandas as pd

from core.tools.base import register_tool
from core.tools.trade_date_policy import apply_stable_data_cutoff, build_stable_data_cutoff_note

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
    market_info = StockUtils.get_market_info(normalized_ticker)
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


def _snapshot_value(value: Any, default: str = 'N/A') -> str:
    if value in (None, '', 'None', 'nan', 'NaN'):
        return default
    return str(value)


def _format_pct_change(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return 'N/A'
    return f"{number:+.2f}%"


def _build_china_company_profile(ticker: str) -> Optional[str]:
    """构造不含实时价格字段的 A 股公司基础信息。"""
    normalized_ticker = _normalize_china_ticker(ticker)

    try:
        from tradingagents.dataflows.cache.app_adapter import get_basics_from_cache

        basics_doc = get_basics_from_cache(normalized_ticker)
        if isinstance(basics_doc, list):
            basics_doc = basics_doc[0] if basics_doc else None

        if not basics_doc:
            return None

        lines = [
            f"股票代码: {normalized_ticker}",
            f"股票名称: {_snapshot_value((basics_doc or {}).get('name') or (basics_doc or {}).get('stock_name'), '未知公司')}",
            f"所属地区: {_snapshot_value((basics_doc or {}).get('area'), '未知')}",
            f"所属行业: {_snapshot_value((basics_doc or {}).get('industry') or (basics_doc or {}).get('industry_name'), '未知')}",
            f"上市市场: {_snapshot_value((basics_doc or {}).get('market'), '未知')}",
            f"上市日期: {_snapshot_value((basics_doc or {}).get('list_date'), '未知')}",
        ]
        logger.info(f"📊 [统一基本面工具] 使用数据库静态信息构造 A 股公司概况: {normalized_ticker}")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning(f"⚠️ A股静态公司信息读取失败: {exc}")
        return None


def _build_china_snapshot_from_cache(ticker: str) -> Optional[str]:
    """优先从 app MongoDB 快照构造当前价格信息，避免为基本面工具拉取历史行情。"""
    normalized_ticker = _normalize_china_ticker(ticker)

    try:
        from tradingagents.dataflows.cache.app_adapter import get_basics_from_cache, get_market_quote_dataframe

        basics_doc = get_basics_from_cache(normalized_ticker)
        if isinstance(basics_doc, list):
            basics_doc = basics_doc[0] if basics_doc else None

        quote_df = get_market_quote_dataframe(normalized_ticker)
        if not basics_doc and (quote_df is None or quote_df.empty):
            return None

        lines = [
            f"股票代码: {normalized_ticker}",
            f"股票名称: {_snapshot_value((basics_doc or {}).get('name') or (basics_doc or {}).get('stock_name'), '未知公司')}",
            f"所属地区: {_snapshot_value((basics_doc or {}).get('area'), '未知')}",
            f"所属行业: {_snapshot_value((basics_doc or {}).get('industry') or (basics_doc or {}).get('industry_name'), '未知')}",
            f"上市市场: {_snapshot_value((basics_doc or {}).get('market'), '未知')}",
            f"上市日期: {_snapshot_value((basics_doc or {}).get('list_date'), '未知')}",
        ]

        current_price = 'N/A'
        change_pct = 'N/A'
        volume = 'N/A'
        if quote_df is not None and not quote_df.empty:
            latest_quote = quote_df.iloc[-1]
            current_price = _snapshot_value(latest_quote.get('close'))
            change_pct = _format_pct_change(latest_quote.get('pct_chg'))
            volume = _snapshot_value(latest_quote.get('volume'))

        lines.extend([
            f"当前价格: {current_price}",
            f"涨跌幅: {change_pct}",
            f"成交量: {volume}",
        ])
        logger.info(f"📊 [统一基本面工具] 使用数据库快照构造 A 股价格信息: {normalized_ticker}")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning(f"⚠️ A股数据库快照读取失败: {exc}")
        return None


def _is_placeholder_china_snapshot(snapshot: Optional[str]) -> bool:
    if not snapshot:
        return True
    markers = (
        '股票名称: 未知公司',
        '当前价格: N/A',
        '涨跌幅: N/A',
        '成交量: N/A',
    )
    return all(marker in snapshot for marker in markers)


def _get_china_price_snapshot(ticker: str, curr_date: str) -> str:
    """为统一基本面工具构造 A 股价格快照，优先读库，最后才降级到行情 provider。"""
    normalized_ticker = _normalize_china_ticker(ticker)

    cached_snapshot = _build_china_snapshot_from_cache(normalized_ticker)
    if cached_snapshot:
        return cached_snapshot

    try:
        from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider

        analyzer = OptimizedChinaDataProvider()
        snapshot = analyzer._get_stock_basic_info_only(normalized_ticker)
        if not _is_placeholder_china_snapshot(snapshot):
            logger.info(f"📊 [统一基本面工具] 使用基础信息接口构造 A 股价格信息: {normalized_ticker}")
            return snapshot
    except Exception as exc:
        logger.warning(f"⚠️ A股基础信息获取失败: {exc}")

    recent_end_date = curr_date
    recent_start_date = (datetime.strptime(curr_date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')
    from tradingagents.dataflows.interface import get_china_stock_data_unified

    logger.warning(f"⚠️ A股数据库快照不可用，降级到行情接口: {normalized_ticker}")
    return get_china_stock_data_unified(normalized_ticker, recent_start_date, recent_end_date)


def _strip_realtime_snapshot_fields(text: Optional[str]) -> str:
    """移除基本面研究中不应使用的实时快照字段。"""
    if not text:
        return ""

    dropped_markers = (
        '当前价格',
        '当前股价',
        '最新价格',
        '涨跌幅',
        '成交量',
        '总市值',
        '流通市值',
        '基本价格信息',
        '市盈率(PE)',
        '市盈率TTM(PE_TTM)',
        '市净率(PB)',
        '市销率(PS)',
        '股息收益率',
    )

    cleaned_lines: List[str] = []
    previous_blank = False
    for raw_line in str(text).splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped and any(marker in stripped for marker in dropped_markers):
            continue

        if not stripped:
            if previous_blank:
                continue
            previous_blank = True
            cleaned_lines.append("")
            continue

        previous_blank = False
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


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


def _quarter_from_period(period_token: str) -> Optional[int]:
    digits = re.sub(r'\D', '', str(period_token))
    if len(digits) != 8:
        return None

    return {
        '0331': 1,
        '0630': 2,
        '0930': 3,
        '1231': 4,
    }.get(digits[4:8])


def _previous_cumulative_period(period_token: str) -> Optional[str]:
    digits = re.sub(r'\D', '', str(period_token))
    if len(digits) != 8:
        return None

    quarter = _quarter_from_period(digits)
    if quarter in (None, 1):
        return None

    previous_suffix = {
        2: '0331',
        3: '0630',
        4: '0930',
    }[quarter]
    return f"{digits[:4]}{previous_suffix}"


def _derive_single_quarter_value(
    period_token: str,
    records_by_period: Dict[str, Dict[str, Any]],
    fields: List[str],
) -> Tuple[Optional[float], str]:
    current_record = records_by_period.get(period_token) or {}
    current_value = _to_float(_pick_value(current_record, *fields))
    if current_value is None:
        return None, 'missing-current'

    quarter = _quarter_from_period(period_token)
    if quarter == 1:
        return current_value, 'q1'

    previous_period = _previous_cumulative_period(period_token)
    if not previous_period:
        return None, 'missing-prev-period'

    previous_record = records_by_period.get(previous_period) or {}
    previous_value = _to_float(_pick_value(previous_record, *fields))
    if previous_value is None:
        return None, 'missing-prev-value'

    return current_value - previous_value, 'derived'


def _single_quarter_metric_line(
    period_token: str,
    records_by_period: Dict[str, Dict[str, Any]],
    label: str,
    fields: List[str],
    style: str = 'number',
) -> Optional[str]:
    value, status = _derive_single_quarter_value(period_token, records_by_period, fields)
    if value is not None:
        return f"- {label}: {_format_value(value, style)}"

    if status in {'missing-prev-period', 'missing-prev-value'}:
        return f"- {label}: N/A（缺少上期累计值，暂无法推导单季度）"

    return None


def _calculate_percentile_rank(values: List[float], current: float) -> Optional[float]:
    valid = [value for value in values if value is not None]
    if not valid:
        return None

    count = sum(1 for value in valid if value <= current)
    return count / len(valid) * 100


def _describe_percentile_band(percentile: Optional[float]) -> str:
    if percentile is None:
        return 'N/A'
    if percentile < 20:
        return '历史低位'
    if percentile < 40:
        return '历史中低位'
    if percentile < 60:
        return '历史中枢附近'
    if percentile < 80:
        return '历史中高位'
    return '历史高位'


def _build_historical_valuation_section_from_frame(
    valuation_df: pd.DataFrame,
    *,
    window_start: str,
    window_end: str,
    requested_analysis_date: Optional[str] = None,
    effective_analysis_date: Optional[str] = None,
) -> str:
    if valuation_df is None or valuation_df.empty:
        return "工具结果未提供历史估值分位数据。"

    working_df = valuation_df.copy()
    if 'trade_date' not in working_df.columns:
        return "工具结果未提供历史估值分位数据。"

    working_df['trade_date'] = working_df['trade_date'].astype(str)
    working_df = working_df.sort_values('trade_date', ascending=False)
    latest_available_trade_date = _display_period(str(working_df.iloc[0]['trade_date']))

    lines = [
        f"- 样本窗口: {window_start} 至 {window_end}",
        f"- 有效交易日样本: {len(working_df)}",
        f"- 最近可用估值快照日期: {latest_available_trade_date}",
        "- 估值快照口径: 下文如写“当前 PE/PB/PS(TTM)”等，均指该指标历史序列中最近可得且有效的交易日快照，而非实时盘口价格。",
        "- 日期说明: 每个指标后括号中的日期即该指标本次采用的估值快照日期；若不同指标可用样本不同，不默认视为同一交易日。不得用分析日期替代该快照日期。",
    ]

    cutoff_note = build_stable_data_cutoff_note(
        requested_analysis_date or "",
        effective_analysis_date or "",
        subject="估值分析所需的当日收盘后日频数据",
    )
    if cutoff_note:
        lines.append(f"- 稳定数据说明: {cutoff_note}")

    metric_specs = [
        ('pe', 'PE'),
        ('pe_ttm', 'PE(TTM)'),
        ('pb', 'PB'),
        ('ps_ttm', 'PS(TTM)'),
    ]

    any_metric = False
    for column, label in metric_specs:
        if column not in working_df.columns:
            lines.append(f"- {label}: 工具结果未提供历史序列，历史分位暂无法计算。")
            continue

        numeric_series = pd.to_numeric(working_df[column], errors='coerce')
        valid_df = working_df.loc[numeric_series.notna()].copy()
        valid_df[column] = pd.to_numeric(valid_df[column], errors='coerce')
        valid_df = valid_df[valid_df[column] > 0]

        if len(valid_df) < 60:
            lines.append(f"- {label}: 工具结果未提供足够历史样本，历史分位暂无法计算。")
            continue

        latest_row = valid_df.iloc[0]
        current_value = float(latest_row[column])
        percentile = _calculate_percentile_rank(valid_df[column].tolist(), current_value)
        median_value = float(valid_df[column].median())
        latest_trade_date = _display_period(str(latest_row['trade_date']))
        percentile_text = f"{percentile:.1f}%" if percentile is not None else 'N/A'
        band = _describe_percentile_band(percentile)

        lines.append(
            f"- {label}: 当前 {current_value:.2f} 倍（{latest_trade_date}） | 历史中位数 {median_value:.2f} 倍 | 历史分位 {percentile_text} | 历史位置: {band}"
        )
        any_metric = True

    lines.append("- PEG: 当前工具未提供稳定的日频 PEG 历史序列，历史分位暂无法计算。")

    if not any_metric:
        return "工具结果未提供可用于计算历史估值分位的有效估值序列。"

    return "\n".join(lines)


def _get_historical_valuation_summary(
    ticker: str,
    curr_date: str,
    *,
    lookback_years: int = 3,
) -> str:
    normalized_ticker = _normalize_china_ticker(ticker)

    requested_curr_date = curr_date
    stable_curr_date = apply_stable_data_cutoff(curr_date)
    if stable_curr_date != curr_date:
        logger.info(
            f"🕖 基本面历史估值输入日期 {requested_curr_date} 尚未达到稳定数据时点，按业务口径回退到 {stable_curr_date}"
        )
        curr_date = stable_curr_date
    try:
        end_dt = datetime.strptime(curr_date, '%Y-%m-%d')
    except Exception:
        end_dt = datetime.now()

    start_dt = end_dt - timedelta(days=365 * lookback_years)

    try:
        from tradingagents.dataflows.providers.china.tushare import TushareProvider

        provider = TushareProvider()
        if not provider.is_available():
            provider.connect_sync()
        if not provider.is_available() or provider.api is None:
            return "工具结果未提供历史估值分位数据。"

        ts_code = provider._normalize_ts_code(normalized_ticker)
        valuation_df = provider.api.daily_basic(
            ts_code=ts_code,
            start_date=start_dt.strftime('%Y%m%d'),
            end_date=end_dt.strftime('%Y%m%d'),
            fields='ts_code,trade_date,pe,pe_ttm,pb,ps_ttm',
        )

        return _build_historical_valuation_section_from_frame(
            valuation_df,
            window_start=start_dt.strftime('%Y-%m-%d'),
            window_end=end_dt.strftime('%Y-%m-%d'),
            requested_analysis_date=requested_curr_date,
            effective_analysis_date=curr_date,
        )
    except Exception as exc:
        logger.warning(f"⚠️ 历史估值分位计算失败: {exc}")
        return "工具结果未提供历史估值分位数据。"


@tool
@register_tool(
    tool_id="get_stock_fundamentals_unified",
    name="统一股票基本面数据",
    description="获取A股公司完整基本面数据：营收、净利润、ROE、ROIC、毛利率、净利率、资产负债率、每股收益等核心财务指标",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["基本面", "财务数据", "营收", "净利润", "ROE", "ROIC", "毛利率", "净利率", "每股收益", "资产负债率", "利润表", "资产负债表", "A股"],
    when_to_use="需要获取A股股票的营收、利润率、ROE/ROIC、资产负债等基本面财务数据时使用",
    tool_role_hint="primary",
    output_shape="structured_metrics",
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
            normalized_ticker = _normalize_china_ticker(ticker)
            company_profile_data = ""

            try:
                company_profile_data = _build_china_company_profile(normalized_ticker)
                if not company_profile_data:
                    from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider

                    analyzer = OptimizedChinaDataProvider()
                    company_profile_data = _strip_realtime_snapshot_fields(
                        analyzer._get_stock_basic_info_only(normalized_ticker)
                    )

                if company_profile_data:
                    result_data.append(f"## A股公司基础信息\n{company_profile_data}")
            except Exception as e:
                logger.error(f"❌ A股静态公司信息获取失败: {e}")

            result_data.append(
                "## A股基本面分析口径说明\n"
                "- 本工具面向历史财务、历史估值区间和已披露经营数据分析。\n"
                "- 不提供当前股价、涨跌幅、成交量、当前总市值等实时快照字段，也不应将这些字段作为基本面结论依据。"
            )
            result_data.append(
                "## A股估值快照日期说明\n"
                "- 估值快照口径: PE、PE(TTM)、PB、PS(TTM) 等估值指标如被表述为“当前值”，均指对应指标最近可得且有效的交易日快照，而非实时盘口价格。\n"
                "- 历史估值分位部分如已在指标后附带日期，该日期就是该指标本次采用的估值快照日期；若不同指标日期不同，不默认视为同一交易日。"
            )
            stable_curr_date = apply_stable_data_cutoff(curr_date)
            stable_note = build_stable_data_cutoff_note(
                curr_date,
                stable_curr_date,
                subject="估值分析所需的当日收盘后日频数据",
            )
            if stable_note:
                result_data.append(f"## A股数据日期说明\n- {stable_note}")

            try:
                # 获取基本面财务数据
                from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider
                analyzer = OptimizedChinaDataProvider()
                fundamentals_data = analyzer._generate_fundamentals_report(normalized_ticker, company_profile_data, "standard")
                fundamentals_data = _strip_realtime_snapshot_fields(fundamentals_data)
                result_data.append(f"## A股基本面财务数据\n{fundamentals_data}")
            except Exception as e:
                logger.error(f"❌ A股基本面数据获取失败: {e}")
                result_data.append(f"## A股基本面财务数据\n获取失败: {e}")

            try:
                historical_valuation = _get_historical_valuation_summary(normalized_ticker, curr_date)
                result_data.append(f"## A股历史估值分位\n{historical_valuation}")
            except Exception as e:
                logger.error(f"❌ A股历史估值分位获取失败: {e}")
                result_data.append("## A股历史估值分位\n工具结果未提供历史估值分位数据。")

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

        elif is_us:
            # 美股
            logger.info(f"🇺🇸 [统一基本面工具] 处理美股数据...")

            try:
                from tradingagents.dataflows.interface import get_fundamentals_openai
                us_data = get_fundamentals_openai(ticker, curr_date)
                result_data.append(f"## 美股基本面数据\n{us_data}")
            except Exception as e:
                logger.error(f"❌ 美股数据获取失败: {e}")
                result_data.append(f"## 美股基本面数据\n获取失败: {e}")

        else:
            logger.warning(f"⚠️ [统一基本面工具] 未识别的股票市场: {ticker} -> {market_info['market_name']}")
            result_data.append(
                f"## 市场识别结果\n{ticker} 未识别到受支持的股票市场，当前识别结果为 {market_info['market_name']}。"
            )

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
    description="获取A股最近几个季度的利润表（营业收入、营业成本、净利润等）、资产负债表和核心财务指标明细，并对主要利润表字段推导单季度口径",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["利润表", "资产负债表", "财务报表", "净利润", "营收", "营业收入", "营业成本", "A股", "财报"],
    when_to_use="需要获取A股公司的最新季度财务报表，包括利润表和资产负债表时使用",
    tool_role_hint="primary",
    output_shape="structured_metrics",
)
def get_financial_statements(
    ticker: Annotated[str, "A股股票代码，支持 000001 或 000001.SZ 形式"],
    limit: Annotated[int, "返回最近几个季度，默认 4"] = 4
) -> str:
    """获取最近季度财报明细。

    Args:
        ticker: A股股票代码，支持 "000001" 或 "000001.SZ" 形式
        limit: 返回最近几个季度（自动截断到 1-8），默认 4

    Returns:
        str: Markdown 格式字符串，包含以下章节——
            标题: "{ticker} 最近{N}个季度财报明细"
            股票类型: 市场名称
            数据来源: 数据来源说明
            口径说明: 关于累计值与单季度口径的说明
            各报告期章节（按 ## 报告期 分组），每个报告期下包含——
                - 利润表（单季度推导）: 营业总收入/营业利润/归母净利润/净利润的单季度推导值
                - 利润表（原始报告期累计/快照）: 营业总收入/营业利润/归母净利润/净利润/基本每股收益
                - 资产负债表: 资产总计/负债合计/股东权益合计/流动资产合计/流动负债合计/货币资金
                - 核心财务指标: ROE/ROA/毛利率/净利率/资产负债率/流动比率/单季度净利率（推导）

            若非 A 股市场返回提示字符串；
            若无数据返回 "{ticker} 暂未获取到最近季度财报明细。"；
            若异常返回 "获取 {ticker} 最近季度财报明细失败: ..." 字符串。
    """
    try:
        limit = max(1, min(int(limit), 8))
        load_limit = min(limit + 1, 8)
        financial_data = _load_recent_financial_data(ticker, limit=load_limit)
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
            "**口径说明**: A股利润表中的营业收入、归母净利润等字段通常为年初至报告期累计值，Q2/Q3/Q4 不是单季度值，不能直接相加或直接写成单季度逐季改善；如需估算单季度，通常应使用本期累计减上期累计（Q1 可近似视为单季度）。ROE、净利率等财务指标当前展示为对应报告期指标快照，未做单季度还原。",
            "",
        ]

        for period in periods:
            result_lines.append(f"## 报告期 {_display_period(period)}")

            income = income_by_period.get(period)
            if income:
                single_quarter_lines = [
                    _single_quarter_metric_line(period, income_by_period, '营业总收入（单季度推导）', ['total_revenue', 'revenue']),
                    _single_quarter_metric_line(period, income_by_period, '营业利润（单季度推导）', ['operate_profit', 'oper_profit']),
                    _single_quarter_metric_line(period, income_by_period, '归母净利润（单季度推导）', ['n_income_attr_p', 'net_profit']),
                    _single_quarter_metric_line(period, income_by_period, '净利润（单季度推导）', ['n_income']),
                ]
                if any(single_quarter_lines):
                    result_lines.append("### 利润表（单季度推导）")
                    for line in single_quarter_lines:
                        if line:
                            result_lines.append(line)

                result_lines.append("### 利润表（原始报告期累计/快照）")
                for line in [
                    _metric_line(income, '营业总收入（原始累计）', ['total_revenue', 'revenue']),
                    _metric_line(income, '营业利润（原始累计）', ['operate_profit', 'oper_profit']),
                    _metric_line(income, '归母净利润（原始累计）', ['n_income_attr_p', 'net_profit']),
                    _metric_line(income, '净利润（原始累计）', ['n_income']),
                    _metric_line(income, '基本每股收益（报告期）', ['basic_eps'], 'plain'),
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
                single_quarter_revenue, _ = _derive_single_quarter_value(period, income_by_period, ['total_revenue', 'revenue'])
                single_quarter_profit, _ = _derive_single_quarter_value(period, income_by_period, ['n_income_attr_p', 'net_profit'])
                for line in [
                    _metric_line(indicators, '报告期净资产收益率 ROE', ['roe', 'roe_dt'], 'percent'),
                    _metric_line(indicators, '报告期总资产收益率 ROA', ['roa'], 'percent'),
                    _metric_line(indicators, '报告期毛利率', ['grossprofit_margin', 'gross_margin'], 'percent'),
                    _metric_line(indicators, '报告期净利率', ['netprofit_margin', 'net_margin'], 'percent'),
                    _metric_line(indicators, '资产负债率', ['debt_to_assets', 'debt_to_asset'], 'percent'),
                    _metric_line(indicators, '流动比率', ['current_ratio'], 'plain'),
                ]:
                    if line:
                        result_lines.append(line)

                if single_quarter_revenue not in (None, 0) and single_quarter_profit is not None:
                    result_lines.append(
                        f"- 单季度净利率（推导）: {single_quarter_profit / single_quarter_revenue * 100:.2f}%"
                    )

            result_lines.append("")

        return "\n".join(result_lines).strip()

    except Exception as exc:
        logger.error(f"❌ [财报明细工具] 执行失败: {exc}", exc_info=True)
        return f"获取 {ticker} 最近季度财报明细失败: {exc}"


@tool
@register_tool(
    tool_id="get_cash_flow_statement",
    name="最近季度现金流量表",
    description="获取A股最近几个季度的现金流量表（经营现金流、投资现金流、筹资现金流、自由现金流），并对主要现金流字段推导单季度口径",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["现金流", "现金流量表", "经营现金流", "自由现金流", "FCF", "资本支出", "CAPEX", "折旧", "A股"],
    when_to_use="需要获取A股公司现金流量表，包括经营/投资/筹资现金流、自由现金流、资本支出等数据时使用",
    tool_role_hint="primary",
    output_shape="structured_metrics",
)
def get_cash_flow_statement(
    ticker: Annotated[str, "A股股票代码，支持 000001 或 000001.SZ 形式"],
    limit: Annotated[int, "返回最近几个季度，默认 4"] = 4
) -> str:
    """获取最近季度现金流量表。

    Args:
        ticker: A股股票代码，支持 "000001" 或 "000001.SZ" 形式
        limit: 返回最近几个季度（自动截断到 1-8），默认 4

    Returns:
        str: Markdown 格式字符串，包含以下章节——
            标题: "{ticker} 最近{N}个季度现金流量表"
            股票类型: 市场名称
            数据来源: 数据来源说明
            口径说明: 关于现金流累计值与单季度口径的说明
            各报告期章节（按 ## 报告期 分组），每个报告期下包含——
                - 现金流量表（单季度推导）: 经营/投资/筹资活动现金流量净额的单季度推导值
                - 现金流量表（原始报告期累计/快照）: 经营/投资/筹资活动现金流量净额、
                  期初/期末现金及现金等价物余额
                - 单季度经营现金净额/归母净利润（推导）: 比值
                - 报告期累计经营现金净额/归母净利润: 比值

            若非 A 股市场返回提示字符串；
            若无数据返回 "{ticker} 暂未获取到最近季度现金流量表数据。"；
            若异常返回 "获取 {ticker} 最近季度现金流量表失败: ..." 字符串。
    """
    try:
        limit = max(1, min(int(limit), 8))
        load_limit = min(limit + 1, 8)
        financial_data = _load_recent_financial_data(ticker, limit=load_limit)
        market_info = financial_data['market_info']

        if not market_info.get('is_china'):
            return f"{ticker} 当前仅支持中国A股现金流量表查询，暂不支持 {market_info.get('market_name', '该市场')}。"

        cash_flow_records = financial_data['cash_flow']
        income_by_period = _index_by_period(financial_data['income_statement'])

        if not cash_flow_records:
            return f"{financial_data['ticker']} 暂未获取到最近季度现金流量表数据。"

        display_cash_flows = cash_flow_records[:limit]

        result_lines = [
            f"# {financial_data['ticker']} 最近{len(display_cash_flows)}个季度现金流量表",
            "",
            f"**股票类型**: {market_info['market_name']}",
            f"**数据来源**: {financial_data['data_source']}",
            "**口径说明**: A股现金流量表中的经营活动现金流量净额等字段通常为年初至报告期累计值，Q2/Q3/Q4 不是单季度值，不能直接相加或直接写成单季度逐季改善；如需估算单季度，通常应使用本期累计减上期累计（Q1 可近似视为单季度）。",
            "",
        ]

        cash_flow_by_period = _index_by_period(cash_flow_records)

        for cash_flow in display_cash_flows:
            period = _period_token(cash_flow)
            result_lines.append(f"## 报告期 {_display_period(period)}")

            single_quarter_cash_lines = [
                _single_quarter_metric_line(period, cash_flow_by_period, '经营活动现金流量净额（单季度推导）', ['n_cashflow_act']),
                _single_quarter_metric_line(period, cash_flow_by_period, '投资活动现金流量净额（单季度推导）', ['n_cashflow_inv_act']),
                _single_quarter_metric_line(period, cash_flow_by_period, '筹资活动现金流量净额（单季度推导）', ['n_cash_flows_fnc_act', 'n_cashflow_fin_act']),
            ]
            if any(single_quarter_cash_lines):
                result_lines.append("### 现金流量表（单季度推导）")
                for line in single_quarter_cash_lines:
                    if line:
                        result_lines.append(line)

            result_lines.append("### 现金流量表（原始报告期累计/快照）")

            for line in [
                _metric_line(cash_flow, '经营活动现金流量净额（原始累计）', ['n_cashflow_act']),
                _metric_line(cash_flow, '投资活动现金流量净额（原始累计）', ['n_cashflow_inv_act']),
                _metric_line(cash_flow, '筹资活动现金流量净额（原始累计）', ['n_cash_flows_fnc_act', 'n_cashflow_fin_act']),
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

            single_quarter_operating_cash, _ = _derive_single_quarter_value(period, cash_flow_by_period, ['n_cashflow_act'])
            single_quarter_profit, _ = _derive_single_quarter_value(period, income_by_period, ['n_income_attr_p', 'n_income', 'net_profit'])

            if single_quarter_operating_cash is not None and single_quarter_profit not in (None, 0):
                result_lines.append(
                    f"- 单季度经营现金净额/归母净利润（推导）: {single_quarter_operating_cash / single_quarter_profit:.2f} 倍"
                )

            if operating_cash is not None and net_profit not in (None, 0):
                result_lines.append(f"- 报告期累计经营现金净额/归母净利润: {operating_cash / net_profit:.2f} 倍")

            result_lines.append("")

        return "\n".join(result_lines).strip()

    except Exception as exc:
        logger.error(f"❌ [现金流工具] 执行失败: {exc}", exc_info=True)
        return f"获取 {ticker} 最近季度现金流量表失败: {exc}"

