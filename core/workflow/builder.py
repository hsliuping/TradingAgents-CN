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
from typing import Any, Callable, Dict, List, Optional, Set

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
from ..agents import AgentRegistry, AgentFactory, AgentConfig

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
    "social_analyst_v2": "social",
}


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
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试或重新配置）"""
        cls._instance = None

    def get_llm(self, llm_type: str = "quick", temperature: Optional[float] = None):
        """
        获取 LLM 实例

        Args:
            llm_type: "quick" 或 "deep"
            temperature: 可选，如果指定则创建新的 LLM 实例（用于 Agent 特定的温度配置）
        """
        # 如果指定了 temperature，创建新的 LLM 实例
        if temperature is not None:
            logger.info(f"[依赖提供者] 创建自定义温度 LLM: type={llm_type}, temperature={temperature}")
            return self._create_custom_llm(llm_type, temperature)
        
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
            logger.info(f"  - Quick API Key: 已配置 (前3位: {quick_api_key[:3] if len(quick_api_key) >= 3 else 'N/A'})")
        else:
            logger.info(f"  - Quick API Key: 空")
        logger.info(f"  - Deep: provider={deep_provider}, model={deep_model}, url={deep_url[:50] if deep_url else 'None'}...")
        logger.info(f"  - Deep API Key 来源: {'用户显式指定' if deep_api_key_from_config else ('数据库配置' if deep_api_key_from_db else ('继承 Quick' if quick_api_key else '未配置（将使用环境变量）'))}")
        if deep_api_key:
            logger.info(f"  - Deep API Key: 已配置 (前3位: {deep_api_key[:3] if len(deep_api_key) >= 3 else 'N/A'})")
        else:
            logger.info(f"  - Deep API Key: 空")

        try:
            # 创建快速模型
            self._quick_llm = create_llm_by_provider(
                provider=quick_provider,
                model=quick_model,
                backend_url=quick_url,
                temperature=self._config.get("quick_temperature", 0.1),
                max_tokens=self._config.get("quick_max_tokens", 2000),
                timeout=self._config.get("quick_timeout", 60),
                api_key=quick_api_key
            )

            # 创建深度模型
            self._deep_llm = create_llm_by_provider(
                provider=deep_provider,
                model=deep_model,
                backend_url=deep_url,
                temperature=self._config.get("deep_temperature", 0.1),
                max_tokens=self._config.get("deep_max_tokens", 4000),
                timeout=self._config.get("deep_timeout", 120),
                api_key=deep_api_key
            )

            logger.info("[依赖提供者] LLM 实例创建成功")
            logger.info(f"  - Quick LLM: {type(self._quick_llm).__name__}")
            logger.info(f"  - Deep LLM: {type(self._deep_llm).__name__}")
        except Exception as e:
            logger.error(f"[依赖提供者] LLM 创建失败: {e}")
            raise

    def _create_custom_llm(self, llm_type: str, temperature: float):
        """
        创建自定义温度的 LLM 实例（用于 Agent 特定的温度配置）

        Args:
            llm_type: "quick" 或 "deep"
            temperature: 温度参数

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

        # 使用默认的 max_tokens 和 timeout
        max_tokens = self._config.get(f"{llm_type}_max_tokens", 2000 if llm_type == "quick" else 4000)
        timeout = self._config.get(f"{llm_type}_timeout", 60 if llm_type == "quick" else 120)

        logger.info(f"[依赖提供者] 创建自定义温度 LLM: type={llm_type}, model={model}, temperature={temperature}")
        logger.info(f"  - API Key 来源: {'用户显式指定' if api_key_from_config else ('数据库配置' if api_key_from_db else '未配置（将使用环境变量）')}")
        if api_key:
            # 打印 API Key 的前3位和后3位，用于调试验证
            key_preview = f"{api_key[:3]}...{api_key[-3:]}" if len(api_key) > 6 else api_key[:3] + "..."
            logger.info(f"  - API Key: 已配置 (前3位: {api_key[:3] if len(api_key) >= 3 else 'N/A'})")
        else:
            logger.info(f"  - API Key: 空")

        return create_llm_by_provider(
            provider=provider,
            model=model,
            backend_url=url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            api_key=api_key
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

                        # 确定 API Key
                        api_key = None
                        if model_api_key and model_api_key.strip() and model_api_key != "your-api-key":
                            api_key = model_api_key
                        elif provider_doc and provider_doc.get("api_key"):
                            pk = provider_doc["api_key"]
                            if pk and pk.strip() and pk != "your-api-key" and not pk.startswith("sk-xxx"):
                                api_key = pk

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
        from tradingagents.agents.utils.memory import FinancialSituationMemory
        from tradingagents.default_config import DEFAULT_CONFIG

        config = {**DEFAULT_CONFIG, **self._config}

        if config.get("memory_enabled", True):
            self._memories[memory_type] = FinancialSituationMemory(memory_type, config)
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

        # 添加边（使用过滤后的定义）
        self._add_edges(graph, filtered_definition, debate_configs, analyst_nodes_info)

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
        analyst_type: str
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
            result = analyst_node(analyst_state)

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

        def merge_dict(left: dict, right: dict) -> dict:
            """
            智能合并两个字典，用于处理并发更新

            特殊处理：对于辩论状态的历史字段（*_history），
            优先保留非空值，避免被空字符串覆盖
            """
            if left is None:
                return right
            if right is None:
                return left

            result = left.copy()

            # 需要特殊处理的历史字段
            history_fields = [
                'bull_history', 'bear_history', 'history',
                'risky_history', 'safe_history', 'neutral_history'
            ]

            for key, value in right.items():
                # 对于历史字段，只有当新值非空时才更新
                if key in history_fields:
                    old_value = result.get(key, "")
                    # 如果新值为空但旧值非空，保留旧值
                    if not value and old_value:
                        continue
                    # 如果两者都非空，保留更长的那个（包含更多内容）
                    if value and old_value and len(old_value) > len(value):
                        continue
                result[key] = value

            return result

        # 定义一个reducer函数，用于处理并发更新（保留非空值）
        def keep_non_empty(left: Any, right: Any) -> Any:
            """保留非空值，优先使用right（新值）"""
            if right:
                return right
            return left if left else right

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

            # 研究结果
            bull_report: Annotated[str, keep_non_empty]
            bear_report: Annotated[str, keep_non_empty]
            investment_plan: Annotated[str, keep_non_empty]
            trader_investment_plan: Annotated[str, keep_non_empty]

            # 最终决策
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

            # 分析师独立消息历史（避免并行执行时消息混乱）
            # 注意：这些字段用于工具调用循环，每个分析师使用自己的消息历史
            _market_messages: Annotated[List, keep_non_empty]
            _social_messages: Annotated[List, keep_non_empty]
            _news_messages: Annotated[List, keep_non_empty]
            _fundamentals_messages: Annotated[List, keep_non_empty]

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
            logger.info(f"[智能体创建] 📋 从数据库加载 Agent 配置: {agent_id}")
            # 提取执行配置（temperature, max_iterations, timeout等）
            execution_config = db_agent_config.get('config', {})
            logger.info(f"[智能体创建]    - 执行配置: {execution_config}")
            # 🔥 记录 temperature 配置（如果存在）
            if 'temperature' in execution_config:
                logger.info(f"[智能体创建] 🌡️ Agent 配置的 temperature: {execution_config['temperature']}")
            else:
                logger.info(f"[智能体创建] 🌡️ Agent 配置中没有 temperature，将使用 LLM 默认值")
        else:
            logger.info(f"[智能体创建] 📋 未找到数据库配置，使用默认配置: {agent_id}")
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

        # 首先尝试使用新架构创建智能体
        if self.registry.is_registered(agent_id):
            logger.info(f"=" * 80)
            logger.info(f"[智能体创建] 🚀 开始创建 Agent: {agent_id}")
            logger.info(f"   - 节点 ID: {node_id}")
            logger.info(f"   - 节点标签: {node_label}")
            logger.info(f"   - 工作流 ID: {self._workflow_id or 'N/A'}")

            # 🆕 从 BindingManager 获取动态工具列表
            tool_ids = None
            if self._workflow_id:
                tool_ids = self.binding_manager.get_tools_for_workflow_agent(
                    self._workflow_id, agent_id
                )
                if tool_ids:
                    logger.info(f"[智能体创建] 🔧 从 BindingManager 获取工具 (工作流级别): {agent_id} -> {tool_ids}")
                else:
                    logger.info(f"[智能体创建] ⚠️ 未找到工作流级别的工具绑定，尝试 Agent 级别...")
                    # 如果工作流级别没有绑定，尝试 Agent 级别
                    tool_ids = self.binding_manager.get_tools_for_agent(agent_id)
                    if tool_ids:
                        logger.info(f"[智能体创建] 🔧 从 BindingManager 获取工具 (Agent 级别): {agent_id} -> {tool_ids}")
            else:
                # 没有工作流 ID，直接获取 Agent 级别的工具
                tool_ids = self.binding_manager.get_tools_for_agent(agent_id)
                if tool_ids:
                    logger.info(f"[智能体创建] 🔧 从 BindingManager 获取工具 (Agent 级别): {agent_id} -> {tool_ids}")

            if not tool_ids:
                logger.warning(f"[智能体创建] ⚠️ 未找到任何工具绑定: {agent_id}")

            # 🔥 关键修复：根据 agent_id 判断应该使用 quick 还是 deep LLM
            # 使用深度模型的 Agent：
            # 1. 管理者（research_manager, risk_manager）- 需要综合大量信息做决策
            # 2. 风险分析师（risky/safe/neutral_analyst_v2）- 需要处理大量分析报告
            # 其他 agent（普通分析师、研究员）使用快速模型
            llm_type = "quick"  # 默认使用快速模型
            if agent_id in [
                "research_manager_v2", "risk_manager_v2",  # v2.0 管理者
                "risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2",  # v2.0 风险分析师
                "research_manager", "risk_manager"  # 旧版管理者
            ]:
                llm_type = "deep"  # 使用深度模型
                logger.info(f"[智能体创建] 🔧 {agent_id} 使用深度分析模型 (deep_think_llm)")
            else:
                logger.info(f"[智能体创建] 🔧 {agent_id} 使用快速分析模型 (quick_think_llm)")

            # 获取 LLM 实例
            # 🔥 优先使用 Agent 配置的 temperature（如果存在）
            agent_temperature = execution_config.get("temperature")
            logger.info(f"[智能体创建] 🌡️ Temperature 优先级检查:")
            logger.info(f"   - Agent 配置中的 temperature: {agent_temperature}")
            logger.info(f"   - LLM 类型: {llm_type}")
            
            if self.llm_override:
                llm = self.llm_override
                logger.info(f"[智能体创建] 🤖 LLM 实例: {type(llm).__name__ if llm else 'None'}")
                logger.info(f"[智能体创建]    - 使用自定义 LLM (llm_override)，忽略 temperature 配置")
            elif agent_temperature is not None:
                # Agent 配置中有 temperature，创建新的 LLM 实例
                logger.info(f"[智能体创建] ✅ 检测到 Agent 配置的 temperature={agent_temperature}，创建自定义 LLM 实例")
                llm = self._legacy_provider.get_llm(llm_type, temperature=agent_temperature)
                logger.info(f"[智能体创建] 🤖 LLM 实例: {type(llm).__name__ if llm else 'None'}")
                logger.info(f"[智能体创建]    - ✅ 成功使用 Agent 配置的温度: {agent_temperature}")
                # 验证 LLM 实例的 temperature（如果 LLM 支持）
                if hasattr(llm, 'temperature'):
                    logger.info(f"[智能体创建]    - 验证: LLM 实例的 temperature={llm.temperature}")
            else:
                # 使用默认 LLM 实例
                logger.info(f"[智能体创建] ⚠️ Agent 配置中没有 temperature，使用默认 LLM 实例")
                llm = self._legacy_provider.get_llm(llm_type)
                logger.info(f"[智能体创建] 🤖 LLM 实例: {type(llm).__name__ if llm else 'None'}")
                logger.info(f"[智能体创建]    - 使用 LegacyProvider 的 {llm_type} LLM (默认温度)")
                # 验证默认 LLM 的 temperature（如果 LLM 支持）
                if hasattr(llm, 'temperature'):
                    logger.info(f"[智能体创建]    - 验证: 默认 LLM 的 temperature={llm.temperature}")

            # 🆕 获取 Agent 的记忆实例（如果记忆系统可用）
            agent_memory = None
            if self.memory_manager:
                try:
                    agent_memory = self.memory_manager.get_agent_memory(agent_id)
                    logger.info(f"[智能体创建] 🧠 为 {agent_id} 创建记忆实例")
                except Exception as mem_error:
                    logger.warning(f"[智能体创建] ⚠️ 获取记忆实例失败: {mem_error}")

            # 创建 Agent（使用 v2.0 方式，传入 LLM、工具列表和记忆）
            logger.info(f"[智能体创建] 📦 调用 factory.create()...")
            logger.info(f"   - agent_id: {agent_id}")
            # 🔥 排除 llm_provider 和 llm_model，因为这些不应该在 Agent 配置中
            config_dict_log = config.model_dump(exclude={'llm_provider', 'llm_model'}) if config else None
            logger.info(f"   - config: {config_dict_log}")
            logger.info(f"   - llm: {type(llm).__name__ if llm else 'None'}")
            logger.info(f"   - tool_ids: {tool_ids}")
            logger.info(f"   - memory: {type(agent_memory).__name__ if agent_memory else 'None'}")

            agent = self.factory.create(
                agent_id,
                config,
                llm=llm,
                tool_ids=tool_ids,
                memory=agent_memory
            )

            logger.info(f"[智能体创建] ✅ Agent 实例创建成功: {type(agent).__name__}")

            # 如果是旧版 Agent，还需要设置 toolkit 依赖
            if hasattr(agent, 'set_dependencies'):
                toolkit = self._legacy_provider.get_toolkit()
                agent.set_dependencies(llm, toolkit)
                logger.info(f"[智能体创建] ✅ 为 {agent_id} 设置了额外的 toolkit 依赖")
            else:
                logger.info(f"[智能体创建] ✅ {agent_id} 使用 v2.0 方式创建，无需额外设置依赖")

            self._agents[node.id] = agent

            # 🔍 打印 Agent 的最终状态
            logger.info(f"[智能体创建] 📊 Agent 最终状态:")
            logger.info(f"   - Agent ID: {agent_id}")
            logger.info(f"   - Agent 类型: {type(agent).__name__}")
            logger.info(f"   - 是否有 LLM: {hasattr(agent, '_llm') and agent._llm is not None}")
            logger.info(f"   - 是否有工具: {hasattr(agent, '_tools') and agent._tools is not None}")
            if hasattr(agent, '_tools') and agent._tools:
                logger.info(f"   - 工具数量: {len(agent._tools)}")
                logger.info(f"   - 工具列表: {[t.name if hasattr(t, 'name') else str(t) for t in agent._tools]}")
            logger.info(f"=" * 80)

            # 包装以添加日志
            def logged_agent(state, _agent=agent, _id=node_id, _label=node_label, _agent_id=agent_id):
                logger.info(f"[节点执行] 🚀 {_id} ({_label}) - 开始执行")
                result = _agent(state)
                # 🔍 调试：打印返回结果
                if isinstance(result, dict):
                    result_keys = list(result.keys())
                    logger.info(f"[节点执行] 📝 {_id} ({_label}) - Agent返回字段: {result_keys}")
                    # 检查是否包含分析结果
                    for key in ['timing_analysis', 'position_analysis', 'emotion_analysis', 'attribution_analysis', 'review_summary']:
                        if key in result:
                            content = result[key]
                            logger.info(f"[节点执行] ✅ {_id} 包含 {key}: {len(content) if isinstance(content, str) else 'N/A'} 字符")
                logger.info(f"[节点执行] ✅ {_id} ({_label}) - 执行完成")
                return result
            return logged_agent

        # 尝试使用遗留适配器
        legacy_node = self._try_create_legacy_agent(agent_id)
        if legacy_node is not None:
            self._agents[node.id] = legacy_node
            logger.info(f"[智能体创建] ✅ 使用遗留适配器创建: {agent_id} -> node_id: {node.id}")

            # 检查是否是分析师节点（需要独立消息历史）
            if agent_id in ANALYST_TOOL_MAPPING:
                analyst_type = ANALYST_TOOL_MAPPING[agent_id]
                return self._create_analyst_wrapper(legacy_node, node_id, node_label, agent_id, analyst_type)

            def logged_legacy(state, _node=legacy_node, _id=node_id, _label=node_label, _agent_id=agent_id):
                logger.info(f"[节点执行] 🚀 {_id} ({_label}) - 开始执行 (遗留适配器: {_agent_id})")
                result = _node(state)
                # 打印返回结果的键，方便调试
                if isinstance(result, dict):
                    logger.info(f"[节点执行] 📝 {_id} ({_label}) - 返回字段: {list(result.keys())}")
                logger.info(f"[节点执行] ✅ {_id} ({_label}) - 执行完成")
                return result
            return logged_legacy

        # 智能体未实现，返回占位函数
        def placeholder_node(state, _id=node_id, _label=node_label, _agent_id=agent_id):
            logger.info(f"[节点执行] 🔸 {_id} ({_label}) - 占位执行 (智能体 {_agent_id} 未实现)")
            return {
                f"{_agent_id}_report": f"[{_agent_id}] 智能体未实现"
            }
        return placeholder_node

    def _try_create_legacy_agent(self, agent_id: str) -> Optional[Callable]:
        """
        尝试使用遗留适配器创建智能体

        Args:
            agent_id: 智能体 ID

        Returns:
            可调用的节点函数，如果不支持则返回 None
        """
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
            # 交易员
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

    def _add_edges(
        self,
        graph: StateGraph,
        definition: WorkflowDefinition,
        debate_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        analyst_nodes_info: Optional[Dict[str, str]] = None
    ) -> None:
        """
        添加边到图

        辩论流程设计：
        - 辩论节点 → 第一个参与者（普通边）
        - 参与者之间使用条件边（检查计数决定继续或结束）
        - 最后一个参与者 → 下一阶段（通过条件边控制）

        分析师工具循环设计：
        - 分析师节点 → 条件边 → 工具节点/消息清理节点
        - 工具节点 → 分析师节点（循环）
        - 消息清理节点 → 下一个节点
        """
        start_node = definition.get_start_node()
        added_edges: Set[tuple] = set()

        if debate_configs is None:
            debate_configs = self._identify_debate_configs(definition)

        if analyst_nodes_info is None:
            analyst_nodes_info = {}

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

            # 辩论节点 → 第一个参与者
            graph.add_edge(debate_id, participants[0])
            added_edges.add((debate_id, participants[0]))

            # 为每个参与者添加条件边
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
            else:
                graph.add_edge(edge.source, edge.target)
            added_edges.add(edge_key)

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
