"""
股票分析服务
整合了原 simple_analysis_service.py 和 analysis_service.py 的功能
"""

import asyncio
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import sys
import concurrent.futures
import os

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 初始化TradingAgents日志系统
from tradingagents.utils.logging_init import init_logging
init_logging()

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.utils.runtime_paths import get_analysis_results_dir, resolve_path
from tradingagents.dataflows.data_source_manager import get_data_source_manager

from app.models.analysis import (
    AnalysisParameters, AnalysisResult, AnalysisTask, AnalysisBatch,
    AnalysisStatus, BatchStatus, SingleAnalysisRequest, BatchAnalysisRequest
)
from app.models.user import PyObjectId
from app.models.notification import NotificationCreate
from bson import ObjectId
from app.core.database import get_mongo_db, get_redis_client
from app.core.redis_client import get_redis_service, RedisKeys
from app.services.queue_service import QueueService
from app.services.usage_statistics_service import UsageStatisticsService
from app.services.redis_progress_tracker import RedisProgressTracker, get_progress_by_id
from app.services.config_service import ConfigService
from app.services.config_provider import provider as config_provider
from app.services.memory_state_manager import get_memory_state_manager, TaskStatus
from app.services.progress_log_handler import register_analysis_tracker, unregister_analysis_tracker
from app.services.websocket_manager import get_websocket_manager
from app.core.config import settings
from app.services.queue import DEFAULT_USER_CONCURRENT_LIMIT, GLOBAL_CONCURRENT_LIMIT, VISIBILITY_TIMEOUT_SECONDS

# 设置日志
logger = logging.getLogger("app.services.analysis_service")

# 配置服务实例
config_service = ConfigService()

# 股票基础信息获取（用于补充显示名称）
try:
    _data_source_manager = get_data_source_manager()
    def _get_stock_info_safe(stock_code: str):
        """获取股票基础信息的安全封装"""
        return _data_source_manager.get_stock_basic_info(stock_code)
except Exception:
    _get_stock_info_safe = None

# -----------------------------------------------------------------------------
# Helper Functions (from simple_analysis_service.py)
# -----------------------------------------------------------------------------

async def get_provider_by_model_name(model_name: str) -> str:
    """
    根据模型名称从数据库配置中查找对应的供应商（异步版本）
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
    """
    provider_info = get_provider_and_url_by_model_sync(model_name)
    return provider_info["provider"]


def get_provider_and_url_by_model_sync(model_name: str) -> dict:
    """
    根据模型名称从数据库配置中查找对应的供应商和 API URL（同步版本）
    """
    try:
        # 使用同步 MongoDB 客户端直接查询
        from pymongo import MongoClient
        
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

                    client.close()
                    return {
                        "provider": provider,
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

            client.close()
            return {
                "provider": provider,
                "backend_url": backend_url,
                "api_key": api_key
            }
        except Exception as e:
            logger.warning(f"⚠️ [同步查询] 无法查询厂家配置: {e}")

        # 最后回退到硬编码的默认 URL 和环境变量 API Key
        return {
            "provider": provider,
            "backend_url": _get_default_backend_url(provider),
            "api_key": _get_env_api_key_for_provider(provider)
        }

    except Exception as e:
        logger.error(f"❌ [同步查询] 查找模型供应商失败: {e}")
        provider = _get_default_provider_by_model(model_name)
        return {
            "provider": provider,
            "backend_url": _get_default_backend_url(provider),
            "api_key": _get_env_api_key_for_provider(provider)
        }


def _get_env_api_key_for_provider(provider: str) -> str:
    """从环境变量获取指定供应商的 API Key"""
    env_key_map = {
        "google": "GOOGLE_API_KEY",
        "dashscope": "DASHSCOPE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "siliconflow": "SILICONFLOW_API_KEY",
        "qianfan": "QIANFAN_API_KEY",
        "302ai": "AI302_API_KEY",
    }

    env_key_name = env_key_map.get(provider.lower())
    if env_key_name:
        api_key = os.getenv(env_key_name)
        if api_key and api_key.strip() and api_key != "your-api-key":
            return api_key

    return None


def _get_default_backend_url(provider: str) -> str:
    """根据供应商名称返回默认的 backend_url"""
    default_urls = {
        "google": "https://generativelanguage.googleapis.com/v1beta",
        "dashscope": "https://dashscope.aliyuncs.com/api/v1",
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com",
        "anthropic": "https://api.anthropic.com",
        "openrouter": "https://openrouter.ai/api/v1",
        "qianfan": "https://qianfan.baidubce.com/v2",
        "302ai": "https://api.302.ai/v1",
    }

    url = default_urls.get(provider, "https://dashscope.aliyuncs.com/compatible-mode/v1")
    return url


def _get_default_provider_by_model(model_name: str) -> str:
    """根据模型名称返回默认的供应商映射"""
    model_provider_map = {
        'qwen-turbo': 'dashscope',
        'qwen-plus': 'dashscope',
        'qwen-max': 'dashscope',
        'qwen-plus-latest': 'dashscope',
        'qwen-max-longcontext': 'dashscope',
        'gpt-3.5-turbo': 'openai',
        'gpt-4': 'openai',
        'gpt-4-turbo': 'openai',
        'gpt-4o': 'openai',
        'gpt-4o-mini': 'openai',
        'gemini-pro': 'google',
        'gemini-2.0-flash': 'google',
        'gemini-2.0-flash-thinking-exp': 'google',
        'deepseek-chat': 'deepseek',
        'deepseek-coder': 'deepseek',
        'glm-4': 'zhipu',
        'glm-3-turbo': 'zhipu',
        'chatglm3-6b': 'zhipu'
    }
    provider = model_provider_map.get(model_name, 'dashscope')
    return provider


def create_analysis_config(
    research_depth,
    selected_analysts: list,
    quick_model: str,
    deep_model: str,
    llm_provider: str,
    market_type: str = "A股",
    quick_model_config: dict = None,
    deep_model_config: dict = None
) -> dict:
    """创建分析配置"""
    
    numeric_to_chinese = {
        1: "快速", 2: "基础", 3: "标准", 4: "深度", 5: "全面"
    }

    # 标准化研究深度
    if isinstance(research_depth, (int, float)):
        research_depth = int(research_depth)
        if research_depth in numeric_to_chinese:
            research_depth = numeric_to_chinese[research_depth]
        else:
            research_depth = "标准"
    elif isinstance(research_depth, str):
        if research_depth.isdigit():
            numeric_level = int(research_depth)
            if numeric_level in numeric_to_chinese:
                research_depth = numeric_to_chinese[numeric_level]
            else:
                research_depth = "标准"
        elif research_depth not in ["快速", "基础", "标准", "深度", "全面"]:
            research_depth = "标准"
    else:
        research_depth = "标准"

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = llm_provider
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = quick_model

    if research_depth == "快速":
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = False
        config["online_tools"] = True
    elif research_depth == "基础":
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = True
        config["online_tools"] = True
    elif research_depth == "标准":
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True
    elif research_depth == "深度":
        config["max_debate_rounds"] = 2
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True
    elif research_depth == "全面":
        config["max_debate_rounds"] = 3
        config["max_risk_discuss_rounds"] = 3
        config["memory_enabled"] = True
        config["online_tools"] = True
    else:
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True

    try:
        quick_provider_info = get_provider_and_url_by_model_sync(quick_model)
        deep_provider_info = get_provider_and_url_by_model_sync(deep_model)

        config["backend_url"] = quick_provider_info["backend_url"]
        config["quick_api_key"] = quick_provider_info.get("api_key")
        config["deep_api_key"] = deep_provider_info.get("api_key")
    except Exception as e:
        logger.warning(f"⚠️  无法从数据库获取 backend_url 和 API Key: {e}")
        config["backend_url"] = _get_default_backend_url(llm_provider)

    config["selected_analysts"] = selected_analysts
    config["debug"] = False
    config["research_depth"] = research_depth

    if quick_model_config:
        config["quick_model_config"] = quick_model_config
    if deep_model_config:
        config["deep_model_config"] = deep_model_config

    return config


# -----------------------------------------------------------------------------
# AnalysisService Class
# -----------------------------------------------------------------------------

class AnalysisService:
    """股票分析服务类 - 整合版"""

    def __init__(self):
        # 初始化组件
        self._trading_graph_cache = {}
        self.memory_manager = get_memory_state_manager()
        self._progress_trackers: Dict[str, RedisProgressTracker] = {}
        self._stock_name_cache: Dict[str, str] = {}

        # 线程池
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        logger.info(f"🔧 [服务初始化] 线程池最大并发数: 3")

        # 队列和统计服务 (从原AnalysisService合并)
        try:
            redis_client = get_redis_client()
            self.queue_service = QueueService(redis_client)
            self.usage_service = UsageStatisticsService()
        except Exception as e:
            logger.warning(f"⚠️ 队列或统计服务初始化失败: {e}")

        # 设置 WebSocket 管理器
        try:
            self.memory_manager.set_websocket_manager(get_websocket_manager())
        except ImportError:
            logger.warning("⚠️ WebSocket 管理器不可用")

        logger.info(f"🔧 [服务初始化] AnalysisService 实例ID: {id(self)}")

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    async def _update_progress_async(self, task_id: str, progress: int, message: str):
        """异步更新进度（内存和MongoDB）"""
        try:
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=progress,
                message=message,
                current_step=message
            )
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
        except Exception as e:
            logger.warning(f"⚠️ [异步更新] 失败: {e}")

    def _resolve_stock_name(self, code: Optional[str]) -> str:
        """解析股票名称（带缓存）"""
        if not code:
            return ""
        if code in self._stock_name_cache:
            return self._stock_name_cache[code]
        name = None
        try:
            if _get_stock_info_safe:
                info = _get_stock_info_safe(code)
                if isinstance(info, dict):
                    name = info.get("name")
        except Exception:
            pass
        if not name:
            name = f"股票{code}"
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
            if user_id == "admin":
                return PyObjectId(ObjectId("507f1f77bcf86cd799439011"))
            return PyObjectId(ObjectId(user_id))
        except Exception:
            return PyObjectId(ObjectId())

    def _get_trading_graph(self, config: Dict[str, Any]) -> TradingAgentsGraph:
        """获取或创建TradingAgents实例 (每次创建新实例以保证线程安全)"""
        return TradingAgentsGraph(
            selected_analysts=config.get("selected_analysts", ["market", "fundamentals"]),
            debug=config.get("debug", False),
            config=config
        )

    # -------------------------------------------------------------------------
    # Main Analysis Methods (Core Logic from simple_analysis_service.py)
    # -------------------------------------------------------------------------

    async def create_analysis_task(
        self,
        user_id: str,
        request: SingleAnalysisRequest
    ) -> Dict[str, Any]:
        """创建分析任务（立即返回，不执行分析）"""
        try:
            task_id = str(uuid.uuid4())
            stock_code = request.get_symbol()
            if not stock_code:
                raise ValueError("股票代码不能为空")

            logger.info(f"📝 创建分析任务: {task_id} - {stock_code}")

            # 在内存中创建任务状态
            await self.memory_manager.create_task(
                task_id=task_id,
                user_id=user_id,
                stock_code=stock_code,
                parameters=request.parameters.model_dump() if request.parameters else {},
                stock_name=self._resolve_stock_name(stock_code),
            )

            # 写入MongoDB
            code = stock_code
            name = self._resolve_stock_name(code)
            try:
                db = get_mongo_db()
                await db.analysis_tasks.update_one(
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
            except Exception as e:
                logger.error(f"❌ 创建任务时写入MongoDB失败: {e}")

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
        """在后台执行分析任务 (Core Logic)"""
        stock_code = request.get_symbol()
        progress_tracker = None
        try:
            logger.info(f"🚀 开始后台执行分析任务: {task_id}")

            # 验证股票代码
            from tradingagents.utils.stock_validator import prepare_stock_data_async
            market_type = request.parameters.market_type if request.parameters else "A股"
            analysis_date = request.parameters.analysis_date if request.parameters else None
            
            if analysis_date and isinstance(analysis_date, datetime):
                analysis_date = analysis_date.strftime('%Y-%m-%d')
            elif analysis_date and isinstance(analysis_date, str):
                try:
                    parsed_date = datetime.strptime(analysis_date, '%Y-%m-%d')
                    analysis_date = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    analysis_date = datetime.now().strftime('%Y-%m-%d')

            validation_result = await prepare_stock_data_async(
                stock_code=stock_code,
                market_type=market_type,
                period_days=30,
                analysis_date=analysis_date
            )

            if not validation_result.is_valid:
                error_msg = f"❌ 股票代码无效: {validation_result.error_message}"
                await self.memory_manager.update_task_status(
                    task_id=task_id, status=AnalysisStatus.FAILED, progress=0, error_message=error_msg
                )
                await self._update_task_status(task_id, AnalysisStatus.FAILED, 0, error_message=error_msg)
                return

            # 创建Redis进度跟踪器
            def create_progress_tracker():
                return RedisProgressTracker(
                    task_id=task_id,
                    analysts=request.parameters.selected_analysts or ["market", "fundamentals"],
                    research_depth=request.parameters.research_depth or "标准",
                    llm_provider="dashscope"
                )

            progress_tracker = await asyncio.to_thread(create_progress_tracker)
            self._progress_trackers[task_id] = progress_tracker
            register_analysis_tracker(task_id, progress_tracker)

            # 更新初始状态
            await asyncio.to_thread(progress_tracker.update_progress, {"progress_percentage": 10, "last_message": "🚀 开始股票分析"})
            await self.memory_manager.update_task_status(
                task_id=task_id, status=TaskStatus.RUNNING, progress=10, message="分析开始...", current_step="initialization"
            )
            await self._update_task_status(task_id, AnalysisStatus.PROCESSING, 10)

            # 执行实际分析
            result = await self._execute_analysis_sync(task_id, user_id, request, progress_tracker)

            # 完成
            await asyncio.to_thread(progress_tracker.mark_completed)
            
            # 保存结果
            await self._save_analysis_results_complete(task_id, result)

            # 更新完成状态
            await self.memory_manager.update_task_status(
                task_id=task_id, status=TaskStatus.COMPLETED, progress=100, message="分析完成", current_step="completed", result_data=result
            )
            await self._update_task_status(task_id, AnalysisStatus.COMPLETED, 100)

            # 发送通知
            try:
                from app.services.notifications_service import get_notifications_service
                svc = get_notifications_service()
                summary = str(result.get("summary", ""))[:120]
                await svc.create_and_publish(
                    payload=NotificationCreate(
                        user_id=str(user_id), type='analysis', title=f"{stock_code} 分析完成",
                        content=summary, link=f"/stocks/{stock_code}", source='analysis'
                    )
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"❌ 后台分析任务失败: {task_id} - {e}")
            if progress_tracker:
                progress_tracker.mark_failed(str(e))
            await self.memory_manager.update_task_status(
                task_id=task_id, status=TaskStatus.FAILED, progress=0, message="分析失败", error_message=str(e)
            )
            await self._update_task_status(task_id, AnalysisStatus.FAILED, 0, str(e))
        finally:
            if task_id in self._progress_trackers:
                del self._progress_trackers[task_id]
            unregister_analysis_tracker(task_id)

    # -------------------------------------------------------------------------
    # Compatibility Methods (for API Router)
    # -------------------------------------------------------------------------

    async def submit_single_analysis(self, user_id: str, request: SingleAnalysisRequest) -> Dict[str, Any]:
        """
        提交单股分析任务 (兼容旧 AnalysisService 接口)
        注意：这个方法现在只是 create_analysis_task 的别名，
        实际执行需要在调用处通过 BackgroundTasks 或其他方式触发 execute_analysis_background
        """
        return await self.create_analysis_task(user_id, request)

    async def submit_batch_analysis(self, user_id: str, request: BatchAnalysisRequest) -> Dict[str, Any]:
        """提交批量分析任务 (保留原功能)"""
        try:
            batch_id = str(uuid.uuid4())
            converted_user_id = self._convert_user_id(user_id)
            
            # 读取配置
            effective_settings = await config_provider.get_effective_system_settings()
            params = request.parameters or AnalysisParameters()
            
            if not getattr(params, 'quick_analysis_model', None):
                params.quick_analysis_model = effective_settings.get("quick_analysis_model", "qwen-turbo")
            if not getattr(params, 'deep_analysis_model', None):
                params.deep_analysis_model = effective_settings.get("deep_analysis_model", "qwen-max")

            stock_symbols = request.get_symbols()
            
            batch = AnalysisBatch(
                batch_id=batch_id,
                user_id=converted_user_id,
                title=request.title,
                description=request.description,
                total_tasks=len(stock_symbols),
                parameters=params,
                status=BatchStatus.PENDING
            )

            tasks = []
            for symbol in stock_symbols:
                task_id = str(uuid.uuid4())
                task = AnalysisTask(
                    task_id=task_id,
                    batch_id=batch_id,
                    user_id=converted_user_id,
                    symbol=symbol,
                    stock_code=symbol,
                    parameters=batch.parameters,
                    status=AnalysisStatus.PENDING
                )
                tasks.append(task)
            
            db = get_mongo_db()
            await db.analysis_batches.insert_one(batch.dict(by_alias=True))
            await db.analysis_tasks.insert_many([task.dict(by_alias=True) for task in tasks])
            
            for task in tasks:
                queue_params = task.parameters.dict() if task.parameters else {}
                queue_params.update({
                    "task_id": task.task_id,
                    "symbol": task.symbol,
                    "stock_code": task.symbol,
                    "user_id": str(task.user_id),
                    "batch_id": task.batch_id,
                    "created_at": task.created_at.isoformat() if task.created_at else None
                })
                await self.queue_service.enqueue_task(
                    user_id=str(converted_user_id),
                    symbol=task.symbol,
                    params=queue_params,
                    batch_id=task.batch_id
                )
            
            return {
                "batch_id": batch_id,
                "total_tasks": len(tasks),
                "status": BatchStatus.PENDING,
                "message": f"已提交{len(tasks)}个分析任务到队列"
            }
        except Exception as e:
            logger.error(f"提交批量分析任务失败: {e}")
            raise

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            await self._update_task_status(task_id, AnalysisStatus.CANCELLED, 0)
            await self.queue_service.remove_task(task_id)
            return True
        except Exception as e:
            logger.error(f"取消任务失败: {task_id} - {e}")
            return False

    # -------------------------------------------------------------------------
    # Internal Execution Logic (from simple_analysis_service.py)
    # -------------------------------------------------------------------------

    async def _execute_analysis_sync(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest,
        progress_tracker: Optional[RedisProgressTracker] = None
    ) -> Dict[str, Any]:
        """同步执行分析（在共享线程池中运行）"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._thread_pool,
            self._run_analysis_sync,
            task_id,
            user_id,
            request,
            progress_tracker
        )
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
            from tradingagents.utils.logging_init import init_logging, get_logger
            init_logging()
            
            # 进度更新回调
            def update_progress_sync(progress: int, message: str, step: str):
                try:
                    if progress_tracker:
                        progress_tracker.update_progress({"progress_percentage": progress, "last_message": message})
                    
                    # 更新内存和MongoDB
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            self.memory_manager.update_task_status(
                                task_id=task_id, status=TaskStatus.RUNNING, progress=progress, message=message, current_step=step
                            )
                        )
                    finally:
                        loop.close()
                        
                    from pymongo import MongoClient
                    sync_client = MongoClient(settings.MONGO_URI)
                    sync_db = sync_client[settings.MONGO_DB]
                    sync_db.analysis_tasks.update_one(
                        {"task_id": task_id},
                        {"$set": {"progress": progress, "current_step": step, "message": message, "updated_at": datetime.utcnow()}}
                    )
                    sync_client.close()
                except Exception:
                    pass

            update_progress_sync(7, "⚙️ 配置分析参数", "configuration")

            # 模型选择逻辑
            from app.services.model_capability_service import get_model_capability_service
            capability_service = get_model_capability_service()
            research_depth = request.parameters.research_depth if request.parameters else "标准"

            if (request.parameters and getattr(request.parameters, 'quick_analysis_model', None) 
                and getattr(request.parameters, 'deep_analysis_model', None)):
                quick_model = request.parameters.quick_analysis_model
                deep_model = request.parameters.deep_analysis_model
                # 验证逻辑省略，直接使用
            else:
                quick_model, deep_model = capability_service.recommend_models_for_depth(research_depth)

            quick_provider_info = get_provider_and_url_by_model_sync(quick_model)
            deep_provider_info = get_provider_and_url_by_model_sync(deep_model)
            quick_provider = quick_provider_info["provider"]
            
            market_type = request.parameters.market_type if request.parameters else "A股"
            
            config = create_analysis_config(
                research_depth=research_depth,
                selected_analysts=request.parameters.selected_analysts if request.parameters else ["market", "fundamentals"],
                quick_model=quick_model,
                deep_model=deep_model,
                llm_provider=quick_provider,
                market_type=market_type
            )
            
            # 混合模式配置
            config["quick_provider"] = quick_provider
            config["deep_provider"] = deep_provider_info["provider"]
            config["quick_backend_url"] = quick_provider_info["backend_url"]
            config["deep_backend_url"] = deep_provider_info["backend_url"]
            config["backend_url"] = quick_provider_info["backend_url"]

            update_progress_sync(9, "🚀 初始化AI分析引擎", "engine_initialization")
            trading_graph = self._get_trading_graph(config)
            
            start_time = datetime.now()
            analysis_date = datetime.now().strftime("%Y-%m-%d")
            if request.parameters and request.parameters.analysis_date:
                ad = request.parameters.analysis_date
                if isinstance(ad, datetime): analysis_date = ad.strftime("%Y-%m-%d")
                elif isinstance(ad, str): analysis_date = ad

            update_progress_sync(10, "🤖 开始多智能体协作分析", "agent_analysis")

            # 进度回调
            node_progress_map = {
                "📊 市场分析师": 27.5, "💼 基本面分析师": 45, "📰 新闻分析师": 27.5, "💬 社交媒体分析师": 27.5,
                "🐂 看涨研究员": 51.25, "🐻 看跌研究员": 57.5, "👔 研究经理": 70,
                "💼 交易员决策": 78,
                "🔥 激进风险评估": 81.75, "🛡️ 保守风险评估": 85.5, "⚖️ 中性风险评估": 89.25, "🎯 风险经理": 93,
                "📊 生成报告": 97,
            }

            def graph_progress_callback(message: str):
                try:
                    if not progress_tracker: return
                    progress_pct = node_progress_map.get(message)
                    if progress_pct is not None:
                        current_progress = progress_tracker.progress_data.get('progress_percentage', 0)
                        if int(progress_pct) > current_progress:
                            progress_tracker.update_progress({'progress_percentage': int(progress_pct), 'last_message': message})
                            # 尝试异步更新，如果不行则同步
                            try:
                                asyncio.create_task(self._update_progress_async(task_id, int(progress_pct), message))
                            except RuntimeError:
                                update_progress_sync(int(progress_pct), message, message)
                        else:
                            progress_tracker.update_progress({'last_message': message})
                    else:
                        progress_tracker.update_progress({'last_message': message})
                except Exception:
                    pass

            # 执行分析
            state, decision = trading_graph.propagate(
                request.stock_code,
                analysis_date,
                progress_callback=graph_progress_callback,
                task_id=task_id
            )

            update_progress_sync(90, "处理分析结果...", "result_processing")
            execution_time = (datetime.now() - start_time).total_seconds()

            # 构建结果 (简化版，完整版在 _save_analysis_result_web_style 中重构)
            # 这里直接返回字典
            result = {
                "stock_code": request.stock_code,
                "stock_symbol": request.stock_code,
                "analysis_date": analysis_date,
                "summary": str(decision.get("summary", ""))[:200] if isinstance(decision, dict) else "",
                "recommendation": str(decision.get("recommendation", "")) if isinstance(decision, dict) else "",
                "confidence_score": decision.get("confidence_score", 0.0) if isinstance(decision, dict) else 0.0,
                "risk_level": decision.get("risk_level", "中等") if isinstance(decision, dict) else "中等",
                "detailed_analysis": decision,
                "execution_time": execution_time,
                "state": state,
                "decision": decision,
                "model_info": decision.get('model_info', 'Unknown') if isinstance(decision, dict) else 'Unknown',
                "analysts": request.parameters.selected_analysts if request.parameters else [],
                "research_depth": request.parameters.research_depth if request.parameters else "快速",
            }
            return result

        except Exception as e:
            logger.error(f"❌ 分析执行失败: {task_id} - {e}")
            raise

    # -------------------------------------------------------------------------
    # Status & Saving Methods
    # -------------------------------------------------------------------------

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态 (包含详细进度)"""
        global_memory_manager = get_memory_state_manager()
        result = await global_memory_manager.get_task_dict(task_id)
        if result:
            redis_progress = get_progress_by_id(task_id)
            if redis_progress:
                result.update({
                    'progress': redis_progress.get('progress_percentage', result.get('progress', 0)),
                    'message': redis_progress.get('last_message', result.get('message', '')),
                    'steps': redis_progress.get('steps', [])
                })
        return result

    async def list_all_tasks(self, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """获取所有任务列表 (数据库 + 内存状态合并)"""
        # 兼容性处理：processing -> running
        if status == "processing":
            status = "running"
        
        # 构建查询条件
        query = {}
        if status:
            query["status"] = status
        
        try:
            db = get_mongo_db()
            cursor = db.analysis_tasks.find(query).sort("created_at", -1).skip(offset).limit(limit)
            db_tasks = await cursor.to_list(length=limit)
            
            results = []
            for task in db_tasks:
                if "_id" in task:
                    task["_id"] = str(task["_id"])
                
                task_id = task.get("task_id")
                if task_id:
                    memory_task = await self.memory_manager.get_task_dict(task_id)
                    if memory_task:
                        task["status"] = memory_task.get("status", task.get("status"))
                        task["progress"] = memory_task.get("progress", task.get("progress"))
                        task["message"] = memory_task.get("message", task.get("message"))
                        task["current_step"] = memory_task.get("current_step", task.get("current_step"))
                
                results.append(task)
            
            return self._enrich_stock_names(results)
            
        except Exception as e:
            logger.error(f"❌ 获取所有任务列表失败 (DB): {e}")
            status_enum = None
            if status:
                try:
                    status_enum = TaskStatus(status)
                except ValueError:
                    logger.warning(f"⚠️ 无效的任务状态过滤: {status}")
            
            tasks = await self.memory_manager.list_all_tasks(status=status_enum, limit=limit, offset=offset)
            return self._enrich_stock_names(tasks)

    async def list_user_tasks(self, user_id: str, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """获取用户任务列表 (数据库 + 内存状态合并)"""
        # 兼容性处理：processing -> running
        if status == "processing":
            status = "running"
            
        # 构建查询条件
        query = {"user_id": user_id}
        if status:
            query["status"] = status
            
        try:
            db = get_mongo_db()
            # 按创建时间倒序
            cursor = db.analysis_tasks.find(query).sort("created_at", -1).skip(offset).limit(limit)
            db_tasks = await cursor.to_list(length=limit)
            
            # 转换为前端友好的格式，并合并内存中的实时状态
            results = []
            for task in db_tasks:
                # 转换 ObjectId 等
                if "_id" in task:
                    task["_id"] = str(task["_id"])
                
                # 尝试从内存获取最新状态
                task_id = task.get("task_id")
                if task_id:
                    memory_task = await self.memory_manager.get_task_dict(task_id)
                    if memory_task:
                        # 内存中的状态通常更新（尤其是进度和消息）
                        # 我们主要关心 status, progress, message, current_step
                        task["status"] = memory_task.get("status", task.get("status"))
                        task["progress"] = memory_task.get("progress", task.get("progress"))
                        task["message"] = memory_task.get("message", task.get("message"))
                        task["current_step"] = memory_task.get("current_step", task.get("current_step"))
                
                results.append(task)
            
            # 如果数据库返回为空，可能是因为所有数据都在内存中（极少见情况，例如DB写入失败但内存成功）
            # 或者如果是刚启动，DB 为空也是正常的。
            # 这里我们只返回 DB 的结果，因为 create_analysis_task 保证了先写 DB。
            
            return self._enrich_stock_names(results)
            
        except Exception as e:
            logger.error(f"❌ 获取用户任务列表失败 (DB): {e}")
            # 降级：如果 DB 失败，尝试返回内存中的数据
            status_enum = None
            if status:
                try:
                    status_enum = TaskStatus(status)
                except ValueError:
                    pass
                    
            tasks = await self.memory_manager.list_user_tasks(
                user_id=user_id, 
                status=status_enum, 
                limit=limit, 
                offset=offset
            )
            return self._enrich_stock_names(tasks)

    async def cleanup_zombie_tasks(self, max_running_hours: int = 2) -> Dict[str, Any]:
        """清理僵尸任务"""
        return await self.memory_manager.cleanup_zombie_tasks(max_running_hours)

    async def _update_task_status(self, task_id: str, status: AnalysisStatus, progress: int, error_message: str = None):
        """更新任务状态到MongoDB"""
        try:
            db = get_mongo_db()
            update_data = {"status": status, "progress": progress, "updated_at": datetime.utcnow()}
            if status == AnalysisStatus.PROCESSING and progress == 10:
                update_data["started_at"] = datetime.utcnow()
            elif status == AnalysisStatus.COMPLETED:
                update_data["completed_at"] = datetime.utcnow()
            elif status == AnalysisStatus.FAILED:
                update_data["last_error"] = error_message
                update_data["completed_at"] = datetime.utcnow()
            await db.analysis_tasks.update_one({"task_id": task_id}, {"$set": update_data})
        except Exception as e:
            logger.error(f"❌ 更新任务状态失败: {task_id} - {e}")

    async def _save_analysis_results_complete(self, task_id: str, result: Dict[str, Any]):
        """完整的分析结果保存"""
        try:
            stock_symbol = result.get('stock_symbol') or result.get('stock_code', 'UNKNOWN')
            # 1. 保存到本地
            await self._save_modular_reports_to_data_dir(result, stock_symbol)
            # 2. 保存到数据库 (Web Style)
            await self._save_analysis_result_web_style(task_id, result)
        except Exception as e:
            logger.error(f"❌ 保存结果失败: {e}")

    async def _save_modular_reports_to_data_dir(self, result: Dict[str, Any], stock_symbol: str) -> Dict[str, str]:
        """保存分模块报告到data目录"""
        try:
            runtime_base = settings.RUNTIME_BASE_DIR
            results_dir = get_analysis_results_dir(runtime_base)
            analysis_date_str = result.get('analysis_date', datetime.now().strftime('%Y-%m-%d'))
            
            stock_dir = results_dir / stock_symbol / analysis_date_str
            reports_dir = stock_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            state = result.get('state', {})
            saved_files = {}
            
            # 简化的保存逻辑，只保存 decision
            decision = result.get('decision', {})
            if decision:
                decision_file = reports_dir / "final_trade_decision.md"
                with open(decision_file, 'w', encoding='utf-8') as f:
                    f.write(str(decision))
                saved_files['final_trade_decision'] = str(decision_file)
            
            return saved_files
        except Exception as e:
            logger.error(f"❌ 保存本地报告失败: {e}")
            return {}

    async def _save_analysis_result_web_style(self, task_id: str, result: Dict[str, Any]):
        """保存分析结果 (Web Style)"""
        try:
            db = get_mongo_db()
            stock_symbol = result.get('stock_symbol') or result.get('stock_code', 'UNKNOWN')
            timestamp = datetime.utcnow()
            analysis_id = f"{stock_symbol}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            document = {
                "analysis_id": analysis_id,
                "stock_symbol": stock_symbol,
                "stock_name": self._resolve_stock_name(stock_symbol),
                "analysis_date": result.get('analysis_date'),
                "status": "completed",
                "decision": result.get("decision", {}),
                "task_id": task_id,
                "created_at": timestamp,
            }
            
            await db.analysis_reports.insert_one(document)
            
            await db.analysis_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"result": document}}
            )
        except Exception as e:
            logger.error(f"❌ 保存DB结果失败: {e}")


# 全局分析服务实例
analysis_service: Optional[AnalysisService] = None

def get_analysis_service() -> AnalysisService:
    """获取分析服务实例"""
    global analysis_service
    if analysis_service is None:
        analysis_service = AnalysisService()
    return analysis_service


