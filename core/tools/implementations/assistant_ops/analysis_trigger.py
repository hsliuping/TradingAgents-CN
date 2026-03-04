"""
分析触发类工具

提供股票分析任务的创建和状态查询功能。
分析任务异步执行，工具立即返回 task_id，不阻塞等待结果。
"""

import asyncio
import logging
import uuid
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import get_current_im_channel, require_current_user_id

logger = logging.getLogger(__name__)

# ── 深度映射 ──
_DEPTH_MAP = {1: "快速", 2: "基础", 3: "标准", 4: "深度", 5: "全面"}


def _depth_label(depth: int) -> str:
    return _DEPTH_MAP.get(depth, "标准")


@tool
@register_tool(
    tool_id="trigger_stock_analysis",
    name="触发股票分析",
    description=(
        "发起一次全新的股票多智能体深度分析，生成新报告。"
        "仅当用户明确要求「分析/重新分析某股票」时使用，任务需要 2-5 分钟在后台执行。"
        "若用户想查看、解读或总结已有的分析报告，请勿使用此工具，应使用 get_latest_report。"
    ),
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def trigger_stock_analysis(
    symbol: Annotated[str, "股票代码，6位数字，如 000001、600519"],
    depth: Annotated[int, "分析深度 1-5（1=快速 2=基础 3=标准 4=深度 5=全面），默认3"] = 3,
    workflow_id: Annotated[Optional[str], "指定工作流ID，留空则自动选择"] = None,
) -> str:
    """发起一次全新的股票分析任务。任务在后台异步执行（通常需要 2-5 分钟），返回任务ID以便后续查询状态或报告。"""
    try:
        from bson import ObjectId
        from app.services.task_analysis_service import get_task_analysis_service
        from app.models.analysis import AnalysisTaskType

        user_id = require_current_user_id()
        logger.info("[trigger_stock_analysis] 开始创建任务: symbol=%s, depth=%s, user_id=%s", symbol, depth, user_id)

        service = get_task_analysis_service()

        # 构造任务参数，若在 IM 渠道触发则附加回调渠道信息（用于任务完成后推送通知）
        task_params: dict = {"symbol": symbol, "market_type": "cn", "research_depth": _depth_label(depth)}
        im_channel = get_current_im_channel()
        if im_channel:
            task_params["_im_channel"] = im_channel
            logger.info("[trigger_stock_analysis] IM 渠道回调: %s", im_channel)

        task = await service.create_task(
            user_id=ObjectId(user_id),
            task_type=AnalysisTaskType.STOCK_ANALYSIS,
            task_params=task_params,
            engine_type="auto",
            workflow_id=workflow_id,
        )
        logger.info("[trigger_stock_analysis] ✅ 任务已创建: task_id=%s", task.task_id)

        # 后台执行，不阻塞
        bg_task = asyncio.create_task(service.execute_task(task.task_id))
        bg_task.add_done_callback(
            lambda t: logger.error("[trigger_stock_analysis] ❌ 后台执行异常: %s", t.exception())
            if not t.cancelled() and t.exception() else None
        )
        logger.info("[trigger_stock_analysis] 后台执行任务已提交")

        return (
            f"✅ 分析任务已创建\n"
            f"- 任务ID: {task.task_id}\n"
            f"- 股票: {symbol}\n"
            f"- 深度: {_depth_label(depth)}\n"
            f"- 预计 2-5 分钟完成，届时可用「查看报告」功能查看结果。"
        )
    except Exception as e:
        logger.exception("[trigger_stock_analysis] ❌ 创建任务失败: %s", e)
        return f"❌ 创建分析任务失败: {e}"


@tool
@register_tool(
    tool_id="trigger_batch_analysis",
    name="触发批量分析",
    description="同时为多只股票创建分析任务，返回批次ID和各任务ID。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def trigger_batch_analysis(
    symbols: Annotated[str, "股票代码列表，用逗号分隔，如 000001,600519,000858"],
    depth: Annotated[int, "分析深度 1-5，默认3"] = 3,
) -> str:
    """批量触发多只股票的分析任务。每只股票单独创建任务，全部后台异步执行。"""
    from bson import ObjectId
    from app.services.task_analysis_service import get_task_analysis_service
    from app.models.analysis import AnalysisTaskType

    user_id = require_current_user_id()
    service = get_task_analysis_service()
    batch_id = str(uuid.uuid4())

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return "❌ 请提供至少一个股票代码"
    if len(symbol_list) > 10:
        return "❌ 单次批量分析最多支持 10 只股票"

    task_ids = []
    for sym in symbol_list:
        task = await service.create_task(
            user_id=ObjectId(user_id),
            task_type=AnalysisTaskType.STOCK_ANALYSIS,
            task_params={"symbol": sym, "market_type": "cn", "research_depth": _depth_label(depth)},
            engine_type="auto",
            batch_id=batch_id,
        )
        asyncio.create_task(service.execute_task(task.task_id))
        task_ids.append(f"  - {sym}: {task.task_id}")

    return (
        f"✅ 批量分析已创建（{len(symbol_list)} 只股票）\n"
        f"- 批次ID: {batch_id}\n"
        f"- 深度: {_depth_label(depth)}\n"
        + "\n".join(task_ids)
        + "\n- 每只股票预计 2-5 分钟完成。"
    )


@tool
@register_tool(
    tool_id="get_analysis_status",
    name="查询分析状态",
    description="根据任务ID查询分析任务的当前状态和进度。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def get_analysis_status(
    task_id: Annotated[str, "分析任务ID"],
) -> str:
    """查询指定分析任务的状态、进度和结果摘要。"""
    from app.services.task_analysis_service import get_task_analysis_service

    service = get_task_analysis_service()
    task = await service.get_task(task_id)

    if not task:
        return f"❌ 未找到任务: {task_id}"

    status_emoji = {"pending": "⏳", "processing": "🔄", "completed": "✅", "failed": "❌", "cancelled": "🚫"}
    emoji = status_emoji.get(task.status, "❓")
    lines = [
        f"{emoji} 任务状态: {task.status}",
        f"- 任务ID: {task.task_id}",
        f"- 类型: {task.task_type}",
        f"- 进度: {task.progress}%",
    ]
    if task.current_step:
        lines.append(f"- 当前步骤: {task.current_step}")
    if task.status == "completed" and task.result:
        recommendation = task.result.get("recommendation", "")
        if recommendation:
            lines.append(f"- 投资建议: {recommendation[:200]}")
    if task.status == "failed" and task.error_message:
        lines.append(f"- 错误: {task.error_message[:200]}")
    if task.execution_time > 0:
        lines.append(f"- 耗时: {task.execution_time:.1f}s")

    return "\n".join(lines)

