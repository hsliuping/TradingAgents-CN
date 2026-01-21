"""
分析任务Worker进程
消费队列中的分析任务，调用TradingAgents进行股票分析
"""

import asyncio
import logging
import signal
import sys
import uuid
import traceback
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.queue_service import get_queue_service
from app.services.analysis_service import get_analysis_service
from app.core.database import init_database, close_database
from app.core.redis_client import init_redis, close_redis
from app.core.config import settings
from app.models.analysis import AnalysisTask, AnalysisParameters, AnalysisStatus
from app.services.config_provider import provider as config_provider
from app.services.queue import DEFAULT_USER_CONCURRENT_LIMIT, GLOBAL_CONCURRENT_LIMIT, VISIBILITY_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class AnalysisWorker:
    """分析任务Worker类"""

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.queue_service = None
        self.running = False
        self.current_task = None
        
        # 🔥 并发控制：使用 Semaphore 限制同时执行的任务数量
        self.max_concurrent_tasks = 3  # 默认并发数，会在 start() 中从配置读取
        self.semaphore = None  # 在 start() 中初始化
        self.running_tasks = set()  # 跟踪正在运行的任务

        # 配置参数（可由系统设置覆盖）
        self.heartbeat_interval = int(getattr(settings, 'WORKER_HEARTBEAT_INTERVAL', 30))
        self.max_retries = int(getattr(settings, 'QUEUE_MAX_RETRIES', 3))
        self.poll_interval = float(getattr(settings, 'QUEUE_POLL_INTERVAL_SECONDS', 1))  # 队列轮询间隔（秒）
        self.cleanup_interval = float(getattr(settings, 'QUEUE_CLEANUP_INTERVAL_SECONDS', 60))

        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理器，优雅关闭"""
        logger.info(f"收到信号 {signum}，准备关闭Worker...")
        self.running = False

    async def start(self):
        """启动Worker"""
        try:
            logger.info(f"🚀 启动分析Worker: {self.worker_id}")

            # 初始化数据库连接
            await init_database()
            await init_redis()
            
            # 🔥 配置桥接：将统一配置写入环境变量，供 TradingAgents 核心库使用
            # 这必须在其他初始化之前执行，因为后续的 LLM、数据源等都需要从环境变量读取配置
            try:
                from app.core.config_bridge import bridge_config_to_env
                bridge_config_to_env()
                logger.info("✅ 配置桥接完成")
            except Exception as e:
                logger.warning(f"⚠️ 配置桥接失败: {e}")
                logger.warning("⚠️ TradingAgents 将使用 .env 文件中的配置")
            
            # 🔥 初始化 Agent 注册表（导入 adapters 模块会触发自动注册）
            try:
                logger.info("🔄 开始加载 Agent 适配器模块...")
                import core.agents.adapters  # 这会触发所有 Agent 的自动注册
                from core.agents.registry import get_registry
                registry = get_registry()
                agent_count = len(registry.list_all())
                logger.info(f"✅ Agent 注册表已初始化，共 {agent_count} 个 Agent")
            except Exception as e:
                logger.error(f"❌ Agent 注册表初始化失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 不阻止 Worker 启动，但会记录错误
            
            # 🔥 初始化工具注册表（必须在执行任务前初始化，确保工具可用）
            try:
                # 1. 显式导入工具实现模块，触发 @register_tool 装饰器
                logger.info("🔄 开始加载工具实现模块...")
                try:
                    # 导入工具实现模块的 __init__.py，这会触发所有工具的自动注册
                    import core.tools.implementations
                    logger.info("✅ 工具实现模块已导入")
                except Exception as e:
                    logger.warning(f"⚠️ 导入工具实现模块失败: {e}")
                
                # 2. 创建 ToolRegistry 实例（会自动加载所有工具模块）
                from core.tools.registry import ToolRegistry
                registry = ToolRegistry()
                tool_count = len(registry.list_all())
                logger.info(f"✅ 工具注册表已初始化，共 {tool_count} 个工具")
                
                # 3. 验证关键工具是否已加载
                critical_tools = [
                    "get_stock_market_data_unified",
                    "get_stock_fundamentals_unified",
                    "get_stock_news_unified",
                    "get_stock_sentiment_unified",
                    "get_index_data",
                    "get_market_breadth",
                    "get_market_environment",
                    "identify_market_cycle",
                    "get_sector_data",
                    "get_fund_flow_data",
                    "get_peer_comparison",
                ]
                missing_tools = []
                for tool_id in critical_tools:
                    has_metadata = registry.has_tool(tool_id)
                    has_function = registry.get_function(tool_id) is not None
                    if not has_metadata:
                        missing_tools.append(f"{tool_id} (无元数据)")
                    elif not has_function:
                        missing_tools.append(f"{tool_id} (无函数实现)")
                
                if missing_tools:
                    logger.warning(f"⚠️ 以下关键工具未正确加载: {missing_tools}")
                    # 尝试手动加载这些工具
                    from core.tools.loader import get_tool_loader
                    loader = get_tool_loader()
                    for tool_info in missing_tools:
                        tool_id = tool_info.split(" ")[0]  # 提取工具ID
                        logger.info(f"🔄 尝试重新加载工具: {tool_id}")
                        loader.load_tool(tool_id)
                    
                    # 重新验证
                    still_missing = []
                    for tool_id in critical_tools:
                        if not registry.has_tool(tool_id) or registry.get_function(tool_id) is None:
                            still_missing.append(tool_id)
                    if still_missing:
                        logger.error(f"❌ 以下工具重新加载后仍然缺失: {still_missing}")
                    else:
                        logger.info("✅ 所有关键工具已成功重新加载")
                else:
                    logger.info("✅ 所有关键工具已正确加载")
            except Exception as e:
                logger.error(f"❌ 工具注册表初始化失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 不阻止 Worker 启动，但会记录错误
            
            # 🔥 初始化自定义工具（从数据库加载用户自定义的工具）
            try:
                from app.core.database import get_mongo_db
                from core.tools.custom_tool import CustomToolDefinition, register_custom_tool
                
                db = get_mongo_db()
                cursor = db.custom_tools.find()
                custom_tool_count = 0
                async for doc in cursor:
                    try:
                        # 移除 _id 字段以符合 Pydantic 模型
                        if "_id" in doc:
                            del doc["_id"]
                        definition = CustomToolDefinition(**doc)
                        await register_custom_tool(definition)
                        custom_tool_count += 1
                        logger.info(f"✅ 加载自定义工具: {definition.id}")
                    except Exception as e:
                        logger.error(f"❌ 加载自定义工具失败 {doc.get('id')}: {e}")
                
                if custom_tool_count > 0:
                    logger.info(f"✅ 自定义工具初始化完成，共加载 {custom_tool_count} 个工具")
                else:
                    logger.info("✅ 自定义工具初始化完成（无自定义工具）")
            except Exception as e:
                logger.warning(f"⚠️ 自定义工具初始化失败: {e}")
                # 不阻止 Worker 启动，但会记录警告
            
            # 🔥 初始化工作流注册表（必须在执行任务前初始化）
            from app.services.workflow_registry import initialize_builtin_workflows
            initialize_builtin_workflows()
            logger.info("✅ 工作流注册表已初始化")

            # 读取系统设置（ENV 优先 → DB）
            try:
                effective_settings = await config_provider.get_effective_system_settings()
                
                # 🔥 应用动态日志级别设置（与 API 进程保持一致）
                try:
                    desired_level = str(effective_settings.get("log_level", "INFO")).upper()
                    logging.getLogger().setLevel(desired_level)
                    # 设置关键日志器的级别
                    for name in ("worker", "webapi", "core", "tradingagents"):
                        logging.getLogger(name).setLevel(desired_level)
                    logger.info(f"✅ 日志级别已设置为: {desired_level}")
                except Exception as e:
                    logger.warning(f"⚠️ 设置日志级别失败: {e}")
            except Exception:
                effective_settings = {}

            # 获取队列服务
            self.queue_service = get_queue_service()

            self.running = True

            # 应用队列并发/超时配置 + Worker/轮询参数
            try:
                # 🔥 Worker 并发数配置（从系统设置读取，默认3）
                self.max_concurrent_tasks = int(effective_settings.get("worker_max_concurrent_tasks", 3))
                # 初始化 Semaphore
                self.semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
                logger.info(f"🔧 Worker 并发数设置为: {self.max_concurrent_tasks}")
                
                self.queue_service.user_concurrent_limit = int(effective_settings.get("max_concurrent_tasks", DEFAULT_USER_CONCURRENT_LIMIT))
                self.queue_service.global_concurrent_limit = int(effective_settings.get("max_concurrent_tasks", GLOBAL_CONCURRENT_LIMIT))
                self.queue_service.visibility_timeout = int(effective_settings.get("default_analysis_timeout", VISIBILITY_TIMEOUT_SECONDS))
                # Worker intervals
                self.heartbeat_interval = int(effective_settings.get("worker_heartbeat_interval_seconds", self.heartbeat_interval))
                self.poll_interval = float(effective_settings.get("queue_poll_interval_seconds", self.poll_interval))
                self.cleanup_interval = float(effective_settings.get("queue_cleanup_interval_seconds", self.cleanup_interval))
            except Exception:
                # 如果配置读取失败，使用默认值
                self.max_concurrent_tasks = 3
                self.semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
                logger.warning(f"⚠️ 使用默认 Worker 并发数: {self.max_concurrent_tasks}")
            # 🔥 Worker启动时恢复卡住的任务（进程重启后）
            await self._recover_stuck_tasks()
            
            # 启动心跳任务
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # 启动清理任务
            cleanup_task = asyncio.create_task(self._cleanup_loop())

            # 主工作循环
            await self._work_loop()

            # 取消后台任务
            heartbeat_task.cancel()
            cleanup_task.cancel()

            try:
                await heartbeat_task
                await cleanup_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            # 🔥 记录详细的启动失败信息，并重新抛出异常
            logger.error(f"❌ Worker启动失败: {e}")
            logger.error(traceback.format_exc())
            self.running = False
            # 🔥 重新抛出异常，让调用者知道启动失败
            raise
        finally:
            await self._cleanup()

    async def _work_loop(self):
        """主工作循环 - 支持并发执行多个任务"""
        logger.info(f"✅ Worker {self.worker_id} 开始工作 (最大并发数: {self.max_concurrent_tasks})")

        while self.running:
            try:
                # 🔥 检查当前并发数，如果未达到上限，继续获取任务
                current_concurrent = len(self.running_tasks)
                if current_concurrent < self.max_concurrent_tasks:
                    # 从队列获取任务
                    task_data = await self.queue_service.dequeue_task(self.worker_id)

                    if task_data:
                        # 🔥 使用 create_task 并发执行任务，不阻塞主循环
                        task_coro = self._process_task_with_semaphore(task_data)
                        task = asyncio.create_task(task_coro)
                        self.running_tasks.add(task)
                        
                        # 🔥 添加异常回调，确保任务异常时也能从集合中移除
                        def remove_task(task_future):
                            """任务完成或异常时从集合中移除"""
                            try:
                                self.running_tasks.discard(task_future)
                                # 如果任务有异常，记录日志但不影响 Worker 进程
                                if task_future.exception():
                                    logger.error(f"❌ 任务执行异常: {task_future.exception()}")
                            except Exception as e:
                                logger.error(f"❌ 移除任务时出错: {e}")
                        
                        task.add_done_callback(remove_task)
                        
                        logger.debug(f"📊 当前并发任务数: {len(self.running_tasks)}/{self.max_concurrent_tasks}")
                    else:
                        # 没有任务，短暂休眠
                        await asyncio.sleep(self.poll_interval)
                else:
                    # 已达到并发上限，等待一段时间后再检查
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                # 🔥 工作循环异常不应该导致 Worker 进程退出
                logger.error(f"❌ 工作循环异常: {e}")
                logger.error(traceback.format_exc())
                logger.info("🔄 Worker 将继续运行，等待下次循环...")
                await asyncio.sleep(5)  # 异常后等待5秒再继续

        # 🔥 等待所有正在运行的任务完成
        if self.running_tasks:
            logger.info(f"⏳ 等待 {len(self.running_tasks)} 个任务完成...")
            await asyncio.gather(*self.running_tasks, return_exceptions=True)

        logger.info(f"🔄 Worker {self.worker_id} 工作循环结束")

    async def _process_task_with_semaphore(self, task_data: Dict[str, Any]):
        """使用 Semaphore 控制并发的任务处理包装器"""
        task_id = task_data.get("id", "unknown")
        try:
            async with self.semaphore:  # 🔥 并发控制：最多同时执行 max_concurrent_tasks 个任务
                await self._process_task(task_data)
        except Exception as e:
            # 🔥 确保任务级别的异常不会导致 Worker 进程崩溃
            logger.error(f"❌ 任务处理包装器捕获异常: {task_id} - {e}")
            logger.error(traceback.format_exc())
            
            # 尝试更新任务状态为失败
            try:
                from app.services.queue_service import get_queue_service
                queue_service = get_queue_service()
                await queue_service.ack_task(task_id, success=False)
            except Exception as ack_error:
                logger.error(f"❌ 确认失败任务时出错: {task_id} - {ack_error}")
            
            # 如果是 v2 引擎任务，尝试更新任务状态
            try:
                parameters_dict = task_data.get("parameters", {})
                if isinstance(parameters_dict, str):
                    import json
                    parameters_dict = json.loads(parameters_dict)
                
                engine_type = parameters_dict.get("engine", "legacy")
                if engine_type == "v2":
                    from app.services.task_analysis_service import get_task_analysis_service
                    from app.models.analysis import AnalysisStatus
                    from app.utils.timezone import now_tz
                    
                    task_service = get_task_analysis_service()
                    task = await task_service.get_task(task_id)
                    if task:
                        task.status = AnalysisStatus.FAILED
                        task.error_message = f"任务处理异常: {str(e)}"
                        task.completed_at = now_tz()
                        await task_service._update_task(task)
            except Exception as update_error:
                logger.error(f"❌ 更新任务状态时出错: {task_id} - {update_error}")
            
            # 异常已处理，不重新抛出，确保 Worker 进程继续运行
    
    async def _process_task(self, task_data: Dict[str, Any]):
        """处理单个任务"""
        task_id = task_data.get("id")
        stock_code = task_data.get("symbol")
        user_id = task_data.get("user")

        logger.info(f"📊 开始处理任务: {task_id} - {stock_code} (当前并发: {len(self.running_tasks)}/{self.max_concurrent_tasks})")

        self.current_task = task_id
        success = False

        try:
            # 解析任务参数
            parameters_dict = task_data.get("parameters", {})
            if isinstance(parameters_dict, str):
                import json
                parameters_dict = json.loads(parameters_dict)
            
            # 🔥 数据校验：暂时禁用（功能未完善）
            # validation_result = await self._validate_task_data(stock_code, parameters_dict)
            # if not validation_result.is_valid:
            #     # 数据校验失败，更新任务状态并返回
            #     error_message = validation_result.message
            #     logger.warning(f"⚠️ 任务 {task_id} 数据校验失败: {error_message}")
            #
            #     # 更新任务状态（如果是 v2 引擎任务）
            #     engine_type = parameters_dict.get("engine", "legacy")
            #     if engine_type == "v2":
            #         from app.services.task_analysis_service import get_task_analysis_service
            #         from app.utils.timezone import now_tz
            #         task_service = get_task_analysis_service()
            #         task = await task_service.get_task(task_id)
            #         if task:
            #             task.status = AnalysisStatus.FAILED
            #             task.error_message = error_message
            #             task.completed_at = now_tz()
            #             await task_service._update_task(task)
            #
            #     # 更新进度回调
            #     await self._progress_callback(0, error_message)
            #
            #     # 抛出异常，让上层处理
            #     raise ValueError(error_message)
            
            # 检查引擎类型
            engine_type = parameters_dict.get("engine", "legacy")
            
            if engine_type == "v2":
                # v2 引擎：使用统一任务服务
                logger.info(f"🔧 [Worker] 使用 v2 引擎执行任务: {task_id}")
                from app.services.task_analysis_service import get_task_analysis_service
                from app.services.memory_state_manager import get_memory_state_manager
                
                task_service = get_task_analysis_service()
                
                # 获取任务对象
                task = await task_service.get_task(task_id)
                if not task:
                    raise ValueError(f"任务不存在: {task_id}")
                
                # 🔥 关键：确保任务在内存状态管理器中存在（Worker 进程和 API 进程是分开的）
                memory_manager = get_memory_state_manager()
                try:
                    # 尝试获取任务，如果不存在则创建
                    memory_task = await memory_manager.get_task(task_id)
                    if not memory_task:
                        logger.info(f"📝 [Worker] 任务不在内存中，创建内存状态: {task_id}")
                        await memory_manager.create_task(
                            task_id=task_id,
                            user_id=user_id,
                            stock_code=stock_code,
                            parameters=parameters_dict,
                            stock_name=None
                        )
                        logger.info(f"✅ [Worker] 任务已创建到内存状态管理器: {task_id}")
                except Exception as e:
                    logger.warning(f"⚠️ [Worker] 检查/创建内存任务失败: {e}，继续执行")
                
                # 执行任务
                await task_service.execute_task(task, progress_callback=self._progress_callback)
                success = True
                logger.info(f"✅ [v2引擎] 任务完成: {task_id}")
                
            elif engine_type == "unified":
                # unified 引擎：使用统一分析服务
                logger.info(f"🔧 [Worker] 使用 unified 引擎执行任务: {task_id}")
                from app.services.unified_analysis_service import get_unified_analysis_service
                from app.models.analysis import SingleAnalysisRequest
                
                unified_service = get_unified_analysis_service()
                
                # 构建 SingleAnalysisRequest
                single_req = SingleAnalysisRequest(
                    symbol=stock_code,
                    stock_code=stock_code,
                    parameters=AnalysisParameters(**parameters_dict) if parameters_dict else None
                )
                
                # 执行分析
                await unified_service.execute_analysis_for_ab_test(
                    task_id=task_id,
                    user_id=user_id,
                    request=single_req
                )
                success = True
                logger.info(f"✅ [unified引擎] 任务完成: {task_id}")
                
            else:
                # legacy 引擎：使用旧的分析服务
                logger.info(f"🔧 [Worker] 使用 legacy 引擎执行任务: {task_id}")
                parameters = AnalysisParameters(**parameters_dict)

                task = AnalysisTask(
                    task_id=task_id,
                    user_id=user_id,
                    stock_code=stock_code,
                    batch_id=task_data.get("batch_id"),
                    parameters=parameters
                )

                # 执行分析
                result = await get_analysis_service().execute_analysis_task(
                    task,
                    progress_callback=self._progress_callback
                )

                success = True
                logger.info(f"✅ [legacy引擎] 任务完成: {task_id} - 耗时: {result.execution_time:.2f}秒")

        except Exception as e:
            logger.error(f"❌ 任务执行失败: {task_id} - {e}")
            logger.error(traceback.format_exc())

        finally:
            # 确认任务完成
            try:
                await self.queue_service.ack_task(task_id, success)
            except Exception as e:
                logger.error(f"确认任务失败: {task_id} - {e}")

            self.current_task = None

    async def _validate_task_data(
        self,
        stock_code: str,
        parameters_dict: Dict[str, Any]
    ) -> 'DataValidationResult':
        """
        校验任务所需的数据完整性
        
        Args:
            stock_code: 股票代码
            parameters_dict: 任务参数字典
            
        Returns:
            DataValidationResult: 校验结果
        """
        from app.services.data_validation_service import get_data_validation_service, DataValidationResult
        
        # 从参数中提取必要信息
        analysis_date = parameters_dict.get("analysis_date")
        market_type = parameters_dict.get("market_type", "cn")
        
        # 如果 market_type 是 "A股" 等中文，转换为英文
        market_type_map = {
            "A股": "cn",
            "港股": "hk",
            "美股": "us",
            "cn": "cn",
            "hk": "hk",
            "us": "us"
        }
        market_type = market_type_map.get(market_type, "cn")
        
        # 如果没有指定分析日期，使用当前日期
        if not analysis_date:
            from datetime import datetime
            analysis_date = datetime.now().strftime('%Y-%m-%d')
        
        if not stock_code:
            return DataValidationResult(
                is_valid=False,
                message="任务参数中缺少股票代码",
                missing_data=["symbol"],
                details={"error": "股票代码缺失"}
            )
        
        # 调用数据校验服务
        validation_service = get_data_validation_service()
        result = await validation_service.validate_stock_data(
            symbol=stock_code,
            analysis_date=analysis_date,
            market_type=market_type,
            check_basic_info=True,
            check_historical_data=False,  # 🔥 禁用历史数据检查（避免误报）
            check_financial_data=False,  # 财务数据可选
            check_realtime_quotes=False,  # 实时行情可选
            historical_days=365  # 默认检查近1年的历史数据
        )

        return result
    
    def _progress_callback(self, progress: int, message: str, **kwargs):
        """进度回调函数
        
        Args:
            progress: 进度百分比 (0-100)
            message: 进度消息
            **kwargs: 额外参数（如 step_name 等）
        """
        step_name = kwargs.get("step_name", "")
        if step_name:
            logger.debug(f"任务进度 {self.current_task}: {progress}% - {step_name} - {message}")
        else:
            logger.debug(f"任务进度 {self.current_task}: {progress}% - {message}")

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳异常: {e}")
                await asyncio.sleep(5)

    async def _send_heartbeat(self):
        """发送心跳"""
        try:
            from app.core.redis_client import get_redis_service
            redis_service = get_redis_service()

            heartbeat_data = {
                "worker_id": self.worker_id,
                "timestamp": datetime.utcnow().isoformat(),
                "current_task": self.current_task,
                "status": "active" if self.running else "stopping"
            }

            heartbeat_key = f"worker:{self.worker_id}:heartbeat"
            await redis_service.set_json(heartbeat_key, heartbeat_data, ttl=self.heartbeat_interval * 2)

        except Exception as e:
            logger.error(f"发送心跳失败: {e}")

    async def _cleanup_loop(self):
        """定期清理过期任务的循环"""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                if self.queue_service:
                    await self.queue_service.cleanup_expired_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理过期任务失败: {e}")
                await asyncio.sleep(5)

    async def _recover_stuck_tasks(self):
        """Worker启动时恢复卡住的任务（进程重启后）
        
        检查两种情况：
        1. Redis队列中标记为"processing"但超过可见性超时的任务
        2. 数据库中状态为"processing"但超过超时时间的任务
        """
        try:
            logger.info("🔍 Worker启动：检查并恢复卡住的任务...")
            
            # 1. 清理Redis队列中的过期任务
            if self.queue_service:
                await self.queue_service.cleanup_expired_tasks()
            
            # 2. 检查数据库中的"processing"状态任务
            from app.core.database import get_mongo_db_sync
            from app.models.analysis import AnalysisStatus
            
            db = get_mongo_db_sync()
            collection = db["unified_analysis_tasks"]
            
            # 计算超时时间（默认30分钟）
            timeout_seconds = self.queue_service.visibility_timeout if self.queue_service else 1800
            timeout_threshold = datetime.utcnow() - timedelta(seconds=timeout_seconds)
            
            # 查找所有"processing"状态且超过超时时间的任务
            stuck_tasks = collection.find({
                "status": AnalysisStatus.PROCESSING.value,
                "$or": [
                    {"started_at": {"$lt": timeout_threshold}},
                    {"started_at": {"$exists": False}}  # 没有started_at的任务也视为卡住
                ]
            })
            
            stuck_count = 0
            for task_doc in stuck_tasks:
                task_id = task_doc.get("task_id")
                if not task_id:
                    continue
                
                try:
                    # 检查任务是否在Redis队列中
                    task_data = await self.queue_service.get_task(task_id)
                    
                    if task_data:
                        # 如果任务在Redis中且状态是processing，检查是否过期
                        if task_data.get("status") == "processing":
                            started_at_str = task_data.get("started_at")
                            if started_at_str:
                                started_at = int(started_at_str)
                                if time.time() - started_at > timeout_seconds:
                                    # 任务过期，重新入队
                                    logger.warning(f"🔄 恢复卡住的任务（Redis队列）: {task_id}")
                                    await self.queue_service._handle_expired_task(task_id)
                                    
                                    # 🔥 同时更新数据库中的任务状态为"queued"
                                    try:
                                        collection.update_one(
                                            {"task_id": task_id},
                                            {
                                                "$set": {
                                                    "status": AnalysisStatus.PENDING.value,
                                                    "error_message": None,
                                                    "progress": 0
                                                }
                                            }
                                        )
                                    except Exception as db_err:
                                        logger.warning(f"更新数据库任务状态失败: {task_id} - {db_err}")
                                    
                                    stuck_count += 1
                    else:
                        # 任务不在Redis队列中，但数据库状态是processing，标记为失败
                        logger.warning(f"⚠️ 恢复卡住的任务（数据库）: {task_id} - 标记为失败")
                        collection.update_one(
                            {"task_id": task_id},
                            {
                                "$set": {
                                    "status": AnalysisStatus.FAILED.value,
                                    "error_message": "Worker进程重启，任务执行中断",
                                    "completed_at": datetime.utcnow()
                                }
                            }
                        )
                        stuck_count += 1
                        
                except Exception as e:
                    logger.error(f"恢复任务失败: {task_id} - {e}")
            
            if stuck_count > 0:
                logger.info(f"✅ 已恢复 {stuck_count} 个卡住的任务")
            else:
                logger.info("✅ 没有发现卡住的任务")
                
        except Exception as e:
            logger.error(f"恢复卡住的任务失败: {e}")
            logger.error(traceback.format_exc())

    async def _cleanup(self):
        """清理资源"""
        logger.info(f"🧹 清理Worker资源: {self.worker_id}")

        try:
            # 清理心跳记录
            from app.core.redis_client import get_redis_service
            redis_service = get_redis_service()
            heartbeat_key = f"worker:{self.worker_id}:heartbeat"
            await redis_service.redis.delete(heartbeat_key)
        except Exception as e:
            logger.error(f"清理心跳记录失败: {e}")

        try:
            # 关闭数据库连接
            await close_database()
            await close_redis()
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建并启动Worker
    worker = AnalysisWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("⏹️  收到中断信号，正在关闭...")
    except Exception as e:
        # 🔥 记录详细的异常信息，包括堆栈跟踪
        logger.error(f"❌ Worker异常退出: {e}")
        logger.error(traceback.format_exc())
        # 确保清理资源
        try:
            await worker._cleanup()
        except Exception as cleanup_error:
            logger.error(f"❌ Worker清理资源时出错: {cleanup_error}")
        sys.exit(1)
    finally:
        # 确保 Worker 正确清理资源
        try:
            await worker._cleanup()
        except Exception as cleanup_error:
            logger.error(f"❌ Worker清理资源时出错: {cleanup_error}")

    logger.info("✅ Worker已安全退出")


if __name__ == "__main__":
    asyncio.run(main())
