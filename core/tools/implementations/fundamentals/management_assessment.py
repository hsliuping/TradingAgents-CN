"""管理层评估数据获取工具 - A股审计意见、信息披露评级、股权激励、违规处罚

基于 Tushare Provider 的 stk_audit / disclosure_rating / equity_incentive / stk_penalty 接口
"""

import asyncio
import json
import logging
import threading
from typing import Optional

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _ticker_to_ts_code(ticker: str) -> str:
    """将通用 ticker 转为 Tushare ts_code 格式"""
    ticker = str(ticker).strip()
    if "." in ticker:
        return ticker  # 已经是 ts_code 格式
    # 纯数字，根据市场判断
    if ticker.startswith("6"):
        return f"{ticker}.SH"
    elif ticker.startswith(("0", "3")):
        return f"{ticker}.SZ"
    return f"{ticker}.SH"


def _run_async_in_thread(coro, timeout: int = 30):
    """在独立线程中运行异步协程"""
    container = {"result": None, "error": None}

    def _run():
        try:
            container["result"] = asyncio.run(coro)
        except Exception as exc:
            container["error"] = exc

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=timeout)
    if "error" in container and container["error"] is not None:
        raise container["error"]
    return container["result"]


@tool
@register_tool(
    tool_id="get_audit_opinion",
    name="审计意见查询",
    description="获取A股公司历史审计意见类型（标准无保留/带强调事项/保留/否定/无法表示）及审计机构、审计费用等，用于评估财务诚信",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["审计", "审计意见", "审计机构", "财务诚信", "A股", "管理层"],
    when_to_use="评估管理层财务诚信、检查审计意见异常、判断财务信息可靠性时使用",
    tool_role_hint="primary",
    output_shape="structured_records",
)
def get_audit_opinion(
    ticker: str = "600519",
    start_date: str = "2020-01-01",
    end_date: str = "2025-12-31",
) -> str:
    """获取A股公司审计意见

    Args:
        ticker: 股票代码，如 600519、000001
        start_date: 起始日期
        end_date: 截止日期
    """
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider.is_available():
            return json.dumps({"error": "Tushare 不可用（Token 未配置或库未安装）", "ticker": ticker}, ensure_ascii=False)

        ts_code = _ticker_to_ts_code(ticker)

        async def _fetch():
            return await provider.get_audit_opinion(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )

        df = _run_async_in_thread(_fetch())

        if df is None or df.empty:
            return json.dumps({
                "ticker": ticker,
                "ts_code": ts_code,
                "message": "未查询到审计意见数据",
                "records": [],
                "latest_opinion": "未知",
            }, ensure_ascii=False)

        records = []
        for _, row in df.iterrows():
            rec = {
                "公告日期": str(row.get("ann_date", row.get("公告日期", ""))),
                "报告期": str(row.get("end_date", row.get("报告期", ""))),
                "审计意见": str(row.get("audit_result", row.get("审计结果", ""))),
                "审计机构": str(row.get("audit_company", row.get("审计机构", ""))),
                "审计费用(元)": row.get("audit_fees", row.get("审计费用", "")),
            }
            records.append(rec)

        latest = records[0]["审计意见"] if records else "未知"
        return json.dumps({
            "ticker": ticker,
            "ts_code": ts_code,
            "total_records": len(records),
            "latest_opinion": latest,
            "records": records,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"❌ 审计意见查询失败: {e}")
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)


@tool
@register_tool(
    tool_id="get_disclosure_rating",
    name="信息披露评级查询",
    description="获取交易所对A股公司信息披露工作的年度考评结果（A/B/C/D），用于评估公司治理透明度",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["信息披露", "信披评级", "公司治理", "透明度", "A股", "管理层"],
    when_to_use="评估公司信息披露质量、检查交易所信披考评记录时使用",
    tool_role_hint="primary",
    output_shape="structured_records",
)
def get_disclosure_rating(
    ticker: str = "600519",
    end_date: str = "2025-12-31",
) -> str:
    """获取交易所信息披露考评结果

    Args:
        ticker: 股票代码，如 600519
        end_date: 截止报告期
    """
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider.is_available():
            return json.dumps({"error": "Tushare 不可用（Token 未配置或库未安装）", "ticker": ticker}, ensure_ascii=False)

        ts_code = _ticker_to_ts_code(ticker)

        async def _fetch():
            return await provider.get_disclosure_rating(
                ts_code=ts_code,
                end_date=end_date,
            )

        df = _run_async_in_thread(_fetch())

        if df is None or df.empty:
            return json.dumps({
                "ticker": ticker,
                "ts_code": ts_code,
                "message": "未查询到信息披露评级数据",
                "records": [],
                "latest_rating": "未知",
            }, ensure_ascii=False)

        # Tushare disclosure_rating 返回字段：ts_code, end_date, announcement_date, disclosure_result
        records = []
        for _, row in df.iterrows():
            rec = {
                "考评年度": str(row.get("end_date", row.get("考评年度", ""))),
                "考评结果": str(row.get("disclosure_result", row.get("考评结果", ""))),
            }
            records.append(rec)

        latest = records[0]["考评结果"] if records else "未知"
        return json.dumps({
            "ticker": ticker,
            "ts_code": ts_code,
            "total_records": len(records),
            "latest_rating": latest,
            "records": records,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"❌ 信息披露评级查询失败: {e}")
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)


@tool
@register_tool(
    tool_id="get_equity_incentive",
    name="股权激励计划查询",
    description="获取A股公司股权激励计划明细（激励方案、授予价格、行权条件、激励年限、总股本占比），用于评估管理层激励合理性",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["股权激励", "激励计划", "行权条件", "管理层激励", "A股", "管理层"],
    when_to_use="评估管理层股权激励合理性、检查激励覆盖率与行权条件、判断激励计划对股东利益的影响时使用",
    tool_role_hint="specialized",
    output_shape="structured_records",
)
def get_equity_incentive(
    ticker: str = "600519",
    start_date: str = "2020-01-01",
    end_date: str = "2025-12-31",
) -> str:
    """获取股权激励计划明细

    Args:
        ticker: 股票代码，如 600519
        start_date: 起始日期
        end_date: 截止日期
    """
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider.is_available():
            return json.dumps({"error": "Tushare 不可用（Token 未配置或库未安装）", "ticker": ticker}, ensure_ascii=False)

        ts_code = _ticker_to_ts_code(ticker)

        async def _fetch():
            return await provider.get_equity_incentive(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )

        df = _run_async_in_thread(_fetch())

        if df is None or df.empty:
            return json.dumps({
                "ticker": ticker,
                "ts_code": ts_code,
                "message": "未查询到股权激励计划数据",
                "has_incentive_plan": False,
                "records": [],
            }, ensure_ascii=False)

        records = []
        for _, row in df.iterrows():
            rec = {
                "公告日期": str(row.get("ann_date", row.get("公告日期", ""))),
                "激励方案": str(row.get("inc_plan", row.get("激励方案", ""))),
                "授予数量(万股)": str(row.get("grant_num", row.get("授予数量", ""))),
                "授予价格": str(row.get("grant_price", row.get("授予价格", ""))),
                "激励年限": str(row.get("inc_duration", row.get("激励年限", ""))),
                "行权条件": str(row.get("inc_perf", row.get("行权条件", ""))),
                "总股本占比": str(row.get("stockholder_rt", row.get("总股本占比", ""))),
            }
            records.append(rec)

        return json.dumps({
            "ticker": ticker,
            "ts_code": ts_code,
            "has_incentive_plan": True,
            "total_plans": len(records),
            "records": records,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"❌ 股权激励查询失败: {e}")
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)


@tool
@register_tool(
    tool_id="get_management_penalties",
    name="管理层违规处罚查询",
    description="获取A股公司及其管理层的历史违规处罚记录（处罚类型、处罚对象、处罚金额、违规事由），用于评估管理层行为风险",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["违规", "处罚", "管理层", "监管", "行为风险", "A股", "管理层"],
    when_to_use="评估管理层历史行为风险、检查违规处罚记录、判断公司合规文化时使用",
    tool_role_hint="primary",
    output_shape="structured_records",
)
def get_management_penalties(
    ticker: str = "600519",
    start_date: str = "2020-01-01",
    end_date: str = "2025-12-31",
) -> str:
    """获取管理层违规处罚记录

    Args:
        ticker: 股票代码，如 600519
        start_date: 起始日期
        end_date: 截止日期
    """
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider.is_available():
            return json.dumps({"error": "Tushare 不可用（Token 未配置或库未安装）", "ticker": ticker}, ensure_ascii=False)

        ts_code = _ticker_to_ts_code(ticker)

        async def _fetch():
            return await provider.get_management_penalties(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )

        df = _run_async_in_thread(_fetch())

        if df is None or df.empty:
            return json.dumps({
                "ticker": ticker,
                "ts_code": ts_code,
                "message": "未查询到违规处罚记录（近5年无违规记录，正面信号）",
                "has_penalties": False,
                "total_records": 0,
                "records": [],
            }, ensure_ascii=False)

        records = []
        for _, row in df.iterrows():
            rec = {
                "公告日期": str(row.get("ann_date", row.get("公告日期", ""))),
                "处罚类型": str(row.get("punish_type", row.get("处罚类型", ""))),
                "处罚对象": str(row.get("punish_object", row.get("处罚对象", ""))),
                "违规类型": str(row.get("violat_type", row.get("违规类型", ""))),
                "违规事由": str(row.get("violate_content", row.get("违规事由", "")))[:300],
                "处罚金额(万元)": str(row.get("punish_amount", row.get("处罚金额", ""))),
            }
            records.append(rec)

        return json.dumps({
            "ticker": ticker,
            "ts_code": ts_code,
            "has_penalties": True,
            "total_records": len(records),
            "records": records,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"❌ 违规处罚查询失败: {e}")
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)
