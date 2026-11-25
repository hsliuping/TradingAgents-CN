"""
工作流构建器

从 WorkflowDefinition 构建 LangGraph 图

核心设计：
1. 辩论节点(DEBATE)不是一个执行节点，而是控制流程的标记
2. 辩论参与者(如 bull_researcher, bear_researcher)通过条件边连接
3. 条件边检查状态中的辩论计数来决定继续辩论还是结束
"""

import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from app.utils.api_key_utils import truncate_api_key

logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from .models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
)


# ============================================================
# v3.6.0 项8：辩论反思触发器（模块级函数）
# ============================================================

def _trigger_debate_reflection(
    *,
    state: Dict[str, Any],
    result: Dict[str, Any],
    debate_state_field: str,
    debate_type: str,
    agent_id: str,
    node_id: str,
) -> None:
    """辩论结束后触发反思提炼。

    在 research_manager / risk_manager 节点执行后调用，从 state 和 result
    中提取辩论历史与裁决，调用 run_reflection_sync 提炼为结构化 debate_lesson，
    写入 AGENT_EXPERIENCE scope（memory_kind=debate_lesson）。

    降级策略：
    - 辩论历史为空 → 跳过
    - LLM 超时/返回非 JSON → fallback 写入辩论历史摘要
    - mem0 不可用 → 跳过
    - 任何异常 → 不阻塞主流程（caller 已 try/except）
    """
    try:
        # 合并 state 和 result（管理者返回的 result 包含更新后的 debate_state）
        merged = dict(state or {})
        if isinstance(result, dict):
            merged.update(result)

        debate_state = merged.get(debate_state_field) or {}
        if not isinstance(debate_state, dict):
            return

        debate_history = str(debate_state.get("history", "") or "").strip()
        # judge_decision 可能存在于 debate_state 或顶层字段（如 investment_plan / final_trade_decision）
        conclusion = str(debate_state.get("judge_decision", "") or "").strip()
        if not conclusion:
            # 兜底：从 result 中取管理者输出
            if debate_state_field == "risk_debate_state":
                conclusion = str(merged.get("final_trade_decision", "") or "").strip()
            else:
                conclusion = str(merged.get("investment_plan", "") or "").strip()

        if not debate_history and not conclusion:
            logger.debug("[辩论反思] 跳过：辩论历史和裁决均为空 node=%s", node_id)
            return

        # 提取 ticker（兼容多种字段名）
        ticker = (
            merged.get("ticker")
            or merged.get("symbol")
            or merged.get("stock_code")
            or merged.get("code")
            or ""
        )
        ticker = str(ticker).strip() if ticker else ""

        # 提取 user_id（用于 mem0 元数据）
        user_id = str(merged.get("user_id") or merged.get("userId") or "default_user")

        # 获取 db 句柄
        db = merged.get("_db") or merged.get("db")
        if db is None:
            try:
                from app.core.database import get_mongo_db_sync
                db = get_mongo_db_sync()
            except Exception as exc:
                logger.debug("[辩论反思] 获取 db 句柄失败: %s", exc)
                return
        if db is None:
            return

        # 构造 fallback 内容
        fallback_parts = [f"辩论反思 {ticker} ({debate_type})"]
        if debate_history:
            # 仅保留末尾 800 字，避免 fallback 过长
            fallback_parts.append(debate_history[-800:])
        if conclusion:
            fallback_parts.append(f"最终裁决: {conclusion[:300]}")
        fallback_content = "\n\n".join(fallback_parts)

        from core.agents.reflection_helper import run_reflection_sync
        from core.agents.reflection_prompts import (
            DEBATE_REFLECTION_SYSTEM_PROMPT,
            build_debate_reflection_user_prompt,
        )
        from core.memory.models import MemoryScope

        user_prompt = build_debate_reflection_user_prompt(
            ticker=ticker,
            debate_history=debate_history,
            conclusion=conclusion,
            debate_type=debate_type,
        )
        if not user_prompt.strip():
            return

        success = run_reflection_sync(
            db=db,
            user_id=user_id,
            agent_id=agent_id,
            scope=MemoryScope.AGENT_EXPERIENCE,
            memory_kind="debate_lesson",
            system_prompt=DEBATE_REFLECTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            fallback_content=fallback_content,
            fallback_metadata={
                "symbol": str(ticker).upper() if ticker else "",
                "debate_type": debate_type,
                "agent_id": agent_id,
                "node_id": node_id,
                "source": "debate_reflection",
            },
        )
        if success:
            logger.info(
                "[辩论反思] 已写入 debate_lesson 教训: ticker=%s type=%s node=%s",
                ticker, debate_type, node_id,
            )
    except Exception as exc:
        logger.warning("[辩论反思] 异常: %s", exc, exc_info=True)


# v3.6.0 项8 fix：管理者 agent_id 前缀匹配，覆盖 v2 变体
_MANAGER_AGENT_PREFIXES = ("research_manager", "risk_manager")


def _is_manager_agent(agent_id: str) -> bool:
    """判断 agent_id 是否属于管理者节点（含 v2 变体）。"""
    agent_id = str(agent_id or "").strip()
    return any(agent_id.startswith(prefix) for prefix in _MANAGER_AGENT_PREFIXES)


from ..agents import AgentRegistry, AgentFactory, AgentConfig
from ..collaboration_runtime import (
    InvocationArtifactRef,
    InvocationPolicy,
    InvocationProvenance,
    InvocationRequest,
    InvocationResult,
    InvocationSourceType,
    InvocationStatus,
    InvocationTargetType,
    utc_now,
)

# 分析师类型映射 - 需要工具节点支持的智能体
# 注意: index_analyst 和 sector_analyst 是"自包含"分析师，
# 它们不使用 LangGraph 的工具调用机制，而是在单次调用中直接获取数据并完成分析
ANALYST_TOOL_MAPPING = {
    "market_analyst": "market",
    "news_analyst": "news",
    "fundamentals_analyst": "fundamentals",
    "social_analyst": "social",
    "market_analyst_v2": "market",
    "news_analyst_v2": "news",
    "fundamentals_analyst_v2": "fundamentals",
    "etf_analyst_v2": "fundamentals",  # ETF 分析师复用 fundamentals 消息槽
    "social_analyst_v2": "social",
}

_DEFAULT_CALLABLE_SURFACES = {"assistant", "workflow"}

_DEEP_AGENTS = {
    "research_manager_v2", "risk_manager_v2",
    "risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2",
    # A9-P1: 风险自我辩论节点使用深度 LLM（单次调用承载三视角辩论）
    "risk_self_debate_v2",
    "index_analyst_v2", "sector_analyst_v2",
    "research_manager", "risk_manager",
}


def _select_llm_type_for_agent(agent_id: str) -> str:
    normalized_agent_id = str(agent_id or "").strip()
    return "deep" if normalized_agent_id in _DEEP_AGENTS else "quick"


class LegacyDependencyProvider:
    """
    遗留智能体依赖提供者

    为适配器提供 LLM 和 Toolkit 实例
    """

    _instance = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._quick_llm = None
        self._deep_llm = None
        self._debate_llm = None  # 🆕 辩论专用 LLM（使用更高温度）
        self._toolkit = None
        self._memories = {}
        self._memory_provider = None

    @classmethod
    def get_instance(cls, config: Optional[Dict[str, Any]] = None) -> "LegacyDependencyProvider":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(config)
        elif config:
            # 如果有新配置，重置实例以便重新创建 LLM
            cls._instance._config.update(config)
            cls._instance._quick_llm = None
            cls._instance._deep_llm = None
            cls._instance._debate_llm = None  # 🆕 重置辩论 LLM
            cls._instance._toolkit = None
            cls._instance._memories = {}
            cls._instance._memory_provider = None
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试或重新配置）"""
        cls._instance = None

    def get_llm(
        self,
        llm_type: str = "quick",
        temperature: Optional[float] = None,
        timeout: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        获取 LLM 实例

        Args:
            llm_type: "quick" 或 "deep"
            temperature: 可选，如果指定则创建新的 LLM 实例（用于 Agent 特定的温度配置）
            timeout: 可选，覆盖默认超时时间
            max_tokens: 可选，覆盖默认最大输出长度
        """
        # 只要存在任一 Agent 级 LLM 覆盖，就创建独立实例
        if temperature is not None or timeout is not None or max_tokens is not None:
            logger.info(
                f"[依赖提供者] 创建自定义 LLM: type={llm_type}, "
                f"temperature={temperature}, timeout={timeout}, max_tokens={max_tokens}"
            )
            return self._create_custom_llm(
                llm_type,
                temperature=temperature,
                timeout=timeout,
                max_tokens=max_tokens,
            )
        
        # 🔥 每次调用时都检查配置是否变化，如果变化则重新创建 LLM 实例
        # 这样可以确保 API key 更新后立即生效，无需重启服务
        self._create_llm_instances(force_refresh=True)
        return self._deep_llm if llm_type == "deep" else self._quick_llm

    def get_toolkit(self):
        """获取 Toolkit 实例"""
        if self._toolkit is None:
            self._create_toolkit()
        return self._toolkit

    def get_memory(self, memory_type: str):
        """获取 Memory 实例"""
        if memory_type not in self._memories:
            self._create_memory(memory_type)
        return self._memories.get(memory_type)

    def _create_llm_instances(self, force_refresh: bool = False):
        """
        创建 LLM 实例

        逻辑与旧引擎 (simple_analysis_service.create_analysis_config) 保持一致：
        1. 如果用户传入了模型名称 (quick_think_llm, deep_think_llm)，根据模型名称从数据库查找配置
        2. 如果用户没有传入模型名称，从数据库获取默认配置
        3. 根据模型名称获取对应的 provider、backend_url、api_key
        
        Args:
            force_refresh: 是否强制刷新（重新从数据库读取配置并重新创建 LLM 实例）
        """
        from tradingagents.graph.trading_graph import create_llm_by_provider

        # 🔥 如果 force_refresh=False 且 LLM 实例已存在，直接返回（避免重复创建）
        if not force_refresh and self._quick_llm and self._deep_llm:
            logger.debug("[依赖提供者] LLM 实例已存在且不需要刷新，使用缓存")
            return

        # 获取用户传入的模型名称
        quick_model = self._config.get("quick_think_llm")
        deep_model = self._config.get("deep_think_llm")

        logger.info(f"[依赖提供者] 用户传入配置: quick_model={quick_model}, deep_model={deep_model}")

        # 🔧 京东云模式：如果没有传入模型名称，使用环境变量中的默认模型，跳过数据库查询
        from app.core.jdyun import is_jdyun_mode, get_jdyun_default_model
        if is_jdyun_mode():
            jdyun_default = get_jdyun_default_model()
            if not quick_model:
                quick_model = jdyun_default
            if not deep_model:
                deep_model = jdyun_default
            logger.info(f"[依赖提供者] 京东云模式: quick_model={quick_model}, deep_model={deep_model}")
        else:
            # 如果用户没有传入模型名称，从数据库获取默认配置
            if not quick_model or not deep_model:
                db_default = self._get_default_llm_config_from_db()
                if not quick_model:
                    quick_model = db_default.get("quick_think_llm", "qwen-flash")
                if not deep_model:
                    deep_model = db_default.get("deep_think_llm", "qwen-plus")
                logger.info(f"[依赖提供者] 使用数据库默认配置补充: quick_model={quick_model}, deep_model={deep_model}")

        # 根据模型名称从数据库获取完整配置（provider, url, api_key）
        # 复用 simple_analysis_service 中已有的统一查询函数
        # 🔥 每次调用时都重新从数据库读取配置，确保 API key 更新后立即生效
        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
        quick_config = get_provider_and_url_by_model_sync(quick_model)
        deep_config = get_provider_and_url_by_model_sync(deep_model)

        quick_provider = quick_config.get("provider", "dashscope")
        deep_provider = deep_config.get("provider", "dashscope")

        # URL 和 API Key 优先使用用户显式指定的，否则使用数据库配置
        quick_url = self._config.get("quick_backend_url") or self._config.get("backend_url") or quick_config.get("backend_url", "")
        deep_url = self._config.get("deep_backend_url") or deep_config.get("backend_url", "") or quick_url

        # 🔥 API Key 获取优先级：用户显式指定 > 数据库配置 > 环境变量（在 create_llm_by_provider 中处理）
        quick_api_key_from_config = self._config.get("quick_api_key") or self._config.get("api_key")
        quick_api_key_from_db = quick_config.get("api_key")
        quick_api_key = quick_api_key_from_config or quick_api_key_from_db
        
        deep_api_key_from_config = self._config.get("deep_api_key")
        deep_api_key_from_db = deep_config.get("api_key")
        deep_api_key = deep_api_key_from_config or deep_api_key_from_db or quick_api_key

        logger.info("[依赖提供者] 创建 LLM:")
        logger.info(f"  - Quick: provider={quick_provider}, model={quick_model}, url={quick_url[:50] if quick_url else 'None'}...")
        logger.info(f"  - Quick API Key 来源: {'用户显式指定' if quick_api_key_from_config else ('数据库配置' if quick_api_key_from_db else '未配置（将使用环境变量）')}")
        if quick_api_key:
            logger.info(f"  - Quick API Key: 已配置 ({truncate_api_key(quick_api_key)})")
        else:
            logger.info(f"  - Quick API Key: 空")
        logger.info(f"  - Deep: provider={deep_provider}, model={deep_model}, url={deep_url[:50] if deep_url else 'None'}...")
        logger.info(f"  - Deep API Key 来源: {'用户显式指定' if deep_api_key_from_config else ('数据库配置' if deep_api_key_from_db else ('继承 Quick' if quick_api_key else '未配置（将使用环境变量）'))}")
        if deep_api_key:
            logger.info(f"  - Deep API Key: 已配置 ({truncate_api_key(deep_api_key)})")
        else:
            logger.info(f"  - Deep API Key: 空")

        try:
            # 🔧 从数据库读取模型配置（max_tokens, temperature, timeout, reasoning_effort）
            # 优先级：用户显式指定(self._config) > 数据库配置 > 默认值
            # 修复：之前 builder 不读 DB 的 max_tokens，导致 UI 配置的 Token 数不生效
            from app.services.simple_analysis_service import _load_model_config_from_db
            quick_db_cfg = _load_model_config_from_db(quick_model)
            deep_db_cfg = _load_model_config_from_db(deep_model)

            quick_max_tokens = self._config.get("quick_max_tokens") or quick_db_cfg.get("max_tokens", 2000)
            deep_max_tokens = self._config.get("deep_max_tokens") or deep_db_cfg.get("max_tokens", 4000)
            logger.info(
                f"🔧 [依赖提供者] max_tokens: quick={quick_model}={quick_max_tokens}, "
                f"deep={deep_model}={deep_max_tokens}"
            )

            # 🧠 A1b: 深度档位 → reasoning_effort 思考预算
            # 合并语义与旧链路一致（resolve_reasoning_efforts）：DB 显式配置 > 档位默认，
            # 仅火山方舟 Agent Plan（provider=volcengine）注入；快速模型在档位基础上降两档
            from tradingagents.graph.trading_graph import resolve_reasoning_efforts
            _effort_cfg = dict(self._config)
            _effort_cfg.setdefault("quick_provider", quick_provider)
            _effort_cfg.setdefault("deep_provider", deep_provider)
            quick_effort, deep_effort = resolve_reasoning_efforts(_effort_cfg, quick_db_cfg, deep_db_cfg)
            if self._config.get("depth_reasoning_effort"):
                logger.info(
                    f"🧠 [依赖提供者] reasoning_effort: 档位默认={self._config.get('depth_reasoning_effort')}"
                    f" → quick={quick_model}={quick_effort}, deep={deep_model}={deep_effort}"
                    f"（DB显式配置优先，仅火山注入）"
                )

            # 创建快速模型
            self._quick_llm = create_llm_by_provider(
                provider=quick_provider,
                model=quick_model,
                backend_url=quick_url,
                temperature=self._config.get("quick_temperature") or quick_db_cfg.get("temperature", 0.1),
                max_tokens=quick_max_tokens,
                timeout=self._config.get("quick_timeout") or quick_db_cfg.get("timeout", 60),
                api_key=quick_api_key,
                reasoning_effort=quick_effort,
            )

            # 创建深度模型
            self._deep_llm = create_llm_by_provider(
                provider=deep_provider,
                model=deep_model,
                backend_url=deep_url,
                temperature=self._config.get("deep_temperature") or deep_db_cfg.get("temperature", 0.1),
                max_tokens=deep_max_tokens,
                timeout=self._config.get("deep_timeout") or deep_db_cfg.get("timeout", 120),
                api_key=deep_api_key,
                reasoning_effort=deep_effort,
            )

            logger.info("[依赖提供者] LLM 实例创建成功")
            logger.info(f"  - Quick LLM: {type(self._quick_llm).__name__}")
            logger.info(f"  - Deep LLM: {type(self._deep_llm).__name__}")
        except Exception as e:
            logger.error(f"[依赖提供者] LLM 创建失败: {e}")
            raise

    def _create_custom_llm(
        self,
        llm_type: str,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        创建带 Agent 级覆盖参数的 LLM 实例。

        Args:
            llm_type: "quick" 或 "deep"
            temperature: 温度参数
            timeout: 超时参数
            max_tokens: 最大输出长度

        Returns:
            LLM 实例
        """
        from tradingagents.graph.trading_graph import create_llm_by_provider

        # 获取模型名称（从分析流程创建时指定的配置）
        model = self._config.get(f"{llm_type}_think_llm")
        if not model:
            db_default = self._get_default_llm_config_from_db()
            model = db_default.get(f"{llm_type}_think_llm", "qwen-turbo" if llm_type == "quick" else "qwen-plus")

        # 根据模型名称获取配置（provider, url, api_key）
        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
        config = get_provider_and_url_by_model_sync(model)

        provider = config.get("provider", "dashscope")
        url = self._config.get(f"{llm_type}_backend_url") or self._config.get("backend_url") or config.get("backend_url", "")
        
        # 🔥 API Key 获取优先级：用户显式指定 > 数据库配置 > 环境变量（在 create_llm_by_provider 中处理）
        api_key_from_config = self._config.get(f"{llm_type}_api_key") or self._config.get("api_key")
        api_key_from_db = config.get("api_key")
        api_key = api_key_from_config or api_key_from_db

        # 🔧 从数据库读取模型配置（max_tokens, temperature, timeout, reasoning_effort）
        # 优先级：显式参数 > self._config > 数据库配置 > 默认值
        from app.services.simple_analysis_service import _load_model_config_from_db
        db_cfg = _load_model_config_from_db(model)

        resolved_temperature = (
            temperature if temperature is not None
            else self._config.get(f"{llm_type}_temperature") or db_cfg.get("temperature", 0.1)
        )
        resolved_max_tokens = (
            max_tokens if max_tokens is not None
            else self._config.get(f"{llm_type}_max_tokens") or db_cfg.get("max_tokens", 2000 if llm_type == "quick" else 4000)
        )
        resolved_timeout = (
            timeout if timeout is not None
            else self._config.get(f"{llm_type}_timeout") or db_cfg.get("timeout", 60 if llm_type == "quick" else 120)
        )

        # 🧠 A1b: reasoning_effort 合并（DB 显式配置 > 档位默认；仅火山方舟注入；quick 降两档）
        from tradingagents.graph.trading_graph import _lower_reasoning_effort
        resolved_effort = db_cfg.get("reasoning_effort")
        _depth_effort = self._config.get("depth_reasoning_effort")
        if _depth_effort and not resolved_effort and str(provider or "").lower() == "volcengine":
            resolved_effort = _lower_reasoning_effort(_depth_effort) if llm_type == "quick" else _depth_effort

        logger.info(
            f"[依赖提供者] 创建自定义 LLM: type={llm_type}, model={model}, "
            f"temperature={resolved_temperature}, timeout={resolved_timeout}, max_tokens={resolved_max_tokens}"
            + (f", reasoning_effort={resolved_effort}" if resolved_effort else "")
        )
        logger.info(f"  - API Key 来源: {'用户显式指定' if api_key_from_config else ('数据库配置' if api_key_from_db else '未配置（将使用环境变量）')}")
        if api_key:
            logger.info(f"  - API Key: 已配置 ({truncate_api_key(api_key)})")
        else:
            logger.info(f"  - API Key: 空")

        return create_llm_by_provider(
            provider=provider,
            model=model,
            backend_url=url,
            temperature=resolved_temperature,
            max_tokens=resolved_max_tokens,
            timeout=resolved_timeout,
            api_key=api_key,
            reasoning_effort=resolved_effort,
        )

    def _get_llm_config_from_db(self) -> Dict[str, Any]:
        """从数据库获取 LLM 配置"""
        try:
            from pymongo import MongoClient
            from app.core.config import settings

            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]

            # 1. 获取系统配置中的默认模型
            configs_collection = db.system_configs
            doc = configs_collection.find_one({"is_active": True}, sort=[("version", -1)])

            if not doc or "llm_configs" not in doc:
                logger.warning("[依赖提供者] 数据库中没有 LLM 配置，使用默认配置")
                return {}

            llm_configs = doc["llm_configs"]

            # 找到第一个启用的非 google 模型作为默认模型
            # （因为 google 模型不适合中国区域直接使用）
            default_config = None
            for cfg in llm_configs:
                if cfg.get("enabled", True):
                    provider = cfg.get("provider", "").lower()
                    # 优先选择阿里百炼或 DeepSeek
                    if provider in ["dashscope", "deepseek"]:
                        default_config = cfg
                        break

            # 如果没找到首选厂家，使用任何可用的配置
            if not default_config:
                for cfg in llm_configs:
                    if cfg.get("enabled", True):
                        default_config = cfg
                        break

            if not default_config:
                logger.warning("[依赖提供者] 没有找到启用的 LLM 配置")
                return {}

            # 2. 获取厂家配置（API Key 和 base_url）
            provider_name = default_config.get("provider", "")
            model_name = default_config.get("model_name", "")
            providers_collection = db.llm_providers
            provider_doc = providers_collection.find_one({"name": provider_name})

            # 🔥 确定 API Key（优先级：模型配置 > 厂家配置 > 环境变量）
            api_key = None
            model_api_key = default_config.get("api_key", "")
            if model_api_key and model_api_key.strip() and model_api_key != "your-api-key" and not model_api_key.startswith("sk-xxx"):
                api_key = model_api_key
                logger.info(f"✅ [依赖提供者] 使用模型配置的 API Key")
            elif provider_doc:
                provider_api_key = provider_doc.get("api_key", "")
                if provider_api_key and provider_api_key.strip() and provider_api_key != "your-api-key" and not provider_api_key.startswith("sk-xxx"):
                    api_key = provider_api_key
                    logger.info(f"✅ [依赖提供者] 使用厂家配置的 API Key")
            
            backend_url = default_config.get("api_base", "")
            if provider_doc and not backend_url:
                backend_url = provider_doc.get("default_base_url", "")

            # 如果数据库没有 API Key，尝试从环境变量获取
            if not api_key:
                api_key = self._get_env_api_key(provider_name)
                if api_key:
                    logger.info(f"✅ [依赖提供者] 使用环境变量的 API Key")

            result = {
                "llm_provider": provider_name,
                "quick_think_llm": model_name,
                "deep_think_llm": model_name,
                "backend_url": backend_url,
                "api_key": api_key,
                "quick_temperature": default_config.get("temperature", 0.1),
                "quick_max_tokens": default_config.get("max_tokens", 2000),
                "quick_timeout": default_config.get("timeout", 30),
            }

            logger.info(f"[依赖提供者] 从数据库获取配置: provider={provider_name}, model={model_name}, url={backend_url[:50] if backend_url else 'None'}...")

            client.close()
            return result

        except Exception as e:
            logger.warning(f"[依赖提供者] 从数据库获取配置失败: {e}")
            return {}

    def _get_env_api_key(self, provider_name: str) -> Optional[str]:
        """从环境变量获取 API Key"""
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "dashscope": "DASHSCOPE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "qianfan": "QIANFAN_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
        }
        env_name = env_key_map.get(provider_name.lower())
        if env_name:
            return os.getenv(env_name)
        return None

    def _get_default_llm_config_from_db(self) -> Dict[str, Any]:
        """
        从数据库获取默认的 LLM 配置（仅模型名称）

        用于当用户没有传入模型名称时，获取系统默认配置
        """
        try:
            from pymongo import MongoClient
            from app.core.config import settings

            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]

            # 获取系统配置中的默认模型
            doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])

            if not doc or "llm_configs" not in doc:
                logger.warning("[依赖提供者] 数据库中没有 LLM 配置，使用默认配置")
                client.close()
                return {"quick_think_llm": "qwen-turbo", "deep_think_llm": "qwen-plus"}

            llm_configs = doc["llm_configs"]

            # 找到第一个启用的非 google 模型作为默认模型
            default_config = None
            for cfg in llm_configs:
                if cfg.get("enabled", True):
                    provider = cfg.get("provider", "").lower()
                    if provider in ["dashscope", "deepseek"]:
                        default_config = cfg
                        break

            if not default_config:
                for cfg in llm_configs:
                    if cfg.get("enabled", True):
                        default_config = cfg
                        break

            client.close()

            if default_config:
                model_name = default_config.get("model_name", "qwen-turbo")
                return {
                    "quick_think_llm": model_name,
                    "deep_think_llm": model_name,
                }

            return {"quick_think_llm": "qwen-turbo", "deep_think_llm": "qwen-plus"}

        except Exception as e:
            logger.warning(f"[依赖提供者] 从数据库获取默认配置失败: {e}")
            return {"quick_think_llm": "qwen-turbo", "deep_think_llm": "qwen-plus"}

    def _get_config_by_model_name(self, model_name: str) -> Dict[str, Any]:
        """
        根据模型名称从数据库获取完整配置（provider, url, api_key）

        逻辑与旧引擎 get_provider_and_url_by_model_sync 保持一致

        Args:
            model_name: 模型名称，如 'qwen-turbo', 'gpt-4' 等

        Returns:
            dict: {"provider": "dashscope", "backend_url": "https://...", "api_key": "xxx"}
        """
        # 默认 URL 映射
        default_urls = {
            "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "deepseek": "https://api.deepseek.com",
            "openai": "https://api.openai.com/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta/openai",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "siliconflow": "https://api.siliconflow.cn/v1",
        }

        # 模型名称到厂家的默认映射
        model_provider_map = {
            "qwen": "dashscope",
            "gpt": "openai",
            "deepseek": "deepseek",
            "gemini": "google",
            "glm": "zhipu",
            "ernie": "qianfan",
        }

        try:
            from pymongo import MongoClient
            from app.core.config import settings

            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]

            # 查询活跃的系统配置
            doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])

            if doc and "llm_configs" in doc:
                for cfg in doc["llm_configs"]:
                    if cfg.get("model_name") == model_name:
                        provider = cfg.get("provider", "")
                        api_base = cfg.get("api_base", "")
                        model_api_key = cfg.get("api_key")

                        # 从 llm_providers 获取厂家配置
                        provider_doc = db.llm_providers.find_one({"name": provider})

                        # 🔥 方案3：确定 API Key（新优先级：厂家配置 > 模型配置 > 环境变量）
                        api_key = None

                        # 优先级1：厂家配置
                        if provider_doc and provider_doc.get("api_key"):
                            pk = provider_doc["api_key"]
                            if pk and pk.strip() and pk != "your-api-key" and not pk.startswith("sk-xxx"):
                                api_key = pk

                        # 优先级2：模型配置（作为备选）
                        if not api_key:
                            if model_api_key and model_api_key.strip() and model_api_key != "your-api-key":
                                api_key = model_api_key

                        # 优先级3：环境变量
                        if not api_key:
                            api_key = self._get_env_api_key(provider)

                        # 确定 backend_url
                        backend_url = api_base
                        if not backend_url and provider_doc:
                            backend_url = provider_doc.get("default_base_url", "")
                        if not backend_url:
                            backend_url = default_urls.get(provider.lower(), "")

                        client.close()
                        logger.info(f"[依赖提供者] 模型 {model_name} 配置: provider={provider}, url={backend_url[:40] if backend_url else 'None'}...")
                        return {
                            "provider": provider,
                            "backend_url": backend_url,
                            "api_key": api_key
                        }

            client.close()

        except Exception as e:
            logger.warning(f"[依赖提供者] 从数据库获取模型 {model_name} 配置失败: {e}")

        # 如果数据库中没有找到，使用默认映射
        provider = "dashscope"
        for prefix, p in model_provider_map.items():
            if model_name.lower().startswith(prefix):
                provider = p
                break

        logger.info(f"[依赖提供者] 使用默认映射: {model_name} -> {provider}")
        return {
            "provider": provider,
            "backend_url": default_urls.get(provider, ""),
            "api_key": self._get_env_api_key(provider)
        }

    def _get_provider_config_from_db(self, provider_name: str) -> Dict[str, Any]:
        """
        根据 provider 名称从数据库获取对应的配置（URL 和 API Key）

        Args:
            provider_name: 厂家名称，如 "dashscope", "deepseek", "openai" 等

        Returns:
            包含 backend_url 和 api_key 的配置字典
        """
        # 默认 URL 映射
        default_urls = {
            "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "deepseek": "https://api.deepseek.com",
            "openai": "https://api.openai.com/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta/openai",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "siliconflow": "https://api.siliconflow.cn/v1",
        }

        result = {
            "backend_url": default_urls.get(provider_name.lower(), ""),
            "api_key": None,
        }

        try:
            from pymongo import MongoClient
            from app.core.config import settings

            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]

            # 从 llm_providers 集合获取厂家配置
            providers_collection = db.llm_providers
            provider_doc = providers_collection.find_one({"name": provider_name})

            if provider_doc:
                if provider_doc.get("default_base_url"):
                    result["backend_url"] = provider_doc["default_base_url"]
                if provider_doc.get("api_key") and not provider_doc["api_key"].startswith("sk-xxx"):
                    result["api_key"] = provider_doc["api_key"]

            client.close()

        except Exception as e:
            logger.debug(f"[依赖提供者] 从数据库获取 {provider_name} 配置失败: {e}")

        # 如果数据库没有 API Key，尝试从环境变量获取
        if not result["api_key"]:
            result["api_key"] = self._get_env_api_key(provider_name)

        logger.debug(f"[依赖提供者] {provider_name} 配置: url={result['backend_url'][:30] if result['backend_url'] else 'None'}..., api_key={'有值' if result['api_key'] else '无'}")

        return result

    def _create_toolkit(self):
        """创建 Toolkit 实例"""
        from tradingagents.agents.utils.agent_utils import Toolkit
        from tradingagents.default_config import DEFAULT_CONFIG

        config = {**DEFAULT_CONFIG, **self._config}
        self._toolkit = Toolkit(config=config)
        logger.info("[依赖提供者] Toolkit 创建成功")

    def _create_memory(self, memory_type: str):
        """创建 Memory 实例"""
        from tradingagents.core.engine.memory_provider import MemoryProvider
        from tradingagents.default_config import DEFAULT_CONFIG

        config = {**DEFAULT_CONFIG, **self._config}

        if config.get("memory_enabled", True):
            if self._memory_provider is None:
                self._memory_provider = MemoryProvider(config=config, memory_enabled=True)
            self._memories[memory_type] = self._memory_provider.get_memory(memory_type)
        else:
            self._memories[memory_type] = None

    def get_tool_nodes(self) -> Dict[str, ToolNode]:
        """获取工具节点（用于分析师的工具调用循环）"""
        toolkit = self.get_toolkit()
        return {
            "market": ToolNode([
                toolkit.get_stock_market_data_unified,
                toolkit.get_YFin_data_online,
                toolkit.get_stockstats_indicators_report_online,
                toolkit.get_YFin_data,
                toolkit.get_stockstats_indicators_report,
            ]),
            "social": ToolNode([
                toolkit.get_stock_sentiment_unified,
                toolkit.get_stock_news_openai,
                toolkit.get_reddit_stock_info,
            ]),
            "news": ToolNode([
                toolkit.get_stock_news_unified,
                toolkit.get_global_news_openai,
                toolkit.get_google_news,
                toolkit.get_finnhub_news,
                toolkit.get_reddit_news,
            ]),
            "fundamentals": ToolNode([
                toolkit.get_stock_fundamentals_unified,
                toolkit.get_finnhub_company_insider_sentiment,
                toolkit.get_finnhub_company_insider_transactions,
                toolkit.get_simfin_balance_sheet,
                toolkit.get_simfin_cashflow,
                toolkit.get_simfin_income_stmt,
                toolkit.get_china_stock_data,
                toolkit.get_china_fundamentals,
            ]),
        }


class WorkflowBuilder:
    """
    工作流构建器

    将 WorkflowDefinition 转换为可执行的 LangGraph

    用法:
        builder = WorkflowBuilder()
        graph = builder.build(workflow_definition)
        result = graph.invoke({"ticker": "AAPL", "trade_date": "2024-01-15"})
    """

    # 分析师 agent_id 到类型的映射（用于 selected_analysts 过滤）
    ANALYST_ID_TO_TYPE = {
        "market_analyst": "market",
        "news_analyst": "news",
        "fundamentals_analyst": "fundamentals",
        "social_analyst": "social",
        "market_analyst_v2": "market",
        "news_analyst_v2": "news",
        "fundamentals_analyst_v2": "fundamentals",
        "etf_analyst_v2": "etf",  # ETF 分析师
        "social_analyst_v2": "social",
        "index_analyst": "index_analyst",
        "sector_analyst": "sector_analyst",
        "index_analyst_v2": "index_analyst",
        "sector_analyst_v2": "sector_analyst",
    }

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        factory: Optional[AgentFactory] = None,
        default_config: Optional[AgentConfig] = None,
        legacy_config: Optional[Dict[str, Any]] = None,
        binding_manager: Optional[Any] = None,  # BindingManager
        llm_override: Optional[Any] = None,  # Optional LLM instance override
    ):
        from ..agents.registry import get_registry
        from ..config.binding_manager import BindingManager
        from ..config.agent_config_manager import AgentConfigManager

        # 确保 Agent 适配器模块被导入，触发 Agent 注册
        try:
            import core.agents.adapters  # noqa: F401
            logger.debug("[WorkflowBuilder] Agent 适配器模块已加载")
        except ImportError as e:
            logger.warning(f"[WorkflowBuilder] 加载 Agent 适配器模块失败: {e}")

        self.registry = registry or get_registry()
        self.factory = factory or AgentFactory(self.registry)
        self.default_config = default_config or AgentConfig()
        self.llm_override = llm_override

        # BindingManager 用于动态工具绑定
        self.binding_manager = binding_manager or BindingManager()

        # 🔥 AgentConfigManager 用于加载 Agent 配置
        self.agent_config_manager = AgentConfigManager()

        # 为 BindingManager 和 AgentConfigManager 设置数据库连接
        # 🆕 同时初始化 EmbeddingManager 和 MemoryManager
        self.embedding_manager = None
        self.memory_manager = None

        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            self.binding_manager.set_database(db)
            self.agent_config_manager.set_database(db)
            logger.info("[WorkflowBuilder] BindingManager 和 AgentConfigManager 已初始化并连接数据库")

            # 🆕 初始化 EmbeddingManager 和 MemoryManager
            try:
                from core.llm import EmbeddingManager
                from core.memory import MemoryManager

                self.embedding_manager = EmbeddingManager(db=db)
                self.memory_manager = MemoryManager(self.embedding_manager)
                logger.info("[WorkflowBuilder] 🧠 EmbeddingManager 和 MemoryManager 已初始化")
            except Exception as mem_error:
                logger.warning(f"[WorkflowBuilder] 记忆系统初始化失败: {mem_error}")
                logger.info("[WorkflowBuilder] Agent 将在没有记忆功能的情况下运行")

        except Exception as e:
            logger.warning(f"[WorkflowBuilder] 数据库连接失败: {e}")
            logger.info("[WorkflowBuilder] 将使用代码配置模式")

        # 遗留依赖提供者（用于适配原有智能体）
        self._legacy_provider = LegacyDependencyProvider.get_instance(legacy_config)

        # 从 legacy_config 获取 selected_analysts（用于动态过滤分析师节点）
        self._selected_analysts: Optional[List[str]] = None
        if legacy_config:
            self._selected_analysts = legacy_config.get("selected_analysts")
            if self._selected_analysts:
                logger.info(f"[WorkflowBuilder] 选中的分析师: {self._selected_analysts}")

        self._agents: Dict[str, Any] = {}  # 缓存创建的智能体
        self._workflow_id: Optional[str] = None  # 当前工作流ID

    def _is_analyst_selected(self, node: NodeDefinition) -> bool:
        """
        检查分析师节点是否被选中

        Args:
            node: 节点定义

        Returns:
            True 如果节点被选中或不是分析师节点
        """
        # 如果没有设置 selected_analysts，所有分析师都执行
        if not self._selected_analysts:
            return True

        # 不是分析师节点，不过滤
        if node.type != NodeType.ANALYST:
            return True

        # 检查是否在选中列表中
        if node.agent_id in self.ANALYST_ID_TO_TYPE:
            analyst_type = self.ANALYST_ID_TO_TYPE[node.agent_id]
            is_selected = analyst_type in self._selected_analysts
            if not is_selected:
                logger.info(f"[WorkflowBuilder] 过滤分析师节点: {node.id} (类型: {analyst_type})")
            return is_selected

        # 未知类型的分析师，保留
        return True

    def build(
        self,
        definition: WorkflowDefinition,
        state_schema: Optional[type] = None,
    ):
        """
        构建 LangGraph 图

        Args:
            definition: 工作流定义
            state_schema: 状态模式 (默认使用通用字典)

        Returns:
            编译后的 LangGraph
        """
        # 保存工作流ID，用于动态工具绑定
        self._workflow_id = definition.id
        logger.info(f"[WorkflowBuilder] 开始构建工作流: {self._workflow_id}")

        # 使用默认状态模式
        if state_schema is None:
            state_schema = self._get_default_state_schema()

        # 创建图
        graph = StateGraph(state_schema)

        # 过滤工作流定义中的分析师节点
        filtered_definition = self._filter_analyst_nodes(definition)

        # 首先识别辩论配置
        debate_configs = self._identify_debate_configs(filtered_definition)

        # 构建辩论参与者集合及其对应的 debate_key
        participant_debate_keys: Dict[str, str] = {}
        for debate_id, config in debate_configs.items():
            debate_key = f"_debate_{debate_id}_count"
            for p in config["participants"]:
                participant_debate_keys[p] = debate_key

        # 识别分析师节点（需要工具节点支持）
        analyst_nodes_info: Dict[str, str] = {}  # node_id -> analyst_type
        for node in filtered_definition.nodes:
            if node.agent_id and node.agent_id in ANALYST_TOOL_MAPPING:
                analyst_type = ANALYST_TOOL_MAPPING[node.agent_id]
                analyst_nodes_info[node.id] = analyst_type
                logger.info(f"[工具节点] 识别分析师节点: {node.id} -> {analyst_type}")

        # 获取工具节点
        tool_nodes = {}
        if analyst_nodes_info:
            tool_nodes = self._legacy_provider.get_tool_nodes()
            logger.info(f"[工具节点] 创建工具节点: {list(tool_nodes.keys())}")

        # 添加节点（使用过滤后的定义）
        logger.info(f"[图构建] 📋 工作流节点列表: {[n.id for n in filtered_definition.nodes]}")
        for node in filtered_definition.nodes:
            if node.type in (NodeType.START, NodeType.END):
                continue

            # 如果是辩论参与者，使用包装函数
            if node.id in participant_debate_keys:
                debate_key = participant_debate_keys[node.id]
                node_func = self._create_debate_participant_wrapper(node, debate_key)
            elif _is_manager_agent(node.agent_id):
                # v3.6.0 项8：管理者节点（research_manager / risk_manager 及其 v2 变体）
                # 在管理者产出裁决后触发辩论反思，把辩论历史+裁决提炼为
                # 结构化 debate_lesson 教训，写入 AGENT_EXPERIENCE scope。
                debate_state_field = (
                    "risk_debate_state" if node.agent_id.startswith("risk_manager")
                    else "investment_debate_state"
                )
                node_func = self._create_manager_with_debate_reflection(
                    node, debate_state_field=debate_state_field
                )
            else:
                node_func = self._create_node_function(node)

            graph.add_node(node.id, node_func)
            logger.info(f"[图构建] ✅ 添加节点: {node.id} (agent_id={node.agent_id}, type={node.type})")

            # 如果是分析师节点，添加对应的工具节点和消息清理节点
            if node.id in analyst_nodes_info:
                analyst_type = analyst_nodes_info[node.id]
                tools_node_id = f"tools_{node.id}"
                clear_node_id = f"msg_clear_{node.id}"

                # 添加工具节点（包装以使用独立消息历史）
                wrapped_tool_node = self._create_tool_node_wrapper(
                    tool_nodes[analyst_type], node.id, analyst_type
                )
                graph.add_node(tools_node_id, wrapped_tool_node)
                logger.info(f"[工具节点] 添加工具节点: {tools_node_id}")

                # 添加消息清理节点
                graph.add_node(clear_node_id, self._create_msg_clear_node(node.id, analyst_type))
                logger.info(f"[工具节点] 添加消息清理节点: {clear_node_id}")

        # A9-P1: 为每个风险辩论添加隐藏的自我辩论单节点
        # 仅当运行时 state["_risk_self_debate"]=True（深度/全面档且开关开启）时被路由到，
        # 默认走原风险三角多 agent 路径。节点创建失败时降级为不加节点（保留原路径），
        # 不阻塞整个工作流构建。
        risk_self_debate_nodes: Set[str] = set()
        for debate_id in debate_configs:
            if "risk" in debate_id.lower():
                self_debate_node_id = f"{debate_id}_self_debate"
                try:
                    graph.add_node(
                        self_debate_node_id,
                        self._create_risk_self_debate_node_func(debate_id),
                    )
                    risk_self_debate_nodes.add(self_debate_node_id)
                    logger.info(f"[图构建] ✅ 添加风险自我辩论节点: {self_debate_node_id} (A9-P1)")
                except Exception as e:
                    logger.warning(
                        f"[图构建] ⚠️ 风险自我辩论节点创建失败，回退原风险三角路径: {e}"
                    )

        # A3: 为投资辩论（非风险）添加隐藏的并行开局节点
        # 仅当运行时 state["_parallel_opening"]=True（默认启用，可一键关闭）时被路由到，
        # 第一轮乐观/审慎研究员并行出简报，后续轮次回原轮循对抗。节点创建失败时
        # 降级为不加节点（保留原串行路径），不阻塞整个工作流构建。
        parallel_opening_nodes: Set[str] = set()
        for debate_id, debate_config in debate_configs.items():
            if "risk" in debate_id.lower():
                continue  # 风险辩论：深度档由 A9-P1 接管，低档位保留原串行三角
            if len(debate_config["participants"]) < 2:
                continue  # 单参与者无从并行
            po_node_id = f"{debate_id}_parallel_opening"
            try:
                graph.add_node(
                    po_node_id,
                    self._create_parallel_opening_node_func(
                        debate_id, debate_config, filtered_definition
                    ),
                )
                parallel_opening_nodes.add(po_node_id)
                logger.info(f"[图构建] ✅ 添加投资辩论并行开局节点: {po_node_id} (A3)")
            except Exception as e:
                logger.warning(
                    f"[图构建] ⚠️ 并行开局节点创建失败，回退原串行路径: {e}"
                )

        # 添加边（使用过滤后的定义）
        self._add_edges(
            graph, filtered_definition, debate_configs, analyst_nodes_info,
            risk_self_debate_nodes=risk_self_debate_nodes,
            parallel_opening_nodes=parallel_opening_nodes,
        )

        # 编译
        return graph.compile()

    def _filter_analyst_nodes(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        """
        根据 selected_analysts 过滤工作流定义中的分析师节点

        这个方法会：
        1. 移除未选中的分析师节点
        2. 更新边，将被过滤节点的入边直接连接到出边
        3. 保持工作流的连通性

        Args:
            definition: 原始工作流定义

        Returns:
            过滤后的工作流定义（副本）
        """
        # 如果没有 selected_analysts 配置，返回原始定义
        if not self._selected_analysts:
            return definition

        # 收集要移除的分析师节点 ID
        nodes_to_remove: Set[str] = set()
        for node in definition.nodes:
            if not self._is_analyst_selected(node):
                nodes_to_remove.add(node.id)

        if not nodes_to_remove:
            logger.info("[WorkflowBuilder] 没有需要过滤的分析师节点")
            return definition

        logger.info(f"[WorkflowBuilder] 将过滤以下分析师节点: {nodes_to_remove}")

        # 创建新的节点列表（排除被过滤的节点）
        new_nodes = [n for n in definition.nodes if n.id not in nodes_to_remove]

        # 重新构建边
        # 策略：对于 PARALLEL -> 分析师 -> MERGE 模式
        # 如果分析师被过滤，直接移除对应的边即可
        # 因为 PARALLEL 和 MERGE 节点会自动处理剩余的分析师

        new_edges = []
        for edge in definition.edges:
            # 如果边的源或目标是被移除的节点，跳过这条边
            if edge.source in nodes_to_remove or edge.target in nodes_to_remove:
                logger.debug(f"[WorkflowBuilder] 移除边: {edge.source} -> {edge.target}")
                continue
            new_edges.append(edge)

        # 创建新的工作流定义
        filtered_definition = WorkflowDefinition(
            id=definition.id,
            name=definition.name,
            description=definition.description,
            version=definition.version,
            nodes=new_nodes,
            edges=new_edges,
            created_at=definition.created_at,
            updated_at=definition.updated_at,
            created_by=definition.created_by,
            config=definition.config,
            tags=definition.tags,
            is_template=definition.is_template,
        )

        logger.info(f"[WorkflowBuilder] 过滤完成: {len(definition.nodes)} 节点 -> {len(new_nodes)} 节点, "
                   f"{len(definition.edges)} 边 -> {len(new_edges)} 边")

        return filtered_definition

    def _create_msg_clear_node(self, node_id: str, analyst_type: str) -> Callable:
        """
        创建消息清理节点

        清理分析师的独立消息历史，避免消息无限累积。
        """
        messages_key = f"_{analyst_type}_messages"

        def safe_msg_clear(state):
            """清理分析师的独立消息历史"""
            logger.info(f"[消息清理] {node_id} - 清理独立消息历史: {messages_key}")
            # 清空独立消息历史
            return {messages_key: []}

        return safe_msg_clear

    def _create_tool_node_wrapper(
        self,
        tool_node: ToolNode,
        analyst_node_id: str,
        analyst_type: str
    ) -> Callable:
        """
        为工具节点创建包装器，使用分析师的独立消息历史
        """
        messages_key = f"_{analyst_type}_messages"

        def wrapped_tool_node(state):
            logger.info(f"[工具节点] tools_{analyst_node_id} - 开始执行")

            # 获取分析师独立的消息历史
            analyst_messages = list(state.get(messages_key, []))
            if not analyst_messages:
                logger.warning(f"[工具节点] {analyst_node_id} - 独立消息历史为空，使用共享消息")
                analyst_messages = list(state.get("messages", []))

            # 创建工具节点专用的 state
            tool_state = {**state, "messages": analyst_messages}

            # 执行工具节点
            result = tool_node.invoke(tool_state)

            # 更新独立消息历史，移除共享 messages 字段
            if "messages" in result:
                new_messages = result["messages"]
                if isinstance(new_messages, list):
                    updated_messages = analyst_messages + new_messages
                else:
                    updated_messages = analyst_messages + [new_messages]
                # 存储到独立消息字段
                result[messages_key] = updated_messages
                # 移除共享 messages 字段
                del result["messages"]
                logger.info(f"[工具节点] {analyst_node_id} - 更新消息历史，消息数: {len(updated_messages)}")

            logger.info(f"[工具节点] tools_{analyst_node_id} - 执行完成")
            return result

        return wrapped_tool_node

    def _create_analyst_condition_func(self, node_id: str, analyst_type: str) -> Callable:
        """
        创建分析师节点的条件函数
        判断是否有工具调用，决定路由到工具节点还是消息清理节点
        使用分析师的独立消息历史
        """
        tools_node_id = f"tools_{node_id}"
        clear_node_id = f"msg_clear_{node_id}"
        messages_key = f"_{analyst_type}_messages"

        # 报告字段映射
        report_field_map = {
            "market": "market_report",
            "social": "sentiment_report",
            "news": "news_report",
            "fundamentals": "fundamentals_report",
        }
        report_field = report_field_map.get(analyst_type, f"{analyst_type}_report")

        # 工具计数字段映射
        tool_count_field_map = {
            "market": "market_tool_call_count",
            "social": "sentiment_tool_call_count",
            "news": "news_tool_call_count",
            "fundamentals": "fundamentals_tool_call_count",
        }
        tool_count_field = tool_count_field_map.get(analyst_type, f"{analyst_type}_tool_call_count")

        def condition_func(state):
            """判断是否继续工具调用循环（使用独立消息历史）"""
            # 使用分析师独立的消息历史
            messages = state.get(messages_key, [])
            if not messages:
                # 如果没有独立消息，回退到共享消息
                messages = state.get("messages", [])

            if not messages:
                logger.info(f"🔀 [{node_id}] 无消息，返回: {clear_node_id}")
                return clear_node_id

            last_message = messages[-1]
            report = state.get(report_field, "")
            tool_call_count = state.get(tool_count_field, 0)
            max_tool_calls = 3  # 最大工具调用次数

            logger.info(f"🔀 [{node_id}] 条件判断 (独立消息: {messages_key}):")
            logger.info(f"  - 消息数量: {len(messages)}")
            logger.info(f"  - 报告长度: {len(report)}")
            logger.info(f"  - 工具调用次数: {tool_call_count}/{max_tool_calls}")
            logger.info(f"  - 最后消息类型: {type(last_message).__name__}")

            # 如果已有报告，结束循环
            if report and len(report) > 100:
                logger.info(f"🔀 [{node_id}] ✅ 报告已完成，返回: {clear_node_id}")
                return clear_node_id

            # 如果达到最大工具调用次数，强制结束
            if tool_call_count >= max_tool_calls:
                logger.warning(f"🔀 [{node_id}] ⚠️ 达到最大调用次数，返回: {clear_node_id}")
                return clear_node_id

            # 检查是否有工具调用
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                logger.info(f"🔀 [{node_id}] 🔧 检测到工具调用，返回: {tools_node_id}")
                return tools_node_id

            logger.info(f"🔀 [{node_id}] ✅ 无工具调用，返回: {clear_node_id}")
            return clear_node_id

        return condition_func

    def _create_analyst_wrapper(
        self,
        analyst_node: Callable,
        node_id: str,
        node_label: str,
        agent_id: str,
        analyst_type: str,
        output_field: Optional[str] = None,
    ) -> Callable:
        """
        为分析师创建包装器，使用独立的消息历史

        这解决了多个分析师并行执行时共享 messages 字段导致的问题：
        - 每个分析师使用独立的消息字段（如 _fundamentals_messages）
        - 避免工具调用和响应混乱
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        # 独立消息字段名
        messages_key = f"_{analyst_type}_messages"

        def wrapped_analyst(state):
            logger.info(f"[节点执行] 🚀 {node_id} ({node_label}) - 开始执行 (分析师: {agent_id})")

            # 打印调试信息
            logger.info(f"[分析师调试] {node_id} - 独立消息字段: {messages_key}")
            logger.info(f"[分析师调试] {node_id} - 共享messages数量: {len(state.get('messages', []))}")
            logger.info(f"[分析师调试] {node_id} - 独立messages数量: {len(state.get(messages_key, []))}")

            # 打印状态中的计数器
            for key in ["market_tool_call_count", "sentiment_tool_call_count", "news_tool_call_count", "fundamentals_tool_call_count"]:
                if key in state:
                    logger.info(f"[分析师调试] {node_id} - 状态中 {key}: {state.get(key)}")

            # 获取分析师独立的消息历史
            analyst_messages = list(state.get(messages_key, []))

            if not analyst_messages:
                # 第一次调用：从 state["messages"] 中提取基本消息
                base_messages = []
                for msg in state.get("messages", []):
                    if isinstance(msg, (HumanMessage, SystemMessage)):
                        base_messages.append(msg)
                analyst_messages = base_messages
                logger.info(f"[分析师] {node_id} - 初始化消息历史，基础消息数: {len(base_messages)}")
            else:
                logger.info(f"[分析师] {node_id} - 使用现有消息历史，消息数: {len(analyst_messages)}")
                # 打印消息类型
                for i, msg in enumerate(analyst_messages):
                    logger.info(f"[分析师] {node_id} - 消息[{i}]: {type(msg).__name__}")

            # 创建分析师专用的 state（使用独立消息）
            analyst_state = {**state, "messages": analyst_messages}

            # 调用分析师节点
            result = self._execute_agent_node_with_runtime(
                state=analyst_state,
                agent_callable=analyst_node,
                agent_id=agent_id,
                node_id=node_id,
                node_label=node_label,
                output_field=output_field,
                legacy_adapter=True,
            )

            # 打印返回结果中的计数器
            for key in ["market_tool_call_count", "sentiment_tool_call_count", "news_tool_call_count", "fundamentals_tool_call_count"]:
                if key in result:
                    logger.info(f"[分析师] {node_id} - 返回结果包含 {key}: {result[key]}")

            # 更新独立消息历史，移除共享 messages 字段
            if "messages" in result:
                new_messages = result["messages"]
                if isinstance(new_messages, list):
                    updated_messages = analyst_messages + new_messages
                else:
                    updated_messages = analyst_messages + [new_messages]
                # 存储到独立消息字段
                result[messages_key] = updated_messages
                # 移除共享 messages 字段，避免污染
                del result["messages"]
                logger.info(f"[分析师] {node_id} - 更新消息历史，消息数: {len(updated_messages)}")

            logger.info(f"[节点执行] ✅ {node_id} ({node_label}) - 执行完成")
            return result

        return wrapped_analyst
    
    def _get_default_state_schema(self) -> type:
        """
        获取默认状态模式

        使用 TypedDict 但包含 __extra_items__ 来支持动态字段
        参考 tradingagents 的 AgentState 设计
        """
        from typing import Annotated, Any, List
        from typing_extensions import TypedDict
        from langgraph.graph import MessagesState
        import operator
        from core.state.reducers import keep_non_empty, merge_dict, keep_latest_list

        class WorkflowState(MessagesState):
            # 基本信息
            company_of_interest: Annotated[str, keep_non_empty]
            trade_date: Annotated[str, keep_non_empty]

            # 🆕 系统变量（由工作流引擎在启动时准备）
            ticker: Annotated[str, keep_non_empty]
            analysis_date: Annotated[str, keep_non_empty]
            company_name: Annotated[str, keep_non_empty]
            industry: Annotated[str, keep_non_empty]
            current_price: Annotated[str, keep_non_empty]
            market_name: Annotated[str, keep_non_empty]
            currency_name: Annotated[str, keep_non_empty]
            currency_symbol: Annotated[str, keep_non_empty]
            current_date: Annotated[str, keep_non_empty]
            start_date: Annotated[str, keep_non_empty]

            # 分析报告 - 使用reducer支持并发更新
            market_report: Annotated[str, keep_non_empty]
            fundamentals_report: Annotated[str, keep_non_empty]
            news_report: Annotated[str, keep_non_empty]
            sentiment_report: Annotated[str, keep_non_empty]
            index_report: Annotated[str, keep_non_empty]
            sector_report: Annotated[str, keep_non_empty]

            # 🆕 工具调用摘要（各分析师的工具调用记录，供下游 Agent 引用）
            # key: analyst_type 或 agent_id，value: Markdown 格式的摘要文本
            tool_call_summaries: Annotated[dict, merge_dict]

            # 🆕 v3.5.0 质量门禁标记（各分析师报告的质量检查结果，供下游和监控引用）
            # 每个元素是 {agent_id, analyst_type, ticker, reason, severity, retried} 字典
            quality_flags: Annotated[list, keep_latest_list]

            # 研究结果
            bull_report: Annotated[str, keep_non_empty]
            bear_report: Annotated[str, keep_non_empty]
            investment_plan: Annotated[str, keep_non_empty]
            trader_investment_plan: Annotated[str, keep_non_empty]

            # 最终研究结论
            final_decision: Annotated[str, keep_non_empty]
            risk_assessment: Annotated[str, keep_non_empty]
            final_trade_decision: Annotated[str, keep_non_empty]

            # 🆕 交易复盘相关字段
            trade_info: Annotated[dict, merge_dict]
            market_data: Annotated[dict, merge_dict]
            benchmark_data: Annotated[dict, merge_dict]
            trading_plan: Annotated[dict, merge_dict]  # 🆕 交易计划规则
            timing_analysis: Annotated[str, keep_non_empty]
            position_analysis: Annotated[str, keep_non_empty]
            emotion_analysis: Annotated[str, keep_non_empty]
            attribution_analysis: Annotated[str, keep_non_empty]
            review_summary: Annotated[str, keep_non_empty]

            # 辩论状态 - 使用 merge_dict reducer 来处理并发更新
            investment_debate_state: Annotated[dict, merge_dict]
            risk_debate_state: Annotated[dict, merge_dict]

            # 辩论计数 - 注意使用 operator.add 来处理并发更新
            _debate_debate_count: Annotated[int, operator.add]
            _debate_risk_debate_count: Annotated[int, operator.add]

            # 辩论配置
            _max_debate_rounds: Annotated[int, keep_non_empty]
            _max_risk_rounds: Annotated[int, keep_non_empty]

            # A9-P1: 风险自我辩论开关（True=深度/全面档走单节点自我辩论路径，
            # False/缺省=走原风险三角多 agent 辩论路径）。keep_non_empty 保证
            # 一旦注入 True 不会被并行节点的空返回覆盖。
            _risk_self_debate: Annotated[bool, keep_non_empty]

            # 分析师独立消息历史（避免并行执行时消息混乱）
            # 注意：这些字段用于工具调用循环，每个分析师使用自己的消息历史
            _market_messages: Annotated[List, keep_latest_list]
            _social_messages: Annotated[List, keep_latest_list]
            _news_messages: Annotated[List, keep_latest_list]
            _fundamentals_messages: Annotated[List, keep_latest_list]

            # 分析师工具调用计数（防止死循环）
            market_tool_call_count: Annotated[int, keep_non_empty]
            sentiment_tool_call_count: Annotated[int, keep_non_empty]
            news_tool_call_count: Annotated[int, keep_non_empty]
            fundamentals_tool_call_count: Annotated[int, keep_non_empty]

            # v2.0 辩论相关字段
            bull_opinion: Annotated[str, keep_non_empty]
            bear_opinion: Annotated[str, keep_non_empty]
            risky_opinion: Annotated[str, keep_non_empty]
            safe_opinion: Annotated[str, keep_non_empty]
            neutral_opinion: Annotated[str, keep_non_empty]

            # 持仓分析相关字段（v2.0）
            technical_analysis: Annotated[str, keep_non_empty]
            fundamental_analysis: Annotated[str, keep_non_empty]
            risk_analysis: Annotated[str, keep_non_empty]
            action_advice: Annotated[str, keep_non_empty]
            
            # 持仓信息
            position_info: Annotated[dict, merge_dict]
            stock_analysis_report: Annotated[dict, merge_dict]
            user_preference: Annotated[str, keep_non_empty]
            analysis_params: Annotated[dict, merge_dict]

            # 🆕 调试和上下文相关字段
            context: Annotated[Any, keep_non_empty]  # AgentContext 对象
            skip_cache: Annotated[bool, keep_non_empty]  # 是否跳过缓存
            prompt_overrides: Annotated[dict, merge_dict]  # 提示词覆盖

            # 🆕 外部事实记忆注入（智能助手联网提取的事实，带采集日期与来源）
            # 由 UnifiedAnalysisEngine 在启动时按 ticker 查询写入，仅辩论环节
            # （bull/bear）与风险评估环节（risk_manager）消费，其他环节不受影响
            memory_facts_summary: Annotated[str, keep_non_empty]

        # 🔥 动态注入工坊 Agent 的 output_field 到 State schema
        # LangGraph 的 StateGraph 只会保留 schema 中声明的字段，未声明的字段会被丢弃
        # 工坊创建的 Agent（如 valuation_analyst_v1）使用自定义 output_field（如 valuation_report）
        # 必须在这里动态声明，否则 Agent 返回的输出会被 LangGraph 丢掉
        try:
            from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name
            from pymongo import MongoClient as _MC
            _client = _MC(build_mongodb_connection_string(), serverSelectionTimeoutMS=2000)
            _db = _client[get_mongodb_database_name()]
            _docs = list(_db.agent_configs.find(
                {"enabled": True, "version_status": "active", "runtime_status": "active"},
                {"agent_id": 1, "output_field": 1, "metadata.output_field": 1, "_id": 0},
            ))
            _client.close()
            _builtin_fields = set(WorkflowState.__annotations__.keys())
            _added = []
            for _doc in _docs:
                _field = _doc.get("output_field") or (_doc.get("metadata") or {}).get("output_field")
                if _field and _field not in _builtin_fields and _field not in _added:
                    WorkflowState.__annotations__[_field] = Annotated[str, keep_non_empty]
                    _added.append(_field)
            if _added:
                logger.info(f"[StateSchema] 动态注入工坊 Agent output_field: {_added}")
        except Exception as _e:
            logger.warning(f"[StateSchema] 动态注入工坊 Agent output_field 失败: {_e}")

        return WorkflowState
    
    def _create_node_function(self, node: NodeDefinition) -> Callable:
        """为节点创建执行函数"""

        if node.type == NodeType.CONDITION:
            return self._create_condition_node(node)
        elif node.type == NodeType.PARALLEL:
            return self._create_parallel_node(node)
        elif node.type == NodeType.MERGE:
            return self._create_merge_node(node)
        elif node.type == NodeType.DEBATE:
            return self._create_debate_node(node)
        else:
            return self._create_agent_node(node)

    def _create_agent_node(self, node: NodeDefinition) -> Callable:
        """创建智能体节点"""
        agent_id = node.agent_id
        node_id = node.id
        node_label = node.label or node_id

        if agent_id is None:
            raise ValueError(f"节点 {node.id} 缺少 agent_id")

        # 🔥 从数据库加载 Agent 配置
        db_agent_config = self.agent_config_manager.get_agent_config(agent_id)
        if db_agent_config:
            logger.debug(f"[智能体创建] 从数据库加载 Agent 配置: {agent_id}")
            execution_config = db_agent_config.get('config', {})
            logger.debug(f"[智能体创建] 执行配置: {execution_config}")
        else:
            logger.debug(f"[智能体创建] 未找到数据库配置，使用默认配置: {agent_id}")
            execution_config = {}

        # 合并节点配置（优先级：node.config > 数据库配置 > 默认配置）
        # 🔥 排除 llm_provider 和 llm_model，因为这些不应该在 Agent 配置中
        default_dict = self.default_config.model_dump(exclude={'llm_provider', 'llm_model'})
        execution_config_clean = {k: v for k, v in execution_config.items() if k not in ['llm_provider', 'llm_model']}
        node_config_clean = {k: v for k, v in (node.config or {}).items() if k not in ['llm_provider', 'llm_model']}
        
        # 🔥 创建配置字典，显式设置 llm_provider 和 llm_model 为 None 以覆盖默认值
        config_dict = {
            **default_dict,
            **execution_config_clean,
            **node_config_clean,
            'llm_provider': None,  # 🔥 显式设置为 None，覆盖 AgentConfig 的默认值 "deepseek"
            'llm_model': None      # 🔥 显式设置为 None
        }
        
        config = AgentConfig(**config_dict)
        
        # 🔥 创建后再次验证并清理：使用 exclude 重新创建，确保这些字段不在最终配置中
        config_dict_clean = config.model_dump(exclude={'llm_provider', 'llm_model'})
        # 重新创建时，由于字典中没有这些字段，Pydantic 会使用默认值，所以我们需要再次显式设置
        config_dict_clean['llm_provider'] = None
        config_dict_clean['llm_model'] = None
        config = AgentConfig(**config_dict_clean)
        
        # 🔥 最终验证：如果 model_dump 中仍然有这些字段且有值，记录警告
        final_dict = config.model_dump()
        if final_dict.get('llm_provider') not in [None, '']:
            logger.warning(f"⚠️ Agent 配置中仍然包含 llm_provider={final_dict.get('llm_provider')}，这不应该发生")

        # 首先尝试使用新架构创建智能体（已注册 OR 数据库中有 agent_configs 记录）
        if self.registry.is_registered(agent_id) or self._has_agent_config_in_db(agent_id):
            logger.info(f"=" * 80)
            logger.info(f"[智能体创建] 开始创建 Agent: {agent_id} (node={node_id})")

            # 🆕 三层优先级工具查询：node > workflow > agent默认
            tool_ids = self.binding_manager.get_tools_for_node(
                agent_id=agent_id,
                workflow_id=self._workflow_id,
                node_id=node_id,
            )
            if tool_ids:
                logger.info(f"[智能体创建] 🔧 从 BindingManager 获取工具 (三层优先级): {agent_id} -> {tool_ids}")
            else:
                logger.warning(f"[智能体创建] ⚠️ 未找到任何工具绑定: {agent_id}")

            # 🔥 关键修复：根据 agent_id 判断应该使用 quick 还是 deep LLM
            llm_type = _select_llm_type_for_agent(agent_id)
            agent_temperature = node_config_clean.get("temperature", execution_config_clean.get("temperature"))
            agent_timeout = node_config_clean.get("timeout", execution_config_clean.get("timeout"))
            agent_max_tokens = node_config_clean.get("max_tokens", execution_config_clean.get("max_tokens"))

            if self.llm_override:
                llm = self.llm_override
            elif any(value is not None for value in (agent_temperature, agent_timeout, agent_max_tokens)):
                llm = self._legacy_provider.get_llm(
                    llm_type,
                    temperature=agent_temperature,
                    timeout=agent_timeout,
                    max_tokens=agent_max_tokens,
                )
            else:
                llm = self._legacy_provider.get_llm(llm_type)
            logger.debug(
                f"[智能体创建] LLM: type={llm_type}, temp={agent_temperature}, "
                f"timeout={agent_timeout}, max_tokens={agent_max_tokens}"
            )

            agent_memory = None
            if self.memory_manager:
                try:
                    agent_memory = self.memory_manager.get_agent_memory(agent_id)
                except Exception as mem_error:
                    logger.warning(f"[智能体创建] 获取记忆实例失败: {mem_error}")

            agent = self.factory.create(
                agent_id,
                config,
                llm=llm,
                tool_ids=tool_ids,
                memory=agent_memory
            )

            if hasattr(agent, 'set_dependencies'):
                toolkit = self._legacy_provider.get_toolkit()
                agent.set_dependencies(llm, toolkit)

            self._agents[node.id] = agent
            logger.info(f"[智能体创建] {agent_id} -> {type(agent).__name__} (tools={len(getattr(agent, '_tools', []) or [])})")

            # 包装以添加日志
            self._ensure_workflow_surface_access(agent_id, db_agent_config)
            output_field = self._resolve_agent_output_field(agent_id, node.config, db_agent_config)

            def logged_agent(state, _agent=agent, _id=node_id, _label=node_label, _agent_id=agent_id, _output_field=output_field):
                return self._execute_agent_node_with_runtime(
                    state=state,
                    agent_callable=_agent,
                    agent_id=_agent_id,
                    node_id=_id,
                    node_label=_label,
                    output_field=_output_field,
                    node_config=node.config,
                )
            return logged_agent

        # 尝试使用遗留适配器
        legacy_node = self._try_create_legacy_agent(agent_id)
        if legacy_node is not None:
            self._agents[node.id] = legacy_node
            logger.info(f"[智能体创建] ✅ 使用遗留适配器创建: {agent_id} -> node_id: {node.id}")

            self._ensure_workflow_surface_access(agent_id, db_agent_config)
            output_field = self._resolve_agent_output_field(agent_id, node.config, db_agent_config)

            # 检查是否是分析师节点（需要独立消息历史）
            if agent_id in ANALYST_TOOL_MAPPING:
                analyst_type = ANALYST_TOOL_MAPPING[agent_id]
                return self._create_analyst_wrapper(
                    legacy_node,
                    node_id,
                    node_label,
                    agent_id,
                    analyst_type,
                    output_field=output_field,
                )

            def logged_legacy(state, _node=legacy_node, _id=node_id, _label=node_label, _agent_id=agent_id, _output_field=output_field):
                return self._execute_agent_node_with_runtime(
                    state=state,
                    agent_callable=_node,
                    agent_id=_agent_id,
                    node_id=_id,
                    node_label=_label,
                    output_field=_output_field,
                    node_config=node.config,
                    legacy_adapter=True,
                )
            return logged_legacy

        # 智能体未实现，返回占位函数
        def placeholder_node(state, _id=node_id, _label=node_label, _agent_id=agent_id):
            logger.info(f"[节点执行] 🔸 {_id} ({_label}) - 占位执行 (智能体 {_agent_id} 未实现)")
            return {
                f"{_agent_id}_report": f"[{_agent_id}] 智能体未实现"
            }
        return placeholder_node

    def _has_agent_config_in_db(self, agent_id: str) -> bool:
        """
        检查 agent_configs 集合中是否存在该 agent_id 的配置。

        用于判断未注册的 Agent 是否可以用 UniversalAgent 替代。
        """
        try:
            db = self.binding_manager._db
            if db is None:
                return False
            doc = db.agent_configs.find_one({
                "agent_id": agent_id,
                "enabled": True,
                "$or": [
                    {"metadata.source": {"$ne": "agent_workshop"}},
                    {"metadata.source": "agent_workshop", "version_status": "active", "runtime_status": "active"},
                ],
            }, {"_id": 1})
            return doc is not None
        except Exception:
            return False

    def _normalize_callable_surfaces(self, raw_surfaces: Optional[List[Any]]) -> Set[str]:
        normalized = {
            str(item).strip().lower()
            for item in (raw_surfaces or [])
            if str(item).strip()
        }
        return normalized or set(_DEFAULT_CALLABLE_SURFACES)

    def _ensure_workflow_surface_access(
        self,
        agent_id: str,
        db_agent_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        metadata = self.registry.get_metadata(agent_id)
        metadata_surfaces = getattr(metadata, "callable_surfaces", None)
        db_surfaces = ((db_agent_config or {}).get("metadata") or {}).get("callable_surfaces")
        allowed_surfaces = self._normalize_callable_surfaces(db_surfaces or metadata_surfaces)

        if "workflow" not in allowed_surfaces:
            raise ValueError(f"Agent {agent_id} 当前不允许从 workflow 入口直接调用")

    def _resolve_agent_output_field(
        self,
        agent_id: str,
        node_config: Optional[Dict[str, Any]] = None,
        db_agent_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        config = node_config or {}
        if config.get("output_field"):
            return str(config["output_field"])

        if (db_agent_config or {}).get("output_field"):
            return str(db_agent_config["output_field"])

        db_metadata = (db_agent_config or {}).get("metadata") or {}
        if db_metadata.get("output_field"):
            return str(db_metadata["output_field"])

        metadata = self.registry.get_metadata(agent_id)
        if metadata and getattr(metadata, "output_field", None):
            return str(metadata.output_field)
        if metadata and getattr(metadata, "outputs", None):
            outputs = getattr(metadata, "outputs", []) or []
            if outputs and getattr(outputs[0], "name", None):
                return str(outputs[0].name)
        return None

    def _sanitize_runtime_value(self, value: Any, max_text_length: int = 2000, depth: int = 0) -> Any:
        if isinstance(value, str):
            return value[:max_text_length]
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if depth >= 1:
            return str(value)[:max_text_length]
        if isinstance(value, list):
            return [self._sanitize_runtime_value(item, max_text_length=max_text_length, depth=depth + 1) for item in value[:10]]
        if isinstance(value, dict):
            sanitized: Dict[str, Any] = {}
            for key, item in list(value.items())[:20]:
                sanitized[str(key)] = self._sanitize_runtime_value(item, max_text_length=max_text_length, depth=depth + 1)
            return sanitized
        return str(value)[:max_text_length]

    def _build_workflow_payload(self, state: Any) -> Dict[str, Any]:
        if not isinstance(state, dict):
            return {"raw_state": self._sanitize_runtime_value(state)}

        payload: Dict[str, Any] = {}
        preferred_keys = [
            "symbol",
            "ticker",
            "stock_symbol",
            "stock_code",
            "trade_date",
            "analysis_date",
            "market_type",
            "task",
            "task_description",
            "query",
        ]

        for key in preferred_keys:
            if key in state:
                payload[key] = self._sanitize_runtime_value(state.get(key))

        if not payload:
            snapshot = {}
            for key, value in state.items():
                if key.startswith("_") or key == "messages":
                    continue
                snapshot[key] = self._sanitize_runtime_value(value)
                if len(snapshot) >= 12:
                    break
            payload["state_snapshot"] = snapshot

        return payload

    def _extract_report_text(self, result: Dict[str, Any], output_field: Optional[str]) -> str:
        candidate_fields = [
            output_field,
            "final_report",
            "analysis_report",
            "summary",
            "analysis_result",
        ]
        for field_name in candidate_fields:
            if not field_name:
                continue
            value = result.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested_key in ("content", "markdown", "text", "message", "report"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, str) and nested_value.strip():
                        return nested_value.strip()

        for value in result.values():
            if isinstance(value, str) and value.strip() and len(value.strip()) > 20:
                return value.strip()
        return ""

    def _sanitize_structured_output(self, result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return {"raw_result": self._sanitize_runtime_value(result, max_text_length=4000)}

        sanitized: Dict[str, Any] = {}
        for key, value in result.items():
            if key == "messages":
                continue
            sanitized[str(key)] = self._sanitize_runtime_value(value, max_text_length=4000)
        return sanitized

    def _build_workflow_invocation_request(
        self,
        *,
        state: Any,
        agent_id: str,
        node_id: str,
        node_label: str,
        output_field: Optional[str],
        timeout_seconds: int,
    ) -> InvocationRequest:
        runtime_context = {}
        user_id = None
        thread_id = None
        execution_id = None
        parent_invocation_id = None
        root_invocation_id = None
        if isinstance(state, dict):
            runtime_context = dict(state.get("_workflow_runtime") or {})
            user_id = state.get("user_id") or runtime_context.get("user_id")
            thread_id = state.get("thread_id") or runtime_context.get("thread_id")
            execution_id = state.get("execution_id") or runtime_context.get("execution_id")
            lineage = state.get("invocation_lineage") if isinstance(state.get("invocation_lineage"), dict) else {}
            parent_invocation_id = lineage.get("current_invocation_id") or lineage.get("parent_invocation_id")
            root_invocation_id = lineage.get("root_invocation_id")
            if not user_id:
                context = state.get("context")
                if isinstance(context, dict):
                    user_id = context.get("user_id")
                    thread_id = thread_id or context.get("thread_id") or context.get("session_id")
                    execution_id = execution_id or context.get("request_id")
                    extra = context.get("extra") if isinstance(context.get("extra"), dict) else {}
                    parent_invocation_id = parent_invocation_id or context.get("request_id") or extra.get("invocation_id")
                    root_invocation_id = root_invocation_id or extra.get("root_invocation_id") or parent_invocation_id
                elif context is not None:
                    user_id = getattr(context, "user_id", None)
                    thread_id = thread_id or getattr(context, "thread_id", None) or getattr(context, "session_id", None)
                    execution_id = execution_id or getattr(context, "request_id", None)
                    extra = getattr(context, "extra", None)
                    if isinstance(extra, dict):
                        parent_invocation_id = parent_invocation_id or getattr(context, "request_id", None) or extra.get("invocation_id")
                        root_invocation_id = root_invocation_id or extra.get("root_invocation_id") or parent_invocation_id

        workflow_id = runtime_context.get("workflow_id") or self._workflow_id
        execution_id = execution_id or runtime_context.get("execution_id")
        invocation_id = f"winv_{uuid.uuid4().hex}"
        idempotency_key = f"{execution_id}:{node_id}" if execution_id else invocation_id

        return InvocationRequest(
            invocation_id=invocation_id,
            target_type=InvocationTargetType.AGENT,
            target_id=agent_id,
            action="execute",
            payload=self._build_workflow_payload(state),
            provenance=InvocationProvenance(
                source_type=InvocationSourceType.WORKFLOW,
                source_id=workflow_id,
                user_id=user_id,
                session_id=execution_id,
                thread_id=thread_id,
                workflow_id=workflow_id,
                step_id=node_id,
                trigger="workflow_node",
                metadata={
                    "node_label": node_label,
                    "state_keys": [
                        key for key in list(state.keys())[:30]
                        if isinstance(state, dict) and not str(key).startswith("_")
                    ] if isinstance(state, dict) else [],
                },
            ),
            policy=InvocationPolicy(
                idempotency_key=idempotency_key,
                timeout_seconds=timeout_seconds,
                lane=f"workflow.{workflow_id or 'default'}",
                visible_to_caller=True,
            ),
            metadata={
                "invocation_source": "workflow_builder",
                "node_id": node_id,
                "node_label": node_label,
                "output_field": output_field,
                "root_invocation_id": root_invocation_id or parent_invocation_id or invocation_id,
                "parent_invocation_id": parent_invocation_id,
            },
        )

    def _persist_workflow_invocation_record(
        self,
        request: InvocationRequest,
        result: InvocationResult,
    ) -> None:
        db = getattr(self.binding_manager, "_db", None)
        if db is None:
            return

        db.workflow_agent_invocations.update_one(
            {"invocation_id": request.invocation_id},
            {
                "$set": {
                    "invocation_id": request.invocation_id,
                    "root_invocation_id": request.metadata.get("root_invocation_id") or request.invocation_id,
                    "parent_invocation_id": request.metadata.get("parent_invocation_id"),
                    "workflow_id": request.provenance.workflow_id,
                    "execution_id": request.provenance.session_id,
                    "thread_id": request.provenance.thread_id,
                    "step_id": request.provenance.step_id,
                    "user_id": request.provenance.user_id,
                    "target_type": request.target_type.value,
                    "target_id": request.target_id,
                    "status": result.status.value,
                    "request": request.to_python_dict(),
                    "result": result.to_python_dict(),
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {"created_at": datetime.utcnow()},
            },
            upsert=True,
        )

    def _execute_agent_node_with_runtime(
        self,
        *,
        state: Any,
        agent_callable: Callable,
        agent_id: str,
        node_id: str,
        node_label: str,
        output_field: Optional[str],
        node_config: Optional[Dict[str, Any]] = None,
        legacy_adapter: bool = False,
    ) -> Dict[str, Any]:
        logger.info(
            f"[节点执行] 🚀 {node_id} ({node_label}) - 开始执行"
            + (f" (遗留适配器: {agent_id})" if legacy_adapter else "")
        )

        agent_metadata = self.registry.get_metadata(agent_id)
        agent_version = getattr(agent_metadata, "version", None)
        raw_maintenance_status = getattr(agent_metadata, "maintenance_status", None)
        if raw_maintenance_status is not None:
            agent_maintenance_status = getattr(raw_maintenance_status, "value", str(raw_maintenance_status))
        else:
            normalized_version = str(agent_version or "").lower()
            agent_maintenance_status = "unmaintained" if normalized_version.startswith(("1", "v1")) else "maintained"

        # 🔥 检查是否为废弃 Agent
        if agent_maintenance_status == "deprecated":
            import warnings
            warnings.warn(
                f"Agent '{agent_id}' 已废弃，请使用 v2 版本。该 Agent 将在未来的版本中被移除。",
                DeprecationWarning,
                stacklevel=3
            )
            logger.warning(f"[节点执行] ⚠️ Agent '{agent_id}' 已废弃，建议使用 v2 版本")

        invocation_request = self._build_workflow_invocation_request(
            state=state,
            agent_id=agent_id,
            node_id=node_id,
            node_label=node_label,
            output_field=output_field,
            timeout_seconds=180,
        )
        started_at = utc_now()

        _trace_recorder = None  # 🔑 统一执行轨迹埋点：提前初始化，确保 finally 可用
        try:
            agent_state = state
            if isinstance(state, dict):
                agent_state = {
                    **state,
                    "node_id": node_id,
                    "node_config": dict(node_config or {}),
                    "invocation_provenance": invocation_request.provenance.to_python_dict(),
                    "invocation_lineage": {
                        "current_invocation_id": invocation_request.invocation_id,
                        "parent_invocation_id": invocation_request.metadata.get("parent_invocation_id"),
                        "root_invocation_id": invocation_request.metadata.get("root_invocation_id") or invocation_request.invocation_id,
                    },
                }

            import time as _time
            _agent_start = _time.time()
            logger.info(f"[节点执行] ⏳ {node_id} ({node_label}) - 调用 agent_callable...")
            # 🔑 统一执行轨迹埋点：在节点执行层面启动轨迹采集
            # 这样无论适配器是否覆盖 execute，都能记录轨迹
            _agent_obj = agent_callable if hasattr(agent_callable, 'execute') else None
            _trace_recorder = None
            if _agent_obj is not None:
                from core.agents.execution_trace_recorder import start_execution_trace, is_trace_enabled
                if is_trace_enabled():
                    try:
                        _trace_recorder = start_execution_trace(_agent_obj, agent_state)
                        _agent_obj._last_trace_id = _trace_recorder.trace_id
                    except Exception as _trace_err:
                        logger.warning(f"⚠️ [节点执行] 启动轨迹采集失败（不影响执行）: {_trace_err}")

            raw_result = agent_callable(agent_state)
            _agent_elapsed = _time.time() - _agent_start
            logger.info(f"[节点执行] ⏱️ {node_id} ({node_label}) - agent_callable 执行完成, 耗时: {_agent_elapsed:.1f}s")
            result = raw_result if isinstance(raw_result, dict) else {
                (output_field or f"{agent_id}_report"): raw_result
            }

            # 🔑 统一执行轨迹埋点：记录解析后的输出
            if _trace_recorder:
                try:
                    _trace_recorder.record_parsed_output(result)
                except Exception:
                    pass

            logger.info(f"[节点执行] 📝 {node_id} ({node_label}) - 返回字段: {list(result.keys())}")

            invocation_result = InvocationResult(
                invocation_id=invocation_request.invocation_id,
                target_type=InvocationTargetType.AGENT,
                target_id=agent_id,
                status=InvocationStatus.SUCCEEDED,
                started_at=started_at,
                output_text=self._extract_report_text(result, output_field),
                structured_output=self._sanitize_structured_output(result),
                output_field=output_field,
                artifacts=[
                    InvocationArtifactRef(
                        ref_type="workflow_agent_invocation",
                        artifact_key=invocation_request.invocation_id,
                        title=f"Workflow节点调用：{node_label}",
                        summary=self._extract_report_text(result, output_field)[:300],
                        source_collection="workflow_agent_invocations",
                        output_field=output_field,
                        metadata={
                            "agent_id": agent_id,
                            "agent_version": agent_version,
                            "maintenance_status": agent_maintenance_status,
                            "node_id": node_id,
                            "workflow_id": invocation_request.provenance.workflow_id,
                        },
                    )
                ],
                metadata={
                    "node_id": node_id,
                    "node_label": node_label,
                    "workflow_id": invocation_request.provenance.workflow_id,
                    "execution_id": invocation_request.provenance.session_id,
                    "agent_version": agent_version,
                    "maintenance_status": agent_maintenance_status,
                    "legacy_adapter": legacy_adapter,
                    "root_invocation_id": invocation_request.metadata.get("root_invocation_id") or invocation_request.invocation_id,
                    "parent_invocation_id": invocation_request.metadata.get("parent_invocation_id"),
                },
            )
            self._persist_workflow_invocation_record(invocation_request, invocation_result)

            logger.info(f"[节点执行] ✅ {node_id} ({node_label}) - 执行完成")
            return result
        except Exception as exc:
            # 🔑 统一执行轨迹埋点：记录异常
            if _trace_recorder:
                try:
                    _trace_recorder.record_error(exc)
                except Exception:
                    pass

            invocation_result = InvocationResult(
                invocation_id=invocation_request.invocation_id,
                target_type=InvocationTargetType.AGENT,
                target_id=agent_id,
                status=InvocationStatus.FAILED,
                started_at=started_at,
                output_field=output_field,
                error_message=str(exc),
                metadata={
                    "node_id": node_id,
                    "node_label": node_label,
                    "workflow_id": invocation_request.provenance.workflow_id,
                    "execution_id": invocation_request.provenance.session_id,
                    "agent_version": agent_version,
                    "maintenance_status": agent_maintenance_status,
                    "legacy_adapter": legacy_adapter,
                },
            )
            self._persist_workflow_invocation_record(invocation_request, invocation_result)
            logger.exception(f"[节点执行] ❌ {node_id} ({node_label}) - 执行失败: {exc}")

            field_key = output_field or f"{agent_id}_report"
            degraded = {
                field_key: (
                    f"[{node_label} 执行失败]\n\n"
                    f"该分析节点在运行过程中遇到错误，已跳过。\n"
                    f"错误摘要: {type(exc).__name__}\n\n"
                    f"其余节点的分析结果不受影响，请参考其他报告。"
                ),
                f"_node_errors": {
                    **(state.get("_node_errors", {}) if isinstance(state, dict) else {}),
                    node_id: {
                        "agent_id": agent_id,
                        "label": node_label,
                        "error": str(exc)[:500],
                    },
                },
            }
            logger.warning(
                f"[节点执行] ⚠️ {node_id} ({node_label}) - 降级处理，工作流继续执行"
            )
            return degraded
        finally:
            # 🔑 统一执行轨迹埋点：完成采集并写入 MongoDB（非阻塞）
            if _trace_recorder:
                try:
                    _trace_recorder.finish()
                except Exception:
                    pass

    def _try_create_legacy_agent(self, agent_id: str) -> Optional[Callable]:
        """
        尝试使用遗留适配器创建智能体 — 已停用

        v3.0 起旧版 agent（不带 _v2 后缀）不再维护，所有入口已封堵。
        详见 docs/99-archive/deprecated-features/legacy-agents-deprecation.md

        Args:
            agent_id: 智能体 ID

        Returns:
            始终返回 None（旧版 agent 已停用，走 placeholder_node 占位）
        """
        logger.warning(
            "[已停用] _try_create_legacy_agent 已停用，agent_id=%s 应使用对应的 _v2 版本。"
            "详见 docs/99-archive/deprecated-features/legacy-agents-deprecation.md",
            agent_id,
        )
        return None
        # pragma: no cover - 以下旧版 factory_map 代码保留但不执行，为 v4.0 删除做准备
        # 智能体到工厂函数的映射
        factory_map = {
            # 分析师
            "market_analyst": ("tradingagents.agents.analysts.market_analyst", "create_market_analyst", "toolkit"),
            "news_analyst": ("tradingagents.agents.analysts.news_analyst", "create_news_analyst", "toolkit"),
            "fundamentals_analyst": ("tradingagents.agents.analysts.fundamentals_analyst", "create_fundamentals_analyst", "toolkit"),
            "social_analyst": ("tradingagents.agents.analysts.social_media_analyst", "create_social_media_analyst", "toolkit"),
            # 🆕 大盘分析师和板块分析师（需要 toolkit，但内部不使用工具调用机制）
            "index_analyst": ("tradingagents.agents.analysts.index_analyst", "create_index_analyst", "toolkit"),
            "sector_analyst": ("tradingagents.agents.analysts.sector_analyst", "create_sector_analyst", "toolkit"),
            # 研究员
            "bull_researcher": ("tradingagents.agents.researchers.bull_researcher", "create_bull_researcher", "bull_memory"),
            "bear_researcher": ("tradingagents.agents.researchers.bear_researcher", "create_bear_researcher", "bear_memory"),
            # 研究整合员
            "trader": ("tradingagents.agents.trader.trader", "create_trader", "trader_memory"),
            # 管理者
            "research_manager": ("tradingagents.agents.managers.research_manager", "create_research_manager", "invest_judge_memory"),
            "risk_manager": ("tradingagents.agents.managers.risk_manager", "create_risk_manager", "risk_manager_memory"),
            # 风险辩论者
            "risky_analyst": ("tradingagents.agents.risk_mgmt.aggresive_debator", "create_risky_debator", None),
            "safe_analyst": ("tradingagents.agents.risk_mgmt.conservative_debator", "create_safe_debator", None),
            "neutral_analyst": ("tradingagents.agents.risk_mgmt.neutral_debator", "create_neutral_debator", None),
        }

        if agent_id not in factory_map:
            return None

        module_path, func_name, dep_type = factory_map[agent_id]

        try:
            import importlib
            module = importlib.import_module(module_path)
            factory_func = getattr(module, func_name)

            # 🔥 关键修复：根据 agent_id 判断应该使用 quick 还是 deep LLM
            # 使用深度模型的 Agent：
            # 1. 管理者（research_manager, risk_manager）- 需要综合大量信息做决策
            # 2. 风险分析师（risky/safe/neutral_analyst）- 需要处理大量分析报告
            llm_type = "quick"  # 默认使用快速模型
            if agent_id in [
                "research_manager", "risk_manager",  # 管理者
                "risky_analyst", "safe_analyst", "neutral_analyst"  # 旧版风险分析师
            ]:
                llm_type = "deep"  # 使用深度模型
                logger.info(f"[遗留适配器] 🔧 {agent_id} 使用深度分析模型 (deep_think_llm)")
            else:
                logger.info(f"[遗留适配器] 🔧 {agent_id} 使用快速分析模型 (quick_think_llm)")
            
            # 🔥 获取 Agent 配置的 temperature（如果存在）
            # 注意：遗留适配器创建的 Agent 可能没有从数据库加载配置
            # 这里暂时使用默认 LLM，后续可以考虑改进
            llm = self._legacy_provider.get_llm(llm_type)

            # 根据依赖类型获取第二个参数
            if dep_type == "toolkit":
                second_arg = self._legacy_provider.get_toolkit()
            elif dep_type:
                second_arg = self._legacy_provider.get_memory(dep_type)
            else:
                second_arg = None

            # 创建节点函数
            if second_arg is not None:
                node_func = factory_func(llm, second_arg)
            else:
                # 风险辩论者只需要 LLM
                node_func = factory_func(llm)

            logger.info(f"[遗留适配器] 成功创建: {agent_id}")
            return node_func

        except Exception as e:
            logger.warning(f"[遗留适配器] 创建失败 {agent_id}: {e}")
            return None

    def _create_condition_node(self, node: NodeDefinition) -> Callable:
        """创建条件节点"""
        condition_expr = node.condition or "True"
        node_id = node.id
        node_label = node.label or node_id

        def condition_node(state):
            logger.info(f"[节点执行] 🔀 {node_id} ({node_label}) - 条件判断")
            # 评估条件
            try:
                result = eval(condition_expr, {"state": state})
                logger.info(f"[节点执行] 🔀 {node_id} 结果: {result}")
                return {"_condition_result": bool(result)}
            except Exception as e:
                logger.error(f"[节点执行] ❌ {node_id} 条件评估错误: {e}")
                return {"_condition_result": True, "_condition_error": str(e)}

        return condition_node

    def _create_parallel_node(self, node: NodeDefinition) -> Callable:
        """创建并行节点 (标记开始)"""
        node_id = node.id
        node_label = node.label or node_id

        def parallel_node(state):
            logger.info(f"[节点执行] ⚡ {node_id} ({node_label}) - 并行开始")
            return {"_parallel_start": node_id}
        return parallel_node

    def _create_merge_node(self, node: NodeDefinition) -> Callable:
        """创建合并节点"""
        node_id = node.id
        node_label = node.label or node_id

        def merge_node(state):
            logger.info(f"[节点执行] 🔗 {node_id} ({node_label}) - 合并完成")
            return {"_parallel_end": node_id}
        return merge_node

    def _create_debate_node(self, node: NodeDefinition) -> Callable:
        """
        创建辩论节点 - 协调多个参与者进行多轮辩论

        辩论节点本身不执行分析，而是初始化辩论状态。
        实际的辩论流程通过条件边控制。

        重要：必须初始化辩论状态字典，包含 count=0，
        因为研究员智能体期望 state["investment_debate_state"]["count"] 存在
        """
        participants = node.config.get("participants", [])
        rounds = node.config.get("rounds", 1)
        node_id = node.id
        node_label = node.label or node_id

        # 根据辩论节点 ID 确定要初始化的状态键
        # "debate" -> investment_debate_state
        # "risk_debate" -> risk_debate_state
        is_risk_debate = "risk" in node_id.lower()
        state_key = "risk_debate_state" if is_risk_debate else "investment_debate_state"

        def debate_node(state):
            logger.info(f"[节点执行] 💬 {node_id} ({node_label}) - 辩论开始, 参与者: {participants}")

            # 初始化辩论状态字典
            # 这是研究员智能体期望的状态结构
            if is_risk_debate:
                # 风险辩论状态
                debate_state = {
                    "risky_history": "",
                    "safe_history": "",
                    "neutral_history": "",
                    "history": "",
                    "latest_speaker": "",
                    "current_risky_response": "",
                    "current_safe_response": "",
                    "current_neutral_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            else:
                # 投资辩论状态
                debate_state = {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                }

            logger.info(f"[辩论初始化] 初始化 {state_key} 状态: count=0")

            return {
                f"{node_id}_status": "debate_started",
                "_debate_node": node_id,
                "_debate_participants": participants,
                "_debate_rounds": rounds,
                state_key: debate_state,  # 🔥 关键：初始化辩论状态
            }
        return debate_node

    def _create_debate_participant_wrapper(
        self,
        node: NodeDefinition,
        debate_key: str
    ) -> Callable:
        """
        为辩论参与者包装执行函数，自动递增辩论计数

        使用 operator.add 作为 reducer，每次返回增量 1
        """
        original_func = self._create_agent_node(node)

        def wrapped(state):
            # 先执行原始函数（已包含日志）
            result = original_func(state)
            # 返回增量 1（会被 operator.add 累加到当前值）
            result[debate_key] = 1
            return result

        return wrapped

    @staticmethod
    def _merge_debate_states(
        old: Optional[Dict[str, Any]],
        new: Dict[str, Any],
    ) -> Dict[str, Any]:
        """A3: 按发言顺序合并两个辩论状态（并行开局专用）

        规则：
        - history：按参与者顺序拼接（保证完整辩论史有序）
        - 其他字段（各自的 *_history / current_response / latest_speaker）：
          非空值优先（避免并行双方基于同一初始 state 拷贝时互相覆盖为空）
        """
        if not old:
            return dict(new)
        merged = dict(old)
        for k, v in new.items():
            if k == "history":
                merged["history"] = (
                    str(merged.get("history") or "") + "\n" + str(v or "")
                ).strip("\n")
            elif v not in (None, ""):
                merged[k] = v
        return merged

    def _create_parallel_opening_node_func(
        self,
        debate_id: str,
        config: Dict[str, Any],
        definition: WorkflowDefinition,
    ) -> Callable:
        """A3: 创建投资辩论第一轮并行开局节点

        内部以线程池并行执行全部参与者（乐观/审慎研究员各自基于同一份
        分析师材料独立产出初始简报），手动合并共享 debate_state，
        count 增量 = 参与者数（operator.add reducer 累加）。

        出边由 _add_edges 挂条件路由：count >= max → next_node（如
        research_manager）；否则回到轮循（participants[count % N] 继续
        对抗辩论）。原串行路径通过 state["_parallel_opening"] 开关保留。
        """
        participants = list(config["participants"])
        debate_key = config["debate_key"]
        # 投资辩论专用（风险辩论由 A9-P1 接管深度档，不走此路径）
        debate_state_field = "investment_debate_state"

        # 预创建参与者原始执行函数（每次独立创建 Agent 实例，并发安全）
        participant_funcs = []
        for pid in participants:
            node_def = definition.get_node(pid)
            if node_def is None:
                raise ValueError(f"并行开局：参与者节点不存在: {pid}")
            participant_funcs.append((pid, self._create_node_function(node_def)))

        def parallel_opening_node(state):
            t0 = time.time()
            logger.info(
                f"[节点执行] ⚡ {debate_id}_parallel_opening (辩论并行开局) - "
                f"参与者并行执行: {participants}"
            )
            # 浅拷贝 state 隔离并发读写
            with ThreadPoolExecutor(max_workers=len(participant_funcs)) as pool:
                futures = {
                    pid: pool.submit(fn, dict(state))
                    for pid, fn in participant_funcs
                }
                # 按参与顺序收集（保证 history 拼接顺序确定）
                results = {pid: futures[pid].result() for pid, _ in participant_funcs}

            # 合并：独立字段（bull_report / bear_report 等）直接并集；
            # 共享 debate_state 深合并
            merged: Dict[str, Any] = {}
            merged_debate: Optional[Dict[str, Any]] = None
            for pid, res in (results or {}).items():
                if not isinstance(res, dict):
                    logger.warning(f"[A3] 参与者 {pid} 返回非 dict 结果，跳过: {type(res)}")
                    continue
                for k, v in res.items():
                    if k == debate_state_field and isinstance(v, dict):
                        merged_debate = self._merge_debate_states(merged_debate, v)
                    else:
                        merged[k] = v
            if merged_debate is None:
                merged_debate = dict(state.get(debate_state_field) or {})
            merged[debate_state_field] = merged_debate
            # count 增量 = 参与者数（operator.add reducer 累加到当前值）
            merged[debate_key] = len(participants)
            logger.info(
                f"[节点执行] ✅ {debate_id}_parallel_opening - 并行开局完成, "
                f"耗时 {time.time() - t0:.1f}s, 参与者 {len(participants)} 个"
            )
            return merged

        return parallel_opening_node

    def _create_risk_self_debate_node_func(self, debate_id: str) -> Callable:
        """
        A9-P1: 创建风险自我辩论节点函数（单节点替代风险三角多轮辩论）。

        构造合成 NodeDefinition 复用 _create_agent_node 的完整创建链
        （数据库配置合并、deep LLM 选择、执行轨迹包装等），
        agent 实现为 core/agents/adapters/risk_self_debate_v2.py。
        """
        node = NodeDefinition(
            id=f"{debate_id}_self_debate",
            type=NodeType.RISK,
            agent_id="risk_self_debate_v2",
            label="风险三视角自我辩论",
            config={
                "description": "单节点内完成高弹性/防御/基准三视角质证（A9-P1 深度档路径）",
            },
        )
        return self._create_agent_node(node)

    def _create_manager_with_debate_reflection(
        self,
        node: NodeDefinition,
        debate_state_field: str,
    ) -> Callable:
        """为管理者节点（research_manager / risk_manager）包装执行函数。

        v3.6.0 项8：管理者产出裁决后，触发辩论反思节点，把辩论历史+裁决
        提炼为结构化 debate_lesson 教训，写入 AGENT_EXPERIENCE scope。

        反思在独立线程中执行（run_reflection_sync 内部处理 sync→async），
        失败时 helper 内部降级，不阻塞主工作流。
        """
        original_func = self._create_agent_node(node)
        node_id = node.id
        agent_id = node.agent_id or node_id
        debate_type = (
            "risk_debate_state" if debate_state_field == "risk_debate_state"
            else "investment_debate_state"
        )

        def wrapped(state):
            # 1. 先执行管理者原始逻辑（产出 judge_decision / final_trade_decision 等）
            result = original_func(state)

            # 2. 触发辩论反思（失败不影响主流程）
            try:
                _trigger_debate_reflection(
                    state=state,
                    result=result,
                    debate_state_field=debate_state_field,
                    debate_type=debate_type,
                    agent_id=agent_id,
                    node_id=node_id,
                )
            except Exception as exc:
                logger.warning(
                    "[辩论反思] 触发失败 node=%s agent=%s: %s",
                    node_id, agent_id, exc,
                )

            return result

        return wrapped

    def _add_edges(
        self,
        graph: StateGraph,
        definition: WorkflowDefinition,
        debate_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        analyst_nodes_info: Optional[Dict[str, str]] = None,
        risk_self_debate_nodes: Optional[Set[str]] = None,
        parallel_opening_nodes: Optional[Set[str]] = None,
    ) -> None:
        """
        添加边到图

        辩论流程设计：
        - 辩论节点 → 第一个参与者（普通边）
        - 参与者之间使用条件边（检查计数决定继续或结束）
        - 最后一个参与者 → 下一阶段（通过条件边控制）
        - A9-P1：风险辩论入口使用条件边，state["_risk_self_debate"]=True 时
          路由到隐藏的自我辩论单节点（深度/全面档），否则走原参与者路径
        - A3：投资辩论入口使用条件边，state["_parallel_opening"]=True 时
          路由到隐藏的并行开局节点（第一轮乐观/审慎研究员并行出简报，
          后续轮次回原轮循），否则走原串行参与者路径

        分析师工具循环设计：
        - 分析师节点 → 条件边 → 工具节点/消息清理节点
        - 工具节点 → 分析师节点（循环）
        - 消息清理节点 → 下一个节点
        """
        start_node = definition.get_start_node()
        added_edges: Set[tuple] = set()
        merge_barriers: Dict[str, Set[str]] = {}

        def add_merge_predecessor(merge_node_id: str, predecessor: str) -> None:
            merge_barriers.setdefault(merge_node_id, set()).add(predecessor)
            logger.info(f"[合并屏障] 收集上游: {predecessor} -> {merge_node_id}")

        def merge_waits_all(merge_node: NodeDefinition) -> bool:
            config = merge_node.config or {}
            strategy = str(config.get("strategy") or config.get("merge_strategy") or "wait_all").strip().lower()
            return strategy in {"", "wait_all", "wait-all", "all"}

        if debate_configs is None:
            debate_configs = self._identify_debate_configs(definition)

        if analyst_nodes_info is None:
            analyst_nodes_info = {}

        if risk_self_debate_nodes is None:
            risk_self_debate_nodes = set()

        if parallel_opening_nodes is None:
            parallel_opening_nodes = set()

        # 收集所有辩论参与者
        all_participants: Set[str] = set()
        for config in debate_configs.values():
            all_participants.update(config["participants"])

        # 添加 START 边
        if start_node:
            for edge in definition.get_edges_from(start_node.id):
                graph.add_edge(START, edge.target)

        # 1. 先处理辩论流程的边
        for debate_id, config in debate_configs.items():
            participants = config["participants"]

            # A9-P1: 风险辩论入口条件路由
            # state["_risk_self_debate"]=True → 单节点自我辩论路径（深度/全面档）
            # 否则 → 原风险三角多 agent 辩论路径（默认，行为不变）
            self_debate_node_id = f"{debate_id}_self_debate"
            if self_debate_node_id in risk_self_debate_nodes:
                def debate_entry_router(
                    state,
                    _first_participant=participants[0],
                    _self_debate_node=self_debate_node_id,
                    _debate_id=debate_id,
                ):
                    if state.get("_risk_self_debate"):
                        logger.info(
                            f"[A9-P1] 风险自我辩论已启用: {_debate_id} -> {_self_debate_node}"
                        )
                        return _self_debate_node
                    return _first_participant

                graph.add_conditional_edges(
                    debate_id,
                    debate_entry_router,
                    [participants[0], self_debate_node_id],
                )
                added_edges.add((debate_id, participants[0]))
                added_edges.add((debate_id, self_debate_node_id))

                # 自我辩论节点 → 辩论后的下一节点（如 risk_manager）
                next_node = config["next_node"]
                if next_node:
                    next_node_def = definition.get_node(next_node)
                    if (
                        next_node_def
                        and next_node_def.type == NodeType.MERGE
                        and merge_waits_all(next_node_def)
                    ):
                        add_merge_predecessor(next_node, self_debate_node_id)
                    else:
                        graph.add_edge(self_debate_node_id, next_node)
                    added_edges.add((self_debate_node_id, next_node))
                else:
                    graph.add_edge(self_debate_node_id, END)
                logger.info(
                    f"[A9-P1] 风险辩论入口条件路由: {debate_id} -> "
                    f"[{participants[0]}(原路径), {self_debate_node_id}(自我辩论)]"
                )
            else:
                # A3: 投资辩论入口条件路由
                # state["_parallel_opening"]=True → 并行开局节点（第一轮并行出简报）
                # 否则 → 原串行路径（辩论节点 → 第一个参与者）
                po_node_id = f"{debate_id}_parallel_opening"
                if po_node_id in parallel_opening_nodes:
                    def opening_entry_router(
                        state,
                        _first_participant=participants[0],
                        _po_node=po_node_id,
                        _debate_id=debate_id,
                    ):
                        if state.get("_parallel_opening"):
                            logger.info(
                                f"[A3] 投资辩论并行开局已启用: {_debate_id} -> {_po_node}"
                            )
                            return _po_node
                        return _first_participant

                    graph.add_conditional_edges(
                        debate_id,
                        opening_entry_router,
                        [participants[0], po_node_id],
                    )
                    added_edges.add((debate_id, participants[0]))
                    added_edges.add((debate_id, po_node_id))

                    # 并行开局 → 条件路由（复用轮循语义）：
                    # count >= rounds × 参与者数 → next_node（如 research_manager）
                    # 否则 → participants[count % N] 继续对抗辩论（原参与者条件边接管后续）
                    _po_max_rounds = int(config["rounds"]) if config["rounds"] else 1
                    _po_debate_key = config["debate_key"]
                    _po_next_node = config["next_node"]
                    _po_num_participants = len(participants)
                    _po_participants = list(participants)

                    def opening_exit_router(
                        state,
                        _debate_key=_po_debate_key,
                        _max_rounds=_po_max_rounds,
                        _next_node=_po_next_node,
                        _num_participants=_po_num_participants,
                        _participants=_po_participants,
                    ):
                        count = state.get(_debate_key, 0)
                        dynamic_rounds = state.get("_max_debate_rounds", _max_rounds)
                        max_count = dynamic_rounds * _num_participants
                        if count >= max_count:
                            logger.info(
                                f"[A3] 并行开局路由: count={count} >= {max_count} "
                                f"-> {_next_node or 'END'} (辩论结束)"
                            )
                            return _next_node if _next_node else END
                        target = _participants[count % _num_participants]
                        logger.info(
                            f"[A3] 并行开局路由: count={count} -> {target} (继续辩论)"
                        )
                        return target

                    _po_exit_targets = list(participants)
                    if _po_next_node and _po_next_node not in _po_exit_targets:
                        _po_exit_targets.append(_po_next_node)
                    graph.add_conditional_edges(
                        po_node_id, opening_exit_router, _po_exit_targets
                    )
                    logger.info(
                        f"[A3] 投资辩论入口条件路由: {debate_id} -> "
                        f"[{participants[0]}(原路径), {po_node_id}(并行开局)]"
                    )
                else:
                    # 辩论节点 → 第一个参与者（原路径）
                    graph.add_edge(debate_id, participants[0])
                    added_edges.add((debate_id, participants[0]))

            # 为每个参与者添加条件边（原逻辑保留，自我辩论路径不会经过）
            for i, participant in enumerate(participants):
                self._add_participant_conditional_edge(
                    graph, participant, config, i, debate_id
                )
                # 标记所有从参与者出发的边为已处理
                for edge in definition.get_edges_from(participant):
                    added_edges.add((participant, edge.target))

        # 2. 处理分析师节点的工具循环边
        for node_id, analyst_type in analyst_nodes_info.items():
            tools_node_id = f"tools_{node_id}"
            clear_node_id = f"msg_clear_{node_id}"

            # 分析师节点 → 条件边 → 工具节点/消息清理节点
            condition_func = self._create_analyst_condition_func(node_id, analyst_type)
            graph.add_conditional_edges(
                node_id,
                condition_func,
                [tools_node_id, clear_node_id]
            )
            logger.info(f"[工具循环] 添加条件边: {node_id} -> [{tools_node_id}, {clear_node_id}]")

            # 工具节点 → 分析师节点（循环）
            graph.add_edge(tools_node_id, node_id)
            logger.info(f"[工具循环] 添加循环边: {tools_node_id} -> {node_id}")

            # 找到分析师节点的下一个目标节点
            for edge in definition.get_edges_from(node_id):
                target = edge.target
                target_node = definition.get_node(target)

                # 消息清理节点 → 原来的目标节点
                if target_node and target_node.type == NodeType.END:
                    graph.add_edge(clear_node_id, END)
                    logger.info(f"[工具循环] 添加出边: {clear_node_id} -> END")
                elif target_node and target_node.type == NodeType.MERGE and merge_waits_all(target_node):
                    add_merge_predecessor(target, clear_node_id)
                    logger.info(f"[工具循环] 延迟添加合并屏障出边: {clear_node_id} -> {target}")
                else:
                    graph.add_edge(clear_node_id, target)
                    logger.info(f"[工具循环] 添加出边: {clear_node_id} -> {target}")

                # 标记边为已处理
                added_edges.add((node_id, target))

        # 3. 处理普通边
        for edge in definition.edges:
            source_node = definition.get_node(edge.source)
            target_node = definition.get_node(edge.target)

            if source_node is None or target_node is None:
                continue
            if source_node.type == NodeType.START:
                continue

            edge_key = (edge.source, edge.target)
            if edge_key in added_edges:
                continue

            # 跳过辩论节点的所有出边（已在上面处理）
            if source_node.type == NodeType.DEBATE:
                continue

            # 跳过参与者的边（已在上面处理）
            if source_node.id in all_participants:
                continue

            # 跳过分析师节点的边（已在上面处理）
            if source_node.id in analyst_nodes_info:
                continue

            # 普通边
            if target_node.type == NodeType.END:
                graph.add_edge(edge.source, END)
            elif edge.type == EdgeType.CONDITIONAL:
                self._add_conditional_edge(graph, edge, definition)
            elif target_node.type == NodeType.MERGE and merge_waits_all(target_node):
                add_merge_predecessor(edge.target, edge.source)
            else:
                graph.add_edge(edge.source, edge.target)
            added_edges.add(edge_key)

        # 4. 为合并节点添加真正的 barrier 边
        # LangGraph 支持 graph.add_edge([a, b, c], merge)，只有所有上游都完成后才触发 merge。
        # 否则多个并行分支逐个到达 merge 时，会重复触发 merge 以及其下游节点。
        for merge_node_id, predecessors in merge_barriers.items():
            ordered_predecessors = sorted(predecessors)
            if len(ordered_predecessors) == 1:
                graph.add_edge(ordered_predecessors[0], merge_node_id)
                logger.info(
                    f"[合并屏障] 单上游普通边: {ordered_predecessors[0]} -> {merge_node_id}"
                )
            else:
                graph.add_edge(ordered_predecessors, merge_node_id)
                logger.info(
                    f"[合并屏障] 添加 barrier 边: {ordered_predecessors} -> {merge_node_id}"
                )

    def _add_participant_conditional_edge(
        self,
        graph: StateGraph,
        participant: str,
        debate_config: Dict[str, Any],
        participant_index: int,
        debate_id: str
    ) -> None:
        """为辩论参与者添加条件边"""
        participants = debate_config["participants"]
        max_rounds = int(debate_config["rounds"]) if debate_config["rounds"] else 1
        next_node = debate_config["next_node"]
        debate_key = debate_config["debate_key"]
        num_participants = len(participants)

        # 下一个参与者
        next_idx = (participant_index + 1) % num_participants
        next_participant = participants[next_idx]

        # 根据辩论类型选择动态轮数的 state key
        # "risk" 相关的辩论使用 _max_risk_rounds，其他使用 _max_debate_rounds
        is_risk_debate = "risk" in debate_id.lower()
        dynamic_rounds_key = "_max_risk_rounds" if is_risk_debate else "_max_debate_rounds"

        # 创建路由函数
        def create_router(
            _debate_key: str,
            _max_rounds: int,
            _next_participant: str,
            _next_node: str,
            _num_participants: int,
            _dynamic_rounds_key: str,
            _participant: str
        ):
            def router(state):
                count = state.get(_debate_key, 0)
                dynamic_rounds = state.get(_dynamic_rounds_key, _max_rounds)
                max_count = dynamic_rounds * _num_participants
                logger.info(
                    f"[辩论路由] {_participant}: count={count}, max={max_count} "
                    f"(rounds={dynamic_rounds}, participants={_num_participants})"
                )
                if count >= max_count:
                    logger.info(f"[辩论路由] {_participant} -> {_next_node} (辩论结束)")
                    return _next_node if _next_node else END
                logger.info(f"[辩论路由] {_participant} -> {_next_participant} (继续辩论)")
                return _next_participant
            return router

        router = create_router(
            debate_key, max_rounds, next_participant, next_node,
            num_participants, dynamic_rounds_key, participant
        )

        targets = [next_participant]
        if next_node and next_node != next_participant:
            targets.append(next_node)

        graph.add_conditional_edges(participant, router, targets)

    def _identify_debate_configs(
        self, definition: WorkflowDefinition
    ) -> Dict[str, Dict[str, Any]]:
        """识别工作流中的辩论配置"""
        debate_configs = {}

        for node in definition.nodes:
            if node.type == NodeType.DEBATE:
                participants = node.config.get("participants", [])
                rounds_raw = node.config.get("rounds", 1)

                # 处理 rounds 可能是字符串的情况（如 "auto", "1" 等）
                if isinstance(rounds_raw, str):
                    if rounds_raw.lower() == "auto" or not rounds_raw.isdigit():
                        rounds = 1  # 默认1轮，实际会从 state 读取
                    else:
                        rounds = int(rounds_raw)
                else:
                    rounds = int(rounds_raw) if rounds_raw else 1

                # 找到辩论后的下一个节点
                next_node = None
                for edge in definition.get_edges_from(node.id):
                    target = definition.get_node(edge.target)
                    if target and target.id not in participants:
                        next_node = edge.target
                        break

                debate_configs[node.id] = {
                    "participants": participants,
                    "rounds": rounds,
                    "next_node": next_node,
                    "debate_key": f"_debate_{node.id}_count"
                }

        return debate_configs

    def _add_conditional_edge(
        self,
        graph: StateGraph,
        edge: EdgeDefinition,
        definition: WorkflowDefinition
    ) -> None:
        """添加普通条件边"""
        all_edges = definition.get_edges_from(edge.source)

        def route(state):
            result = state.get("_condition_result", True)
            for e in all_edges:
                if e.condition == "true" and result:
                    return e.target
                if e.condition == "false" and not result:
                    return e.target
            return all_edges[0].target if all_edges else END

        targets = {e.target for e in all_edges}
        graph.add_conditional_edges(edge.source, route, list(targets))
