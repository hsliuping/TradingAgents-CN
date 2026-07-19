"""使用问答机器人工具：查询数据同步状态。

提供查询 tushare/akshare 的历史行情、财务数据、股票基础数据的同步状态能力，
让使用问答助手能"看到"数据源同步是否正常、是否需要触发新的同步，
而非凭 FAQ 猜答案。

覆盖的查询维度：
1. 股票基础数据（stock_basic_info / sync_status 集合）——多源同步任务的整体状态
2. 历史行情数据（historical_data 集合）——覆盖股票数、最新数据日期、记录数
3. 财务数据（stock_financial_data 集合）——覆盖股票数、最新更新时间、记录数
4. 单股同步状态（传 symbol 时）——该股的历史/财务/基础数据同步情况
5. 正在运行中的同步任务（stock_sync_tasks 集合）——是否有任务在跑
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


# 同步状态集合与任务标识（与 app/services/multi_source_basics_sync_service.py 保持一致）
_SYNC_STATUS_COLLECTION = "sync_status"
_STOCK_BASICS_JOB_KEY = "stock_basics_multi_source"
_STOCK_SYNC_TASKS_COLLECTION = "stock_sync_tasks"

# 数据集合
_HISTORICAL_DATA_COLLECTION = "historical_data"
_FINANCIAL_DATA_COLLECTION = "stock_financial_data"
_STOCK_BASIC_INFO_COLLECTION = "stock_basic_info"


def _format_time_ago(iso_str: Optional[str]) -> str:
    """将 ISO 时间字符串格式化为人类可读的'X 小时前'格式。"""
    if not iso_str:
        return "从未"
    try:
        # 兼容带 Z 和带时区的时间字符串
        normalized = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        now = datetime.now()
        diff = now - dt
        if diff.total_seconds() < 0:
            return dt.strftime("%Y-%m-%d %H:%M")
        if diff.total_seconds() < 60:
            return "刚刚"
        if diff.total_seconds() < 3600:
            return f"{int(diff.total_seconds() / 60)} 分钟前"
        if diff.total_seconds() < 86400:
            return f"{int(diff.total_seconds() / 3600)} 小时前"
        days = int(diff.total_seconds() / 86400)
        if days < 30:
            return f"{days} 天前"
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(iso_str)[:19]


def _summarize_status(status: str) -> tuple[str, str]:
    """将内部 status 字段映射为 (emoji, 中文描述)。"""
    mapping = {
        "success": ("✅", "成功"),
        "success_with_errors": ("⚠️", "成功（含部分错误）"),
        "running": ("🔄", "运行中"),
        "queued": ("⏳", "排队中"),
        "failed": ("❌", "失败"),
        "idle": ("💤", "空闲"),
        "never_run": ("⚪", "从未运行"),
    }
    return mapping.get(status, ("❓", status or "未知"))


async def _query_stock_basics_sync(db) -> Dict[str, Any]:
    """查询股票基础数据（多源同步任务）的同步状态。"""
    try:
        doc = await db[_SYNC_STATUS_COLLECTION].find_one({"job": _STOCK_BASICS_JOB_KEY})
        if not doc:
            return {"available": False}
        doc.pop("_id", None)
        return {"available": True, "doc": doc}
    except Exception as exc:
        logger.warning("[get_data_sync_status] 查询股票基础数据同步状态失败: %s", exc)
        return {"available": False, "error": str(exc)}


async def _query_historical_overview(db) -> Dict[str, Any]:
    """查询历史行情数据整体情况：覆盖股票数、最新数据日期、总记录数。"""
    try:
        total_records = await db[_HISTORICAL_DATA_COLLECTION].count_documents({})
        distinct_symbols = await db[_HISTORICAL_DATA_COLLECTION].distinct("symbol")
        # 最新数据日期（按 date 字段降序）
        latest_doc = await db[_HISTORICAL_DATA_COLLECTION].find_one(
            {}, sort=[("date", -1)]
        )
        latest_date = None
        if latest_doc:
            d = latest_doc.get("date")
            if isinstance(d, datetime):
                latest_date = d.strftime("%Y-%m-%d")
            elif d:
                latest_date = str(d)[:10]
        return {
            "total_records": total_records,
            "symbol_count": len(distinct_symbols) if distinct_symbols else 0,
            "latest_date": latest_date,
        }
    except Exception as exc:
        logger.warning("[get_data_sync_status] 查询历史数据整体情况失败: %s", exc)
        return {"error": str(exc)}


async def _query_financial_overview(db) -> Dict[str, Any]:
    """查询财务数据整体情况：覆盖股票数、最新更新时间、总记录数。"""
    try:
        total_records = await db[_FINANCIAL_DATA_COLLECTION].count_documents({})
        distinct_symbols = await db[_FINANCIAL_DATA_COLLECTION].distinct("symbol")
        latest_doc = await db[_FINANCIAL_DATA_COLLECTION].find_one(
            {}, sort=[("updated_at", -1)]
        )
        latest_updated = None
        if latest_doc:
            u = latest_doc.get("updated_at")
            if isinstance(u, datetime):
                latest_updated = u.isoformat()
            elif u:
                latest_updated = str(u)
        return {
            "total_records": total_records,
            "symbol_count": len(distinct_symbols) if distinct_symbols else 0,
            "latest_updated": latest_updated,
        }
    except Exception as exc:
        logger.warning("[get_data_sync_status] 查询财务数据整体情况失败: %s", exc)
        return {"error": str(exc)}


async def _query_running_sync_tasks(db) -> List[Dict[str, Any]]:
    """查询正在运行中的同步任务。"""
    try:
        cursor = db[_STOCK_SYNC_TASKS_COLLECTION].find(
            {"status": {"$in": ["running", "pending", "queued"]}},
            {"task_id": 1, "task_type": 1, "symbol": 1, "status": 1, "started_at": 1, "progress": 1}
        ).limit(10)
        docs = await cursor.to_list(length=10)
        for d in docs:
            d.pop("_id", None)
        return docs
    except Exception as exc:
        logger.warning("[get_data_sync_status] 查询运行中同步任务失败: %s", exc)
        return []


async def _query_single_stock_status(db, symbol: str) -> Dict[str, Any]:
    """查询单只股票的同步状态。复用 stock_sync 路由的逻辑。"""
    try:
        normalized = str(symbol).strip().upper()
        if "." in normalized:
            normalized = normalized.split(".", 1)[0]

        # 历史数据
        hist_doc = await db[_HISTORICAL_DATA_COLLECTION].find_one(
            {"symbol": normalized}, sort=[("date", -1)]
        )
        hist_count = await db[_HISTORICAL_DATA_COLLECTION].count_documents({"symbol": normalized})

        # 财务数据
        fin_doc = await db[_FINANCIAL_DATA_COLLECTION].find_one(
            {"symbol": normalized}, sort=[("updated_at", -1)]
        )
        fin_count = await db[_FINANCIAL_DATA_COLLECTION].count_documents({"symbol": normalized})

        # 基础数据
        basic_doc = await db[_STOCK_BASIC_INFO_COLLECTION].find_one({"symbol": normalized})

        return {
            "symbol": normalized,
            "historical": {
                "last_sync": hist_doc.get("updated_at") if hist_doc else None,
                "last_date": (
                    hist_doc.get("date").strftime("%Y-%m-%d")
                    if hist_doc and isinstance(hist_doc.get("date"), datetime)
                    else (str(hist_doc.get("date"))[:10] if hist_doc and hist_doc.get("date") else None)
                ),
                "total_records": hist_count,
            },
            "financial": {
                "last_sync": fin_doc.get("updated_at") if fin_doc else None,
                "total_records": fin_count,
            },
            "basic": {"available": basic_doc is not None},
        }
    except Exception as exc:
        logger.warning("[get_data_sync_status] 查询单股同步状态失败(%s): %s", symbol, exc)
        return {"symbol": symbol, "error": str(exc)}


def _format_single_stock_status(result: Dict[str, Any]) -> List[str]:
    """格式化单股同步状态为文本行。"""
    if result.get("error"):
        return [f"❌ 查询失败: {result['error']}"]

    lines = [f"📊 股票 {result.get('symbol', '?')} 的数据同步状态"]

    hist = result.get("historical", {})
    hist_records = hist.get("total_records", 0)
    if hist_records > 0:
        lines.append(
            f"- 历史行情: ✅ 已同步 {hist_records} 条，"
            f"最近日期 {hist.get('last_date', '?')}（更新时间: {_format_time_ago(hist.get('last_sync'))}）"
        )
    else:
        lines.append("- 历史行情: ❌ 未同步（该股票在 historical_data 集合中无记录）")

    fin = result.get("financial", {})
    fin_records = fin.get("total_records", 0)
    if fin_records > 0:
        lines.append(
            f"- 财务数据: ✅ 已同步 {fin_records} 条（更新时间: {_format_time_ago(fin.get('last_sync'))}）"
        )
    else:
        lines.append("- 财务数据: ❌ 未同步（该股票在 stock_financial_data 集合中无记录）")

    basic = result.get("basic", {})
    if basic.get("available"):
        lines.append("- 基础数据: ✅ 已同步")
    else:
        lines.append("- 基础数据: ❌ 未同步")

    # 综合判断
    has_data = hist_records > 0 or fin_records > 0
    if not has_data:
        lines.append("")
        lines.append("💡 该股票尚未同步数据，分析前建议先触发同步。")
        lines.append("   可以说：「同步股票 600519 的数据」")
    elif hist_records == 0:
        lines.append("")
        lines.append("💡 缺历史行情数据，如需分析请先同步历史数据。")
    elif fin_records == 0:
        lines.append("")
        lines.append("💡 缺财务数据，如需做财务分析请先同步财务数据。")

    return lines


@tool
@register_tool(
    tool_id="get_data_sync_status",
    name="查询数据同步状态",
    description="查询 tushare/akshare 的数据同步状态：股票基础数据、历史行情、财务数据的最近同步时间、记录数、是否正在运行同步任务。支持传 symbol 查单股，不传查整体。当用户问'数据同步了吗''数据是否最新''要不要重新同步'时使用。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "data_sync_status", "tushare", "akshare", "historical_data", "financial_data", "sync_status", "data_freshness"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=[
        "数据同步好了吗",
        "数据是否最新",
        "tushare 同步状态",
        "历史数据同步到什么时候",
        "财务数据是否需要更新",
        "中国银行数据同步了吗",
        "是否需要重新同步",
        "有同步任务在跑吗",
    ],
    when_to_use="当用户问到数据同步状态、数据新鲜度、是否需要重新同步、是否有同步任务在运行时使用。支持传 symbol 参数查单股数据同步状态。",
    returns="返回文本格式的数据同步状态摘要，包含基础数据/历史行情/财务数据的最近同步时间和记录数、正在运行的同步任务、是否需要触发新同步的判断。",
)
async def get_data_sync_status(
    symbol: Annotated[
        Optional[str],
        "股票代码（可选，6 位数字如 600519）。传入则查该股的同步状态；不传则查整体数据同步状态。"
    ] = None,
) -> str:
    """查询数据同步状态。"""
    from app.core.database import get_mongo_db

    db = get_mongo_db()

    # ---- 单股查询分支 ----
    if symbol and str(symbol).strip():
        result = await _query_single_stock_status(db, str(symbol).strip())
        return "\n".join(_format_single_stock_status(result))

    # ---- 整体查询分支 ----
    basics_sync = await _query_stock_basics_sync(db)
    hist_overview = await _query_historical_overview(db)
    fin_overview = await _query_financial_overview(db)
    running_tasks = await _query_running_sync_tasks(db)

    lines = ["📊 数据同步状态总览"]

    # 1) 股票基础数据同步任务
    if basics_sync.get("available"):
        doc = basics_sync["doc"]
        status = doc.get("status", "未知")
        emoji, status_cn = _summarize_status(status)
        lines.append("")
        lines.append("【1】股票基础数据（A 股列表+行业+财务指标）")
        lines.append(f"- 状态: {emoji} {status_cn}")
        if doc.get("started_at"):
            lines.append(f"- 最近开始时间: {_format_time_ago(doc.get('started_at'))}")
        if doc.get("finished_at"):
            lines.append(f"- 最近完成时间: {_format_time_ago(doc.get('finished_at'))}")
        total = doc.get("total", 0) or 0
        inserted = doc.get("inserted", 0) or 0
        updated = doc.get("updated", 0) or 0
        errors = doc.get("errors", 0) or 0
        if total > 0 or inserted > 0 or updated > 0:
            lines.append(f"- 总数 {total}：新增 {inserted}，更新 {updated}，错误 {errors}")
        if doc.get("last_trade_date"):
            lines.append(f"- 最近交易日: {doc.get('last_trade_date')}")
        sources_used = doc.get("data_sources_used") or []
        if sources_used:
            lines.append(f"- 使用的数据源: {', '.join(sources_used)}")
        if doc.get("message") and status in {"failed", "success_with_errors"}:
            lines.append(f"- 备注: {doc.get('message')}")
    else:
        lines.append("")
        lines.append("【1】股票基础数据: ⚪ 从未运行过同步任务")

    # 2) 历史行情数据整体情况
    lines.append("")
    lines.append("【2】历史行情数据（historical_data）")
    if hist_overview.get("error"):
        lines.append(f"- ❌ 查询失败: {hist_overview['error']}")
    else:
        symbol_count = hist_overview.get("symbol_count", 0)
        total_records = hist_overview.get("total_records", 0)
        latest_date = hist_overview.get("latest_date")
        lines.append(f"- 已覆盖股票数: {symbol_count}")
        lines.append(f"- 总记录数: {total_records}")
        lines.append(f"- 最新数据日期: {latest_date or '无'}")
        if symbol_count == 0:
            lines.append("- ⚠️ 数据为空，建议触发股票基础数据同步后再做单股同步")

    # 3) 财务数据整体情况
    lines.append("")
    lines.append("【3】财务数据（stock_financial_data）")
    if fin_overview.get("error"):
        lines.append(f"- ❌ 查询失败: {fin_overview['error']}")
    else:
        symbol_count = fin_overview.get("symbol_count", 0)
        total_records = fin_overview.get("total_records", 0)
        latest_updated = fin_overview.get("latest_updated")
        lines.append(f"- 已覆盖股票数: {symbol_count}")
        lines.append(f"- 总记录数: {total_records}")
        lines.append(f"- 最近更新时间: {_format_time_ago(latest_updated)}")

    # 4) 正在运行中的同步任务
    lines.append("")
    lines.append("【4】运行中的同步任务")
    if not running_tasks:
        lines.append("- 💤 当前无运行中的同步任务")
    else:
        lines.append(f"- 🔄 共 {len(running_tasks)} 个任务在运行:")
        for t in running_tasks[:5]:
            task_type = t.get("task_type", "?")
            sym = t.get("symbol", "?")
            st = t.get("status", "?")
            started = _format_time_ago(t.get("started_at")) if t.get("started_at") else "?"
            progress = t.get("progress")
            progress_str = f"，进度 {progress}" if progress is not None else ""
            lines.append(f"  • [{task_type}] {sym} | {st} | 开始于 {started}{progress_str}")

    # 5) 综合建议
    lines.append("")
    lines.append("💡 综合判断")
    suggestions = []

    basics_status = basics_sync.get("doc", {}).get("status") if basics_sync.get("available") else "never_run"
    if basics_status == "running":
        suggestions.append("股票基础数据同步正在运行，请等待完成再查看详情")
    elif basics_status == "failed":
        suggestions.append("⚠️ 股票基础数据同步上次失败，建议在「数据同步」页面查看错误原因或重新触发")
    elif basics_status in ("never_run", "idle") or not basics_sync.get("available"):
        suggestions.append("股票基础数据尚未同步过，建议先触发股票基础数据同步")

    hist_symbol_count = hist_overview.get("symbol_count", 0) if not hist_overview.get("error") else 0
    if hist_symbol_count == 0:
        suggestions.append("历史行情数据为空，分析前需要先同步股票数据")
    elif hist_symbol_count < 100:
        suggestions.append(f"历史行情仅覆盖 {hist_symbol_count} 只股票，建议补充同步")

    fin_symbol_count = fin_overview.get("symbol_count", 0) if not fin_overview.get("error") else 0
    if fin_symbol_count == 0:
        suggestions.append("财务数据为空，做财务分析前需要先同步")

    if not suggestions:
        lines.append("- ✅ 数据同步正常，可正常进行分析任务")
    else:
        for s in suggestions:
            lines.append(f"- {s}")

    lines.append("")
    lines.append("📌 说明：京东云版仅支持 Tushare + AKShare 两个数据源，强制单并发，同步会比较慢")

    return "\n".join(lines)
