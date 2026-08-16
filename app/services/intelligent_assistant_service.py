"""
智能助手服务 - Agent 自主编排模式

支持 ReAct 模式的工具自主调用，用于事件驱动分析、探索性查询等场景。
"""

import asyncio
import inspect
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from bson import ObjectId

# 智能助手整体超时（LLM + 多轮工具调用），默认 300 秒
ASSISTANT_TIMEOUT_SECONDS = int(os.environ.get("ASSISTANT_TIMEOUT_SECONDS", "300"))
# 当对话中使用了重型工具（Agent 调用等）时，额外追加的超时余量
ASSISTANT_HEAVY_TOOL_EXTRA_SECONDS = 120

# 会话历史最大条数（每用户）
ASSISTANT_CONVERSATION_LIMIT = 100
ASSISTANT_DEFAULT_THREAD_ID = "default"
ASSISTANT_MAX_CONTEXT_MESSAGES = 10
ASSISTANT_MAX_REPORT_REFS = 12
ASSISTANT_REPORT_INBOX_TITLE = "报告收纳"

from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.tools.context import set_current_assistant_thread_id, set_current_user_id
from core.llm import UnifiedLLMClient
from core.llm.models import LLMConfig, LLMProvider, Message, MessageRole, ToolCall, ToolResult

logger = logging.getLogger(__name__)

_MEMORY_FACT_KEYWORDS = [
    "结论", "营收", "收入", "净利润", "扣非", "毛利率", "现金流", "分红", "股息率", "估值",
    "预期", "超预期", "低于预期", "价格战", "成本", "销量", "增长", "下滑", "风险", "压力",
    "支撑", "阻力", "走势", "震荡", "偏弱", "偏强", "回调", "反弹", "逻辑", "原因",
]

_NUMBER_ONLY_REPLY_RE = re.compile(r"^\s*([1-9]\d?)\s*[\.、\)）]?\s*$")
_NUMBERED_OPTION_LINE_RE = re.compile(r"^\s*(\d{1,2})\s*[\.、\)）]\s*(.+?)\s*$")


def _extract_memory_subject(user_msg: str, assistant_msg: str) -> str:
    title_match = re.search(r"##\s*[📌✅⚠️🔍💡]*\s*([A-Za-z0-9\u4e00-\u9fff]{2,20})(?:[（(][^\n]{0,20}[)）])?(?:——|\-|：|:)", assistant_msg or "")
    if title_match:
        return title_match.group(1).strip()

    user_match = re.search(r"([A-Za-z0-9\u4e00-\u9fff]{2,20})(?:股票|走势|业绩|表现|分红|怎么看|为什么|如何)", user_msg or "")
    if user_match:
        return user_match.group(1).strip()

    return ""


def _clean_memory_line(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^#+\s*", "", cleaned)
    cleaned = re.sub(r"^[>\-*\d\.\s✅⚠️📌🔍💡]+", "", cleaned)
    cleaned = re.sub(r"\*+", "", cleaned)
    cleaned = re.sub(r"`+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" |：:-")


def _build_fallback_memory_facts(user_msg: str, assistant_msg: str, limit: int = 5) -> List[str]:
    subject = _extract_memory_subject(user_msg, assistant_msg)
    candidates: List[str] = []

    for raw_line in (assistant_msg or "").splitlines():
        line = _clean_memory_line(raw_line)
        if not line or len(line) < 10:
            continue
        if line.startswith("|") or set(line) <= {"-", "|", ":", " "}:
            continue
        if "数据来源" in line:
            continue
        if any(keyword in line for keyword in _MEMORY_FACT_KEYWORDS):
            if subject and subject not in line and len(line) < 70:
                line = f"{subject}：{line}"
            candidates.append(line[:120])

    seen = set()
    facts: List[str] = []
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        facts.append(item)
        if len(facts) >= limit:
            break
    return facts


# 股票代码正则（6位数字，A股主板/创业板/科创板）
_STOCK_CODE_RE = re.compile(r"\b(00|30|60|68)\d{4}\b")
# 数据相关关键词——用于判断用户问题是否涉及股票数据查询
_STOCK_DATA_KEYWORDS = [
    "财报", "利润", "营收", "收入", "净利润", "毛利率", "现金流", "资产", "负债",
    "估值", "市盈率", "市净率", "pe", "pb", "ps",
    "销量", "产量", "出栏", "交付",
    "价格", "股价", "行情", "涨跌", "涨幅", "跌幅",
    "入手", "买入", "卖出", "加仓", "减仓", "持有", "清仓", "值得", "能不能买", "该不该",
    "分析", "研究", "怎么样", "如何", "技术面", "基本面", "基本面",
]


def _extract_stock_code(user_message: str) -> Optional[str]:
    """从用户消息中提取 6 位 A 股股票代码。"""
    if not user_message:
        return None
    match = _STOCK_CODE_RE.search(user_message)
    if match:
        return match.group(0)
    return None


async def _resolve_stock_name_to_code(user_message: str, db=None) -> Optional[str]:
    """尝试从用户消息中匹配股票名称并返回股票代码。

    查询 stock_basic_info 集合，用消息中的文本匹配 stock_name 字段。
    db 参数优先；未传时尝试 get_mongo_db()（某些上下文会失败）。
    """
    if not user_message:
        return None
    try:
        if db is None:
            from app.core.database import get_mongo_db
            db = get_mongo_db()
        # 取消息中可能的股票名称关键词（含"股份""集团"等后缀的词）
        # 简单策略：用消息中的连续中文字符段去匹配 stock_name
        import re as _re
        chinese_segments = _re.findall(r"[\u4e00-\u9fa5]{2,8}(?:股份|集团|科技|新能|汽车|银行|证券|保险|能源)", user_message)
        if not chinese_segments:
            # 也尝试匹配一些常见简称
            common_names = ["牧原", "赛力斯", "比亚迪", "宁德", "温氏", "新希望", "万科", "茅台", "五粮液"]
            for name in common_names:
                if name in user_message:
                    chinese_segments = [name]
                    break

        if not chinese_segments:
            return None

        # 查询数据库匹配股票名称（字段为 name/symbol）
        for segment in chinese_segments:
            doc = await db["stock_basic_info"].find_one(
                {"name": {"$regex": segment, "$options": "i"}},
                {"symbol": 1, "name": 1, "code": 1}
            )
            if not doc:
                doc = await db["stock_basic_info"].find_one(
                    {"name": {"$regex": segment[:2], "$options": "i"}},
                    {"symbol": 1, "name": 1, "code": 1}
                )
            if doc and doc.get("symbol"):
                return doc["symbol"]

        return None
    except Exception as e:
        logger.warning("[智能助手] 股票名称解析失败: %s", e)
        return None


async def _check_stock_data_sync(symbol: str, db=None) -> dict:
    """检查单只股票的数据同步状态，返回 {has_historical, has_financial, has_basic, ...}。

    直接查询实际数据集合（与前端数据检验接口一致）：
    - 基础数据: stock_basic_info（按 symbol）
    - 历史行情: stock_daily_quotes（按 symbol/code）
    - 财务数据: stock_financial_data（按 symbol）
    """
    try:
        if db is None:
            from app.core.database import get_mongo_db
            db = get_mongo_db()

        normalized = str(symbol).strip().upper()
        if "." in normalized:
            normalized = normalized.split(".", 1)[0]

        # 基础数据
        basic_doc = await db["stock_basic_info"].find_one(
            {"symbol": normalized}, {"symbol": 1, "name": 1}
        )

        # 历史行情（stock_daily_quotes，兼容 symbol/code 两种字段）
        hist_count = await db["stock_daily_quotes"].count_documents({"symbol": normalized})
        if hist_count == 0:
            hist_count = await db["stock_daily_quotes"].count_documents({"code": normalized})
        hist_latest = await db["stock_daily_quotes"].find_one(
            {"symbol": normalized}, sort=[("trade_date", -1)]
        ) or await db["stock_daily_quotes"].find_one(
            {"code": normalized}, sort=[("trade_date", -1)]
        )
        hist_last_date = None
        if hist_latest:
            d = hist_latest.get("trade_date") or hist_latest.get("date")
            hist_last_date = str(d)[:10] if d else None

        # 财务数据
        fin_count = await db["stock_financial_data"].count_documents({"symbol": normalized})

        return {
            "has_historical": hist_count > 0,
            "has_financial": fin_count > 0,
            "has_basic": basic_doc is not None,
            "hist_records": hist_count,
            "fin_records": fin_count,
            "hist_last_date": hist_last_date,
            "stock_name": basic_doc.get("name") if basic_doc else None,
            "symbol": normalized,
        }
    except Exception as e:
        logger.warning("[智能助手] 检查股票数据同步状态失败(%s): %s", symbol, e)
        return {"error": str(e)}


# 匹配回复中伪造的工具调用痕迹（如"数据来源：get_xxx_tool"或"📌 数据来源：XXX工具"）
_FABRICATED_TOOL_REF_RE = re.compile(
    r"(数据来源[:：]\s*(get_|fetch_)[a-z_]+|📌\s*数据来源[:：].*工具)",
    re.IGNORECASE,
)
# 匹配回复中出现的具体数字（亿元/万元/元/%/元/公斤等），用于检测未调工具却给数据的情况
_SPECIFIC_NUMBER_RE = re.compile(
    r"[\d,]+\.?\d*\s*(亿元|万元|元|公斤|辆|头|%|pct|分位|x|倍)"
)
# 匹配"工具名(参数) → { JSON结果 }"模式：所有真实工具的返回都是 Markdown 文本，
# 回复中把工具结果包装成 JSON 对象必然是 LLM 编造的结构化字段（如 post_count: 127）
_FABRICATED_TOOL_JSON_RE = re.compile(
    r"(get_|fetch_|trigger_|set_)[a-z0-9_]+\s*\([^)\n]{0,80}\)[^{\n]{0,60}\{[^{}\n]{5,500}\}",
    re.IGNORECASE,
)


def _has_fabricated_tool_json(reply: str) -> bool:
    """检测回复中是否把工具结果编造为 JSON 对象。

    系统所有工具的真实返回均为 Markdown 文本（output_shape=markdown），
    绝不会返回 {"sentiment_score": 0.32, "post_count": 127} 这类 JSON。
    若回复中出现"工具名(参数) ... { json }"模式，说明 LLM 自行构造了
    工具返回的结构化假数据 —— 硬拦截。
    """
    if not reply:
        return False
    m = _FABRICATED_TOOL_JSON_RE.search(reply)
    if m:
        logger.warning("[智能助手] 检测到编造的工具JSON结果: %.120s", m.group(0))
        return True
    return False


def _has_fabricated_tool_refs(reply: str, tools_used: list) -> bool:
    """检测回复中是否伪造了工具调用痕迹。

    判定标准：回复中出现了"数据来源：get_xxx_tool"等字样，
    但 tools_used 为空或不包含对应工具名。
    """
    if not reply:
        return False
    matches = _FABRICATED_TOOL_REF_RE.findall(reply)
    if not matches:
        return False
    # 有工具引用痕迹但没有实际调用任何工具 → 伪造
    if not tools_used:
        return True
    # 有工具引用痕迹，检查引用的工具名是否在 tools_used 中
    # 从回复中提取工具名
    tool_names_in_reply = set()
    for m in re.finditer(r"(get_|fetch_)[a-z_]+", reply, re.IGNORECASE):
        tool_names_in_reply.add(m.group(0).lower())
    tools_used_lower = {t.lower() for t in tools_used}
    # 如果引用的工具名都不在实际调用列表中 → 伪造
    if tool_names_in_reply and not tool_names_in_reply.intersection(tools_used_lower):
        return True
    return False


def _has_unsourced_numbers(reply: str, tools_used: list) -> bool:
    """检测回复中是否包含大量具体数字但未调用任何数据工具。

    用于拦截 LLM 未调工具却在回复中编造精确财务/销量数据的情况。
    """
    if not reply or tools_used:
        return False
    # 统计回复中的具体数字数量
    numbers = _SPECIFIC_NUMBER_RE.findall(reply)
    # 超过 5 个具体数字且未调任何工具 → 大概率编造
    return len(numbers) > 5


# ── 第4道防线：高风险数字溯源校验 ─────────────────────────────────────────────
# 提取回复中带金融单位的高风险数字（长单位优先，避免"元/公斤"被"元"截断；
# 同时覆盖中英文单位写法：元/kg 与 元/公斤 是同一单位）
_RISKY_NUMBER_RE = re.compile(
    r"(\d[\d,]*\.?\d*)\s*(元/[kK][gG]|元/公斤|元/吨|元/斤|亿元|万元|分位|pct|%|倍|元)"
)
# 提取工具返回文本中的所有数字（带金融单位或裸数字，如 JSON 字段值 0.37 / 15764.6）
_TOOL_NUMBER_RE = re.compile(
    r"(\d[\d,]*\.?\d*)\s*(元/[kK][gG]|元/公斤|元/吨|元/斤|亿元|万元|分位|pct|%|倍|元)?"
)
# 金额类单位 → 归一化到"亿元"的换算因子
_AMOUNT_UNIT_FACTOR = {"亿元": 1.0, "万元": 1e-4}
# 匹配容差（工具值与回复值的相对误差上限；1% 覆盖常规四舍五入，
# 同时避免跨语义误匹配——如编造"15.8元/公斤"撞上质押 holding_ratio 15.54）
_TRACE_TOLERANCE = 0.01
# 不可溯源高风险数字达到该数量 → 拦截回复
_UNTRACED_NUMBER_LIMIT = 3


def _normalize_unit(unit: str) -> str:
    """单位别名归一：元/kg 与 元/公斤 视为同一单位。"""
    u = (unit or "").lower()
    return u.replace("/kg", "/公斤").replace("kg", "公斤")


def _parse_number(text: str) -> Optional[float]:
    """'1,771.97' → 1771.97；失败返回 None。"""
    try:
        return float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _extract_risky_numbers(text: str, pattern: re.Pattern) -> list:
    """从文本中提取 (数值, 单位) 列表，单位统一小写。"""
    out = []
    for m in pattern.finditer(text or ""):
        val = _parse_number(m.group(1))
        if val is None:
            continue
        unit = (m.group(2) or "").lower() if pattern.groups >= 2 else ""
        out.append((val, unit))
    return out


def _number_matches(value: float, unit: str, candidates: list) -> bool:
    """判断 (数值, 单位) 是否能在候选集（工具返回数字）中溯源。

    匹配规则：
    - 金额类（亿元/万元）：必须同属金额类，按归一化到亿元后匹配
      （如 15764.6万 ↔ 1.58亿；15764.6万 ≠ 157.6亿，防100倍换算错误）
    - 非金额类（%/元/公斤/kg/倍/分位/裸数字）：单位写法差异（元/kg vs 元/公斤、
      "15.77元一公斤"截断为"元" vs 回复"15.77元/公斤"）按数值直接匹配（1%容差）
    - 不做 ×100 的百分比换算：工具返回 0.37 就是 0.37%，回复写 37% 视为不可溯源
    """
    tol = _TRACE_TOLERANCE
    unit = _normalize_unit(unit)
    value_is_amount = unit in _AMOUNT_UNIT_FACTOR
    for cand_val, cand_unit_raw in candidates:
        cand_unit = _normalize_unit(cand_unit_raw)
        cand_is_amount = cand_unit in _AMOUNT_UNIT_FACTOR
        if value_is_amount or cand_is_amount:
            # 金额类只与金额类匹配（归一化到亿元），不与价格/百分比/裸数字混配
            if value_is_amount and cand_is_amount:
                v1 = value * _AMOUNT_UNIT_FACTOR[unit]
                v2 = cand_val * _AMOUNT_UNIT_FACTOR[cand_unit]
                if abs(v1 - v2) <= tol * max(abs(v2), 1e-9):
                    return True
            continue
        # 非金额类：数值相等即匹配（容忍单位写法差异）
        if abs(value - cand_val) <= tol * max(abs(cand_val), 1e-9):
            return True
    return False


def _get_untraced_risky_numbers(
    reply: str,
    tool_results: Optional[list],
    user_message: str = "",
    history_tool_contents: Optional[list] = None,
    return_candidates: bool = False,
):
    """提取回复中无法在工具返回原文（或用户消息）中溯源的高风险数字。

    Args:
        tool_results: 本轮工具返回（collector 收集）
        user_message: 用户消息（引用用户给的数字不算编造）
        history_tool_contents: 会话历史中 role=tool 的消息内容（多轮对话时，
            引用上一轮工具的真实数据同样可溯源，不应误判）
        return_candidates: True 时返回 (untraced, candidates) 供日志排查

    Returns:
        不可溯源的 "数值+单位" 字符串列表（用于日志与阈值判断）。
    """
    if not reply:
        return ([], []) if return_candidates else []
    # 工具返回原文中的所有数字（含裸数字）作为可信候选集
    candidates: list = []
    for item in (tool_results or []):
        content = item.get("content") or ""
        if not content or item.get("is_error"):
            continue
        candidates.extend(_extract_risky_numbers(content, _TOOL_NUMBER_RE))
    # 会话历史中工具返回过的数字同样可信（多轮引用）
    for content in (history_tool_contents or []):
        if content:
            candidates.extend(_extract_risky_numbers(content, _TOOL_NUMBER_RE))
    # 用户消息中出现的数字也视为可信（助手引用用户给的数字不算编造）
    user_numbers = _extract_risky_numbers(user_message or "", _TOOL_NUMBER_RE)
    candidates.extend(user_numbers)

    untraced = []
    for m in _RISKY_NUMBER_RE.finditer(reply):
        val = _parse_number(m.group(1))
        unit = (m.group(2) or "").lower()
        if val is None:
            continue
        # 排除：年份（1900-2099）、百分比里的小整数序号等噪音由阈值兜底
        if 1900 <= val <= 2099 and val == int(val):
            continue
        if _number_matches(val, unit, candidates):
            continue
        untraced.append(f"{m.group(1)}{m.group(2)}")
    if return_candidates:
        return untraced, candidates
    return untraced


def _has_untraced_risky_numbers(
    reply: str,
    tool_results: Optional[list],
    tools_used: list,
    user_message: str = "",
    history_tool_contents: Optional[list] = None,
) -> bool:
    """第4道防线：调用了工具，但回复中混入大量无法溯源的高风险数字。

    场景：LLM 确实调用了工具（前三道防线通过），却用训练记忆补齐
    工具未返回的数字（如"行业成本线15.8元/公斤""PE近5年75%分位"），
    或对工具数字做错误换算（0.37 说成 37%、15764.6万 说成 157.6亿）。
    """
    if not reply or not tools_used:
        return False
    untraced, candidates = _get_untraced_risky_numbers(
        reply, tool_results, user_message, history_tool_contents, return_candidates=True
    )
    if len(untraced) >= _UNTRACED_NUMBER_LIMIT:
        # 附带候选集摘要，便于排查"数字在工具返回里但没匹配上"的误判（如单位别名差异）
        cand_preview = [f"{v}{u}" for v, u in candidates[:30]]
        logger.warning(
            "[智能助手] 检测到 %d 个无法溯源的高风险数字: %s | 工具候选集(%d个, 前30): %s",
            len(untraced), untraced[:10], len(candidates), cand_preview,
        )
        return True
    return False


def _extract_history_tool_contents(messages: List[Any]) -> List[str]:
    """从对话历史中提取 role=tool 的消息内容（多轮溯源用）。

    上一轮工具返回过的真实数字（如财务数据），本轮回复引用时
    同样应视为可溯源，避免误拦截。
    """
    contents = []
    for m in (messages or []):
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        content = getattr(m, "content", None)
        if content is None and isinstance(m, dict):
            content = m.get("content")
        if role == "tool" and content:
            contents.append(str(content))
    return contents


def _should_force_tool_retry(user_message: str) -> bool:
    """判断是否属于“应优先调用工具”的个人数据查询请求。"""
    text = (user_message or "").strip().lower()
    if not text:
        return False

    # 个人数据+操作查询意图（计划/持仓/复盘/任务/报告等）
    personal_markers = ["我的", "我", "当前", "现在"]
    domain_markers = [
        "交易计划", "投资计划", "计划", "持仓", "仓位", "复盘", "报告", "分析任务", "任务状态",
        "股票关注列表", "定时分析", "提醒", "schedule", "watchlist", "position", "review", "plan",
    ]
    query_markers = ["查看", "列出", "查询", "获取", "多少", "有没有", "是什么", "详情", "状态"]

    has_personal = any(k in text for k in personal_markers)
    has_domain = any(k in text for k in domain_markers)
    has_query = any(k in text for k in query_markers)

    market_markers = [
        "大盘", "指数", "上证", "深证", "创业板", "沪深300", "中证", "点位", "收盘", "开盘",
        "成交额", "量能", "涨跌家数", "北向", "南向", "主力资金", "技术面", "技术指标",
        "macd", "rsi", "kdj", "boll", "布林", "均线", "ma", "ema", "超买", "超卖",
        "背离", "支撑", "阻力", "回调", "反弹", "突破", "压力位", "自然周期",
    ]
    recency_markers = ["最新", "当前", "现在", "今日", "今天", "近期", "最近", "截至目前", "今年", "本周", "本月"]

    has_market = any(k in text for k in market_markers)
    has_recency = any(k in text for k in recency_markers)

    # 至少满足：个人+领域，或 领域+查询，或 市场+近期，或 股票+数据
    # 股票数据类问题：股票代码/名称 + 数据相关词汇（如"牧原股份值得入手吗"）
    import re
    has_stock_code = bool(re.search(r"(00|30|60|68)\d{4}", text))
    has_stock_name = any(k in text for k in ["股份", "集团", "科技", "新能", "汽车", "银行", "证券", "保险", "能源", "牧原", "赛力斯", "比亚迪", "宁德"])
    stock_data_markers = [
        "财报", "利润", "营收", "收入", "净利润", "毛利率", "现金流", "资产", "负债",
        "估值", "市盈率", "市净率", "pe", "pb", "ps",
        "销量", "产量", "出栏", "交付",
        "价格", "股价", "行情", "涨跌", "涨幅", "跌幅",
        "入手", "买入", "卖出", "加仓", "减仓", "持有", "清仓", "值得", "能不能买", "该不该",
        "分析", "研究", "怎么样", "如何",
    ]
    has_stock_data = any(k in text for k in stock_data_markers)
    stock_data_query = (has_stock_code or has_stock_name) and has_stock_data

    return (has_personal and has_domain) or (has_domain and has_query) or (has_market and has_recency) or stock_data_query


async def _record_assistant_token_usage(
    resp_obj: Any,
    session_id: str,
    analysis_type: str = "assistant",
) -> None:
    """记录 LLM 调用的 token 使用情况（失败不影响主流程）。"""
    try:
        from app.services.usage_statistics_service import usage_statistics_service
        await usage_statistics_service.record_llm_usage(
            response=resp_obj,
            session_id=session_id,
            analysis_type=analysis_type,
        )
    except Exception as e:
        logger.warning(f"记录 token 使用失败: {e}")


# =============================================================================
# 用户记忆元工具：让 LLM 在用户表达"请记住""请帮我记下"等意图时主动登记
# 设计文档参考：docs/05-design/v3.0/unified-memory-layer-mem0.md §15.5 P0-1
# =============================================================================

REMEMBER_THIS_TOOL_NAME = "remember_this"


def _build_remember_this_tool_def() -> Dict[str, Any]:
    """构造 `remember_this` 的 OpenAI Function Calling 定义"""
    return {
        "type": "function",
        "function": {
            "name": REMEMBER_THIS_TOOL_NAME,
            "description": (
                "当用户明确表达「请记住」「请帮我记下」「我希望以后也按这个偏好」等意图时调用此工具，"
                "把这条偏好/事实写入用户长期记忆（user_preference）。"
                "调用后请告知用户『已记下』，然后继续完成原本的任务。"
                "禁止滥用：仅当用户**明确表达需要记忆**时调用；用户随口提到的偏好不要写入。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "需要记住的事实文本（一句话，包含足够上下文，如『用户偏好分红率>3%的高股息蓝筹股，回避高市盈率成长股』）",
                    },
                    "category": {
                        "type": "string",
                        "description": "偏好类型：investment_style（投资风格）/ risk_tolerance（风险偏好）/ industry_preference（行业偏好）/ trading_discipline（交易纪律）/ other",
                        "enum": [
                            "investment_style",
                            "risk_tolerance",
                            "industry_preference",
                            "trading_discipline",
                            "other",
                        ],
                    },
                },
                "required": ["content"],
            },
        },
    }


def _make_remember_this_callable(db, user_id: str):
    """生成绑定了 db + user_id 的 remember_this 异步实现。"""

    async def _remember_this(content: str, category: str = "other") -> str:
        if not user_id:
            return "记忆失败：当前会话未关联用户。"
        text = (content or "").strip()
        if not text:
            return "记忆失败：内容为空。"
        try:
            from core.memory.service import get_memory_service
            from core.memory.models import MemoryScope
            svc = get_memory_service(db)
            result = await svc.store(
                [{"role": "user", "content": text}],
                user_id=user_id,
                agent_id="assistant",
                scope=MemoryScope.USER_PREFERENCE,
                metadata={
                    "source": "user_explicit_remember",
                    "category": (category or "other").strip().lower(),
                },
                infer=False,  # 用户已明确表达，不需要 LLM 再提取
            )
            if not result.success:
                logger.warning(f"[智能助手] remember_this 写入失败: {result.error}")
                return f"记忆失败：{result.error or '记忆层不可用'}"
            logger.info(f"[智能助手] remember_this 已写入: user={user_id} category={category}")
            return f"已记下：{text[:60]}{'...' if len(text) > 60 else ''}。下次对话会自动参考此偏好。"
        except Exception as e:
            logger.warning(f"[智能助手] remember_this 异常: {e}")
            return f"记忆失败：{e}"

    return _remember_this


def _should_use_recent_search(user_message: str) -> bool:
    """判断是否属于应优先走近期搜索的事实确认类问题。"""
    text = (user_message or "").strip().lower()
    if not text:
        return False

    recency_markers = [
        "截至目前", "截至现在", "最新", "近期", "最近", "刚刚", "今日", "现在",
        "确认", "核实", "联网", "公告", "新闻", "消息", "进展",
    ]
    fact_markers = [
        "持股", "持股比例", "减持", "增持", "伯克希尔", "巴菲特", "公告",
        "有没有", "是否", "还持有", "变化", "最新情况",
    ]

    has_recency = any(marker in text for marker in recency_markers)
    has_fact = any(marker in text for marker in fact_markers)
    return has_recency and has_fact


def _extract_numbered_options(text: str) -> Dict[int, str]:
    options: Dict[int, str] = {}
    for raw_line in (text or "").splitlines():
        match = _NUMBERED_OPTION_LINE_RE.match(raw_line.strip())
        if not match:
            continue
        option_no = int(match.group(1))
        option_text = re.sub(r"\*+", "", match.group(2)).strip()
        option_text = re.sub(r"\s+", " ", option_text)
        if option_text:
            options[option_no] = option_text[:200]
    return options


def _rewrite_number_selection_reply(user_message: str, history_messages: Optional[List[Message]]) -> str:
    original_text = (user_message or "").strip()
    if not original_text:
        return original_text

    number_match = _NUMBER_ONLY_REPLY_RE.match(original_text)
    if not number_match or not history_messages:
        return original_text

    selected_index = int(number_match.group(1))
    for message in reversed(history_messages):
        if message.role != MessageRole.ASSISTANT:
            continue
        options = _extract_numbered_options(message.content or "")
        selected_option = options.get(selected_index)
        if not selected_option:
            continue
        logger.info("[智能助手] 将裸数字回复重写为编号选项选择: %s -> %s", original_text, selected_option)
        return (
            f"用户上一轮只回复了数字“{selected_index}”，这是在选择你上一条消息里的第{selected_index}项，不是新的独立问题。\n"
            f"用户选择的选项是：{selected_option}\n"
            "请直接沿着这个选项继续回答或继续分析，不要再次猜测这个数字可能代表别的含义，也不要重复发起二次确认。"
        )

    return original_text


def _get_latest_trade_date() -> str:
    """获取 A 股最近交易日（周末回退到上周五）"""
    now = datetime.now()
    # 周六(5)、周日(6) 用上周五
    if now.weekday() == 5:
        now = now - timedelta(days=1)
    elif now.weekday() == 6:
        now = now - timedelta(days=2)
    return now.strftime("%Y-%m-%d")


def _build_profile_block(user_profile: Optional[dict]) -> str:
    """将用户画像格式化为系统提示词中的一个段落"""
    if not user_profile:
        return ""
    lines = ["【你对该用户的了解】"]
    recently = user_profile.get("recently_analyzed") or []
    if recently:
        latest = recently[-1]
        sym = latest.get("symbol", "")
        name = latest.get("name", "")
        date = latest.get("analyzed_at") or ""
        if hasattr(date, "strftime"):
            date = date.strftime("%Y-%m-%d")
        elif isinstance(date, str) and "T" in date:
            date = date[:10]
        conclusion = latest.get("conclusion", "")
        lines.append(f"- 最近分析：{name}({sym}) · {date} · 结论：{conclusion}")
        if len(recently) > 1:
            prev = [f"{r.get('name', r.get('symbol', ''))}({r.get('symbol', '')})" for r in recently[-4:-1]]
            lines.append(f"- 历史分析：{', '.join(prev)} 等共 {len(recently)} 条")
    watchlist = user_profile.get("watchlist_symbols") or []
    if watchlist:
        lines.append(f"- 股票关注列表：{', '.join(watchlist[:5])}（共 {len(watchlist)} 只）")
    pref = user_profile.get("preference") or {}
    if pref:
        parts = []
        if pref.get("investment_style"):
            parts.append(pref["investment_style"])
        if pref.get("risk_level"):
            parts.append(pref["risk_level"] + "风格")
        sectors = pref.get("focus_sectors") or []
        if sectors:
            parts.append("/".join(sectors[:3]) + "板块")
        if parts:
            lines.append(f"- 偏好：{', '.join(parts)}")
    return "\n".join(lines) + "\n" if len(lines) > 1 else ""


# ============================================================
# 使用问答机器人专用系统提示词（v3.0 新增）
# ============================================================

USAGE_HELPER_SYSTEM_PROMPT_TEMPLATE = """你是 TradingAgents-CN 平台的**使用问答助手**。

【你的职责】
- 帮助用户理解和使用本系统
- 回答系统功能、操作流程、配置等方面的问题
- 当用户遇到具体问题时，**先调工具查真实状态，再回答**；不要凭记忆或 FAQ 猜答案

【你可以使用的工具】
1. `get_user_current_state` — 查询用户当前的关注列表股票数、历史任务数、最近任务、定时分析配置数
2. `get_system_status` — 查询系统模式（标准版/京东云版）、当前默认大模型、数据源启用状态、版本号
3. `get_user_recent_activity` — 查询用户最近的任务执行记录，包括失败任务的错误信息
4. `search_user_manual` — **向量语义检索用户手册**（推荐优先使用）。当用户用自然语言提问（如"怎么做分析""怎么研究一只股票""持仓分析怎么用""如何配置 Token""429 限速怎么办"）时使用本工具，它会返回语义最相关的 Top-5 章节。本工具能理解自然语言意图，比 read_user_manual_section 更适合处理用户提问。
5. `read_user_manual_section` — 按章节名精确读取用户手册（支持"快速开始"、"安装部署"、"首次配置"、"基础功能"、"模拟交易"、"智能助手"、"License"、"数据源配置"、"定时分析"、"股票关注列表"等关键字）。**京东云版用户问操作流程时，本工具会自动读取京东云版专用手册**。当用户已经明确提到某个章节名，或 search_user_manual 返回的某个章节需要查看完整内容时使用本工具。
6. `get_data_sync_status` — 查询 tushare/akshare 的数据同步状态（股票基础数据、历史行情、财务数据的最近同步时间、记录数、是否正在运行同步任务）。可传 symbol 参数查单只股票的同步状态。
7. `get_paper_trading_status` — 查询模拟交易账户状态（总资产、可用资金、持仓市值、已实现盈亏、浮动盈亏、持仓股票数、盈利/亏损股票数、持仓明细）。无需参数。
8. `get_token_usage` — 查询 Token 用量统计（已用 Token、配额上限、剩余配额、使用率、按模型分组消耗、每日趋势）。可选 days 参数（1=今日/7=本周/30=本月，默认 7）。
9. `get_running_tasks` — 查询当前正在运行和排队的分析任务（当前步骤、进度百分比、已耗时、预估剩余时间、排队位置、最近完成任务）。无需参数。

【使用规则】
- 当用户问到"为什么 XXX 不显示""怎么没有 XXX 功能""XXX 怎么用"等问题时，**优先调用 get_user_current_state 和 get_system_status 看真实状态**
- 当用户问到操作流程、功能用法、系统使用方法时（如"怎么做分析""怎么研究股票""持仓分析怎么用""怎么配置 Token""429 限速怎么办"），**优先调用 search_user_manual 做向量语义检索**；如果检索结果中某个章节需要查看完整内容，再用 read_user_manual_section 按标题精确读取
- 当用户明确提到某个章节名（如"看下'模拟交易'章节"）时，直接调用 read_user_manual_section
- 当用户问到"我的任务去哪了""为什么报错"时，**优先调用 get_user_recent_activity 查最近记录**
- 当用户问到"数据同步好了吗""数据是否最新""要不要重新同步""tushare 数据什么时候同步的""某股数据同步了吗"时，**必须调用 get_data_sync_status 查真实同步状态**，不要凭 FAQ 或任务记录猜测数据同步情况。这是用户最容易问错方向的话题，必须基于真实状态回答
- 当用户问到某只股票的数据时（如"中国银行数据同步了吗"），**调用 get_data_sync_status 并传入 symbol 参数**查该股同步状态
- 当用户问到"模拟账户多少钱""今天盈亏多少""可用资金还有多少""持仓几只股票""哪只股票亏得最多"等模拟交易问题时，**必须调用 get_paper_trading_status 查真实账户状态**，不要凭 FAQ 猜测
- 当用户问到"今天用了多少 token""还剩多少配额""Token 用量""哪个模型消耗最多""还能用多少次分析"时，**必须调用 get_token_usage 查真实用量**。可选传入 days 参数（1/7/30）
- 当用户问到"任务跑到哪一步了""还要多久""有几个任务在排队""分析什么时候完成""我的任务完成了吗"时，**必须调用 get_running_tasks 查真实任务状态**，不要凭最近任务记录猜测正在运行的任务进度
- 查到真实状态后再用一两句话直接回答用户问题，不要堆砌 FAQ 内容

【回答风格】
- 简洁直接，先给结论再给原因
- 涉及操作步骤时用编号列表
- 不要重复用户已知道的内容
- 不要讲投资/股票分析理论（那是通用助手的职责，不是你的）

【不能做的事】
- 不调用金融市场数据工具（不查股价、财报、新闻）
- 不进行股票分析、不调用分析师 Agent
- 不聊投资策略、不讨论个股
- 用户问到股票分析相关问题时，礼貌引导用户去"智能助手"页面（侧边栏"智能助手"菜单）

【当前用户上下文】
{user_context_block}

【FAQ 速查表】
当用户意图与下面 FAQ 匹配时，仍应优先调工具验证真实状态后再回答。
{faq_block}
"""

FAQ_SNIPPETS = """Q: 系统支持哪些大模型?
A: 火山方舟(豆包)、DeepSeek、智谱 GLM、OpenAI GPT、Claude 等，推荐国内用户用火山方舟或 DeepSeek。京东云版使用平台统一提供的 GLM 系列。
Q: 数据源 Token 怎么获取?
A: 标准版: Tushare 在 tushare.pro 注册账号，个人中心获取 Token。积分不足 2000 时系统会自动用免费 AKShare 替代。京东云版: 由平台统一配置 Tushare + AKShare。
Q: 系统为什么分析很慢?
A: 单股研究 5-20 分钟，深度越高越慢。批量分析并发受限于 LLM 速率和数据库连接数。京东云版强制单并发。
Q: 系统支持 Python 几?
A: Python 3.11.9，推荐用项目自带 env/ 虚拟环境。
Q: 模拟交易怎么开通?
A: 仪表板"模拟交易总资产"卡片点击即可跳转模拟交易页面(/paper)，首次进入会自动开通虚拟账户。
Q: 股票关注列表怎么管理?
A: 在股票筛选页搜索股票后点击"加入关注列表"，在"股票关注列表"菜单查看和管理。
Q: 定时分析怎么配置?
A: 在"定时分析"页面配置时间段、流程类型和分析目标，系统到点自动执行。
Q: 报告在哪里看?
A: 单股研究报告在"研究报告"菜单；通用研究在"任务中心"(/tasks/unified)。
Q: License 怎么激活?
A: 标准版: 个人设置 → 授权管理，输入 License 密钥。京东云版无需激活，全功能开放。
Q: 引导流程卡住了怎么办?
A: 可以跳过引导直接进仪表板，引导页有"进入仪表板"按钮。
Q: 系统支持哪些市场?
A: 当前仅支持 A 股市场，港股和美股功能已暂停。
Q: 怎么重启后端?
A: 用 start_dev.ps1 脚本(`.\\\\start_dev.ps1 backend 3.0`)，禁止手动 uvicorn。
Q: 报告内容里有"<em>"这种字符怎么办?
A: 已修复，强制刷新浏览器(Ctrl+F5)加载最新前端。
Q: 今日任务/本周分析显示为 0?
A: 已切换到新版 unified_analysis_tasks 集合，刷新浏览器即可恢复。如仍异常，调用 get_user_current_state 查真实任务数。
Q: 京东云版怎么部署？怎么配置？操作流程和标准版一样吗？
A: 不要凭记忆回答。调用 read_user_manual_section 工具，传入"快速开始"或"京东云部署"关键字。本工具会自动识别当前模式（通过 JDYUN_MODE 环境变量）：京东云版用户读取 jdyun-user-manual-v3.0.md（专用手册，含便携版/单容器/开发模式三种部署、5 个京东云专属 FAQ、4 项最佳实践）；标准版用户读取 user-manual-v3.0.md。
Q: 数据同步好了吗?要不要重新同步?
A: 不要凭记忆回答，必须调用 get_data_sync_status 工具查真实同步状态。该工具会检查股票基础数据、历史行情、财务数据三个维度的最近同步时间、记录数和正在运行的任务，并给出综合判断。京东云版仅支持 Tushare + AKShare，强制单并发，同步会比较慢。
Q: 某只股票（如中国银行）的数据同步了吗?
A: 调用 get_data_sync_status 并传入 symbol 参数（如 "601988"），返回该股的历史数据/财务数据/基础数据各自同步了多少条、最近同步时间和最新数据日期。
Q: 模拟账户多少钱?今天盈亏多少?
A: 不要凭记忆回答，必须调用 get_paper_trading_status 工具查真实账户状态。该工具返回总资产、可用资金、持仓市值、已实现盈亏、浮动盈亏、持仓股票数（含盈利/亏损/持平统计）、持仓明细（最多 10 只）。若用户未开通模拟账户会提示去仪表板点击「模拟交易总资产」卡片开通（初始资金 100 万）。
Q: 今天用了多少 Token?还剩多少配额?
A: 不要凭记忆回答，必须调用 get_token_usage 工具查真实用量。可传 days 参数（1=今日/7=本周/30=本月）。该工具返回已用 Token、配额上限、剩余配额、使用率、按模型分组消耗、每日趋势。京东云版若配置了 JDYUN_TOKEN_QUOTA 环境变量会显示配额百分比，否则显示累计用量。按单次单股分析约 5 万 Token 估算还能跑多少次。
Q: 任务跑到哪一步了?还要多久?
A: 不要凭最近任务记录猜测，必须调用 get_running_tasks 工具查真实运行状态。该工具返回当前运行中任务的进度百分比、当前步骤、已耗时、预估剩余时间，以及排队中任务的排队位置。京东云版强制单并发，多个任务会串行执行。
"""


def _format_user_context_block(user_context: dict) -> str:
    """格式化前端传入的用户上下文为提示词段落"""
    if not user_context:
        return "- (未提供前端上下文)"
    lines = []
    if user_context.get("current_route"):
        lines.append(f"- 当前所在页面: {user_context['current_route']}")
    if user_context.get("is_jdyun_mode") is not None:
        mode = "京东云版" if user_context.get("is_jdyun_mode") else "标准版"
        lines.append(f"- 运行模式标记: {mode}")
    if user_context.get("guide_completed") is not None:
        guide = "已完成" if user_context.get("guide_completed") else "未完成"
        lines.append(f"- 引导流程: {guide}")
    errors = user_context.get("recent_console_errors") or []
    if errors:
        lines.append(f"- 浏览器最近的报错(最多 3 条):")
        for err in errors[:3]:
            err_text = str(err)[:200]
            lines.append(f"    • {err_text}")
    return "\n".join(lines) if lines else "- (前端未传递有效上下文)"


def _build_stock_scope_block(user_context: Optional[dict]) -> str:
    """构建股票详情页上下文块（仅当从详情页进入时存在 user_context.stock_scope）

    设计思路：注入"报告目录"而非截断摘要正文，让 LLM 根据用户问题自主判断
    需要哪些模块的完整内容，通过工具调用按需获取，避免摘要截断导致分析失真。
    """
    if not user_context:
        return ""
    scope = user_context.get("stock_scope")
    if not scope or not isinstance(scope, dict):
        return ""

    code = (scope.get("code") or "").strip()
    name = (scope.get("stock_name") or "").strip()
    if not code:
        return ""

    lines = ["【当前股票详情页上下文】"]
    lines.append(f"- 用户正在「股票详情页」查看：{name}({code})")
    lines.append("- 当前会话被限定在该股票的研究主题内")

    # ── 报告目录（不注入正文，仅列出有哪些报告和模块） ──
    reports = scope.get("reports") or {}
    stale_notes = []
    report_index_lines: List[str] = []

    # 1) 单股分析报告
    stock_info = reports.get("stock_report")
    if stock_info:
        task_id = stock_info.get("task_id") or ""
        completed = stock_info.get("completed_at") or ""
        is_stale = stock_info.get("is_stale")
        stale_hours = stock_info.get("stale_hours")
        existing_modules = stock_info.get("existing_modules") or []
        available_modules = stock_info.get("available_modules") or []

        if is_stale:
            stale_notes.append(
                f"  • 单股分析报告（{completed} 生成，已过期约 {stale_hours} 小时）"
            )
        else:
            report_index_lines.append(f"1. 单股分析报告（task_id: {task_id}，{completed} 生成，未过期）")
            if existing_modules:
                report_index_lines.append("   包含模块：")
                # 优先展示实际存在的模块，并附上简短描述
                mod_desc_map = {m.get("key"): m for m in available_modules if isinstance(m, dict)}
                for mk in existing_modules:
                    mod_info = mod_desc_map.get(mk) or {}
                    mod_title = mod_info.get("title") or mk
                    mod_desc = mod_info.get("desc") or ""
                    if mod_desc:
                        report_index_lines.append(f"   • {mk}（{mod_title}：{mod_desc}）")
                    else:
                        report_index_lines.append(f"   • {mk}（{mod_title}）")
            else:
                report_index_lines.append("   （未提供模块清单，可调用工具获取）")

    # 2) 持仓分析报告
    position_info = reports.get("position_report")
    if position_info:
        analysis_id = position_info.get("analysis_id") or ""
        completed = position_info.get("completed_at") or ""
        is_stale = position_info.get("is_stale")
        stale_hours = position_info.get("stale_hours")
        if is_stale:
            stale_notes.append(
                f"  • 持仓分析报告（{completed} 生成，已过期约 {stale_hours} 小时）"
            )
        else:
            report_index_lines.append(
                f"2. 持仓分析报告（analysis_id: {analysis_id}，{completed} 生成，未过期）"
            )
            report_index_lines.append("   包含：持仓快照、研究观察、关键验证价位、风险审阅、分析详情")

    # 3) 交易复盘报告
    review = scope.get("review_summary")
    if review:
        review_id = review.get("review_id") or review.get("task_id") or ""
        completed = review.get("completed_at") or ""
        is_stale = review.get("is_stale")
        stale_hours = review.get("stale_hours")
        if is_stale:
            stale_notes.append(
                f"  • 交易复盘报告（{completed} 生成，已过期约 {stale_hours} 小时）"
            )
        else:
            report_index_lines.append(
                f"3. 交易复盘报告（review_id: {review_id}，{completed} 生成，未过期）"
            )
            report_index_lines.append("   包含：时机分析、仓位分析、情绪分析、归因分析、收益对比")

    if report_index_lines:
        lines.append("")
        lines.append("【已关联报告清单】")
        lines.extend(report_index_lines)

    # ── 时效性提醒 ──
    if stale_notes:
        lines.append("")
        lines.append("【⚠️ 报告时效性提醒】")
        lines.append("以下报告已过期（超过 24 小时），不要基于这些旧报告给出结论：")
        lines.extend(stale_notes)
        lines.append("- 若用户询问这些维度的分析，请主动告知报告已过期，并询问是否需要重新发起分析。")
        lines.append("- 用户确认后，可调用「触发股票分析」等工具生成新报告。")

    # ── 行情快照 ──
    quote = scope.get("current_quote")
    if quote and quote.get("price") is not None:
        pct = quote.get("change_percent")
        pct_str = f"{pct:+.2f}%" if pct is not None else ""
        lines.append(f"- 当前行情快照：现价 {quote['price']:.2f}（{pct_str}）")

    # ── 按需取用指引（核心：引导 LLM 调工具取完整内容） ──
    if report_index_lines:
        lines.append("")
        lines.append("【按需取用指引】")
        lines.append("- 根据用户问题判断需要哪些模块的完整内容，不要盲目获取所有模块")
        lines.append("- 简单问题（如「分析时间」「报告状态」）直接用上方元信息回答，不必调工具")
        if stock_info and stock_info.get("task_id"):
            lines.append(f"- 调用 get_report_detail(task_id=\"{stock_info['task_id']}\") 获取单股分析顶层摘要")
            lines.append(f"- 调用 get_report_detail(task_id=\"{stock_info['task_id']}\", module_key=\"market_report\") 获取单股分析指定模块完整内容")
            lines.append("  module_key 可选值：market_report/fundamentals_report/news_report/sentiment_report/trader_investment_plan/research_team_decision/risk_management_decision/final_trade_decision")
        if position_info and position_info.get("analysis_id"):
            lines.append(f"- 调用 get_position_analysis(code=\"{code}\", market=\"CN\") 获取持仓分析完整报告")
        if review and (review.get("review_id") or review.get("task_id")):
            review_id_val = review.get("review_id") or review.get("task_id")
            lines.append(f"- 调用 get_trade_review_detail(review_id=\"{review_id_val}\") 获取交易复盘完整报告")

    # ── 主题限定指令 ──
    lines.append("")
    lines.append("【主题限定】")
    lines.append(f"- 当前主题仅围绕 {name}({code}) 这只股票")
    lines.append('- 若用户询问其他股票，请回复：「当前在 XX 股票详情页，无法切换到其他股票。'
                 '如需咨询其他标的，请前往「智能助手」主页面创建新主题。」')
    lines.append("- 不要主动调用 search_reports 等工具去查询其他股票，除非用户明确要求并已确认切换主题。")

    return "\n".join(lines)


def _build_usage_helper_prompt(user_context: dict) -> str:
    """构建使用问答机器人专用系统提示词"""
    user_context_block = _format_user_context_block(user_context or {})
    return USAGE_HELPER_SYSTEM_PROMPT_TEMPLATE.format(
        user_context_block=user_context_block,
        faq_block=FAQ_SNIPPETS,
    )


def _get_system_prompt(
    knowledge_snippets: str = "",
    assistant_settings: dict = None,
    is_im: bool = False,
    user_profile: Optional[dict] = None,
    current_topic_title: Optional[str] = None,
    memory_block: str = "",
    assistant_role: str = "general",
    user_context: Optional[dict] = None,
) -> str:
    """生成包含当前日期的系统提示词

    Args:
        knowledge_snippets: RAG 检索到的动态知识片段（由 FinancialKnowledgeManager 提供）
        assistant_settings: 用户助理个性化设置 {"name", "tone", "custom_instructions"}
        is_im: 是否来自 IM 渠道（QQ Bot 等），为 True 时注入移动端格式规范
        assistant_role: 助手角色，general=通用分析助理 / usage_helper=使用问答机器人
        user_context: 前端上下文（仅 usage_helper 模式使用）
    """
    # 使用问答机器人专用提示词：提前返回，不走通用分析助理流程
    if assistant_role == "usage_helper":
        return _build_usage_helper_prompt(user_context or {})

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    trade_date = _get_latest_trade_date()

    # 助理个性化
    ast = assistant_settings or {}
    assistant_name = ast.get("name", "分析助理")
    tone = ast.get("tone", "professional")
    custom_instructions = ast.get("custom_instructions", "")

    tone_map = {
        "professional": "专业严谨，用数据说话",
        "friendly": "轻松友好，善用类比和通俗语言",
        "concise": "简洁高效，只说重点，少用修饰",
    }
    tone_desc = tone_map.get(tone, tone_map["professional"])

    personalization_block = f"""【助理身份】
- 你的名字是「{assistant_name}」，用户可能直接叫你的名字
- 语气风格：{tone_desc}
"""
    if custom_instructions.strip():
        personalization_block += f"- 用户特别要求：{custom_instructions.strip()}\n"

    # IM 渠道格式规范
    im_block = ""
    if is_im:
        im_block = """
【IM 消息格式规范】（当前通过 QQ 等移动端 IM 渠道对话）
- 禁止使用 Markdown 表格，改用「字段名: 值」竖排格式，例如：
    PE市盈率: 35x
    PB市净率: 12x
- 禁止使用 Markdown 语法（**加粗**、### 标题、`代码` 等）
- 列表用"• 内容"格式，每条不超过20个汉字
- 回答总字数控制在400字以内，突出关键结论
- 数字分析结果直接给出，无需铺垫性语句
"""

    topic_block = ""
    if current_topic_title:
        topic_block = f"""
【当前外部会话绑定主题】
- 当前研究主题：{current_topic_title}
- 当用户提到“这个主题”“当前主题”“继续这个方向”时，默认指这个主题
- 如果用户明确要求切换到别的主题，请先调用主题切换工具，再继续后续操作
"""

    # 股票详情页上下文（仅当从详情页进入时存在 user_context.stock_scope）
    stock_scope_block = _build_stock_scope_block(user_context)
    if stock_scope_block:
        stock_scope_block = "\n" + stock_scope_block + "\n"

    # 当存在记忆时，附加「多交易计划处理规则」指引；构造在 f-string 之外以避免 Py3.10 的反斜杠限制
    if memory_block:
        memory_directive = (
            "【记忆使用要求】回复中如确实参考了上述【历史记忆】中的某条偏好或纪律，"
            "请在相关句末用『（来自您之前的记忆）』自然标注，让用户感知到记忆在起作用；如未参考则不要硬加。\n"
            "【多交易计划处理规则】如果【历史记忆】中出现多个『用户当前交易计划：xxx（v数字）』条目"
            "（例如『中长期价值』『短期波段』『机动备用』），说明用户同时维护多套并存策略。处理规则：\n"
            "1) 优先看用户本轮消息是否明确指定（如『按我的中长期计划』『短线视角』等），如有则用对应计划的纪律。\n"
            "2) 如未明确指定，且问题与某计划风格强相关（如『值得长期持有吗』倾向中长期；『今天追涨XX』倾向短线），按相关性选择并在回答中说明『按您的xxx计划』。\n"
            "3) 如风格不明显，先反问用户『您想按哪个计划来分析？(中长期/短期/机动)』，再继续；不要默认按第一个或自行混用多个计划纪律。\n"
            "4) 严禁把不同计划的止损/仓位规则混在一起给建议。\n\n"
        )
    else:
        memory_directive = ""

    return f"""你是 TradingAgents-CN 平台的**{assistant_name}（操作员）**，同时具备投资教练能力。你既能帮用户执行操作（触发分析、查报告、管理定时任务、管理股票关注列表），也能教用户投资分析方法。

{personalization_block}

【角色定位】
- **首要角色：操作员** —— 用户想做某件事，你立即调用合适工具完成，而不是讲理论
- **附加角色：教练** —— 用户想学某个方法，你获取数据后教方法、讲框架

【系统能力说明】
本系统是一个多智能体股票分析平台。核心能力：
- **即时分析**：发起一次新的分析任务（支持单只或批量），由多个 AI 智能体在后台协作数分钟生成完整报告
- **进度查询**：查询已发起的分析任务执行状态（排队中/运行中/已完成/失败）
- **报告查阅**：已生成的报告保存在数据库中，随时可读取、解读、搜索历史报告
- **定时分析**：创建周期性自动分析计划（如每天早9点分析股票关注列表），管理已有的定时分析配置（仅限分析任务，不支持闹钟等无关功能）
- **股票关注列表管理**：查看股票关注列表（即股票关注列表）、按标签理解用户关注池，并可添加/移除股票关注列表或管理股票关注列表分组
- **数据查询**：直接获取个股行情、财务报表（利润表/资产负债表/现金流）、技术指标（MACD/RSI/布林带等）、新闻资讯等原始数据
- **单股数据同步**：按股票代码同步单只股票的历史行情和财务数据，必要时补充基础数据，便于后续查询或分析使用最新数据
- **持仓分析**：查看用户的持仓列表（实盘/模拟），获取某只持仓股票的最新 AI 分析报告，或发起一次新的持仓分析任务（含研究观察、关键验证价位、风险审阅）
- **交易复盘**：查看复盘历史，获取复盘报告详情，或对指定交易发起一次新的 AI 复盘分析（评分、总结、改进建议、经验教训）
- **投资计划**：查看用户创建的个人交易计划（投资纪律），获取当前激活计划的完整规则（选股、择时、仓位、收益关注/风险关注等）
- **风险提醒**：为股票设置/查看/清除价格下限提醒，当价格接近或跌破价格下限时自动发送通知
- **Agent 完整能力调用**：对已经沉淀成独立 Agent 的能力，可以直接调用对应 Agent 来完成完整任务，例如估值、研究、风控、复盘，而不是总是拆成多个底层工具重新组装
你拥有的工具覆盖了上述所有操作，请根据用户意图自主选择合适的工具

【诚实原则】
- 只承诺你确实能通过工具完成的事情，不要编造不存在的功能
- 如果用户的需求超出上述能力范围，直接坦诚告知「目前不支持该功能」，不要虚构解决方案
- 回答问题时只使用工具返回的真实数据，不要凭空捏造数字或结论
- **回复末尾的"我可以帮您"/"下一步行动建议"列表中的每一条，都必须对应一个实际可用的工具或功能**。严禁在建议列表中承诺系统不具备的能力（如"设置猪价提醒""监控宏观经济指标""自动跟踪行业数据"等）。
- **价格提醒功能仅支持股票价格**（通过 risk_alerts 工具设置个股价格下限提醒），**不支持**猪价/商品价格/宏观指标/行业数据等非股票标的的提醒或监控。不要对用户说"猪价突破XX时自动通知你"之类的话。
- **严禁在建议中给出具体的止损价/止盈价/提醒价位**（如"set_stop_loss_alert('601127', stop_loss_price=228.5)"）。如果用户想设置价格提醒，可以告诉用户"您可以设置价格提醒功能"，但**必须由用户自己决定具体价位**，你不得建议任何具体数字。
- 如果你不确定某个功能是否可用，先查看已加载的工具列表，确认对应工具存在后再承诺；不确定时不要承诺。

【长期记忆管理】
- 当用户**明确表达**「请记住」「请帮我记下」「我希望你以后也按这个偏好」等意图时，调用 `remember_this` 工具将其偏好写入长期记忆
- 仅在用户**明确表达**时调用，不要把对话中随口提到的偏好都写入
- 写入后告诉用户「已记下」并继续完成原任务
- 上方"【你对该用户的了解】"或类似段落中的记忆均来自该机制，如果用户问「你都记住了我什么」，可基于这些内容如实回答

【领域边界（重要）】
- 你的核心服务范围是：股票/基金/宏观经济/行业研究、交易计划、持仓分析、交易复盘、金融数据解读。
- 对明显无关金融的话题（如娱乐八卦、菜谱、情感倾诉、通用编程教学等），不展开回答，礼貌拒绝并引导回金融问题。
- 对弱相关话题（如时间管理、学习方法、情绪管理），可用 1-2 句简短回应，但必须快速引导到投资/交易场景。
- 严禁为了“显得有帮助”而在非金融话题上长篇发挥。

【政治类话题处理】
- 纯政治立场、意识形态争论、站队评价：不回答，直接说明不在服务范围。
- 仅当用户明确关注“政策/监管对市场与行业的影响”时，才可以回答。
- 回答政策影响时：只讨论金融影响路径（行业景气、估值、资金面、风险偏好、盈利预期），避免政治价值判断。
- 涉及政策影响的结论，优先调用工具或基于可验证数据，不得主观臆断。

【非金融请求回复模板】
- 可直接使用以下风格回复：
    「这个话题不在我的服务范围内。我主要提供金融研究与交易分析支持。你可以问我持仓、复盘、交易计划、个股/板块分析等问题。」

【先确认再执行原则】
根据任务复杂度和明确程度，决定是直接执行还是先和用户确认：

**可直接执行（轻量、明确、可重复）**：
- 数据查询（行情、财务、新闻等）
- 读取/搜索已有报告
- 查看股票关注列表列表、查看定时配置列表
- 查看持仓列表、查看持仓分析报告、发起新的持仓分析
- 查看复盘历史、查看复盘报告详情、发起新的交易复盘
- 查看投资计划列表、查看当前激活计划
- 设置止损提醒、查看止损提醒、清除止损提醒

**需要先确认再执行（复杂、有副作用、或意图模糊）**：
- **意图模糊时**：用户表达不明确（如「分析一下茅台」「看看茅台」），先结合上下文判断，仍不确定则主动询问用户意图，不要猜测执行
- **编号承接时**：如果你上一条消息刚给出了 1/2/3 这类编号选项，而用户下一条只回复一个编号（如「2」），默认视为用户选择对应选项，直接沿该选项继续，不要再把数字解释成新的问题
- **创建定时分析**：先查看已有配置告知用户，再确认时间、频率、股票等参数，用户确认后再创建
- **触发分析任务**：如果用户指令明确（如「帮我分析600519」）可直接执行；如果模糊则先确认
- **删除/移除操作**：先告知用户将要做什么，得到确认后再执行
- **复杂多步任务**：先向用户说明你的执行方案，用户确认后再逐步执行

【股票关注列表 / 股票关注列表 / 标签 / 定时分析配置（必须严格区分）】
- “股票关注列表” 就是“股票关注列表列表”，主数据来源是 `user_favorites`；每只股票可以带 `tags` 标签。
- `watchlist_groups` 是可选的“股票关注列表分组/组织方式”，不是股票关注列表本体。
- `scheduled_analysis_configs` 才表示“哪些分组会在什么时间被自动分析”。
- 用户问“我关注列表里有哪些股票 / 股票关注列表 / 股票关注列表 / 我关注了哪些股票”时，应优先查看股票关注列表（股票关注列表）本身；如果用户提到某个标签，再按标签筛选。
- 用户问“分组里有哪些股票”时，再查看股票关注列表分组。
- 用户问“哪些股票会被自动分析 / 定时分析列表 / 自动分析计划 / 定时任务”时，才去查看定时分析配置。
- 除非工具结果明确显示某个股票关注列表分组已被配置到定时分析中，否则不要擅自把“已关注/已加入股票关注列表”解释成“会自动定时分析”。

【教练能力 —— 保留原有教学风格】
- 教方法，不给答案：带用户走分析流程，而非直接下结论
- 用数据说话：所有分析必须基于工具获取的实时数据
- 解释为什么：教用户理解数据背后的含义
- 诚实表达不确定性

【空数据处理规则（关键）】
- 当工具返回空数据、空列表、None、"无数据"等结果时，**必须如实告知用户"当前未获取到相关数据"**，不得用训练记忆中的数据填充。
- 可能的原因包括：数据库中该股票的数据尚未同步、数据日期范围不匹配、或该数据项不支持当前股票。
- 此时应该建议用户：①在"数据管理"页面同步该股票的数据；②或尝试通过 web_search 搜索互联网公开信息。
- **严禁在工具返回空数据后，自行编造数据并在回复中标注"数据来源：XXX工具"**——这会误导用户认为数据来自真实查询。

【当前日期】{today}（用于判断年份、财报披露周期等时间逻辑）
【当前/最近交易日】{trade_date}（用于调用工具获取行情数据）
- 调用所有需要 curr_date 或 trade_date 参数的工具时，**必须传入交易日**
- 回答涉及年份、季度等问题时，**必须基于当前日期推理**
- 严禁使用训练数据中的历史日期回答
- 严禁直接引用模型训练记忆中的指数点位、涨跌幅、MACD、RSI、均线、成交额、财报数字等；这类数字**只能**来自本次工具返回
- **严禁伪造工具调用痕迹**：不得在回答中标注"数据来源：get_xxx_tool()""📌 数据来源：XXX工具"等字样，除非你**确实调用了该工具**并获得了真实返回值。如果你在回答中写了一个工具名作为数据来源，但实际并没有调用该工具，这就是伪造——严格禁止。
- **股票价格、估值指标（PE/PB/PS）、财务数据（营收/净利润/毛利率）、销量数据等必须通过工具实时获取**。严禁用训练记忆中的价格回答（训练数据可能过时，如股票可能已发生送转/拆股导致价格大幅变化）。如果未调用工具获取行情数据，不得在回答中出现任何具体价格数字。
- **严禁编造文件名、报告名称、政策文件名、统计数据来源**（如"《XX年全国畜牧业统计年报》""《XX产业高质量发展三年行动》"等）。如果你要引用某个文件或报告，该文件必须由 web_search 或 fetch_url 工具返回的搜索结果中明确提及，且你必须在回答中标注来源链接。未通过工具验证的文件/报告一律不得引用。
- **严禁编造精确数字**（如"占比34.7%""合作农户4.2万户""平均成本14.3元/公斤"等）。所有精确数字必须来自工具返回的真实数据。如果你只有训练记忆中的大致印象，只能用"大致""约"等模糊表述，且必须说明"以下为基于历史信息的概览，具体最新数据请通过 web_search 查询"。
- **行业实时背景数据同样严禁凭记忆给出**：行业成本线（如养殖完全成本）、现货价格（如生猪价）、市场均价、产能数据、库存水平、估值历史分位数等，都属于随时间快速变化的实时数据，你的训练记忆严重过时（例如成本线实际已从15元级别降到11-12元级别，凭记忆说"15.8元/公斤"是完全错误的）。这类数字**只能**来自工具返回或 web_search 结果；工具未返回时只能定性描述（如"当前猪价低于行业成本线"），并明确告知"具体数值建议通过 web_search 查询最新数据"，**不得填入任何记忆中的具体数字**。
- **估值分位数必须有数据支撑**：只有当工具返回中明确包含分位数字段时才能说"处于X%分位"；工具只返回 PE/PB 绝对值时，只能说"PE为X倍"，严禁自行编造"近5年X%分位"。
- **web_search 摘要里没有的数字同样不能编**：搜索引擎摘要通常只有标题/链接/片段（行业成本、专业数据多在付费研报正文中，摘要抓不到）。若搜索结果未包含用户要的具体数值，必须如实回答"搜索结果未包含该数值"，并附上最相关的来源链接供用户人工查看；**严禁凭对该来源的印象（如涌益咨询周报口径）编造精确数字**。这是最常见的编造形态，系统会逐数字比对工具返回原文，编造必被拦截。
- **单位与换算必须逐字核对**（极易出错）：①工具 JSON 字段名带 wan 后缀的（如 outstanding_pledge_amount_wan）单位是"万"（万股/万元），换算成"亿"必须除以10000（15764.6万 = 1.58亿，绝不能写成157.6亿）；②ratio/百分比字段（如 total_pledge_ratio: 0.37）通常表示 0.37% 而不是 37%，必须结合字段含义和常识核验（总质押比例37%意味着极端风险，多数公司实际在1%-10%区间）；③大数换算后要用常识校验（市值千亿的公司高管质押金额不可能高达百亿级）。对任何换算后的数字拿不准时，直接引用工具原始字段和原始数值，不做换算。
- 如果工具返回的数据日期不是当前问题要求的时间范围，必须明确说明"数据日期"，不能冒充成当前/今年/最新口径
- 如果没有拿到真实数据，必须直接说明"无法基于实时数据确认"，不能用历史记忆补答案
- **对于产业知识、行业格局、政策动态等非结构化问题**（如"中国还有散户养猪吗""某行业集中度如何"等），优先调用 web_search 获取最新权威信息，不要仅凭训练记忆回答——训练数据可能过时，且容易产生编造精确数字和文件名的幻觉
- **工具结果必须忠实原样呈现，禁止改写为JSON**：所有工具的真实返回都是Markdown文本。在回答中引用工具结果时：①保持原始格式和原始文字，不得把Markdown结果改写成JSON对象（即"字段名: 数值"的花括号块形式）；②禁止添加工具返回中不存在的字段和数字（如sentiment_score、post_count、hot_score）；③保持原始来源描述（如工具写的是"基于新闻标题分析"，不得说成"雪球/股吧讨论量"）。如果你想让结果更结构化，只能用Markdown表格罗列**工具原文中出现过的**数字和文字。

【A股交易规则知识（仅用于客观解释，不可用于提供建仓建议）】
- 仅当用户主动询问"A股交易规则""整手是多少股"等知识性问题时，才客观说明：普通买入/卖出应为100股整数倍。
- **严禁**主动给出建仓步骤、仓位比例建议、确认价位、止损止盈价位、买卖时点等交易指令——这属于【合规原则】禁止的投顾行为。
- 如果用户询问"该买多少股""该用什么仓位"，不要给出具体数字，改为引导用户参考其个人投资计划（如有）或咨询持牌投顾。

【A股财报披露时间规则】
- 年报：1月1日～4月30日 | 一季报：4月30日前 | 半年报：8月31日前 | 三季报：10月31日前

{knowledge_snippets}
{_build_profile_block(user_profile)}
{memory_block}{memory_directive}【合规原则】
- 你是助理+教练，不是投顾：**教分析方法，不给"买入/卖出/持有"的直接建议**
- 所有观点必须有工具返回的数据支撑，不做主观臆断
- 不提供目标价、仓位建议、具体买卖时点
- 每次回答结尾自然提醒：以上分析仅供学习参考，不构成投资建议
- **对"是否值得入手/该不该买/现在能不能买/要不要加仓"等直接索要投资建议的问题**，按以下方式处理：
  1. 第一句话明确告知："我无法提供'是否值得入手'这类投资建议，这需要您根据自身风险承受能力和投资策略独立判断。"
  2. 简要列出你可以从哪些维度研究这只股票（如：基本面盈利质量、技术面趋势位置、行业竞争格局、估值水平横向对比、资金面动向），每个维度一句话说明看什么，**不要展开给数据**
  3. 询问用户想从哪个维度开始研究，由用户选择后调用对应工具获取真实数据
  4. **严禁**在此类问题的回答中直接给出长篇分析报告、具体数据表格、止损价位、仓位建议——那等于变相替用户做了投资决策

【工具使用原则】
- **严禁**根据训练数据回答行情、大盘、市场等需要实时数据的问题，**必须**通过调用工具获取
- 对“大盘现在多少点”“今年高点/低点”“MACD/RSI 是否超买”“技术面怎么看”“市场是否放量”“最近是否突破/回调”这类问题，必须先调用工具，再回答
- 根据每个工具的描述，**自主选择**最合适的工具；若一次调用不足，可继续调用其他工具
- 所有需要 curr_date 或 trade_date 的工具，**必须**传入上述日期
- 对“截至目前”“最新”“近期是否有变化”“请确认最新口径”“最新公告/持股比例/减持进展”这类问题，优先调用“近期信息搜索”或相关新闻工具，先检索近期公开信息，再回答
- **板块/行业类问题**优先使用板块级别工具，无需股票代码
- **操作类请求**（分析、报告、定时、股票关注列表）优先使用 assistant_ops 类工具
- 如果系统里已经存在合适的完整 Agent，优先考虑直接调用 Agent 完成任务；只有在没有合适 Agent 时，再退回到底层工具组合
- 对“分析某只股票”“看看持仓”“查一下报告”这类零星查询，直接完成查询或分析，不要为了记录上下文而新建研究主题
- 对股票筛选/智能筛选类请求，如果筛选工具返回“未找到符合条件的股票”或明确空结果，必须直接告诉用户当前没有符合其条件的标的。
- 在股票筛选空结果场景下，严禁为了“给点参考”而推荐其它不符合筛选条件的股票，严禁擅自放宽条件后再给出候选名单；只有用户明确要求你放宽条件或改条件时，才可以继续下一步。

【Web 搜索策略】
- **数据库覆盖范围**：财务报表（资产负债表/利润表/现金流量表）、行情数据（K线/技术指标）、资金流向、板块数据、宏观指标、估值数据等结构化数据
- **数据库不覆盖的数据**：月度销量、产销快报、行业新闻、最新公告、政策动态、公司公告等非结构化实时信息
- **判断流程**：用户问的数据如果不在数据库覆盖范围内（如“某月销量”“最新公告”“行业动态”），直接调用 `web_search` 搜索互联网，不要先尝试数据库工具
- **搜索策略**：拆分关键词，每次搜索一个维度的信息。例如“赛力斯4-7月销量趋势”，分别搜索“赛力斯 4月销量”“赛力斯 5月销量”等，而不是一次搜索所有月份
- **数据提取**：优先从搜索结果的摘要中提取关键数字。如果摘要信息不够完整，再调用 `fetch_url` 抓取完整网页内容
- **分析要求**：获取到数据后，做同比/环比分析、趋势分析，给出有数据支撑的结论
{topic_block}
{stock_scope_block}
{im_block}"""


def _resolve_models(config_doc) -> tuple:
    """从配置文档解析默认模型选择，优先 config_id，其次兼容旧 model_name。"""
    return (
        _resolve_model_selection(config_doc, "quick_analysis_model"),
        _resolve_model_selection(config_doc, "deep_analysis_model"),
        _resolve_model_selection(config_doc, "deep_reasoning_model"),
        _resolve_model_selection(config_doc, "coding_model"),
    )


def _normalize_model_name(model_name: Optional[str]) -> Optional[str]:
    if not model_name:
        return None
    text = str(model_name).strip()
    return text or None


def _normalize_config_id(config_id: Optional[str]) -> Optional[str]:
    if not config_id:
        return None
    text = str(config_id).strip()
    return text or None


def _get_config_setting_value(config_doc: Dict[str, Any], key: str) -> Any:
    default_models = config_doc.get("default_models") or {}
    system_settings = config_doc.get("system_settings") or {}
    return default_models.get(key) or system_settings.get(key)


def _get_default_provider(config_doc: Dict[str, Any]) -> str:
    return str(_get_config_setting_value(config_doc, "default_provider") or "").strip().lower()


def _select_llm_config_from_doc(
    config_doc: Dict[str, Any],
    *,
    config_id: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    llm_configs = [cfg for cfg in (config_doc.get("llm_configs") or []) if cfg.get("enabled", True)]
    normalized_config_id = _normalize_config_id(config_id)
    normalized_model_name = _normalize_model_name(model_name)

    if normalized_config_id:
        exact_config = next(
            (
                cfg
                for cfg in llm_configs
                if _normalize_config_id(cfg.get("config_id")) == normalized_config_id
            ),
            None,
        )
        if exact_config is not None:
            return exact_config

    if not normalized_model_name:
        return None

    model_configs = [cfg for cfg in llm_configs if _normalize_model_name(cfg.get("model_name")) == normalized_model_name]
    if not model_configs:
        return None

    preferred_provider = _get_default_provider(config_doc)
    if preferred_provider:
        preferred_config = next(
            (
                cfg
                for cfg in model_configs
                if str(cfg.get("provider") or "").strip().lower() == preferred_provider
            ),
            None,
        )
        if preferred_config is not None:
            return preferred_config

    return model_configs[0]


def _resolve_model_selection(config_doc: Dict[str, Any], model_key: str) -> Optional[Dict[str, Any]]:
    config_id = _normalize_config_id(_get_config_setting_value(config_doc, f"{model_key}_config_id"))
    model_name = _normalize_model_name(_get_config_setting_value(config_doc, model_key))
    matched_config = _select_llm_config_from_doc(
        config_doc,
        config_id=config_id,
        model_name=model_name,
    )
    if matched_config is not None:
        return {
            "config_id": _normalize_config_id(matched_config.get("config_id")),
            "model_name": _normalize_model_name(matched_config.get("model_name")),
            "provider": str(matched_config.get("provider") or "").strip().lower(),
        }
    if not config_id and not model_name:
        return None
    return {
        "config_id": config_id,
        "model_name": model_name,
        "provider": None,
    }


def _selection_model_name(selection: Optional[Dict[str, Any]]) -> Optional[str]:
    if not selection:
        return None
    return _normalize_model_name(selection.get("model_name"))


def _selection_config_id(selection: Optional[Dict[str, Any]]) -> Optional[str]:
    if not selection:
        return None
    return _normalize_config_id(selection.get("config_id"))


def _normalize_preferred_models(preferred_models: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not preferred_models:
        return {}

    normalized: Dict[str, str] = {}
    unified_model = _normalize_model_name(preferred_models.get("model"))
    unified_model_config_id = _normalize_config_id(preferred_models.get("model_config_id"))
    quick_model = _normalize_model_name(preferred_models.get("quick_model"))
    quick_model_config_id = _normalize_config_id(preferred_models.get("quick_model_config_id"))
    deep_model = _normalize_model_name(preferred_models.get("deep_model"))
    deep_model_config_id = _normalize_config_id(preferred_models.get("deep_model_config_id"))

    if unified_model:
        normalized["model"] = unified_model
    if unified_model_config_id:
        normalized["model_config_id"] = unified_model_config_id

    if quick_model:
        normalized["quick_model"] = quick_model
    if quick_model_config_id:
        normalized["quick_model_config_id"] = quick_model_config_id
    if deep_model:
        normalized["deep_model"] = deep_model
    if deep_model_config_id:
        normalized["deep_model_config_id"] = deep_model_config_id

    if unified_model and not quick_model:
        normalized["quick_model"] = unified_model
    if unified_model and not deep_model:
        normalized["deep_model"] = unified_model
    if unified_model_config_id and not quick_model_config_id:
        normalized["quick_model_config_id"] = unified_model_config_id
    if unified_model_config_id and not deep_model_config_id:
        normalized["deep_model_config_id"] = unified_model_config_id

    return normalized


def _get_preferred_assistant_model(preferred_models: Optional[Dict[str, Any]]) -> Optional[str]:
    normalized = _normalize_preferred_models(preferred_models)
    return (
        normalized.get("model")
        or normalized.get("deep_model")
        or normalized.get("quick_model")
    )


def _get_preferred_assistant_config_id(preferred_models: Optional[Dict[str, Any]]) -> Optional[str]:
    normalized = _normalize_preferred_models(preferred_models)
    return (
        normalized.get("model_config_id")
        or normalized.get("deep_model_config_id")
        or normalized.get("quick_model_config_id")
    )


def _build_assistant_model_preferences(
    model: Optional[str] = None,
    model_config_id: Optional[str] = None,
    quick_model: Optional[str] = None,
    quick_model_config_id: Optional[str] = None,
    deep_model: Optional[str] = None,
    deep_model_config_id: Optional[str] = None,
) -> Dict[str, str]:
    normalized = _normalize_preferred_models(
        {
            "model": model,
            "model_config_id": model_config_id,
            "quick_model": quick_model,
            "quick_model_config_id": quick_model_config_id,
            "deep_model": deep_model,
            "deep_model_config_id": deep_model_config_id,
        }
    )
    assistant_model = _get_preferred_assistant_model(normalized)
    assistant_model_config_id = _get_preferred_assistant_config_id(normalized)
    if not assistant_model and not assistant_model_config_id:
        return {}
    preferred: Dict[str, str] = {}
    if assistant_model:
        preferred["model"] = assistant_model
    if assistant_model_config_id:
        preferred["model_config_id"] = assistant_model_config_id
    return preferred


async def _get_llm_config_for_model(
    db,
    target_model: Optional[str],
    target_config_id: Optional[str] = None,
    purpose: str = "",
) -> Optional[LLMConfig]:
    """根据模型选择获取 LLM 配置，优先 config_id，兼容旧 model_name。"""
    if not target_model and not target_config_id:
        return None
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    return resolve_llm_config_from_config_doc(
        config_doc,
        target_model=target_model,
        target_config_id=target_config_id,
        purpose=purpose,
    )


def resolve_llm_config_from_config_doc(
    config_doc: Optional[Dict[str, Any]],
    *,
    target_model: Optional[str],
    target_config_id: Optional[str] = None,
    purpose: str = "",
) -> Optional[LLMConfig]:
    """基于 system_configs 文档解析统一 LLMConfig，供各子系统共享。"""
    if not config_doc or "llm_configs" not in config_doc:
        return None

    model_config = _select_llm_config_from_doc(
        config_doc,
        config_id=target_config_id,
        model_name=target_model,
    )
    if model_config is None:
        return None

    resolved_model_name = _normalize_model_name(model_config.get("model_name")) or _normalize_model_name(target_model)
    if not resolved_model_name:
        return None

    from app.services.simple_analysis_service import get_provider_and_url_by_model_sync

    provider_info = get_provider_and_url_by_model_sync(
        resolved_model_name,
        preferred_provider=str(model_config.get("provider") or _get_default_provider(config_doc) or "").strip().lower(),
        preferred_config_id=_normalize_config_id(model_config.get("config_id")) or target_config_id,
    )
    if not provider_info:
        return None

    provider_str = str(model_config.get("provider") or provider_info.get("provider") or "").lower()
    provider_map = {
        "openai": LLMProvider.OPENAI, "deepseek": LLMProvider.DEEPSEEK,
        "dashscope": LLMProvider.DASHSCOPE, "qwen": LLMProvider.DASHSCOPE,
        "zhipu": LLMProvider.ZHIPU, "google": LLMProvider.GOOGLE,
        "anthropic": LLMProvider.ANTHROPIC, "siliconflow": LLMProvider.SILICONFLOW,
        "kimi": LLMProvider.OPENAI, "moonshot": LLMProvider.OPENAI,
        "ollama": LLMProvider.OLLAMA, "openrouter": LLMProvider.OPENROUTER,
    }
    provider = provider_map.get(provider_str, LLMProvider.DASHSCOPE)
    logger.info(
        "[智能助手] 模型路由解析: provider=%s model=%s config_id=%s backend_provider=%s",
        provider_str or "unknown",
        resolved_model_name,
        _normalize_config_id(model_config.get("config_id")) or target_config_id or "",
        provider.value,
    )
    return LLMConfig(
        provider=provider, model=resolved_model_name,
        api_key=provider_info.get("api_key"), base_url=provider_info.get("backend_url"),
        temperature=float(model_config.get("temperature", 0.2)),
        max_tokens=int(model_config.get("max_tokens", 4000)),
        timeout=int(model_config.get("timeout", 60)),
        retry_times=int(model_config.get("retry_times", 3)),
    )


def get_system_llm_config_from_config_doc(
    config_doc: Optional[Dict[str, Any]],
    *,
    model_keys: Optional[List[str]] = None,
) -> Optional[LLMConfig]:
    """按系统设置中的模型选择顺序解析统一 LLMConfig。"""
    if not config_doc or "llm_configs" not in config_doc:
        return None

    resolved_model_keys = model_keys or ["quick_analysis_model", "deep_analysis_model"]
    for model_key in resolved_model_keys:
        selection = _resolve_model_selection(config_doc, model_key)
        if not selection:
            continue

        llm_config = resolve_llm_config_from_config_doc(
            config_doc,
            target_model=_selection_model_name(selection),
            target_config_id=_selection_config_id(selection),
            purpose=model_key,
        )
        if llm_config is not None:
            return llm_config

    for llm_config_doc in config_doc.get("llm_configs") or []:
        if not llm_config_doc.get("enabled", True):
            continue
        llm_config = resolve_llm_config_from_config_doc(
            config_doc,
            target_model=_normalize_model_name(llm_config_doc.get("model_name")),
            target_config_id=_normalize_config_id(llm_config_doc.get("config_id")),
            purpose="first_enabled",
        )
        if llm_config is not None:
            return llm_config

    return None


async def _get_assistant_llm_config(
    db,
    use_reasoning_model: bool = False,
    preferred_models: Optional[Dict[str, Any]] = None,
) -> Optional[LLMConfig]:
    """
    从数据库获取智能助手使用的 LLM 配置
    优先使用深度思考模型（deep_analysis_model），以保证时间逻辑、财报披露等推理准确
    use_reasoning_model=True 时，优先使用深度推理模型（deep_reasoning_model），适用于策略生成、规划等
    若未配置则回退到快速模型或默认模型
    """
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    if not config_doc or "llm_configs" not in config_doc:
        logger.warning("[智能助手] 数据库中没有 LLM 配置")
        return None

    llm_configs = config_doc.get("llm_configs", [])
    default_llm = config_doc.get("default_llm")
    quick_selection, deep_selection, reasoning_selection, _ = _resolve_models(config_doc)
    quick_model = _selection_model_name(quick_selection)
    deep_model = _selection_model_name(deep_selection)
    reasoning_model = _selection_model_name(reasoning_selection)
    preferred_assistant_model = _get_preferred_assistant_model(preferred_models)
    preferred_assistant_config_id = _get_preferred_assistant_config_id(preferred_models)
    target_config_id: Optional[str] = None

    if use_reasoning_model and (preferred_assistant_model or preferred_assistant_config_id):
        target_model = preferred_assistant_model
        target_config_id = preferred_assistant_config_id
        logger.info(
            "[智能助手] 使用用户选择的助手模型: model=%s config_id=%s",
            target_model or "",
            target_config_id or "",
        )
    elif use_reasoning_model and reasoning_selection:
        target_model = _selection_model_name(reasoning_selection)
        target_config_id = _selection_config_id(reasoning_selection)
        logger.info(f"[智能助手] 使用深度推理模型: {target_model}")
    else:
        target_selection = deep_selection or quick_selection
        target_model = preferred_assistant_model or _selection_model_name(target_selection) or default_llm
        if preferred_assistant_config_id:
            target_config_id = preferred_assistant_config_id
        elif not preferred_assistant_model and target_selection is not None:
            target_config_id = _selection_config_id(target_selection)
        if preferred_assistant_model or preferred_assistant_config_id:
            logger.info(
                "[智能助手] 使用用户选择的助手模型: model=%s config_id=%s",
                preferred_assistant_model or "",
                preferred_assistant_config_id or "",
            )
        elif deep_selection:
            logger.info(f"[智能助手] 使用深度分析模型: {deep_model}")
        elif quick_selection:
            logger.info(f"[智能助手] 深度模型未配置，使用快速模型: {quick_model}")

    if not target_model:
        target_model = preferred_assistant_model or deep_model or quick_model or default_llm
    if not target_model and llm_configs:
        for cfg in llm_configs:
            if cfg.get("enabled", True):
                target_model = cfg.get("model_name")
                target_config_id = _normalize_config_id(cfg.get("config_id"))
                break

    if not target_model:
        logger.warning("[智能助手] 未找到可用的模型配置")
        return None

    return await _get_llm_config_for_model(db, target_model, target_config_id=target_config_id)


async def get_reasoning_llm_config(db=None):
    """
    获取深度推理模型配置，用于策略 DSL 生成、规划等需要强推理的场景
    优先 deep_reasoning_model，未配置时回退到 deep_analysis_model
    """
    from app.core.database import get_mongo_db
    db = db if db is not None else get_mongo_db()
    return await _get_assistant_llm_config(db, use_reasoning_model=True)


async def get_coding_llm_config(db=None):
    """
    获取编程模型配置，用于策略 DSL 生成等需要结构化 JSON 输出的场景
    优先 coding_model，未配置时回退到 deep_reasoning_model → deep_analysis_model
    """
    from app.core.database import get_mongo_db
    db = db if db is not None else get_mongo_db()
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    if not config_doc or "llm_configs" not in config_doc:
        return await get_reasoning_llm_config(db)
    _, deep_selection, reasoning_selection, coding_selection = _resolve_models(config_doc)
    deep_model = _selection_model_name(deep_selection)
    reasoning_model = _selection_model_name(reasoning_selection)
    coding_model = _selection_model_name(coding_selection)
    target_selection = coding_selection or reasoning_selection or deep_selection
    target_model = _selection_model_name(target_selection)
    target_config_id = _selection_config_id(target_selection)
    if target_model:
        logger.info(f"[编程模型] 使用: {target_model} (coding={bool(coding_model)}, reasoning={bool(reasoning_model)})")
    return await _get_llm_config_for_model(db, target_model, target_config_id=target_config_id) if target_model else await get_reasoning_llm_config(db)


class IntelligentAssistantService:
    """智能助手服务"""

    def __init__(
        self,
        db,
        preferred_models: Optional[Dict[str, Any]] = None,
        prefer_reasoning_model: bool = False,
        user_id: str = "",
        assistant_role: str = "general",
        user_context: Optional[dict] = None,
    ):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._openai_tools: Optional[List[Dict[str, Any]]] = None
        self._tool_functions: Optional[Dict[str, Any]] = None
        self._preferred_model = _get_preferred_assistant_model(preferred_models)
        self._preferred_model_config_id = _get_preferred_assistant_config_id(preferred_models)
        self._prefer_reasoning_model = prefer_reasoning_model
        self._user_id = user_id  # 用于构造带 user_id 闭包的元工具（如 remember_this）
        # v3.0 新增：使用问答机器人角色相关字段
        self._assistant_role = assistant_role or "general"
        self._user_context = user_context or {}

    async def _ensure_client(self) -> bool:
        """确保 LLM 客户端和工具已加载"""
        if self._llm_client is not None:
            return True

        llm_config = await _get_assistant_llm_config(
            self._db,
            use_reasoning_model=self._prefer_reasoning_model,
            preferred_models=_build_assistant_model_preferences(
                model=self._preferred_model,
                model_config_id=self._preferred_model_config_id,
            ) if (self._preferred_model or self._preferred_model_config_id) else None,
        )
        if not llm_config:
            return False

        try:
            self._llm_client = UnifiedLLMClient.from_config(llm_config)
        except Exception as e:
            logger.error(f"[智能助手] 创建 LLM 客户端失败: {e}", exc_info=True)
            return False

        registry = get_tool_registry()
        all_metadata = registry.list_all()

        # v3.0 新增：使用问答机器人只注册 9 个系统感知工具
        # 不加载金融市场数据工具、不加载分析师 Agent 工具
        if self._assistant_role == "usage_helper":
            allowed_tool_ids = {
                "get_user_current_state",
                "get_system_status",
                "get_user_recent_activity",
                "read_user_manual_section",
                "search_user_manual",  # 向量语义检索（v3.0.1 新增，解决自然语言问题匹配）
                "get_data_sync_status",
                "get_paper_trading_status",
                "get_token_usage",
                "get_running_tasks",
            }
            all_metadata = [t for t in all_metadata if t.id in allowed_tool_ids]
            logger.info(f"[智能助手·使用问答] 仅加载 {len(all_metadata)} 个系统感知工具（含向量检索/数据同步/模拟交易/Token用量/任务进度）")

        self._openai_tools = tool_metadata_list_to_openai(all_metadata)

        self._tool_functions = {}
        for tool in all_metadata:
            # 无参数工具同样需要注入，否则会出现"工具已加载但无法执行"
            if tool.fc_enabled:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        # 注入 `remember_this` 元工具：允许用户主动让助手记住偏好
        # 参考：docs/05-design/v3.0/unified-memory-layer-mem0.md §15.5 P0-1
        # 使用问答机器人不注入 remember_this（避免污染用户长期记忆）
        if self._user_id and self._assistant_role != "usage_helper":
            self._openai_tools.append(_build_remember_this_tool_def())
            self._tool_functions[REMEMBER_THIS_TOOL_NAME] = _make_remember_this_callable(
                self._db, self._user_id,
            )

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(f"[智能助手] 已加载 {len(self._openai_tools)} 个工具")
        return True

    def _build_tool_interceptor(self, conversation_id: str):
        """构建 HITL 工具拦截器（v3.6.0：提取为类方法，供 chat/chat_stream 共用）。

        对关键操作（触发分析/删除配置等）先保存 pending 到 MongoDB，
        让用户确认后再执行，避免 LLM 在流式/非流式路径下绕过确认直接执行。
        """
        async def _intercept(tool_call) -> Optional[Any]:
            from core.hitl.assistant_hitl import (
                is_critical_tool,
                save_pending_critical_action,
                build_pending_confirmation_reply,
            )

            tool_id = tool_call.name
            if not is_critical_tool(tool_id):
                return None

            pending_id = await save_pending_critical_action(
                self._db,
                user_id=self._user_id or "default",
                conversation_id=conversation_id or "default",
                tool_id=tool_id,
                tool_arguments=tool_call.arguments,
            )
            if not pending_id:
                # 保存失败时降级为直接执行
                return None

            confirmation_msg = build_pending_confirmation_reply(
                tool_id=tool_id,
                tool_arguments=tool_call.arguments,
                pending_id=pending_id,
            )
            # 返回 ToolResult（兼容统一 LLM 客户端）
            from core.llm.unified_client import ToolResult
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_id,
                content=confirmation_msg,
                is_error=False,
            )
        return _intercept

    async def chat(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        assistant_settings: dict = None,
        is_im: bool = False,
        history_messages: Optional[List[Message]] = None,
        user_profile: Optional[dict] = None,
        current_topic_title: Optional[str] = None,
        memory_block: str = "",
    ) -> Dict[str, Any]:
        """
        处理用户对话

        Args:
            user_message: 用户输入
            conversation_id: 会话 ID（首版未使用，预留）
            assistant_settings: 用户助理个性化设置
            is_im: 是否来自 IM 渠道，为 True 时注入移动端格式规范到 system prompt
            memory_block: mem0 召回的格式化记忆文本

        Returns:
            {"reply": str, "tools_used": List[str], "data_refs": Optional[List]}
        """
        resolved_user_message = _rewrite_number_selection_reply(user_message, history_messages)

        # v3.5.0 项4：智能助手 HITL —— 检查用户是否在确认/拒绝待确认操作
        # 如果用户消息是确认/拒绝意图，且有 pending 操作，直接执行/丢弃，不进入 LLM 循环
        try:
            from core.hitl.assistant_hitl import try_resolve_pending_action
            resolution = await try_resolve_pending_action(
                self._db,
                user_id=self._user_id or "default",
                conversation_id=conversation_id or "default",
                user_message=resolved_user_message,
            )
            if resolution:
                if resolution.get("type") == "confirmed":
                    result_text = resolution.get("result", "") or "操作已执行完成"
                    return {
                        "reply": f"✅ 已确认执行：{result_text}",
                        "tools_used": [resolution.get("tool_id", "")],
                        "data_refs": None,
                    }
                elif resolution.get("type") == "rejected":
                    return {
                        "reply": resolution.get("message", "已取消操作"),
                        "tools_used": [],
                        "data_refs": None,
                    }
        except Exception as e:
            logger.warning(f"[智能助手] HITL 检查失败（降级为正常对话）: {e}")

        # 前置检查：不支持的品种类型
        from app.services.planned_analysis_service import _check_unsupported_asset
        unsupported_msg = _check_unsupported_asset(resolved_user_message)
        if unsupported_msg:
            return {
                "reply": unsupported_msg,
                "tools_used": [],
                "data_refs": None,
            }

        if not await self._ensure_client():
            return {
                "reply": "智能助手暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。",
                "tools_used": [],
                "data_refs": None,
            }

        # 快路径：对“最新/截至目前/近期确认”类事实问题，优先直接执行近期搜索工具，
        # 避免模型在首轮未触发工具时退回训练期知识。
        if _should_use_recent_search(resolved_user_message):
            try:
                from core.tools.implementations.assistant_ops.recent_search import run_recent_information_search

                tool_result = run_recent_information_search(resolved_user_message.strip())
                if inspect.isawaitable(tool_result):
                    tool_result = await tool_result
                tool_text = str(tool_result or "").strip()
                if tool_text:
                    logger.info("[智能助手] 命中近期搜索快路径，直接返回搜索结果")
                    return {
                        "reply": tool_text,
                        "tools_used": ["search_recent_information"],
                        "data_refs": None,
                    }
            except Exception as e:
                logger.warning(f"[智能助手] 近期搜索快路径失败，回退常规对话: {e}")

        # 数据同步预检查：当用户问到某只股票的数据相关问题时，
        # 先检查该股票的数据是否已同步。数据不充分直接提示用户同步，不调 LLM。
        stock_code = _extract_stock_code(resolved_user_message)
        if not stock_code:
            # 没有直接匹配到股票代码，尝试从股票名称解析
            text_lower = resolved_user_message.lower()
            has_data_keyword = any(k in text_lower for k in _STOCK_DATA_KEYWORDS)
            if has_data_keyword:
                stock_code = await _resolve_stock_name_to_code(resolved_user_message, db=self._db)
                logger.info("[智能助手] 预检查·名称解析结果: %s", stock_code)
        if stock_code:
            text_lower = resolved_user_message.lower()
            has_data_keyword = any(k in text_lower for k in _STOCK_DATA_KEYWORDS)
            if has_data_keyword:
                sync_status = await _check_stock_data_sync(stock_code, db=self._db)
                logger.info("[智能助手] 预检查·股票 %s 数据状态: %s", stock_code, sync_status)
                if sync_status and not sync_status.get("error"):
                    has_hist = sync_status.get("has_historical", False)
                    has_fin = sync_status.get("has_financial", False)
                    has_basic = sync_status.get("has_basic", False)
                    hist_records = sync_status.get("hist_records", 0)
                    fin_records = sync_status.get("fin_records", 0)

                    # 判断用户问题需要哪些数据
                    financial_keywords = [
                        "财报", "利润", "营收", "收入", "净利润", "毛利率", "现金流",
                        "资产", "负债", "估值", "市盈率", "市净率", "pe", "pb", "ps",
                        "盈利", "财务", "roe", "roa", "资产负债率",
                    ]
                    technical_keywords = [
                        "技术面", "技术指标", "macd", "rsi", "kdj", "boll", "布林",
                        "均线", "ma", "ema", "超买", "超卖", "背离", "支撑", "阻力",
                        "压力位", "趋势", "k线",
                    ]
                    investment_decision_keywords = [
                        "入手", "买入", "卖出", "加仓", "减仓", "持有", "清仓",
                        "值得", "能不能买", "该不该", "怎么样", "如何", "分析",
                    ]
                    asks_financial = any(k in text_lower for k in financial_keywords)
                    asks_technical = any(k in text_lower for k in technical_keywords)
                    asks_investment_decision = any(k in text_lower for k in investment_decision_keywords)
                    # 投资决策类问题需要财务+技术面综合判断
                    if asks_investment_decision:
                        asks_financial = True
                        asks_technical = True

                    # 构建缺失数据提示
                    missing_parts = []
                    if asks_financial and not has_fin:
                        missing_parts.append(f"财务数据（利润表/资产负债表/现金流量表，当前 0 条）")
                    if asks_technical and (not has_hist or hist_records < 30):
                        missing_parts.append(f"历史行情数据（当前 {hist_records} 条，技术分析需要至少 30 条）")

                    if missing_parts:
                        missing_text = "\n".join(f"• ❌ {p}" for p in missing_parts)
                        available_text = (
                            f"• ✅ 历史行情: {hist_records} 条"
                            if has_hist else "• ❌ 历史行情: 未同步"
                        )
                        available_text += "\n"
                        available_text += (
                            f"• ✅ 财务数据: {fin_records} 条"
                            if has_fin else "• ❌ 财务数据: 未同步"
                        )
                        available_text += "\n"
                        available_text += "✅ 基础数据: 已同步" if has_basic else "❌ 基础数据: 未同步"

                        logger.info(
                            "[智能助手] 股票 %s 数据不充分，拦截（缺失: %s）",
                            stock_code, ", ".join(missing_parts)
                        )
                        return {
                            "reply": (
                                f"📊 股票 {stock_code} 的数据不充分，无法进行分析\n\n"
                                f"当前数据同步状态：\n{available_text}\n\n"
                                f"缺失的数据：\n{missing_text}\n\n"
                                f"请先同步数据后再提问：\n"
                                f"• 前往「数据管理」页面，搜索 {stock_code} 并触发数据同步\n"
                                f"• 建议同步完整的历史行情（至少 250 个交易日）和财务数据\n"
                                f"• 同步完成后再次提问，我会调用工具获取真实数据为您分析\n\n"
                                f"或者，如果您只是想了解互联网公开信息，我也可以通过 web_search 搜索。"
                                f"是否需要我搜索？"
                            ),
                            "tools_used": ["get_data_sync_status"],
                            "data_refs": None,
                        }

        # RAG 动态知识检索（优雅降级：不可用时返回空字符串）
        knowledge_snippets = ""
        try:
            from core.knowledge import FinancialKnowledgeManager
            km = FinancialKnowledgeManager(db=self._db)
            knowledge_snippets = km.retrieve_for_prompt(resolved_user_message)
            if knowledge_snippets:
                logger.info(f"[智能助手] ✅ RAG 知识检索成功 ({len(knowledge_snippets)} 字符)")
            else:
                logger.info("[智能助手] RAG 知识检索返回空（无匹配知识）")
        except Exception as e:
            logger.warning(f"[智能助手] ⚠️ 知识检索失败（降级为静态知识）: {e}")

        # 构建消息列表：系统提示 + 历史记录 + 当前用户消息
        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=_get_system_prompt(
                    knowledge_snippets,
                    assistant_settings,
                    is_im=is_im,
                    user_profile=user_profile,
                    current_topic_title=current_topic_title,
                    memory_block=memory_block,
                    assistant_role=self._assistant_role,
                    user_context=self._user_context,
                ),
            ),
        ]
        if history_messages:
            messages.extend(history_messages)
            logger.info(f"[智能助手] 已注入 {len(history_messages)} 条历史消息")
        messages.append(Message(role=MessageRole.USER, content=resolved_user_message.strip()))

        tools_used: List[str] = []
        tool_results: List[Dict[str, Any]] = []

        def _effective_timeout() -> int:
            """根据已调用工具的 tier 动态计算总超时"""
            base = ASSISTANT_TIMEOUT_SECONDS
            if not tools_used:
                return base
            try:
                from core.tools import get_tool_registry
                from core.tools.config import ToolTimeoutTier
                registry = get_tool_registry()
                for name in tools_used:
                    meta = registry.get(name)
                    if meta and getattr(meta, "timeout_tier", "") == ToolTimeoutTier.HEAVY:
                        return base + ASSISTANT_HEAVY_TOOL_EXTRA_SECONDS
            except Exception:
                pass
            return base

        async def _do_chat():
            nonlocal tools_used

            tool_interceptor = self._build_tool_interceptor(conversation_id or "default")

            resp = await self._llm_client.achat(
                messages,
                tools=self._openai_tools,
                auto_execute_tools=True,
                max_tool_rounds=8,
                tools_used=tools_used,
                tool_results_collector=tool_results,
                dry_run=False,
                tool_interceptor=tool_interceptor,
            )
            await _record_assistant_token_usage(resp, conversation_id or "assistant_chat")

            # 兜底：对于“应走工具”的个人数据查询，如果首轮未调工具，则二次强制引导
            if not tools_used and _should_force_tool_retry(resolved_user_message):
                logger.warning("[智能助手] 首轮未调用工具，触发工具重试兜底")
                retry_messages = list(messages)
                retry_messages.append(Message(
                    role=MessageRole.USER,
                    content=(
                        "请不要直接根据上下文猜测或编造结果。"
                        "这类问题必须先调用相关工具获取真实数据，再基于工具返回回答。"
                        "尤其不能直接编造指数点位、涨跌幅、MACD、RSI、均线、成交额等实时数字。"
                        "如果工具返回为空或日期不匹配，再明确说明数据为空或数据日期不匹配。"
                    ),
                ))

                # 优先尝试强制 tool choice；若模型侧不支持则降级为普通重试
                try:
                    resp = await self._llm_client.achat(
                        retry_messages,
                        tools=self._openai_tools,
                        auto_execute_tools=True,
                        max_tool_rounds=8,
                        tools_used=tools_used,
                        tool_results_collector=tool_results,
                        dry_run=False,
                        tool_choice="required",
                        tool_interceptor=tool_interceptor,
                    )
                    await _record_assistant_token_usage(resp, conversation_id or "assistant_chat")
                except Exception as retry_err:
                    logger.warning("[智能助手] tool_choice=required 重试失败，降级普通重试: %s", retry_err)
                    resp = await self._llm_client.achat(
                        retry_messages,
                        tools=self._openai_tools,
                        auto_execute_tools=True,
                        max_tool_rounds=8,
                        tools_used=tools_used,
                        tool_results_collector=tool_results,
                        dry_run=False,
                        tool_interceptor=tool_interceptor,
                    )
                    await _record_assistant_token_usage(resp, conversation_id or "assistant_chat")

            # 回复后验证：检测 LLM 是否在文本中伪造了工具调用痕迹
            reply_content = resp.content or ""
            if _has_fabricated_tool_json(reply_content):
                logger.warning("[智能助手] 检测到编造的工具JSON结果，硬拦截回复")
                return (
                    "抱歉，我在呈现工具返回结果时出现了格式错误（把工具返回改写成了结构化数据），"
                    "这可能导致数据失真。\n\n"
                    "请重新提问，我会严格按工具返回的原始内容为您呈现分析结果。"
                )
            if _has_fabricated_tool_refs(reply_content, tools_used):
                logger.warning("[智能助手] 检测到伪造工具调用痕迹，拦截回复（tools_used=%s）", tools_used)
                return (
                    "抱歉，我在生成回复时出现了数据来源标注错误。\n\n"
                    "为确保您获取的信息真实可靠，请尝试将问题拆分得更具体一些，"
                    "例如直接指定想查看的数据维度（如\"查一下牧原股份最新财报\"\"看技术指标\"等），"
                    "我会调用对应工具获取真实数据后为您分析。"
                )
            if _has_unsourced_numbers(reply_content, tools_used):
                logger.warning("[智能助手] 检测到未调工具但回复含大量数字，拦截回复（数字数=%d）",
                               len(_SPECIFIC_NUMBER_RE.findall(reply_content)))
                return (
                    "抱歉，我目前未能通过工具获取到与您问题相关的实时数据，无法提供有数据支撑的分析。\n\n"
                    "可能的原因：数据库中的股票数据尚未同步完整。\n"
                    "建议您：\n"
                    "• 在\"数据管理\"页面同步该股票的基础数据和历史行情\n"
                    "• 同步完成后再次提问，我会调用工具获取真实数据为您分析\n"
                    "• 或尝试通过 web_search 搜索互联网公开信息"
                )
            if _has_untraced_risky_numbers(
                reply_content, tool_results, tools_used,
                resolved_user_message,
                _extract_history_tool_contents(messages),
            ):
                logger.warning("[智能助手] 检测到无法溯源的高风险数字（疑似训练记忆填充/单位换算错误），拦截回复")
                untraced_detail = "、".join(_get_untraced_risky_numbers(
                    reply_content, tool_results, resolved_user_message,
                    _extract_history_tool_contents(messages))[:6])
                return (
                    "抱歉，我在刚才的回复中引用了一些工具和搜索结果里都没有的具体数字"
                    f"（如 {untraced_detail}），这类数字可能来自过时的记忆而非实时数据，"
                    "继续呈现会误导您的判断，因此已整段拦截。\n\n"
                    "常见原因：搜索结果只有标题/链接/摘要，未包含具体数值"
                    "（如行业成本数据多在付费研报正文中，搜索引擎摘要抓不到）。\n"
                    "您可以：\n"
                    "• 换更具体的关键词让我再搜索（如\"牧原股份 7月成本 公告\"）\n"
                    "• 让我引用搜索到的来源链接，由您人工查看原文\n"
                    "• 只让我分析工具已返回的真实数据\n"
                )

            return reply_content

        try:
            content = await asyncio.wait_for(
                _do_chat(),
                timeout=_effective_timeout(),
            )
            reply = content or "抱歉，暂时无法生成回答，请稍后再试。"
            if tools_used:
                logger.info("[智能助手] 已调用工具: %s", tools_used)
            else:
                logger.info("[智能助手] 未调用任何工具（纯文本回复）")
            logger.info("[智能助手] 回复内容(前200字): %s", reply[:200])

            return {
                "reply": reply,
                "tools_used": tools_used,
                "data_refs": None,
            }
        except asyncio.TimeoutError:
            timeout_used = _effective_timeout()
            logger.warning(f"[智能助手] 请求超时（{timeout_used}s）")
            return {
                "reply": f"抱歉，处理您的问题用时过长（已超过 {timeout_used} 秒），为避免长时间等待已中断。\n\n"
                "建议您：\n"
                "• 尝试将问题拆分得更具体一些\n"
                "• 检查网络连接是否稳定\n"
                "• 稍后重试",
                "tools_used": tools_used,
                "data_refs": None,
            }
        except Exception as e:
            logger.exception("[智能助手] 对话失败")
            return {
                "reply": f"处理您的请求时发生错误：{str(e)}。请检查网络和 LLM 配置后重试。",
                "tools_used": tools_used,
                "data_refs": None,
            }

    async def chat_stream(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        assistant_settings: dict = None,
        is_im: bool = False,
        history_messages: Optional[List[Message]] = None,
        user_profile: Optional[dict] = None,
        current_topic_title: Optional[str] = None,
        memory_block: str = "",
    ) -> AsyncGenerator[str, None]:
        """流式对话 — 返回 SSE 格式的 async generator"""

        def _sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        resolved_user_message = _rewrite_number_selection_reply(user_message, history_messages)

        logger.info("[智能助手·流式] chat_stream 开始，user_message=%r", resolved_user_message[:50])

        # v3.5.0 项4：智能助手 HITL —— 流式版本同样检查待确认操作
        try:
            from core.hitl.assistant_hitl import try_resolve_pending_action
            resolution = await try_resolve_pending_action(
                self._db,
                user_id=self._user_id or "default",
                conversation_id=conversation_id or "default",
                user_message=resolved_user_message,
            )
            if resolution:
                if resolution.get("type") == "confirmed":
                    result_text = resolution.get("result", "") or "操作已执行完成"
                    yield _sse("token", {"content": f"✅ 已确认执行：{result_text}"})
                    yield _sse("done", {"tools_used": [resolution.get("tool_id", "")]})
                    return
                elif resolution.get("type") == "rejected":
                    yield _sse("token", {"content": resolution.get("message", "已取消操作")})
                    yield _sse("done", {"tools_used": []})
                    return
        except Exception as e:
            logger.warning(f"[智能助手·流式] HITL 检查失败（降级为正常对话）: {e}")

        from app.services.planned_analysis_service import _check_unsupported_asset
        unsupported_msg = _check_unsupported_asset(resolved_user_message)
        if unsupported_msg:
            yield _sse("token", {"content": unsupported_msg})
            yield _sse("done", {"tools_used": []})
            return

        logger.info("[智能助手·流式] 准备调用 _ensure_client")
        if not await self._ensure_client():
            logger.warning("[智能助手·流式] _ensure_client 返回 False，LLM 客户端创建失败")
            yield _sse("token", {"content": "智能助手暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。"})
            yield _sse("done", {"tools_used": []})
            return
        logger.info("[智能助手·流式] _ensure_client 成功，开始处理对话")

        if _should_use_recent_search(resolved_user_message):
            try:
                from core.tools.implementations.assistant_ops.recent_search import run_recent_information_search
                tool_result = run_recent_information_search(resolved_user_message.strip())
                if inspect.isawaitable(tool_result):
                    tool_result = await tool_result
                tool_text = str(tool_result or "").strip()
                if tool_text:
                    logger.info("[智能助手·流式] 命中近期搜索快路径")
                    yield _sse("token", {"content": tool_text})
                    yield _sse("done", {"tools_used": ["search_recent_information"]})
                    return
            except Exception as e:
                logger.warning(f"[智能助手·流式] 近期搜索快路径失败，回退常规对话: {e}")

        # 数据同步预检查：当用户问到某只股票的数据相关问题时，
        # 先检查该股票的数据是否已同步。数据不充分直接提示用户同步，不调 LLM。
        stock_code_stream = _extract_stock_code(resolved_user_message)
        if not stock_code_stream:
            text_lower_s = resolved_user_message.lower()
            has_data_keyword_s = any(k in text_lower_s for k in _STOCK_DATA_KEYWORDS)
            if has_data_keyword_s:
                stock_code_stream = await _resolve_stock_name_to_code(resolved_user_message, db=self._db)
                logger.info("[智能助手·流式] 预检查·名称解析结果: %s", stock_code_stream)
        if stock_code_stream:
            text_lower_s = resolved_user_message.lower()
            has_data_keyword_s = any(k in text_lower_s for k in _STOCK_DATA_KEYWORDS)
            if has_data_keyword_s:
                sync_status_s = await _check_stock_data_sync(stock_code_stream, db=self._db)
                logger.info("[智能助手·流式] 预检查·股票 %s 数据状态: %s", stock_code_stream, sync_status_s)
                if sync_status_s and not sync_status_s.get("error"):
                    has_hist_s = sync_status_s.get("has_historical", False)
                    has_fin_s = sync_status_s.get("has_financial", False)
                    has_basic_s = sync_status_s.get("has_basic", False)
                    hist_records_s = sync_status_s.get("hist_records", 0)
                    fin_records_s = sync_status_s.get("fin_records", 0)

                    financial_keywords_s = [
                        "财报", "利润", "营收", "收入", "净利润", "毛利率", "现金流",
                        "资产", "负债", "估值", "市盈率", "市净率", "pe", "pb", "ps",
                        "盈利", "财务", "roe", "roa", "资产负债率",
                    ]
                    technical_keywords_s = [
                        "技术面", "技术指标", "macd", "rsi", "kdj", "boll", "布林",
                        "均线", "ma", "ema", "超买", "超卖", "背离", "支撑", "阻力",
                        "压力位", "趋势", "k线",
                    ]
                    investment_decision_keywords_s = [
                        "入手", "买入", "卖出", "加仓", "减仓", "持有", "清仓",
                        "值得", "能不能买", "该不该", "怎么样", "如何", "分析",
                    ]
                    asks_fin_s = any(k in text_lower_s for k in financial_keywords_s)
                    asks_tech_s = any(k in text_lower_s for k in technical_keywords_s)
                    asks_inv_s = any(k in text_lower_s for k in investment_decision_keywords_s)
                    if asks_inv_s:
                        asks_fin_s = True
                        asks_tech_s = True

                    missing_parts_s = []
                    if asks_fin_s and not has_fin_s:
                        missing_parts_s.append(f"财务数据（利润表/资产负债表/现金流量表，当前 0 条）")
                    if asks_tech_s and (not has_hist_s or hist_records_s < 30):
                        missing_parts_s.append(f"历史行情数据（当前 {hist_records_s} 条，技术分析需要至少 30 条）")

                    if missing_parts_s:
                        missing_text_s = "\n".join(f"• ❌ {p}" for p in missing_parts_s)
                        available_text_s = (
                            f"• ✅ 历史行情: {hist_records_s} 条"
                            if has_hist_s else "• ❌ 历史行情: 未同步"
                        )
                        available_text_s += "\n"
                        available_text_s += (
                            f"• ✅ 财务数据: {fin_records_s} 条"
                            if has_fin_s else "• ❌ 财务数据: 未同步"
                        )
                        available_text_s += "\n"
                        available_text_s += "✅ 基础数据: 已同步" if has_basic_s else "❌ 基础数据: 未同步"

                        logger.info(
                            "[智能助手·流式] 股票 %s 数据不充分，拦截（缺失: %s）",
                            stock_code_stream, ", ".join(missing_parts_s)
                        )
                        reply_text = (
                            f"📊 股票 {stock_code_stream} 的数据不充分，无法进行分析\n\n"
                            f"当前数据同步状态：\n{available_text_s}\n\n"
                            f"缺失的数据：\n{missing_text_s}\n\n"
                            f"请先同步数据后再提问：\n"
                            f"• 前往「数据管理」页面，搜索 {stock_code_stream} 并触发数据同步\n"
                            f"• 建议同步完整的历史行情（至少 250 个交易日）和财务数据\n"
                            f"• 同步完成后再次提问，我会调用工具获取真实数据为您分析\n\n"
                            f"或者，如果您只是想了解互联网公开信息，我也可以通过 web_search 搜索。"
                            f"是否需要我搜索？"
                        )
                        yield _sse("token", {"content": reply_text})
                        yield _sse("done", {"tools_used": ["get_data_sync_status"]})
                        return

        knowledge_snippets = ""
        try:
            from core.knowledge import FinancialKnowledgeManager
            km = FinancialKnowledgeManager(db=self._db)
            knowledge_snippets = km.retrieve_for_prompt(resolved_user_message)
        except Exception:
            pass

        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=_get_system_prompt(
                    knowledge_snippets, assistant_settings,
                    is_im=is_im, user_profile=user_profile,
                    current_topic_title=current_topic_title,
                    memory_block=memory_block,
                    assistant_role=self._assistant_role,
                    user_context=self._user_context,
                ),
            ),
        ]
        if history_messages:
            messages.extend(history_messages)
        messages.append(Message(role=MessageRole.USER, content=resolved_user_message.strip()))

        tools_used: List[str] = []
        tool_results: List[Dict[str, Any]] = []
        event_queue: asyncio.Queue = asyncio.Queue()

        async def _progress(payload):
            await event_queue.put(payload)

        async def _do_chat():
            nonlocal tools_used
            tool_interceptor = self._build_tool_interceptor(conversation_id or "default")
            resp = await self._llm_client.achat(
                messages,
                tools=self._openai_tools,
                auto_execute_tools=True,
                max_tool_rounds=8,
                tools_used=tools_used,
                tool_results_collector=tool_results,
                dry_run=False,
                progress_callback=_progress,
                tool_interceptor=tool_interceptor,
            )
            await _record_assistant_token_usage(resp, conversation_id or "assistant_chat_stream")
            if not tools_used and _should_force_tool_retry(resolved_user_message):
                logger.warning("[智能助手·流式] 首轮未调用工具，触发工具重试兜底")
                retry_messages = list(messages)
                retry_messages.append(Message(
                    role=MessageRole.USER,
                    content=(
                        "请不要直接根据上下文猜测或编造结果。"
                        "这类问题必须先调用相关工具获取真实数据，再基于工具返回回答。"
                        "尤其不能直接编造指数点位、涨跌幅、MACD、RSI、均线、成交额等实时数字。"
                        "如果工具返回为空或日期不匹配，再明确说明数据为空或数据日期不匹配。"
                    ),
                ))
                try:
                    resp = await self._llm_client.achat(
                        retry_messages,
                        tools=self._openai_tools,
                        auto_execute_tools=True,
                        max_tool_rounds=8,
                        tools_used=tools_used,
                        tool_results_collector=tool_results,
                        dry_run=False,
                        progress_callback=_progress,
                        tool_choice="required",
                        tool_interceptor=tool_interceptor,
                    )
                    await _record_assistant_token_usage(resp, conversation_id or "assistant_chat_stream")
                except Exception:
                    resp = await self._llm_client.achat(
                        retry_messages,
                        tools=self._openai_tools,
                        auto_execute_tools=True,
                        max_tool_rounds=8,
                        tools_used=tools_used,
                        tool_results_collector=tool_results,
                        dry_run=False,
                        progress_callback=_progress,
                        tool_interceptor=tool_interceptor,
                    )
                    await _record_assistant_token_usage(resp, conversation_id or "assistant_chat_stream")
            return resp.content

        def _stream_effective_timeout() -> int:
            base = ASSISTANT_TIMEOUT_SECONDS
            if not tools_used:
                return base
            try:
                from core.tools import get_tool_registry
                from core.tools.config import ToolTimeoutTier
                registry = get_tool_registry()
                for name in tools_used:
                    meta = registry.get(name)
                    if meta and getattr(meta, "timeout_tier", "") == ToolTimeoutTier.HEAVY:
                        return base + ASSISTANT_HEAVY_TOOL_EXTRA_SECONDS
            except Exception:
                pass
            return base

        task = asyncio.create_task(
            asyncio.wait_for(_do_chat(), timeout=_stream_effective_timeout())
        )

        try:
            while not task.done():
                try:
                    payload = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    yield _sse(payload.get("event", "progress"), payload)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

            while not event_queue.empty():
                payload = event_queue.get_nowait()
                yield _sse(payload.get("event", "progress"), payload)

            content = task.result()
            reply = content or "抱歉，暂时无法生成回答，请稍后再试。"

            # 回复后验证（与非流式一致）：编造工具JSON / 伪造工具痕迹 / 未调工具大量数字
            if _has_fabricated_tool_json(reply):
                logger.warning("[智能助手·流式] 检测到编造的工具JSON结果，硬拦截回复")
                reply = (
                    "抱歉，我在呈现工具返回结果时出现了格式错误（把工具返回改写成了结构化数据），"
                    "这可能导致数据失真。\n\n"
                    "请重新提问，我会严格按工具返回的原始内容为您呈现分析结果。"
                )
            elif _has_fabricated_tool_refs(reply, tools_used):
                logger.warning("[智能助手·流式] 检测到伪造工具调用痕迹，拦截回复（tools_used=%s）", tools_used)
                reply = (
                    "抱歉，我在生成回复时出现了数据来源标注错误。\n\n"
                    "为确保您获取的信息真实可靠，请尝试将问题拆分得更具体一些，"
                    "例如直接指定想查看的数据维度（如\"查一下牧原股份最新财报\"\"看技术指标\"等），"
                    "我会调用对应工具获取真实数据后为您分析。"
                )
            elif _has_unsourced_numbers(reply, tools_used):
                logger.warning("[智能助手·流式] 检测到未调工具但回复含大量数字，拦截回复")
                reply = (
                    "抱歉，我目前未能通过工具获取到与您问题相关的实时数据，无法提供有数据支撑的分析。\n\n"
                    "可能的原因：数据库中的股票数据尚未同步完整。\n"
                    "建议您：\n"
                    "• 在\"数据管理\"页面同步该股票的基础数据和历史行情\n"
                    "• 同步完成后再次提问，我会调用工具获取真实数据为您分析\n"
                    "• 或尝试通过 web_search 搜索互联网公开信息"
                )
            elif _has_untraced_risky_numbers(
                reply, tool_results, tools_used,
                resolved_user_message,
                _extract_history_tool_contents(messages),
            ):
                logger.warning("[智能助手·流式] 检测到无法溯源的高风险数字（疑似训练记忆填充/单位换算错误），拦截回复")
                untraced_detail = "、".join(_get_untraced_risky_numbers(
                    reply, tool_results, resolved_user_message,
                    _extract_history_tool_contents(messages))[:6])
                reply = (
                    "抱歉，我在刚才的回复中引用了一些工具和搜索结果里都没有的具体数字"
                    f"（如 {untraced_detail}），这类数字可能来自过时的记忆而非实时数据，"
                    "继续呈现会误导您的判断，因此已整段拦截。\n\n"
                    "常见原因：搜索结果只有标题/链接/摘要，未包含具体数值"
                    "（如行业成本数据多在付费研报正文中，搜索引擎摘要抓不到）。\n"
                    "您可以：\n"
                    "• 换更具体的关键词让我再搜索（如\"牧原股份 7月成本 公告\"）\n"
                    "• 让我引用搜索到的来源链接，由您人工查看原文\n"
                    "• 只让我分析工具已返回的真实数据\n"
                )

            CHUNK_SIZE = 40
            for i in range(0, len(reply), CHUNK_SIZE):
                yield _sse("token", {"content": reply[i:i + CHUNK_SIZE]})
                await asyncio.sleep(0.015)

            yield _sse("done", {"tools_used": tools_used})
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
            yield _sse("error", {"message": "请求已取消"})
            yield _sse("done", {"tools_used": tools_used, "error": True})
        except asyncio.TimeoutError:
            timeout_used = _stream_effective_timeout()
            logger.warning(f"[智能助手·流式] 请求超时（{timeout_used}s）")
            yield _sse("error", {"message": f"处理超时（已超过 {timeout_used} 秒），请尝试更简短的问题。"})
            yield _sse("done", {"tools_used": tools_used, "error": True})
        except Exception as e:
            logger.exception("[智能助手·流式] 对话失败")
            yield _sse("error", {"message": f"处理请求时发生错误：{str(e)}"})
            yield _sse("done", {"tools_used": tools_used, "error": True})


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_thread_id() -> str:
    return f"thr_{uuid.uuid4().hex[:12]}"


def _normalize_thread_title(title: str) -> str:
    text = (title or "").strip().lower()
    if not text:
        return ""

    replacements = {
        "新能源汽车": "新能源车",
        "新能源汽車": "新能源车",
        "个股": "公司",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    for token in ["（", "）", "(", ")", "-", "_", " ", "　", "/", "\\", "·", "、"]:
        text = text.replace(token, "")

    removable_suffixes = [
        "研究主题",
        "产业链研究",
        "行业研究",
        "板块研究",
        "公司研究",
        "个股研究",
        "深度研究",
        "专题研究",
        "课题研究",
        "产业链",
        "行业",
        "板块",
        "研究",
        "分析",
        "跟踪",
        "专题",
        "主题",
    ]
    changed = True
    while changed and len(text) > 2:
        changed = False
        for suffix in removable_suffixes:
            if text.endswith(suffix) and len(text) > len(suffix) + 1:
                text = text[: -len(suffix)]
                changed = True
                break

    return text


def _thread_titles_match(first: str, second: str) -> bool:
    normalized_first = _normalize_thread_title(first)
    normalized_second = _normalize_thread_title(second)
    if not normalized_first or not normalized_second:
        return False
    return normalized_first == normalized_second


def _find_similar_thread(
    docs: List[Dict[str, Any]],
    title: str,
    parent_thread_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    normalized_parent_id = (parent_thread_id or "").strip() or None
    candidates = [
        doc for doc in docs
        if (doc.get("parent_thread_id") or None) == normalized_parent_id
    ]
    for doc in candidates:
        if _thread_titles_match(doc.get("title") or "", title):
            return doc
    return None


def _is_external_session_thread_id(thread_id: Optional[str]) -> bool:
    return bool(thread_id and ":" in thread_id)


def _is_visible_assistant_topic(doc: Dict[str, Any]) -> bool:
    if doc.get("archived") is True:
        return False
    if (doc.get("topic_type") or "") == "im_session":
        return False
    return not _is_external_session_thread_id(doc.get("thread_id"))


def _sanitize_thread_summary(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not summary:
        return None

    abstract = str(summary.get("abstract") or "").strip()
    confirmed_facts = summary.get("confirmed_facts") or []
    open_questions = summary.get("open_questions") or []
    next_actions = summary.get("next_actions") or []
    focus_score = float(summary.get("focus_score") or 0.0)

    # 历史坏数据特征：只有 abstract，被 assistant 原文切片覆盖，且仍保留初始化占位值。
    if (
        abstract
        and not confirmed_facts
        and not open_questions
        and not next_actions
        and focus_score <= 0
        and (
            "##" in abstract
            or "|" in abstract
            or "---" in abstract
            or "**" in abstract
            or len(abstract) > 100
        )
    ):
        return None

    return {
        "abstract": abstract,
        "confirmed_facts": confirmed_facts,
        "open_questions": open_questions,
        "next_actions": next_actions,
        "focus_score": focus_score,
    }


def _thread_doc_to_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    summary = _sanitize_thread_summary(doc.get("current_summary") or {})
    updated_at = doc.get("updated_at")
    if isinstance(updated_at, datetime):
        updated_at = updated_at.isoformat()
    report_refs = []
    for ref in doc.get("report_refs") or []:
        created_at = ref.get("created_at")
        linked_at = ref.get("linked_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        if isinstance(linked_at, datetime):
            linked_at = linked_at.isoformat()
        report_refs.append({
            "ref_type": ref.get("ref_type") or "unknown",
            "report_key": ref.get("report_key") or "",
            "source_collection": ref.get("source_collection") or "",
            "title": ref.get("title") or "未命名报告",
            "symbol": ref.get("symbol") or None,
            "summary": ref.get("summary") or "",
            "status": ref.get("status") or None,
            "task_id": ref.get("task_id") or None,
            "analysis_id": ref.get("analysis_id") or None,
            "created_at": created_at,
            "linked_at": linked_at,
        })
    return {
        "thread_id": doc.get("thread_id", ASSISTANT_DEFAULT_THREAD_ID),
        "title": doc.get("title") or "默认主题",
        "parent_thread_id": doc.get("parent_thread_id"),
        "topic_type": doc.get("topic_type") or "general",
        "pinned": bool(doc.get("pinned", False)),
        "archived": bool(doc.get("archived", False)),
        "message_count": int(doc.get("message_count", 0)),
        "last_user_message": doc.get("last_user_message", ""),
        "updated_at": updated_at,
        "report_refs": report_refs,
        "current_summary": {
            "abstract": summary.get("abstract") or "",
            "confirmed_facts": summary.get("confirmed_facts") or [],
            "open_questions": summary.get("open_questions") or [],
            "next_actions": summary.get("next_actions") or [],
            "focus_score": float(summary.get("focus_score") or 0.0),
        } if summary else None,
    }


def serialize_assistant_report_ref(ref: Dict[str, Any]) -> Dict[str, Any]:
    created_at = ref.get("created_at")
    linked_at = ref.get("linked_at")
    return {
        "ref_type": ref.get("ref_type") or "unknown",
        "report_key": ref.get("report_key") or "",
        "source_collection": ref.get("source_collection") or "",
        "title": ref.get("title") or "未命名报告",
        "symbol": ref.get("symbol") or None,
        "summary": ref.get("summary") or "",
        "status": ref.get("status") or None,
        "task_id": ref.get("task_id") or None,
        "analysis_id": ref.get("analysis_id") or None,
        "created_at": _to_iso_datetime(created_at),
        "linked_at": _to_iso_datetime(linked_at),
    }


def _normalize_summary_items(items: List[str], limit: int = 3) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for item in items:
        text = (item or "").strip().replace("\n", " ")
        if not text:
            continue
        text = text[:120]
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_report_ref_item(report_ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ref_type = (report_ref.get("ref_type") or "").strip()
    report_key = (report_ref.get("report_key") or report_ref.get("task_id") or report_ref.get("analysis_id") or "").strip()
    if not ref_type or not report_key:
        return None

    now = _now_utc()
    created_at = report_ref.get("created_at")
    if not isinstance(created_at, datetime):
        created_at = now

    return {
        "ref_type": ref_type,
        "report_key": report_key,
        "source_collection": (report_ref.get("source_collection") or "").strip(),
        "title": (report_ref.get("title") or "未命名报告").strip(),
        "symbol": (report_ref.get("symbol") or "").strip() or None,
        "summary": (report_ref.get("summary") or "").strip()[:600],
        "status": (report_ref.get("status") or "").strip() or None,
        "task_id": (report_ref.get("task_id") or "").strip() or None,
        "analysis_id": (report_ref.get("analysis_id") or "").strip() or None,
        "created_at": created_at,
        "linked_at": now,
    }


async def attach_report_ref_to_thread(
    db,
    user_id: str,
    thread_id: Optional[str],
    report_ref: Dict[str, Any],
) -> bool:
    normalized_thread_id = (thread_id or "").strip()
    if not normalized_thread_id or _is_external_session_thread_id(normalized_thread_id):
        return False

    normalized_ref = _normalize_report_ref_item(report_ref)
    if not normalized_ref:
        return False

    thread = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": normalized_thread_id,
        "archived": {"$ne": True},
    })
    if not thread or (thread.get("topic_type") or "") == "im_session":
        return False

    existing_refs = thread.get("report_refs") or []
    merged_refs = [
        ref for ref in existing_refs
        if not (
            (ref.get("ref_type") or "") == normalized_ref["ref_type"]
            and (ref.get("report_key") or "") == normalized_ref["report_key"]
        )
    ]
    merged_refs.insert(0, normalized_ref)
    merged_refs = merged_refs[:ASSISTANT_MAX_REPORT_REFS]

    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": normalized_thread_id},
        {
            "$set": {
                "report_refs": merged_refs,
                "updated_at": _now_utc(),
            }
        },
    )
    return True


async def resolve_thread_for_report_writeback(
    db,
    user_id: str,
    preferred_thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_thread_id = (preferred_thread_id or "").strip()
    if normalized_thread_id and not _is_external_session_thread_id(normalized_thread_id):
        thread = await db.assistant_threads.find_one({
            "user_id": user_id,
            "thread_id": normalized_thread_id,
            "archived": {"$ne": True},
        })
        if thread and (thread.get("topic_type") or "") != "im_session":
            return thread

    fallback_thread = await create_assistant_thread(
        db,
        user_id=user_id,
        title=ASSISTANT_REPORT_INBOX_TITLE,
        parent_thread_id=None,
    )
    thread = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": fallback_thread["thread_id"],
        "archived": {"$ne": True},
    })
    return thread or fallback_thread


async def write_report_back_to_assistant_thread(
    db,
    user_id: str,
    report_ref: Dict[str, Any],
    preferred_thread_id: Optional[str] = None,
    summary_message: Optional[str] = None,
) -> Optional[str]:
    target_thread = await resolve_thread_for_report_writeback(db, user_id, preferred_thread_id)
    if not target_thread:
        return None

    target_thread_id = target_thread.get("thread_id")
    attached = await attach_report_ref_to_thread(db, user_id, target_thread_id, report_ref)
    if not attached:
        return None

    text = (summary_message or "").strip()
    if text:
        await append_assistant_message(
            db,
            user_id=user_id,
            role="assistant",
            content=text,
            conversation_id=target_thread_id,
            tools_used=["report_writeback"],
        )
        await summarize_assistant_thread(
            db,
            user_id=user_id,
            conversation_id=target_thread_id,
            summary_type="report_writeback",
        )

    return target_thread_id


def _to_iso_datetime(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or "").strip()
    return text or None


def _build_stock_report_detail_content(task: Any) -> str:
    result = task.result or {}
    symbol = task.task_params.get("symbol", "未知") if task.task_params else "未知"
    lines = [f"# {symbol} 分析报告"]

    recommendation = result.get("recommendation")
    if recommendation:
        lines.append(f"\n## 投资建议\n{recommendation}")

    summary = result.get("summary") or result.get("executive_summary")
    if summary:
        lines.append(f"\n## 摘要\n{summary}")

    decision = result.get("decision") or {}
    if decision:
        decision_lines: List[str] = []
        if decision.get("action"):
            decision_lines.append(f"- 操作观点: {decision['action']}")
        if decision.get("confidence") is not None:
            decision_lines.append(f"- 置信度: {decision['confidence']}")
        if decision.get("risk_score") is not None:
            decision_lines.append(f"- 风险分: {decision['risk_score']}")
        reasoning = decision.get("reasoning")
        if reasoning:
            decision_lines.append(f"- 决策依据: {reasoning}")
        if decision_lines:
            lines.append("\n## 决策信息\n" + "\n".join(decision_lines))

    key_points = result.get("key_points") or []
    if key_points:
        lines.append("\n## 关键要点\n" + "\n".join(f"- {item}" for item in key_points[:8]))

    reports = result.get("reports") or {}
    if reports:
        lines.append("\n## 分析师摘录")
        for key, text in reports.items():
            cleaned = str(text or "").strip()
            if not cleaned:
                continue
            lines.append(f"\n### {key}\n{cleaned[:1500]}")

    lines.append(f"\n---\n任务ID: {task.task_id}")
    return "\n".join(lines)


def _build_stock_report_detail_content_from_doc(report_doc: Dict[str, Any]) -> str:
    stock_symbol = (report_doc.get("stock_symbol") or "未知").strip() or "未知"
    stock_name = (report_doc.get("stock_name") or "").strip()
    title = f"{stock_name}({stock_symbol})" if stock_name else stock_symbol
    lines = [f"# {title} 分析报告"]

    recommendation = str(report_doc.get("recommendation") or "").strip()
    if recommendation:
        lines.append(f"\n## 投资建议\n{recommendation}")

    summary = str(report_doc.get("summary") or "").strip()
    if summary:
        lines.append(f"\n## 摘要\n{summary}")

    decision = report_doc.get("decision") or {}
    if isinstance(decision, dict) and decision:
        decision_lines: List[str] = []
        if decision.get("action"):
            decision_lines.append(f"- 操作观点: {decision['action']}")
        if decision.get("confidence") is not None:
            decision_lines.append(f"- 置信度: {decision['confidence']}")
        if decision.get("risk_score") is not None:
            decision_lines.append(f"- 风险分: {decision['risk_score']}")
        reasoning = decision.get("reasoning")
        if reasoning:
            decision_lines.append(f"- 决策依据: {reasoning}")
        if decision_lines:
            lines.append("\n## 决策信息\n" + "\n".join(decision_lines))

    key_points = report_doc.get("key_points") or []
    if key_points:
        lines.append("\n## 关键要点\n" + "\n".join(f"- {item}" for item in key_points[:8]))

    reports = report_doc.get("reports") or {}
    if isinstance(reports, dict) and reports:
        lines.append("\n## 分析师摘录")
        for key, text in reports.items():
            cleaned = str(text or "").strip()
            if not cleaned:
                continue
            lines.append(f"\n### {key}\n{cleaned[:1500]}")

    if report_doc.get("analysis_id"):
        lines.append(f"\n---\n分析ID: {report_doc['analysis_id']}")
    if report_doc.get("task_id"):
        lines.append(f"任务ID: {report_doc['task_id']}")
    return "\n".join(lines)


def _build_position_report_detail_content(report: Dict[str, Any]) -> str:
    code = report.get("code") or "未知"
    name = report.get("name") or code
    lines = [f"# {name}({code}) 持仓分析报告"]

    status = report.get("status")
    action = report.get("action")
    confidence = report.get("confidence")
    meta: List[str] = []
    if status:
        meta.append(f"- 状态: {status}")
    if action:
        meta.append(f"- 研究观察: {action}")
    if confidence is not None:
        meta.append(f"- 置信度: {confidence}")
    if meta:
        lines.append("\n## 核心结论\n" + "\n".join(meta))

    summary = report.get("summary") or {}
    summary_lines: List[str] = []
    if summary.get("quantity") is not None:
        summary_lines.append(f"- 持仓数量: {summary['quantity']}")
    if summary.get("cost_price") is not None:
        summary_lines.append(f"- 成本价: {summary['cost_price']}")
    if summary.get("current_price") is not None:
        summary_lines.append(f"- 当前价: {summary['current_price']}")
    if summary.get("unrealized_pnl") is not None:
        summary_lines.append(f"- 浮动盈亏: {summary['unrealized_pnl']}")
    if summary.get("unrealized_pnl_pct") is not None:
        summary_lines.append(f"- 盈亏比例: {summary['unrealized_pnl_pct']}%")
    if summary_lines:
        lines.append("\n## 持仓概览\n" + "\n".join(summary_lines))

    targets = report.get("price_targets") or {}
    target_lines: List[str] = []
    for label, key in (("关键验证价位", "target_price"), ("风险关注价格", "stop_loss"), ("收益关注价格", "take_profit_price")):
        if targets.get(key) is not None:
            target_lines.append(f"- {label}: {targets[key]}")
    if target_lines:
        lines.append("\n## 关键价位\n" + "\n".join(target_lines))

    action_reason = str(report.get("action_reason") or "").strip()
    if action_reason:
        lines.append(f"\n## 分析详情\n{action_reason}")

    detailed = str(report.get("detailed_analysis") or "").strip()
    if detailed:
        lines.append(f"\n## 详细分析\n{detailed}")

    analysis_id = report.get("analysis_id")
    if analysis_id:
        lines.append(f"\n---\n分析ID: {analysis_id}")
    return "\n".join(lines)


def _build_review_report_detail_content(review_data: Dict[str, Any]) -> str:
    """将交易复盘报告数据构建为 Markdown 详情内容。"""
    trade_info = review_data.get("trade_info") or {}
    code = trade_info.get("code") or "未知"
    name = trade_info.get("name") or code
    lines = [f"# {name}({code}) 交易复盘报告"]

    status = review_data.get("status")
    execution_time = review_data.get("execution_time")
    meta: List[str] = []
    if status:
        meta.append(f"- 状态: {status}")
    if execution_time is not None:
        meta.append(f"- 执行耗时: {execution_time:.1f}s")
    source = review_data.get("source")
    if source:
        meta.append(f"- 来源: {'实盘' if source == 'position' else '模拟'}")
    if meta:
        lines.append("\n## 核心信息\n" + "\n".join(meta))

    # 交易概览
    summary_lines: List[str] = []
    if trade_info.get("code"):
        summary_lines.append(f"- 股票代码: {trade_info['code']}")
    if trade_info.get("name"):
        summary_lines.append(f"- 股票名称: {trade_info['name']}")
    if trade_info.get("realized_pnl") is not None:
        summary_lines.append(f"- 实现盈亏: {trade_info['realized_pnl']}")
    if trade_info.get("remaining_quantity") is not None:
        summary_lines.append(f"- 剩余持仓: {trade_info['remaining_quantity']} 股")
    if summary_lines:
        lines.append("\n## 交易概览\n" + "\n".join(summary_lines))

    # AI 复盘内容
    ai_review = review_data.get("ai_review") or {}
    if ai_review.get("summary"):
        lines.append(f"\n## 复盘结论\n{ai_review['summary']}")
    if ai_review.get("strengths"):
        lines.append("\n## 做得好的地方\n" + "\n".join(f"- {s}" for s in ai_review["strengths"]))
    if ai_review.get("weaknesses"):
        lines.append("\n## 需要改进的地方\n" + "\n".join(f"- {w}" for w in ai_review["weaknesses"]))
    if ai_review.get("suggestions"):
        lines.append("\n## 后续观察点\n" + "\n".join(f"- {s}" for s in ai_review["suggestions"]))
    if ai_review.get("plan_deviation"):
        lines.append(f"\n## 计划偏离\n{ai_review['plan_deviation']}")

    review_id = review_data.get("review_id")
    if review_id:
        lines.append(f"\n---\n复盘ID: {review_id}")
    return "\n".join(lines)


async def get_assistant_thread_report_detail(
    db,
    user_id: str,
    thread_id: str,
    ref_type: str,
    report_key: str,
) -> Dict[str, Any]:
    thread = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": thread_id,
        "archived": {"$ne": True},
    })
    if not thread:
        raise ValueError("主题不存在或已删除")

    target_ref = None
    for ref in thread.get("report_refs") or []:
        if (ref.get("ref_type") or "") == ref_type and (ref.get("report_key") or "") == report_key:
            target_ref = ref
            break
    if not target_ref:
        raise ValueError("当前主题下未找到对应的关联报告")

    detail = {
        "ref_type": target_ref.get("ref_type") or ref_type,
        "report_key": target_ref.get("report_key") or report_key,
        "title": target_ref.get("title") or "未命名报告",
        "symbol": target_ref.get("symbol") or None,
        "status": target_ref.get("status") or None,
        "task_id": target_ref.get("task_id") or None,
        "analysis_id": target_ref.get("analysis_id") or None,
        "created_at": _to_iso_datetime(target_ref.get("created_at")),
        "linked_at": _to_iso_datetime(target_ref.get("linked_at")),
        "content": (target_ref.get("summary") or "").strip(),
        "content_format": "markdown",
    }

    if ref_type == "stock_report":
        from app.services.task_analysis_service import get_task_analysis_service

        task_id = (target_ref.get("task_id") or report_key or "").strip()
        task = await get_task_analysis_service().get_task(task_id) if task_id else None
        if task and str(task.user_id) == str(user_id):
            detail["status"] = str(task.status)
            detail["created_at"] = _to_iso_datetime(task.created_at)
            detail["content"] = _build_stock_report_detail_content(task)
            return detail

        analysis_key = (target_ref.get("analysis_id") or report_key or task_id or "").strip()
        report_doc = await db.analysis_reports.find_one(_build_analysis_report_lookup_query(user_id, analysis_key))
        if not report_doc:
            raise ValueError("原始报告不存在或已被删除")
        detail["status"] = report_doc.get("status") or detail["status"]
        detail["task_id"] = report_doc.get("task_id") or detail["task_id"]
        detail["analysis_id"] = report_doc.get("analysis_id") or detail["analysis_id"]
        detail["created_at"] = _to_iso_datetime(report_doc.get("created_at"))
        detail["content"] = _build_stock_report_detail_content_from_doc(report_doc)
        return detail

    if ref_type == "position_report":
        from app.services.portfolio_service import get_portfolio_service

        analysis_id = (target_ref.get("analysis_id") or report_key or "").strip()
        report = await get_portfolio_service().get_position_analysis_by_id(user_id, analysis_id)
        if not report:
            raise ValueError("原始持仓报告不存在或已被删除")
        detail["created_at"] = _to_iso_datetime(report.get("created_at"))
        detail["content"] = _build_position_report_detail_content(report)
        detail["status"] = report.get("status") or detail["status"]
        return detail

    if ref_type == "review_report":
        from app.services.trade_review_service import TradeReviewService

        review_id = (target_ref.get("task_id") or report_key or "").strip()
        service = TradeReviewService()
        review = await service.get_review_detail(user_id, review_id)
        if not review:
            raise ValueError("原始交易复盘报告不存在或已被删除")
        review_data = review.model_dump() if hasattr(review, "model_dump") else dict(review)
        detail["created_at"] = _to_iso_datetime(review_data.get("created_at"))
        detail["status"] = review_data.get("status") or detail["status"]
        detail["content"] = _build_review_report_detail_content(review_data)
        return detail

    if ref_type == "position_task":
        task_id = (target_ref.get("task_id") or report_key or "").strip()
        task_doc = await db.unified_analysis_tasks.find_one({"task_id": task_id})
        if not task_doc:
            raise ValueError("原始任务不存在或已被删除")
        if str(task_doc.get("user_id")) != str(user_id):
            raise ValueError("无权访问该任务")

        result = task_doc.get("result") or {}
        analysis_id = (result.get("analysis_id") or target_ref.get("analysis_id") or "").strip()
        if analysis_id:
            from app.services.portfolio_service import get_portfolio_service

            report = await get_portfolio_service().get_position_analysis_by_id(user_id, analysis_id)
            if report:
                detail["analysis_id"] = analysis_id
                detail["created_at"] = _to_iso_datetime(report.get("created_at"))
                detail["status"] = report.get("status") or detail["status"]
                detail["content"] = _build_position_report_detail_content(report)
                return detail

        status = task_doc.get("status") or detail["status"] or "unknown"
        detail["status"] = str(status)
        detail["created_at"] = _to_iso_datetime(task_doc.get("created_at"))
        detail["content"] = (
            f"# {detail['title']}\n\n"
            f"- 任务状态: {status}\n"
            f"- 任务ID: {task_id}\n\n"
            f"{(target_ref.get('summary') or '该任务尚未生成完整报告，后续完成后可在这里查看。').strip()}"
        )
        return detail

    return detail


def _build_stock_report_ref_from_task(task: Any, stock_name: Optional[str] = None) -> Dict[str, Any]:
    result = task.result or {}
    task_params = task.task_params or {}
    symbol = (task_params.get("symbol") or "").strip()
    display_name = (stock_name or "").strip()
    title_prefix = f"{display_name}({symbol})" if display_name and symbol else display_name or symbol or "未知标的"
    return {
        "ref_type": "stock_report",
        "report_key": task.task_id,
        "source_collection": "unified_analysis_tasks",
        "title": f"{title_prefix} 分析报告",
        "symbol": symbol or None,
        "summary": ((result.get("summary") or result.get("recommendation") or "")[:400]).strip(),
        "status": str(task.status),
        "task_id": task.task_id,
        "created_at": getattr(task, "created_at", None),
    }


def _build_stock_report_ref_from_analysis_doc(report_doc: Dict[str, Any]) -> Dict[str, Any]:
    stock_symbol = (report_doc.get("stock_symbol") or "").strip()
    stock_name = (report_doc.get("stock_name") or "").strip()
    title_prefix = f"{stock_name}({stock_symbol})" if stock_name and stock_symbol else stock_name or stock_symbol or "未知标的"
    report_key = (report_doc.get("task_id") or report_doc.get("analysis_id") or str(report_doc.get("_id") or "")).strip()
    return {
        "ref_type": "stock_report",
        "report_key": report_key,
        "source_collection": "analysis_reports",
        "title": f"{title_prefix} 分析报告",
        "symbol": stock_symbol or None,
        "summary": ((report_doc.get("summary") or report_doc.get("recommendation") or "")[:400]).strip(),
        "status": report_doc.get("status") or "completed",
        "task_id": (report_doc.get("task_id") or "").strip() or None,
        "analysis_id": (report_doc.get("analysis_id") or "").strip() or None,
        "created_at": report_doc.get("created_at"),
    }


def _build_analysis_report_lookup_query(user_id: str, report_key: str) -> Dict[str, Any]:
    report_query = {
        "$or": [
            {"task_id": report_key},
            {"analysis_id": report_key},
        ]
    }
    if ObjectId.is_valid(report_key):
        report_query["$or"].append({"_id": ObjectId(report_key)})

    return {
        "$and": [
            {"$or": [{"user_id": user_id}, {"user_id": str(user_id)}]},
            report_query,
        ]
    }


def _build_position_report_ref_from_report(report: Dict[str, Any]) -> Dict[str, Any]:
    code = (report.get("code") or "").strip()
    name = (report.get("name") or "").strip()
    title_prefix = f"{name}({code})" if name and code else name or code or "未知持仓"
    return {
        "ref_type": "position_report",
        "report_key": report.get("analysis_id") or "",
        "source_collection": "position_analysis_reports",
        "title": f"{title_prefix} 持仓分析",
        "symbol": code or None,
        "summary": ((report.get("summary") or report.get("action_reason") or "")[:400]).strip(),
        "status": report.get("status") or None,
        "analysis_id": report.get("analysis_id") or None,
        "created_at": report.get("created_at"),
    }


def _build_review_report_ref_from_review(review: Any) -> Dict[str, Any]:
    """从交易复盘报告对象构建主题关联引用。

    兼容 TradeReviewReport 对象(Pydantic) 和字典两种形式。
    """
    if hasattr(review, "model_dump"):
        data = review.model_dump()
    elif hasattr(review, "dict"):
        data = review.dict()
    else:
        data = dict(review)

    trade_info = data.get("trade_info") or {}
    code = (trade_info.get("code") or "").strip()
    name = (trade_info.get("name") or "").strip()
    title_prefix = f"{name}({code})" if name and code else name or code or "未知标的"

    ai_review = data.get("ai_review") or {}
    summary_text = (ai_review.get("summary") or "").strip()

    return {
        "ref_type": "review_report",
        "report_key": data.get("review_id") or data.get("task_id") or "",
        "source_collection": "trade_reviews",
        "title": f"{title_prefix} 交易复盘",
        "symbol": code or None,
        "summary": summary_text[:600],
        "status": data.get("status") or "completed",
        "task_id": data.get("review_id") or data.get("task_id") or None,
        "created_at": data.get("created_at"),
    }


async def search_assistant_attachable_reports(
    db,
    user_id: str,
    thread_id: str,
    ref_type: str = "stock_report",
    keyword: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    thread = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": thread_id,
        "archived": {"$ne": True},
    })
    if not thread or (thread.get("topic_type") or "") == "im_session":
        raise ValueError("当前主题不存在或不支持关联报告")

    normalized_type = (ref_type or "stock_report").strip() or "stock_report"
    normalized_keyword = (keyword or "").strip()
    limit = max(1, min(limit, 20))

    if normalized_type == "position_report":
        from app.services.portfolio_service import get_portfolio_service

        query: Dict[str, Any] = {
            "user_id": user_id,
            "analysis_id": {"$exists": True, "$ne": ""},
        }
        if normalized_keyword:
            query["$or"] = [
                {"code": {"$regex": normalized_keyword, "$options": "i"}},
                {"name": {"$regex": normalized_keyword, "$options": "i"}},
                {"summary": {"$regex": normalized_keyword, "$options": "i"}},
                {"analysis_id": {"$regex": normalized_keyword, "$options": "i"}},
            ]

        docs = await db.position_analysis_reports.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
        service = get_portfolio_service()
        results: List[Dict[str, Any]] = []
        for doc in docs:
            analysis_id = (doc.get("analysis_id") or "").strip()
            if not analysis_id:
                continue
            report = await service.get_position_analysis_by_id(user_id, analysis_id)
            if not report:
                continue
            results.append(_normalize_report_ref_item(_build_position_report_ref_from_report(report)))
        return [item for item in results if item][:limit]

    if normalized_type == "review_report":
        # 交易复盘报告候选：从 trade_reviews 集合查询
        review_query: Dict[str, Any] = {
            "user_id": user_id,
        }
        if normalized_keyword:
            review_query["$or"] = [
                {"trade_info.code": {"$regex": normalized_keyword, "$options": "i"}},
                {"trade_info.name": {"$regex": normalized_keyword, "$options": "i"}},
                {"review_id": {"$regex": normalized_keyword, "$options": "i"}},
                {"ai_review.summary": {"$regex": normalized_keyword, "$options": "i"}},
            ]

        review_docs = await db["trade_reviews"].find(review_query).sort("created_at", -1).limit(limit).to_list(length=limit)
        review_results: List[Dict[str, Any]] = []
        from app.services.trade_review_service import TradeReviewService

        review_service = TradeReviewService()
        for doc in review_docs:
            review_id = (doc.get("review_id") or "").strip()
            if not review_id:
                continue
            review = await review_service.get_review_detail(user_id, review_id)
            if not review:
                continue
            ref = _normalize_report_ref_item(_build_review_report_ref_from_review(review))
            if ref:
                review_results.append(ref)
            if len(review_results) >= limit:
                break
        return review_results[:limit]

    from app.services.task_analysis_service import get_task_analysis_service

    service = get_task_analysis_service()
    results: List[Dict[str, Any]] = []
    seen_keys = set()

    if normalized_keyword:
        analysis_query: Dict[str, Any] = {
            "$and": [
                {"$or": [{"user_id": user_id}, {"user_id": str(user_id)}]},
                {
                    "$or": [
                        {"stock_symbol": {"$regex": normalized_keyword, "$options": "i"}},
                        {"stock_name": {"$regex": normalized_keyword, "$options": "i"}},
                        {"summary": {"$regex": normalized_keyword, "$options": "i"}},
                        {"analysis_id": {"$regex": normalized_keyword, "$options": "i"}},
                        {"task_id": {"$regex": normalized_keyword, "$options": "i"}},
                    ]
                },
            ]
        }
        analysis_docs = await db.analysis_reports.find(analysis_query).sort("created_at", -1).limit(limit * 3).to_list(length=limit * 3)
        for doc in analysis_docs:
            ref = _normalize_report_ref_item(_build_stock_report_ref_from_analysis_doc(doc))
            ref_key = (ref or {}).get("report_key") if ref else None
            if not ref_key or ref_key in seen_keys:
                continue
            if ref:
                results.append(ref)
                seen_keys.add(ref_key)
            if len(results) >= limit:
                return results[:limit]

    task_query: Dict[str, Any] = {
        "$and": [
            {"status": "completed"},
            {"$or": [{"user_id": user_id}, {"user_id": ObjectId(user_id)}]},
        ]
    }
    if normalized_keyword:
        task_query["$and"].append({
            "$or": [
                {"task_params.symbol": {"$regex": normalized_keyword, "$options": "i"}},
                {"result.summary": {"$regex": normalized_keyword, "$options": "i"}},
                {"result.recommendation": {"$regex": normalized_keyword, "$options": "i"}},
                {"task_id": {"$regex": normalized_keyword, "$options": "i"}},
            ]
        })

    task_docs = await db.unified_analysis_tasks.find(task_query).sort("created_at", -1).limit(limit * 2).to_list(length=limit * 2)
    for doc in task_docs:
        task_id = (doc.get("task_id") or "").strip()
        if not task_id or task_id in seen_keys:
            continue
        task = await service.get_task(task_id)
        if not task or str(task.user_id) != str(user_id) or str(task.status) != "completed":
            continue
        ref = _normalize_report_ref_item(_build_stock_report_ref_from_task(task))
        if ref:
            results.append(ref)
            seen_keys.add(task_id)
        if len(results) >= limit:
            break

    return results[:limit]


async def attach_existing_report_to_thread(
    db,
    user_id: str,
    thread_id: str,
    ref_type: str,
    report_key: str,
) -> Dict[str, Any]:
    normalized_type = (ref_type or "").strip()
    normalized_key = (report_key or "").strip()
    if not normalized_type or not normalized_key:
        raise ValueError("报告类型和报告标识不能为空")

    if normalized_type == "position_report":
        from app.services.portfolio_service import get_portfolio_service

        report = await get_portfolio_service().get_position_analysis_by_id(user_id, normalized_key)
        if not report:
            raise ValueError("未找到可关联的持仓报告")
        ref = _normalize_report_ref_item(_build_position_report_ref_from_report(report))
    elif normalized_type == "review_report":
        from app.services.trade_review_service import TradeReviewService

        service = TradeReviewService()
        review = await service.get_review_detail(user_id, normalized_key)
        if not review:
            raise ValueError("未找到可关联的交易复盘报告")
        ref = _normalize_report_ref_item(_build_review_report_ref_from_review(review))
    else:
        from app.services.task_analysis_service import get_task_analysis_service

        task = await get_task_analysis_service().get_task(normalized_key)
        if task and str(task.user_id) == str(user_id) and str(task.status) == "completed":
            ref = _normalize_report_ref_item(_build_stock_report_ref_from_task(task))
        else:
            report_doc = await db.analysis_reports.find_one(_build_analysis_report_lookup_query(user_id, normalized_key))
            if not report_doc:
                raise ValueError("未找到可关联的历史分析报告")
            ref = _normalize_report_ref_item(_build_stock_report_ref_from_analysis_doc(report_doc))

    if not ref:
        raise ValueError("报告信息不完整，无法关联")

    attached = await attach_report_ref_to_thread(db, user_id, thread_id, ref)
    if not attached:
        raise ValueError("当前主题不支持关联该报告")
    return ref


def _extract_sentences(text: str) -> List[str]:
    raw = (text or "").replace("\r", "\n")
    fragments: List[str] = []
    for chunk in raw.split("\n"):
        chunk = chunk.strip(" -•\t")
        if not chunk:
            continue
        parts = [part.strip() for part in chunk.replace("！", "。").replace("？", "。").split("。")]
        for part in parts:
            if part:
                fragments.append(part)
    return fragments


def _format_messages_for_summary(messages: List[Dict[str, Any]], limit: int = 12) -> str:
    formatted: List[str] = []
    for index, message in enumerate(messages[-limit:], start=1):
        role = str(message.get("role") or "assistant").strip() or "assistant"
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        content = re.sub(r"\s+", " ", content)
        formatted.append(f"{index}. [{role}] {content[:800]}")
    return "\n".join(formatted)


def _strip_json_code_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _load_summary_json(text: str) -> Dict[str, Any]:
    cleaned = _strip_json_code_fence(text)
    if not cleaned:
        raise ValueError("摘要模型返回为空")

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise ValueError("摘要模型返回的不是 JSON object")
    return data


def _normalize_thread_summary_payload(payload: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    abstract = str(payload.get("abstract") or "").strip()
    focus_score = payload.get("focus_score")
    try:
        focus_score = float(focus_score)
    except (TypeError, ValueError):
        focus_score = fallback.get("focus_score") or 0.0
    focus_score = max(0.0, min(round(float(focus_score), 2), 1.0))

    return {
        "abstract": abstract[:160] or fallback.get("abstract") or "当前主题尚未形成摘要",
        "confirmed_facts": _normalize_summary_items(payload.get("confirmed_facts") or fallback.get("confirmed_facts") or []),
        "open_questions": _normalize_summary_items(payload.get("open_questions") or fallback.get("open_questions") or []),
        "next_actions": _normalize_summary_items(payload.get("next_actions") or fallback.get("next_actions") or []),
        "focus_score": focus_score,
    }


async def _build_thread_summary_with_llm(
    db,
    messages: List[Dict[str, Any]],
    title: str = "",
) -> Dict[str, Any]:
    fallback = _build_thread_summary_from_messages(messages, title)
    transcript = _format_messages_for_summary(messages)
    if not transcript:
        return fallback

    try:
        llm_config = await get_coding_llm_config(db)
        if not llm_config:
            logger.warning("[智能助手摘要] 未找到可用 LLM 配置，回退规则摘要")
            return fallback

        summary_config = llm_config.model_copy(deep=True) if hasattr(llm_config, "model_copy") else llm_config.copy(deep=True)
        summary_config.temperature = 0.1
        summary_config.max_tokens = min(int(summary_config.max_tokens or 600), 600)
        summary_config.timeout = min(int(summary_config.timeout or 45), 45)

        client = UnifiedLLMClient.from_config(summary_config)
        messages_for_llm = [
            Message(
                role=MessageRole.SYSTEM,
                content=(
                    "你是研究主题摘要器。你的任务是为主题会话生成结构化摘要，供侧边栏和主题卡片展示。\n"
                    "必须只输出一个 JSON object，不要输出 markdown、代码块、解释、前后缀。\n"
                    "字段要求：\n"
                    "- abstract: 1-2 句中文摘要，40-90 字，突出当前结论或讨论焦点，不要复制大段原文，不要保留 markdown 标题、表格、分隔线。\n"
                    "- confirmed_facts: 1-3 条已被会话明确给出的事实，必须具体，不要写空话。\n"
                    "- open_questions: 0-3 条仍待回答的问题；如果问题已经回答，不要重复放进去。\n"
                    "- next_actions: 1-3 条下一步建议，必须贴合当前主题。\n"
                    "- focus_score: 0 到 1 之间的小数，表示当前主题是否聚焦。\n"
                    "如果信息不足，宁可简短，也不要抄录正文碎片。"
                ),
            ),
            Message(
                role=MessageRole.USER,
                content=(
                    f"主题标题: {title or '未命名主题'}\n"
                    "最近消息如下：\n"
                    f"{transcript}\n\n"
                    "请输出 JSON：\n"
                    "{\n"
                    '  "abstract": "",\n'
                    '  "confirmed_facts": [],\n'
                    '  "open_questions": [],\n'
                    '  "next_actions": [],\n'
                    '  "focus_score": 0.0\n'
                    "}"
                ),
            ),
        ]

        response = await client.achat(messages_for_llm)
        await _record_assistant_token_usage(response, "assistant_summary", analysis_type="assistant_summary")
        payload = _load_summary_json(response.content or "")
        summary = _normalize_thread_summary_payload(payload, fallback)
        logger.info("[智能助手摘要] 使用 LLM 生成结构化摘要成功")
        return summary
    except Exception as exc:
        logger.warning("[智能助手摘要] LLM 摘要生成失败，回退规则摘要: %s", exc)
        return fallback


def _build_thread_summary_from_messages(messages: List[Dict[str, Any]], title: str = "") -> Dict[str, Any]:
    user_messages = [m.get("content", "").strip() for m in messages if m.get("role") == "user" and m.get("content")]
    assistant_messages = [m.get("content", "").strip() for m in messages if m.get("role") == "assistant" and m.get("content")]

    latest_user = user_messages[-1] if user_messages else ""
    latest_assistant = assistant_messages[-1] if assistant_messages else ""
    abstract = latest_assistant[:160] or latest_user[:160] or (title[:160] if title else "") or "当前主题尚未形成摘要"

    confirmed_candidates: List[str] = []
    for content in reversed(assistant_messages[-4:]):
        confirmed_candidates.extend(_extract_sentences(content))

    question_candidates: List[str] = []
    for content in reversed(user_messages[-4:]):
        question_candidates.extend(_extract_sentences(content))

    next_actions: List[str] = []
    if latest_user:
        next_actions.append(f"围绕“{latest_user[:40]}”继续追问或补数")
    if latest_assistant:
        next_actions.append("结合当前结论继续细化估值、行业或风险主线")
    if not next_actions:
        next_actions.append("继续在当前主题下补充问题或触发深度分析")

    total_messages = len(messages)
    assistant_ratio = len(assistant_messages) / total_messages if total_messages else 0
    focus_score = 0.55
    if total_messages >= 4:
        focus_score += 0.1
    if total_messages >= 8:
        focus_score += 0.05
    if latest_user and title and any(token for token in title.split() if token and token in latest_user):
        focus_score += 0.1
    if assistant_ratio >= 0.4:
        focus_score += 0.1
    focus_score = min(round(focus_score, 2), 0.95)

    return {
        "abstract": abstract,
        "confirmed_facts": _normalize_summary_items(confirmed_candidates),
        "open_questions": _normalize_summary_items(question_candidates),
        "next_actions": _normalize_summary_items(next_actions),
        "focus_score": focus_score,
    }


async def _create_thread_document(
    db,
    user_id: str,
    thread_id: str,
    title: str,
    parent_thread_id: Optional[str] = None,
    topic_type: str = "general",
) -> Dict[str, Any]:
    now = _now_utc()
    doc = {
        "thread_id": thread_id,
        "user_id": user_id,
        "title": title,
        "parent_thread_id": parent_thread_id,
        "topic_type": topic_type,
        "pinned": thread_id == ASSISTANT_DEFAULT_THREAD_ID,
        "archived": False,
        "message_count": 0,
        "last_user_message": "",
        "report_refs": [],
        "current_summary": {
            "abstract": "",
            "confirmed_facts": [],
            "open_questions": [],
            "next_actions": [],
            "focus_score": 0.0,
        },
        "created_at": now,
        "updated_at": now,
    }
    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread_id},
        {"$setOnInsert": doc},
        upsert=True,
    )
    return await db.assistant_threads.find_one({"user_id": user_id, "thread_id": thread_id})


async def _migrate_legacy_conversation_if_needed(db, user_id: str, thread_id: str) -> None:
    if thread_id != ASSISTANT_DEFAULT_THREAD_ID:
        return

    message_count = await db.assistant_thread_messages.count_documents({
        "user_id": user_id,
        "thread_id": thread_id,
    })
    if message_count > 0:
        return

    legacy_doc = await db.assistant_conversations.find_one({"user_id": user_id})
    legacy_messages = (legacy_doc or {}).get("messages") or []
    if not legacy_messages:
        return

    now = _now_utc()
    payload = []
    last_user_message = ""
    for idx, message in enumerate(legacy_messages):
        content = (message.get("content") or "").strip()
        if not content:
            continue
        role = message.get("role") or "assistant"
        if role == "user":
            last_user_message = content
        payload.append({
            "message_id": f"legacy_{idx}_{uuid.uuid4().hex[:8]}",
            "thread_id": thread_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "tools_used": message.get("tools_used") or [],
            "created_at": now,
        })

    if not payload:
        return

    await db.assistant_thread_messages.insert_many(payload)
    abstract = ""
    for message in reversed(payload):
        if message["role"] == "assistant":
            abstract = message["content"][:120]
            break

    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread_id},
        {
            "$set": {
                "message_count": len(payload),
                "last_user_message": last_user_message,
                "current_summary": {
                    "abstract": abstract,
                    "confirmed_facts": [],
                    "open_questions": [],
                    "next_actions": [],
                    "focus_score": 0.5,
                },
                "updated_at": now,
            }
        },
    )


async def get_or_create_assistant_thread(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    thread_id = (conversation_id or ASSISTANT_DEFAULT_THREAD_ID).strip() if conversation_id else ASSISTANT_DEFAULT_THREAD_ID
    topic_type = "im_session" if _is_external_session_thread_id(thread_id) else "general"
    doc = await db.assistant_threads.find_one({"user_id": user_id, "thread_id": thread_id})
    if doc is None:
        title = "默认主题" if thread_id == ASSISTANT_DEFAULT_THREAD_ID else ("外部会话" if topic_type == "im_session" else f"新主题 {datetime.now().strftime('%m-%d %H:%M')}")
        doc = await _create_thread_document(db, user_id, thread_id, title, topic_type=topic_type)
    elif topic_type == "im_session" and doc.get("topic_type") != "im_session":
        await db.assistant_threads.update_one(
            {"user_id": user_id, "thread_id": thread_id},
            {
                "$set": {
                    "topic_type": "im_session",
                    "title": doc.get("title") or "外部会话",
                    "updated_at": _now_utc(),
                }
            },
        )
    await _migrate_legacy_conversation_if_needed(db, user_id, thread_id)
    return await db.assistant_threads.find_one({"user_id": user_id, "thread_id": thread_id})


async def list_assistant_threads(db, user_id: str) -> List[Dict[str, Any]]:
    await get_or_create_assistant_thread(db, user_id)
    items: List[Dict[str, Any]] = []
    cursor = db.assistant_threads.find({
        "user_id": user_id,
        "archived": {"$ne": True},
    }).sort([("pinned", -1), ("parent_thread_id", 1), ("updated_at", -1)])
    async for doc in cursor:
        if _is_visible_assistant_topic(doc):
            items.append(_thread_doc_to_item(doc))
    return items


async def create_assistant_thread(
    db,
    user_id: str,
    title: Optional[str] = None,
    parent_thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_parent_id = (parent_thread_id or "").strip() or None
    if normalized_parent_id:
        parent = await db.assistant_threads.find_one({
            "user_id": user_id,
            "thread_id": normalized_parent_id,
            "archived": {"$ne": True},
        })
        if not parent:
            raise ValueError("父主题不存在或已删除")

    thread_id = _generate_thread_id()
    thread_title = (title or "").strip() or f"新主题 {datetime.now().strftime('%m-%d %H:%M')}"
    existing_docs = await db.assistant_threads.find({
        "user_id": user_id,
        "archived": {"$ne": True},
    }).to_list(length=None)
    existing_docs = [doc for doc in existing_docs if _is_visible_assistant_topic(doc)]
    similar_doc = _find_similar_thread(existing_docs, thread_title, normalized_parent_id)
    if similar_doc:
        return _thread_doc_to_item(similar_doc)

    doc = await _create_thread_document(
        db,
        user_id,
        thread_id,
        thread_title,
        parent_thread_id=normalized_parent_id,
        topic_type="subtopic" if normalized_parent_id else "general",
    )
    return _thread_doc_to_item(doc)


async def delete_assistant_thread(db, user_id: str, thread_id: str) -> List[str]:
    normalized_thread_id = (thread_id or "").strip()
    if not normalized_thread_id:
        raise ValueError("主题 ID 不能为空")
    if normalized_thread_id == ASSISTANT_DEFAULT_THREAD_ID:
        raise ValueError("默认主题不能删除")

    docs = await db.assistant_threads.find({
        "user_id": user_id,
        "archived": {"$ne": True},
    }).to_list(length=None)
    docs = [doc for doc in docs if _is_visible_assistant_topic(doc)]

    by_id = {doc.get("thread_id"): doc for doc in docs}
    if normalized_thread_id not in by_id:
        raise ValueError("主题不存在或已删除")

    children_by_parent: Dict[str, List[str]] = {}
    for doc in docs:
        parent_id = doc.get("parent_thread_id")
        child_id = doc.get("thread_id")
        if parent_id and child_id:
            children_by_parent.setdefault(parent_id, []).append(child_id)

    pending = [normalized_thread_id]
    deleted_ids: List[str] = []
    while pending:
        current_id = pending.pop()
        if current_id in deleted_ids:
            continue
        deleted_ids.append(current_id)
        pending.extend(children_by_parent.get(current_id, []))

    await db.assistant_thread_messages.delete_many({
        "user_id": user_id,
        "thread_id": {"$in": deleted_ids},
    })
    await db.assistant_thread_checkpoints.delete_many({
        "user_id": user_id,
        "thread_id": {"$in": deleted_ids},
    })
    await db.assistant_threads.delete_many({
        "user_id": user_id,
        "thread_id": {"$in": deleted_ids},
    })

    return deleted_ids


async def get_assistant_thread_messages(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    messages: List[Dict[str, Any]] = []
    cursor = db.assistant_thread_messages.find({
        "user_id": user_id,
        "thread_id": thread["thread_id"],
    }).sort("created_at", 1)
    async for doc in cursor:
        messages.append({
            "role": doc.get("role", "assistant"),
            "content": doc.get("content", ""),
            "tools_used": doc.get("tools_used") or None,
        })
    return _thread_doc_to_item(thread), messages


async def append_assistant_message(
    db,
    user_id: str,
    role: str,
    content: str,
    conversation_id: Optional[str] = None,
    tools_used: Optional[List[str]] = None,
) -> str:
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    thread_id = thread["thread_id"]
    text = (content or "").strip()
    if not text:
        return thread_id

    await db.assistant_thread_messages.insert_one({
        "message_id": f"msg_{uuid.uuid4().hex}",
        "thread_id": thread_id,
        "user_id": user_id,
        "role": role,
        "content": text,
        "tools_used": tools_used or [],
        "created_at": _now_utc(),
    })

    updates: Dict[str, Any] = {"updated_at": _now_utc()}
    if role == "user":
        updates["last_user_message"] = text[:200]

    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread_id},
        {
            "$set": updates,
            "$inc": {"message_count": 1},
        },
    )
    return thread_id


async def summarize_assistant_thread(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
    summary_type: str = "manual",
) -> Dict[str, Any]:
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    _, messages = await get_assistant_thread_messages(db, user_id, thread["thread_id"])
    summary = await _build_thread_summary_with_llm(db, messages[-12:], thread.get("title") or "")
    now = _now_utc()

    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread["thread_id"]},
        {
            "$set": {
                "current_summary": summary,
                "updated_at": now,
            }
        },
    )

    await db.assistant_thread_checkpoints.insert_one({
        "checkpoint_id": f"chk_{uuid.uuid4().hex[:12]}",
        "thread_id": thread["thread_id"],
        "user_id": user_id,
        "summary_type": summary_type,
        "summary_text": summary.get("abstract", ""),
        "structured_summary": summary,
        "created_at": now,
    })

    await _store_thread_summary_memory(
        db,
        user_id=user_id,
        thread_id=thread["thread_id"],
        title=thread.get("title") or "",
        summary=summary,
        summary_type=summary_type,
    )

    return summary


async def _store_thread_summary_memory(
    db,
    *,
    user_id: str,
    thread_id: str,
    title: str,
    summary: Dict[str, Any],
    summary_type: str,
) -> None:
    """主题摘要只保留在 Mongo 线程摘要集合，不再写入 mem0 长期记忆。"""
    return


async def save_assistant_message(
    db,
    user_id: str,
    user_content: str,
    assistant_content: str,
    tools_used: List[str],
    conversation_id: Optional[str] = None,
) -> None:
    """将会话追加写入 MongoDB"""
    thread_id = await append_assistant_message(
        db,
        user_id=user_id,
        role="user",
        content=user_content,
        conversation_id=conversation_id,
    )
    await append_assistant_message(
        db,
        user_id=user_id,
        role="assistant",
        content=assistant_content,
        conversation_id=thread_id,
        tools_used=tools_used,
    )
    await summarize_assistant_thread(
        db,
        user_id=user_id,
        conversation_id=thread_id,
        summary_type="auto",
    )


async def get_assistant_conversation(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """获取用户的智能助手会话历史"""
    _, messages = await get_assistant_thread_messages(db, user_id, conversation_id)
    return messages


async def clear_assistant_conversation(
    db,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> None:
    """清空用户的智能助手会话"""
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    await db.assistant_thread_messages.delete_many(
        {"user_id": user_id, "thread_id": thread["thread_id"]}
    )
    await db.assistant_threads.update_one(
        {"user_id": user_id, "thread_id": thread["thread_id"]},
        {
            "$set": {
                "message_count": 0,
                "last_user_message": "",
                "current_summary": {
                    "abstract": "",
                    "confirmed_facts": [],
                    "open_questions": [],
                    "next_actions": [],
                    "focus_score": 0.0,
                },
                "updated_at": _now_utc(),
            }
        },
    )


async def load_user_profile(db, user_id: str) -> Optional[dict]:
    """从 assistant_user_profiles 集合加载用户画像"""
    try:
        doc = await db.assistant_user_profiles.find_one({"user_id": user_id})
        return doc
    except Exception as e:
        logger.warning("[智能助手] 加载用户画像失败: %s", e)
    return None


async def update_user_profile_with_analysis(
    db,
    user_id: str,
    symbol: str,
    name: str,
    conclusion: str,
    task_id: str,
) -> None:
    """
    分析任务完成后，将结果追加到用户画像的 recently_analyzed 列表。
    保留最近 20 条，upsert 方式写入 assistant_user_profiles 集合。
    """
    try:
        now = datetime.now(timezone.utc)
        entry = {
            "symbol": symbol,
            "name": name,
            "analyzed_at": now.strftime("%Y-%m-%d"),
            "conclusion": conclusion,
            "task_id": task_id,
        }
        await db.assistant_user_profiles.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "recently_analyzed": {
                        "$each": [entry],
                        "$slice": -20,
                    }
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
        )
        logger.info(f"[用户画像] ✅ 已更新 {user_id} 的 recently_analyzed: {symbol}({name})")
    except Exception as e:
        logger.warning(f"[用户画像] 更新失败（已忽略）: {e}")


async def _load_assistant_settings(db, user_id: str) -> Optional[dict]:
    """从数据库加载用户的助理个性化设置"""
    try:
        from bson import ObjectId
        user_doc = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"preferences.assistant_settings": 1},
        )
        if user_doc:
            prefs = user_doc.get("preferences", {})
            return prefs.get("assistant_settings")
    except Exception as e:
        logger.warning("[智能助手] 加载助理设置失败: %s", e)
    return None


# ------------------------------------------------------------------
#  mem0 统一记忆层 — 助手对话集成
# ------------------------------------------------------------------

async def _recall_memory_block(db, user_id: str, user_message: str) -> str:
    """从 mem0 召回与当前用户/问题相关的记忆，格式化为可注入 prompt 的文本。

    召回范围：
    - user_preference: 用户偏好（通过 remember_this 显式登记）
    - trade_pattern:   交易纪律记忆（复盘完成后写入）
    """
    try:
        from core.memory.service import get_memory_service
        svc = get_memory_service(db)
        return await svc.recall_formatted(
            query=user_message,
            user_id=user_id,
            scopes=["user_preference", "trade_pattern"],
            limit=6,
            max_chars=800,
        )
    except Exception as e:
        logger.debug("[mem0] 记忆召回失败（已忽略）: %s", e)
        return ""


async def chat_with_assistant(
    db,
    user_message: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    current_thread_id: Optional[str] = None,
    is_im: bool = False,
    model: Optional[str] = None,
    model_config_id: Optional[str] = None,
    quick_model: Optional[str] = None,
    quick_model_config_id: Optional[str] = None,
    deep_model: Optional[str] = None,
    deep_model_config_id: Optional[str] = None,
    assistant_role: str = "general",
    user_context: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    便捷函数：使用智能助手进行对话
    user_id: 用于持久化会话；若提供则对话会后保存
    is_im: 是否来自 IM 渠道（QQ Bot 等），为 True 时注入移动端格式规范
    assistant_role: 助手角色 general=通用分析助理 / usage_helper=使用问答机器人
    user_context: 前端上下文（仅 usage_helper 模式使用）
    """
    # 设置用户上下文，供 assistant_ops 工具获取当前用户
    if user_id:
        set_current_user_id(user_id)
    if current_thread_id:
        set_current_assistant_thread_id(current_thread_id)
    elif conversation_id:
        set_current_assistant_thread_id(conversation_id)

    # 加载用户助理个性化设置
    assistant_settings = None
    if user_id:
        assistant_settings = await _load_assistant_settings(db, user_id)

    # 加载用户画像（跨会话持久记忆）
    user_profile: Optional[dict] = None
    current_topic_title: Optional[str] = None
    if user_id:
        try:
            user_profile = await load_user_profile(db, user_id)
            if user_profile and user_profile.get("recently_analyzed"):
                logger.info(f"[智能助手] ✅ 用户画像加载成功，最近分析 {len(user_profile['recently_analyzed'])} 条")
        except Exception as e:
            logger.warning(f"[智能助手] 加载用户画像失败（已跳过）: {e}")

    if user_id and current_thread_id:
        try:
            current_topic = await db.assistant_threads.find_one(
                {
                    "user_id": user_id,
                    "thread_id": current_thread_id,
                    "archived": {"$ne": True},
                },
                {"title": 1},
            )
            if current_topic:
                current_topic_title = (current_topic.get("title") or "").strip() or None
        except Exception as e:
            logger.warning(f"[智能助手] 加载当前主题失败（已跳过）: {e}")

    # 加载最近会话历史（最多 10 条，注入到 LLM 上下文）
    history_messages: Optional[List[Message]] = None
    if user_id:
        try:
            raw_history = await get_assistant_conversation(db, user_id, conversation_id)
            if raw_history:
                recent = raw_history[-ASSISTANT_MAX_CONTEXT_MESSAGES:]
                history_messages = []
                for m in recent:
                    role = MessageRole.USER if m.get("role") == "user" else MessageRole.ASSISTANT
                    content = (m.get("content") or "").strip()
                    if content:
                        history_messages.append(Message(role=role, content=content[:800]))
                if not history_messages:
                    history_messages = None
        except Exception as e:
            logger.warning(f"[智能助手] 加载历史会话失败（已跳过）: {e}")

    # mem0 记忆召回（降级安全）
    memory_block = ""
    if user_id:
        memory_block = await _recall_memory_block(db, user_id, user_message)

    service = IntelligentAssistantService(
        db,
        preferred_models=_build_assistant_model_preferences(
            model=model,
            model_config_id=model_config_id,
            quick_model=quick_model,
            quick_model_config_id=quick_model_config_id,
            deep_model=deep_model,
            deep_model_config_id=deep_model_config_id,
        ),
        user_id=user_id or "",
        assistant_role=assistant_role,
        user_context=user_context,
    )
    result = await service.chat(
        user_message,
        conversation_id,
        assistant_settings,
        is_im=is_im,
        history_messages=history_messages,
        user_profile=user_profile,
        current_topic_title=current_topic_title,
        memory_block=memory_block,
    )
    if user_id and result.get("reply"):
        try:
            await save_assistant_message(
                db,
                user_id=user_id,
                user_content=user_message.strip(),
                assistant_content=result["reply"],
                tools_used=result.get("tools_used") or [],
                conversation_id=conversation_id,
            )
        except Exception as e:
            logger.warning("[智能助手] 保存会话失败: %s", e)

        # 注：mem0 conversation scope 已废弃，对话不再自动写入长期记忆。
        # 用户偏好通过 `remember_this` 元工具显式登记，详见 mem0 §15.5 P0-1。
    if user_id:
        thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
        result["conversation_id"] = thread["thread_id"]
    return result


async def stream_chat_with_assistant(
    db,
    user_message: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    current_thread_id: Optional[str] = None,
    model: Optional[str] = None,
    model_config_id: Optional[str] = None,
    quick_model: Optional[str] = None,
    quick_model_config_id: Optional[str] = None,
    deep_model: Optional[str] = None,
    deep_model_config_id: Optional[str] = None,
    assistant_role: str = "general",
    user_context: Optional[dict] = None,
) -> AsyncGenerator[str, None]:
    """
    流式便捷函数：使用智能助手进行流式对话，返回 SSE 事件字符串的 async generator。
    assistant_role: 助手角色 general=通用分析助理 / usage_helper=使用问答机器人
    user_context: 前端上下文（仅 usage_helper 模式使用）
    """
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    if user_id:
        set_current_user_id(user_id)
    if current_thread_id:
        set_current_assistant_thread_id(current_thread_id)
    elif conversation_id:
        set_current_assistant_thread_id(conversation_id)

    assistant_settings = None
    if user_id:
        assistant_settings = await _load_assistant_settings(db, user_id)

    user_profile: Optional[dict] = None
    current_topic_title: Optional[str] = None
    if user_id:
        try:
            user_profile = await load_user_profile(db, user_id)
        except Exception:
            pass

    if user_id and (current_thread_id or conversation_id):
        tid = current_thread_id or conversation_id
        try:
            current_topic = await db.assistant_threads.find_one(
                {"user_id": user_id, "thread_id": tid, "archived": {"$ne": True}},
                {"title": 1},
            )
            if current_topic:
                current_topic_title = (current_topic.get("title") or "").strip() or None
        except Exception:
            pass

    history_messages: Optional[List[Message]] = None
    if user_id:
        try:
            raw_history = await get_assistant_conversation(db, user_id, conversation_id)
            if raw_history:
                recent = raw_history[-ASSISTANT_MAX_CONTEXT_MESSAGES:]
                history_messages = []
                for m in recent:
                    role = MessageRole.USER if m.get("role") == "user" else MessageRole.ASSISTANT
                    content = (m.get("content") or "").strip()
                    if content:
                        history_messages.append(Message(role=role, content=content[:800]))
                if not history_messages:
                    history_messages = None
        except Exception:
            pass

    # mem0 记忆召回
    memory_block = ""
    if user_id:
        memory_block = await _recall_memory_block(db, user_id, user_message)

    logger.info("[智能助手·流式] mem0 召回完成，memory_block 长度=%d，准备创建 service", len(memory_block))

    service = IntelligentAssistantService(
        db,
        preferred_models=_build_assistant_model_preferences(
            model=model,
            model_config_id=model_config_id,
            quick_model=quick_model,
            quick_model_config_id=quick_model_config_id,
            deep_model=deep_model,
            deep_model_config_id=deep_model_config_id,
        ),
        user_id=user_id or "",
        assistant_role=assistant_role,
        user_context=user_context,
    )

    collected_reply = ""
    collected_tools: List[str] = []

    logger.info("[智能助手·流式] 准备调用 service.chat_stream")

    try:
        async for event_str in service.chat_stream(
            user_message,
            conversation_id,
            assistant_settings,
            history_messages=history_messages,
            user_profile=user_profile,
            current_topic_title=current_topic_title,
            memory_block=memory_block,
        ):
            if event_str.startswith("event: done\n"):
                try:
                    data_line = event_str.split("\ndata: ", 1)[1].rstrip("\n")
                    data = json.loads(data_line)
                    collected_tools = data.get("tools_used", [])
                except Exception:
                    pass
                continue
            if event_str.startswith("event: token\n"):
                try:
                    data_line = event_str.split("\ndata: ", 1)[1].rstrip("\n")
                    data = json.loads(data_line)
                    collected_reply += data.get("content", "")
                except Exception:
                    pass
            yield event_str
    except Exception as e:
        logger.error("[智能助手·流式] chat_stream 生成器抛出异常: %s", e, exc_info=True)
        yield _sse("token", {"content": f"⚠️ 处理过程发生异常：{e}"})

    if user_id and collected_reply:
        try:
            await save_assistant_message(
                db,
                user_id=user_id,
                user_content=user_message.strip(),
                assistant_content=collected_reply,
                tools_used=collected_tools,
                conversation_id=conversation_id,
            )
        except Exception as e:
            logger.warning("[智能助手·流式] 保存会话失败: %s", e)

        # 注：mem0 conversation scope 已废弃，对话不再自动写入长期记忆。
        # 用户偏好通过 `remember_this` 元工具显式登记，详见 mem0 §15.5 P0-1。

    conv_id = conversation_id
    if user_id:
        thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
        conv_id = thread["thread_id"]

    yield _sse("done", {"tools_used": collected_tools, "conversation_id": conv_id})
