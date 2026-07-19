"""使用问答机器人工具：查询 Token 用量统计。

让使用问答助手能"看到"用户当前的 Token 用量、配额使用情况，
让京东云版用户能实时了解配额消耗速度，避免超额。

数据来源：
- 直接复用 UsageStatisticsService.get_usage_statistics() 拿详细统计
- 从环境变量 JDYUN_TOKEN_QUOTA 读取配额上限（仅京东云版有效）
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


def _format_tokens(value: Optional[int]) -> str:
    """格式化 token 数为人类可读字符串。"""
    if value is None:
        return "未知"
    try:
        v = int(value)
        if v >= 1_000_000:
            return f"{v / 1_000_000:.2f} M"
        if v >= 1_000:
            return f"{v / 1_000:.2f} K"
        return f"{v}"
    except Exception:
        return str(value)


def _resolve_token_quota() -> int:
    """读取 Token 配额上限（仅京东云版有效）。"""
    if os.getenv("JDYUN_MODE", "").strip().lower() in ("true", "1", "yes"):
        return int(os.getenv("JDYUN_TOKEN_QUOTA", "0") or "0")
    return 0


@tool
@register_tool(
    tool_id="get_token_usage",
    name="查询 Token 用量统计",
    description="查询 Token 用量统计：今日/本周/本月的已用 Token 数、配额上限、剩余配额、按模型分组的消耗、按任务分组的消耗。当用户问'今天用了多少 token''还剩多少配额''哪个模型消耗最多''Token 用量趋势'时使用。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "token_usage", "quota", "cost", "llm_usage", "api_usage"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=[
        "今天用了多少 token",
        "还剩多少配额",
        "Token 用量",
        "本周 Token 消耗",
        "哪个模型消耗最多",
        "Token 用量趋势",
        "配额什么时候重置",
        "还能用多少次分析",
    ],
    when_to_use="当用户问到 Token 用量、配额使用情况、模型消耗、API 调用成本时使用。支持 days 参数指定统计周期（默认 7 天）。",
    returns="返回文本格式的 Token 用量摘要，包含已用/配额/剩余/百分比/按模型分组消耗/按日期趋势。",
)
async def get_token_usage(
    days: Annotated[
        Optional[int],
        "统计周期天数（默认 7 天，可选 1/7/30，1=今日，7=本周，30=本月）。京东云版建议传 1 或 7。"
    ] = 7,
) -> str:
    """查询 Token 用量统计。"""
    from app.core.database import get_mongo_db
    from app.services.usage_statistics_service import usage_statistics_service

    # 触发用户上下文（虽然服务侧按全局统计，但保持一致性）
    require_current_user_id()

    # 规范化 days
    try:
        days_int = int(days) if days else 7
    except (TypeError, ValueError):
        days_int = 7
    if days_int < 1:
        days_int = 1
    if days_int > 365:
        days_int = 365

    db = get_mongo_db()
    is_jdyun = os.getenv("JDYUN_MODE", "").strip().lower() in ("true", "1", "yes")

    # 复用现有 service 拿详细统计
    try:
        stats = await usage_statistics_service.get_usage_statistics(days=days_int)
    except Exception as exc:
        logger.warning("[get_token_usage] 查询统计失败: %s", exc)
        return (
            "📊 Token 用量统计\n"
            "\n"
            f"❌ 查询失败: {exc}\n"
            "\n"
            "请稍后重试，或检查后端日志。"
        )

    used_tokens = (stats.total_input_tokens or 0) + (stats.total_output_tokens or 0)
    input_tokens = stats.total_input_tokens or 0
    output_tokens = stats.total_output_tokens or 0
    total_requests = stats.total_requests or 0
    quota_tokens = _resolve_token_quota()
    percentage = round((used_tokens / quota_tokens) * 100, 2) if quota_tokens > 0 else 0.0
    remaining_tokens = max(0, quota_tokens - used_tokens) if quota_tokens > 0 else 0

    # 配额重置时间
    reset_at = (datetime.utcnow() + timedelta(days=days_int)).strftime("%Y-%m-%d %H:%M UTC")

    # 按模型分组消耗（stats.by_model 是 dict: {model_name: {requests, input_tokens, output_tokens, cost, ...}}）
    by_model_dict = getattr(stats, "by_model", None) or {}
    # 按供应商分组消耗（stats.by_provider 是 dict）
    by_provider_dict = getattr(stats, "by_provider", None) or {}
    # 按日期趋势（stats.by_date 是 dict: {date_str: {...}}）
    by_date_dict = getattr(stats, "by_date", None) or {}

    lines = ["📊 Token 用量统计"]
    period_label = {1: "今日", 7: "本周", 30: "本月"}.get(days_int, f"近 {days_int} 天")
    lines.append(f"- 统计周期: {period_label}（{days_int} 天）")
    lines.append("")

    # 1) 总览
    lines.append("【1】用量总览")
    lines.append(f"- 已用 Token: {_format_tokens(used_tokens)}（输入 {_format_tokens(input_tokens)} + 输出 {_format_tokens(output_tokens)}）")
    lines.append(f"- 总请求数: {total_requests}")

    if quota_tokens > 0:
        lines.append(f"- 配额上限: {_format_tokens(quota_tokens)}")
        lines.append(f"- 剩余配额: {_format_tokens(remaining_tokens)}")
        lines.append(f"- 使用率: {percentage}%")
        lines.append(f"- 配额重置时间: {reset_at}")

        # 配额预警
        if percentage >= 90:
            lines.append("- 🔴 配额即将用尽，建议减少分析任务或等待重置")
        elif percentage >= 70:
            lines.append("- 🟡 配额消耗较快，建议关注用量")
        elif percentage >= 50:
            lines.append("- 🟢 配额使用过半，正常")
        else:
            lines.append("- 🟢 配额充足")
    else:
        lines.append("- 配额上限: 不限额（标准版默认）")

    # 2) 按模型分组消耗
    lines.append("")
    lines.append("【2】按模型分组消耗")
    if by_model_dict:
        # 按 total_tokens 降序排序，取 TOP 5
        sorted_models = sorted(
            by_model_dict.items(),
            key=lambda kv: (kv[1].get("input_tokens", 0) + kv[1].get("output_tokens", 0)),
            reverse=True,
        )
        for model_name, m_data in sorted_models[:5]:
            m_input = m_data.get("input_tokens", 0)
            m_output = m_data.get("output_tokens", 0)
            m_tokens = m_input + m_output
            m_requests = m_data.get("requests", 0)
            lines.append(f"  • {model_name}: {_format_tokens(m_tokens)} ({m_requests} 次)")
    else:
        lines.append("  - 无数据")

    # 3) 按供应商分组消耗
    lines.append("")
    lines.append("【3】按供应商分组消耗")
    if by_provider_dict:
        sorted_providers = sorted(
            by_provider_dict.items(),
            key=lambda kv: (kv[1].get("input_tokens", 0) + kv[1].get("output_tokens", 0)),
            reverse=True,
        )
        for provider_name, p_data in sorted_providers[:3]:
            p_tokens = p_data.get("input_tokens", 0) + p_data.get("output_tokens", 0)
            lines.append(f"  • {provider_name}: {_format_tokens(p_tokens)}")
    else:
        lines.append("  - 无数据")

    # 4) 按日期趋势
    lines.append("")
    lines.append("【4】每日用量趋势")
    if by_date_dict:
        # 按日期升序排序，取最近 7 天
        sorted_dates = sorted(by_date_dict.items(), key=lambda kv: kv[0], reverse=False)
        recent_dates = sorted_dates[-7:] if len(sorted_dates) > 7 else sorted_dates
        for date_str, d_data in recent_dates:
            d_tokens = d_data.get("input_tokens", 0) + d_data.get("output_tokens", 0)
            lines.append(f"  • {date_str}: {_format_tokens(d_tokens)}")
    else:
        lines.append("  - 无数据")

    # 5) 综合判断
    lines.append("")
    lines.append("💡 综合判断")
    if total_requests == 0:
        lines.append(f"- 近 {days_int} 天没有 LLM 调用记录，可能是分析任务未运行或统计未生效")
    else:
        avg_per_request = used_tokens // max(total_requests, 1)
        lines.append(f"- 平均每次请求消耗 {_format_tokens(avg_per_request)} Token")

        if is_jdyun:
            # 京东云版：估算还能跑多少次分析
            avg_analysis_cost = 50_000  # 单次单股分析约 5 万 token
            if quota_tokens > 0:
                remaining_analyses = remaining_tokens // avg_analysis_cost
                lines.append(f"- 按单次分析约 5 万 Token 估算，剩余可执行约 {remaining_analyses} 次单股分析")
            else:
                lines.append("- 京东云版未配置配额上限，请关注控制台用量告警")

        # 按日期趋势观察
        if by_date_dict:
            sorted_dates = sorted(by_date_dict.items(), key=lambda kv: kv[0], reverse=False)
            if len(sorted_dates) >= 2:
                last_date, last_data = sorted_dates[-1]
                prev_date, prev_data = sorted_dates[-2]
                last_tokens = last_data.get("input_tokens", 0) + last_data.get("output_tokens", 0)
                prev_tokens = prev_data.get("input_tokens", 0) + prev_data.get("output_tokens", 0)
                if prev_tokens > 0:
                    change_pct = ((last_tokens - prev_tokens) / prev_tokens) * 100
                    trend = "上升" if change_pct > 0 else "下降" if change_pct < 0 else "持平"
                    lines.append(f"- 最近一天用量 {_format_tokens(last_tokens)}，较前一日{trend} {abs(change_pct):.1f}%")

    if is_jdyun:
        lines.append("")
        lines.append("📌 说明：京东云版仅支持 GLM 系列模型，强制单并发，单次单股分析约消耗 5-10 万 Token")

    return "\n".join(lines)
