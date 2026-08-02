"""
持仓分析类工具

提供持仓列表查看、持仓分析报告查询、发起持仓分析功能。
"""

import asyncio
import logging
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import get_current_assistant_thread_id, require_current_user_id

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="list_positions",
    name="查看持仓列表",
    description="列出用户当前持有的所有股票持仓，包括成本价、现价、盈亏等信息。支持按数据来源筛选（实盘/模拟）。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["position_analysis", "position", "list", "query", "assistant_ops", "portfolio", "holdings", "position_query", "real_position", "paper_position", "portfolio_view"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["持仓列表查看", "持仓股票查询", "实盘持仓浏览", "模拟持仓查看", "持仓盈亏查询"],
    when_to_use="当用户想查看当前持有的所有股票、了解持仓成本、现价和浮动盈亏时使用，支持按实盘/模拟筛选。",
    returns="返回文本消息，包含持仓数量及每只股票的代码、名称、数量、成本价、现价、市值和浮动盈亏。",
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
            mv_str = f"{p.market_value:.2f}" if p.market_value is not None else "--"
            lines.append(
                f"[{src_label}] {p.code} {p.name or ''} | "
                f"数量: {p.quantity} | 成本: {p.cost_price:.2f} | {price_str} | "
                f"市值: {mv_str}{pnl_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[list_positions] 获取持仓列表失败: %s", e)
        return f"获取持仓列表时出错: {e}"


@tool
@register_tool(
    tool_id="get_position_analysis",
    name="获取持仓分析报告",
    description="获取某只持仓股票的最新 AI 研究分析报告，包含研究观察倾向、关键验证价位、风险审阅要点等。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["position_analysis", "position", "query", "report", "assistant_ops", "ai_analysis", "position_report", "action_suggestion", "price_target", "risk_assessment", "holdings_analysis"],
    tool_role_hint="primary",
    output_shape="report",
    preferred_for=["持仓分析报告查看", "研究观察查询", "关键价位确认", "持仓风险审阅"],
    when_to_use="当用户想查看某只持仓股票的最新 AI 研究分析报告、获取研究观察与风险审阅参考时使用。",
    returns="返回文本报告，包含研究观察倾向、置信度、持仓摘要、关键验证价位、风险关注价格和分析详情。",
)
async def get_position_analysis(
    code: Annotated[str, "股票代码，如 600519、00700"],
    market: Annotated[str, "市场代码：CN=A股, HK=港股, US=美股"] = "CN",
    position_type: Annotated[str, "持仓类型：real=实盘, simulated=模拟"] = "real",
) -> str:
    """获取指定股票持仓的最新 AI 分析报告。"""
    try:
        from app.services.portfolio_service import get_portfolio_service
        from app.services.intelligent_assistant_service import attach_report_ref_to_thread
        from app.core.database import get_mongo_db

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
        lines.append(f"状态: {status} | 研究观察: {action}" + (f" | 置信度: {confidence}%" if confidence else ""))

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

        # 关键验证价位
        pt = report.get("price_targets") or {}
        if pt.get("target_price") or pt.get("stop_loss"):
            tp = pt.get("target_price")
            sl = pt.get("stop_loss")
            lines.append(f"关键验证价位: {tp}" + (f" | 风险关注价格: {sl}" if sl else ""))

        # 操作理由
        reason = report.get("action_reason")
        if reason:
            lines.append(f"\n分析详情:\n{reason}")

        if created:
            lines.append(f"\n报告时间: {created[:16] if isinstance(created, str) else created}")

        await attach_report_ref_to_thread(
            get_mongo_db(),
            user_id,
            get_current_assistant_thread_id(),
            {
                "ref_type": "position_report",
                "report_key": (report.get("analysis_id") or report.get("task_id") or f"{code}_{market}_{position_type}"),
                "source_collection": "position_analysis_reports",
                "title": f"{name}({code}) 持仓分析报告",
                "symbol": code,
                "summary": (reason or report.get("summary") or "")[:400],
                "status": status or "completed",
                "task_id": report.get("task_id"),
                "analysis_id": report.get("analysis_id"),
                "created_at": report.get("created_at"),
            },
        )

        return "\n".join(lines)
    except Exception as e:
        logger.exception("[get_position_analysis] 获取持仓分析报告失败: %s", e)
        return f"获取持仓分析报告时出错: {e}"


@tool
@register_tool(
    tool_id="trigger_position_analysis",
    name="发起持仓分析",
    description="对某只持仓股票发起一次新的 AI 持仓研究分析任务，结合持仓成本、盈亏等信息生成研究观察、关键验证价位和风险审阅。任务在后台异步执行（约2-5分钟），返回任务ID。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["position_analysis", "position", "trigger", "create", "assistant_ops", "ai_analysis", "async_task", "position_analysis_task", "action_suggestion", "deep_analysis", "holdings_analysis"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["持仓分析触发", "持仓 AI 分析发起", "研究观察生成", "持仓深度分析"],
    when_to_use="当用户要求对某只持仓股票发起 AI 研究分析、生成研究观察与关键验证价位时使用，任务在后台异步执行（约2-5分钟）。",
    returns="返回文本消息，包含任务ID、股票代码、市场、持仓类型、分析重点和预计完成时间。",
)
async def trigger_position_analysis(
    code: Annotated[str, "股票代码，如 600519、00700"],
    market: Annotated[str, "市场代码：CN=A股, HK=港股, US=美股"] = "CN",
    position_type: Annotated[str, "持仓类型：real=实盘, simulated=模拟"] = "real",
    analysis_focus: Annotated[str, "分析重点：technical=技术面, fundamental=基本面, comprehensive=综合"] = "comprehensive",
) -> str:
    """对某只持仓股票发起一次新的 AI 分析，后台异步执行，返回任务ID。"""
    try:
        from app.core.database import get_mongo_db
        from app.services.intelligent_assistant_service import attach_report_ref_to_thread
        from app.services.unified_analysis_service import get_unified_analysis_service

        user_id = require_current_user_id()
        logger.info("[trigger_position_analysis] 开始创建持仓分析任务: code=%s, market=%s, user_id=%s", code, market, user_id)

        unified_service = get_unified_analysis_service()

        task_params = {
            "research_depth": "标准",
            "include_add_position": True,
            "target_profit_pct": 20.0,
            "max_position_pct": 30.0,
            "max_loss_pct": 10.0,
            "risk_tolerance": "medium",
            "investment_horizon": "medium",
            "analysis_focus": analysis_focus,
            "position_type": position_type,
        }
        current_thread_id = (get_current_assistant_thread_id() or "").strip()
        if current_thread_id:
            task_params["_assistant_thread_id"] = current_thread_id

        result = await unified_service.create_position_analysis_task(
            user_id=user_id,
            code=code,
            market=market,
            task_params=task_params,
        )
        task_id = result["task_id"]
        logger.info("[trigger_position_analysis] ✅ 任务已创建: task_id=%s", task_id)

        # 后台执行，不阻塞
        bg_task = asyncio.create_task(
            unified_service.execute_position_analysis(
                task_id=task_id,
                user_id=user_id,
                code=code,
                market=market,
                task_params=task_params,
            )
        )
        bg_task.add_done_callback(
            lambda t: logger.error("[trigger_position_analysis] ❌ 后台执行异常: %s", t.exception())
            if not t.cancelled() and t.exception() else None
        )

        await attach_report_ref_to_thread(
            get_mongo_db(),
            user_id,
            get_current_assistant_thread_id(),
            {
                "ref_type": "position_task",
                "report_key": task_id,
                "source_collection": "position_analysis_reports",
                "title": f"{code} 持仓分析任务",
                "symbol": code,
                "summary": f"已发起 {code} 的持仓分析任务，等待生成正式报告。",
                "status": "running",
                "task_id": task_id,
            },
        )

        return (
            f"✅ 持仓分析任务已创建\n"
            f"- 任务ID: {task_id}\n"
            f"- 股票: {code}（{market}）\n"
            f"- 持仓类型: {'实盘' if position_type == 'real' else '模拟'}\n"
            f"- 分析重点: {analysis_focus}\n"
            f"- 预计 2-5 分钟完成，届时可用「获取持仓分析报告」查看结果。"
        )
    except Exception as e:
        logger.exception("[trigger_position_analysis] ❌ 创建任务失败: %s", e)
        return f"❌ 创建持仓分析任务失败: {e}"

