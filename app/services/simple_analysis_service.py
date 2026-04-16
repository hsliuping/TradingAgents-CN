"""
简化的股票分析服务
直接调用现有的 TradingAgents 分析功能
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 初始化TradingAgents日志系统
from tradingagents.utils.logging_init import init_logging
init_logging()

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from app.models.analysis import (
    AnalysisTask, AnalysisStatus, SingleAnalysisRequest, AnalysisParameters
)
from app.models.user import PyObjectId
from app.models.notification import NotificationCreate
from bson import ObjectId
from app.core.database import get_mongo_db
from app.services.config_service import ConfigService
from app.services.memory_state_manager import get_memory_state_manager, TaskStatus
from app.services.redis_progress_tracker import RedisProgressTracker, get_progress_by_id
from app.services.progress_log_handler import register_analysis_tracker, unregister_analysis_tracker

# 股票基础信息获取（用于补充显示名称）
try:
    from tradingagents.dataflows.data_source_manager import get_data_source_manager
    _data_source_manager = get_data_source_manager()
    def _get_stock_info_safe(stock_code: str):
        """获取股票基础信息的安全封装"""
        return _data_source_manager.get_stock_basic_info(stock_code)
except Exception:
    _get_stock_info_safe = None

# 设置日志
logger = logging.getLogger("app.services.simple_analysis_service")

# 配置服务实例
config_service = ConfigService()


async def get_provider_by_model_name(model_name: str) -> str:
    """
    根据模型名称从数据库配置中查找对应的供应商（异步版本）

    Args:
        model_name: 模型名称，如 'qwen-turbo', 'gpt-4' 等

    Returns:
        str: 供应商名称，如 'dashscope', 'openai' 等
    """
    try:
        # 从配置服务获取系统配置
        system_config = await config_service.get_system_config()
        if not system_config or not system_config.llm_configs:
            logger.warning(f"⚠️ 系统配置为空，使用默认供应商映射")
            return _get_default_provider_by_model(model_name)

        # 在LLM配置中查找匹配的模型
        for llm_config in system_config.llm_configs:
            if llm_config.model_name == model_name:
                provider = llm_config.provider.value if hasattr(llm_config.provider, 'value') else str(llm_config.provider)
                logger.info(f"✅ 从数据库找到模型 {model_name} 的供应商: {provider}")
                return provider

        # 如果数据库中没有找到，使用默认映射
        logger.warning(f"⚠️ 数据库中未找到模型 {model_name}，使用默认映射")
        return _get_default_provider_by_model(model_name)

    except Exception as e:
        logger.error(f"❌ 查找模型供应商失败: {e}")
        return _get_default_provider_by_model(model_name)


def get_provider_by_model_name_sync(model_name: str) -> str:
    """
    根据模型名称从数据库配置中查找对应的供应商（同步版本）

    Args:
        model_name: 模型名称，如 'qwen-turbo', 'gpt-4' 等

    Returns:
        str: 供应商名称，如 'dashscope', 'openai' 等
    """
    provider_info = get_provider_and_url_by_model_sync(model_name)
    return provider_info["provider"]


def get_provider_and_url_by_model_sync(model_name: str) -> dict:
    """
    根据模型名称从数据库配置中查找对应的供应商和 API URL（同步版本）

    Args:
        model_name: 模型名称，如 'qwen-turbo', 'gpt-4' 等

    Returns:
        dict: {"provider": "google", "backend_url": "https://...", "api_key": "xxx"}
    """
    try:
        # 使用同步 MongoDB 客户端直接查询
        from pymongo import MongoClient
        from app.core.config import settings
        import os

        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB]

        # 查询最新的活跃配置
        configs_collection = db.system_configs
        doc = configs_collection.find_one({"is_active": True}, sort=[("version", -1)])

        if doc and "llm_configs" in doc:
            llm_configs = doc["llm_configs"]

            for config_dict in llm_configs:
                if config_dict.get("model_name") == model_name:
                    provider = config_dict.get("provider")
                    api_base = config_dict.get("api_base")
                    model_api_key = config_dict.get("api_key")  # 🔥 获取模型配置的 API Key

                    # 从 llm_providers 集合中查找厂家配置
                    providers_collection = db.llm_providers
                    provider_doc = providers_collection.find_one({"name": provider})

                    # 🔥 确定 API Key（优先级：模型配置 > 厂家配置 > 环境变量）
                    api_key = None
                    if model_api_key and model_api_key.strip() and model_api_key != "your-api-key":
                        api_key = model_api_key
                        logger.info(f"✅ [同步查询] 使用模型配置的 API Key")
                    elif provider_doc and provider_doc.get("api_key"):
                        provider_api_key = provider_doc["api_key"]
                        if provider_api_key and provider_api_key.strip() and provider_api_key != "your-api-key":
                            api_key = provider_api_key
                            logger.info(f"✅ [同步查询] 使用厂家配置的 API Key")

                    # 如果数据库中没有有效的 API Key，尝试从环境变量获取
                    if not api_key:
                        api_key = _get_env_api_key_for_provider(provider)
                        if api_key:
                            logger.info(f"✅ [同步查询] 使用环境变量的 API Key")
                        else:
                            logger.warning(f"⚠️ [同步查询] 未找到 {provider} 的 API Key")

                    # 确定 backend_url
                    backend_url = None
                    if api_base:
                        backend_url = api_base
                        logger.info(f"✅ [同步查询] 模型 {model_name} 使用自定义 API: {api_base}")
                    elif provider_doc and provider_doc.get("default_base_url"):
                        backend_url = provider_doc["default_base_url"]
                        logger.info(f"✅ [同步查询] 模型 {model_name} 使用厂家默认 API: {backend_url}")
                    else:
                        backend_url = _get_default_backend_url(provider)
                        logger.warning(f"⚠️ [同步查询] 厂家 {provider} 没有配置 default_base_url，使用硬编码默认值")

                    from tradingagents.llm_clients.provider_keys import normalize_provider_key, default_backend_url

                    provider_key = normalize_provider_key(provider)
                    if provider_key == "qwen" and backend_url == "https://dashscope.aliyuncs.com/api/v1":
                        backend_url = default_backend_url(provider_key)

                    client.close()
                    return {
                        "provider": provider_key,
                        "backend_url": backend_url,
                        "api_key": api_key
                    }

        client.close()

        # 如果数据库中没有找到模型配置，使用默认映射
        logger.warning(f"⚠️ [同步查询] 数据库中未找到模型 {model_name}，使用默认映射")
        provider = _get_default_provider_by_model(model_name)

        # 尝试从厂家配置中获取 default_base_url 和 API Key
        try:
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            providers_collection = db.llm_providers
            provider_doc = providers_collection.find_one({"name": provider})

            backend_url = _get_default_backend_url(provider)
            api_key = None

            if provider_doc:
                if provider_doc.get("default_base_url"):
                    backend_url = provider_doc["default_base_url"]
                    logger.info(f"✅ [同步查询] 使用厂家 {provider} 的 default_base_url: {backend_url}")

                if provider_doc.get("api_key"):
                    provider_api_key = provider_doc["api_key"]
                    if provider_api_key and provider_api_key.strip() and provider_api_key != "your-api-key":
                        api_key = provider_api_key
                        logger.info(f"✅ [同步查询] 使用厂家 {provider} 的 API Key")

            # 如果厂家配置中没有 API Key，尝试从环境变量获取
            if not api_key:
                api_key = _get_env_api_key_for_provider(provider)
                if api_key:
                    logger.info(f"✅ [同步查询] 使用环境变量的 API Key")

            from tradingagents.llm_clients.provider_keys import normalize_provider_key, default_backend_url

            provider_key = normalize_provider_key(provider)
            if provider_key == "qwen" and backend_url == "https://dashscope.aliyuncs.com/api/v1":
                backend_url = default_backend_url(provider_key)

            client.close()
            return {
                "provider": provider_key,
                "backend_url": backend_url,
                "api_key": api_key
            }
        except Exception as e:
            logger.warning(f"⚠️ [同步查询] 无法查询厂家配置: {e}")

        # 最后回退到硬编码的默认 URL 和环境变量 API Key
        from tradingagents.llm_clients.provider_keys import normalize_provider_key

        provider_key = normalize_provider_key(provider)
        return {
            "provider": provider_key,
            "backend_url": _get_default_backend_url(provider_key),
            "api_key": _get_env_api_key_for_provider(provider_key)
        }

    except Exception as e:
        logger.error(f"❌ [同步查询] 查找模型供应商失败: {e}")
        provider = _get_default_provider_by_model(model_name)

        # 尝试从厂家配置中获取 default_base_url 和 API Key
        try:
            from pymongo import MongoClient
            from app.core.config import settings

            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            providers_collection = db.llm_providers
            provider_doc = providers_collection.find_one({"name": provider})

            backend_url = _get_default_backend_url(provider)
            api_key = None

            if provider_doc:
                if provider_doc.get("default_base_url"):
                    backend_url = provider_doc["default_base_url"]
                    logger.info(f"✅ [同步查询] 使用厂家 {provider} 的 default_base_url: {backend_url}")

                if provider_doc.get("api_key"):
                    provider_api_key = provider_doc["api_key"]
                    if provider_api_key and provider_api_key.strip() and provider_api_key != "your-api-key":
                        api_key = provider_api_key
                        logger.info(f"✅ [同步查询] 使用厂家 {provider} 的 API Key")

            # 如果厂家配置中没有 API Key，尝试从环境变量获取
            if not api_key:
                api_key = _get_env_api_key_for_provider(provider)

            client.close()
            return {
                "provider": provider,
                "backend_url": backend_url,
                "api_key": api_key
            }
        except Exception as e2:
            logger.warning(f"⚠️ [同步查询] 无法查询厂家配置: {e2}")

        # 最后回退到硬编码的默认 URL 和环境变量 API Key
        return {
            "provider": provider,
            "backend_url": _get_default_backend_url(provider),
            "api_key": _get_env_api_key_for_provider(provider)
        }


def _get_env_api_key_for_provider(provider: str) -> str:
    """
    从环境变量获取指定供应商的 API Key

    Args:
        provider: 供应商名称，如 'google', 'dashscope' 等

    Returns:
        str: API Key，如果未找到则返回 None
    """
    import os

    from tradingagents.llm_clients.provider_keys import env_key_for_provider, normalize_provider_key

    provider_key = normalize_provider_key(provider)
    env_key_name = env_key_for_provider(provider_key)
    if not env_key_name and provider_key == "302ai":
        env_key_name = "AI302_API_KEY"
    if not env_key_name and provider_key == "aihubmix":
        env_key_name = "AIHUBMIX_API_KEY"
    if env_key_name:
        api_key = os.getenv(env_key_name)
        if api_key and api_key.strip() and api_key != "your-api-key":
            return api_key

    return None


def _get_default_backend_url(provider: str) -> str:
    """
    根据供应商名称返回默认的 backend_url

    Args:
        provider: 供应商名称，如 'google', 'dashscope' 等

    Returns:
        str: 默认的 backend_url
    """
    from tradingagents.llm_clients.provider_keys import default_backend_url, normalize_provider_key

    provider_key = normalize_provider_key(provider)
    if provider_key == "302ai":
        url = "https://api.302.ai/v1"
    elif provider_key == "aihubmix":
        url = "https://aihubmix.com/v1"
    else:
        url = default_backend_url(provider_key)

    logger.info(f"🔧 [默认URL] {provider} -> {url}")
    return url


def _get_default_provider_by_model(model_name: str) -> str:
    """
    根据模型名称返回默认的供应商映射
    这是一个后备方案，当数据库查询失败时使用
    """
    # 模型名称到供应商的默认映射
    model_provider_map = {
        # 阿里百炼 (DashScope)
        'qwen-turbo': 'qwen',
        'qwen-plus': 'qwen',
        'qwen-max': 'qwen',
        'qwen-plus-latest': 'qwen',
        'qwen-max-longcontext': 'qwen',

        # OpenAI
        'gpt-3.5-turbo': 'openai',
        'gpt-4': 'openai',
        'gpt-4-turbo': 'openai',
        'gpt-4o': 'openai',
        'gpt-4o-mini': 'openai',

        # Google
        'gemini-pro': 'google',
        'gemini-2.0-flash': 'google',
        'gemini-2.0-flash-thinking-exp': 'google',

        # DeepSeek
        'deepseek-chat': 'deepseek',
        'deepseek-coder': 'deepseek',

        # 智谱AI
        'glm-4': 'glm',
        'glm-3-turbo': 'glm',
        'chatglm3-6b': 'glm'
    }

    provider = model_provider_map.get(model_name, 'qwen')  # 默认使用阿里百炼
    logger.info(f"🔧 使用默认映射: {model_name} -> {provider}")
    return provider


def create_analysis_config(
    research_depth,  # 支持数字(1-5)或字符串("快速", "标准", "深度")
    selected_analysts: list,
    quick_model: str,
    deep_model: str,
    llm_provider: str,
    market_type: str = "A股",
    quick_model_config: dict = None,  # 新增：快速模型的完整配置
    deep_model_config: dict = None    # 新增：深度模型的完整配置
) -> dict:
    """
    创建分析配置 - 支持数字等级和中文等级

    Args:
        research_depth: 研究深度，支持数字(1-5)或中文("快速", "基础", "标准", "深度", "全面")
        selected_analysts: 选中的分析师列表
        quick_model: 快速分析模型
        deep_model: 深度分析模型
        llm_provider: LLM供应商
        market_type: 市场类型
        quick_model_config: 快速模型的完整配置（包含 max_tokens、temperature、timeout 等）
        deep_model_config: 深度模型的完整配置（包含 max_tokens、temperature、timeout 等）

    Returns:
        dict: 完整的分析配置
    """
    # 🔍 [调试] 记录接收到的原始参数
    logger.info(f"🔍 [配置创建] 接收到的research_depth参数: {research_depth} (类型: {type(research_depth).__name__})")

    # 数字等级到中文等级的映射
    numeric_to_chinese = {
        1: "快速",
        2: "基础",
        3: "标准",
        4: "深度",
        5: "全面"
    }

    # 标准化研究深度：支持数字输入
    if isinstance(research_depth, (int, float)):
        research_depth = int(research_depth)
        if research_depth in numeric_to_chinese:
            chinese_depth = numeric_to_chinese[research_depth]
            logger.info(f"🔢 [等级转换] 数字等级 {research_depth} → 中文等级 '{chinese_depth}'")
            research_depth = chinese_depth
        else:
            logger.warning(f"⚠️ 无效的数字等级: {research_depth}，使用默认标准分析")
            research_depth = "标准"
    elif isinstance(research_depth, str):
        # 如果是字符串形式的数字，转换为整数
        if research_depth.isdigit():
            numeric_level = int(research_depth)
            if numeric_level in numeric_to_chinese:
                chinese_depth = numeric_to_chinese[numeric_level]
                logger.info(f"🔢 [等级转换] 字符串数字 '{research_depth}' → 中文等级 '{chinese_depth}'")
                research_depth = chinese_depth
            else:
                logger.warning(f"⚠️ 无效的字符串数字等级: {research_depth}，使用默认标准分析")
                research_depth = "标准"
        # 如果已经是中文等级，直接使用
        elif research_depth in ["快速", "基础", "标准", "深度", "全面"]:
            logger.info(f"📝 [等级确认] 使用中文等级: '{research_depth}'")
        else:
            logger.warning(f"⚠️ 未知的研究深度: {research_depth}，使用默认标准分析")
            research_depth = "标准"
    else:
        logger.warning(f"⚠️ 无效的研究深度类型: {type(research_depth)}，使用默认标准分析")
        research_depth = "标准"

    # 从DEFAULT_CONFIG开始，完全复制web目录的逻辑
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = llm_provider
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = quick_model

    # 根据研究深度调整配置 - 支持5个级别（与Web界面保持一致）
    if research_depth == "快速":
        # 1级 - 快速分析
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = False  # 禁用记忆以加速
        config["online_tools"] = True  # 统一使用在线工具，避免离线工具的各种问题
        logger.info(f"🔧 [1级-快速分析] {market_type}使用统一工具，确保数据源正确和稳定性")
        logger.info(f"🔧 [1级-快速分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}")

    elif research_depth == "基础":
        # 2级 - 基础分析
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = True
        config["online_tools"] = True
        logger.info(f"🔧 [2级-基础分析] {market_type}使用在线工具，获取最新数据")
        logger.info(f"🔧 [2级-基础分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}")

    elif research_depth == "标准":
        # 3级 - 标准分析（推荐）
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True
        logger.info(f"🔧 [3级-标准分析] {market_type}平衡速度和质量（推荐）")
        logger.info(f"🔧 [3级-标准分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}")

    elif research_depth == "深度":
        # 4级 - 深度分析
        config["max_debate_rounds"] = 2
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True
        logger.info(f"🔧 [4级-深度分析] {market_type}多轮辩论，深度研究")
        logger.info(f"🔧 [4级-深度分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}")

    elif research_depth == "全面":
        # 5级 - 全面分析
        config["max_debate_rounds"] = 3
        config["max_risk_discuss_rounds"] = 3
        config["memory_enabled"] = True
        config["online_tools"] = True
        logger.info(f"🔧 [5级-全面分析] {market_type}最全面的分析，最高质量")
        logger.info(f"🔧 [5级-全面分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}")

    else:
        # 默认使用标准分析
        logger.warning(f"⚠️ 未知的研究深度: {research_depth}，使用标准分析")
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True

    # 🔧 获取 backend_url 和 API Key（优先级：模型配置 > 厂家配置 > 环境变量）
    try:
        # 1️⃣ 优先从数据库获取（包含模型配置的 api_base、API Key 和厂家的 default_base_url、API Key）
        quick_provider_info = get_provider_and_url_by_model_sync(quick_model)
        deep_provider_info = get_provider_and_url_by_model_sync(deep_model)

        config["backend_url"] = quick_provider_info["backend_url"]
        config["quick_api_key"] = quick_provider_info.get("api_key")  # 🔥 保存快速模型的 API Key
        config["deep_api_key"] = deep_provider_info.get("api_key")    # 🔥 保存深度模型的 API Key

        logger.info(f"✅ 使用数据库配置的 backend_url: {quick_provider_info['backend_url']}")
        logger.info(f"   来源: 模型 {quick_model} 的配置或厂家 {quick_provider_info['provider']} 的默认地址")
        logger.info(f"🔑 快速模型 API Key: {'已配置' if config['quick_api_key'] else '未配置（将使用环境变量）'}")
        logger.info(f"🔑 深度模型 API Key: {'已配置' if config['deep_api_key'] else '未配置（将使用环境变量）'}")
    except Exception as e:
        logger.warning(f"⚠️  无法从数据库获取 backend_url 和 API Key: {e}")
        config["backend_url"] = _get_default_backend_url(llm_provider)

        logger.info(f"⚠️  使用回退的 backend_url: {config['backend_url']}")

    # 添加分析师配置
    config["selected_analysts"] = selected_analysts
    config["debug"] = False

    # 🔧 添加research_depth到配置中，使工具函数能够访问分析级别信息
    config["research_depth"] = research_depth

    # 🔧 添加模型配置参数（max_tokens、temperature、timeout、retry_times）
    if quick_model_config:
        config["quick_model_config"] = quick_model_config
        logger.info(f"🔧 [快速模型配置] max_tokens={quick_model_config.get('max_tokens')}, "
                   f"temperature={quick_model_config.get('temperature')}, "
                   f"timeout={quick_model_config.get('timeout')}, "
                   f"retry_times={quick_model_config.get('retry_times')}")

    if deep_model_config:
        config["deep_model_config"] = deep_model_config
        logger.info(f"🔧 [深度模型配置] max_tokens={deep_model_config.get('max_tokens')}, "
                   f"temperature={deep_model_config.get('temperature')}, "
                   f"timeout={deep_model_config.get('timeout')}, "
                   f"retry_times={deep_model_config.get('retry_times')}")

    logger.info(f"📋 ========== 创建分析配置完成 ==========")
    logger.info(f"   🎯 研究深度: {research_depth}")
    logger.info(f"   🔥 辩论轮次: {config['max_debate_rounds']}")
    logger.info(f"   ⚖️ 风险讨论轮次: {config['max_risk_discuss_rounds']}")
    logger.info(f"   💾 记忆功能: {config['memory_enabled']}")
    logger.info(f"   🌐 在线工具: {config['online_tools']}")
    logger.info(f"   🤖 LLM供应商: {llm_provider}")
    logger.info(f"   ⚡ 快速模型: {config['quick_think_llm']}")
    logger.info(f"   🧠 深度模型: {config['deep_think_llm']}")
    logger.info(f"📋 ========================================")

    return config


class SimpleAnalysisService:
    """简化的股票分析服务类"""

    def __init__(self):
        self._trading_graph_cache = {}
        self.memory_manager = get_memory_state_manager()

        # 进度跟踪器缓存
        self._progress_trackers: Dict[str, RedisProgressTracker] = {}

        # 🔧 创建共享的线程池，支持并发执行多个分析任务
        # 默认最多同时执行3个分析任务（可根据服务器资源调整）
        import concurrent.futures
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)

        logger.info(f"🔧 [服务初始化] SimpleAnalysisService 实例ID: {id(self)}")
        logger.info(f"🔧 [服务初始化] 内存管理器实例ID: {id(self.memory_manager)}")
        logger.info(f"🔧 [服务初始化] 线程池最大并发数: 3")

        # 设置 WebSocket 管理器
        # 简单的股票名称缓存，减少重复查询
        self._stock_name_cache: Dict[str, str] = {}

        # 设置 WebSocket 管理器
        try:
            from app.services.websocket_manager import get_websocket_manager
            self.memory_manager.set_websocket_manager(get_websocket_manager())
        except ImportError:
            logger.warning("⚠️ WebSocket 管理器不可用")

    async def _update_progress_async(self, task_id: str, progress: int, message: str):
        """异步更新进度（内存和MongoDB）"""
        try:
            # 更新内存
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=progress,
                message=message,
                current_step=message
            )

            # 更新 MongoDB
            from app.core.database import get_mongo_db
            from datetime import datetime
            db = get_mongo_db()
            await db.analysis_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "progress": progress,
                        "current_step": message,
                        "message": message,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.debug(f"✅ [异步更新] 已更新内存和MongoDB: {progress}%")
        except Exception as e:
            logger.warning(f"⚠️ [异步更新] 失败: {e}")

    def _resolve_stock_name(self, code: Optional[str]) -> str:
        """解析股票名称（带缓存）"""
        if not code:
            return ""
        # 命中缓存
        if code in self._stock_name_cache:
            return self._stock_name_cache[code]
        name = None
        try:
            if _get_stock_info_safe:
                info = _get_stock_info_safe(code)
                if isinstance(info, dict):
                    name = info.get("name")
        except Exception as e:
            logger.warning(f"⚠️ 获取股票名称失败: {code} - {e}")
        if not name:
            name = f"股票{code}"
        # 写缓存
        self._stock_name_cache[code] = name
        return name

    def _enrich_stock_names(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """为任务列表补齐股票名称(就地更新)"""
        try:
            for t in tasks:
                code = t.get("stock_code") or t.get("stock_symbol")
                name = t.get("stock_name")
                if not name and code:
                    t["stock_name"] = self._resolve_stock_name(code)
        except Exception as e:
            logger.warning(f"⚠️ 补齐股票名称时出现异常: {e}")
        return tasks

    def _convert_user_id(self, user_id: str) -> PyObjectId:
        """将字符串用户ID转换为PyObjectId"""
        try:
            logger.info(f"🔄 开始转换用户ID: {user_id} (类型: {type(user_id)})")

            # 如果是admin用户，使用固定的ObjectId
            if user_id == "admin":
                admin_object_id = ObjectId("507f1f77bcf86cd799439011")
                logger.info(f"🔄 转换admin用户ID: {user_id} -> {admin_object_id}")
                return PyObjectId(admin_object_id)
            else:
                # 尝试将字符串转换为ObjectId
                object_id = ObjectId(user_id)
                logger.info(f"🔄 转换用户ID: {user_id} -> {object_id}")
                return PyObjectId(object_id)
        except Exception as e:
            logger.error(f"❌ 用户ID转换失败: {user_id} -> {e}")
            # 如果转换失败，生成一个新的ObjectId
            new_object_id = ObjectId()
            logger.warning(f"⚠️ 生成新的用户ID: {new_object_id}")
            return PyObjectId(new_object_id)

    def _get_trading_graph(self, config: Dict[str, Any]) -> TradingAgentsGraph:
        """获取或创建TradingAgents实例

        ⚠️ 注意：为了避免并发执行时的数据混淆，每次都创建新实例
        虽然这会增加一些初始化开销，但可以确保线程安全

        TradingAgentsGraph 实例包含可变状态（self.ticker, self.curr_state等），
        如果多个线程共享同一个实例，会导致数据混淆。
        """
        # 🔧 [并发安全] 每次都创建新实例，避免多线程共享状态
        # 不再使用缓存，因为 TradingAgentsGraph 有可变的实例变量
        logger.info(f"🔧 创建新的TradingAgents实例（并发安全模式）...")

        trading_graph = TradingAgentsGraph(
            selected_analysts=config.get("selected_analysts", ["market", "fundamentals"]),
            debug=config.get("debug", False),
            config=config
        )

        logger.info(f"✅ TradingAgents实例创建成功（实例ID: {id(trading_graph)}）")

        return trading_graph

    async def create_analysis_task(
        self,
        user_id: str,
        request: SingleAnalysisRequest
    ) -> Dict[str, Any]:
        """创建分析任务（立即返回，不执行分析）"""
        try:
            # 生成任务ID
            task_id = str(uuid.uuid4())

            # 🔧 使用 get_symbol() 方法获取股票代码（兼容 symbol 和 stock_code 字段）
            stock_code = request.get_symbol()
            if not stock_code:
                raise ValueError("股票代码不能为空")

            logger.info(f"📝 创建分析任务: {task_id} - {stock_code}")
            logger.info(f"🔍 内存管理器实例ID: {id(self.memory_manager)}")

            # 在内存中创建任务状态
            task_state = await self.memory_manager.create_task(
                task_id=task_id,
                user_id=user_id,
                stock_code=stock_code,
                parameters=request.parameters.model_dump() if request.parameters else {},
                stock_name=(self._resolve_stock_name(stock_code) if hasattr(self, '_resolve_stock_name') else None),
            )

            logger.info(f"✅ 任务状态已创建: {task_state.task_id}")

            # 立即验证任务是否可以查询到
            verify_task = await self.memory_manager.get_task(task_id)
            if verify_task:
                logger.info(f"✅ 任务创建验证成功: {verify_task.task_id}")
            else:
                logger.error(f"❌ 任务创建验证失败: 无法查询到刚创建的任务 {task_id}")

            # 补齐股票名称并写入数据库任务文档的初始记录
            code = stock_code
            name = self._resolve_stock_name(code) if hasattr(self, '_resolve_stock_name') else f"股票{code}"

            try:
                db = get_mongo_db()
                result = await db.analysis_tasks.update_one(
                    {"task_id": task_id},
                    {"$setOnInsert": {
                        "task_id": task_id,
                        "user_id": user_id,
                        "stock_code": code,
                        "stock_symbol": code,
                        "stock_name": name,
                        "status": "pending",
                        "progress": 0,
                        "created_at": datetime.utcnow(),
                    }},
                    upsert=True
                )

                if result.upserted_id or result.matched_count > 0:
                    logger.info(f"✅ 任务已保存到MongoDB: {task_id}")
                else:
                    logger.warning(f"⚠️ MongoDB保存结果异常: matched={result.matched_count}, upserted={result.upserted_id}")

            except Exception as e:
                logger.error(f"❌ 创建任务时写入MongoDB失败: {e}")
                # 这里不应该忽略错误，因为没有MongoDB记录会导致状态查询失败
                # 但为了不影响任务执行，我们记录错误但继续执行
                import traceback
                logger.error(f"❌ MongoDB保存详细错误: {traceback.format_exc()}")

            return {
                "task_id": task_id,
                "status": "pending",
                "message": "任务已创建，等待执行"
            }

        except Exception as e:
            logger.error(f"❌ 创建分析任务失败: {e}")
            raise

    async def execute_analysis_background(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest
    ):
        """在后台执行分析任务"""
        # 🔧 使用 get_symbol() 方法获取股票代码（兼容 symbol 和 stock_code 字段）
        stock_code = request.get_symbol()

        # 添加最外层的异常捕获，确保所有异常都被记录
        try:
            logger.info(f"🎯🎯🎯 [ENTRY] execute_analysis_background 方法被调用: {task_id}")
            logger.info(f"🎯🎯🎯 [ENTRY] user_id={user_id}, stock_code={stock_code}")
        except Exception as entry_error:
            print(f"❌❌❌ [CRITICAL] 日志记录失败: {entry_error}")
            import traceback
            traceback.print_exc()

        progress_tracker = None
        try:
            logger.info(f"🚀 开始后台执行分析任务: {task_id}")

            # 🔍 验证股票代码是否存在
            logger.info(f"🔍 开始验证股票代码: {stock_code}")
            from tradingagents.utils.stock_validator import prepare_stock_data_async
            from datetime import datetime

            # 获取市场类型
            market_type = request.parameters.market_type if request.parameters else "A股"

            # 获取分析日期并转换为字符串格式
            analysis_date = request.parameters.analysis_date if request.parameters else None
            if analysis_date:
                # 如果是 datetime 对象，转换为字符串
                if isinstance(analysis_date, datetime):
                    analysis_date = analysis_date.strftime('%Y-%m-%d')
                # 如果是字符串，确保格式正确
                elif isinstance(analysis_date, str):
                    # 尝试解析并重新格式化，确保格式统一
                    try:
                        parsed_date = datetime.strptime(analysis_date, '%Y-%m-%d')
                        analysis_date = parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        # 如果格式不对，使用今天
                        analysis_date = datetime.now().strftime('%Y-%m-%d')
                        logger.warning(f"⚠️ 分析日期格式不正确，使用今天: {analysis_date}")

            # 🔥 使用异步版本，直接 await，避免事件循环冲突
            validation_result = await prepare_stock_data_async(
                stock_code=stock_code,
                market_type=market_type,
                period_days=30,
                analysis_date=analysis_date
            )

            if not validation_result.is_valid:
                error_msg = f"❌ 股票代码验证失败: {validation_result.error_message}"
                logger.error(error_msg)
                logger.error(f"💡 建议: {validation_result.suggestion}")

                # 构建用户友好的错误消息
                user_friendly_error = (
                    f"❌ 股票代码无效\n\n"
                    f"{validation_result.error_message}\n\n"
                    f"💡 {validation_result.suggestion}"
                )

                # 更新任务状态为失败
                await self.memory_manager.update_task_status(
                    task_id=task_id,
                    status=AnalysisStatus.FAILED,
                    progress=0,
                    error_message=user_friendly_error
                )

                # 更新MongoDB状态
                await self._update_task_status(
                    task_id,
                    AnalysisStatus.FAILED,
                    0,
                    error_message=user_friendly_error
                )

                return

            logger.info(f"✅ 股票代码验证通过: {stock_code} - {validation_result.stock_name}")
            logger.info(f"📊 市场类型: {validation_result.market_type}")
            logger.info(f"📈 历史数据: {'有' if validation_result.has_historical_data else '无'}")
            logger.info(f"📋 基本信息: {'有' if validation_result.has_basic_info else '无'}")

            # 在线程池中创建Redis进度跟踪器（避免阻塞事件循环）
            def create_progress_tracker():
                """在线程中创建进度跟踪器"""
                logger.info(f"📊 [线程] 创建进度跟踪器: {task_id}")
                tracker = RedisProgressTracker(
                    task_id=task_id,
                    analysts=request.parameters.selected_analysts or ["market", "fundamentals"],
                    research_depth=request.parameters.research_depth or "标准",
                    llm_provider="dashscope"
                )
                logger.info(f"✅ [线程] 进度跟踪器创建完成: {task_id}")
                return tracker

            progress_tracker = await asyncio.to_thread(create_progress_tracker)

            # 缓存进度跟踪器
            self._progress_trackers[task_id] = progress_tracker

            # 注册到日志监控
            register_analysis_tracker(task_id, progress_tracker)

            # 初始化进度（在线程中执行）
            await asyncio.to_thread(
                progress_tracker.update_progress,
                {
                    "progress_percentage": 10,
                    "last_message": "🚀 开始股票分析"
                }
            )

            # 更新状态为运行中
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=10,
                message="分析开始...",
                current_step="initialization"
            )

            # 同步更新MongoDB状态
            await self._update_task_status(task_id, AnalysisStatus.PROCESSING, 10)

            # 数据准备阶段（在线程中执行）
            await asyncio.to_thread(
                progress_tracker.update_progress,
                {
                    "progress_percentage": 20,
                    "last_message": "🔧 检查环境配置"
                }
            )
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=20,
                message="准备分析数据...",
                current_step="data_preparation"
            )

            # 同步更新MongoDB状态
            await self._update_task_status(task_id, AnalysisStatus.PROCESSING, 20)

            # 执行实际的分析
            result = await self._execute_analysis_sync(task_id, user_id, request, progress_tracker)

            # 标记进度跟踪器完成（在线程中执行）
            await asyncio.to_thread(progress_tracker.mark_completed)

            # 保存分析结果到文件和数据库
            try:
                logger.info(f"💾 开始保存分析结果: {task_id}")
                await self._save_analysis_results_complete(task_id, result)
                logger.info(f"✅ 分析结果保存完成: {task_id}")
            except Exception as save_error:
                logger.error(f"❌ 保存分析结果失败: {task_id} - {save_error}")
                # 保存失败不影响分析完成状态

            # 🔍 调试：检查即将保存到内存的result
            logger.info(f"🔍 [DEBUG] 即将保存到内存的result键: {list(result.keys())}")
            logger.info(f"🔍 [DEBUG] 即将保存到内存的decision: {bool(result.get('decision'))}")
            if result.get('decision'):
                logger.info(f"🔍 [DEBUG] 即将保存的decision内容: {result['decision']}")

            # 更新状态为完成
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                message="分析完成",
                current_step="completed",
                result_data=result
            )

            # 同步更新MongoDB状态为完成
            await self._update_task_status(task_id, AnalysisStatus.COMPLETED, 100)

            # 创建通知：分析完成（方案B：REST+SSE）
            try:
                from app.services.notifications_service import get_notifications_service
                svc = get_notifications_service()
                summary = str(result.get("summary", ""))[:120]
                await svc.create_and_publish(
                    payload=NotificationCreate(
                        user_id=str(user_id),
                        type='analysis',
                        title=f"{request.stock_code} 分析完成",
                        content=summary,
                        link=f"/stocks/{request.stock_code}",
                        source='analysis'
                    )
                )
            except Exception as notif_err:
                logger.warning(f"⚠️ 创建通知失败(忽略): {notif_err}")

            logger.info(f"✅ 后台分析任务完成: {task_id}")

        except Exception as e:
            logger.error(f"❌ 后台分析任务失败: {task_id} - {e}")

            # 格式化错误信息为用户友好的提示
            from ..utils.error_formatter import ErrorFormatter

            # 收集上下文信息
            error_context = {}
            if hasattr(request, 'parameters') and request.parameters:
                if hasattr(request.parameters, 'quick_model'):
                    error_context['model'] = request.parameters.quick_model
                if hasattr(request.parameters, 'deep_model'):
                    error_context['model'] = request.parameters.deep_model

            # 格式化错误
            formatted_error = ErrorFormatter.format_error(str(e), error_context)

            # 构建用户友好的错误消息
            user_friendly_error = (
                f"{formatted_error['title']}\n\n"
                f"{formatted_error['message']}\n\n"
                f"💡 {formatted_error['suggestion']}"
            )

            # 标记进度跟踪器失败
            if progress_tracker:
                progress_tracker.mark_failed(user_friendly_error)

            # 更新状态为失败
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                progress=0,
                message="分析失败",
                current_step="failed",
                error_message=user_friendly_error
            )

            # 同步更新MongoDB状态为失败
            await self._update_task_status(task_id, AnalysisStatus.FAILED, 0, user_friendly_error)
        finally:
            # 清理进度跟踪器缓存
            if task_id in self._progress_trackers:
                del self._progress_trackers[task_id]

            # 从日志监控中注销
            unregister_analysis_tracker(task_id)

    async def _execute_analysis_sync(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest,
        progress_tracker: Optional[RedisProgressTracker] = None
    ) -> Dict[str, Any]:
        """同步执行分析（在共享线程池中运行）"""
        # 🔧 使用共享线程池，支持多个任务并发执行
        # 不再每次创建新的线程池，避免串行执行
        loop = asyncio.get_event_loop()
        logger.info(f"🚀 [线程池] 提交分析任务到共享线程池: {task_id} - {request.stock_code}")
        result = await loop.run_in_executor(
            self._thread_pool,  # 使用共享线程池
            self._run_analysis_sync,
            task_id,
            user_id,
            request,
            progress_tracker
        )
        logger.info(f"✅ [线程池] 分析任务执行完成: {task_id}")
        return result

    def _run_analysis_sync(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest,
        progress_tracker: Optional[RedisProgressTracker] = None
    ) -> Dict[str, Any]:
        """同步执行分析的具体实现"""
        try:
            # 在线程中重新初始化日志系统
            from tradingagents.utils.logging_init import init_logging, get_logger
            init_logging()
            thread_logger = get_logger('analysis_thread')

            thread_logger.info(f"🔄 [线程池] 开始执行分析: {task_id} - {request.stock_code}")
            logger.info(f"🔄 [线程池] 开始执行分析: {task_id} - {request.stock_code}")

            # 🔧 根据 RedisProgressTracker 的步骤权重计算准确的进度
            # 基础准备阶段 (10%): 0.03 + 0.02 + 0.01 + 0.02 + 0.02 = 0.10
            # 步骤索引 0-4 对应 0-10%

            # 异步更新进度（在线程池中调用）
            def update_progress_sync(progress: int, message: str, step: str):
                """在线程池中同步更新进度"""
                try:
                    # 同时更新 Redis 进度跟踪器
                    if progress_tracker:
                        progress_tracker.update_progress({
                            "progress_percentage": progress,
                            "last_message": message
                        })

                    # 🔥 使用同步方式更新内存和 MongoDB，避免事件循环冲突
                    # 1. 更新内存中的任务状态（使用新事件循环）
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            self.memory_manager.update_task_status(
                                task_id=task_id,
                                status=TaskStatus.RUNNING,
                                progress=progress,
                                message=message,
                                current_step=step
                            )
                        )
                    finally:
                        loop.close()

                    # 2. 更新 MongoDB（使用同步客户端，避免事件循环冲突）
                    from pymongo import MongoClient
                    from app.core.config import settings
                    from datetime import datetime

                    sync_client = MongoClient(settings.MONGO_URI)
                    sync_db = sync_client[settings.MONGO_DB]

                    sync_db.analysis_tasks.update_one(
                        {"task_id": task_id},
                        {
                            "$set": {
                                "progress": progress,
                                "current_step": step,
                                "message": message,
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    sync_client.close()

                except Exception as e:
                    logger.warning(f"⚠️ 进度更新失败: {e}")

            # 配置阶段 - 对应步骤3 "⚙️ 参数设置" (6-8%)
            update_progress_sync(7, "⚙️ 配置分析参数", "configuration")

            # 🆕 智能模型选择逻辑
            from app.services.model_capability_service import get_model_capability_service
            capability_service = get_model_capability_service()

            research_depth = request.parameters.research_depth if request.parameters else "标准"

            # 1. 检查前端是否指定了模型
            if (request.parameters and
                hasattr(request.parameters, 'quick_analysis_model') and
                hasattr(request.parameters, 'deep_analysis_model') and
                request.parameters.quick_analysis_model and
                request.parameters.deep_analysis_model):

                # 使用前端指定的模型
                quick_model = request.parameters.quick_analysis_model
                deep_model = request.parameters.deep_analysis_model

                logger.info(f"📝 [分析服务] 用户指定模型: quick={quick_model}, deep={deep_model}")

                # 验证模型是否合适
                validation = capability_service.validate_model_pair(
                    quick_model, deep_model, research_depth
                )

                if not validation["valid"]:
                    # 记录警告
                    for warning in validation["warnings"]:
                        logger.warning(warning)

                    # 如果模型不合适，自动切换到推荐模型
                    logger.info(f"🔄 自动切换到推荐模型...")
                    quick_model, deep_model = capability_service.recommend_models_for_depth(
                        research_depth
                    )
                    logger.info(f"✅ 已切换: quick={quick_model}, deep={deep_model}")
                else:
                    # 即使验证通过，也记录警告信息
                    for warning in validation["warnings"]:
                        logger.info(warning)
                    logger.info(f"✅ 用户选择的模型验证通过: quick={quick_model}, deep={deep_model}")

            else:
                # 2. 自动推荐模型
                quick_model, deep_model = capability_service.recommend_models_for_depth(
                    research_depth
                )
                logger.info(f"🤖 自动推荐模型: quick={quick_model}, deep={deep_model}")

            # 🔧 根据快速模型和深度模型分别查找对应的供应商和 API URL
            quick_provider_info = get_provider_and_url_by_model_sync(quick_model)
            deep_provider_info = get_provider_and_url_by_model_sync(deep_model)

            quick_provider = quick_provider_info["provider"]
            deep_provider = deep_provider_info["provider"]
            quick_backend_url = quick_provider_info["backend_url"]
            deep_backend_url = deep_provider_info["backend_url"]

            logger.info(f"🔍 [供应商查找] 快速模型 {quick_model} 对应的供应商: {quick_provider}")
            logger.info(f"🔍 [API地址] 快速模型使用 backend_url: {quick_backend_url}")
            logger.info(f"🔍 [供应商查找] 深度模型 {deep_model} 对应的供应商: {deep_provider}")
            logger.info(f"🔍 [API地址] 深度模型使用 backend_url: {deep_backend_url}")

            # 检查两个模型是否来自同一个厂家
            if quick_provider == deep_provider:
                logger.info(f"✅ [供应商验证] 两个模型来自同一厂家: {quick_provider}")
            else:
                logger.info(f"✅ [混合模式] 快速模型({quick_provider}) 和 深度模型({deep_provider}) 来自不同厂家")

            # 获取市场类型
            market_type = request.parameters.market_type if request.parameters else "A股"
            logger.info(f"📊 [市场类型] 使用市场类型: {market_type}")

            # 创建分析配置（支持混合模式）
            config = create_analysis_config(
                research_depth=research_depth,
                selected_analysts=request.parameters.selected_analysts if request.parameters else ["market", "fundamentals"],
                quick_model=quick_model,
                deep_model=deep_model,
                llm_provider=quick_provider,  # 主要使用快速模型的供应商
                market_type=market_type  # 使用前端传递的市场类型
            )

            # 🔧 添加混合模式配置
            config["quick_provider"] = quick_provider
            config["deep_provider"] = deep_provider
            config["quick_backend_url"] = quick_backend_url
            config["deep_backend_url"] = deep_backend_url
            config["backend_url"] = quick_backend_url  # 保持向后兼容

            # 🔍 验证配置中的模型
            logger.info(f"🔍 [模型验证] 配置中的快速模型: {config.get('quick_think_llm')}")
            logger.info(f"🔍 [模型验证] 配置中的深度模型: {config.get('deep_think_llm')}")
            logger.info(f"🔍 [模型验证] 配置中的LLM供应商: {config.get('llm_provider')}")

            # 初始化分析引擎 - 对应步骤4 "🚀 启动引擎" (8-10%)
            update_progress_sync(9, "🚀 初始化AI分析引擎", "engine_initialization")
            trading_graph = self._get_trading_graph(config)

            # 🔍 验证TradingGraph实例中的配置
            logger.info(f"🔍 [引擎验证] TradingGraph配置中的快速模型: {trading_graph.config.get('quick_think_llm')}")
            logger.info(f"🔍 [引擎验证] TradingGraph配置中的深度模型: {trading_graph.config.get('deep_think_llm')}")

            # 准备分析数据
            start_time = datetime.now()

            # 🔧 使用前端传递的分析日期，如果没有则使用当前日期
            if request.parameters and hasattr(request.parameters, 'analysis_date') and request.parameters.analysis_date:
                # 前端传递的是 datetime 对象或字符串
                if isinstance(request.parameters.analysis_date, datetime):
                    analysis_date = request.parameters.analysis_date.strftime("%Y-%m-%d")
                elif isinstance(request.parameters.analysis_date, str):
                    analysis_date = request.parameters.analysis_date
                else:
                    analysis_date = datetime.now().strftime("%Y-%m-%d")
                logger.info(f"📅 使用前端指定的分析日期: {analysis_date}")
            else:
                analysis_date = datetime.now().strftime("%Y-%m-%d")
                logger.info(f"📅 使用当前日期作为分析日期: {analysis_date}")

            # 🔧 智能日期范围处理：获取最近10天的数据，自动处理周末/节假日
            # 这样可以确保即使是周末或节假日，也能获取到最后一个交易日的数据
            from tradingagents.utils.dataflow_utils import get_trading_date_range
            data_start_date, data_end_date = get_trading_date_range(analysis_date, lookback_days=10)

            logger.info(f"📅 分析目标日期: {analysis_date}")
            logger.info(f"📅 数据查询范围: {data_start_date} 至 {data_end_date} (最近10天)")
            logger.info(f"💡 说明: 获取10天数据可自动处理周末、节假日和数据延迟问题")

            # 开始分析 - 进度10%，即将进入分析师阶段
            # 注意：不要手动设置过高的进度，让 graph_progress_callback 来更新实际的分析进度
            update_progress_sync(10, "🤖 开始多智能体协作分析", "agent_analysis")

            # 启动一个异步任务来模拟进度更新
            import threading
            import time

            def simulate_progress():
                """模拟TradingAgents内部进度"""
                try:
                    if not progress_tracker:
                        return

                    # 分析师阶段 - 根据选择的分析师数量动态调整
                    analysts = request.parameters.selected_analysts if request.parameters else ["market", "fundamentals"]

                    # 模拟分析师执行
                    for i, analyst in enumerate(analysts):
                        time.sleep(15)  # 每个分析师大约15秒
                        if analyst == "market":
                            progress_tracker.update_progress("📊 市场分析师正在分析")
                        elif analyst == "fundamentals":
                            progress_tracker.update_progress("💼 基本面分析师正在分析")
                        elif analyst == "news":
                            progress_tracker.update_progress("📰 新闻分析师正在分析")
                        elif analyst == "social":
                            progress_tracker.update_progress("💬 社交媒体分析师正在分析")

                    # 研究团队阶段
                    time.sleep(10)
                    progress_tracker.update_progress("🐂 看涨研究员构建论据")

                    time.sleep(8)
                    progress_tracker.update_progress("🐻 看跌研究员识别风险")

                    # 辩论阶段 - 根据5个级别确定辩论轮次
                    research_depth = request.parameters.research_depth if request.parameters else "标准"
                    if research_depth == "快速":
                        debate_rounds = 1
                    elif research_depth == "基础":
                        debate_rounds = 1
                    elif research_depth == "标准":
                        debate_rounds = 1
                    elif research_depth == "深度":
                        debate_rounds = 2
                    elif research_depth == "全面":
                        debate_rounds = 3
                    else:
                        debate_rounds = 1  # 默认

                    for round_num in range(debate_rounds):
                        time.sleep(12)
                        progress_tracker.update_progress(f"🎯 研究辩论 第{round_num+1}轮")

                    time.sleep(8)
                    progress_tracker.update_progress("👔 研究经理形成共识")

                    # 交易员阶段
                    time.sleep(10)
                    progress_tracker.update_progress("💼 交易员制定策略")

                    # 风险管理阶段
                    time.sleep(8)
                    progress_tracker.update_progress("🔥 激进风险评估")

                    time.sleep(6)
                    progress_tracker.update_progress("🛡️ 保守风险评估")

                    time.sleep(6)
                    progress_tracker.update_progress("⚖️ 中性风险评估")

                    time.sleep(8)
                    progress_tracker.update_progress("🎯 风险经理制定策略")

                    # 最终阶段
                    time.sleep(5)
                    progress_tracker.update_progress("📡 信号处理")

                except Exception as e:
                    logger.warning(f"⚠️ 进度模拟失败: {e}")

            # 启动进度模拟线程
            progress_thread = threading.Thread(target=simulate_progress, daemon=True)
            progress_thread.start()

            # 定义进度回调函数，用于接收 LangGraph 的实时进度
            # 节点进度映射表（与 RedisProgressTracker 的步骤权重对应）
            node_progress_map = {
                # 分析师阶段 (10% → 45%)
                "📊 市场分析师": 27.5,      # 10% + 17.5% (假设2个分析师)
                "💼 基本面分析师": 45,       # 10% + 35%
                "📰 新闻分析师": 27.5,       # 如果有3个分析师
                "💬 社交媒体分析师": 27.5,   # 如果有4个分析师
                # 研究辩论阶段 (45% → 70%)
                "🐂 看涨研究员": 51.25,      # 45% + 6.25%
                "🐻 看跌研究员": 57.5,       # 45% + 12.5%
                "👔 研究经理": 70,           # 45% + 25%
                # 交易员阶段 (70% → 78%)
                "💼 交易员决策": 78,         # 70% + 8%
                # 风险评估阶段 (78% → 93%)
                "🔥 激进风险评估": 81.75,    # 78% + 3.75%
                "🛡️ 保守风险评估": 85.5,    # 78% + 7.5%
                "⚖️ 中性风险评估": 89.25,   # 78% + 11.25%
                "🎯 风险经理": 93,           # 78% + 15%
                # 最终阶段 (93% → 100%)
                "📊 生成报告": 97,           # 93% + 4%
            }

            def graph_progress_callback(message: str):
                """接收 LangGraph 的进度更新

                根据节点名称直接映射到进度百分比，确保与 RedisProgressTracker 的步骤权重一致
                注意：只在进度增加时更新，避免覆盖 RedisProgressTracker 的虚拟步骤进度
                """
                try:
                    logger.info(f"🎯🎯🎯 [Graph进度回调被调用] message={message}")
                    if not progress_tracker:
                        logger.warning(f"⚠️ progress_tracker 为 None，无法更新进度")
                        return

                    # 查找节点对应的进度百分比
                    progress_pct = node_progress_map.get(message)

                    if progress_pct is not None:
                        # 获取当前进度（使用 progress_data 属性）
                        current_progress = progress_tracker.progress_data.get('progress_percentage', 0)

                        # 只在进度增加时更新，避免覆盖虚拟步骤的进度
                        if int(progress_pct) > current_progress:
                            # 更新 Redis 进度跟踪器
                            progress_tracker.update_progress({
                                'progress_percentage': int(progress_pct),
                                'last_message': message
                            })
                            logger.info(f"📊 [Graph进度] 进度已更新: {current_progress}% → {int(progress_pct)}% - {message}")

                            # 🔥 同时更新内存和 MongoDB
                            try:
                                import asyncio
                                from datetime import datetime

                                # 尝试获取当前运行的事件循环
                                try:
                                    loop = asyncio.get_running_loop()
                                    # 如果在事件循环中，使用 create_task
                                    asyncio.create_task(
                                        self._update_progress_async(task_id, int(progress_pct), message)
                                    )
                                    logger.debug(f"✅ [Graph进度] 已提交异步更新任务: {int(progress_pct)}%")
                                except RuntimeError:
                                    # 没有运行的事件循环，使用同步方式更新 MongoDB
                                    from pymongo import MongoClient
                                    from app.core.config import settings

                                    # 创建同步 MongoDB 客户端
                                    sync_client = MongoClient(settings.MONGO_URI)
                                    sync_db = sync_client[settings.MONGO_DB]

                                    # 同步更新 MongoDB
                                    sync_db.analysis_tasks.update_one(
                                        {"task_id": task_id},
                                        {
                                            "$set": {
                                                "progress": int(progress_pct),
                                                "current_step": message,
                                                "message": message,
                                                "updated_at": datetime.utcnow()
                                            }
                                        }
                                    )
                                    sync_client.close()

                                    # 异步更新内存（创建新的事件循环）
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    try:
                                        loop.run_until_complete(
                                            self.memory_manager.update_task_status(
                                                task_id=task_id,
                                                status=TaskStatus.RUNNING,
                                                progress=int(progress_pct),
                                                message=message,
                                                current_step=message
                                            )
                                        )
                                    finally:
                                        loop.close()

                                    logger.debug(f"✅ [Graph进度] 已同步更新内存和MongoDB: {int(progress_pct)}%")
                            except Exception as sync_err:
                                logger.warning(f"⚠️ [Graph进度] 同步更新失败: {sync_err}")
                        else:
                            # 进度没有增加，只更新消息
                            progress_tracker.update_progress({
                                'last_message': message
                            })
                            logger.info(f"📊 [Graph进度] 进度未变化({current_progress}% >= {int(progress_pct)}%)，仅更新消息: {message}")
                    else:
                        # 未知节点，只更新消息
                        logger.warning(f"⚠️ [Graph进度] 未知节点: {message}，仅更新消息")
                        progress_tracker.update_progress({
                            'last_message': message
                        })

                except Exception as e:
                    logger.error(f"❌ Graph进度回调失败: {e}", exc_info=True)

            logger.info(f"🚀 准备调用 trading_graph.propagate，progress_callback={graph_progress_callback}")

            # 执行实际分析，传递进度回调和task_id
            state, decision = trading_graph.propagate(
                request.stock_code,
                analysis_date,
                progress_callback=graph_progress_callback,
                task_id=task_id
            )

            logger.info(f"✅ trading_graph.propagate 执行完成")

            # 🔍 调试：检查decision的结构
            logger.info(f"🔍 [DEBUG] Decision类型: {type(decision)}")
            logger.info(f"🔍 [DEBUG] Decision内容: {decision}")
            if isinstance(decision, dict):
                logger.info(f"🔍 [DEBUG] Decision键: {list(decision.keys())}")
            elif hasattr(decision, '__dict__'):
                logger.info(f"🔍 [DEBUG] Decision属性: {list(vars(decision).keys())}")

            # 处理结果
            if progress_tracker:
                progress_tracker.update_progress("📊 处理分析结果")
            update_progress_sync(90, "处理分析结果...", "result_processing")

            execution_time = (datetime.now() - start_time).total_seconds()

            # 从state中提取reports字段
            reports = {}
            try:
                # 定义所有可能的报告字段
                report_fields = [
                    'market_report',
                    'sentiment_report',
                    'news_report',
                    'fundamentals_report',
                    'investment_plan',
                    'trader_investment_plan',
                    'final_trade_decision'
                ]

                # 从state中提取报告内容
                for field in report_fields:
                    if hasattr(state, field):
                        value = getattr(state, field, "")
                    elif isinstance(state, dict) and field in state:
                        value = state[field]
                    else:
                        value = ""

                    if isinstance(value, str) and len(value.strip()) > 10:  # 只保存有实际内容的报告
                        reports[field] = value.strip()
                        logger.info(f"📊 [REPORTS] 提取报告: {field} - 长度: {len(value.strip())}")
                    else:
                        logger.debug(f"⚠️ [REPORTS] 跳过报告: {field} - 内容为空或太短")

                # 处理研究团队辩论状态报告
                if hasattr(state, 'investment_debate_state') or (isinstance(state, dict) and 'investment_debate_state' in state):
                    debate_state = getattr(state, 'investment_debate_state', None) if hasattr(state, 'investment_debate_state') else state.get('investment_debate_state')
                    if debate_state:
                        # 提取多头研究员历史
                        if hasattr(debate_state, 'bull_history'):
                            bull_content = getattr(debate_state, 'bull_history', "")
                        elif isinstance(debate_state, dict) and 'bull_history' in debate_state:
                            bull_content = debate_state['bull_history']
                        else:
                            bull_content = ""

                        if bull_content and len(bull_content.strip()) > 10:
                            reports['bull_researcher'] = bull_content.strip()
                            logger.info(f"📊 [REPORTS] 提取报告: bull_researcher - 长度: {len(bull_content.strip())}")

                        # 提取空头研究员历史
                        if hasattr(debate_state, 'bear_history'):
                            bear_content = getattr(debate_state, 'bear_history', "")
                        elif isinstance(debate_state, dict) and 'bear_history' in debate_state:
                            bear_content = debate_state['bear_history']
                        else:
                            bear_content = ""

                        if bear_content and len(bear_content.strip()) > 10:
                            reports['bear_researcher'] = bear_content.strip()
                            logger.info(f"📊 [REPORTS] 提取报告: bear_researcher - 长度: {len(bear_content.strip())}")

                        # 提取研究经理决策
                        if hasattr(debate_state, 'judge_decision'):
                            decision_content = getattr(debate_state, 'judge_decision', "")
                        elif isinstance(debate_state, dict) and 'judge_decision' in debate_state:
                            decision_content = debate_state['judge_decision']
                        else:
                            decision_content = str(debate_state)

                        if decision_content and len(decision_content.strip()) > 10:
                            reports['research_team_decision'] = decision_content.strip()
                            logger.info(f"📊 [REPORTS] 提取报告: research_team_decision - 长度: {len(decision_content.strip())}")

                # 处理风险管理团队辩论状态报告
                if hasattr(state, 'risk_debate_state') or (isinstance(state, dict) and 'risk_debate_state' in state):
                    risk_state = getattr(state, 'risk_debate_state', None) if hasattr(state, 'risk_debate_state') else state.get('risk_debate_state')
                    if risk_state:
                        # 提取激进分析师历史
                        if hasattr(risk_state, 'risky_history'):
                            risky_content = getattr(risk_state, 'risky_history', "")
                        elif isinstance(risk_state, dict) and 'risky_history' in risk_state:
                            risky_content = risk_state['risky_history']
                        else:
                            risky_content = ""

                        if risky_content and len(risky_content.strip()) > 10:
                            reports['risky_analyst'] = risky_content.strip()
                            logger.info(f"📊 [REPORTS] 提取报告: risky_analyst - 长度: {len(risky_content.strip())}")

                        # 提取保守分析师历史
                        if hasattr(risk_state, 'safe_history'):
                            safe_content = getattr(risk_state, 'safe_history', "")
                        elif isinstance(risk_state, dict) and 'safe_history' in risk_state:
                            safe_content = risk_state['safe_history']
                        else:
                            safe_content = ""

                        if safe_content and len(safe_content.strip()) > 10:
                            reports['safe_analyst'] = safe_content.strip()
                            logger.info(f"📊 [REPORTS] 提取报告: safe_analyst - 长度: {len(safe_content.strip())}")

                        # 提取中性分析师历史
                        if hasattr(risk_state, 'neutral_history'):
                            neutral_content = getattr(risk_state, 'neutral_history', "")
                        elif isinstance(risk_state, dict) and 'neutral_history' in risk_state:
                            neutral_content = risk_state['neutral_history']
                        else:
                            neutral_content = ""

                        if neutral_content and len(neutral_content.strip()) > 10:
                            reports['neutral_analyst'] = neutral_content.strip()
                            logger.info(f"📊 [REPORTS] 提取报告: neutral_analyst - 长度: {len(neutral_content.strip())}")

                        # 提取投资组合经理决策
                        if hasattr(risk_state, 'judge_decision'):
                            risk_decision = getattr(risk_state, 'judge_decision', "")
                        elif isinstance(risk_state, dict) and 'judge_decision' in risk_state:
                            risk_decision = risk_state['judge_decision']
                        else:
                            risk_decision = str(risk_state)

                        if risk_decision and len(risk_decision.strip()) > 10:
                            reports['risk_management_decision'] = risk_decision.strip()
                            logger.info(f"📊 [REPORTS] 提取报告: risk_management_decision - 长度: {len(risk_decision.strip())}")

                logger.info(f"📊 [REPORTS] 从state中提取到 {len(reports)} 个报告: {list(reports.keys())}")

            except Exception as e:
                logger.warning(f"⚠️ 提取reports时出错: {e}")
                # 降级到从detailed_analysis提取
                try:
                    if isinstance(decision, dict):
                        for key, value in decision.items():
                            if isinstance(value, str) and len(value) > 50:
                                reports[key] = value
                        logger.info(f"📊 降级：从decision中提取到 {len(reports)} 个报告")
                except Exception as fallback_error:
                    logger.warning(f"⚠️ 降级提取也失败: {fallback_error}")

            # 🔥 格式化decision数据（参考web目录的实现）
            formatted_decision = {}
            try:
                if isinstance(decision, dict):
                    # 处理目标价格
                    target_price = decision.get('target_price')
                    if target_price is not None and target_price != 'N/A':
                        try:
                            if isinstance(target_price, str):
                                # 移除货币符号和空格
                                clean_price = target_price.replace('$', '').replace('¥', '').replace('￥', '').strip()
                                target_price = float(clean_price) if clean_price and clean_price != 'None' else None
                            elif isinstance(target_price, (int, float)):
                                target_price = float(target_price)
                            else:
                                target_price = None
                        except (ValueError, TypeError):
                            target_price = None
                    else:
                        target_price = None

                    # 将英文投资建议转换为中文
                    action_translation = {
                        'BUY': '买入',
                        'SELL': '卖出',
                        'HOLD': '持有',
                        'buy': '买入',
                        'sell': '卖出',
                        'hold': '持有'
                    }
                    action = decision.get('action', '持有')
                    chinese_action = action_translation.get(action, action)

                    formatted_decision = {
                        'action': chinese_action,
                        'confidence': decision.get('confidence', 0.5),
                        'risk_score': decision.get('risk_score', 0.3),
                        'target_price': target_price,
                        'reasoning': decision.get('reasoning', '暂无分析推理')
                    }

                    logger.info(f"🎯 [DEBUG] 格式化后的decision: {formatted_decision}")
                else:
                    # 处理其他类型
                    formatted_decision = {
                        'action': '持有',
                        'confidence': 0.5,
                        'risk_score': 0.3,
                        'target_price': None,
                        'reasoning': '暂无分析推理'
                    }
                    logger.warning(f"⚠️ Decision不是字典类型: {type(decision)}")
            except Exception as e:
                logger.error(f"❌ 格式化decision失败: {e}")
                formatted_decision = {
                    'action': '持有',
                    'confidence': 0.5,
                    'risk_score': 0.3,
                    'target_price': None,
                    'reasoning': '暂无分析推理'
                }

            # 🔥 按照web目录的方式生成summary和recommendation
            summary = ""
            recommendation = ""

            # 1. 优先从reports中的final_trade_decision提取summary（与web目录保持一致）
            if isinstance(reports, dict) and 'final_trade_decision' in reports:
                final_decision_content = reports['final_trade_decision']
                if isinstance(final_decision_content, str) and len(final_decision_content) > 50:
                    # 提取前200个字符作为摘要（与web目录完全一致）
                    summary = final_decision_content[:200].replace('#', '').replace('*', '').strip()
                    if len(final_decision_content) > 200:
                        summary += "..."
                    logger.info(f"📝 [SUMMARY] 从final_trade_decision提取摘要: {len(summary)}字符")

            # 2. 如果没有final_trade_decision，从state中提取
            if not summary and isinstance(state, dict):
                final_decision = state.get('final_trade_decision', '')
                if isinstance(final_decision, str) and len(final_decision) > 50:
                    summary = final_decision[:200].replace('#', '').replace('*', '').strip()
                    if len(final_decision) > 200:
                        summary += "..."
                    logger.info(f"📝 [SUMMARY] 从state.final_trade_decision提取摘要: {len(summary)}字符")

            # 3. 生成recommendation（从decision的reasoning）
            if isinstance(formatted_decision, dict):
                action = formatted_decision.get('action', '持有')
                target_price = formatted_decision.get('target_price')
                reasoning = formatted_decision.get('reasoning', '')

                # 生成投资建议
                recommendation = f"投资建议：{action}。"
                if target_price:
                    recommendation += f"目标价格：{target_price}元。"
                if reasoning:
                    recommendation += f"决策依据：{reasoning}"
                logger.info(f"💡 [RECOMMENDATION] 生成投资建议: {len(recommendation)}字符")

            # 4. 如果还是没有，从其他报告中提取
            if not summary and isinstance(reports, dict):
                # 尝试从其他报告中提取摘要
                for report_name, content in reports.items():
                    if isinstance(content, str) and len(content) > 100:
                        summary = content[:200].replace('#', '').replace('*', '').strip()
                        if len(content) > 200:
                            summary += "..."
                        logger.info(f"📝 [SUMMARY] 从{report_name}提取摘要: {len(summary)}字符")
                        break

            # 5. 最后的备用方案
            if not summary:
                summary = f"对{request.stock_code}的分析已完成，请查看详细报告。"
                logger.warning(f"⚠️ [SUMMARY] 使用备用摘要")

            if not recommendation:
                recommendation = f"请参考详细分析报告做出投资决策。"
                logger.warning(f"⚠️ [RECOMMENDATION] 使用备用建议")

            # 从决策中提取模型信息
            model_info = decision.get('model_info', 'Unknown') if isinstance(decision, dict) else 'Unknown'

            # 构建结果
            result = {
                "analysis_id": str(uuid.uuid4()),
                "stock_code": request.stock_code,
                "stock_symbol": request.stock_code,  # 添加stock_symbol字段以保持兼容性
                "analysis_date": analysis_date,
                "summary": summary,
                "recommendation": recommendation,
                "confidence_score": formatted_decision.get("confidence", 0.0) if isinstance(formatted_decision, dict) else 0.0,
                "risk_level": "中等",  # 可以根据risk_score计算
                "key_points": [],  # 可以从reasoning中提取关键点
                "detailed_analysis": decision,
                "execution_time": execution_time,
                "tokens_used": decision.get("tokens_used", 0) if isinstance(decision, dict) else 0,
                "state": state,
                # 添加分析师信息
                "analysts": request.parameters.selected_analysts if request.parameters else [],
                "research_depth": request.parameters.research_depth if request.parameters else "快速",
                # 添加提取的报告内容
                "reports": reports,
                # 🔥 关键修复：添加格式化后的decision字段！
                "decision": formatted_decision,
                # 🔥 添加模型信息字段
                "model_info": model_info,
                # 🆕 性能指标数据
                "performance_metrics": state.get("performance_metrics", {}) if isinstance(state, dict) else {}
            }

            logger.info(f"✅ [线程池] 分析完成: {task_id} - 耗时{execution_time:.2f}秒")

            # 🔍 调试：检查返回的result结构
            logger.info(f"🔍 [DEBUG] 返回result的键: {list(result.keys())}")
            logger.info(f"🔍 [DEBUG] 返回result中有decision: {bool(result.get('decision'))}")
            if result.get('decision'):
                decision = result['decision']
                logger.info(f"🔍 [DEBUG] 返回decision内容: {decision}")

            return result

        except Exception as e:
            logger.error(f"❌ [线程池] 分析执行失败: {task_id} - {e}")

            # 格式化错误信息为用户友好的提示
            from ..utils.error_formatter import ErrorFormatter

            # 收集上下文信息
            error_context = {}
            if request and hasattr(request, 'parameters') and request.parameters:
                if hasattr(request.parameters, 'quick_model'):
                    error_context['model'] = request.parameters.quick_model
                if hasattr(request.parameters, 'deep_model'):
                    error_context['model'] = request.parameters.deep_model

            # 格式化错误
            formatted_error = ErrorFormatter.format_error(str(e), error_context)

            # 构建用户友好的错误消息
            user_friendly_error = (
                f"{formatted_error['title']}\n\n"
                f"{formatted_error['message']}\n\n"
                f"💡 {formatted_error['suggestion']}"
            )

            # 抛出包含友好错误信息的异常
            raise Exception(user_friendly_error) from e

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        logger.info(f"🔍 查询任务状态: {task_id}")
        logger.info(f"🔍 当前服务实例ID: {id(self)}")
        logger.info(f"🔍 内存管理器实例ID: {id(self.memory_manager)}")

        # 强制使用全局内存管理器实例（临时解决方案）
        global_memory_manager = get_memory_state_manager()
        logger.info(f"🔍 全局内存管理器实例ID: {id(global_memory_manager)}")

        # 获取统计信息
        stats = await global_memory_manager.get_statistics()
        logger.info(f"📊 内存中任务统计: {stats}")

        result = await global_memory_manager.get_task_dict(task_id)
        if result:
            logger.info(f"✅ 找到任务: {task_id} - 状态: {result.get('status')}")

            # 🔍 调试：检查从内存获取的result_data
            result_data = result.get('result_data')
            logger.debug(f"🔍 [GET_STATUS] result_data存在: {bool(result_data)}")
            if result_data:
                logger.debug(f"🔍 [GET_STATUS] result_data键: {list(result_data.keys())}")
                logger.debug(f"🔍 [GET_STATUS] result_data中有decision: {bool(result_data.get('decision'))}")
                if result_data.get('decision'):
                    logger.debug(f"🔍 [GET_STATUS] decision内容: {result_data['decision']}")
            else:
                logger.debug(f"🔍 [GET_STATUS] result_data为空或不存在（任务运行中，这是正常的）")

            # 优先从Redis获取详细进度信息
            redis_progress = get_progress_by_id(task_id)
            if redis_progress:
                logger.info(f"📊 [Redis进度] 获取到详细进度: {task_id}")

                # 从 steps 数组中提取当前步骤的名称和描述
                current_step_index = redis_progress.get('current_step', 0)
                steps = redis_progress.get('steps', [])
                current_step_name = redis_progress.get('current_step_name', '')
                current_step_description = redis_progress.get('current_step_description', '')

                # 如果 Redis 中的名称/描述为空，从 steps 数组中提取
                if not current_step_name and steps and 0 <= current_step_index < len(steps):
                    current_step_info = steps[current_step_index]
                    current_step_name = current_step_info.get('name', '')
                    current_step_description = current_step_info.get('description', '')
                    logger.info(f"📋 从steps数组提取当前步骤信息: index={current_step_index}, name={current_step_name}")

                # 合并Redis进度数据
                result.update({
                    'progress': redis_progress.get('progress_percentage', result.get('progress', 0)),
                    'current_step': current_step_index,  # 使用索引而不是名称
                    'current_step_name': current_step_name,  # 步骤名称
                    'current_step_description': current_step_description,  # 步骤描述
                    'message': redis_progress.get('last_message', result.get('message', '')),
                    'elapsed_time': redis_progress.get('elapsed_time', 0),
                    'remaining_time': redis_progress.get('remaining_time', 0),
                    'estimated_total_time': redis_progress.get('estimated_total_time', result.get('estimated_duration', 300)),  # 🔧 修复：使用Redis中的预估总时长
                    'steps': steps,
                    'start_time': result.get('start_time'),  # 保持原有格式
                    'last_update': redis_progress.get('last_update', result.get('start_time'))
                })
            else:
                # 如果Redis中没有，尝试从内存中的进度跟踪器获取
                if task_id in self._progress_trackers:
                    progress_tracker = self._progress_trackers[task_id]
                    progress_data = progress_tracker.to_dict()

                    # 合并进度跟踪器的详细信息
                    result.update({
                        'progress': progress_data['progress'],
                        'current_step': progress_data['current_step'],
                        'message': progress_data['message'],
                        'elapsed_time': progress_data['elapsed_time'],
                        'remaining_time': progress_data['remaining_time'],
                        'estimated_total_time': progress_data.get('estimated_total_time', 0),
                        'steps': progress_data['steps'],
                        'start_time': progress_data['start_time'],
                        'last_update': progress_data['last_update']
                    })
                    logger.info(f"📊 合并内存进度跟踪器数据: {task_id}")
                else:
                    logger.info(f"⚠️ 未找到进度信息: {task_id}")
        else:
            logger.warning(f"❌ 未找到任务: {task_id}")

        return result

    async def list_all_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取所有任务列表（不限用户）
        - 合并内存和 MongoDB 数据
        - 按开始时间倒序排列
        """
        try:
            task_status = None
            if status:
                try:
                    status_mapping = {
                        "processing": "running",
                        "pending": "pending",
                        "completed": "completed",
                        "failed": "failed",
                        "cancelled": "cancelled"
                    }
                    mapped_status = status_mapping.get(status, status)
                    task_status = TaskStatus(mapped_status)
                except ValueError:
                    logger.warning(f"⚠️ [Tasks] 无效的状态值: {status}")
                    task_status = None

            # 1) 从内存读取所有任务
            logger.info(f"📋 [Tasks] 准备从内存读取所有任务: status={status}, limit={limit}, offset={offset}")
            tasks_in_mem = await self.memory_manager.list_all_tasks(
                status=task_status,
                limit=limit * 2,
                offset=0
            )
            logger.info(f"📋 [Tasks] 内存返回数量: {len(tasks_in_mem)}")

            # 2) 从 MongoDB 读取任务
            db = get_mongo_db()
            collection = db["analysis_tasks"]

            query = {}
            if task_status:
                query["status"] = task_status.value

            count = await collection.count_documents(query)
            logger.info(f"📋 [Tasks] MongoDB 任务总数: {count}")

            cursor = collection.find(query).sort("start_time", -1).limit(limit * 2)
            tasks_from_db = []
            async for doc in cursor:
                doc.pop("_id", None)
                tasks_from_db.append(doc)

            logger.info(f"📋 [Tasks] MongoDB 返回数量: {len(tasks_from_db)}")

            # 3) 合并任务（内存优先）
            task_dict = {}

            # 先添加 MongoDB 中的任务
            for task in tasks_from_db:
                task_id = task.get("task_id")
                if task_id:
                    task_dict[task_id] = task

            # 再添加内存中的任务（覆盖 MongoDB 中的同名任务）
            for task in tasks_in_mem:
                task_id = task.get("task_id")
                if task_id:
                    task_dict[task_id] = task

            # 转换为列表并按时间排序
            merged_tasks = list(task_dict.values())
            merged_tasks.sort(key=lambda x: x.get('start_time', ''), reverse=True)

            # 分页
            results = merged_tasks[offset:offset + limit]

            # 为结果补齐股票名称
            results = self._enrich_stock_names(results)
            logger.info(f"📋 [Tasks] 合并后返回数量: {len(results)} (内存: {len(tasks_in_mem)}, MongoDB: {count})")
            return results
        except Exception as outer_e:
            logger.error(f"❌ list_all_tasks 外层异常: {outer_e}", exc_info=True)
            return []

    async def list_user_tasks(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取用户任务列表
        - 对于 processing 状态：优先从内存读取（实时进度）
        - 对于 completed/failed/all 状态：合并内存和 MongoDB 数据
        """
        try:
            task_status = None
            if status:
                try:
                    # 前端传递的是 "processing"，但 TaskStatus 使用的是 "running"
                    # 需要做映射转换
                    status_mapping = {
                        "processing": "running",  # 前端使用 processing，内存使用 running
                        "pending": "pending",
                        "completed": "completed",
                        "failed": "failed",
                        "cancelled": "cancelled"
                    }
                    mapped_status = status_mapping.get(status, status)
                    task_status = TaskStatus(mapped_status)
                except ValueError:
                    logger.warning(f"⚠️ [Tasks] 无效的状态值: {status}")
                    task_status = None

            # 1) 从内存读取任务
            logger.info(f"📋 [Tasks] 准备从内存读取任务: user_id={user_id}, status={status} (mapped to {task_status}), limit={limit}, offset={offset}")
            tasks_in_mem = await self.memory_manager.list_user_tasks(
                user_id=user_id,
                status=task_status,
                limit=limit * 2,  # 多读一些，后面合并去重
                offset=0  # 内存中的任务不多，全部读取
            )
            logger.info(f"📋 [Tasks] 内存返回数量: {len(tasks_in_mem)}")

            # 2) 🔧 对于 processing/running 状态，需要合并 MongoDB 数据以获取最新进度
            # 因为 graph_progress_callback 可能直接更新了 MongoDB，而内存数据可能是旧的

            # 3) 从 MongoDB 读取历史任务（用于合并或兜底）
            logger.info(f"📋 [Tasks] 从 MongoDB 读取历史任务")
            mongo_tasks: List[Dict[str, Any]] = []
            count = 0
            try:
                db = get_mongo_db()

                # user_id 可能是字符串或 ObjectId，做兼容
                uid_candidates: List[Any] = [user_id]

                # 特殊处理 admin 用户
                if str(user_id) == 'admin':
                    # admin 用户：添加固定的 ObjectId 和字符串形式
                    try:
                        from bson import ObjectId
                        admin_oid_str = '507f1f77bcf86cd799439011'
                        uid_candidates.append(ObjectId(admin_oid_str))
                        uid_candidates.append(admin_oid_str)  # 兼容字符串存储
                        logger.info(f"📋 [Tasks] admin用户查询，候选ID: ['admin', ObjectId('{admin_oid_str}'), '{admin_oid_str}']")
                    except Exception as e:
                        logger.warning(f"⚠️ [Tasks] admin用户ObjectId创建失败: {e}")
                else:
                    # 普通用户：尝试转换为 ObjectId
                    try:
                        from bson import ObjectId
                        uid_candidates.append(ObjectId(user_id))
                        logger.debug(f"📋 [Tasks] 用户ID已转换为ObjectId: {user_id}")
                    except Exception as conv_err:
                        logger.warning(f"⚠️ [Tasks] 用户ID转换ObjectId失败，按字符串匹配: {conv_err}")

                # 兼容 user_id 与 user 两种字段名
                base_condition = {"$in": uid_candidates}
                or_conditions: List[Dict[str, Any]] = [
                    {"user_id": base_condition},
                    {"user": base_condition}
                ]
                query = {"$or": or_conditions}

                if task_status:
                    # 使用映射后的状态值（TaskStatus枚举的value）
                    query["status"] = task_status.value
                    logger.info(f"📋 [Tasks] 添加状态过滤: {task_status.value}")

                logger.info(f"📋 [Tasks] MongoDB 查询条件: {query}")
                # 读取更多数据用于合并
                cursor = db.analysis_tasks.find(query).sort("created_at", -1).limit(limit * 2)
                async for doc in cursor:
                    count += 1
                    # 兼容 user_id 或 user 字段
                    user_field_val = doc.get("user_id", doc.get("user"))
                    # 🔧 兼容多种股票代码字段名：symbol, stock_code, stock_symbol
                    stock_code_value = doc.get("symbol") or doc.get("stock_code") or doc.get("stock_symbol")
                    item = {
                        "task_id": doc.get("task_id"),
                        "user_id": str(user_field_val) if user_field_val is not None else None,
                        "symbol": stock_code_value,  # 🔧 添加 symbol 字段（前端优先使用）
                        "stock_code": stock_code_value,  # 🔧 兼容字段
                        "stock_symbol": stock_code_value,  # 🔧 兼容字段
                        "stock_name": doc.get("stock_name"),
                        "status": str(doc.get("status", "pending")),
                        "progress": int(doc.get("progress", 0) or 0),
                        "message": doc.get("message", ""),
                        "current_step": doc.get("current_step", ""),
                        "start_time": doc.get("started_at") or doc.get("created_at"),
                        "end_time": doc.get("completed_at"),
                        "parameters": doc.get("parameters", {}),
                        "execution_time": doc.get("execution_time"),
                        "tokens_used": doc.get("tokens_used"),
                        # 为兼容前端，这里沿用 memory_manager 的字段名
                        "result_data": doc.get("result"),
                    }
                    # 时间格式转为 ISO 字符串（添加时区信息）
                    for k in ("start_time", "end_time"):
                        if item.get(k) and hasattr(item[k], "isoformat"):
                            dt = item[k]
                            # 如果是 naive datetime（没有时区信息），假定为 UTC+8
                            if dt.tzinfo is None:
                                from datetime import timezone, timedelta
                                china_tz = timezone(timedelta(hours=8))
                                dt = dt.replace(tzinfo=china_tz)
                            item[k] = dt.isoformat()
                    mongo_tasks.append(item)

                logger.info(f"📋 [Tasks] MongoDB 返回数量: {count}")
            except Exception as mongo_e:
                logger.error(f"❌ MongoDB 查询任务列表失败: {mongo_e}", exc_info=True)
                # MongoDB 查询失败，继续使用内存数据

            # 4) 合并内存和 MongoDB 数据，去重
            # 🔧 对于 processing/running 状态，优先使用 MongoDB 中的进度数据
            # 因为 graph_progress_callback 直接更新 MongoDB，而内存数据可能是旧的
            task_dict = {}

            # 先添加内存中的任务
            for task in tasks_in_mem:
                task_id = task.get("task_id")
                if task_id:
                    task_dict[task_id] = task

            # 再添加 MongoDB 中的任务
            # 对于 processing/running 状态，使用 MongoDB 中的进度数据（更新）
            # 对于其他状态，如果内存中已有，则跳过（内存优先）
            for task in mongo_tasks:
                task_id = task.get("task_id")
                if not task_id:
                    continue

                # 如果内存中已有这个任务
                if task_id in task_dict:
                    mem_task = task_dict[task_id]
                    mongo_task = task

                    # 如果是 processing/running 状态，使用 MongoDB 中的进度数据
                    if mongo_task.get("status") in ["processing", "running"]:
                        # 保留内存中的基本信息，但更新进度相关字段
                        mem_task["progress"] = mongo_task.get("progress", mem_task.get("progress", 0))
                        mem_task["message"] = mongo_task.get("message", mem_task.get("message", ""))
                        mem_task["current_step"] = mongo_task.get("current_step", mem_task.get("current_step", ""))
                        logger.debug(f"🔄 [Tasks] 更新任务进度: {task_id}, progress={mem_task['progress']}%")
                else:
                    # 内存中没有，直接添加 MongoDB 中的任务
                    task_dict[task_id] = task

            # 转换为列表并按时间排序
            merged_tasks = list(task_dict.values())
            merged_tasks.sort(key=lambda x: x.get('start_time', ''), reverse=True)

            # 分页
            results = merged_tasks[offset:offset + limit]

            # 🔥 统一处理时区信息（确保所有时间字段都有时区标识）
            from datetime import timezone, timedelta
            china_tz = timezone(timedelta(hours=8))

            for task in results:
                for time_field in ("start_time", "end_time", "created_at", "started_at", "completed_at"):
                    value = task.get(time_field)
                    if value:
                        # 如果是 datetime 对象
                        if hasattr(value, "isoformat"):
                            # 如果是 naive datetime，添加时区信息
                            if value.tzinfo is None:
                                value = value.replace(tzinfo=china_tz)
                            task[time_field] = value.isoformat()
                        # 如果是字符串且没有时区标识，添加时区标识
                        elif isinstance(value, str) and value and not value.endswith(('Z', '+08:00', '+00:00')):
                            # 检查是否是 ISO 格式的时间字符串
                            if 'T' in value or ' ' in value:
                                task[time_field] = value.replace(' ', 'T') + '+08:00'

            # 为结果补齐股票名称
            results = self._enrich_stock_names(results)
            logger.info(f"📋 [Tasks] 合并后返回数量: {len(results)} (内存: {len(tasks_in_mem)}, MongoDB: {count})")
            return results
        except Exception as outer_e:
            logger.error(f"❌ list_user_tasks 外层异常: {outer_e}", exc_info=True)
            return []

    async def cleanup_zombie_tasks(self, max_running_hours: int = 2) -> Dict[str, Any]:
        """清理僵尸任务（长时间处于 processing/running 状态的任务）

        Args:
            max_running_hours: 最大运行时长（小时），超过此时长的任务将被标记为失败

        Returns:
            清理结果统计
        """
        try:
            # 1) 清理内存中的僵尸任务
            memory_cleaned = await self.memory_manager.cleanup_zombie_tasks(max_running_hours)

            # 2) 清理 MongoDB 中的僵尸任务
            db = get_mongo_db()
            from datetime import timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=max_running_hours)

            # 查找长时间处于 processing 状态的任务
            zombie_filter = {
                "status": {"$in": ["processing", "running", "pending"]},
                "$or": [
                    {"started_at": {"$lt": cutoff_time}},
                    {"created_at": {"$lt": cutoff_time, "started_at": None}}
                ]
            }

            # 更新为失败状态
            update_result = await db.analysis_tasks.update_many(
                zombie_filter,
                {
                    "$set": {
                        "status": "failed",
                        "last_error": f"任务超时（运行时间超过 {max_running_hours} 小时）",
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            mongo_cleaned = update_result.modified_count

            logger.info(f"🧹 僵尸任务清理完成: 内存={memory_cleaned}, MongoDB={mongo_cleaned}")

            return {
                "success": True,
                "memory_cleaned": memory_cleaned,
                "mongo_cleaned": mongo_cleaned,
                "total_cleaned": memory_cleaned + mongo_cleaned,
                "max_running_hours": max_running_hours
            }

        except Exception as e:
            logger.error(f"❌ 清理僵尸任务失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "memory_cleaned": 0,
                "mongo_cleaned": 0,
                "total_cleaned": 0
            }

    async def get_zombie_tasks(self, max_running_hours: int = 2) -> List[Dict[str, Any]]:
        """获取僵尸任务列表（不执行清理，仅查询）

        Args:
            max_running_hours: 最大运行时长（小时）

        Returns:
            僵尸任务列表
        """
        try:
            db = get_mongo_db()
            from datetime import timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=max_running_hours)

            # 查找长时间处于 processing 状态的任务
            zombie_filter = {
                "status": {"$in": ["processing", "running", "pending"]},
                "$or": [
                    {"started_at": {"$lt": cutoff_time}},
                    {"created_at": {"$lt": cutoff_time, "started_at": None}}
                ]
            }

            cursor = db.analysis_tasks.find(zombie_filter).sort("created_at", -1)
            zombie_tasks = []

            async for doc in cursor:
                task = {
                    "task_id": doc.get("task_id"),
                    "user_id": str(doc.get("user_id", doc.get("user"))),
                    "stock_code": doc.get("stock_code"),
                    "stock_name": doc.get("stock_name"),
                    "status": doc.get("status"),
                    "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                    "started_at": doc.get("started_at").isoformat() if doc.get("started_at") else None,
                    "running_hours": None
                }

                # 计算运行时长
                start_time = doc.get("started_at") or doc.get("created_at")
                if start_time:
                    running_seconds = (datetime.utcnow() - start_time).total_seconds()
                    task["running_hours"] = round(running_seconds / 3600, 2)

                zombie_tasks.append(task)

            logger.info(f"📋 查询到 {len(zombie_tasks)} 个僵尸任务")
            return zombie_tasks

        except Exception as e:
            logger.error(f"❌ 查询僵尸任务失败: {e}", exc_info=True)
            return []



    async def _update_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        progress: int,
        error_message: str = None
    ):
        """更新任务状态"""
        try:
            db = get_mongo_db()
            update_data = {
                "status": status,
                "progress": progress,
                "updated_at": datetime.utcnow()
            }

            if status == AnalysisStatus.PROCESSING and progress == 10:
                update_data["started_at"] = datetime.utcnow()
            elif status == AnalysisStatus.COMPLETED:
                update_data["completed_at"] = datetime.utcnow()
            elif status == AnalysisStatus.FAILED:
                update_data["last_error"] = error_message
                update_data["completed_at"] = datetime.utcnow()

            await db.analysis_tasks.update_one(
                {"task_id": task_id},
                {"$set": update_data}
            )

            logger.debug(f"📊 任务状态已更新: {task_id} -> {status} ({progress}%)")

        except Exception as e:
            logger.error(f"❌ 更新任务状态失败: {task_id} - {e}")

    async def _save_analysis_result(self, task_id: str, result: Dict[str, Any]):
        """保存分析结果（原始方法）"""
        try:
            db = get_mongo_db()
            await db.analysis_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"result": result}}
            )
            logger.debug(f"💾 分析结果已保存: {task_id}")
        except Exception as e:
            logger.error(f"❌ 保存分析结果失败: {task_id} - {e}")

    async def _save_analysis_result_web_style(self, task_id: str, result: Dict[str, Any]):
        """保存分析结果 - 采用web目录的方式，保存到analysis_reports集合"""
        try:
            db = get_mongo_db()

            # 生成分析ID（与web目录保持一致）
            from datetime import datetime
            timestamp = datetime.utcnow()  # 存储 UTC 时间（标准做法）
            stock_symbol = result.get('stock_symbol') or result.get('stock_code', 'UNKNOWN')
            analysis_id = f"{stock_symbol}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

            # 处理reports字段 - 从state中提取所有分析报告
            reports = {}
            if 'state' in result:
                try:
                    state = result['state']

                    # 定义所有可能的报告字段
                    report_fields = [
                        'market_report',
                        'sentiment_report',
                        'news_report',
                        'fundamentals_report',
                        'investment_plan',
                        'trader_investment_plan',
                        'final_trade_decision'
                    ]

                    # 从state中提取报告内容
                    for field in report_fields:
                        if hasattr(state, field):
                            value = getattr(state, field, "")
                        elif isinstance(state, dict) and field in state:
                            value = state[field]
                        else:
                            value = ""

                        if isinstance(value, str) and len(value.strip()) > 10:  # 只保存有实际内容的报告
                            reports[field] = value.strip()

                    # 处理研究团队辩论状态报告
                    if hasattr(state, 'investment_debate_state') or (isinstance(state, dict) and 'investment_debate_state' in state):
                        debate_state = getattr(state, 'investment_debate_state', None) if hasattr(state, 'investment_debate_state') else state.get('investment_debate_state')
                        if debate_state:
                            # 提取多头研究员历史
                            if hasattr(debate_state, 'bull_history'):
                                bull_content = getattr(debate_state, 'bull_history', "")
                            elif isinstance(debate_state, dict) and 'bull_history' in debate_state:
                                bull_content = debate_state['bull_history']
                            else:
                                bull_content = ""

                            if bull_content and len(bull_content.strip()) > 10:
                                reports['bull_researcher'] = bull_content.strip()

                            # 提取空头研究员历史
                            if hasattr(debate_state, 'bear_history'):
                                bear_content = getattr(debate_state, 'bear_history', "")
                            elif isinstance(debate_state, dict) and 'bear_history' in debate_state:
                                bear_content = debate_state['bear_history']
                            else:
                                bear_content = ""

                            if bear_content and len(bear_content.strip()) > 10:
                                reports['bear_researcher'] = bear_content.strip()

                            # 提取研究经理决策
                            if hasattr(debate_state, 'judge_decision'):
                                decision_content = getattr(debate_state, 'judge_decision', "")
                            elif isinstance(debate_state, dict) and 'judge_decision' in debate_state:
                                decision_content = debate_state['judge_decision']
                            else:
                                decision_content = str(debate_state)

                            if decision_content and len(decision_content.strip()) > 10:
                                reports['research_team_decision'] = decision_content.strip()

                    # 处理风险管理团队辩论状态报告
                    if hasattr(state, 'risk_debate_state') or (isinstance(state, dict) and 'risk_debate_state' in state):
                        risk_state = getattr(state, 'risk_debate_state', None) if hasattr(state, 'risk_debate_state') else state.get('risk_debate_state')
                        if risk_state:
                            # 提取激进分析师历史
                            if hasattr(risk_state, 'risky_history'):
                                risky_content = getattr(risk_state, 'risky_history', "")
                            elif isinstance(risk_state, dict) and 'risky_history' in risk_state:
                                risky_content = risk_state['risky_history']
                            else:
                                risky_content = ""

                            if risky_content and len(risky_content.strip()) > 10:
                                reports['risky_analyst'] = risky_content.strip()

                            # 提取保守分析师历史
                            if hasattr(risk_state, 'safe_history'):
                                safe_content = getattr(risk_state, 'safe_history', "")
                            elif isinstance(risk_state, dict) and 'safe_history' in risk_state:
                                safe_content = risk_state['safe_history']
                            else:
                                safe_content = ""

                            if safe_content and len(safe_content.strip()) > 10:
                                reports['safe_analyst'] = safe_content.strip()

                            # 提取中性分析师历史
                            if hasattr(risk_state, 'neutral_history'):
                                neutral_content = getattr(risk_state, 'neutral_history', "")
                            elif isinstance(risk_state, dict) and 'neutral_history' in risk_state:
                                neutral_content = risk_state['neutral_history']
                            else:
                                neutral_content = ""

                            if neutral_content and len(neutral_content.strip()) > 10:
                                reports['neutral_analyst'] = neutral_content.strip()

                            # 提取投资组合经理决策
                            if hasattr(risk_state, 'judge_decision'):
                                risk_decision = getattr(risk_state, 'judge_decision', "")
                            elif isinstance(risk_state, dict) and 'judge_decision' in risk_state:
                                risk_decision = risk_state['judge_decision']
                            else:
                                risk_decision = str(risk_state)

                            if risk_decision and len(risk_decision.strip()) > 10:
                                reports['risk_management_decision'] = risk_decision.strip()

                    logger.info(f"📊 从state中提取到 {len(reports)} 个报告: {list(reports.keys())}")

                except Exception as e:
                    logger.warning(f"⚠️ 处理state中的reports时出错: {e}")
                    # 降级到从detailed_analysis提取
                    if 'detailed_analysis' in result:
                        try:
                            detailed_analysis = result['detailed_analysis']
                            if isinstance(detailed_analysis, dict):
                                for key, value in detailed_analysis.items():
                                    if isinstance(value, str) and len(value) > 50:
                                        reports[key] = value
                                logger.info(f"📊 降级：从detailed_analysis中提取到 {len(reports)} 个报告")
                        except Exception as fallback_error:
                            logger.warning(f"⚠️ 降级提取也失败: {fallback_error}")

            # 🔥 根据股票代码推断市场类型
            from tradingagents.utils.stock_utils import StockUtils
            market_info = StockUtils.get_market_info(stock_symbol)
            market_type_map = {
                "china_a": "A股",
                "hong_kong": "港股",
                "us": "美股",
                "unknown": "A股"  # 默认为A股
            }
            market_type = market_type_map.get(market_info.get("market", "unknown"), "A股")
            logger.info(f"📊 推断市场类型: {stock_symbol} -> {market_type}")

            # 🔥 获取股票名称
            stock_name = stock_symbol  # 默认使用股票代码
            try:
                if market_info.get("market") == "china_a":
                    # A股：使用统一接口获取股票信息
                    from tradingagents.dataflows.interface import get_china_stock_info_unified
                    stock_info = get_china_stock_info_unified(stock_symbol)
                    logger.debug(f"📊 获取股票信息返回: {stock_info[:200] if stock_info else 'None'}...")

                    if stock_info and "股票名称:" in stock_info:
                        stock_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                        logger.info(f"✅ 获取A股名称: {stock_symbol} -> {stock_name}")
                    else:
                        # 降级方案：尝试直接从数据源管理器获取
                        logger.warning(f"⚠️ 无法从统一接口解析股票名称: {stock_symbol}，尝试降级方案")
                        try:
                            from tradingagents.dataflows.data_source_manager import get_china_stock_info_unified as get_info_dict
                            info_dict = get_info_dict(stock_symbol)
                            if info_dict and info_dict.get('name'):
                                stock_name = info_dict['name']
                                logger.info(f"✅ 降级方案成功获取股票名称: {stock_symbol} -> {stock_name}")
                        except Exception as fallback_e:
                            logger.error(f"❌ 降级方案也失败: {fallback_e}")

                elif market_info.get("market") == "hong_kong":
                    # 港股：使用改进的港股工具
                    try:
                        from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                        stock_name = get_hk_company_name_improved(stock_symbol)
                        logger.info(f"📊 获取港股名称: {stock_symbol} -> {stock_name}")
                    except Exception:
                        clean_ticker = stock_symbol.replace('.HK', '').replace('.hk', '')
                        stock_name = f"港股{clean_ticker}"
                elif market_info.get("market") == "us":
                    # 美股：使用简单映射
                    us_stock_names = {
                        'AAPL': '苹果公司', 'TSLA': '特斯拉', 'NVDA': '英伟达',
                        'MSFT': '微软', 'GOOGL': '谷歌', 'AMZN': '亚马逊',
                        'META': 'Meta', 'NFLX': '奈飞'
                    }
                    stock_name = us_stock_names.get(stock_symbol.upper(), f"美股{stock_symbol}")
                    logger.info(f"📊 获取美股名称: {stock_symbol} -> {stock_name}")
            except Exception as e:
                logger.warning(f"⚠️ 获取股票名称失败: {stock_symbol} - {e}")
                stock_name = stock_symbol

            # 构建文档（与web目录的MongoDBReportManager保持一致）
            document = {
                "analysis_id": analysis_id,
                "stock_symbol": stock_symbol,
                "stock_name": stock_name,  # 🔥 添加股票名称字段
                "market_type": market_type,  # 🔥 添加市场类型字段
                "model_info": result.get("model_info", "Unknown"),  # 🔥 添加模型信息字段
                "analysis_date": timestamp.strftime('%Y-%m-%d'),
                "timestamp": timestamp,
                "status": "completed",
                "source": "api",

                # 分析结果摘要
                "summary": result.get("summary", ""),
                "analysts": result.get("analysts", []),
                "research_depth": result.get("research_depth", 1),

                # 报告内容
                "reports": reports,

                # 🔥 关键修复：添加格式化后的decision字段！
                "decision": result.get("decision", {}),

                # 元数据
                "created_at": timestamp,
                "updated_at": timestamp,

                # API特有字段
                "task_id": task_id,
                "recommendation": result.get("recommendation", ""),
                "confidence_score": result.get("confidence_score", 0.0),
                "risk_level": result.get("risk_level", "中等"),
                "key_points": result.get("key_points", []),
                "execution_time": result.get("execution_time", 0),
                "tokens_used": result.get("tokens_used", 0),

                # 🆕 性能指标数据
                "performance_metrics": result.get("performance_metrics", {})
            }

            # 保存到analysis_reports集合（与web目录保持一致）
            result_insert = await db.analysis_reports.insert_one(document)

            if result_insert.inserted_id:
                logger.info(f"✅ 分析报告已保存到MongoDB analysis_reports: {analysis_id}")

                # 同时更新analysis_tasks集合中的result字段，保持API兼容性
                await db.analysis_tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {"result": {
                        "analysis_id": analysis_id,
                        "stock_symbol": stock_symbol,
                        "stock_code": result.get('stock_code', stock_symbol),
                        "analysis_date": result.get('analysis_date'),
                        "summary": result.get("summary", ""),
                        "recommendation": result.get("recommendation", ""),
                        "confidence_score": result.get("confidence_score", 0.0),
                        "risk_level": result.get("risk_level", "中等"),
                        "key_points": result.get("key_points", []),
                        "detailed_analysis": result.get("detailed_analysis", {}),
                        "execution_time": result.get("execution_time", 0),
                        "tokens_used": result.get("tokens_used", 0),
                        "reports": reports,  # 包含提取的报告内容
                        # 🔥 关键修复：添加格式化后的decision字段！
                        "decision": result.get("decision", {})
                    }}}
                )
                logger.info(f"💾 分析结果已保存 (web风格): {task_id}")
            else:
                logger.error("❌ MongoDB插入失败")

        except Exception as e:
            logger.error(f"❌ 保存分析结果失败: {task_id} - {e}")
            # 降级到简单保存
            try:
                simple_result = {
                    'task_id': task_id,
                    'success': result.get('success', True),
                    'error': str(e),
                    'completed_at': datetime.utcnow().isoformat()
                }
                await db.analysis_tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {"result": simple_result}}
                )
                logger.info(f"💾 使用简化结果保存: {task_id}")
            except Exception as fallback_error:
                logger.error(f"❌ 简化保存也失败: {task_id} - {fallback_error}")

    async def _save_analysis_results_complete(self, task_id: str, result: Dict[str, Any]):
        """完整的分析结果保存 - 完全采用web目录的双重保存方式"""
        try:
            # 调试：打印result中的所有键
            logger.info(f"🔍 [调试] result中的所有键: {list(result.keys())}")
            logger.info(f"🔍 [调试] stock_code: {result.get('stock_code', 'NOT_FOUND')}")
            logger.info(f"🔍 [调试] stock_symbol: {result.get('stock_symbol', 'NOT_FOUND')}")

            # 优先使用stock_symbol，如果没有则使用stock_code
            stock_symbol = result.get('stock_symbol') or result.get('stock_code', 'UNKNOWN')
            logger.info(f"💾 开始完整保存分析结果: {stock_symbol}")

            # 1. 保存分模块报告到本地目录
            logger.info(f"📁 [本地保存] 开始保存分模块报告到本地目录")
            local_files = await self._save_modular_reports_to_data_dir(result, stock_symbol)
            if local_files:
                logger.info(f"✅ [本地保存] 已保存 {len(local_files)} 个本地报告文件")
                for module, path in local_files.items():
                    logger.info(f"  - {module}: {path}")
            else:
                logger.warning(f"⚠️ [本地保存] 本地报告文件保存失败")

            # 2. 保存分析报告到数据库
            logger.info(f"🗄️ [数据库保存] 开始保存分析报告到数据库")
            await self._save_analysis_result_web_style(task_id, result)
            logger.info(f"✅ [数据库保存] 分析报告已成功保存到数据库")

            # 3. 记录保存结果
            if local_files:
                logger.info(f"✅ 分析报告已保存到数据库和本地文件")
            else:
                logger.warning(f"⚠️ 数据库保存成功，但本地文件保存失败")

        except Exception as save_error:
            logger.error(f"❌ [完整保存] 保存分析报告时发生错误: {str(save_error)}")
            # 降级到仅数据库保存
            try:
                await self._save_analysis_result_web_style(task_id, result)
                logger.info(f"💾 降级保存成功 (仅数据库): {task_id}")
            except Exception as fallback_error:
                logger.error(f"❌ 降级保存也失败: {task_id} - {fallback_error}")

    async def _save_modular_reports_to_data_dir(self, result: Dict[str, Any], stock_symbol: str) -> Dict[str, str]:
        """保存分模块报告到data目录 - 完全采用web目录的文件结构"""
        try:
            import os
            from pathlib import Path
            from datetime import datetime
            import json

            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent

            # 确定results目录路径 - 与web目录保持一致
            results_dir_env = os.getenv("TRADINGAGENTS_RESULTS_DIR")
            if results_dir_env:
                if not os.path.isabs(results_dir_env):
                    results_dir = project_root / results_dir_env
                else:
                    results_dir = Path(results_dir_env)
            else:
                # 默认使用data目录而不是results目录
                results_dir = project_root / "data" / "analysis_results"

            # 创建股票专用目录 - 完全按照web目录的结构
            analysis_date_raw = result.get('analysis_date', datetime.now())

            # 确保 analysis_date 是字符串格式
            if isinstance(analysis_date_raw, datetime):
                analysis_date_str = analysis_date_raw.strftime('%Y-%m-%d')
            elif isinstance(analysis_date_raw, str):
                # 如果已经是字符串，检查格式
                try:
                    # 尝试解析日期字符串，确保格式正确
                    parsed_date = datetime.strptime(analysis_date_raw, '%Y-%m-%d')
                    analysis_date_str = analysis_date_raw
                except ValueError:
                    # 如果格式不正确，使用当前日期
                    analysis_date_str = datetime.now().strftime('%Y-%m-%d')
            else:
                # 其他类型，使用当前日期
                analysis_date_str = datetime.now().strftime('%Y-%m-%d')

            stock_dir = results_dir / stock_symbol / analysis_date_str
            reports_dir = stock_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            # 创建message_tool.log文件 - 与web目录保持一致
            log_file = stock_dir / "message_tool.log"
            log_file.touch(exist_ok=True)

            logger.info(f"📁 创建分析结果目录: {reports_dir}")
            logger.info(f"🔍 [调试] analysis_date_raw 类型: {type(analysis_date_raw)}, 值: {analysis_date_raw}")
            logger.info(f"🔍 [调试] analysis_date_str: {analysis_date_str}")
            logger.info(f"🔍 [调试] 完整路径: {os.path.normpath(str(reports_dir))}")

            state = result.get('state', {})
            saved_files = {}

            # 定义报告模块映射 - 完全按照web目录的定义
            report_modules = {
                'market_report': {
                    'filename': 'market_report.md',
                    'title': f'{stock_symbol} 股票技术分析报告',
                    'state_key': 'market_report'
                },
                'sentiment_report': {
                    'filename': 'sentiment_report.md',
                    'title': f'{stock_symbol} 市场情绪分析报告',
                    'state_key': 'sentiment_report'
                },
                'news_report': {
                    'filename': 'news_report.md',
                    'title': f'{stock_symbol} 新闻事件分析报告',
                    'state_key': 'news_report'
                },
                'fundamentals_report': {
                    'filename': 'fundamentals_report.md',
                    'title': f'{stock_symbol} 基本面分析报告',
                    'state_key': 'fundamentals_report'
                },
                'investment_plan': {
                    'filename': 'investment_plan.md',
                    'title': f'{stock_symbol} 投资决策报告',
                    'state_key': 'investment_plan'
                },
                'trader_investment_plan': {
                    'filename': 'trader_investment_plan.md',
                    'title': f'{stock_symbol} 交易计划报告',
                    'state_key': 'trader_investment_plan'
                },
                'final_trade_decision': {
                    'filename': 'final_trade_decision.md',
                    'title': f'{stock_symbol} 最终投资决策',
                    'state_key': 'final_trade_decision'
                },
                'investment_debate_state': {
                    'filename': 'research_team_decision.md',
                    'title': f'{stock_symbol} 研究团队决策报告',
                    'state_key': 'investment_debate_state'
                },
                'risk_debate_state': {
                    'filename': 'risk_management_decision.md',
                    'title': f'{stock_symbol} 风险管理团队决策报告',
                    'state_key': 'risk_debate_state'
                }
            }

            # 保存各模块报告 - 完全按照web目录的方式
            for module_key, module_info in report_modules.items():
                try:
                    state_key = module_info['state_key']
                    if state_key in state:
                        # 提取模块内容
                        module_content = state[state_key]
                        if isinstance(module_content, str):
                            report_content = module_content
                        else:
                            report_content = str(module_content)

                        # 保存到文件 - 使用web目录的文件名
                        file_path = reports_dir / module_info['filename']
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(report_content)

                        saved_files[module_key] = str(file_path)
                        logger.info(f"✅ 保存模块报告: {file_path}")

                except Exception as e:
                    logger.warning(f"⚠️ 保存模块 {module_key} 失败: {e}")

            # 保存最终决策报告 - 完全按照web目录的方式
            decision = result.get('decision', {})
            if decision:
                decision_content = f"# {stock_symbol} 最终投资决策\n\n"

                if isinstance(decision, dict):
                    decision_content += f"## 投资建议\n\n"
                    decision_content += f"**行动**: {decision.get('action', 'N/A')}\n\n"
                    decision_content += f"**置信度**: {decision.get('confidence', 0):.1%}\n\n"
                    decision_content += f"**风险评分**: {decision.get('risk_score', 0):.1%}\n\n"
                    decision_content += f"**目标价位**: {decision.get('target_price', 'N/A')}\n\n"
                    decision_content += f"## 分析推理\n\n{decision.get('reasoning', '暂无分析推理')}\n\n"
                else:
                    decision_content += f"{str(decision)}\n\n"

                decision_file = reports_dir / "final_trade_decision.md"
                with open(decision_file, 'w', encoding='utf-8') as f:
                    f.write(decision_content)

                saved_files['final_trade_decision'] = str(decision_file)
                logger.info(f"✅ 保存最终决策: {decision_file}")

            # 保存分析元数据文件 - 完全按照web目录的方式
            metadata = {
                'stock_symbol': stock_symbol,
                'analysis_date': analysis_date_str,
                'timestamp': datetime.now().isoformat(),
                'research_depth': result.get('research_depth', 1),
                'analysts': result.get('analysts', []),
                'status': 'completed',
                'reports_count': len(saved_files),
                'report_types': list(saved_files.keys())
            }

            metadata_file = reports_dir.parent / "analysis_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 保存分析元数据: {metadata_file}")
            logger.info(f"✅ 分模块报告保存完成，共保存 {len(saved_files)} 个文件")
            logger.info(f"📁 保存目录: {os.path.normpath(str(reports_dir))}")

            return saved_files

        except Exception as e:
            logger.error(f"❌ 保存分模块报告失败: {e}")
            import traceback
            logger.error(f"❌ 详细错误: {traceback.format_exc()}")
            return {}

# 重复的 get_task_status 方法已删除，使用第469行的内存版本


# 全局服务实例
_analysis_service = None

def get_simple_analysis_service() -> SimpleAnalysisService:
    """获取分析服务实例"""
    global _analysis_service
    if _analysis_service is None:
        logger.info("🔧 [单例] 创建新的 SimpleAnalysisService 实例")
        _analysis_service = SimpleAnalysisService()
    else:
        logger.info(f"🔧 [单例] 返回现有的 SimpleAnalysisService 实例: {id(_analysis_service)}")
    return _analysis_service
