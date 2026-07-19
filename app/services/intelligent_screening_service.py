"""
智能筛选服务 — LLM 多轮对话选股

复用智能助手的 LLM 配置、工具注册表、超时机制等基础设施，
新增两阶段流程（需求确认 → 执行筛选）和多轮记忆。
"""

import asyncio
import inspect
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

# 复用智能助手的基础设施
from app.services.factor_registry_service import build_screening_fields_markdown
from app.services.screening_metric_display import resolve_metric_value, select_metric_display_spec
from app.services.intelligent_assistant_service import (
    _get_assistant_llm_config,
    _get_latest_trade_date,
    ASSISTANT_TIMEOUT_SECONDS,
)
from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.tools.context import set_current_user_id
from core.tools.implementations.market.stock_screening_tool import _execute_screening_query, _format_screening_output
from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)

# 会话历史最大条数（每用户）
SCREENING_CONVERSATION_LIMIT = 50
# 每次请求最多传给 LLM 的历史消息条数
MAX_CONTEXT_MESSAGES = 20
# 选股相关的工具类别
# "screening" 类别包含 screen_stocks_by_criteria 批量筛选工具（核心）
SCREENING_TOOL_CATEGORIES = ["screening", "market", "fundamentals", "news", "china", "technical"]
SCREENING_TOOL_IDS = {
    "add_stocks_to_favorites",
    "list_watchlist_groups",
    "add_stock_to_watchlist",
}

# 执行阶段工具收敛：优先仅允许批量筛选链路，避免单股重工具放大时延
RESULT_TOOL_ALLOWLIST = {
    "screen_stocks_by_criteria",
    "batch_check_profit_consistency",
    "add_stocks_to_favorites",
    "list_watchlist_groups",
    "add_stock_to_watchlist",
}

# 选股场景独立预算，默认比全局助手更紧，避免长尾请求拖垮体验
SCREENING_MAX_TOOL_ROUNDS = int(os.environ.get("SCREENING_MAX_TOOL_ROUNDS", "3"))
SCREENING_RESULT_TIMEOUT_SECONDS = int(os.environ.get("SCREENING_RESULT_TIMEOUT_SECONDS", "300"))

SCREENING_ADJUST_KEYWORDS = [
    "重新",
    "修改",
    "调整需求",
    "换个",
    "不对",
    "重新描述",
    "重新考虑",
    "再低点",
    "再高点",
    "缩小",
    "放宽",
]

SCREENING_APPROVAL_KEYWORDS = [
    "执行筛选方案",
    "按此方案",
    "开始筛选",
    "执行",
    "同意",
    "确认",
    "按原需求筛选",
]

SCREENING_NEW_REQUEST_KEYWORDS = [
    "帮我选",
    "选几只",
    "筛选",
    "选股",
    "推荐几只",
    "找几只",
    "高分红",
    "低估值",
    "股票",
]

SCREENING_RESULT_REFERENCE_KEYWORDS = [
    "这5只",
    "这五只",
    "这几只",
    "这些股票",
    "刚才那5只",
    "刚才推荐",
    "当前推荐",
    "上一轮",
    "加入自选",
    "加入股票关注列表",
    "打标签",
    "分组",
]

SCREENING_MULTI_STOCK_REQUEST_KEYWORDS = [
    "帮我选",
    "筛选",
    "推荐几只",
    "找几只",
    "候选",
    "组合",
]

SINGLE_STOCK_QUERY_PREFIXES = (
    "请问一下",
    "请问",
    "我想问一下",
    "我想问",
    "想问一下",
    "想问",
    "帮我看下",
    "帮我判断一下",
    "麻烦看下",
    "麻烦问下",
)

SINGLE_STOCK_DIVIDEND_YIELD_THRESHOLD = 3.0

SCREENING_FIELD_DISPLAY_LABELS = {
    "industry": "行业",
    "dividend_yield": "股息率",
    "pe": "PE",
    "pe_ttm": "PE(TTM)",
    "pb": "PB",
    "pb_mrq": "PB(MRQ)",
    "roe": "ROE",
    "roa": "ROA",
    "gross_margin": "毛利率",
    "netprofit_margin": "净利率",
    "debt_to_assets": "资产负债率",
    "assets_to_eqt": "权益乘数",
    "current_ratio": "流动比率",
    "quick_ratio": "速动比率",
    "cash_ratio": "现金比率",
    "total_mv": "总市值",
    "close": "股价",
    "pct_chg": "涨跌幅",
    "report_period": "财报期",
    "n_cashflow_act": "经营现金流",
    "revenue_ttm": "营收TTM",
    "net_profit_ttm": "净利TTM",
}

SCREENING_PERCENT_FIELDS = {
    "dividend_yield",
    "roe",
    "roa",
    "gross_margin",
    "netprofit_margin",
    "debt_to_assets",
    "pct_chg",
}

SCREENING_YI_FIELDS = {"n_cashflow_act", "revenue_ttm", "net_profit_ttm"}


class IntelligentScreeningService:
    """
    智能筛选服务 — LLM 多轮对话选股

    复用智能助手的 LLM 配置、工具注册表、超时机制等基础设施，
    新增两阶段流程（需求确认 → 执行筛选）和多轮记忆。
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._openai_tools: Optional[list] = None
        self._result_openai_tools: Optional[list] = None
        self._tool_functions: Optional[dict] = None

    async def _ensure_client(self) -> bool:
        """懒加载 LLM 客户端和工具（只加载选股相关的 5 类工具）"""
        if self._llm_client is not None:
            return True

        llm_config = await _get_assistant_llm_config(self._db)
        if not llm_config:
            return False

        try:
            self._llm_client = UnifiedLLMClient.from_config(llm_config)
        except Exception as e:
            logger.error(f"[智能筛选] 创建 LLM 客户端失败: {e}", exc_info=True)
            return False

        # 只加载选股相关的工具
        registry = get_tool_registry()
        all_metadata = registry.list_all()
        screening_metadata = [
            m for m in all_metadata
            if m.fc_enabled and (m.category in SCREENING_TOOL_CATEGORIES or m.id in SCREENING_TOOL_IDS)
        ]
        self._openai_tools = tool_metadata_list_to_openai(screening_metadata)

        self._tool_functions = {}
        for tool in screening_metadata:
            if tool.parameters:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        # 结果执行阶段仅保留批量筛选相关工具，限制工具链复杂度
        self._result_openai_tools = self._filter_result_tools(self._openai_tools)
        if not self._result_openai_tools:
            self._result_openai_tools = self._openai_tools
            logger.warning("[智能筛选] 结果阶段批量工具白名单为空，回退到完整工具集")

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(
            f"[智能筛选] 已加载 {len(self._openai_tools)} 个选股工具，"
            f"结果阶段使用 {len(self._result_openai_tools)} 个执行工具"
        )
        return True

    def _filter_result_tools(self, openai_tools: Optional[list]) -> list:
        """过滤 result 阶段可用工具，优先保留批量筛选链路。"""
        if not openai_tools:
            return []

        filtered = []
        for t in openai_tools:
            fn = t.get("function", {}) if isinstance(t, dict) else {}
            name = fn.get("name")
            if name in RESULT_TOOL_ALLOWLIST:
                filtered.append(t)
        return filtered

    def _infer_request_focus(self, message: str) -> str:
        """从用户请求中提取核心筛选诉求，用于无结果与降级提示。"""
        text = (message or "").strip()
        if not text:
            return "原筛选条件"

        focus_keywords = [
            ("高分红", ["高分红", "分红", "股息", "股息率", "dividend"]),
            ("低估值", ["低估值", "低pe", "低 pb", "低pb", "估值低", "便宜"]),
            ("银行股", ["银行"]),
            ("消费股", ["消费"]),
            ("科技股", ["科技", "芯片", "半导体", "ai"]),
            ("高ROE", ["roe"]),
        ]
        lower_text = text.lower()
        for label, keywords in focus_keywords:
            if any(keyword in text or keyword in lower_text for keyword in keywords):
                return label
        return "原筛选条件"

    def _extract_single_stock_keyword(self, message: str) -> Optional[str]:
        """从单股判断问题中提取股票代码或简称。"""
        text = re.sub(r"\s+", "", message or "")
        if not text:
            return None

        code_match = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
        if code_match:
            return code_match.group(1)

        normalized = text
        for prefix in SINGLE_STOCK_QUERY_PREFIXES:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break

        normalized = re.sub(r"[？?！!。,.，：:；;]", "", normalized)
        patterns = [
            r"([A-Za-z\u4e00-\u9fa5]{2,16})(?:\(|（)?(?:\d{6})?(?:\)|）)?(?:是不是|是否|算不算|属不属于|属于|是)",
            r"([A-Za-z\u4e00-\u9fa5]{2,16})(?:\(|（)?(?:\d{6})?(?:\)|）)?(?:的)?(?:股息率|分红)",
        ]
        stopwords = {"这个", "这只", "该股", "股票", "A股", "个股"}
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            keyword = match.group(1).strip()
            if keyword in stopwords or len(keyword) < 2:
                continue
            return keyword

        return None

    def _looks_like_single_stock_judgement_query(self, message: str) -> bool:
        """识别“单只股票是否满足某属性”的直接判断问题。"""
        text = re.sub(r"\s+", "", message or "")
        if not text:
            return False

        if self._is_adjustment_message(text) or self._is_approval_message(text):
            return False

        if any(keyword in text for keyword in SCREENING_MULTI_STOCK_REQUEST_KEYWORDS):
            return False

        if self._infer_request_focus(text) != "高分红":
            return False

        if not self._extract_single_stock_keyword(text):
            return False

        return any(token in text for token in ("是不是", "是否", "算不算", "属于", "是", "吗"))

    async def _fetch_single_stock_item(self, keyword: str) -> Optional[dict]:
        """按代码或名称检索最匹配的单只股票快照。"""
        items, _total = await _execute_screening_query(
            [{"field": "keyword", "operator": "contains", "value": keyword}],
            10,
            "total_mv",
            "desc",
        )
        if not items:
            return None

        normalized = keyword.strip().lower()

        def score(item: dict) -> tuple[int, float]:
            code = str(item.get("code") or item.get("symbol") or "").strip().lower()
            name = str(item.get("name") or "").strip().lower()
            item_score = 0
            if normalized == code:
                item_score += 100
            if normalized == name:
                item_score += 95
            if normalized and normalized in name:
                item_score += 80
            if normalized and normalized in code:
                item_score += 70
            return item_score, float(item.get("total_mv") or 0)

        return max(items, key=score)

    def _build_single_stock_snapshot(self, item: dict, reason: str) -> dict[str, Any]:
        pe_order_field = "pe_ttm" if item.get("pe_ttm") is not None else "pe"
        pb_order_field = "pb_mrq" if item.get("pb_mrq") is not None else "pb"
        pe_display_field, pe_display_label = select_metric_display_spec(None, pe_order_field, "pe")
        pb_display_field, pb_display_label = select_metric_display_spec(None, pb_order_field, "pb")
        code = str(item.get("code") or item.get("symbol") or "").strip()

        return {
            "code": code,
            "name": str(item.get("name") or ""),
            "industry": str(item.get("industry") or ""),
            "price": item.get("close"),
            "pe": resolve_metric_value(item, pe_display_field, "pe"),
            "pe_display_label": pe_display_label,
            "pb": resolve_metric_value(item, pb_display_field, "pb"),
            "pb_display_label": pb_display_label,
            "roe": item.get("roe"),
            "roa": item.get("roa"),
            "gross_margin": item.get("gross_margin"),
            "netprofit_margin": item.get("netprofit_margin"),
            "dividend_yield": item.get("dividend_yield"),
            "debt_to_assets": item.get("debt_to_assets"),
            "assets_to_eqt": item.get("assets_to_eqt"),
            "current_ratio": item.get("current_ratio"),
            "quick_ratio": item.get("quick_ratio"),
            "cash_ratio": item.get("cash_ratio"),
            "revenue_ttm": item.get("revenue_ttm"),
            "net_profit_ttm": item.get("net_profit_ttm"),
            "n_cashflow_act": item.get("n_cashflow_act"),
            "report_period": item.get("report_period"),
            "pct_change": item.get("pct_chg"),
            "reason": reason,
        }

    async def _maybe_handle_single_stock_query(
        self,
        message: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """对单股属性判断问题直接返回结果，避免误入全市场筛选流程。"""
        if not self._looks_like_single_stock_judgement_query(message):
            return None

        await self._emit_progress(
            progress_callback,
            "status",
            phase="result",
            message="正在核验单只股票的分红指标",
        )

        keyword = self._extract_single_stock_keyword(message)
        if not keyword:
            return None

        item = await self._fetch_single_stock_item(keyword)
        if not item:
            reply = f"未找到与“{keyword}”匹配的股票，暂时无法判断它是否属于高分红股票。"
            return {
                "reply": reply,
                "tools_used": [],
                "stocks": [],
                "phase": "result",
                "is_fallback": False,
            }

        stock_name = str(item.get("name") or keyword)
        stock_code = str(item.get("code") or item.get("symbol") or "")
        dividend_yield = item.get("dividend_yield")
        if not isinstance(dividend_yield, (int, float)):
            reply = f"已找到 {stock_name}（{stock_code}），但当前快照里没有可用的股息率数据，暂时无法判断它是否属于高分红股票。"
            stock = self._build_single_stock_snapshot(item, "当前缺少可用股息率数据，无法直接判断是否属于高分红。")
            return {
                "reply": reply,
                "tools_used": [],
                "stocks": [stock],
                "phase": "result",
                "is_fallback": False,
            }

        is_high_dividend = dividend_yield >= SINGLE_STOCK_DIVIDEND_YIELD_THRESHOLD
        verdict = "可以算" if is_high_dividend else "严格按当前默认口径暂不算"
        reason = (
            f"单股核验：默认以近12个月股息率 ≥ {SINGLE_STOCK_DIVIDEND_YIELD_THRESHOLD:.1f}% 作为高分红口径；"
            f"当前股息率={dividend_yield:.2f}%，因此{verdict}高分红。"
        )
        stock = self._build_single_stock_snapshot(item, reason)

        metrics: list[str] = [f"股息率={dividend_yield:.2f}%"]
        if isinstance(stock.get("pe"), (int, float)):
            metrics.append(f"{stock.get('pe_display_label') or 'PE'}={stock['pe']:.2f}")
        if isinstance(stock.get("roe"), (int, float)):
            metrics.append(f"ROE={stock['roe']:.2f}%")
        if stock.get("report_period"):
            metrics.append(f"财报期={stock['report_period']}")

        reply_lines = [
            f"结论：{stock_name}（{stock_code}）{verdict}高分红股票。",
            f"判断口径：若未额外指定阈值，本系统默认把近12个月股息率 ≥ {SINGLE_STOCK_DIVIDEND_YIELD_THRESHOLD:.1f}% 视为高分红。",
            f"当前指标：{'；'.join(metrics)}。",
        ]
        if is_high_dividend:
            reply_lines.append("补充说明：它更接近稳定分红的高质量白马，不等同于市场里股息率最高的红利型标的。")
        else:
            reply_lines.append("补充说明：如果您更关注分红稳定性或分红比例，而不是静态股息率阈值，可以换该口径再判断。")

        return {
            "reply": "\n\n".join(reply_lines),
            "tools_used": [],
            "stocks": [stock],
            "phase": "result",
            "is_fallback": False,
        }

    def _build_no_match_reply(self, message: str) -> str:
        """未命中条件时返回硬提示，不推荐任何替代股票。"""
        focus = self._infer_request_focus(message)
        return (
            f"未找到符合“{focus}”条件的股票。\n\n"
            "当前没有适合该筛选要求的标的，不推荐其它不符合条件的股票。"
            "如果您仍想继续筛选，请进一步补充阈值、缩小行业范围，或调整筛选条件后重试。"
        )

    def _build_timeout_reply(self, timeout_seconds: int) -> str:
        """执行超时时返回硬提示，不推荐任何替代股票。"""
        return (
            f"抱歉，处理您的选股需求已超时（超过 {timeout_seconds} 秒）。\n\n"
            "本次不会改为推荐其它不符合原筛选条件的股票。"
            "建议您缩小筛选范围、补充更明确的阈值或行业条件，或稍后重试。"
        )

    def _find_last_assistant(self, history: list) -> Optional[dict]:
        for msg in reversed(history or []):
            if msg.get("role") == "assistant":
                return msg
        return None

    async def _classify_intent(self, message: str, history: list) -> Dict[str, Any]:
        """
        让LLM来分析用户意图，而不是用硬编码关键词。

        返回:
        {
            "intent": "adjustment" | "approval" | "new_request" | "follow_up" | "single_stock_query",
            "adjustment_target": "roe" | "pe" | "pb" | "margin" | "other" | null,
            "adjustment_direction": "loosen" | "tighten" | null,
            "explicit_parameters": str | null,
            "confidence": float
        }
        """
        if not await self._ensure_client():
            # 如果LLM不可用，回退到关键词方式
            return {
                "intent": "adjustment" if self._is_adjustment_message(message) else
                          "approval" if self._is_approval_message(message) else
                          "new_request" if self._looks_like_new_screening_request(message) else
                          "single_stock_query" if self._looks_like_single_stock_judgement_query(message) else
                          "follow_up",
                "adjustment_target": None,
                "adjustment_direction": None,
                "explicit_parameters": None,
                "confidence": 0.5
            }

        history_summary = ""
        if history:
            recent = history[-4:]  # 最近4条足够理解上下文
            for h in recent:
                role = "用户" if h["role"] == "user" else "助手"
                content = h["content"][:200] + "..." if len(h["content"]) > 200 else h["content"]
                history_summary += f"{role}: {content}\n"

        system_prompt = """你是一个意图分类器。请分析用户最新消息，并结合对话历史，判断用户意图。

返回JSON格式：
{
    "intent": "adjustment" | "approval" | "new_request" | "follow_up" | "single_stock_query",
    "adjustment_target": "roe" | "pe" | "pb" | "margin" | "debt" | "cashflow" | "other" | null,
    "adjustment_direction": "loosen" | "tighten" | null,
    "explicit_parameters": "用户明确提到的具体参数，如'把ROE放宽到10%'中的'10%'" | null,
    "confidence": 0.0-1.0之间的置信度
}

意图定义：
- adjustment: 用户希望调整之前的筛选条件（放宽、收紧、修改等）
- approval: 用户明确批准某个方案（"执行"、"按此方案"、"好的"等）
- new_request: 用户提出了全新的选股需求，与之前的筛选关系不大
- follow_up: 用户基于当前结果追问（"这几只怎么样"、"加入自选"等）
- single_stock_query: 用户询问单只股票的情况

adjustment_target: 当intent=adjustment时，指出用户想调整哪个指标
adjustment_direction: 当intent=adjustment时，指出是放宽(loosen)还是收紧(tighten)

注意：
- 如果用户说"先放宽ROE吧"，intent=adjustment, adjustment_target=roe, adjustment_direction=loosen
- 如果用户说"把PE改成<20"，intent=adjustment, adjustment_target=pe, adjustment_direction=loosen, explicit_parameters="20"
- 如果用户说"执行筛选方案"，intent=approval
- 如果用户说"重新帮我选科技股"，intent=new_request
- 如果用户说"把这几只加入自选"，intent=follow_up
- 如果用户问"贵州茅台怎么样"，intent=single_stock_query
"""

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=f"对话历史：\n{history_summary}\n\n用户最新消息：{message}")
        ]

        try:
            resp = await self._llm_client.achat(messages, tools=None, log_payloads=True, payload_log_label="intent_classification")
            content = resp.content if resp else ""
            # 提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group(0))
                return result
        except Exception as e:
            logger.warning(f"[智能筛选] 意图分类LLM调用失败: {e}")

        # 失败时回退
        return {
            "intent": "adjustment" if self._is_adjustment_message(message) else
                      "approval" if self._is_approval_message(message) else
                      "new_request" if self._looks_like_new_screening_request(message) else
                      "single_stock_query" if self._looks_like_single_stock_judgement_query(message) else
                      "follow_up",
            "adjustment_target": None,
            "adjustment_direction": None,
            "explicit_parameters": None,
            "confidence": 0.3
        }

    def _is_adjustment_message(self, message: str) -> bool:
        text = (message or "").strip()
        return any(keyword in text for keyword in SCREENING_ADJUST_KEYWORDS)

    def _is_approval_message(self, message: str) -> bool:
        text = (message or "").strip()
        return any(keyword in text for keyword in SCREENING_APPROVAL_KEYWORDS)

    def _looks_like_new_screening_request(self, message: str) -> bool:
        text = (message or "").strip()
        if not text:
            return False
        if self._is_adjustment_message(text) or self._is_approval_message(text):
            return False
        return any(keyword in text for keyword in SCREENING_NEW_REQUEST_KEYWORDS)

    def _references_latest_result(self, message: str) -> bool:
        text = (message or "").strip()
        return any(keyword in text for keyword in SCREENING_RESULT_REFERENCE_KEYWORDS)

    def _select_phase_history(self, history: list, phase: str, message: str, intent: Dict[str, Any] = None) -> list:
        """按阶段压缩历史，避免 result 阶段继续继承整段旧会话。"""
        recent_history = history[-MAX_CONTEXT_MESSAGES:]
        if not recent_history:
            return []

        # 如果是调整类、批准类或追问消息，保留完整历史以便 LLM 理解上下文
        intent_type = intent.get("intent") if intent else None
        if intent_type in ["adjustment", "approval", "follow_up"]:
            return recent_history

        last_assistant = self._find_last_assistant(recent_history)
        if (
            phase == "confirmation"
            and last_assistant
            and last_assistant.get("phase") == "result"
            and intent_type == "new_request"
        ):
            return []

        if phase != "result":
            return recent_history

        selected_history: List[dict] = []
        latest_planning = None
        latest_result = None
        for item in reversed(recent_history):
            if item.get("role") != "assistant":
                continue
            item_phase = item.get("phase")
            if latest_result is None and item_phase == "result":
                latest_result = item
            if latest_planning is None and item_phase == "planning":
                latest_planning = item
            if latest_planning and latest_result:
                break

        if latest_planning:
            selected_history.append(latest_planning)
        if latest_result and intent_type == "follow_up":
            selected_history.append(latest_result)

        return selected_history or recent_history[-2:]

    def _extract_locked_execution_plan(self, history: list) -> Optional[dict]:
        """从最近的 planning 回复中提取已批准的批量执行参数。"""
        latest_planning = None
        for item in reversed(history or []):
            if item.get("role") == "assistant" and item.get("phase") == "planning":
                latest_planning = item
                break

        if not latest_planning:
            return None

        content = str(latest_planning.get("content") or "")
        conditions_match = re.search(r"`?conditions`?\s*[:：]\s*`(\[[\s\S]*?\])`", content)
        limit_match = re.search(r"`?limit`?\s*[:：]\s*(\d+)", content)
        order_by_match = re.search(r'`?order_by_field`?\s*[:：]\s*"([^"]+)"', content)
        order_direction_match = re.search(r'`?order_direction`?\s*[:：]\s*"([^"]+)"', content)

        if not conditions_match:
            return None

        try:
            raw_conditions = json.loads(conditions_match.group(1))
        except json.JSONDecodeError:
            return None

        if not isinstance(raw_conditions, list) or not raw_conditions:
            return None

        plan: Dict[str, Any] = {
            "planning_content": content,
            "screen": {
                "conditions_json": json.dumps(raw_conditions, ensure_ascii=False),
                "limit": int(limit_match.group(1)) if limit_match else 50,
                "order_by_field": order_by_match.group(1) if order_by_match else "total_mv",
                "order_direction": order_direction_match.group(1) if order_direction_match else "desc",
            },
        }

        years_match = re.search(r"`?years`?\s*[:：]\s*(\d+)", content)
        threshold_match = re.search(r"`?threshold_cv`?\s*[:：]\s*([0-9.]+)", content)
        if years_match or threshold_match:
            plan["batch"] = {
                "years": int(years_match.group(1)) if years_match else 3,
                "threshold_cv": float(threshold_match.group(1)) if threshold_match else 0.3,
            }

        return plan

    def _extract_candidate_codes(self, screening_output: str) -> list[str]:
        match = re.search(r"候选代码列表（按当前排序，共\s*\d+\s*只）:\s*([^\n]+)", screening_output or "")
        if not match:
            return []
        return [code.strip() for code in match.group(1).split(",") if code.strip()]

    def _build_locked_plan_summary(self, locked_plan: dict) -> str:
        screen_plan = locked_plan.get("screen", {})
        try:
            conditions = json.loads(screen_plan.get("conditions_json", "[]"))
        except json.JSONDecodeError:
            conditions = []

        lines = ["已批准执行计划摘要："]
        if conditions:
            lines.append(f"- 筛选条件: {json.dumps(conditions, ensure_ascii=False)}")
        lines.append(f"- limit: {screen_plan.get('limit', 50)}")
        lines.append(f"- order_by_field: {screen_plan.get('order_by_field', 'total_mv')}")
        lines.append(f"- order_direction: {screen_plan.get('order_direction', 'desc')}")

        batch_plan = locked_plan.get("batch")
        if batch_plan:
            lines.append(
                f"- 盈利稳定性验证: years={batch_plan.get('years', 3)}, "
                f"threshold_cv={batch_plan.get('threshold_cv', 0.3)}"
            )

        return "\n".join(lines)

    def _compact_screening_output_for_llm(self, screening_output: str) -> str:
        lines = [line for line in (screening_output or "").splitlines() if line.strip()]
        if not lines:
            return "无筛选结果。"

        summary_lines: List[str] = [lines[0]]
        candidate_lines = [line for line in lines if re.match(r"^\d+\.\s", line)]
        summary_lines.extend(candidate_lines[:5])
        if len(candidate_lines) > 5:
            summary_lines.append(f"其余 {len(candidate_lines) - 5} 只候选已省略。")
        return "\n".join(summary_lines)

    def _compact_batch_output_for_llm(self, batch_output: str) -> str:
        lines = [line for line in (batch_output or "").splitlines() if line.strip()]
        if not lines:
            return "本轮未执行盈利稳定性验证。"

        summary_lines = [lines[0]]
        summary_match = next((line for line in lines if line.startswith("📊 汇总：")), "")
        if summary_match:
            summary_lines.append(summary_match)

        stable_match = re.search(r"✅ 稳定股票代码：([^\n]+)", batch_output or "")
        if stable_match:
            stable_codes = [code.strip() for code in stable_match.group(1).split(",") if code.strip()]
            preview = ", ".join(stable_codes[:8])
            summary_lines.append(f"稳定股票代码预览: {preview}")
            if len(stable_codes) > 8:
                summary_lines.append(f"其余 {len(stable_codes) - 8} 只稳定股票代码已省略。")

        no_data_match = re.search(r"无数据\s*(\d+)\s*只", batch_output or "")
        if no_data_match:
            summary_lines.append(f"无数据股票数量: {no_data_match.group(1)}")

        return "\n".join(summary_lines)

    def _extract_stable_codes(self, batch_output: str) -> list[str]:
        stable_match = re.search(r"✅ 稳定股票代码：([^\n]+)", batch_output or "")
        if not stable_match:
            return []
        return [code.strip() for code in stable_match.group(1).split(",") if code.strip()]

    def _format_reason_metric_value(self, field: str, value: Any) -> str:
        if value is None:
            return "-"
        if field in SCREENING_PERCENT_FIELDS and isinstance(value, (int, float)):
            return f"{value:.2f}%"
        if field in SCREENING_YI_FIELDS and isinstance(value, (int, float)):
            return f"{value / 1e8:.2f}亿"
        if field == "total_mv" and isinstance(value, (int, float)):
            return f"{value:.2f}亿"
        if field == "report_period":
            return str(value)
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return str(value)

    def _get_reason_field_label(self, field: str, pe_display_label: str, pb_display_label: str) -> str:
        if field in {"pe", "pe_ttm"}:
            return pe_display_label
        if field in {"pb", "pb_mrq"}:
            return pb_display_label
        return SCREENING_FIELD_DISPLAY_LABELS.get(field, field)

    def _build_stock_reason(
        self,
        item: dict,
        raw_conditions: list,
        pe_display_field: str,
        pe_display_label: str,
        pb_display_field: str,
        pb_display_label: str,
        stability_checked: bool,
        stability_passed: bool,
    ) -> str:
        reason_parts: list[str] = []
        seen_parts: set[str] = set()

        for condition in raw_conditions:
            if not isinstance(condition, dict):
                continue
            field = condition.get("field")
            if field == "is_st" and condition.get("value") is False:
                if "非ST" not in seen_parts:
                    reason_parts.append("非ST")
                    seen_parts.add("非ST")
                continue

            if field == "keyword":
                continue

            if field in {"pe", "pe_ttm"}:
                value = resolve_metric_value(item, pe_display_field, "pe")
            elif field in {"pb", "pb_mrq"}:
                value = resolve_metric_value(item, pb_display_field, "pb")
            else:
                value = item.get(field)

            if value is None:
                continue

            label = self._get_reason_field_label(field, pe_display_label, pb_display_label)
            part = f"{label}={self._format_reason_metric_value(field, value)}"
            if part not in seen_parts:
                reason_parts.append(part)
                seen_parts.add(part)

        if not reason_parts:
            fallback_fields = [
                (pe_display_field, pe_display_label),
                (pb_display_field, pb_display_label),
                ("dividend_yield", "股息率"),
                ("roe", "ROE"),
                ("debt_to_assets", "资产负债率"),
            ]
            for field, label in fallback_fields:
                value = resolve_metric_value(item, field, "pe") if field in {"pe", "pe_ttm"} else resolve_metric_value(item, field, "pb") if field in {"pb", "pb_mrq"} else item.get(field)
                if value is None:
                    continue
                part = f"{label}={self._format_reason_metric_value(field, value)}"
                if part not in seen_parts:
                    reason_parts.append(part)
                    seen_parts.add(part)

        report_period = item.get("report_period")
        if report_period and "财报期" not in seen_parts:
            reason_parts.append(f"财报期={report_period}")

        if stability_checked:
            reason_parts.append("近3年盈利稳定性验证通过" if stability_passed else "本轮未纳入盈利稳定性通过名单")

        if not reason_parts:
            return "符合已批准的筛选条件。"

        return "符合已批准条件：" + "，".join(reason_parts[:5]) + "。"

    def _build_structured_stocks(
        self,
        items: list,
        raw_conditions: list,
        order_by_field: str,
        batch_output: str,
    ) -> list[dict[str, Any]]:
        pe_display_field, pe_display_label = select_metric_display_spec(raw_conditions, order_by_field, "pe")
        pb_display_field, pb_display_label = select_metric_display_spec(raw_conditions, order_by_field, "pb")
        stable_codes = self._extract_stable_codes(batch_output)
        stable_set = set(stable_codes)
        selected_items = items or []
        if stable_codes:
            stable_items = [
                item for item in selected_items
                if str(item.get("code") or item.get("symbol", "")).strip() in stable_set
            ]
            if stable_items:
                selected_items = stable_items

        stocks: list[dict[str, Any]] = []
        for item in selected_items[:5]:
            code = str(item.get("code") or item.get("symbol", "")).strip()
            if not code:
                continue

            stability_checked = bool(batch_output)
            stability_passed = code in stable_set if stable_set else False
            stocks.append({
                "code": code,
                "name": str(item.get("name") or ""),
                "industry": str(item.get("industry") or ""),
                "price": item.get("close"),
                "pe": resolve_metric_value(item, pe_display_field, "pe"),
                "pe_display_label": pe_display_label,
                "pb": resolve_metric_value(item, pb_display_field, "pb"),
                "pb_display_label": pb_display_label,
                "roe": item.get("roe"),
                "roa": item.get("roa"),
                "gross_margin": item.get("gross_margin"),
                "netprofit_margin": item.get("netprofit_margin"),
                "dividend_yield": item.get("dividend_yield"),
                "debt_to_assets": item.get("debt_to_assets"),
                "assets_to_eqt": item.get("assets_to_eqt"),
                "current_ratio": item.get("current_ratio"),
                "quick_ratio": item.get("quick_ratio"),
                "cash_ratio": item.get("cash_ratio"),
                "revenue_ttm": item.get("revenue_ttm"),
                "net_profit_ttm": item.get("net_profit_ttm"),
                "n_cashflow_act": item.get("n_cashflow_act"),
                "report_period": item.get("report_period"),
                "pct_change": item.get("pct_chg"),
                "reason": self._build_stock_reason(
                    item,
                    raw_conditions,
                    pe_display_field,
                    pe_display_label,
                    pb_display_field,
                    pb_display_label,
                    stability_checked,
                    stability_passed,
                ),
            })

        return stocks

    def _build_locked_result_reply(self, total_candidates: int, stocks: list[dict[str, Any]], batch_output: str) -> str:
        lines = ["已按批准的筛选方案执行完成。"]
        if total_candidates:
            lines.append(f"共筛出 {total_candidates} 只候选。")

        batch_summary = next(
            (line.strip() for line in (batch_output or "").splitlines() if line.strip().startswith("📊 汇总：")),
            "",
        )
        if batch_summary:
            lines.append(batch_summary)

        if not stocks:
            if batch_output:
                lines.append("原始筛选已有候选，但结合盈利稳定性验证后未形成最终清单，不再放宽阈值。")
            else:
                lines.append("当前未形成可展示的最终候选，不再放宽阈值。")
        else:
            if len(stocks) < 5:
                lines.append(f"当前仅有 {len(stocks)} 只候选满足条件，不再放宽阈值。")
            else:
                lines.append("以下为最符合当前条件的 5 只候选：")

            for index, stock in enumerate(stocks, 1):
                metrics = []
                if isinstance(stock.get("price"), (int, float)):
                    metrics.append(f"价格={stock['price']:.2f}元")
                if isinstance(stock.get("pe"), (int, float)):
                    metrics.append(f"{stock.get('pe_display_label') or 'PE'}={stock['pe']:.2f}")
                if isinstance(stock.get("pb"), (int, float)):
                    metrics.append(f"{stock.get('pb_display_label') or 'PB'}={stock['pb']:.2f}")
                if isinstance(stock.get("dividend_yield"), (int, float)):
                    metrics.append(f"股息率={stock['dividend_yield']:.2f}%")
                if isinstance(stock.get("roe"), (int, float)):
                    metrics.append(f"ROE={stock['roe']:.2f}%")

                header = f"{index}. {stock.get('code', '')} {stock.get('name', '')}"
                if stock.get("industry"):
                    header += f"（{stock['industry']}）"
                lines.append(header)
                if metrics:
                    lines.append(f"   - 关键指标：{'；'.join(metrics[:5])}")
                if stock.get("reason"):
                    lines.append(f"   - 理由：{stock['reason']}")

        lines.append("")
        lines.append("```json")
        lines.append(json.dumps({"stocks": stocks}, ensure_ascii=False, indent=2))
        lines.append("```")
        return "\n".join(lines)

    async def _invoke_tool_function(self, tool_name: str, **kwargs) -> str:
        func = (self._tool_functions or {}).get(tool_name)
        if not func:
            raise ValueError(f"工具不存在：{tool_name}")

        result = func(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return str(result or "")

    async def _run_locked_result_execution(
        self,
        message: str,
        locked_plan: dict,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> tuple[str, List[str], list[dict[str, Any]]]:
        """按已批准的 planning 参数直接执行工具，并由服务端生成最终结构化结果。"""
        tools_used: List[str] = []

        screen_args = locked_plan["screen"]
        raw_conditions = json.loads(screen_args.get("conditions_json", "[]"))
        await self._emit_progress(
            progress_callback,
            "status",
            phase="result",
            message="按已批准的执行计划直接运行批量筛选",
        )
        screen_items, total_candidates = await _execute_screening_query(
            raw_conditions,
            int(screen_args.get("limit", 50)),
            screen_args.get("order_by_field", "total_mv"),
            screen_args.get("order_direction", "desc"),
        )
        screen_output = _format_screening_output(
            raw_conditions,
            screen_items,
            total_candidates,
            screen_args.get("order_by_field", "total_mv"),
        )
        tools_used.append("screen_stocks_by_criteria")

        batch_output = ""
        candidate_codes = [
            str(item.get("code") or item.get("symbol", "")).strip()
            for item in screen_items
            if str(item.get("code") or item.get("symbol", "")).strip()
        ]
        batch_plan = locked_plan.get("batch")
        if batch_plan and candidate_codes:
            batch_args = {
                "stock_codes_json": json.dumps(candidate_codes, ensure_ascii=False),
                "years": batch_plan.get("years", 3),
                "threshold_cv": batch_plan.get("threshold_cv", 0.3),
            }
            batch_output = await self._invoke_tool_function("batch_check_profit_consistency", **batch_args)
            tools_used.append("batch_check_profit_consistency")

        stocks = self._build_structured_stocks(
            screen_items,
            raw_conditions,
            screen_args.get("order_by_field", "total_mv"),
            batch_output,
        )
        reply = self._build_locked_result_reply(total_candidates, stocks, batch_output)
        return reply, tools_used, stocks

    async def _emit_progress(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]],
        event: str,
        **data,
    ) -> None:
        """发送智能筛选进度事件，供 WebSocket 流式展示。"""
        if not progress_callback:
            return

        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        try:
            await progress_callback(payload)
        except Exception as e:
            logger.debug("[智能筛选] 进度推送失败(忽略): %s", e)

    def _build_conversation_title(self, message: str) -> str:
        text = re.sub(r"\s+", " ", (message or "").strip())
        if not text:
            return "未命名筛选"
        return text[:30]

    def _format_dt(self, value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return None

    async def _ensure_conversation_doc_identity(self, doc: Optional[dict]) -> Optional[dict]:
        if not doc:
            return None

        messages = doc.get("messages") or []
        first_user_message = next(
            (item.get("content", "") for item in messages if item.get("role") == "user"),
            "",
        )
        updates: Dict[str, Any] = {}
        if not doc.get("conversation_id"):
            updates["conversation_id"] = uuid.uuid4().hex
        if not doc.get("title"):
            updates["title"] = self._build_conversation_title(first_user_message)

        if updates:
            await self._db.screening_conversations.update_one({"_id": doc["_id"]}, {"$set": updates})
            doc.update(updates)

        return doc

    async def _get_conversation_doc(self, user_id: str, conversation_id: Optional[str] = None) -> Optional[dict]:
        if conversation_id:
            doc = await self._db.screening_conversations.find_one({
                "user_id": user_id,
                "conversation_id": conversation_id,
            })
            return await self._ensure_conversation_doc_identity(doc)

        doc = await self._db.screening_conversations.find_one(
            {"user_id": user_id},
            sort=[("updated_at", -1), ("created_at", -1)],
        )
        return await self._ensure_conversation_doc_identity(doc)

    async def chat(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        核心方法：处理用户的选股请求（三阶段流程）

        阶段 1 — 需求确认（confirmation）：LLM 分析需求，返回理解 + 改进建议，不调用工具
        阶段 2 — 执行规划（planning）：LLM 说明具体调用哪些工具、用什么参数，不实际执行
        阶段 3 — 执行筛选（result）：LLM 调用工具，返回 5 只股票
        """
        # 1. 获取历史对话
        resolved_conversation_id, history = await self._get_context_messages(user_id, conversation_id)
        if not resolved_conversation_id:
            resolved_conversation_id = conversation_id or uuid.uuid4().hex

        # 2. LLM意图分类
        intent = await self._classify_intent(message, history)
        logger.info(f"[智能筛选] 用户={user_id} 意图分类={intent.get('intent')} 置信度={intent.get('confidence'):.2f}")

        # 3. 先检查是否是单只股票查询
        if intent.get("intent") == "single_stock_query":
            direct_result = await self._maybe_handle_single_stock_query(
                message,
                progress_callback=progress_callback,
            )
            if direct_result is not None:
                await self._save_message(
                    user_id,
                    resolved_conversation_id,
                    message,
                    direct_result["reply"],
                    direct_result.get("tools_used", []),
                    direct_result.get("stocks", []),
                    direct_result.get("phase", "result"),
                    is_fallback=False,
                )
                direct_result["conversation_id"] = resolved_conversation_id
                return direct_result

        if not await self._ensure_client():
            return {
                "reply": "智能筛选暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。",
                "tools_used": [],
                "stocks": [],
                "phase": "result",
                "conversation_id": conversation_id,
                "is_fallback": False,
            }

        set_current_user_id(user_id)

        # 4. 判断当前应进入哪个阶段
        phase = self._determine_phase(history, message, intent)
        logger.info(f"[智能筛选] 用户={user_id} 当前阶段={phase} 消息={message[:50]}")
        await self._emit_progress(
            progress_callback,
            "phase_determined",
            phase=phase,
            message=(
                "正在分析您的筛选需求" if phase == "confirmation"
                else "正在生成筛选执行计划" if phase == "planning"
                else "正在执行批量筛选与验证"
            ),
        )

        # 5. 构建消息列表（包含历史）
        # planning 阶段需要将实际可用的工具清单传入提示词，防止 LLM 幻觉工具名
        tool_summary = self._build_tool_summary(self._result_openai_tools) if phase == "planning" else ""
        system_prompt = self._get_system_prompt(phase, tool_summary, intent)
        messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        phase_history = self._select_phase_history(history, phase, message, intent)
        locked_plan = (
            self._extract_locked_execution_plan(phase_history)
            if phase == "result" and intent.get("intent") == "approval"
            else None
        )
        for h in phase_history:
            role = MessageRole.USER if h["role"] == "user" else MessageRole.ASSISTANT
            messages.append(Message(role=role, content=h["content"]))
        messages.append(Message(role=MessageRole.USER, content=message))

        tools_used: List[str] = []
        structured_stocks: list = []

        async def _do_chat():
            nonlocal tools_used, structured_stocks
            if phase == "result":
                await self._emit_progress(
                    progress_callback,
                    "status",
                    phase=phase,
                    message="已进入执行阶段，开始调用筛选与股票关注列表工具",
                )
                if locked_plan:
                    logger.info("[智能筛选] 使用已批准计划直接执行 result 阶段")
                    content, locked_tools_used, locked_stocks = await self._run_locked_result_execution(
                        message,
                        locked_plan,
                        progress_callback=progress_callback,
                    )
                    tools_used.extend(locked_tools_used)
                    structured_stocks = locked_stocks
                    return content
                # 阶段 3：实际调用工具执行筛选
                resp = await self._llm_client.achat(
                    messages,
                    tools=self._result_openai_tools,
                    auto_execute_tools=True,
                    max_tool_rounds=SCREENING_MAX_TOOL_ROUNDS,
                    tools_used=tools_used,
                    progress_callback=progress_callback,
                    log_payloads=True,
                    payload_log_label=f"intelligent_screening:{phase}",
                )
            else:
                await self._emit_progress(
                    progress_callback,
                    "status",
                    phase=phase,
                    message="正在生成阶段性回复",
                )
                # 阶段 1（confirmation）和阶段 2（planning）：均不调用工具
                resp = await self._llm_client.achat(
                    messages,
                    tools=None,
                    log_payloads=True,
                    payload_log_label=f"intelligent_screening:{phase}",
                )
            return resp.content

        try:
            started_at = datetime.now(timezone.utc)
            content = await asyncio.wait_for(
                _do_chat(),
                timeout=SCREENING_RESULT_TIMEOUT_SECONDS if phase == "result" else ASSISTANT_TIMEOUT_SECONDS,
            )
            reply = content or "抱歉，暂时无法生成回答，请稍后再试。"
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            logger.info(
                f"[智能筛选] 完成 phase={phase} elapsed={elapsed:.2f}s tools_used={len(tools_used)}"
            )
            await self._emit_progress(
                progress_callback,
                "status",
                phase=phase,
                message=f"阶段处理完成，用时 {elapsed:.2f} 秒",
                tools_used=tools_used,
            )
        except asyncio.TimeoutError:
            timeout_seconds = (
                SCREENING_RESULT_TIMEOUT_SECONDS if phase == "result" else ASSISTANT_TIMEOUT_SECONDS
            )
            logger.warning(f"[智能筛选] 请求超时（{timeout_seconds}s，phase={phase}）")
            await self._emit_progress(
                progress_callback,
                "timeout",
                phase=phase,
                message=f"处理超时（{timeout_seconds} 秒）",
            )

            reply = self._build_timeout_reply(timeout_seconds)
            await self._save_message(user_id, resolved_conversation_id, message, reply, tools_used, [], "result")
            return {
                "reply": reply,
                "tools_used": tools_used,
                "stocks": [],
                "phase": "result",
                "conversation_id": resolved_conversation_id,
            }
        except Exception as e:
            logger.exception("[智能筛选] 对话失败")
            await self._emit_progress(
                progress_callback,
                "error",
                phase=phase,
                message=f"处理失败：{str(e)}",
            )
            reply = f"处理您的请求时发生错误：{str(e)}。请稍后重试。"
            await self._save_message(user_id, resolved_conversation_id, message, reply, tools_used, [], "result")
            return {
                "reply": reply,
                "tools_used": tools_used,
                "stocks": [],
                "phase": "result",
                "conversation_id": resolved_conversation_id,
            }

        # 提取股票（仅 result 阶段）
        stocks = structured_stocks if phase == "result" and structured_stocks else self._extract_stocks(reply) if phase == "result" else []

        # 清理reply中的JSON代码块（股票数据已通过stocks字段返回）
        if phase == "result":
            reply = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', reply)
            reply = re.sub(r'```\s*\{[\s\S]*?\}\s*```', '', reply)
            reply = reply.strip()

        if phase == "result" and not stocks and "screen_stocks_by_criteria" in tools_used:
            reply = self._build_no_match_reply(message)
            stocks = []
            await self._emit_progress(
                progress_callback,
                "no_match",
                phase="result",
                message="未找到符合原筛选条件的股票",
                stocks=[],
            )
            await self._save_message(user_id, resolved_conversation_id, message, reply, tools_used, stocks, phase)
            return {
                "reply": reply,
                "tools_used": tools_used,
                "stocks": stocks,
                "phase": phase,
                "conversation_id": resolved_conversation_id,
                "is_fallback": False,
            }

        await self._save_message(user_id, resolved_conversation_id, message, reply, tools_used, stocks, phase)
        return {
            "reply": reply,
            "tools_used": tools_used,
            "stocks": stocks,
            "phase": phase,
            "conversation_id": resolved_conversation_id,
            "is_fallback": False,
        }

    def _determine_phase(self, history: list, message: str, intent: Dict[str, Any] = None) -> str:
        """
        基于LLM意图分类来判断当前消息应进入哪个阶段

        返回 'confirmation' → 阶段 1：LLM 分析需求，不调用工具
        返回 'planning'     → 阶段 2：LLM 解释执行计划，不调用工具
        返回 'result'       → 阶段 3：LLM 调用工具，返回股票列表
        """
        # 无历史 → 新需求 → 确认阶段
        if not history:
            return "confirmation"

        # 找到最近一条 assistant 消息
        last_assistant = self._find_last_assistant(history)

        if not last_assistant:
            return "confirmation"

        last_phase = last_assistant.get("phase", "")
        intent_type = intent.get("intent") if intent else None

        if last_phase == "confirmation":
            # 用户回应了确认消息 → 进入规划阶段
            return "planning"

        if last_phase == "planning":
            # 用户回应了规划消息
            if intent_type == "adjustment":
                # 用户要调整需求 → 回到确认阶段重新理解
                return "confirmation"
            # 批准计划或其他 → 进入执行阶段
            return "result"

        # last_phase == "result"
        if intent_type == "new_request":
            # 全新的选股需求 → 重新确认
            return "confirmation"

        # adjustment/approval/follow_up/single_stock_query → 都留在 result 阶段处理
        return "result"

    async def _get_context_messages(self, user_id: str, conversation_id: Optional[str] = None) -> tuple[str, list]:
        """获取最近 N 条对话历史，用于传给 LLM 作为上下文"""
        doc = await self._get_conversation_doc(user_id, conversation_id)
        if not doc or not doc.get("messages"):
            return conversation_id or "", []
        messages = doc["messages"]
        return doc.get("conversation_id", conversation_id or ""), messages[-MAX_CONTEXT_MESSAGES:]

    def _build_tool_summary(self, tools: Optional[list] = None) -> str:
        """将当前注册的工具列表转为文字说明，供 planning 阶段系统提示词使用"""
        target_tools = tools if tools is not None else self._openai_tools
        if not target_tools:
            return "（暂无可用工具）"
        lines = []
        for t in target_tools:
            fn = t.get("function", {})
            name = fn.get("name", "")
            desc = fn.get("description", "")
            params = fn.get("parameters", {}).get("properties", {})
            param_names = ", ".join(params.keys()) if params else "无参数"
            lines.append(f"- `{name}`：{desc}\n  参数：{param_names}")
        return "\n".join(lines)

    def _get_system_prompt(self, phase: str, tool_summary: str = "", intent: Dict[str, Any] = None) -> str:
        """构建选股专家的系统提示词（根据阶段定制）"""
        curr_date = _get_latest_trade_date()

        if phase == "confirmation":
            return f"""你是一位专业的 A 股选股专家。用户刚提出了新的选股需求。

## 你的任务：需求分析与确认

**不要调用任何工具，不要推荐股票。** 请按以下步骤回复：

1. **分析理解**：提炼用户需求的核心条件（行业、估值、风格、时间维度等）
2. **展示理解**：用清晰的列表形式告诉用户"我理解您的需求是..."
3. **改进建议**：基于专业判断，提出 2-3 条可选的改进建议（增加筛选维度、调整阈值、补充考量因素等）
4. **等待确认**：明确询问用户是"按原需求筛选"还是"采纳建议后再筛选"

补充规则：
- 如果用户使用“低估值”“低PE”“低PB”这类模糊估值描述，但没有明确口径，必须在确认阶段显式指出这一歧义
- PE 相关口径要区分 `pe`（PE）和 `pe_ttm`（PE(TTM)）
- PB 相关口径要区分 `pb`（PB）和 `pb_mrq`（PB(MRQ)）
- 遇到这类模糊估值需求时，你可以先给出默认建议口径，但必须把口径写清，并提示用户确认是否采用该口径

回复格式：
```
## 📋 需求分析

我理解您的选股需求如下：
- **行业范围**：xxx
- **核心条件**：xxx
- **筛选风格**：xxx
- **待确认口径**：若您提到“低PE/低PB/低估值”，我会进一步确认是使用 `pe` / `pe_ttm`、`pb` / `pb_mrq`

## 💡 改进建议

基于专业分析，我建议您可以考虑：
1. xxx（原因）
2. xxx（原因）
3. 若“低估值”是核心要求，建议明确采用 `pe_ttm`（PE(TTM)）还是 `pe`（PE），以及采用 `pb_mrq`（PB(MRQ)）还是 `pb`（PB）

## ⏳ 请确认

请选择：
- **按原需求筛选** — 直接按您的条件执行
- **采纳建议后筛选** — 添加以上改进条件后再执行
```

当前日期：{curr_date}
只分析需求，不推荐股票，不调用工具。
"""

        if phase == "planning":
            screening_fields_markdown = build_screening_fields_markdown(public_only=True)
            return f"""你是一位专业的 A 股选股专家。用户已确认选股需求，请制定详细的执行计划。

## 可用工具清单（严格限于以下工具，不得使用其他工具名）

{tool_summary}

## `screen_stocks_by_criteria` 支持的筛选字段

{screening_fields_markdown}

支持的操作符：> < >= <= == != between in not_in contains

**注意**：不支持 audit_opinion_type（审计意见类型）、margin_of_safety_score（自定义安全边际评分）等字段。
若用户需求涉及这些条件，请在计划中说明将用现有字段近似替代，或诚实告知此限制。

## 推荐两步法工作流

**第一步（宽口径批量筛选）**：调用 `screen_stocks_by_criteria`，设置 limit=50，按硬性指标（PE(TTM)/PE、PB(MRQ)/PB、市值、资产负债率、is_st 等）过滤候选池。
**第二步（盈利稳定性验证）**：将候选股票代码列表传给 `batch_check_profit_consistency`，一次查询验证近N年ROE稳定性。**禁止对每只股票单独重复查询财务数据。**

## 字段使用建议

- 估值口径必须显式写清，不要只写笼统的“PE/PB”：`pe` 表示 PE，`pe_ttm` 表示 PE(TTM)，`pb` 表示 PB，`pb_mrq` 表示 PB(MRQ)
- 如果用户只说“PE”但未说明口径，优先在计划中明确成你实际选择的字段，例如“使用 `pe_ttm`（PE(TTM)）<= 15”或“使用 `pe`（PE）<= 15”
- 如果用户只说“PB”但未说明口径，优先在计划中明确成你实际选择的字段，例如“使用 `pb`（PB）<= 1.5”或“使用 `pb_mrq`（PB(MRQ)）<= 1.5”
- 优先使用可比较的比率型指标做硬筛选，如 PE(TTM)/PE、PB(MRQ)/PB、ROE、毛利率、资产负债率、流动比率、股息率
- `revenue_ttm`、`net_profit_ttm`、`n_cashflow_act` 更适合作为质量补充条件，不宜单独作为唯一标准
- 如果用户强调“现金流好”“利润扎实”“财务稳健”，优先考虑 `n_cashflow_act > 0`、`net_profit_ttm > 0`、`debt_to_assets`、`current_ratio`
- 如果用户强调“高分红”“防御型”，优先考虑 `dividend_yield` 并结合 `debt_to_assets`、`n_cashflow_act`
- 如果用户强调“财报最新”“只看最新财报”，可通过 `report_period` 增加约束

## 股票关注列表联动规则

- 若用户明确要求“筛选完成后加入股票关注列表”或“把上次推荐加入股票关注列表”，可在最终推荐确定后调用 `add_stocks_to_favorites`
- 若用户明确要求“加标签/打标签/标记”（如“打上巴菲特标签”），优先调用 `add_stocks_to_favorites` 并传入 `tags`
- 若用户明确要求放入某个分类/分组（如“银行”“待分析”），可调用 `add_stock_to_watchlist`，必要时先用 `list_watchlist_groups` 查看现有分类
- “标签”和“分组”不是同一概念：标签写入股票关注列表的 `tags`，分组写入 watchlist group
- 未明确提出股票关注列表操作时，不要主动添加

## 你的任务：执行计划说明

**不要调用任何工具，不要推荐股票。** 请详细说明你打算如何执行此次筛选：

1. **筛选策略**：总结最终采用的筛选条件，注明哪些需求能被现有字段支持，哪些无法精确筛选
2. **工具调用计划**：**仅使用上方可用工具清单中的工具**，列出工具名和具体参数
   - 步骤1：`screen_stocks_by_criteria` 的 conditions JSON 数组（每个条件的 field/operator/value），limit 建议 30-50
    - 若使用估值字段，必须在文字说明里同步写明展示口径，例如“`pe_ttm`（PE(TTM)）”“`pb_mrq`（PB(MRQ)）”
   - 步骤2（如需验证盈利稳定性）：`batch_check_profit_consistency`，传入步骤1的候选股代码列表
3. **数据处理**：说明如何从工具返回结果中选出最终 5 只股票（排序依据、优先级等）
4. **限制说明**：诚实告知用户哪些条件无法精确筛选（如审计意见类型、自定义安全边际评分）
5. **请求批准**：询问用户是否同意该方案

回复格式：
```
## 🔧 执行计划

### 筛选条件（最终版）
- PE(TTM) < xxx（使用 `pe_ttm` 字段）
- 市值 > 50亿（现有字段支持）
- 资产负债率 ≤ 60%（debt_to_assets 字段支持）
- 非ST股（is_st 字段支持）
- 近3年ROE稳定（batch_check_profit_consistency 工具支持）

### 工具调用
**步骤 1**：调用 `screen_stocks_by_criteria`
- conditions: [{{{{"field": "pe_ttm", "operator": "<", "value": 15}}}}, {{{{"field": "pb_mrq", "operator": "<=", "value": 1.5}}}}, {{{{"field": "total_mv", "operator": ">", "value": 50}}}}, {{{{"field": "is_st", "operator": "==", "value": false}}}}]
- limit: 50
- order_by_field: "pb_mrq"
- order_direction: "asc"

**步骤 2**：调用 `batch_check_profit_consistency`（对步骤1的候选股批量验证盈利稳定性）
- stock_codes_json: 步骤1返回的全部股票代码列表
- years: 3
- threshold_cv: 0.3

### 数据处理
- 从步骤2结果中筛选"盈利稳定"的股票，按 PB(MRQ) 升序取前 5 只
- 确保行业不重叠

## ✅ 请确认

以上是我的执行方案，请选择：
- **执行筛选方案** — 按此方案立即执行
- **重新描述需求** — 重新调整筛选条件
```

当前日期：{curr_date}
只说明计划，不调用工具，不推荐股票。**严禁使用工具清单以外的工具名。**
"""

        # phase == "result"
        intent_hint = ""
        if intent:
            intent_type = intent.get("intent")
            if intent_type == "adjustment":
                target = intent.get("adjustment_target")
                direction = intent.get("adjustment_direction")
                params = intent.get("explicit_parameters")
                intent_hint = f"""
## 当前用户意图分析（重要）

用户希望**调整筛选条件**：
- 调整目标：{target or '未知指标'}
- 调整方向：{'放宽条件' if direction == 'loosen' else '收紧条件' if direction == 'tighten' else '未知'}
- 明确参数：{params or '用户未明确给出具体数值，请根据对话历史中的建议推断'}

请仔细阅读对话历史，找到之前的筛选条件，然后按用户意图调整后重新筛选。
特别注意：如果历史中助手给出了具体的调整建议表格（如"放宽 ROE > 15% → ROE > 10%"），请优先采用那个建议值。
"""
            elif intent_type == "approval":
                intent_hint = """
## 当前用户意图分析（重要）

用户已**批准执行计划**，请按之前规划的参数立即执行筛选。
"""

        return f"""你是一位专业的 A 股选股专家。用户已批准执行计划，请立即执行筛选并推荐股票。
{intent_hint}
## 你的任务：执行筛选

1. **调用工具**：按之前计划的参数调用 `screen_stocks_by_criteria` 等工具获取数据
2. **精选推荐**：每次严格推荐 **5 只** 最符合条件的股票
3. **结构化输出**：在回答最后包含以下 JSON 代码块

```json
{{{{
  "stocks": [
    {{{{
      "code": "600519",
      "name": "贵州茅台",
      "industry": "白酒",
      "price": 1680.00,
      "pe": 25.3,
    "pe_display_label": "PE",
      "pb": 8.5,
    "pb_display_label": "PB",
            "roe": 32.1,
            "roa": 18.6,
            "gross_margin": 51.2,
            "netprofit_margin": 24.8,
            "dividend_yield": 3.1,
            "debt_to_assets": 18.5,
            "assets_to_eqt": 1.42,
            "current_ratio": 4.2,
            "quick_ratio": 3.8,
            "cash_ratio": 1.9,
            "revenue_ttm": 123456789000,
            "net_profit_ttm": 45678900000,
            "n_cashflow_act": 39876500000,
            "report_period": "20250930",
      "pct_change": 2.1,
      "reason": "白马股龙头，业绩稳定增长，估值处于历史中位"
    }}}}
  ]
}}}}
```

## 规则

- 当前日期：{curr_date}
- 默认最多执行 **两轮数据工具调用**：
    - 第 1 轮：`screen_stocks_by_criteria`
    - 第 2 轮：仅当确有必要时才调用 `batch_check_profit_consistency`
- 若步骤 1 已能直接选出最终推荐，则**跳过**步骤 2，直接输出最终结果
- 一旦已有足够数据生成最终推荐，**立即停止继续调用工具**
- 不要为了“凑满信息”反复改阈值、重复筛选或重新扩大范围；当前条件下结果不足时，应直接说明限制
- 每次推荐恰好 5 只股票，不多不少
- 推荐理由要具体，结合数据说话
- 若工具结果中已提供 ROE、股息率、资产负债率、流动比率、财报期，优先一并放入 JSON 字段，便于前端直接展示
- 若工具结果中已提供 ROA、毛利率、净利率、滚动营收、滚动净利润、经营现金流、权益乘数、速动比率、现金比率，也可一并放入 JSON 字段，便于前端直接展示
- 若实际筛选或展示口径使用 `pe_ttm` / `pb_mrq`，必须把对应数值写入 `pe` / `pb` 字段，并分别补充 `pe_display_label` / `pb_display_label`，严禁把 `PE(TTM)` 写成 `PE`、把 `PB(MRQ)` 写成 `PB`
- 如果用户要求调整（如"换个行业""PE 再低点"），直接重新调用工具调整筛选
- 如果用户明确要求将当前推荐结果加入股票关注列表，可调用 `add_stocks_to_favorites` 一次性添加；若同时要求“打标签/标记”，把标签通过 `tags` 参数一并写入
- 如果用户明确要求将当前推荐结果放入某个分类/分组，可调用 `add_stock_to_watchlist`，分组不存在时允许自动创建，例如“银行”“待分析”
- 若用户同时要求“加入自选 + 打标签 + 放入分组”，应先调用 `add_stocks_to_favorites` 写入 tags，再调用 `add_stock_to_watchlist`
- 不给出具体的买入/卖出建议，只做选股推荐和分析
- 只推荐 A 股（沪深两市）
"""

    def _extract_stocks(self, reply: str) -> list:
        """从 LLM 回复中提取结构化股票列表"""
        pattern = r'```json\s*(\{[\s\S]*?\})\s*```'
        match = re.search(pattern, reply)
        if match:
            try:
                data = json.loads(match.group(1))
                return data.get("stocks", [])
            except json.JSONDecodeError:
                pass
        return []

    async def _save_message(
        self, user_id: str, conversation_id: str, user_msg: str, assistant_reply: str,
        tools_used: List[str], stocks: list, phase: str, is_fallback: bool = False,
    ) -> None:
        """持久化对话消息到 screening_conversations"""
        now = datetime.now(timezone.utc)
        user_entry = {"role": "user", "content": user_msg, "timestamp": now}
        assistant_entry = {
            "role": "assistant",
            "content": assistant_reply,
            "tools_used": tools_used,
            "stocks": stocks,
            "phase": phase,
            "is_fallback": is_fallback,
            "timestamp": now,
        }
        await self._db.screening_conversations.update_one(
            {"user_id": user_id, "conversation_id": conversation_id},
            {
                "$push": {
                    "messages": {
                        "$each": [user_entry, assistant_entry],
                        "$slice": -SCREENING_CONVERSATION_LIMIT,
                    }
                },
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "title": self._build_conversation_title(user_msg),
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def run_direct_screening(
        self,
        user_id: str,
        criteria: str,
        max_stocks: int = 10,
    ) -> Dict[str, Any]:
        """
        直接执行选股（单轮，不经过确认/规划阶段）。
        供 MCP / API 等外部调用，无需多轮对话。

        Args:
            user_id: 用户 ID（用于 LLM 配额等）
            criteria: 筛选条件（自然语言），如 "PE小于20的科技股"
            max_stocks: 最多返回股票数量，默认 10

        Returns:
            {"reply": str, "stocks": list, "phase": "result"}
        """
        if not await self._ensure_client():
            return {
                "reply": "智能筛选暂时不可用，请检查 LLM 配置。",
                "stocks": [],
                "phase": "result",
            }
        set_current_user_id(user_id)
        tools_used: List[str] = []

        async def _run_direct_flow() -> tuple[str, List[str], list]:
            planning_messages = [
                Message(
                    role=MessageRole.SYSTEM,
                    content=(
                        "【直接执行模式】用户要求你在单轮内给出可执行的选股方案。"
                        "你现在只负责生成 planning 阶段的工具执行计划，不要调用工具，不要输出最终股票推荐。"
                        f"最终展示股票数量上限为 {max_stocks} 只。\n\n"
                        + self._get_system_prompt("planning", self._build_tool_summary(self._result_openai_tools))
                    ),
                ),
                Message(
                    role=MessageRole.USER,
                    content=f"请根据以下条件直接生成筛选执行计划，无需确认环节。\n\n条件：{criteria}",
                ),
            ]
            planning_response = await self._llm_client.achat(
                planning_messages,
                tools=None,
                log_payloads=True,
                payload_log_label="intelligent_screening:direct_planning",
            )
            planning_content = (planning_response.content if planning_response else None) or ""
            locked_plan = self._extract_locked_execution_plan([
                {"role": "assistant", "phase": "planning", "content": planning_content}
            ])
            if not locked_plan:
                raise ValueError("未能解析出可执行的筛选计划，请补充更明确的筛选条件后重试。")

            locked_plan["screen"]["limit"] = min(int(locked_plan["screen"].get("limit", max_stocks)), max_stocks)
            return await self._run_locked_result_execution(criteria, locked_plan)

        try:
            started_at = datetime.now(timezone.utc)
            reply, tools_used, stocks = await asyncio.wait_for(
                _run_direct_flow(),
                timeout=SCREENING_RESULT_TIMEOUT_SECONDS,
            )
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            logger.info(f"[智能筛选] run_direct_screening 完成 elapsed={elapsed:.2f}s tools_used={len(tools_used)}")
        except asyncio.TimeoutError:
            reply = self._build_timeout_reply(SCREENING_RESULT_TIMEOUT_SECONDS)
            stocks = []
            tools_used = []
        except Exception as e:
            logger.exception("[智能筛选] run_direct_screening 失败")
            reply = f"处理选股请求时发生错误：{str(e)}。请稍后重试。"
            stocks = []
        if not stocks and "screen_stocks_by_criteria" in tools_used:
            reply = self._build_no_match_reply(criteria)
            stocks = []

        return {"reply": reply, "stocks": stocks, "phase": "result", "is_fallback": False}

    async def get_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> tuple[Optional[str], list]:
        """获取完整对话历史"""
        doc = await self._get_conversation_doc(user_id, conversation_id)
        if not doc:
            return conversation_id, []
        return doc.get("conversation_id"), doc.get("messages", [])

    async def list_conversations(self, user_id: str) -> list:
        """获取会话列表摘要"""
        cursor = self._db.screening_conversations.find({"user_id": user_id}).sort([
            ("updated_at", -1),
            ("created_at", -1),
        ])
        docs = await cursor.to_list(length=100)

        items = []
        for raw_doc in docs:
            doc = await self._ensure_conversation_doc_identity(raw_doc)
            messages = doc.get("messages") or []
            preview = ""
            for item in reversed(messages):
                content = str(item.get("content") or "").strip()
                if content:
                    preview = re.sub(r"\s+", " ", content)[:80]
                    break

            items.append({
                "conversation_id": doc.get("conversation_id"),
                "title": doc.get("title") or self._build_conversation_title(preview),
                "preview": preview,
                "message_count": len(messages),
                "created_at": self._format_dt(doc.get("created_at")),
                "updated_at": self._format_dt(doc.get("updated_at")),
            })

        return items

    async def clear_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> None:
        """清空对话历史"""
        if conversation_id:
            await self._db.screening_conversations.delete_one({
                "user_id": user_id,
                "conversation_id": conversation_id,
            })
            return

        doc = await self._get_conversation_doc(user_id, None)
        if not doc:
            return
        await self._db.screening_conversations.delete_one({"_id": doc["_id"]})

