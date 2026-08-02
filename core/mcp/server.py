"""
TradingAgents-CN MCP Server

使用 fastmcp 暴露多智能体分析能力，供外部 MCP Client 调用。

MCP 工具列表:
- analyze_stock       — 触发股票分析（支持阻塞/非阻塞）
- get_report          — 查询历史分析报告
- chat_with_assistant — 与分析助理自由对话
- list_workflows      — 列出可用分析工作流
- screen_stocks       — 按条件智能选股（自然语言）
- get_market_overview — 获取市场概览（A 股）
"""

import asyncio
import logging
import os
from typing import Optional

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP, Context

from core.mcp.auth import mcp_auth

logger = logging.getLogger(__name__)

# ── FastMCP 实例 ──
# 当环境变量 MCP_AUTH_ENABLED=true 时启用 API Key 认证；
# 否则（开发/stdio 模式）不启用认证。
_auth_enabled = os.getenv("MCP_AUTH_ENABLED", "false").lower() in ("true", "1", "yes")

_auth_settings = None
if _auth_enabled:
    _auth_settings = AuthSettings(
        issuer_url=os.getenv("MCP_AUTH_ISSUER_URL", "http://127.0.0.1:8000/mcp"),
        resource_server_url=os.getenv("MCP_RESOURCE_SERVER_URL", "http://127.0.0.1:8000/mcp"),
        required_scopes=mcp_auth.required_scopes,
    )

mcp = FastMCP(
    "TradingAgents-CN",
    version="1.0.0",
    instructions=(
        "TradingAgents-CN 是一个多智能体 A 股分析系统。\n"
        "你可以用 analyze_stock 触发深度分析，用 get_report 查看报告，\n"
        "用 chat_with_assistant 进行自由对话，用 list_workflows 查看可用工作流，\n"
        "用 screen_stocks 按条件智能选股，用 get_market_overview 获取 A 股市场概览。"
    ),
    auth=_auth_settings,
    token_verifier=mcp_auth if _auth_enabled else None,
)


# ── 数据库初始化辅助 ──
_db_initialized = False


async def _ensure_db():
    """确保数据库连接已初始化（惰性初始化，仅首次调用时执行）"""
    global _db_initialized
    if _db_initialized:
        return
    from app.core.database import init_database
    await init_database()
    _db_initialized = True
    logger.info("✅ MCP Server 数据库连接已初始化")


# ── 深度映射（与 assistant_ops 保持一致）──
_DEPTH_MAP = {1: "快速", 2: "基础", 3: "标准", 4: "深度", 5: "全面"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP Tool 1: analyze_stock
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
async def analyze_stock(
    symbol: str,
    depth: int = 3,
    wait: bool = False,
    workflow_id: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """
    对指定 A 股股票进行多智能体协作分析。

    Args:
        symbol: 股票代码，6位数字，如 "600519"（贵州茅台）、"000858"（五粮液）
        depth: 分析深度 1-5（1=快速, 2=基础, 3=标准, 4=深度, 5=全面），默认 3
        wait: 是否阻塞等待分析完成。True=等待完成后返回完整报告（最长5分钟）；False=立即返回任务ID
        workflow_id: 指定工作流ID（可选，不指定则使用默认工作流）

    Returns:
        wait=False 时返回任务ID和状态提示；wait=True 时返回完整 Markdown 分析报告
    """
    await _ensure_db()

    from bson import ObjectId
    from app.services.task_analysis_service import get_task_analysis_service
    from app.models.analysis import AnalysisTaskType
    from core.tools.context import set_current_user_id

    mcp_user_id = await _get_mcp_user_id(ctx)
    set_current_user_id(mcp_user_id)

    service = get_task_analysis_service()
    depth_label = _DEPTH_MAP.get(depth, "标准")

    if wait:
        # 阻塞模式：创建并等待完成
        task = await service.create_and_execute_task(
            user_id=ObjectId(mcp_user_id),
            task_type=AnalysisTaskType.STOCK_ANALYSIS,
            task_params={"symbol": symbol, "market_type": "cn", "research_depth": depth_label, "_mcp_source": True},
            engine_type="auto",
            workflow_id=workflow_id,
        )
        return _format_report(task)
    else:
        # 非阻塞模式：立即返回 task_id
        task = await service.create_task(
            user_id=ObjectId(mcp_user_id),
            task_type=AnalysisTaskType.STOCK_ANALYSIS,
            task_params={"symbol": symbol, "market_type": "cn", "research_depth": depth_label, "_mcp_source": True},
            engine_type="auto",
            workflow_id=workflow_id,
        )
        asyncio.create_task(service.execute_task(task.task_id))
        return (
            f"✅ 分析任务已创建\n"
            f"- 任务ID: {task.task_id}\n"
            f"- 股票: {symbol}\n"
            f"- 深度: {depth_label}\n"
            f"- 预计 2-5 分钟完成\n\n"
            f"请稍后调用 get_report(task_id=\"{task.task_id}\") 获取完整报告。"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP Tool 2: get_report
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
async def get_report(
    task_id: Optional[str] = None,
    symbol: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """
    查询分析报告。可通过任务ID或股票代码查询。

    Args:
        task_id: 分析任务ID（由 analyze_stock 返回）
        symbol: 股票代码（查询该股票最近一次已完成的报告）

    Returns:
        Markdown 格式的分析报告，或任务状态信息
    """
    if not task_id and not symbol:
        return "❌ 请提供 task_id 或 symbol 参数"

    await _ensure_db()

    from bson import ObjectId
    from app.services.task_analysis_service import get_task_analysis_service
    from app.core.database import get_mongo_db
    from core.tools.context import set_current_user_id

    mcp_user_id = await _get_mcp_user_id(ctx)
    set_current_user_id(mcp_user_id)

    if task_id:
        # 按 task_id 查询
        service = get_task_analysis_service()
        task = await service.get_task(task_id)
        if not task:
            return f"❌ 未找到任务: {task_id}"
        if task.status != "completed":
            status_emoji = {"pending": "⏳", "processing": "🔄", "failed": "❌", "cancelled": "🚫"}
            emoji = status_emoji.get(task.status, "❓")
            return f"{emoji} 任务尚未完成（状态: {task.status}，进度: {task.progress}%）"
        return _format_report(task)
    else:
        # 按 symbol 查询最近报告
        db = get_mongo_db()
        doc = await db.unified_analysis_tasks.find_one(
            {"user_id": ObjectId(mcp_user_id), "task_params.symbol": symbol, "status": "completed"},
            sort=[("created_at", -1)],
        )
        if not doc:
            return f"未找到 {symbol} 的分析报告。你可以调用 analyze_stock(symbol=\"{symbol}\") 发起分析。"

        # 构建简要报告
        result = doc.get("result", {})
        recommendation = result.get("recommendation", "无")
        confidence = result.get("confidence", "N/A")
        summary = result.get("summary", "无摘要")
        return (
            f"# {symbol} 最近分析报告\n\n"
            f"**研究结论倾向**: {recommendation}\n"
            f"**把握程度**: {confidence}\n\n"
            f"## 摘要\n{summary}\n\n"
            f"💡 使用 get_report(task_id=\"{doc.get('task_id', '')}\") 获取完整详情。"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP Tool 3: chat_with_assistant
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
async def chat_with_assistant(message: str, ctx: Context = None) -> str:
    """
    与 TradingAgents 分析助理自由对话。
    助理具备数据查询、分析触发、报告查看、股票关注列表管理等操作能力。

    Args:
        message: 你的问题或指令，如 "帮我分析600519"、"最近有哪些分析报告"、"茅台基本面怎么样"

    Returns:
        助理的回复
    """
    await _ensure_db()

    from app.services.intelligent_assistant_service import chat_with_assistant as _chat
    from app.core.database import get_mongo_db

    mcp_user_id = await _get_mcp_user_id(ctx)
    db = get_mongo_db()

    result = await _chat(
        db=db,
        user_message=message,
        user_id=mcp_user_id,
    )
    return result.get("reply", "助理暂时无法回复，请稍后再试。")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP Tool 4: list_workflows
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
async def list_workflows(ctx: Context = None) -> str:
    """
    列出系统中可用的分析工作流。
    每个工作流代表不同的分析策略（如标准分析、深度分析、快速筛选等）。

    Returns:
        可用工作流列表，包含 ID、名称和描述
    """
    await _ensure_db()

    from app.core.database import get_mongo_db

    db = get_mongo_db()
    cursor = db.workflow_definitions.find(
        {"is_active": True},
        {"workflow_id": 1, "name": 1, "description": 1, "category": 1, "_id": 0},
    )
    workflows = await cursor.to_list(length=50)

    if not workflows:
        return "当前没有可用的工作流。"

    lines = ["# 可用分析工作流\n"]
    for wf in workflows:
        wf_id = wf.get("workflow_id", "N/A")
        name = wf.get("name", "未命名")
        desc = wf.get("description", "无描述")
        cat = wf.get("category", "")
        cat_tag = f" [{cat}]" if cat else ""
        lines.append(f"- **{name}**{cat_tag}\n  ID: `{wf_id}`\n  {desc}\n")

    lines.append("\n💡 在 analyze_stock 中使用 workflow_id 参数指定工作流。")
    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP Tool 5: screen_stocks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
async def screen_stocks(
    criteria: str,
    max_stocks: int = 10,
    ctx: Context = None,
) -> str:
    """
    按自然语言条件智能筛选 A 股，返回符合条件的股票列表及理由。

    Args:
        criteria: 筛选条件（自然语言），如 "PE小于20的科技股"、"市值大于100亿的消费龙头"
        max_stocks: 最多返回股票数量，默认 10

    Returns:
        选股结果说明与股票列表（含代码、名称、简要理由）
    """
    await _ensure_db()

    from app.core.database import get_mongo_db
    from app.services.intelligent_screening_service import IntelligentScreeningService
    from core.tools.context import set_current_user_id

    mcp_user_id = await _get_mcp_user_id(ctx)
    set_current_user_id(mcp_user_id)

    db = get_mongo_db()
    service = IntelligentScreeningService(db)
    result = await service.run_direct_screening(
        user_id=mcp_user_id,
        criteria=criteria,
        max_stocks=max_stocks,
    )
    reply = result.get("reply", "选股服务暂不可用。")
    stocks = result.get("stocks") or []
    if stocks:
        lines = [reply, "\n## 筛选结果\n"]
        for i, s in enumerate(stocks[:max_stocks], 1):
            code = s.get("code", "")
            name = s.get("name", "")
            reason = s.get("reason", "")
            lines.append(f"{i}. **{name}**({code}) {reason}")
        return "\n".join(lines)
    return reply


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP Tool 6: get_market_overview
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@mcp.tool()
async def get_market_overview(
    market: str = "cn",
    ctx: Context = None,
) -> str:
    """
    获取指定市场的整体概览（指数涨跌、成交等）。
    当前仅支持 A 股（cn）。

    Args:
        market: 市场代码，cn=A股 / hk=港股 / us=美股；暂仅支持 cn

    Returns:
        市场概览报告（Markdown）
    """
    if market and market.lower() not in ("cn", "china", "a", "a股"):
        return "❌ 当前仅支持 A 股市场概览，请使用 market=\"cn\"。港股/美股概览后续开放。"

    await _ensure_db()

    from app.services.intelligent_assistant_service import _get_latest_trade_date
    from core.tools import get_tool_registry

    curr_date = _get_latest_trade_date()
    registry = get_tool_registry()
    fn = registry.get_function("get_china_market_overview")
    if not fn:
        return "❌ 中国市场概览工具未注册，请检查系统配置。"
    try:
        report = await asyncio.to_thread(fn, curr_date=curr_date)
        return report if report else "暂无市场概览数据。"
    except Exception as e:
        logger.warning("get_market_overview 调用失败: %s", e)
        return f"❌ 获取市场概览失败: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 辅助函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _get_mcp_user_id(ctx: Optional[Context] = None) -> str:
    """获取 MCP 服务用户 ID

    优先级：
    1. 从 Context.client_id 获取（认证模式，API Key 映射的 user_id）
    2. 从数据库查找管理员用户（未认证 / stdio 模式的回退方案）
    """
    # 1. 优先使用认证后的 client_id
    if ctx is not None:
        client_id = ctx.client_id
        if client_id:
            return client_id

    # 2. 回退：从数据库查找默认用户
    from app.core.database import get_mongo_db

    db = get_mongo_db()
    user = await db.users.find_one({"role": "admin"}, {"_id": 1})
    if user:
        return str(user["_id"])

    user = await db.users.find_one({}, {"_id": 1})
    if user:
        return str(user["_id"])

    raise RuntimeError("数据库中没有用户，请先创建用户。")


def _format_report(task) -> str:
    """将分析任务结果格式化为 Markdown 报告"""
    if not task.result:
        return "⚠️ 任务已完成但未生成报告数据。"

    result = task.result if isinstance(task.result, dict) else {}
    symbol = (task.task_params or {}).get("symbol", "未知")
    recommendation = result.get("recommendation", "无")
    confidence = result.get("confidence", "N/A")
    summary = result.get("summary", "")
    risk = result.get("risk_assessment", "")
    key_points = result.get("key_points", [])

    lines = [
        f"# {symbol} 分析报告\n",
        f"**研究结论倾向**: {recommendation}",
        f"**把握程度**: {confidence}\n",
    ]
    if summary:
        lines.append(f"## 摘要\n{summary}\n")
    if risk:
        lines.append(f"## 风险评估\n{risk}\n")
    if key_points:
        lines.append("## 关键要点")
        for pt in key_points:
            lines.append(f"- {pt}")

    return "\n".join(lines)
