"""
持仓分析类工具

提供持仓列表查看、持仓分析报告查询功能。
"""

import logging
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="list_positions",
    name="查看持仓列表",
    description="列出用户当前持有的所有股票持仓，包括成本价、现价、盈亏等信息。支持按数据来源筛选（实盘/模拟）。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def list_positions(
    source: Annotated[str, "数据来源：all=全部, real=实盘持仓, paper=模拟持仓"] = "all",
) -> str:
    """列出用户当前所有持仓，返回每只股票的代码、名称、数量、成本价、现价、浮动盈亏等。"""
    try:
        from app.services.portfolio_service import get_portfolio_service

        user_id = require_current_user_id()
        service = get_portfolio_service()
        positions = await service.get_positions(user_id, source=source, include_market_data=True)

        if not positions:
            source_label = {"all": "", "real": "实盘", "paper": "模拟"}.get(source, "")
            return f"当前没有{source_label}持仓记录。"

        lines = [f"共 {len(positions)} 只持仓：\n"]
        for p in positions:
            pnl_str = ""
            if p.unrealized_pnl is not None:
                sign = "+" if p.unrealized_pnl >= 0 else ""
                pct = f"{p.unrealized_pnl_pct:+.2f}%" if p.unrealized_pnl_pct is not None else ""
                pnl_str = f"  浮动盈亏: {sign}{p.unrealized_pnl:.2f} ({pct})"

            src_label = "实盘" if p.source == "real" else "模拟"
            price_str = f"现价: {p.current_price:.2f}" if p.current_price else "现价: --"
            lines.append(
                f"[{src_label}] {p.code} {p.name or ''} | "
                f"数量: {p.quantity} | 成本: {p.cost_price:.2f} | {price_str} | "
                f"市值: {p.market_value:.2f}{pnl_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[list_positions] 获取持仓列表失败: %s", e)
        return f"获取持仓列表时出错: {e}"


@tool
@register_tool(
    tool_id="get_position_analysis",
    name="获取持仓分析报告",
    description="获取某只持仓股票的最新 AI 分析报告，包含操作建议（加仓/减仓/持有/清仓）、目标价位、风险评估等。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def get_position_analysis(
    code: Annotated[str, "股票代码，如 600519、00700"],
    market: Annotated[str, "市场代码：CN=A股, HK=港股, US=美股"] = "CN",
    position_type: Annotated[str, "持仓类型：real=实盘, simulated=模拟"] = "real",
) -> str:
    """获取指定股票持仓的最新 AI 分析报告。"""
    try:
        from app.services.portfolio_service import get_portfolio_service

        user_id = require_current_user_id()
        service = get_portfolio_service()
        report = await service.get_latest_position_analysis(user_id, code, market, position_type)

        if not report:
            return f"未找到 {code} 的持仓分析报告。可以先发起一次持仓分析。"

        # 构建摘要
        lines = []
        name = report.get("name") or code
        action = report.get("action") or "未知"
        confidence = report.get("confidence")
        status = report.get("status", "")
        created = report.get("created_at", "")

        lines.append(f"{name}({code}) 持仓分析报告")
        lines.append(f"状态: {status} | 操作建议: {action}" + (f" | 置信度: {confidence}%" if confidence else ""))

        # 持仓摘要
        summary = report.get("summary") or {}
        if summary.get("quantity"):
            cost = summary.get("cost_price", 0)
            cur = summary.get("current_price", 0)
            pnl = summary.get("unrealized_pnl")
            pnl_pct = summary.get("unrealized_pnl_pct")
            lines.append(f"持仓: {summary['quantity']}股 | 成本: {cost:.2f} | 现价: {cur:.2f}")
            if pnl is not None:
                lines.append(f"浮动盈亏: {pnl:+.2f}" + (f" ({pnl_pct:+.2f}%)" if pnl_pct is not None else ""))

        # 目标价位
        pt = report.get("price_targets") or {}
        if pt.get("target_price") or pt.get("stop_loss"):
            tp = pt.get("target_price")
            sl = pt.get("stop_loss")
            lines.append(f"目标价: {tp}" + (f" | 止损价: {sl}" if sl else ""))

        # 操作理由
        reason = report.get("action_reason")
        if reason:
            lines.append(f"\n分析详情:\n{reason}")

        if created:
            lines.append(f"\n报告时间: {created[:16] if isinstance(created, str) else created}")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("[get_position_analysis] 获取持仓分析报告失败: %s", e)
        return f"获取持仓分析报告时出错: {e}"

