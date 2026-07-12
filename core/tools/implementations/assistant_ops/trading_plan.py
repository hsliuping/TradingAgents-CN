"""
投资计划类工具

提供个人交易计划（Trading System）的查询功能，帮助用户回顾自己的投资纪律和规则。
"""

import logging
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)

# 中文标签映射
_STYLE_LABELS = {"short_term": "短线", "medium_term": "中线", "long_term": "长线"}
_RISK_LABELS = {"conservative": "保守", "balanced": "稳健", "aggressive": "激进"}
_STATUS_LABELS = {"draft": "草稿", "published": "已发布"}


def _fmt_rules_section(title: str, rules) -> str:
    """将规则对象/字典格式化为可读文本"""
    if not rules:
        return ""
    if hasattr(rules, "model_dump"):
        rules = rules.model_dump(exclude_defaults=True)
    if isinstance(rules, dict) and not rules:
        return ""
    import json
    # 简单的 key-value 展示
    lines = [f"\n【{title}】"]
    if isinstance(rules, dict):
        for k, v in rules.items():
            if v is None or v == [] or v == {}:
                continue
            if isinstance(v, list):
                lines.append(f"  {k}: {len(v)} 条规则")
                for i, item in enumerate(v[:5], 1):
                    if isinstance(item, dict):
                        desc = item.get("description", item.get("name", json.dumps(item, ensure_ascii=False)))
                    elif isinstance(item, str):
                        desc = item
                    else:
                        desc = json.dumps(item, ensure_ascii=False)
                    lines.append(f"    {i}. {desc}")
            elif isinstance(v, dict):
                lines.append(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
            else:
                lines.append(f"  {k}: {v}")
    return "\n".join(lines)


@tool
@register_tool(
    tool_id="list_trading_plans",
    name="查看投资计划列表",
    description="列出用户创建的所有个人交易计划（投资纪律）。返回每个计划的名称、风格、风险偏好、状态、版本和是否激活。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["trading_plan", "investment_plan", "list", "query", "assistant_ops", "trading_system", "plan_overview", "investment_discipline", "plan_listing", "trading_rules"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["查看投资计划列表", "浏览已有交易计划", "回顾投资纪律", "确认激活的计划"],
    when_to_use="当用户想查看自己创建的所有投资计划、了解每个计划的状态和风格时使用。",
    returns="返回文本格式的投资计划列表，包含名称、风格、风险偏好、状态、版本和是否激活。",
)
async def list_trading_plans() -> str:
    """列出用户的所有个人交易计划。"""
    try:
        from app.services.trading_system_service import get_trading_system_service

        user_id = require_current_user_id()
        service = get_trading_system_service()
        systems = service.list_systems(user_id)

        if not systems:
            return "还没有创建任何投资计划。可以在「投资计划」页面创建。"

        lines = [f"共 {len(systems)} 个投资计划：\n"]
        for s in systems:
            style = _STYLE_LABELS.get(s.style.value if hasattr(s.style, 'value') else s.style, s.style)
            risk = _RISK_LABELS.get(s.risk_profile.value if hasattr(s.risk_profile, 'value') else s.risk_profile, s.risk_profile)
            status = _STATUS_LABELS.get(s.status.value if hasattr(s.status, 'value') else s.status, s.status)
            active = "✅ 当前激活" if s.is_active else ""
            lines.append(f"- {s.name} | {style}/{risk} | {status} v{s.version} {active}")
            if s.description:
                lines.append(f"  {s.description}")
            if s.id:
                lines.append(f"  计划ID: {s.id}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[list_trading_plans] 获取投资计划列表失败: %s", e)
        return f"获取投资计划列表时出错: {e}"


@tool
@register_tool(
    tool_id="get_active_trading_plan",
    name="获取当前投资计划",
    description="获取用户当前激活的投资计划详情，包含选股规则、择时规则、仓位管理、止盈止损、纪律等完整内容。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["trading_plan", "investment_plan", "query", "active_plan", "assistant_ops", "trading_system", "plan_detail", "investment_discipline", "stock_selection", "risk_management", "position_management"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["查看当前激活的投资计划", "获取投资纪律详情", "回顾交易规则", "确认选股与止盈止损规则"],
    when_to_use="当用户想查看当前正在使用的投资计划的完整内容，包括选股规则、择时、仓位管理、止盈止损等时使用。",
    returns="返回文本格式的投资计划详情，包含各规则模块（选股/择时/仓位/止盈止损/纪律）和执行提醒。",
)
async def get_active_trading_plan() -> str:
    """获取当前激活的投资计划完整详情。"""
    try:
        from app.services.trading_system_service import get_trading_system_service

        user_id = require_current_user_id()
        service = get_trading_system_service()
        system = service.get_active_system(user_id)

        if not system:
            return "当前没有激活的投资计划。可以在「投资计划」页面创建并激活。"

        style = _STYLE_LABELS.get(system.style.value if hasattr(system.style, 'value') else system.style, system.style)
        risk = _RISK_LABELS.get(system.risk_profile.value if hasattr(system.risk_profile, 'value') else system.risk_profile, system.risk_profile)

        lines = [
            f"当前投资计划: {system.name} (v{system.version})",
            f"风格: {style} | 风险偏好: {risk}",
        ]
        if system.description:
            lines.append(f"描述: {system.description}")

        # 展示各规则模块
        lines.append(_fmt_rules_section("选股规则", system.stock_selection))
        lines.append(_fmt_rules_section("择时规则", system.timing))
        lines.append(_fmt_rules_section("仓位管理", system.position))
        lines.append(_fmt_rules_section("持仓规则", system.holding))
        lines.append(_fmt_rules_section("止盈止损", system.risk_management))
        lines.append(_fmt_rules_section("复盘规则", system.review))
        lines.append(_fmt_rules_section("纪律规则", system.discipline))

        warnings = service.get_system_validation_warnings(system)
        if warnings:
            lines.append("\n【执行提醒】")
            lines.extend([f"- {item}" for item in warnings])

        return "\n".join(line for line in lines if line)
    except Exception as e:
        logger.exception("[get_active_trading_plan] 获取投资计划失败: %s", e)
        return f"获取投资计划时出错: {e}"

