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
from core.tools.context import get_current_assistant_thread_id, get_current_im_channel, require_current_user_id

logger = logging.getLogger(__name__)

# ── 深度映射 ──
_DEPTH_MAP = {1: "快速", 2: "基础", 3: "标准", 4: "深度", 5: "全面"}


def _depth_label(depth: int) -> str:
    return _DEPTH_MAP.get(depth, "标准")


def _analysis_models() -> tuple[str, str]:
    """获取当前配置的快速/深度分析模型，写入 task_params 供报告页展示模型名。

    与前端/正常分析入口保持一致（analysis_service 亦从 unified_config 读取），
    避免智能助手发起的分析报告显示 Unknown/Unknown。
    """
    try:
        from app.core.unified_config import unified_config
        return (
            unified_config.get_quick_analysis_model(),
            unified_config.get_deep_analysis_model(),
        )
    except Exception as e:
        logger.warning(f"[analysis_trigger] 读取分析模型配置失败: {e}")
        return "qwen-turbo", "qwen-max"


@tool
@register_tool(
    tool_id="trigger_stock_analysis",
    name="触发股票分析",
    description="创建一个全新的多智能体深度分析任务，由多个 AI 智能体在后台协作生成一份新的分析报告（耗时 2-5 分钟）。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["analysis_trigger", "stock_analysis", "trigger", "create", "assistant_ops", "multi_agent_analysis", "async_task", "analysis_task", "deep_analysis"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["stock_analysis_trigger", "deep_analysis_initiation", "multi_agent_analysis", "async_analysis_task_creation"],
    returns="返回文本消息，包含任务ID、股票代码、分析深度和预计完成时间。",
    when_to_use="当用户要求对某只股票发起深度分析、生成分析报告时使用，任务在后台异步执行。",
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
        quick_model, deep_model = _analysis_models()
        task_params: dict = {
            "symbol": symbol,
            "market_type": "cn",
            "research_depth": _depth_label(depth),
            "quick_analysis_model": quick_model,
            "deep_analysis_model": deep_model,
        }
        im_channel = get_current_im_channel()
        if im_channel:
            task_params["_im_channel"] = im_channel
            logger.info("[trigger_stock_analysis] IM 渠道回调: %s", im_channel)
        current_thread_id = (get_current_assistant_thread_id() or "").strip()
        if current_thread_id:
            task_params["_assistant_thread_id"] = current_thread_id

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
    description="同时为多只股票创建分析任务（批量版本的 trigger_stock_analysis），返回批次ID和各任务ID。适用于用户要求一次分析多只股票的场景。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["analysis_trigger", "batch_analysis", "trigger", "create", "assistant_ops", "multi_stock_analysis", "async_task", "batch_task", "multi_agent_analysis", "batch_create"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["批量股票分析触发", "多只股票同时分析", "批量分析任务创建", "组合分析快速发起"],
    when_to_use="当用户要求一次分析多只股票、批量发起分析任务时使用，每只股票单独创建后台异步任务。",
    returns="返回文本消息，包含批次ID、各股票任务ID、分析深度和预计完成时间。",
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
        quick_model, deep_model = _analysis_models()
        task_params = {
            "symbol": sym,
            "market_type": "cn",
            "research_depth": _depth_label(depth),
            "quick_analysis_model": quick_model,
            "deep_analysis_model": deep_model,
        }
        current_thread_id = (get_current_assistant_thread_id() or "").strip()
        if current_thread_id:
            task_params["_assistant_thread_id"] = current_thread_id
        task = await service.create_task(
            user_id=ObjectId(user_id),
            task_type=AnalysisTaskType.STOCK_ANALYSIS,
            task_params=task_params,
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
    description="根据任务ID查询分析任务的执行状态和进度（排队中/运行中/已完成/失败）。用于了解之前发起的分析是否完成。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["analysis_trigger", "status_query", "query", "assistant_ops", "task_status", "analysis_progress", "task_tracking", "async_task", "monitor", "progress_check"],
    tool_role_hint="supporting",
    output_shape="text",
    preferred_for=["分析任务状态查询", "分析进度跟踪", "任务完成确认", "异步分析结果检查"],
    when_to_use="当用户想了解之前发起的分析任务是否完成、当前进度或失败原因时使用。",
    returns="返回文本消息，包含任务状态、进度百分比、当前步骤和（如已完成）研究结论倾向摘要。",
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
            lines.append(f"- 研究结论倾向: {recommendation[:200]}")
    if task.status == "failed" and task.error_message:
        lines.append(f"- 错误: {task.error_message[:200]}")
    if task.execution_time > 0:
        lines.append(f"- 耗时: {task.execution_time:.1f}s")

    return "\n".join(lines)

