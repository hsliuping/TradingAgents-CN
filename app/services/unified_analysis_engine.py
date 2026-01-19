"""
统一分析引擎

提供统一的任务执行接口，支持多种执行引擎：
- workflow: 工作流引擎（推荐）
- legacy: 旧引擎 TradingAgentsGraph
- llm: 直接 LLM 调用
"""

from typing import Dict, Any, Optional, Callable
import logging
from datetime import datetime

from app.models.analysis import UnifiedAnalysisTask, AnalysisTaskType, AnalysisStatus
from app.services.workflow_registry import AnalysisWorkflowRegistry
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)


class UnifiedAnalysisEngine:
    """统一分析引擎
    
    负责执行各种类型的分析任务，自动选择合适的执行引擎
    
    使用示例:
        engine = UnifiedAnalysisEngine()
        result = await engine.execute_task(task, progress_callback)
    """
    
    def __init__(self):
        """初始化引擎"""
        self.logger = logger
    
    async def execute_task(
        self,
        task: UnifiedAnalysisTask,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """执行分析任务
        
        Args:
            task: 统一分析任务对象
            progress_callback: 进度回调函数 callback(progress: int, message: str)
            
        Returns:
            分析结果字典
            
        Raises:
            ValueError: 任务类型未注册或参数无效
            RuntimeError: 执行失败
        """
        self.logger.info(f"🚀 开始执行任务: {task.task_id} (类型: {task.task_type})")
        
        # 1. 获取流程配置
        # 确保 task_type 是枚举类型（从数据库加载时可能是字符串）
        task_type = task.task_type
        if isinstance(task_type, str):
            try:
                task_type = AnalysisTaskType(task_type)
            except ValueError:
                raise ValueError(f"无效的任务类型: {task_type}")
        
        config = AnalysisWorkflowRegistry.get_config(task_type)
        if not config:
            raise ValueError(f"未注册的任务类型: {task_type}")
        
        # 2. 验证参数
        is_valid, error_msg = AnalysisWorkflowRegistry.validate_params(
            task.task_type,
            task.task_params
        )
        if not is_valid:
            raise ValueError(f"任务参数无效: {error_msg}")
        
        # 3. 选择执行引擎
        engine_type = self._select_engine(task.engine_type, config.default_engine)
        self.logger.info(f"📌 选择执行引擎: {engine_type}")
        
        # 4. 更新任务状态
        task.status = AnalysisStatus.PROCESSING
        task.started_at = now_tz()
        task.current_step = f"使用 {engine_type} 引擎执行"
        task.progress = 5

        # 通知进度
        if progress_callback:
            await self._call_progress_callback(progress_callback, 5, f"开始使用 {engine_type} 引擎执行")

        # 5. 执行分析
        try:
            if engine_type == "workflow":
                result = await self._execute_via_workflow(task, config, progress_callback)
            elif engine_type == "legacy":
                result = await self._execute_via_legacy(task, config, progress_callback)
            elif engine_type == "llm":
                result = await self._execute_via_llm(task, config, progress_callback)
            else:
                raise ValueError(f"不支持的引擎类型: {engine_type}")

            # 6. 更新任务状态
            task.status = AnalysisStatus.COMPLETED
            task.completed_at = now_tz()
            task.result = result
            task.progress = 100

            if task.started_at:
                task.execution_time = (task.completed_at - task.started_at).total_seconds()

            # 通知进度
            if progress_callback:
                await self._call_progress_callback(progress_callback, 100, "任务执行完成")

            self.logger.info(f"✅ 任务执行成功: {task.task_id} (耗时: {task.execution_time:.2f}秒)")

            return result

        except Exception as e:
            # 🔥 优雅处理：检查是否是取消异常
            from app.services.task_analysis_service import TaskCancelledException

            if isinstance(e, TaskCancelledException):
                # 任务取消是正常操作，不记录为错误
                self.logger.info(f"🚫 任务已取消: {task.task_id}")
                # 直接重新抛出，让上层处理
                raise

            # 其他异常才是真正的失败
            task.status = AnalysisStatus.FAILED
            task.completed_at = now_tz()
            task.error_message = str(e)

            if task.started_at:
                task.execution_time = (task.completed_at - task.started_at).total_seconds()

            self.logger.error(f"❌ 任务执行失败: {task.task_id} - {e}")
            raise RuntimeError(f"任务执行失败: {e}") from e
    
    async def _build_llm_config(
        self,
        quick_model: Optional[str],
        deep_model: Optional[str]
    ) -> Dict[str, Any]:
        """根据模型名称从数据库获取完整的 LLM 配置

        Args:
            quick_model: 快速分析模型名称
            deep_model: 深度分析模型名称

        Returns:
            包含 provider、api_key、backend_url 等的完整配置
        """
        if not quick_model and not deep_model:
            return {}

        from app.core.database import get_mongo_db

        db = get_mongo_db()

        # 获取系统配置
        config_doc = await db.system_configs.find_one(
            {"is_active": True},
            sort=[("version", -1)]
        )

        if not config_doc or "llm_configs" not in config_doc:
            self.logger.warning("数据库中没有 LLM 配置")
            return {}

        llm_configs = config_doc["llm_configs"]

        # 查找匹配的模型配置
        target_model = quick_model or deep_model
        model_config = None

        for cfg in llm_configs:
            if cfg.get("model_name") == target_model and cfg.get("enabled", True):
                model_config = cfg
                break

        if not model_config:
            self.logger.warning(f"未找到模型配置: {target_model}")
            return {}

        # 获取厂家配置
        provider_name = model_config.get("provider", "")
        provider_doc = await db.llm_providers.find_one({"name": provider_name})

        # 🔥 确定 API Key（优先级：模型配置 > 厂家配置 > 环境变量）
        api_key = None
        model_api_key = model_config.get("api_key", "")
        if model_api_key and model_api_key.strip() and model_api_key != "your-api-key" and not model_api_key.startswith("sk-xxx"):
            api_key = model_api_key
            self.logger.info(f"✅ [LLM配置] 使用模型配置的 API Key")
        elif provider_doc:
            provider_api_key = provider_doc.get("api_key", "")
            if provider_api_key and provider_api_key.strip() and provider_api_key != "your-api-key" and not provider_api_key.startswith("sk-xxx"):
                api_key = provider_api_key
                self.logger.info(f"✅ [LLM配置] 使用厂家配置的 API Key")
        
        backend_url = model_config.get("api_base", "")
        if provider_doc and not backend_url:
            backend_url = provider_doc.get("default_base_url", "")

        # 如果数据库没有 API Key，尝试从环境变量获取
        if not api_key:
            import os
            env_key_map = {
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "dashscope": "DASHSCOPE_API_KEY",
                "google": "GOOGLE_API_KEY",
                "zhipu": "ZHIPU_API_KEY",
                "siliconflow": "SILICONFLOW_API_KEY",
            }
            env_name = env_key_map.get(provider_name.lower())
            if env_name:
                api_key = os.getenv(env_name)

        # 🔥 获取快速模型配置
        quick_model_config = None
        if quick_model:
            for cfg in llm_configs:
                if cfg.get("model_name") == quick_model and cfg.get("enabled", True):
                    quick_model_config = cfg
                    break
        
        # 🔥 获取深度模型配置
        deep_model_config = None
        if deep_model and deep_model != quick_model:
            for cfg in llm_configs:
                if cfg.get("model_name") == deep_model and cfg.get("enabled", True):
                    deep_model_config = cfg
                    break
        
        # 如果深度模型配置不存在，使用快速模型配置
        if not deep_model_config:
            deep_model_config = quick_model_config or model_config
        
        # 获取深度模型的provider和api_key（如果不同）
        deep_provider_name = provider_name
        deep_api_key = api_key
        deep_backend_url = backend_url
        
        if deep_model_config and deep_model_config != quick_model_config:
            deep_provider_name = deep_model_config.get("provider", provider_name)
            # 🔥 确定深度模型的 API Key（优先级：模型配置 > 厂家配置 > 环境变量）
            deep_model_api_key = deep_model_config.get("api_key", "")
            if deep_model_api_key and deep_model_api_key.strip() and deep_model_api_key != "your-api-key" and not deep_model_api_key.startswith("sk-xxx"):
                deep_api_key = deep_model_api_key
                self.logger.info(f"✅ [LLM配置] 深度模型使用模型配置的 API Key")
            elif deep_provider_name != provider_name:
                deep_provider_doc = await db.llm_providers.find_one({"name": deep_provider_name})
                if deep_provider_doc:
                    deep_provider_api_key = deep_provider_doc.get("api_key", "")
                    if deep_provider_api_key and deep_provider_api_key.strip() and deep_provider_api_key != "your-api-key" and not deep_provider_api_key.startswith("sk-xxx"):
                        deep_api_key = deep_provider_api_key
                        self.logger.info(f"✅ [LLM配置] 深度模型使用厂家配置的 API Key")
                    deep_backend_url = deep_model_config.get("api_base", "") or deep_provider_doc.get("default_base_url", "")
            if not deep_api_key or deep_api_key.startswith("sk-xxx"):
                        import os
                        env_key_map = {
                            "openai": "OPENAI_API_KEY",
                            "deepseek": "DEEPSEEK_API_KEY",
                            "dashscope": "DASHSCOPE_API_KEY",
                            "google": "GOOGLE_API_KEY",
                            "zhipu": "ZHIPU_API_KEY",
                            "siliconflow": "SILICONFLOW_API_KEY",
                        }
                        env_name = env_key_map.get(deep_provider_name.lower())
                        if env_name:
                            deep_api_key = os.getenv(env_name) or deep_api_key
            else:
                deep_backend_url = deep_model_config.get("api_base", "") or backend_url
        
        result = {
            "llm_provider": provider_name,
            "quick_think_llm": quick_model or target_model,
            "deep_think_llm": deep_model or target_model,
            "backend_url": backend_url,
            "api_key": api_key,
            "quick_api_key": api_key,
            "deep_api_key": deep_api_key,
            "quick_temperature": (quick_model_config or model_config).get("temperature", 0.1),
            "quick_max_tokens": (quick_model_config or model_config).get("max_tokens", 2000),
            "quick_timeout": (quick_model_config or model_config).get("timeout", 60),
            "deep_temperature": deep_model_config.get("temperature", 0.1) if deep_model_config else (quick_model_config or model_config).get("temperature", 0.1),
            "deep_max_tokens": deep_model_config.get("max_tokens", 4000) if deep_model_config else (quick_model_config or model_config).get("max_tokens", 4000),
            "deep_timeout": deep_model_config.get("timeout", 120) if deep_model_config else (quick_model_config or model_config).get("timeout", 120),
            "deep_backend_url": deep_backend_url,  # 🔥 始终返回深度模型的backend_url
        }
        
        # 如果深度模型和快速模型使用不同的provider，添加深度模型的provider信息
        if deep_provider_name != provider_name:
            result["deep_llm_provider"] = deep_provider_name

        self.logger.info(f"从数据库获取模型配置: provider={provider_name}, quick={quick_model}, deep={deep_model}")
        self.logger.info(f"  quick: temperature={result['quick_temperature']}, max_tokens={result['quick_max_tokens']}, timeout={result['quick_timeout']}")
        self.logger.info(f"  deep: temperature={result['deep_temperature']}, max_tokens={result['deep_max_tokens']}, timeout={result['deep_timeout']}")

        return result

    async def _call_progress_callback(
        self,
        callback: Optional[Callable],
        progress: int,
        message: str,
        **kwargs
    ):
        """调用进度回调（支持同步和异步）"""
        if callback:
            import asyncio
            if asyncio.iscoroutinefunction(callback):
                await callback(progress, message, **kwargs)
            else:
                callback(progress, message, **kwargs)

    def _select_engine(self, requested_engine: str, default_engine: str) -> str:
        """选择执行引擎

        Args:
            requested_engine: 请求的引擎类型 (auto/workflow/legacy/llm)
            default_engine: 默认引擎类型

        Returns:
            实际使用的引擎类型
        """
        if requested_engine == "auto":
            return default_engine
        return requested_engine
    
    async def _execute_via_workflow(
        self,
        task: UnifiedAnalysisTask,
        config,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """通过工作流引擎执行

        Args:
            task: 任务对象
            config: 工作流配置
            progress_callback: 进度回调

        Returns:
            执行结果
        """
        self.logger.info(f"🔄 使用工作流引擎执行: {config.workflow_id}")

        # 导入工作流 API
        from core.api.workflow_api import WorkflowAPI

        workflow_api = WorkflowAPI()

        # 保存主事件循环的引用（在调用 asyncio.to_thread 之前）
        import asyncio
        main_loop = asyncio.get_running_loop()

        # 创建包装的进度回调，用于更新任务对象
        # 注意：这个回调会在工作流引擎的线程中被调用（因为使用了 asyncio.to_thread）
        # 所以不能直接调用异步函数，需要使用 asyncio.run_coroutine_threadsafe
        def wrapped_progress_callback(progress: int, message: str, **kwargs):
            """包装的进度回调：更新任务对象并调用原始回调"""
            # 🔑 关键：从 kwargs 中提取 step_name（简短名称）
            step_name = kwargs.get("step_name", "")

            # 更新任务对象（这是线程安全的，因为只是修改对象属性）
            task.progress = progress
            task.current_step = step_name or message  # ✅ 使用 step_name 而不是 message
            task.message = message  # ✅ 保存详细描述到 message 字段

            self.logger.debug(f"📊 进度更新: {progress}% - {step_name} - {message}")

            # 调用原始回调（原始回调会检查取消标记）
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    # 如果是异步回调，需要在主事件循环中运行
                    try:
                        # 使用保存的主事件循环引用
                        future = asyncio.run_coroutine_threadsafe(
                            progress_callback(progress, message, **kwargs),
                            main_loop
                        )
                        # 🔥 关键：等待回调完成，以便捕获 TaskCancelledException
                        try:
                            future.result(timeout=5)  # 等待最多5秒
                        except Exception as callback_error:
                            # 如果回调抛出异常（比如 TaskCancelledException），向上传播
                            self.logger.warning(f"⚠️ 进度回调执行异常: {callback_error}")
                            raise callback_error
                    except Exception as e:
                        self.logger.warning(f"⚠️ 进度回调调度失败: {e}")
                        raise  # 向上传播异常
                else:
                    # 同步回调可以直接调用
                    try:
                        progress_callback(progress, message, **kwargs)
                    except Exception as e:
                        self.logger.warning(f"⚠️ 进度回调执行失败: {e}")
                        raise  # 向上传播异常
        
        # 准备工作流输入
        workflow_inputs = task.task_params.copy()

        # 🔑 创建 AgentContext 并添加到工作流输入（用于获取用户配置的提示词）
        from tradingagents.agents.utils.agent_context import AgentContext

        agent_context = AgentContext(
            user_id=str(task.user_id),
            preference_id=task.preference_type,  # 使用任务的偏好类型
            session_id=None,
            request_id=None,
            is_debug_mode=False,  # 正式流程不启用调试模式
            debug_template_id=None
        )

        # 将 AgentContext 添加到工作流输入
        workflow_inputs["context"] = agent_context

        # 参数映射：将 symbol 映射为 ticker（工作流引擎使用 ticker）
        if "symbol" in workflow_inputs and "ticker" not in workflow_inputs:
            workflow_inputs["ticker"] = workflow_inputs["symbol"]

        # 确保有 analysis_date
        if "analysis_date" not in workflow_inputs:
            from datetime import datetime
            workflow_inputs["analysis_date"] = datetime.now().strftime("%Y-%m-%d")

        # 确保有 research_depth
        if "research_depth" not in workflow_inputs:
            workflow_inputs["research_depth"] = "标准"

        # 添加其他可能需要的参数
        workflow_inputs.setdefault("lookback_days", 30)
        workflow_inputs.setdefault("max_debate_rounds", 3)

        self.logger.info(f"📦 工作流输入参数: ticker={workflow_inputs.get('ticker')}, "
                        f"analysis_date={workflow_inputs.get('analysis_date')}, "
                        f"research_depth={workflow_inputs.get('research_depth')}, "
                        f"selected_analysts={workflow_inputs.get('selected_analysts')}, "
                        f"user_id={agent_context.user_id}, "
                        f"preference_id={agent_context.preference_id}")

        # 准备遗留配置（LLM配置等）
        legacy_config = {
            "preference_type": task.preference_type,
        }

        # 🔑 关键：从任务参数中提取 selected_analysts（用于动态裁剪工作流）
        if "selected_analysts" in workflow_inputs:
            legacy_config["selected_analysts"] = workflow_inputs["selected_analysts"]
            self.logger.info(f"🎯 选中的分析师: {workflow_inputs['selected_analysts']}")

        # 从任务参数中提取 LLM 配置
        if "quick_analysis_model" in workflow_inputs:
            legacy_config["quick_think_llm"] = workflow_inputs["quick_analysis_model"]
        if "deep_analysis_model" in workflow_inputs:
            legacy_config["deep_think_llm"] = workflow_inputs["deep_analysis_model"]

        # 如果指定了模型，需要从数据库获取完整的 LLM 配置
        if "quick_analysis_model" in workflow_inputs or "deep_analysis_model" in workflow_inputs:
            # 调用辅助方法构建完整的 LLM 配置
            full_config = await self._build_llm_config(
                workflow_inputs.get("quick_analysis_model"),
                workflow_inputs.get("deep_analysis_model")
            )
            legacy_config.update(full_config)

        self.logger.info(f"🔧 LLM配置: quick={legacy_config.get('quick_think_llm')}, "
                        f"deep={legacy_config.get('deep_think_llm')}, "
                        f"provider={legacy_config.get('llm_provider')}")

        # 执行工作流（WorkflowAPI.execute 是同步方法，需要在线程中运行）
        import asyncio
        result = await asyncio.to_thread(
            workflow_api.execute,
            workflow_id=task.workflow_id or config.workflow_id,
            inputs=workflow_inputs,
            legacy_config=legacy_config,
            progress_callback=wrapped_progress_callback  # 使用包装的回调
        )

        # 检查执行结果
        if not result.get("success"):
            error_msg = result.get("error", "工作流执行失败")
            raise RuntimeError(error_msg)

        return result.get("result", {})

    async def _execute_via_legacy(
        self,
        task: UnifiedAnalysisTask,
        config,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """通过旧引擎执行（TradingAgentsGraph）

        Args:
            task: 任务对象
            config: 工作流配置
            progress_callback: 进度回调

        Returns:
            执行结果
        """
        self.logger.info(f"🔄 使用旧引擎执行: TradingAgentsGraph")

        # 只支持股票分析任务
        if task.task_type != AnalysisTaskType.STOCK_ANALYSIS:
            raise ValueError(f"旧引擎只支持股票分析任务，当前任务类型: {task.task_type}")

        # 导入旧引擎
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        # 准备参数
        symbol = task.task_params.get("symbol")
        analysis_date = task.task_params.get("analysis_date")

        if not symbol:
            raise ValueError("缺少必需参数: symbol")

        # 创建引擎实例
        graph = TradingAgentsGraph(debug=False)

        # 执行分析
        self.logger.info(f"📊 分析股票: {symbol} (日期: {analysis_date or '最新'})")

        # 调用 propagate 方法
        state, decision = graph.propagate(symbol, analysis_date)

        # 转换结果格式
        result = {
            "engine": "legacy",
            "symbol": symbol,
            "analysis_date": analysis_date,
            "decision": decision,
            "state": state,
            "source": "TradingAgentsGraph"
        }

        return result

    async def _execute_via_llm(
        self,
        task: UnifiedAnalysisTask,
        config,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """通过直接 LLM 调用执行

        Args:
            task: 任务对象
            config: 工作流配置
            progress_callback: 进度回调

        Returns:
            执行结果
        """
        self.logger.info(f"🔄 使用 LLM 直接调用执行")

        # 导入 LLM 管理器
        from core.llm.llm_manager import LLMManager

        llm_manager = LLMManager()

        # 根据任务类型构建提示词
        prompt = self._build_prompt_for_task(task)

        # 调用 LLM
        self.logger.info(f"💬 调用 LLM: {task.preference_type} 偏好")

        response = await llm_manager.generate(
            prompt=prompt,
            preference_type=task.preference_type,
            temperature=0.7
        )

        # 转换结果格式
        result = {
            "engine": "llm",
            "task_type": task.task_type.value,
            "response": response,
            "source": "LLM直接调用"
        }

        return result

    def _build_prompt_for_task(self, task: UnifiedAnalysisTask) -> str:
        """为任务构建提示词

        Args:
            task: 任务对象

        Returns:
            提示词字符串
        """
        # 根据任务类型构建不同的提示词
        if task.task_type == AnalysisTaskType.PORTFOLIO_HEALTH:
            return self._build_portfolio_health_prompt(task.task_params)
        elif task.task_type == AnalysisTaskType.RISK_ASSESSMENT:
            return self._build_risk_assessment_prompt(task.task_params)
        elif task.task_type == AnalysisTaskType.MARKET_OVERVIEW:
            return self._build_market_overview_prompt(task.task_params)
        else:
            # 通用提示词
            return f"""请分析以下任务：

任务类型: {task.task_type.value}
任务参数: {task.task_params}

请提供详细的分析结果。"""

    def _build_portfolio_health_prompt(self, params: Dict[str, Any]) -> str:
        """构建组合健康度分析提示词"""
        return f"""请分析投资组合的健康度。

分析要点：
1. 持仓集中度分析
2. 风险分散情况
3. 收益稳定性
4. 资金使用效率
5. 整体健康度评分

参数: {params}

请提供详细的分析报告。"""

    def _build_risk_assessment_prompt(self, params: Dict[str, Any]) -> str:
        """构建风险评估提示词"""
        return f"""请进行风险评估分析。

评估维度：
1. 市场风险
2. 个股风险
3. 流动性风险
4. 集中度风险
5. 综合风险评级

参数: {params}

请提供详细的风险评估报告。"""

    def _build_market_overview_prompt(self, params: Dict[str, Any]) -> str:
        """构建市场概览提示词"""
        return f"""请提供市场概览分析。

分析内容：
1. 市场整体走势
2. 板块表现
3. 资金流向
4. 市场情绪
5. 投资建议

参数: {params}

请提供详细的市场分析报告。"""

