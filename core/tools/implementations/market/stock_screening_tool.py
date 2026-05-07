"""
全市场股票批量筛选工具

封装 EnhancedScreeningService / DatabaseScreeningService，
让 LLM 可以通过 function calling 按条件批量筛选 A 股。
"""

import asyncio
import concurrent.futures
import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from app.services.factor_registry_service import build_screening_fields_markdown, build_screening_tool_description
from core.tools.base import register_tool

logger = logging.getLogger(__name__)

SUPPORTED_FIELDS_DOC = """
支持的筛选字段：
{fields_markdown}

支持的操作符：> < >= <= == != between in not_in contains
- between 的 value 为 [最小值, 最大值]
- in / not_in 的 value 为列表
""".format(fields_markdown=build_screening_fields_markdown(public_only=True))


@tool
@register_tool(
    tool_id="screen_stocks_by_criteria",
    name="全市场股票批量筛选",
    description=build_screening_tool_description(),
    category="screening",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
)
def screen_stocks_by_criteria(
    conditions_json: Annotated[
        str,
        (
            '筛选条件 JSON 数组，格式: [{"field": "pe", "operator": "<", "value": 15}, '
            '{"field": "total_mv", "operator": ">", "value": 50}]。'
            "field 为字段名，operator 为操作符，value 为比较值。"
            "between 操作符的 value 格式为 [最小值, 最大值]，in/not_in 为列表。"
        )
    ],
    limit: Annotated[int, "返回数量，默认 20，最大 100"] = 20,
    order_by_field: Annotated[str, "排序字段，如 pe/pb/roe/total_mv，默认按总市值降序"] = "total_mv",
    order_direction: Annotated[str, "排序方向：asc（升序）或 desc（降序），默认 desc"] = "desc",
) -> str:
    """全市场 A 股批量筛选工具。

    {supported_fields_doc}
    """
    try:
        # 解析条件
        try:
            raw_conditions = json.loads(conditions_json)
        except json.JSONDecodeError as e:
            return f"错误：conditions_json 格式不正确，请传入合法的 JSON 数组。详情：{e}"

        if not isinstance(raw_conditions, list) or len(raw_conditions) == 0:
            return "错误：conditions_json 必须是非空的 JSON 数组。"

        limit = max(1, min(limit, 100))

        # 运行异步筛选
        # 使用独立线程运行，避免与外层 asyncio 事件循环冲突
        def _run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    _run_screening(raw_conditions, limit, order_by_field, order_direction)
                )
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_thread)
            result = future.result(timeout=60)
        return result

    except Exception as e:
        logger.error(f"screen_stocks_by_criteria 执行失败: {e}", exc_info=True)
        return f"筛选执行失败：{e}"


async def _run_screening(
    raw_conditions: list,
    limit: int,
    order_by_field: str,
    order_direction: str,
) -> str:
    """异步调用 DatabaseScreeningService 执行筛选"""
    from app.core.database import init_database, get_mongo_db
    from app.services.database_screening_service import get_database_screening_service

    # 确保数据库已初始化
    try:
        await init_database()
    except Exception:
        pass  # 可能已经初始化

    service = get_database_screening_service()

    order_by = [{"field": order_by_field, "direction": order_direction}]

    items, total = await service.screen_stocks(
        conditions=raw_conditions,
        limit=limit,
        offset=0,
        order_by=order_by,
    )

    if total == 0 or not items:
        return "未找到符合条件的股票。请尝试放宽筛选条件。"

    # 格式化输出
    lines = [f"共找到 {total} 只符合条件的股票，以下展示前 {len(items)} 只：\n"]
    for i, item in enumerate(items, 1):
        code = item.get("code") or item.get("symbol", "")
        name = item.get("name", "")
        industry = item.get("industry", "-")
        pe = item.get("pe") or item.get("pe_ttm", "-")
        pb = item.get("pb") or item.get("pb_mrq", "-")
        ps_ttm = item.get("ps_ttm")
        roe = item.get("roe", "-")
        total_mv = item.get("total_mv", "-")
        close = item.get("close", "-")
        pct_chg = item.get("pct_chg", "-")
        roa = item.get("roa")
        gross_margin = item.get("gross_margin")
        netprofit_margin = item.get("netprofit_margin")
        revenue_ttm = item.get("revenue_ttm")
        net_profit_ttm = item.get("net_profit_ttm")
        n_cashflow_act = item.get("n_cashflow_act")
        debt_to_assets = item.get("debt_to_assets")
        assets_to_eqt = item.get("assets_to_eqt")
        current_ratio = item.get("current_ratio")
        quick_ratio = item.get("quick_ratio")
        cash_ratio = item.get("cash_ratio")
        dividend_yield = item.get("dividend_yield")
        peg = item.get("peg")
        roic = item.get("roic")
        cash_conversion = item.get("cash_conversion")
        accrual_ratio = item.get("accrual_ratio")
        asset_turnover = item.get("asset_turnover")
        gross_profit_to_assets = item.get("gross_profit_to_assets")
        interest_coverage = item.get("interest_coverage")
        inventory_turnover = item.get("inventory_turnover")
        receivable_turnover = item.get("receivable_turnover")
        net_cash_position = item.get("net_cash_position")
        piotroski_f_score = item.get("piotroski_f_score")
        altman_z_score = item.get("altman_z_score")
        beneish_m_score = item.get("beneish_m_score")
        revenue_yoy = item.get("revenue_yoy")
        revenue_cagr_3y = item.get("revenue_cagr_3y")
        net_profit_yoy = item.get("net_profit_yoy")
        profit_cagr_3y = item.get("profit_cagr_3y")
        oper_profit_yoy = item.get("oper_profit_yoy")
        fcf = item.get("fcf")
        fcf_yield = item.get("fcf_yield")
        fcf_margin = item.get("fcf_margin")
        ocf_yield = item.get("ocf_yield")
        net_working_capital = item.get("net_working_capital")
        working_capital_change = item.get("working_capital_change")
        report_period = item.get("report_period")
        is_st = item.get("is_st")
        factor_diagnostics = item.get("factor_diagnostics") or {}
        factor_warnings = item.get("factor_warnings") or {}

        pe_str = f"{pe:.2f}" if isinstance(pe, (int, float)) else str(pe)
        pb_str = f"{pb:.2f}" if isinstance(pb, (int, float)) else str(pb)
        ps_str = f"{ps_ttm:.2f}" if isinstance(ps_ttm, (int, float)) else str(ps_ttm)
        roe_str = f"{roe:.2f}%" if isinstance(roe, (int, float)) else str(roe)
        mv_str = f"{total_mv:.2f}亿" if isinstance(total_mv, (int, float)) else str(total_mv)
        price_str = f"{close:.2f}元" if isinstance(close, (int, float)) else str(close)
        chg_str = f"{pct_chg:+.2f}%" if isinstance(pct_chg, (int, float)) else str(pct_chg)

        # 可选扩展指标
        extra_parts = []
        if roa is not None:
            extra_parts.append(f"ROA={roa:.2f}%")
        if gross_margin is not None:
            extra_parts.append(f"毛利率={gross_margin:.1f}%")
        if netprofit_margin is not None:
            extra_parts.append(f"净利率={netprofit_margin:.1f}%")
        if revenue_ttm is not None:
            extra_parts.append(f"营收TTM={revenue_ttm / 1e8:.2f}亿")
        if net_profit_ttm is not None:
            extra_parts.append(f"净利TTM={net_profit_ttm / 1e8:.2f}亿")
        if n_cashflow_act is not None:
            extra_parts.append(f"经营现金流={n_cashflow_act / 1e8:.2f}亿")
        if debt_to_assets is not None:
            extra_parts.append(f"负债率={debt_to_assets:.1f}%")
        if assets_to_eqt is not None:
            extra_parts.append(f"权益乘数={assets_to_eqt:.2f}")
        if current_ratio is not None:
            extra_parts.append(f"流动比率={current_ratio:.2f}")
        if quick_ratio is not None:
            extra_parts.append(f"速动比率={quick_ratio:.2f}")
        if cash_ratio is not None:
            extra_parts.append(f"现金比率={cash_ratio:.2f}")
        if dividend_yield is not None:
            extra_parts.append(f"股息率={dividend_yield:.2f}%")
        if peg is not None:
            extra_parts.append(f"PEG={peg:.2f}")
        if roic is not None:
            extra_parts.append(f"ROIC={roic:.2f}%")
        if cash_conversion is not None:
            extra_parts.append(f"利润现金转换率={cash_conversion:.2f}")
        if accrual_ratio is not None:
            extra_parts.append(f"应计利润比率={accrual_ratio:.2f}%")
        if asset_turnover is not None:
            extra_parts.append(f"资产周转率={asset_turnover:.2f}")
        if gross_profit_to_assets is not None:
            extra_parts.append(f"毛利资产比={gross_profit_to_assets:.2f}%")
        if interest_coverage is not None:
            extra_parts.append(f"利息保障={interest_coverage:.2f}x")
        if inventory_turnover is not None:
            extra_parts.append(f"存货周转={inventory_turnover:.2f}")
        if receivable_turnover is not None:
            extra_parts.append(f"应收周转={receivable_turnover:.2f}")
        if net_cash_position is not None:
            extra_parts.append(f"净现金头寸={net_cash_position:.2f}%")
        if piotroski_f_score is not None:
            extra_parts.append(f"F-Score={piotroski_f_score:.0f}")
        if altman_z_score is not None:
            extra_parts.append(f"AltmanZ={altman_z_score:.2f}")
        if beneish_m_score is not None:
            extra_parts.append(f"BeneishM={beneish_m_score:.2f}")
        if revenue_yoy is not None:
            extra_parts.append(f"营收同比={revenue_yoy:.2f}%")
        if revenue_cagr_3y is not None:
            extra_parts.append(f"营收3Y CAGR={revenue_cagr_3y:.2f}%")
        if net_profit_yoy is not None:
            extra_parts.append(f"净利同比={net_profit_yoy:.2f}%")
        if profit_cagr_3y is not None:
            extra_parts.append(f"净利3Y CAGR={profit_cagr_3y:.2f}%")
        if oper_profit_yoy is not None:
            extra_parts.append(f"营业利润同比={oper_profit_yoy:.2f}%")
        if fcf is not None:
            extra_parts.append(f"FCF={fcf / 1e8:.2f}亿")
        if fcf_yield is not None:
            extra_parts.append(f"FCF收益率={fcf_yield:.2f}%")
        if fcf_margin is not None:
            extra_parts.append(f"FCF率={fcf_margin:.2f}%")
        if ocf_yield is not None:
            extra_parts.append(f"经营现金流收益率={ocf_yield:.2f}%")
        if net_working_capital is not None:
            extra_parts.append(f"净营运资本={net_working_capital:.2f}亿")
        if working_capital_change is not None:
            extra_parts.append(f"营运资本变动={working_capital_change:.2f}亿")
        if report_period:
            extra_parts.append(f"财报期={report_period}")
        if is_st is True:
            extra_parts.append("⚠️ ST")
        if factor_diagnostics:
            diagnosis_parts = []
            for field_name, label in [
                ("piotroski_f_score", "F-Score"),
                ("altman_z_score", "AltmanZ"),
                ("beneish_m_score", "BeneishM"),
            ]:
                diagnostic = factor_diagnostics.get(field_name) or {}
                state = diagnostic.get("data_quality_state")
                if state:
                    diagnosis_parts.append(f"{label}缺失={state}")
            if diagnosis_parts:
                extra_parts.append("; ".join(diagnosis_parts))
        if factor_warnings:
            warning_parts = []
            for field_name, payload in factor_warnings.items():
                categories = payload.get("warning_categories") or []
                conditions = payload.get("warning_conditions") or []
                category_str = "/".join(str(category) for category in categories) if categories else "warning"
                condition_str = str(conditions[0]) if conditions else "triggered"
                warning_parts.append(f"{field_name}={category_str}:{condition_str}")
            if warning_parts:
                extra_parts.append("Warnings=" + "; ".join(warning_parts))
        extra_str = (" | " + " ".join(extra_parts)) if extra_parts else ""

        lines.append(
            f"{i}. {code} {name}（{industry}）"
            f" | PE={pe_str} PB={pb_str} PS={ps_str} ROE={roe_str}"
            f" | 市值={mv_str} 股价={price_str} 涨跌={chg_str}"
            f"{extra_str}"
        )

    return "\n".join(lines)

