"""
交易复盘类工具

提供复盘历史查询、复盘报告详情获取、发起交易复盘功能。
"""

import asyncio
import logging
from typing import Annotated, List, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="list_trade_reviews",
    name="查看复盘历史",
    description="列出用户的交易复盘记录，支持按股票代码、数据来源（模拟/实盘）、时间范围筛选。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["trade_review", "review", "history", "list", "query", "assistant_ops", "trade_history", "review_records", "trade_analysis", "backtesting", "review_filtering"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["查看复盘历史", "复盘记录查询", "交易复盘列表", "按股票查复盘"],
    when_to_use="当用户想查看自己的交易复盘记录列表、按股票代码或数据来源筛选复盘历史时使用。",
    returns="返回文本格式的复盘记录列表，每条含股票代码、名称、复盘类型、盈亏、评分、状态和复盘ID。",
)
async def list_trade_reviews(
    code: Annotated[Optional[str], "股票代码筛选，如 600519，留空则不限"] = None,
    source: Annotated[Optional[str], "数据来源筛选：paper=模拟交易, position=持仓操作, 留空则全部"] = None,
    page: Annotated[int, "页码，默认1"] = 1,
    page_size: Annotated[int, "每页数量，默认10"] = 10,
) -> str:
    """列出用户的交易复盘历史记录。"""
    try:
        from app.services.trade_review_service import get_trade_review_service

        user_id = require_current_user_id()
        service = get_trade_review_service()
        result = await service.get_review_history(
            user_id=user_id,
            page=page,
            page_size=page_size,
            code=code,
            source=source,
        )

        items = result.get("items", [])
        total = result.get("total", 0)

        if not items:
            filter_desc = ""
            if code:
                filter_desc += f" {code}"
            if source:
                filter_desc += f" ({source})"
            return f"没有找到{filter_desc}的复盘记录。"

        lines = [f"共 {total} 条复盘记录（第 {page} 页）：\n"]
        for item in items:
            code_str = item.get("code", "")
            name_str = item.get("name", "")
            review_type = item.get("review_type", "")
            status = item.get("status", "")
            score = item.get("overall_score", 0)
            pnl = item.get("realized_pnl", 0)
            created = item.get("created_at", "")
            review_id = item.get("review_id", "")

            # 格式化时间
            if isinstance(created, str) and len(created) > 16:
                created = created[:16]

            pnl_str = f"{pnl:+.2f}" if pnl else "0"
            score_str = f"评分: {score}" if score else ""
            type_label = {"complete_trade": "完整交易", "holding_trade": "持仓中"}.get(review_type, review_type)

            lines.append(
                f"{code_str} {name_str} | {type_label} | 盈亏: {pnl_str} | {score_str} | {status} | {created}"
            )
            lines.append(f"  复盘ID: {review_id}")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("[list_trade_reviews] 获取复盘历史失败: %s", e)
        return f"获取复盘历史时出错: {e}"


@tool
@register_tool(
    tool_id="get_trade_review_detail",
    name="获取复盘报告详情",
    description="根据复盘ID获取一篇交易复盘的完整报告，包含 AI 评价、评分、改进建议等。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["trade_review", "review", "detail", "report", "query", "assistant_ops", "review_detail", "ai_review", "review_report", "trade_analysis", "review_suggestions"],
    tool_role_hint="primary",
    output_shape="report",
    preferred_for=["复盘报告详情", "查看复盘结果", "AI评价查看", "复盘改进建议"],
    when_to_use="当用户想查看某篇交易复盘的完整报告详情、获取 AI 评价和改进建议时使用，需提供复盘ID。",
    returns="返回格式化的复盘报告文本，包含基本信息、综合评分、总结、优点、不足和具体建议。",
)
async def get_trade_review_detail(
    review_id: Annotated[str, "复盘ID，从复盘历史列表中获取"],
) -> str:
    """获取指定复盘ID的完整报告详情。"""
    try:
        from app.services.trade_review_service import get_trade_review_service

        user_id = require_current_user_id()
        service = get_trade_review_service()
        report = await service.get_review_detail(user_id, review_id)

        if not report:
            return f"未找到复盘报告（ID: {review_id}）。请检查 ID 是否正确。"

        lines = []
        trade_info = report.trade_info
        ai_review = report.ai_review

        # 基本信息
        code = trade_info.code if trade_info else ""
        name = trade_info.name if trade_info and trade_info.name else ""
        lines.append(f"{name}({code}) 交易复盘报告")
        lines.append(f"复盘类型: {report.review_type} | 状态: {report.status}")

        if trade_info:
            pnl = trade_info.realized_pnl
            if pnl is not None:
                lines.append(f"已实现盈亏: {pnl:+.2f}")
            if trade_info.is_holding:
                lines.append("当前状态: 持仓中")

        # AI 评价
        if ai_review:
            if hasattr(ai_review, "overall_score") and ai_review.overall_score:
                lines.append(f"\n综合评分: {ai_review.overall_score}/100")
            if hasattr(ai_review, "summary") and ai_review.summary:
                lines.append(f"\n总结:\n{ai_review.summary}")
            if hasattr(ai_review, "strengths") and ai_review.strengths:
                lines.append("\n做得好的地方:")
                for s in ai_review.strengths:
                    lines.append(f"  ✅ {s}")
            if hasattr(ai_review, "weaknesses") and ai_review.weaknesses:
                lines.append("\n需要改进:")
                for w in ai_review.weaknesses:
                    lines.append(f"  ⚠️ {w}")
            if hasattr(ai_review, "suggestions") and ai_review.suggestions:
                lines.append("\n具体建议:")
                for sg in ai_review.suggestions:
                    lines.append(f"  💡 {sg}")

        created = report.created_at
        if created:
            ts = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else str(created)[:16]
            lines.append(f"\n报告时间: {ts}")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("[get_trade_review_detail] 获取复盘报告失败: %s", e)
        return f"获取复盘报告时出错: {e}"


@tool
@register_tool(
    tool_id="trigger_trade_review",
    name="发起交易复盘",
    description="对指定的交易记录发起一次新的 AI 复盘分析任务。需要提供交易ID列表（可从持仓变动记录或模拟交易记录中获取）。后台异步执行（约1-3分钟），生成 AI 评价、评分和改进建议。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["trade_review", "review", "trigger", "create", "assistant_ops", "ai_review", "review_task", "trade_analysis", "backtesting", "async_task", "review_creation"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["发起交易复盘", "创建复盘任务", "AI交易分析", "交易记录复盘"],
    when_to_use="当用户想对指定交易记录发起新的 AI 复盘分析任务、获取交易评价和改进建议时使用。",
    returns="返回文本消息，包含任务ID、交易笔数、数据来源和预计完成时间，后台异步执行。",
)
async def trigger_trade_review(
    trade_ids: Annotated[str, "要复盘的交易ID，多个用逗号分隔"],
    code: Annotated[Optional[str], "股票代码，如 600519。留空则从交易记录自动推断"] = None,
    source: Annotated[str, "数据来源：paper=模拟交易, position=持仓操作"] = "paper",
) -> str:
    """对指定交易记录发起一次新的 AI 复盘分析，后台异步执行，返回任务ID。"""
    try:
        from app.services.unified_analysis_service import get_unified_analysis_service
        from app.models.review import CreateTradeReviewRequest

        user_id = require_current_user_id()
        id_list = [tid.strip() for tid in trade_ids.split(",") if tid.strip()]
        if not id_list:
            return "❌ 请提供至少一个交易ID。"

        logger.info("[trigger_trade_review] 开始创建复盘任务: trade_ids=%s, code=%s, user_id=%s", id_list, code, user_id)

        request = CreateTradeReviewRequest(
            trade_ids=id_list,
            code=code,
            source=source,
        )

        unified_service = get_unified_analysis_service()
        result = await unified_service.create_trade_review_task(
            user_id=user_id,
            request=request,
        )
        task_id = result["task_id"]
        logger.info("[trigger_trade_review] ✅ 任务已创建: task_id=%s", task_id)

        # 后台执行，不阻塞
        bg_task = asyncio.create_task(
            unified_service.execute_trade_review(
                task_id=task_id,
                user_id=user_id,
                request=request,
            )
        )
        bg_task.add_done_callback(
            lambda t: logger.error("[trigger_trade_review] ❌ 后台执行异常: %s", t.exception())
            if not t.cancelled() and t.exception() else None
        )

        code_str = f"（{code}）" if code else ""
        source_label = "模拟交易" if source == "paper" else "持仓操作"
        return (
            f"✅ 交易复盘任务已创建\n"
            f"- 任务ID: {task_id}\n"
            f"- 交易笔数: {len(id_list)}{code_str}\n"
            f"- 数据来源: {source_label}\n"
            f"- 预计 1-3 分钟完成，届时可用「获取复盘报告详情」查看结果。"
        )
    except Exception as e:
        logger.exception("[trigger_trade_review] ❌ 创建任务失败: %s", e)
        return f"❌ 创建交易复盘任务失败: {e}"

