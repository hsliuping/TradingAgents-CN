"""
交易复盘类工具

提供复盘历史查询、复盘报告详情获取功能。
"""

import logging
from typing import Annotated, Optional

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

