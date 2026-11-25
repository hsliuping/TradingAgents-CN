"""估值测算表格生成工具（A10-D2）

智能助手可声明调用的确定性交付物工具：
  数据自动装配（valuation_bundle_builder）
  → LLM 生成模型规格（valuation_spec_generator）
  → Excel 渲染 + 文件校验（valuation_excel）

固定分析流程零改动；工具返回 Markdown（含下载链接与数据来源声明）。
"""

import logging
import time
from typing import Annotated

from langchain_core.tools import tool

from core.deliverables.valuation_bundle_builder import ValuationDataError, build_valuation_bundle
from core.deliverables.valuation_excel import (
    render_valuation_excel,
    validate_valuation_excel,
    ValuationSpecError,
)
from core.deliverables.valuation_spec_generator import generate_valuation_spec
from core.tools.base import register_tool

logger = logging.getLogger(__name__)

_OUTPUT_DIR = "data/deliverables"


def _resolve_spec_llm():
    """构建规格生成 LLM（模型解析链与 agent_executor 一致，openai 兼容接入）"""
    from app.core.database import get_mongo_db_sync
    from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
    from core.llm.models import LLMConfig, LLMProvider
    from core.llm.unified_client import UnifiedLLMClient

    db = get_mongo_db_sync()
    config_doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)]) or {}
    default_models = config_doc.get("default_models") or {}
    system_settings = config_doc.get("system_settings") or {}

    target_model = (
        default_models.get("deep_reasoning_model")
        or system_settings.get("deep_reasoning_model")
        or default_models.get("deep_analysis_model")
        or system_settings.get("deep_analysis_model")
    )
    if not target_model:
        raise RuntimeError("系统未配置深度分析模型（deep_reasoning_model / deep_analysis_model）")

    provider_info = get_provider_and_url_by_model_sync(target_model)
    if not provider_info:
        raise RuntimeError(f"无法获取模型 {target_model} 的供应商配置")

    # 估值规格 JSON 结构化输出：经 OpenAI 兼容适配器统一接入（火山方舟/百炼等均兼容）
    llm = UnifiedLLMClient.from_config(
        LLMConfig(
            provider=LLMProvider.OPENAI,
            model=target_model,
            api_key=provider_info.get("api_key"),
            base_url=provider_info.get("backend_url"),
            temperature=0.2,
            max_tokens=4096,
            timeout=300,
        )
    )
    return target_model, llm


def _format_failure(title: str, detail: str) -> str:
    return f"### 估值测算表生成失败\n\n**{title}**\n\n{detail}\n\n*请先完成数据同步或调整需求后再试。*"


@tool
@register_tool(
    tool_id="generate_valuation_excel_tool",
    name="估值测算表格生成",
    description=(
        "基于本地同步的年报财务数据与最新行情，生成未来 1-3 年盈利推演与 PE 估值情景测算表"
        "（xlsx 文件，含真实 Excel 公式与可编辑假设格）。"
        "当用户明确要求'估值测算表格''盈利测算表''估值模型 Excel'等文件交付物时调用。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="heavy",
    capability_tags=[
        "valuation_excel", "earnings_forecast", "pe_valuation",
        "financial_modeling", "target_price_scenario", "deliverable_generation",
    ],
    tool_role_hint="specialized",
    output_shape="structured_markdown",
    when_to_use=(
        "当用户明确要求生成估值测算表格、盈利推演模型、估值情景 Excel 等文件交付物时调用；"
        "生成前系统会自动校验年报/行情/股本数据是否已同步。"
    ),
    when_not_to_use=(
        "以下情况不要调用：1) 用户仅询问估值指标（PE/PB/市值）或一般性估值知识，"
        "直接回答或使用行情/财务查询工具；2) 用户要求把**对话中已经生成的数据、表格、"
        "预测结果**（如销量预测、营收测算等非估值模型）做成/导出 Excel——这不需要建模，"
        "必须改用 export_table_excel_tool（秒级导出，本工具会重新建模耗时数分钟）。"
    ),
    returns=(
        "Markdown 文本：生成结果、估值情景目标价摘要表、文件下载链接、数据来源说明；"
        "数据未同步或规格校验失败时返回明确的失败原因。"
    ),
    example="generate_valuation_excel_tool(symbol='601127', forecast_years=2)",
    related_tools=["get_historical_financial_annual_series_tool"],
)
def generate_valuation_excel_tool(
    symbol: Annotated[str, "A 股股票代码，6 位数字，如 601127"],
    context_notes: Annotated[str, "可选：当前分析中的研究结论/盈利预期摘要，作为测算假设的参考依据"] = "",
    forecast_years: Annotated[int, "预测年数，1-3，默认 2"] = 2,
) -> str:
    """生成估值测算 Excel 表格（盈利推演 + 估值情景）。

    Args:
        symbol: A 股股票代码，6 位数字
        context_notes: 可选研究结论摘要
        forecast_years: 预测年数（1-3）

    Returns:
        Markdown 文本（结果摘要 + 下载链接，或明确失败说明）
    """
    t0 = time.time()
    try:
        # 1. 数据自动装配（缺失即明确报错，不估算补位）
        try:
            bundle = build_valuation_bundle(symbol, context_notes=context_notes, forecast_years=forecast_years)
        except ValuationDataError as exc:
            return _format_failure("必需数据未同步", str(exc))

        # 2. LLM 生成模型规格（校验失败自动反馈重试）
        try:
            model_name, llm = _resolve_spec_llm()
        except Exception as exc:  # noqa: BLE001
            logger.error("[ValuationExcelTool] LLM 构建失败: %s", exc, exc_info=True)
            return _format_failure("模型配置不可用", str(exc))

        spec_result = generate_valuation_spec(bundle, llm, max_attempts=3)
        if not spec_result.get("passed"):
            errors = "\n".join(f"- {e}" for e in (spec_result.get("errors") or ["未知原因"]))
            return _format_failure(
                f"模型规格生成未通过校验（{spec_result.get('attempts')} 次尝试）", errors
            )
        spec = spec_result["spec"]

        # 3. 渲染 Excel
        from datetime import datetime

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"valuation_{bundle['ticker']}_{stamp}.xlsx"
        output_path = f"{_OUTPUT_DIR}/{filename}"
        try:
            render_valuation_excel(spec, output_path)
        except ValuationSpecError as exc:
            return _format_failure("规格渲染被阻断", str(exc))

        # 4. 重开文件校验
        check = validate_valuation_excel(spec, output_path)
        if not check.get("passed"):
            errors = "\n".join(f"- {e}" for e in (check.get("errors") or ["未知原因"]))
            return _format_failure("生成文件校验未通过", errors)

        # 签名下载链接：浏览器直接点击不带 JWT 头，必须用 presigned URL 鉴权
        from core.deliverables.download_links import sign_deliverable_query

        download_url = f"/api/assistant/deliverables/{filename}?{sign_deliverable_query(filename)}"

        # 5. 组装结果 Markdown
        scenarios = check.get("summary", {}).get("scenarios", {})
        scenario_rows = "\n".join(
            f"| {name} | PE | {scen['eps']:.3f} | {scen['target_price']:.2f} |"
            for name, scen in scenarios.items()
        )
        elapsed = time.time() - t0
        data_notes = "；".join(bundle.get("data_notes") or []) or "数据来源：本地同步年报（Tushare/AKShare）与最新行情"
        warnings = check.get("warnings") or []
        warning_lines = ""
        if warnings:
            warning_lines = "\n\n**提示**：\n" + "\n".join(f"- {w}" for w in warnings)

        return (
            f"### 估值测算表已生成 ✅\n\n"
            f"**{bundle['stock_name']}（{bundle['ticker']}）** · 现价 {bundle['current_price']:.2f} 元"
            f" · 总股本 {bundle['share_count']:.2f} 亿股 · 生成耗时 {elapsed:.0f} 秒\n\n"
            f"**估值情景（EPS 基准 → 目标价）**\n\n"
            f"| 情景 | 方法 | EPS（元） | 目标价（元） |\n"
            f"|------|------|-----------|--------------|\n"
            f"{scenario_rows}\n\n"
            f"📎 [下载估值测算表]({download_url})\n\n"
            f"表格含两个 Sheet：盈利推演（营收/净利率假设格可编辑，公式自动联动）与估值情景（PE 倍数可调）。"
            f"{warning_lines}\n\n"
            f"**数据口径**：{data_notes}\n\n"
            f"*本表格由 AI 生成（模型：{model_name}），仅作研究参考，不构成投资建议。*"
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[ValuationExcelTool] 生成失败: %s", exc, exc_info=True)
        return _format_failure("执行异常", str(exc))
