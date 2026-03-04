"""
报告查询类工具

提供分析报告的搜索、详情查看和最新报告获取功能。
查询范围限定为当前用户的报告。
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)

# ── 日期范围快捷方式 ──
_DATE_SHORTCUTS = {
    "today": 0,
    "yesterday": 1,
    "last_week": 7,
    "last_month": 30,
    "last_quarter": 90,
}


def _resolve_date_range(date_range: Optional[str]):
    """将自然语言日期范围转为 (start, end) datetime。"""
    if not date_range:
        return None, None
    key = date_range.strip().lower().replace(" ", "_")
    days = _DATE_SHORTCUTS.get(key)
    if days is not None:
        end = datetime.now()
        start = end - timedelta(days=days)
        return start, end
    # 尝试解析 YYYY-MM-DD ~ YYYY-MM-DD
    if "~" in date_range:
        parts = date_range.split("~")
        try:
            return datetime.strptime(parts[0].strip(), "%Y-%m-%d"), datetime.strptime(parts[1].strip(), "%Y-%m-%d")
        except ValueError:
            pass
    return None, None


@tool
@register_tool(
    tool_id="search_reports",
    name="搜索分析报告",
    description="搜索用户【已有】的历史分析报告，支持按股票代码、关键词、日期范围筛选，返回摘要列表。【重要】：此工具仅用于查询历史记录，用户说「分析XX」时不得调用此工具，应调用 trigger_stock_analysis。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def search_reports(
    symbol: Annotated[Optional[str], "股票代码筛选，如 600519"] = None,
    keyword: Annotated[Optional[str], "搜索关键词，匹配报告内容"] = None,
    date_range: Annotated[Optional[str], "日期范围: today / last_week / last_month 或 YYYY-MM-DD~YYYY-MM-DD"] = None,
    limit: Annotated[int, "返回数量上限，默认5"] = 5,
) -> str:
    """搜索分析报告列表，返回精简摘要（标题、股票、日期、结论），不含完整内容。"""
    from bson import ObjectId
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()

    query = {"user_id": ObjectId(user_id), "status": "completed"}

    if symbol:
        query["task_params.symbol"] = symbol
    if keyword:
        query["$or"] = [
            {"task_params.symbol": {"$regex": keyword, "$options": "i"}},
            {"result.recommendation": {"$regex": keyword, "$options": "i"}},
            {"result.summary": {"$regex": keyword, "$options": "i"}},
        ]
    start, end = _resolve_date_range(date_range)
    if start or end:
        date_q = {}
        if start:
            date_q["$gte"] = start
        if end:
            date_q["$lte"] = end
        query["created_at"] = date_q

    cursor = db.unified_analysis_tasks.find(
        query,
        {"task_id": 1, "task_type": 1, "task_params": 1, "created_at": 1, "result.recommendation": 1, "result.summary": 1, "execution_time": 1},
    ).sort("created_at", -1).limit(limit)

    results = []
    async for doc in cursor:
        sym = doc.get("task_params", {}).get("symbol", "N/A")
        created = doc.get("created_at")
        date_str = created.strftime("%Y-%m-%d %H:%M") if created else "未知"
        rec = (doc.get("result") or {}).get("recommendation", "")
        summary = (doc.get("result") or {}).get("summary", "")
        brief = (rec or summary or "无摘要")[:120]
        results.append(f"  [{doc['task_id'][:8]}] {sym} | {date_str} | {brief}")

    if not results:
        return "未找到符合条件的分析报告。"
    return f"📊 找到 {len(results)} 条报告：\n" + "\n".join(results) + "\n\n💡 使用「查看报告详情」获取完整内容。"


@tool
@register_tool(
    tool_id="get_report_detail",
    name="查看报告详情",
    description="根据任务ID获取完整的分析报告内容。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def get_report_detail(
    task_id: Annotated[str, "分析任务ID"],
) -> str:
    """获取指定分析任务的完整报告，格式化为 Markdown。"""
    from app.services.task_analysis_service import get_task_analysis_service

    service = get_task_analysis_service()
    task = await service.get_task(task_id)
    if not task:
        return f"❌ 未找到任务: {task_id}"
    if task.status != "completed":
        return f"⏳ 任务尚未完成（当前状态: {task.status}，进度: {task.progress}%）"
    if not task.result:
        return "⚠️ 任务已完成但未生成报告数据。"

    r = task.result
    sym = task.task_params.get("symbol", "未知")
    lines = [f"# 📈 {sym} 分析报告"]
    if r.get("recommendation"):
        lines.append(f"\n## 投资建议\n{r['recommendation']}")
    if r.get("confidence_score"):
        lines.append(f"\n**置信度**: {r['confidence_score']}")
    if r.get("risk_level"):
        lines.append(f"**风险等级**: {r['risk_level']}")
    if r.get("key_points"):
        kps = r["key_points"] if isinstance(r["key_points"], list) else [r["key_points"]]
        lines.append("\n## 关键要点\n" + "\n".join(f"- {kp}" for kp in kps))
    if r.get("summary"):
        lines.append(f"\n## 摘要\n{r['summary']}")

    lines.append(f"\n---\n_任务ID: {task.task_id} | 耗时: {task.execution_time:.1f}s_")
    return "\n".join(lines)


@tool
@register_tool(
    tool_id="get_latest_report",
    name="获取最新报告",
    description="获取指定股票最近一次分析报告的摘要。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
)
async def get_latest_report(
    symbol: Annotated[str, "股票代码，如 600519"],
) -> str:
    """快速获取某只股票最近一次已完成的分析报告摘要。"""
    from bson import ObjectId
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()

    doc = await db.unified_analysis_tasks.find_one(
        {"user_id": ObjectId(user_id), "task_params.symbol": symbol, "status": "completed"},
        sort=[("created_at", -1)],
    )
    if not doc:
        return f"未找到 {symbol} 的分析报告。你可以使用「触发股票分析」来发起分析。"

    r = doc.get("result") or {}
    created = doc.get("created_at")
    date_str = created.strftime("%Y-%m-%d %H:%M") if created else "未知"
    rec = r.get("recommendation", "无建议")
    summary = r.get("summary", "")
    brief = (summary or rec)[:300]

    return (
        f"📈 {symbol} 最新报告（{date_str}）\n"
        f"- 建议: {rec[:150]}\n"
        f"- 摘要: {brief}\n"
        f"- 任务ID: {doc['task_id']}\n"
        f"\n💡 使用「查看报告详情」获取完整内容。"
    )
