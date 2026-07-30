"""
报告查询类工具

提供分析报告的搜索、详情查看和最新报告获取功能。
查询范围限定为当前用户的报告。
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import get_current_assistant_thread_id, require_current_user_id

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
    description="在数据库中检索用户已有的历史分析报告，支持按股票代码、关键词、日期范围筛选。返回报告摘要列表（标题、股票、日期、结论），不含完整正文。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["report_query", "analysis_report", "search", "query", "assistant_ops", "report_search", "report_history", "report_filtering", "stock_report"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["report_search", "report_history_query", "analysis_report_filtering", "stock_report_lookup", "report_summary_viewing"],
    returns="返回文本格式的报告摘要列表，包含任务ID、股票代码、日期和结论摘要。",
    when_to_use="当用户想搜索、查找或筛选历史分析报告时使用，支持按股票代码、关键词或日期范围筛选。",
)
async def search_reports(
    symbol: Annotated[Optional[str], "股票代码筛选，如 600519"] = None,
    keyword: Annotated[Optional[str], "搜索关键词，匹配报告内容"] = None,
    date_range: Annotated[Optional[str], "日期范围: today / last_week / last_month 或 YYYY-MM-DD~YYYY-MM-DD"] = None,
    limit: Annotated[int, "返回数量上限，默认5"] = 5,
) -> str:
    """搜索分析报告列表，返回精简摘要（标题、股票、日期、结论），不含完整内容。"""
    try:
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
            date_str = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else (str(created)[:16] if created else "未知")
            rec = (doc.get("result") or {}).get("recommendation", "")
            summary = (doc.get("result") or {}).get("summary", "")
            brief = (rec or summary or "无摘要")[:120]
            results.append(f"  [{doc['task_id'][:8]}] {sym} | {date_str} | {brief}")

        if not results:
            return "未找到符合条件的分析报告。"
        return f"📊 找到 {len(results)} 条报告：\n" + "\n".join(results) + "\n\n💡 使用「查看报告详情」获取完整内容。"
    except Exception as e:
        logger.exception("[search_reports] 查询报告失败: %s", e)
        return f"查询报告时出错: {str(e)}"


@tool
@register_tool(
    tool_id="get_report_detail",
    name="查看报告详情",
    description="根据任务ID获取分析报告内容。支持两种模式：1) 不传 module_key 返回顶层摘要（研究结论倾向、关键要点、摘要）；2) 传 module_key 返回指定子模块的完整正文内容（如 market_report/fundamentals_report/news_report/sentiment_report/trader_investment_plan/research_team_decision/risk_management_decision/final_trade_decision 等）。推荐根据用户问题按需获取指定模块，避免一次拉取过多内容。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["report_query", "analysis_report", "detail", "query", "assistant_ops", "report_detail", "report_content", "full_report", "markdown_report", "report_module"],
    tool_role_hint="primary",
    output_shape="report",
    preferred_for=["report_detail_viewing", "full_report_reading", "report_content_retrieval", "analysis_report_detail", "report_module_reading"],
    returns="返回格式化 Markdown 报告。不传 module_key 时返回顶层摘要；传 module_key 时返回指定模块完整正文。",
    when_to_use="当用户想查看分析报告内容时使用。简单问题（如整体结论）不传 module_key；具体维度问题（如技术面/基本面/新闻）传对应 module_key 获取完整内容。",
)
async def get_report_detail(
    task_id: Annotated[str, "分析任务ID"],
    module_key: Annotated[Optional[str], "指定子模块key获取完整正文。可选值：market_report(市场技术分析)/fundamentals_report(基本面研究)/news_report(新闻研究)/sentiment_report(情绪分析)/trader_investment_plan(研究整合意见)/research_team_decision(研究团队结论)/risk_management_decision(风险审阅结论)/final_trade_decision(综合研究结论)/index_report(大盘环境)/sector_report(行业板块)。不传则返回顶层摘要"] = None,
) -> str:
    """获取指定分析任务的报告内容。传 module_key 返回该模块完整正文，不传返回顶层摘要。"""
    try:
        from app.core.database import get_mongo_db
        from app.services.task_analysis_service import get_task_analysis_service
        from app.services.intelligent_assistant_service import attach_report_ref_to_thread

        user_id = require_current_user_id()
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

        # ── 模块模式：返回指定子模块完整正文 ──
        if module_key:
            module_key_clean = module_key.strip()
            reports_dict = r.get("reports") or {}
            if not isinstance(reports_dict, dict) or not reports_dict:
                return f"⚠️ 任务 {task_id} 的报告中未找到任何子模块数据。"
            content = reports_dict.get(module_key_clean)
            if not content or (isinstance(content, str) and not content.strip()):
                available = ", ".join(reports_dict.keys())
                return (
                    f"⚠️ 未找到模块 `{module_key_clean}`。\n"
                    f"该报告包含以下可用模块：{available}\n"
                    f"请从上述模块中选择一个重新调用。"
                )
            label = _ANALYST_LABELS.get(module_key_clean, module_key_clean)
            # 兼容 content 为字典的情况（如 final_trade_decision 可能是结构化数据）
            if isinstance(content, dict):
                content_text = content.get("content") or content.get("report") or content.get("text") or content.get("markdown") or ""
                if not content_text:
                    content_text = json.dumps(content, ensure_ascii=False, indent=2)
            else:
                content_text = str(content)
            return f"# {label}\n\n{content_text}"

        # ── 顶层摘要模式：返回报告整体摘要 ──
        lines = [f"# 📈 {sym} 分析报告"]
        if r.get("recommendation"):
            lines.append(f"\n## 研究结论倾向\n{r['recommendation']}")
        if r.get("confidence_score"):
            lines.append(f"\n**置信度**: {r['confidence_score']}")
        if r.get("risk_level"):
            lines.append(f"**风险等级**: {r['risk_level']}")
        if r.get("key_points"):
            kps = r["key_points"] if isinstance(r["key_points"], list) else [r["key_points"]]
            lines.append("\n## 关键要点\n" + "\n".join(f"- {kp}" for kp in kps))
        if r.get("summary"):
            lines.append(f"\n## 摘要\n{r['summary']}")

        # 列出可用子模块，引导 LLM 按需获取完整内容
        reports_dict = r.get("reports") or {}
        if isinstance(reports_dict, dict) and reports_dict:
            available_lines = []
            for k in reports_dict.keys():
                label = _ANALYST_LABELS.get(k, k)
                available_lines.append(f"  • {k}（{label}）")
            lines.append("\n## 可用子模块")
            lines.append("如需查看某个模块的完整内容，再次调用本工具并传入 module_key 参数：")
            lines.extend(available_lines)

        db = get_mongo_db()
        await attach_report_ref_to_thread(
            db,
            user_id,
            get_current_assistant_thread_id(),
            {
                "ref_type": "stock_report",
                "report_key": task.task_id,
                "source_collection": "unified_analysis_tasks",
                "title": f"{sym} 分析报告",
                "symbol": sym,
                "summary": (r.get("summary") or r.get("recommendation") or "")[:400],
                "status": task.status,
                "task_id": task.task_id,
                "created_at": getattr(task, "created_at", None),
            },
        )

        lines.append(f"\n---\n_任务ID: {task.task_id} | 耗时: {task.execution_time:.1f}s_")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[get_report_detail] 获取报告详情失败: %s", e)
        return f"获取报告详情时出错: {str(e)}"



# ── 各分析师角色中文标签 ──
# 涵盖单股分析报告 reports 字典中可能出现的所有子模块
_ANALYST_LABELS = {
    # 核心决策类
    "final_trade_decision":   "综合研究结论",
    "research_team_decision": "研究团队结论",
    "risk_management_decision": "风险审阅结论",
    "trader_investment_plan": "研究整合意见",
    "investment_plan":        "投资计划",
    # 研究员辩论类
    "bull_researcher":        "乐观情景论证",
    "bear_researcher":        "审慎情景论证",
    "neutral_analyst":        "基准情景评估",
    "risky_analyst":          "高弹性情景评估",
    "safe_analyst":           "防御情景评估",
    # 个股分析模块
    "fundamentals_report":    "基本面研究",
    "market_report":          "市场技术分析",
    "news_report":            "新闻研究",
    "sentiment_report":       "情绪分析",
    "chip_report":            "筹码分布分析",
    # 宏观分析模块
    "index_report":           "大盘环境研究",
    "sector_report":          "行业板块研究",
    # 持仓分析模块（部分报告可能复用）
    "company_overview":       "公司概况",
    "financial_analysis":     "财务分析",
    "technical_analysis":     "技术分析",
    "market_analysis":        "市场分析",
    "risk_analysis":          "风险分析",
    "valuation_analysis":     "估值分析",
    "investment_recommendation": "研究结论摘要",
}
# 按重要性排序，优先展示核心决策
_REPORT_PRIORITY = [
    "final_trade_decision",
    "research_team_decision",
    "risk_management_decision",
    "bull_researcher",
    "bear_researcher",
    "fundamentals_report",
    "market_report",
    "news_report",
    "sentiment_report",
    "investment_plan",
    "trader_investment_plan",
]
_MAX_TOTAL_CHARS = 6000   # 工具返回上限，控制 LLM 上下文
_EXCERPT_CHARS = 500      # 每个分析师报告的摘录字数


@tool
@register_tool(
    tool_id="get_latest_report",
    name="获取最新报告",
    description="读取指定股票最近一次已完成的分析报告摘要（各分析师核心结论+最终研究结论）。不会创建新任务。symbol 为空时返回用户最近一份报告。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["report_query", "analysis_report", "latest", "query", "assistant_ops", "latest_report", "recent_report", "stock_report", "analyst_summary"],
    tool_role_hint="primary",
    output_shape="report",
    preferred_for=["latest_report_viewing", "recent_report_query", "stock_analysis_summary", "analyst_report_summary"],
    returns="返回格式化文本报告，包含投资观点、价格区间、决策依据、关键要点和各分析师摘录。",
    when_to_use="当用户想快速查看某只股票最近一次已完成的分析报告摘要时使用，不会创建新任务。",
)
async def get_latest_report(
    symbol: Annotated[str, "股票代码，如 600519。若用户未指定可传空字符串，则返回最近一次任意股票的报告"],
) -> str:
    """读取某只股票最近一次已完成的分析报告摘要，不创建新任务。symbol 为空时返回用户最新一份报告。"""
    try:
        from bson import ObjectId
        from app.core.database import get_mongo_db
        from app.services.intelligent_assistant_service import attach_report_ref_to_thread

        user_id = require_current_user_id()
        db = get_mongo_db()

        # ── 构造查询：symbol 为空时不限制股票代码 ──
        query: dict = {"user_id": ObjectId(user_id), "status": "completed"}
        sym_clean = (symbol or "").strip()
        if sym_clean:
            query["task_params.symbol"] = sym_clean

        doc = await db.unified_analysis_tasks.find_one(query, sort=[("created_at", -1)])
        if not doc:
            hint = f"{sym_clean} 的" if sym_clean else "任何"
            return (
                f"未找到{hint}分析报告。"
                f"{'你可以使用「触发股票分析」来发起分析。' if sym_clean else '请先触发一次股票分析。'}"
            )

        r = doc.get("result") or {}
        actual_symbol = doc.get("task_params", {}).get("symbol", sym_clean or "未知")
        created = doc.get("created_at")
        date_str = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else (str(created)[:16] if created else "未知")
        task_id = doc.get("task_id", "")

        # ── 第一部分：结构化摘要（必选） ──
        lines: list[str] = [f"📈 {actual_symbol} 分析报告（{date_str}）"]

        decision = r.get("decision") or {}
        action = decision.get("action") or decision.get("analysis_view", "")
        confidence = decision.get("confidence")
        risk_score = decision.get("risk_score")
        price_range = decision.get("price_analysis_range")
        reasoning = (decision.get("reasoning") or "")[:400]

        if action:
            conf_str = f"  置信度: {confidence:.0%}" if confidence is not None else ""
            risk_str = f"  风险分: {risk_score:.0%}" if risk_score is not None else ""
            lines.append(f"\n【投资观点】{action}{conf_str}{risk_str}")
        if price_range and isinstance(price_range, (list, tuple)) and len(price_range) == 2:
            lines.append(f"【价格区间参考】{price_range[0]} ~ {price_range[1]}")
        if reasoning:
            lines.append(f"【决策依据】\n{reasoning}")

        rec = (r.get("recommendation") or "")[:300]
        if rec and rec != action:
            lines.append(f"\n【建议摘要】\n{rec}")

        risk_level = r.get("risk_level", "")
        if risk_level:
            lines.append(f"【风险等级】{risk_level}")

        key_points = r.get("key_points") or []
        if key_points:
            kp_text = "\n".join(f"  • {kp}" for kp in key_points[:5])
            lines.append(f"\n【关键要点】\n{kp_text}")

        summary = (r.get("summary") or "")[:400]
        if summary:
            lines.append(f"\n【综合摘要】\n{summary}")

        await attach_report_ref_to_thread(
            db,
            user_id,
            get_current_assistant_thread_id(),
            {
                "ref_type": "stock_report",
                "report_key": task_id,
                "source_collection": "unified_analysis_tasks",
                "title": f"{actual_symbol} 分析报告",
                "symbol": actual_symbol,
                "summary": (summary or rec or reasoning or "")[:400],
                "status": doc.get("status") or "completed",
                "task_id": task_id,
                "created_at": created,
            },
        )

        # ── 第二部分：各分析师摘录（按优先级，受总字数限制） ──
        reports: dict = r.get("reports") or {}
        if reports:
            lines.append("\n─── 各分析师摘录 ───")
            current_len = sum(len(l) for l in lines)
            for key in _REPORT_PRIORITY:
                if current_len >= _MAX_TOTAL_CHARS:
                    lines.append("（更多内容已省略，可用「查看报告详情」获取完整版）")
                    break
                text = reports.get(key)
                if not text or not isinstance(text, str) or len(text.strip()) < 20:
                    continue
                label = _ANALYST_LABELS.get(key, key)
                excerpt = text.strip()[:_EXCERPT_CHARS]
                if len(text.strip()) > _EXCERPT_CHARS:
                    excerpt += "…"
                snippet = f"\n[{label}]\n{excerpt}"
                lines.append(snippet)
                current_len += len(snippet)

        lines.append(f"\n─\n任务ID: {task_id[:12]}…")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[get_latest_report] 获取最新报告失败: %s", e)
        return f"获取最新报告时出错: {str(e)}"


@tool
@register_tool(
    tool_id="search_attachable_reports",
    name="搜索可关联旧报告",
    description="搜索当前主题下可手动关联的旧报告。适合用户说‘把宁德时代旧报告挂到当前主题前，先查一下有哪些旧报告可选’。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["report_query", "analysis_report", "search", "attachable", "assistant_ops", "report_attachment", "topic_report_linking", "report_search"],
    tool_role_hint="specialized",
    output_shape="text",
    preferred_for=["attachable_report_search", "report_attachment_query", "topic_report_linking_prep"],
    returns="返回文本列表，包含可关联旧报告的标题、股票代码、创建时间和报告标识。",
    when_to_use="当用户想把某只股票的旧报告关联到当前主题前，需要先查看有哪些可选报告时使用。",
)
async def search_attachable_reports(
    keyword: Annotated[Optional[str], "股票代码、公司名或报告关键词，如 宁德时代 / 比亚迪 / 300750"] = None,
    report_type: Annotated[str, "报告类型：stock_report 单股报告；position_report 持仓报告"] = "stock_report",
    limit: Annotated[int, "返回数量上限，默认 5"] = 5,
) -> str:
    """搜索当前主题可关联的旧报告。"""
    try:
        from app.core.database import get_mongo_db
        from app.services.intelligent_assistant_service import search_assistant_attachable_reports

        user_id = require_current_user_id()
        thread_id = get_current_assistant_thread_id()
        if not thread_id:
            return "当前没有选中的研究主题，无法搜索可关联报告。"

        db = get_mongo_db()
        items = await search_assistant_attachable_reports(
            db,
            user_id,
            thread_id,
            ref_type=(report_type or "stock_report").strip() or "stock_report",
            keyword=(keyword or "").strip() or None,
            limit=max(1, min(limit, 10)),
        )
        if not items:
            target = (keyword or "历史报告").strip() or "历史报告"
            return f"未找到与“{target}”匹配的可关联旧报告。"

        lines = [f"找到 {len(items)} 条可关联旧报告："]
        for item in items:
            title = item.get("title") or "未命名报告"
            symbol = item.get("symbol") or ""
            created_at = item.get("created_at")
            if hasattr(created_at, "strftime"):
                created_text = created_at.strftime("%Y-%m-%d %H:%M")
            else:
                created_text = str(created_at)[:16] if created_at else "未知时间"
            report_key = item.get("report_key") or ""
            lines.append(f"- {title} | {symbol} | {created_text} | key={report_key}")
        lines.append("如需直接挂到当前主题，可继续说：把这份旧报告关联到当前主题。")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[search_attachable_reports] 搜索可关联旧报告失败: %s", e)
        return f"搜索可关联旧报告时出错: {str(e)}"


@tool
@register_tool(
    tool_id="attach_existing_report_to_current_topic",
    name="关联旧报告到当前主题",
    description="把用户历史上已经生成过的旧报告直接挂到当前研究主题。适合用户说‘把宁德时代旧报告关联到当前主题’。默认关联最新匹配的一份。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["report_query", "analysis_report", "attach", "link", "assistant_ops", "report_attachment", "topic_report_linking", "report_binding"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["report_attachment", "topic_report_linking", "historical_report_binding", "report_to_topic_association"],
    returns="返回文本消息，包含关联结果和报告标识。",
    when_to_use="当用户要求把某只股票的历史旧报告直接挂到当前研究主题时使用。",
)
async def attach_existing_report_to_current_topic(
    keyword: Annotated[str, "股票代码、公司名或报告关键词，如 宁德时代 / 比亚迪 / 300750"],
    report_type: Annotated[str, "报告类型：stock_report 单股报告；position_report 持仓报告"] = "stock_report",
) -> str:
    """根据关键词将最新匹配的旧报告挂到当前主题。"""
    try:
        from app.core.database import get_mongo_db
        from app.services.intelligent_assistant_service import (
            attach_existing_report_to_thread,
            search_assistant_attachable_reports,
        )

        user_id = require_current_user_id()
        thread_id = get_current_assistant_thread_id()
        if not thread_id:
            return "当前没有选中的研究主题，无法关联旧报告。"

        keyword_clean = (keyword or "").strip()
        if not keyword_clean:
            return "请提供股票代码、公司名或报告关键词，例如：宁德时代、比亚迪、300750。"

        db = get_mongo_db()
        matches = await search_assistant_attachable_reports(
            db,
            user_id,
            thread_id,
            ref_type=(report_type or "stock_report").strip() or "stock_report",
            keyword=keyword_clean,
            limit=3,
        )
        if not matches:
            return f"未找到与“{keyword_clean}”匹配的旧报告，暂时无法关联。"

        target = matches[0]
        attached_ref = await attach_existing_report_to_thread(
            db,
            user_id,
            thread_id,
            target.get("ref_type") or report_type,
            target.get("report_key") or "",
        )
        if not attached_ref:
            return f"找到了“{keyword_clean}”的旧报告，但关联失败。"

        title = attached_ref.get("title") or keyword_clean
        report_key = attached_ref.get("report_key") or ""
        extra = ""
        if len(matches) > 1:
            extra = f"\n另外还找到 {len(matches) - 1} 条相近历史报告，如需可继续指定日期或让我继续关联。"
        return f"已将旧报告《{title}》关联到当前主题。\n报告标识: {report_key}{extra}"
    except Exception as e:
        logger.exception("[attach_existing_report_to_current_topic] 关联旧报告失败: %s", e)
        return f"关联旧报告时出错: {str(e)}"
