from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from core.embedded_nanobot.agent.context import ContextBuilder
from core.embedded_nanobot.agent.hook import AgentHook, AgentHookContext
from core.embedded_nanobot.agent.memory import MemoryConsolidator
from core.embedded_nanobot.agent.runner import AgentRunSpec, AgentRunner
from core.embedded_nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from core.embedded_nanobot.agent.tools.tradingagents_bridge import TradingAgentsRegistryTool
from core.embedded_nanobot.agent.tools.registry import ToolRegistry
from core.embedded_nanobot.agent.tools.shell import ExecTool
from core.embedded_nanobot.agent.tools.web import WebFetchTool, WebSearchConfig, WebSearchTool
from core.embedded_nanobot.command.builtin import register_builtin_commands
from core.embedded_nanobot.command.router import CommandContext, CommandRouter
from core.embedded_nanobot.cron.service import CronService
from core.embedded_nanobot.providers.unified import TradingAgentsLLMProvider
from core.embedded_nanobot.session.manager import SessionManager
from core.embedded_nanobot.utils.helpers import estimate_prompt_tokens, estimate_prompt_tokens_chain, sanitize_content_blocks, sanitize_tool_result_content, strip_think
from core.tools.config import ToolCategory


logger = logging.getLogger(__name__)


@dataclass
class ExecToolConfig:
    enable: bool = True
    timeout: int = 120
    path_append: str = ""


@dataclass(frozen=True)
class QueryIntent:
    raw_query: str
    normalized_query: str
    matched_domains: tuple[str, ...]
    reason_codes: tuple[str, ...]
    decision_source: str
    is_preview_request: bool
    is_agent_builder_request: bool
    is_skill_creation_request: bool
    prefers_callable_agent: bool
    callable_keyword: str


@dataclass(frozen=True)
class CategoryFeatureRule:
    keywords: tuple[str, ...]
    score: int = 10


class EmbeddedNanobotRuntime:
    CORE_TOOL_NAMES = {
        "read_file",
        "write_file",
        "edit_file",
        "list_dir",
        "exec",
        "web_search",
        "web_fetch",
    }
    MAX_DYNAMIC_TOOLS = 16
    AGENT_BUILDER_TOOL_IDS = {
        "prepare_agent_requirement_intake",
        "prepare_agent_generation_confirmation",
        "search_project_capabilities",
        "inspect_runtime_agent_configs",
        "inspect_agent_blueprints",
        "get_agent_blueprint_details",
        "inspect_agent_workshop_assets",
        "inspect_prompt_templates",
        "get_prompt_template_detail",
        "get_current_thread_effective_prompt_template",
        "get_effective_prompt_template",
        "create_or_update_agent_workshop_draft",
        "analyze_agent_workshop_gaps",
        "generate_agent_workshop_tooling_plan",
        "build_agent_workshop_version",
        "evaluate_agent_workshop_version",
        "iterate_agent_workshop_version",
        "debug_agent_workshop_version",
        "run_agent_workshop_real_data_test",
        "publish_agent_workshop_version",
        "create_or_update_runtime_agent_config",
        "create_or_update_universal_agent_prompt_template",
        "bind_agent_tools_and_validate_candidate",
        "generate_confirmed_candidate_agent",
    }
    SKILL_CREATION_TOOL_IDS = {
        "start_external_skill_generation_session",
        "respond_to_external_skill_generation_session",
        "preview_external_skill_spec",
        "generate_confirmed_external_skill",
        "inspect_external_skill_generation_session",
    }
    CALLABLE_AGENT_TOOL_IDS = {
        "list_callable_agents",
        "execute_callable_agent",
    }
    PREVIEW_HINTS = {
        "样式",
        "模板",
        "骨架",
        "预览",
        "输出结构",
        "字段结构",
        "什么样",
        "preview",
    }
    AGENT_BUILDER_HINTS = {
        "agent",
        "智能体",
        "蓝图",
        "工作流",
        "创建agent",
        "生成agent",
        "创建 agent",
        "生成 agent",
    }
    SKILL_CREATION_HINTS = {
        "skill",
        "技能",
        "可复用",
        "复用",
        "能力缺口",
        "能力沉淀",
        "external skill",
    }
    AGENT_FIRST_VERB_HINTS = (
        "帮我做",
        "给我做",
        "做一下",
        "分析一下",
        "帮我分析",
        "研究一下",
        "看一下",
        "生成报告",
        "输出报告",
        "完整分析",
        "全面分析",
        "直接分析",
    )
    AGENT_FIRST_DOMAIN_HINTS = (
        "估值",
        "基本面",
        "财务",
        "复盘",
        "风险",
        "研究",
        "行业",
        "情绪",
        "etf",
        "技术面",
        "市场",
    )
    CATEGORY_FEATURE_RULES = {
        ToolCategory.FUNDAMENTALS.value: CategoryFeatureRule(keywords=("估值", "基本面", "财务", "利润", "现金流", "分红", "roe", "pe", "pb", "peg", "ps", "股息")),
        ToolCategory.MARKET.value: CategoryFeatureRule(keywords=("行情", "市场", "板块", "指数", "大盘", "k线", "技术面", "成交量", "资金流", "北向")),
        ToolCategory.NEWS.value: CategoryFeatureRule(keywords=("新闻", "公告", "资讯", "消息", "舆情")),
        ToolCategory.SOCIAL.value: CategoryFeatureRule(keywords=("情绪", "社交", "热度", "讨论", "舆论")),
        ToolCategory.ASSISTANT_OPS.value: CategoryFeatureRule(keywords=("持仓", "报告", "计划", "自选股", "提醒", "主题", "会话", "agent", "智能体", "蓝图", "工作流")),
        ToolCategory.SCREENING.value: CategoryFeatureRule(keywords=("筛选", "选股", "条件", "批量")),
        ToolCategory.TRADE_REVIEW.value: CategoryFeatureRule(keywords=("复盘", "交易记录", "回顾")),
        ToolCategory.MCP.value: CategoryFeatureRule(keywords=("mcp",)),
        ToolCategory.UTILITY.value: CategoryFeatureRule(keywords=("工具", "文件", "目录", "执行命令")),
        ToolCategory.EXTERNAL.value: CategoryFeatureRule(keywords=("外部", "skill", "技能", "复用", "可复用", "能力缺口", "能力沉淀")),
    }
    QUERY_STOP_TERMS = {
        "你好", "请问", "帮我", "一下", "一个", "这个", "那个", "现在", "最新", "当前", "什么", "怎么", "可以", "需要", "分析", "看看",
    }

    def __init__(self, provider: TradingAgentsLLMProvider, workspace: Path, model: str | None = None, max_iterations: int = 100, context_window_tokens: int = 65536, web_search_config: WebSearchConfig | None = None, web_proxy: str | None = None, exec_config: ExecToolConfig | None = None, cron_service: CronService | None = None, restrict_to_workspace: bool = False, timezone: str | None = None, max_session_messages: int | None = 1000, memory_db: Any | None = None):
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.memory_db = memory_db
        self.max_iterations = max_iterations
        self.context_window_tokens = context_window_tokens
        self.web_search_config = web_search_config or WebSearchConfig()
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.max_session_messages = max_session_messages
        self._start_time = time.time()
        self._last_usage: dict[str, int] = {}
        self._active_tasks: dict[str, list[asyncio.Task]] = {}
        self._background_tasks: list[asyncio.Task] = []
        self.context = ContextBuilder(workspace, timezone=timezone)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.runner = AgentRunner(provider)
        self.memory_consolidator = MemoryConsolidator(workspace=workspace, provider=provider, model=self.model, sessions=self.sessions, context_window_tokens=context_window_tokens, build_messages=self.context.build_messages, get_tool_definitions=self.tools.get_definitions, max_completion_tokens=provider.generation.max_tokens, db=memory_db)
        self.commands = CommandRouter()
        register_builtin_commands(self.commands)
        self._capability_sync_lock = asyncio.Lock()
        self._dynamic_tool_names: set[str] = set()
        self._register_default_tools()
        self._default_tool_names = set(self.tools.tool_names)

    @staticmethod
    def _extract_query_terms(text: str) -> list[str]:
        lowered = text.lower()
        terms: list[str] = []
        terms.extend(re.findall(r"[a-z0-9_]{2,}", lowered))
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            if len(chunk) <= 4:
                terms.append(chunk)
            else:
                for size in (2, 3, 4):
                    for index in range(0, len(chunk) - size + 1):
                        terms.append(chunk[index:index + size])
        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            if term in seen or term in EmbeddedNanobotRuntime.QUERY_STOP_TERMS:
                continue
            seen.add(term)
            deduped.append(term)
        return deduped

    @staticmethod
    def _contains_any_keyword(text: str, keywords: tuple[str, ...] | set[str]) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    @staticmethod
    def _extract_symbol_from_text(text: str) -> str | None:
        content = str(text or "")
        match = re.search(r"\b(?:sh|sz|bj|hk)\.\d{5,6}\b|\b\d{6}\b", content, re.IGNORECASE)
        if not match:
            return None
        return match.group(0).upper()

    @staticmethod
    def _build_object_binding(thread_context: dict[str, Any], user_message: str) -> tuple[str | None, str | None, str | None]:
        explicit_object_type = str(thread_context.get("object_type") or "").strip() or None
        explicit_object_key = str(thread_context.get("object_key") or "").strip() or None
        explicit_symbol = str(thread_context.get("symbol") or "").strip() or None

        if explicit_object_key and explicit_object_type:
            return explicit_object_type, explicit_object_key, explicit_symbol

        inferred_symbol = explicit_symbol or EmbeddedNanobotRuntime._extract_symbol_from_text(user_message)
        if explicit_object_key and not explicit_object_type:
            return None, explicit_object_key, inferred_symbol
        if inferred_symbol:
            return "stock", inferred_symbol, inferred_symbol
        return explicit_object_type, explicit_object_key, explicit_symbol

    @classmethod
    def _match_domain_hints(cls, user_message: str) -> tuple[str, ...]:
        lowered = str(user_message or "").lower()
        matched: list[str] = []
        for keyword in cls.AGENT_FIRST_DOMAIN_HINTS:
            if keyword.lower() in lowered and keyword not in matched:
                matched.append(keyword)
        return tuple(matched)

    @classmethod
    def _match_category_features(cls, user_message: str) -> dict[str, list[str]]:
        lowered = str(user_message or "").lower()
        matched: dict[str, list[str]] = {}
        for category, rule in cls.CATEGORY_FEATURE_RULES.items():
            hits = [keyword for keyword in rule.keywords if keyword.lower() in lowered]
            if hits:
                matched[category] = hits
        return matched

    @staticmethod
    def _dedupe_preserve_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    @classmethod
    def _infer_callable_agent_keyword(cls, user_message: str) -> str:
        query = str(user_message or "").lower()
        if any(term in query for term in ("估值", "pe", "pb", "peg", "ps", "dcf")):
            return "估值"
        if any(term in query for term in ("复盘", "交易回顾", "交易记录")):
            return "复盘"
        if any(term in query for term in ("风险", "回撤", "波动")):
            return "风险"
        if "etf" in query:
            return "ETF"
        if any(term in query for term in ("行业", "产业链")):
            return "行业"
        if any(term in query for term in ("情绪", "舆情", "热度")):
            return "情绪"
        if any(term in query for term in ("基本面", "财务")):
            return "基本面"
        return "分析"

    @classmethod
    def _classify_query_intent(cls, user_message: str) -> QueryIntent:
        query = str(user_message or "").strip()
        if not query:
            return QueryIntent(
                raw_query="",
                normalized_query="",
                matched_domains=(),
                reason_codes=(),
                decision_source="rule",
                is_preview_request=False,
                is_agent_builder_request=False,
                is_skill_creation_request=False,
                prefers_callable_agent=False,
                callable_keyword="分析",
            )

        lowered = query.lower()
        is_preview_request = cls._contains_any_keyword(lowered, cls.PREVIEW_HINTS)
        is_agent_builder_request = cls._contains_any_keyword(lowered, cls.AGENT_BUILDER_HINTS)
        is_skill_creation_request = cls._contains_any_keyword(lowered, cls.SKILL_CREATION_HINTS)
        matched_domains = cls._match_domain_hints(query)
        has_domain_hint = bool(matched_domains)
        has_verb_hint = cls._contains_any_keyword(query, cls.AGENT_FIRST_VERB_HINTS)
        has_stock_code = bool(re.search(r"\b\d{6}\b", query))
        has_analysis_result_hint = bool(re.search(r"(估值|复盘|风险|研究|行业|情绪|技术面|基本面).{0,8}(分析|报告)", query, re.IGNORECASE))
        prefers_callable_agent = False
        reason_codes: list[str] = []

        if is_preview_request:
            reason_codes.append("preview_hint")
        if is_agent_builder_request:
            reason_codes.append("agent_builder_hint")
        if is_skill_creation_request:
            reason_codes.append("skill_creation_hint")
        if has_domain_hint:
            reason_codes.append("domain_hint")
        if has_verb_hint:
            reason_codes.append("verb_hint")
        if has_stock_code:
            reason_codes.append("stock_code")
        if has_analysis_result_hint:
            reason_codes.append("analysis_result_pattern")

        if not is_preview_request and not is_agent_builder_request and not is_skill_creation_request:
            if has_domain_hint and (has_verb_hint or has_stock_code):
                prefers_callable_agent = True
                reason_codes.append("callable_agent_preferred")
            elif has_analysis_result_hint:
                prefers_callable_agent = True
                reason_codes.append("callable_agent_preferred")

        return QueryIntent(
            raw_query=query,
            normalized_query=lowered,
            matched_domains=matched_domains,
            reason_codes=tuple(reason_codes),
            decision_source="rule",
            is_preview_request=is_preview_request,
            is_agent_builder_request=is_agent_builder_request,
            is_skill_creation_request=is_skill_creation_request,
            prefers_callable_agent=prefers_callable_agent,
            callable_keyword=cls._infer_callable_agent_keyword(query),
        )

    @classmethod
    def _should_prefer_callable_agent(cls, user_message: str) -> bool:
        return cls._classify_query_intent(user_message).prefers_callable_agent

    @classmethod
    def _should_suppress_callable_agent_tools(cls, user_message: str) -> bool:
        intent = cls._classify_query_intent(user_message)
        return intent.is_preview_request or intent.is_agent_builder_request or intent.is_skill_creation_request

    @classmethod
    def _build_route_decision(cls, intent: QueryIntent, category_matches: dict[str, list[str]]) -> dict[str, Any]:
        if intent.is_preview_request:
            primary_intent = "preview_request"
        elif intent.is_agent_builder_request:
            primary_intent = "agent_builder_request"
        elif intent.is_skill_creation_request:
            primary_intent = "skill_creation_request"
        elif intent.prefers_callable_agent:
            primary_intent = "analysis_task"
        elif category_matches:
            primary_intent = "tool_lookup"
        else:
            primary_intent = "general_request"

        suppression_reasons = [
            code for code in intent.reason_codes
            if code in {"preview_hint", "agent_builder_hint", "skill_creation_hint"}
        ]
        if intent.prefers_callable_agent:
            callable_agent_mode = "preferred"
        elif suppression_reasons:
            callable_agent_mode = "suppressed"
        else:
            callable_agent_mode = "neutral"

        matched_categories = cls._dedupe_preserve_order(list(category_matches.keys()))
        return {
            "primary_intent": primary_intent,
            "decision_source": intent.decision_source,
            "callable_agent_mode": callable_agent_mode,
            "reason_codes": list(intent.reason_codes),
            "suppression_reasons": suppression_reasons,
            "matched_categories": matched_categories,
            "callable_keyword": intent.callable_keyword if intent.prefers_callable_agent else "",
        }

    @staticmethod
    def _should_use_llm_route_fallback(route_decision: dict[str, Any]) -> bool:
        suppression_reasons = set(route_decision.get("suppression_reasons") or [])
        reason_codes = set(route_decision.get("reason_codes") or [])
        has_domain_hint = "domain_hint" in reason_codes
        has_strong_analysis_cue = bool(reason_codes.intersection({"verb_hint", "stock_code"}))
        return bool(suppression_reasons) and has_domain_hint and has_strong_analysis_cue

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any] | None:
        try:
            data = json.loads(str(raw or "").strip())
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    @classmethod
    def _build_intent_from_fallback_decision(
        cls,
        query: str,
        base_intent: QueryIntent,
        fallback_decision: dict[str, Any],
    ) -> QueryIntent | None:
        primary_intent = str(fallback_decision.get("primary_intent") or "").strip()
        prefer_callable_agent = bool(fallback_decision.get("prefer_callable_agent", False))
        if primary_intent not in {
            "analysis_task",
            "preview_request",
            "agent_builder_request",
            "skill_creation_request",
            "tool_lookup",
            "general_request",
        }:
            return None

        reason_codes = list(base_intent.reason_codes)
        reason_codes.append("llm_route_fallback")
        if prefer_callable_agent and "callable_agent_preferred" not in reason_codes:
            reason_codes.append("callable_agent_preferred")

        return QueryIntent(
            raw_query=base_intent.raw_query,
            normalized_query=base_intent.normalized_query,
            matched_domains=base_intent.matched_domains,
            reason_codes=tuple(cls._dedupe_preserve_order(reason_codes)),
            decision_source="llm_fallback",
            is_preview_request=primary_intent == "preview_request",
            is_agent_builder_request=primary_intent == "agent_builder_request",
            is_skill_creation_request=primary_intent == "skill_creation_request",
            prefers_callable_agent=(primary_intent == "analysis_task") or prefer_callable_agent,
            callable_keyword=cls._infer_callable_agent_keyword(query),
        )

    async def _resolve_llm_route_fallback(
        self,
        user_message: str,
        tool_selection: dict[str, Any],
    ) -> tuple[QueryIntent | None, dict[str, Any]]:
        route_decision = tool_selection.get("route_decision") or {}
        if not self._should_use_llm_route_fallback(route_decision):
            return None, {"considered": False, "used": False, "status": "skipped"}

        prompt = (
            "You are a strict route classifier for an embedded coding agent.\n"
            "Classify only ambiguous user requests that mix analysis signals with preview/builder/skill signals.\n"
            "Return JSON only with keys: primary_intent, prefer_callable_agent, confidence, rationale.\n"
            "Allowed primary_intent values: analysis_task, preview_request, agent_builder_request, skill_creation_request, tool_lookup, general_request.\n"
            "Use prefer_callable_agent=true only when the request is primarily asking the system to perform a complete analysis task.\n"
            "If the request is mainly asking for report style/preview, creating an agent/blueprint, or creating a reusable skill, keep prefer_callable_agent=false."
        )
        user_payload = {
            "query": user_message,
            "rule_route_decision": route_decision,
            "intent": tool_selection.get("intent") or {},
            "category_matches": tool_selection.get("category_matches") or {},
        }
        response = await self.provider.chat_with_retry(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            tools=None,
            model=self.model,
            max_tokens=180,
            temperature=0,
            tool_choice="none",
        )
        payload = self._parse_json_object(response.content or "")
        if response.finish_reason == "error" or payload is None:
            return None, {
                "considered": True,
                "used": False,
                "status": "invalid_response",
                "raw_response": response.content or "",
            }
        confidence = str(payload.get("confidence") or "").strip().lower()
        if confidence not in {"high", "medium"}:
            return None, {
                "considered": True,
                "used": False,
                "status": "low_confidence",
                "model_decision": payload,
            }
        base_intent = QueryIntent(
            raw_query=str(user_message or "").strip(),
            normalized_query=str(user_message or "").strip().lower(),
            matched_domains=tuple(tool_selection.get("intent", {}).get("matched_domains") or []),
            reason_codes=tuple(tool_selection.get("intent", {}).get("reason_codes") or []),
            decision_source="rule",
            is_preview_request=bool(tool_selection.get("intent", {}).get("preview")),
            is_agent_builder_request=bool(tool_selection.get("intent", {}).get("agent_builder")),
            is_skill_creation_request=bool(tool_selection.get("intent", {}).get("skill_creation")),
            prefers_callable_agent=bool(tool_selection.get("intent", {}).get("prefers_callable_agent")),
            callable_keyword=self._infer_callable_agent_keyword(user_message),
        )
        refined_intent = self._build_intent_from_fallback_decision(user_message, base_intent, payload)
        if refined_intent is None:
            return None, {
                "considered": True,
                "used": False,
                "status": "unsupported_decision",
                "model_decision": payload,
            }
        return refined_intent, {
            "considered": True,
            "used": True,
            "status": "applied",
            "model_decision": payload,
        }

    @classmethod
    def _build_agent_first_guidance(cls, user_message: str, tool_names: set[str]) -> str | None:
        intent = cls._classify_query_intent(user_message)
        if not intent.prefers_callable_agent:
            return None
        if not cls.CALLABLE_AGENT_TOOL_IDS.issubset(tool_names):
            return None

        keyword = intent.callable_keyword
        return (
            "# Agent-first execution rule\n\n"
            "The current user request looks like an integrated analysis task rather than a tool-building or style-preview task. "
            "Prefer reusable callable agents before decomposing the task into low-level tools.\n\n"
            f"Recommended first step: call list_callable_agents(keyword='{keyword}') to check whether an existing agent already covers this task.\n"
            "If a suitable callable agent exists, call execute_callable_agent first. "
            "Only fall back to bottom-level tools when no suitable callable agent exists, or when the user explicitly asks for tool-level decomposition."
        )

    @classmethod
    def _build_agent_builder_guidance(cls, user_message: str, tool_names: set[str], thread_context: dict[str, Any] | None = None) -> str | None:
        intent = cls._classify_query_intent(user_message)
        if not intent.is_agent_builder_request:
            return None

        message_text = f"{user_message} {user_message.lower()}"
        thread_context = dict(thread_context or {})
        spec_id = str(thread_context.get("spec_id") or "").strip()
        version_id = str(thread_context.get("version_id") or "").strip()
        version_status = str(thread_context.get("version_status") or "").strip()
        workshop_session_id = str(thread_context.get("workshop_session_id") or "").strip()

        guidance_lines = [
            "# Agent Workshop governance rule",
            "",
            "Treat Agent Workshop assets and runtime-configured agents as live state, not as something you can infer from earlier conversation memory.",
            "When the user asks to inspect, modify, continue, iterate, debug, test, or publish an existing agent or version, verify the current state first before answering or taking the next action.",
        ]

        context_bits = []
        if spec_id:
            context_bits.append(f"spec_id={spec_id}")
        if version_id:
            context_bits.append(f"version_id={version_id}")
        if version_status:
            context_bits.append(f"version_status={version_status}")
        if workshop_session_id:
            context_bits.append(f"workshop_session_id={workshop_session_id}")
        spec_name = str(thread_context.get("spec_name") or "").strip()
        if context_bits:
            guidance_lines.extend([
                "",
                f"Current thread context already points to: {', '.join(context_bits)}.",
                "Prefer treating this thread context as the candidate target to verify first, rather than asking the user to restate which agent or version is being discussed.",
            ])
            if "inspect_agent_workshop_assets" in tool_names and (spec_id or version_id):
                exact_args = []
                if spec_id:
                    exact_args.append(f"spec_id='{spec_id}'")
                if version_id:
                    exact_args.append(f"version_id='{version_id}'")
                guidance_lines.append(
                    f"Preferred verification call for this thread: inspect_agent_workshop_assets({', '.join(exact_args)}) before falling back to keyword search."
                )
            elif "inspect_agent_workshop_assets" in tool_names and workshop_session_id:
                guidance_lines.append(
                    f"Preferred verification call for this thread: inspect_agent_workshop_assets(workshop_session_id='{workshop_session_id}') before falling back to keyword search."
                )
            if "inspect_runtime_agent_configs" in tool_names and spec_name:
                guidance_lines.append(
                    f"If Workshop inspection is empty but the runtime layer still needs checking, inspect_runtime_agent_configs(keyword='{spec_name}') is the preferred fallback."
                )

        if "inspect_agent_workshop_assets" in tool_names:
            guidance_lines.append(
                "Recommended first step for existing Workshop assets: call inspect_agent_workshop_assets before claiming which spec, version, prompt lineage, or published state currently exists."
            )
        if "inspect_runtime_agent_configs" in tool_names:
            guidance_lines.append(
                "Use inspect_runtime_agent_configs to confirm runtime-configured agent state, and keep it distinct from Workshop assets in agent_specs and agent_versions."
            )
        if "iterate_agent_workshop_version" in tool_names:
            guidance_lines.append(
                "A published or active Workshop version must not be edited in place. If the user wants to change an evaluated or published version, inspect the current asset first and then use iterate_agent_workshop_version to create the next iteration session instead of creating a brand-new unrelated agent."
            )
        if "create_or_update_agent_workshop_draft" in tool_names:
            guidance_lines.append(
                "create_or_update_agent_workshop_draft is only for syncing a newly confirmed candidate agent into a Draft. Do not pass an existing Workshop spec_id or version_id into that tool when the user is modifying a published or active version."
            )
        if "build_agent_workshop_version" in tool_names:
            guidance_lines.append(
                "After iteration or draft updates, use build_agent_workshop_version to produce the next testing candidate rather than describing version creation as a manual user-only step."
            )
        if "debug_agent_workshop_version" in tool_names:
            guidance_lines.append(
                "Use debug_agent_workshop_version only for prompt/runtime diagnosis, output preview, or investigating why a run failed. It does not persist an official evaluation record, does not change publish readiness, and must not be described as completed acceptance testing."
            )
        if "run_agent_workshop_real_data_test" in tool_names:
            guidance_lines.append(
                "Use run_agent_workshop_real_data_test for the official real-data acceptance step. A successful tool call is not the same as a pass result; acceptance depends on the recorded evaluation decision."
            )
        if "debug_agent_workshop_version" in tool_names and "run_agent_workshop_real_data_test" in tool_names:
            guidance_lines.append(
                "Disambiguation rule: if the user asks to test, validate, verify pass/fail, inspect evaluation results, explain why the version is still testing, or check publish readiness, choose run_agent_workshop_real_data_test instead of debug_agent_workshop_version."
            )
            if any(term in message_text for term in (
                "测试",
                "真数据",
                "验证",
                "验收",
                "评估",
                "通过",
                "发布",
                "still testing",
                "pass",
                "publish readiness",
            )):
                guidance_lines.append(
                    "The current request contains testing or acceptance language, so prefer run_agent_workshop_real_data_test unless the user explicitly asks for debug-only diagnosis."
                )
        if "publish_agent_workshop_version" in tool_names:
            guidance_lines.append(
                "Use publish_agent_workshop_version only after the latest official evaluation decision is pass and the user explicitly confirms publication in the current turn. A pass result only moves the version into publish-ready; it must not trigger automatic publication."
            )

        guidance_lines.extend([
            "Do not claim that an agent or version still exists, or claim that the current config is known, unless a live inspection tool has just confirmed that state.",
            "If Workshop assets are absent but runtime-configured agents still exist, describe that as runtime residue or config-layer state rather than as an active Workshop version.",
        ])
        return "\n".join(guidance_lines)

    @staticmethod
    def _merge_system_guidance(*guidance_blocks: str | None) -> str | None:
        parts = [str(block).strip() for block in guidance_blocks if str(block or "").strip()]
        if not parts:
            return None
        return "\n\n".join(parts)

    async def _recall_project_memory_guidance(
        self,
        *,
        user_message: str,
        tool_selection: dict[str, Any],
        thread_context: dict[str, Any] | None = None,
    ) -> str | None:
        if self.memory_db is None:
            return None
        if not tool_selection.get("agent_builder_governance", {}).get("enabled"):
            return None

        try:
            from app.models.project_memory import ProjectMemoryCategory
            from app.services.project_memory_service import get_project_memory_service

            del user_message, thread_context
            block = await get_project_memory_service(self.memory_db).build_prompt_block(
                categories=[
                    ProjectMemoryCategory.PROJECT_RULE.value,
                    ProjectMemoryCategory.GOVERNANCE_CONSTRAINT.value,
                    ProjectMemoryCategory.RESEARCH_TEMPLATE.value,
                ],
                max_items=5,
                max_chars=900,
            )
            if not block:
                return None
            return "# Agent Workshop project memory\n\nUse the following stable project rules and governance constraints as hard context for Agent Workshop reasoning.\n\n" + block
        except Exception as exc:
            logger.debug("EmbeddedNanobot project memory guidance skipped: %s", exc)
            return None

    def _log_agent_builder_lesson_recall_observation(
        self,
        *,
        source_stage: str,
        user_id: str,
        query: str,
        metadata_filters: dict[str, Any] | None,
        recalled: str,
        status: str,
        thread_context: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        clean_thread_context = dict(thread_context or {})
        payload = {
            "source_stage": source_stage or "unknown",
            "status": status,
            "hit": bool(str(recalled or "").strip()),
            "query_chars": len(str(query or "")),
            "query_preview": str(query or "")[:240],
            "result_chars": len(str(recalled or "")),
            "result_preview": str(recalled or "")[:240],
            "metadata_filters": dict(metadata_filters or {}),
            "ranking_profile": "agent_builder",
            "scope": "agent_builder_lesson",
            "user_id": user_id,
            "spec_id": str(clean_thread_context.get("spec_id") or ""),
            "version_id": str(clean_thread_context.get("version_id") or clean_thread_context.get("object_key") or ""),
            "error": error,
        }
        logger.info("[EmbeddedNanobot][agent_builder_lesson_recall_observation] %s", json.dumps(payload, ensure_ascii=False, default=str))

    async def _recall_agent_builder_lesson_guidance(
        self,
        *,
        user_message: str,
        user_id: str,
        tool_selection: dict[str, Any],
        thread_context: dict[str, Any] | None = None,
    ) -> str | None:
        if self.memory_db is None:
            return None
        if not user_id:
            return None
        if not tool_selection.get("agent_builder_governance", {}).get("enabled"):
            return None

        try:
            from core.memory.models import MemoryScope
            from core.memory.service import get_memory_service

            clean_thread_context = dict(thread_context or {})
            spec_id = str(clean_thread_context.get("spec_id") or "").strip()
            version_id = str(clean_thread_context.get("version_id") or clean_thread_context.get("object_key") or "").strip()
            metadata_filters: dict[str, str] | None = None
            if spec_id:
                metadata_filters = {"spec_id": spec_id}
            elif version_id:
                metadata_filters = {"version_id": version_id}

            query_parts = [user_message, spec_id, version_id]
            recall_query = " ".join(part for part in query_parts if str(part or "").strip())
            recalled = await get_memory_service(self.memory_db).recall_formatted(
                query=recall_query,
                user_id=user_id,
                agent_id="agent_builder",
                scopes=[MemoryScope.AGENT_BUILDER_LESSON.value],
                metadata_filters=metadata_filters,
                limit=3,
                max_chars=900,
                ranking_profile="agent_builder",
                group_by_scope=True,
                per_scope_limit=3,
            )
            self._log_agent_builder_lesson_recall_observation(
                source_stage="runtime_governance",
                user_id=user_id,
                query=recall_query,
                metadata_filters=metadata_filters,
                recalled=recalled,
                status="hit" if recalled.strip() else "miss",
                thread_context=clean_thread_context,
            )
            if not recalled.strip():
                return None
            return (
                "# Agent Workshop historical lessons\n\n"
                "Use the following validated lessons from earlier Agent Workshop evaluations to avoid repeating known defects and reuse verified fixes.\n\n"
                f"{recalled.strip()}"
            )
        except Exception as exc:
            self._log_agent_builder_lesson_recall_observation(
                source_stage="runtime_governance",
                user_id=user_id,
                query=user_message,
                metadata_filters=dict(thread_context or {}),
                recalled="",
                status="error",
                thread_context=thread_context,
                error=str(exc),
            )
            logger.debug("EmbeddedNanobot agent builder lesson guidance skipped: %s", exc)
            return None

    @staticmethod
    def _inject_ephemeral_system_guidance(messages: list[dict[str, Any]], guidance: str | None) -> list[dict[str, Any]]:
        if not guidance:
            return messages
        if messages and messages[0].get("role") == "system":
            return [messages[0], {"role": "system", "content": guidance}, *messages[1:]]
        return [{"role": "system", "content": guidance}, *messages]

    def _build_scoped_tools(self, user_message: str, skill_names: list[str] | None = None, intent_override: QueryIntent | None = None, thread_context: dict[str, Any] | None = None) -> tuple[ToolRegistry, dict[str, Any]]:
        scoped = ToolRegistry()
        selected_names = set(self.CORE_TOOL_NAMES)
        query = user_message.strip()
        query_lower = query.lower()
        query_terms = self._extract_query_terms(query)
        registry_scores: list[tuple[int, str, dict[str, Any]]] = []
        agent_first_guidance = None
        intent = intent_override or self._classify_query_intent(query)
        category_matches = self._match_category_features(query)
        route_decision = self._build_route_decision(intent, category_matches)
        focused_factory_scope = bool(
            (skill_names and "nanobot-agent-design" in skill_names)
            or intent.is_agent_builder_request
            or intent.is_skill_creation_request
        )

        if skill_names and "nanobot-agent-design" in skill_names:
            selected_names.update(self.AGENT_BUILDER_TOOL_IDS)
            selected_names.update(self.SKILL_CREATION_TOOL_IDS)

        if intent.is_agent_builder_request:
            selected_names.update(self.AGENT_BUILDER_TOOL_IDS)

        if (
            "模板" in query
            or "prompt" in query_lower
            or "生效模板" in query
            or "当前模板" in query
            or "debug template" in query_lower
        ):
            selected_names.update({
                "inspect_prompt_templates",
                "get_prompt_template_detail",
                "get_current_thread_effective_prompt_template",
                "get_effective_prompt_template",
            })

        if intent.is_skill_creation_request:
            selected_names.update(self.SKILL_CREATION_TOOL_IDS)

        if intent.prefers_callable_agent:
            selected_names.update(self.CALLABLE_AGENT_TOOL_IDS)

        if not focused_factory_scope:
            for tool_name in self.tools.tool_names:
                if tool_name not in self.CORE_TOOL_NAMES and tool_name not in selected_names:
                    tool = self.tools.get(tool_name)
                    metadata = getattr(tool, "metadata", None)
                    if metadata is None:
                        selected_names.add(tool_name)
                        continue

                    if tool_name in self.CALLABLE_AGENT_TOOL_IDS and self._should_suppress_callable_agent_tools(query):
                        continue

                    score = 0
                    haystack = " ".join(filter(None, [
                        str(getattr(metadata, "id", "")),
                        str(getattr(metadata, "name", "")),
                        str(getattr(metadata, "description", "")),
                        str(getattr(metadata, "when_to_use", "")),
                        str(getattr(metadata, "returns", "")),
                        " ".join(getattr(metadata, "related_tools", []) or []),
                    ])).lower()
                    category = str(getattr(metadata, "category", "") or "")
                    category_rule = self.CATEGORY_FEATURE_RULES.get(category)
                    matched_category_terms = category_matches.get(category, [])

                    if category_rule is not None and matched_category_terms:
                        score += len(matched_category_terms) * int(category_rule.score)

                    if tool_name in self.AGENT_BUILDER_TOOL_IDS or tool_name in self.SKILL_CREATION_TOOL_IDS:
                        if tool_name in selected_names:
                            score += 120

                    if tool_name in self.CALLABLE_AGENT_TOOL_IDS and tool_name in selected_names:
                        score += 160

                    if tool_name.lower() in query_lower:
                        score += 60

                    for term in query_terms:
                        if term.lower() in haystack:
                            score += 4 if len(term) <= 2 else 8

                    related_tools = getattr(metadata, "related_tools", []) or []
                    if any(related in query_lower for related in related_tools):
                        score += 12

                    if score > 0:
                        registry_scores.append((score, tool_name, {
                            "category": category,
                            "description": getattr(metadata, "description", ""),
                            "matched_category_terms": matched_category_terms,
                        }))

        registry_scores.sort(key=lambda item: (-item[0], item[1]))
        selected_dynamic = registry_scores[:self.MAX_DYNAMIC_TOOLS]
        selected_names.update(name for _, name, _ in selected_dynamic)
        agent_first_guidance = self._build_agent_first_guidance(query, selected_names)
        agent_builder_guidance = self._build_agent_builder_guidance(query, selected_names, thread_context=thread_context)

        for tool_name in self.tools.tool_names:
            if tool_name in selected_names:
                tool = self.tools.get(tool_name)
                if tool is not None:
                    scoped.register(tool)

        return scoped, {
            "query_terms": query_terms,
            "selected_tool_names": list(scoped.tool_names),
            "selected_dynamic_tools": [
                {"name": name, "score": score, **meta}
                for score, name, meta in selected_dynamic
            ],
            "core_tool_names": sorted(self.CORE_TOOL_NAMES),
            "dynamic_tool_limit": self.MAX_DYNAMIC_TOOLS,
            "focused_factory_scope": focused_factory_scope,
            "intent": {
                "preview": intent.is_preview_request,
                "agent_builder": intent.is_agent_builder_request,
                "skill_creation": intent.is_skill_creation_request,
                "prefers_callable_agent": intent.prefers_callable_agent,
                "matched_domains": list(intent.matched_domains),
                "reason_codes": list(intent.reason_codes),
                "decision_source": intent.decision_source,
            },
            "route_decision": route_decision,
            "category_matches": category_matches,
            "thread_context": dict(thread_context or {}),
            "agent_first": {
                "enabled": bool(agent_first_guidance),
                "guidance": agent_first_guidance or "",
                "keyword": intent.callable_keyword if agent_first_guidance else "",
            },
            "agent_builder_governance": {
                "enabled": bool(agent_builder_guidance),
                "guidance": agent_builder_guidance or "",
            },
        }

    @classmethod
    async def from_database(cls, db, workspace: str | Path, preferred_model: str | None = None, **kwargs: Any) -> "EmbeddedNanobotRuntime":
        provider = await TradingAgentsLLMProvider.from_database(db, preferred_model=preferred_model)
        runtime = cls(provider=provider, workspace=Path(workspace), memory_db=db, **kwargs)
        await runtime.sync_tradingagents_capabilities(db)
        return runtime

    def _register_default_tools(self) -> None:
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
        if self.exec_config.enable:
            self.tools.register(ExecTool(working_dir=str(self.workspace), timeout=self.exec_config.timeout, restrict_to_workspace=self.restrict_to_workspace, path_append=self.exec_config.path_append))
        self.tools.register(WebSearchTool(config=self.web_search_config, proxy=self.web_proxy))
        self.tools.register(WebFetchTool(proxy=self.web_proxy))

    async def sync_tradingagents_capabilities(self, db: Any | None = None) -> None:
        from core.tools.registry import get_tool_registry

        async with self._capability_sync_lock:
            registry = get_tool_registry()
            if db is not None:
                await self._hydrate_registry_capabilities(db, registry)
            self._register_registry_tools(registry)

    async def _hydrate_registry_capabilities(self, db: Any, registry: Any) -> None:
        try:
            from core.skills.models import SkillMetadata
            from core.skills.executor import SkillExecutor

            cursor = db.skills.find({"enabled": True})
            async for doc in cursor:
                impl = doc.get("implementation")
                params = doc.get("parameters", [])
                if not impl or not params:
                    continue
                payload = dict(doc)
                payload.pop("_id", None)
                skill = SkillMetadata(**payload)
                registry.register_function(
                    tool_id=skill.name.replace("-", "_"),
                    func=SkillExecutor.create_sync_wrapper(skill),
                    name=skill.description[:50],
                    category=skill.category,
                    description=skill.description,
                    is_online=True,
                    override=True,
                )
        except Exception:
            pass

        try:
            from core.tools.external_skill_loader import load_external_skills_to_registry

            await load_external_skills_to_registry(db, registry)
        except Exception:
            pass

        try:
            from app.services.mcp_service import MCPService

            await MCPService(db).restore_enabled_servers()
        except Exception:
            pass

    def _register_registry_tools(self, registry: Any) -> None:
        desired: set[str] = set()
        for metadata in registry.list_all():
            if not getattr(metadata, "fc_enabled", True):
                continue
            tool_name = metadata.id
            if tool_name in self._default_tool_names:
                continue
            func = registry.get_function(tool_name)
            if func is None:
                continue
            self.tools.register(TradingAgentsRegistryTool(metadata=metadata, func=func))
            desired.add(tool_name)

        for tool_name in list(self._dynamic_tool_names - desired):
            self.tools.unregister(tool_name)
        self._dynamic_tool_names = desired

    def _schedule_background(self, coro: Awaitable[Any]) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        task.add_done_callback(lambda item: self._background_tasks.remove(item) if item in self._background_tasks else None)

    @staticmethod
    def _drop_oldest_turn(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not history:
            return []
        for index in range(1, len(history)):
            if history[index].get("role") == "user":
                return history[index:]
        return []

    async def _build_capped_initial_messages(
        self,
        session,
        active_tools: ToolRegistry,
        *,
        user_message: str,
        skill_names: list[str] | None,
        media: list[str] | None,
        channel: str,
        chat_id: str,
        extra_system_guidance: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        history = session.get_history(max_messages=500)
        initial_messages = self.context.build_messages(
            history=history[:-1],
            current_message=user_message,
            skill_names=skill_names,
            media=media,
            channel=channel,
            chat_id=chat_id,
        )
        initial_messages = self._inject_ephemeral_system_guidance(initial_messages, extra_system_guidance)

        token_budget = max(0, self.context_window_tokens - self.provider.generation.max_tokens - 1024)
        estimated_tokens, _ = estimate_prompt_tokens_chain(
            self.provider,
            self.model,
            initial_messages,
            active_tools.get_definitions(),
        )

        while token_budget > 0 and estimated_tokens > token_budget and history:
            next_history = self._drop_oldest_turn(history)
            if next_history == history:
                break
            history = next_history
            initial_messages = self.context.build_messages(
                history=history,
                current_message=user_message,
                skill_names=skill_names,
                media=media,
                channel=channel,
                chat_id=chat_id,
            )
            initial_messages = self._inject_ephemeral_system_guidance(initial_messages, extra_system_guidance)
            estimated_tokens, _ = estimate_prompt_tokens_chain(
                self.provider,
                self.model,
                initial_messages,
                active_tools.get_definitions(),
            )

        return initial_messages, history, estimated_tokens

    def _dump_prompt_context(
        self,
        *,
        session_key: str,
        active_tools: ToolRegistry,
        tool_selection: dict[str, Any],
        initial_messages: list[dict[str, Any]],
        estimated_tokens: int,
        history: list[dict[str, Any]],
        skill_names: list[str] | None,
        channel: str,
        chat_id: str,
    ) -> Path:
        dump_dir = self.workspace / "logs" / "embedded_nanobot_context"
        dump_dir.mkdir(parents=True, exist_ok=True)

        safe_session = "".join(ch if ch.isalnum() or ch in {"-", "_", ":"} else "_" for ch in session_key).replace(":", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = dump_dir / f"{safe_session}_{timestamp}.json"

        tool_definitions = active_tools.get_definitions()
        system_prompt = initial_messages[0].get("content") if initial_messages else ""
        payload = {
            "generated_at": datetime.now().isoformat(),
            "session_key": session_key,
            "model": self.model,
            "channel": channel,
            "chat_id": chat_id,
            "skill_names": skill_names or [],
            "estimated_prompt_tokens": estimated_tokens,
            "context_window_tokens": self.context_window_tokens,
            "max_completion_tokens": self.provider.generation.max_tokens,
            "history_message_count": len(history),
            "initial_message_count": len(initial_messages),
            "tool_definition_count": len(tool_definitions),
            "tool_selection": tool_selection,
            "route_decision": dict(tool_selection.get("route_decision") or {}),
            "route_fallback": dict((tool_selection.get("route_decision") or {}).get("fallback") or {}),
            "token_breakdown": {
                "system_prompt": estimate_prompt_tokens([
                    {"role": "system", "content": system_prompt}
                ]),
                "messages_without_tools": estimate_prompt_tokens(initial_messages),
                "tool_definitions": estimate_prompt_tokens([], tool_definitions),
            },
            "message_summaries": [
                {
                    "index": index,
                    "role": message.get("role"),
                    "content_type": type(message.get("content")).__name__,
                    "content_chars": len(message.get("content")) if isinstance(message.get("content"), str) else 0,
                    "has_tool_calls": bool(message.get("tool_calls")),
                }
                for index, message in enumerate(initial_messages)
            ],
            "messages": initial_messages,
            "tool_definitions": tool_definitions,
        }
        dump_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return dump_path

    def _save_turn(self, session, messages: list[dict[str, Any]], skip: int) -> None:
        runtime_tag = self.context._RUNTIME_CONTEXT_TAG
        for message in messages[skip:]:
            entry = dict(message)
            role = entry.get("role")
            content = entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue
            if role == "tool":
                entry["content"] = sanitize_tool_result_content(content)
                if isinstance(entry.get("content"), list) and not entry["content"]:
                    continue
            elif role == "user":
                if isinstance(content, str) and content.startswith(runtime_tag):
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                elif isinstance(content, list):
                    filtered = sanitize_content_blocks(content, drop_runtime=True, runtime_context_tag=runtime_tag)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def _invoke_callback(self, callback: Callable[[str], Awaitable[None]] | None, value: str) -> None:
        if callback is None:
            return
        result = callback(value)
        if inspect.isawaitable(result):
            await result

    async def handle_message(self, user_message: str = "", session_key: str = "embedded:default", channel: str = "embedded", chat_id: str = "default", media: list[str] | None = None, skill_names: list[str] | None = None, on_progress: Callable[[str], Awaitable[None]] | None = None, on_stream: Callable[[str], Awaitable[None]] | None = None, on_tool_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None, on_step_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None, thread_context: dict[str, Any] | None = None, user_id: str | None = None, thread_id: str | None = None) -> dict[str, Any]:
        raw = user_message.strip()
        session = self.sessions.get_or_create(session_key)
        clean_thread_context = dict(thread_context or {})
        session.metadata.update({
            "session_key": session_key,
            "channel": channel,
            "chat_id": chat_id,
            "workspace_path": str(self.workspace.resolve()),
        })
        if user_id:
            session.metadata["user_id"] = user_id
        if thread_id:
            session.metadata["thread_id"] = thread_id
        elif chat_id and chat_id != "default":
            session.metadata["thread_id"] = chat_id
        if clean_thread_context:
            session.metadata["thread_context"] = clean_thread_context
        object_type, object_key, inferred_symbol = self._build_object_binding(clean_thread_context, user_message)
        if inferred_symbol:
            session.metadata["symbol"] = inferred_symbol
        if object_type:
            session.metadata["object_type"] = object_type
        if object_key:
            session.metadata["object_key"] = object_key

        async def emit_step(step: str, status: str, title: str, detail: str = "", iteration: int | None = None) -> None:
            if not on_step_event:
                return
            await self._invoke_callback(on_step_event, {
                "step": step,
                "status": status,
                "title": title,
                "detail": detail,
                "iteration": iteration,
                "session_key": session_key,
                "chat_id": chat_id,
                "channel": channel,
            })

        if self.commands.is_priority(raw):
            outbound = await self.commands.dispatch_priority(CommandContext(msg=type("Msg", (), {"channel": channel, "chat_id": chat_id, "session_key": session_key})(), session=session, key=session_key, raw=raw, loop=self))
            return {"content": outbound.content if outbound else "", "tools_used": [], "messages": session.get_history(max_messages=0), "stop_reason": "command"}
        await emit_step("context_preparation", "started", "准备上下文", "正在准备上下文和可用能力")
        if on_progress:
            await self._invoke_callback(on_progress, "正在准备上下文和可用能力")
        active_tools, tool_selection = self._build_scoped_tools(raw, skill_names, thread_context=clean_thread_context)
        refined_intent, fallback_meta = await self._resolve_llm_route_fallback(raw, tool_selection)
        if refined_intent is not None:
            active_tools, tool_selection = self._build_scoped_tools(raw, skill_names, intent_override=refined_intent, thread_context=clean_thread_context)
        tool_selection.setdefault("route_decision", {})["fallback"] = fallback_meta
        project_memory_guidance = await self._recall_project_memory_guidance(
            user_message=raw,
            tool_selection=tool_selection,
            thread_context=clean_thread_context,
        )
        agent_builder_lesson_guidance = await self._recall_agent_builder_lesson_guidance(
            user_message=raw,
            user_id=str(session.metadata.get("user_id") or "").strip(),
            tool_selection=tool_selection,
            thread_context=clean_thread_context,
        )
        if on_progress:
            await self._invoke_callback(on_progress, f"已选择 {len(active_tools.tool_names)} 个可用工具（核心 {len(self.CORE_TOOL_NAMES)} + 动态 {len(tool_selection['selected_dynamic_tools'])}）")
            if tool_selection.get("agent_first", {}).get("enabled"):
                await self._invoke_callback(on_progress, "检测到这是完整任务请求，将优先尝试复用现有 callable agent")
            if tool_selection.get("agent_builder_governance", {}).get("enabled"):
                await self._invoke_callback(on_progress, "检测到 Agent 工坊治理请求，将先核对当前资产和版本状态")
            if project_memory_guidance:
                await self._invoke_callback(on_progress, "已加载 Agent 工坊的项目长期规则约束")
            if agent_builder_lesson_guidance:
                await self._invoke_callback(on_progress, "已加载 Agent 工坊历史教训")
        logger.debug(
            "EmbeddedNanobot route decision: session_key=%s primary_intent=%s callable_agent_mode=%s reasons=%s matched_categories=%s",
            session_key,
            tool_selection.get("route_decision", {}).get("primary_intent"),
            tool_selection.get("route_decision", {}).get("callable_agent_mode"),
            tool_selection.get("route_decision", {}).get("reason_codes"),
            tool_selection.get("route_decision", {}).get("matched_categories"),
        )
        initial_messages, history, estimated_tokens = await self._build_capped_initial_messages(
            session,
            active_tools,
            user_message=user_message,
            skill_names=skill_names,
            media=media,
            channel=channel,
            chat_id=chat_id,
            extra_system_guidance=self._merge_system_guidance(
                project_memory_guidance,
                agent_builder_lesson_guidance,
                tool_selection.get("agent_first", {}).get("guidance") or None,
                tool_selection.get("agent_builder_governance", {}).get("guidance") or None,
            ),
        )
        if on_progress and estimated_tokens > 0:
            await self._invoke_callback(on_progress, f"上下文已准备完成，估算输入约 {estimated_tokens} tokens")
            dump_path = self._dump_prompt_context(
                session_key=session_key,
                active_tools=active_tools,
                tool_selection=tool_selection,
                initial_messages=initial_messages,
                estimated_tokens=estimated_tokens,
                history=history,
                skill_names=skill_names,
                channel=channel,
                chat_id=chat_id,
            )
            await self._invoke_callback(on_progress, f"上下文快照已写入 {dump_path}")
        await emit_step("context_preparation", "completed", "准备上下文", "上下文与可用能力已准备完成")
        runtime = self

        class _RuntimeHook(AgentHook):
            def __init__(self):
                self._stream_buf = ""

            def wants_streaming(self) -> bool:
                return on_stream is not None

            async def on_stream(self, context: AgentHookContext, delta: str) -> None:
                prev_clean = strip_think(self._stream_buf)
                self._stream_buf += delta
                new_clean = strip_think(self._stream_buf)
                incremental = new_clean[len(prev_clean):]
                if incremental and on_stream:
                    await runtime._invoke_callback(on_stream, incremental)

            async def on_stream_end(self, context: AgentHookContext, *, resuming: bool) -> None:
                self._stream_buf = ""

            async def before_execute_tools(self, context: AgentHookContext) -> None:
                if on_progress and context.tool_calls:
                    await runtime._invoke_callback(on_progress, f"准备调用工具: {', '.join(tc.name for tc in context.tool_calls)}")
                if context.tool_calls:
                    tool_names = ', '.join(tc.name for tc in context.tool_calls)
                    await emit_step("tool_execution", "started", "执行工具", f"准备调用工具: {tool_names}", iteration=context.iteration)
                if on_tool_event and context.tool_calls:
                    for tool_call in context.tool_calls:
                        await runtime._invoke_callback(on_tool_event, {
                            "name": tool_call.name,
                            "status": "started",
                            "detail": "工具已开始执行",
                        })

            async def after_iteration(self, context: AgentHookContext) -> None:
                summaries = []
                if context.tool_events:
                    for event in context.tool_events:
                        name = str(event.get("name") or "unknown")
                        status = str(event.get("status") or "ok")
                        summaries.append(f"{name}({status})")
                    if on_progress and summaries:
                        await runtime._invoke_callback(on_progress, f"工具执行完成: {', '.join(summaries)}")
                    if summaries:
                        await emit_step("tool_execution", "completed", "执行工具", f"工具执行完成: {', '.join(summaries)}", iteration=context.iteration)
                if on_tool_event and context.tool_events:
                    for event in context.tool_events:
                        await runtime._invoke_callback(on_tool_event, event)
                elif on_progress and context.final_content:
                    await runtime._invoke_callback(on_progress, "正在整理最终答复")
                if context.final_content:
                    await emit_step("final_response", "started", "整理答复", "正在整理最终答复", iteration=context.iteration)

            def finalize_content(self, context: AgentHookContext, content: str | None) -> str | None:
                return strip_think(content or "") or None

        result = await self.runner.run(AgentRunSpec(initial_messages=initial_messages, tools=active_tools, model=self.model, max_iterations=self.max_iterations, hook=_RuntimeHook(), concurrent_tools=True))
        if result.stop_reason == "completed" and not (result.final_content or "").strip():
            result.stop_reason = "empty_response"
            result.final_content = "本轮模型调用已结束，但没有返回可显示的正文内容。请重试；如果问题持续出现，请检查 logs/embedded_nanobot_llm.log 中对应请求的原始响应。"
        await emit_step("final_response", "completed", "整理答复", "本轮答复已生成")
        self._last_usage = result.usage
        self._save_turn(session, result.messages, skip=1 + len(history))
        if result.tools_used:
            for message in reversed(session.messages):
                if message.get("role") == "assistant":
                    message["tools_used"] = result.tools_used
                    break
        if self.max_session_messages is not None:
            session.retain_recent_legal_suffix(self.max_session_messages)
        self.sessions.save(session)
        self._schedule_background(self.memory_consolidator.maybe_consolidate_by_tokens(session))
        return {"content": result.final_content or "", "tools_used": result.tools_used, "messages": result.messages, "stop_reason": result.stop_reason, "usage": result.usage, "tool_events": result.tool_events}