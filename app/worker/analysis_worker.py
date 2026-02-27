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
from typing import Optional, Dict, Any, List

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


# 🔥 导入状态更新函数（用于退出日志）
def _update_worker_state(**kwargs):
    """更新 Worker 状态（安全调用，不会失败）"""
    try:
        from app.worker.__main__ import update_worker_state
        update_worker_state(**kwargs)
    except Exception:
        pass  # 忽略导入或调用错误


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

        # 关闭标志（防止重复打印）
        self._shutdown_initiated = False

        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理器，优雅关闭"""
        if self._shutdown_initiated:
            # 已经开始关闭，强制退出
            logger.warning("⚠️ 强制退出Worker...")
            sys.exit(1)

        logger.info(f"收到信号 {signum}，准备关闭Worker...")
        self._shutdown_initiated = True
        self.running = False

        # 取消所有正在运行的任务
        for task in self.running_tasks:
            if not task.done():
                task.cancel()

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
            except asyncio.CancelledError:
                # 收到取消信号，立即退出循环
                logger.info("🛑 工作循环收到取消信号")
                break

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

            # 🔥 更新 Worker 状态：任务异常
            try:
                from app.worker.__main__ import get_worker_state
                state = get_worker_state()
                _update_worker_state(
                    error_count=state.get("error_count", 0) + 1,
                    last_error=f"包装器异常 {task_id}: {str(e)[:200]}",
                    status="error_recovered"
                )
            except Exception:
                pass
            
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

        # 🔥 更新 Worker 状态：开始处理任务
        _update_worker_state(
            last_task_id=task_id,
            last_task_time=datetime.now().isoformat(),
            status=f"processing:{stock_code}"
        )

        try:
            # 解析任务参数
            parameters_dict = task_data.get("parameters", {})
            if isinstance(parameters_dict, str):
                import json
                parameters_dict = json.loads(parameters_dict)
            
            # 数据校验：检查股票数据是否存在且新鲜（防止用陈旧数据分析）
            validation_result = await self._validate_task_data(stock_code, parameters_dict)
            if not validation_result.is_valid:
                error_message = validation_result.message
                logger.warning(f"⚠️ 任务 {task_id} 数据校验失败: {error_message}")

                # 更新任务状态为失败
                engine_type_check = parameters_dict.get("engine", "v2")
                if engine_type_check in ("v2", "unified"):
                    try:
                        from app.services.task_analysis_service import get_task_analysis_service
                        from app.utils.timezone import now_tz
                        task_service_tmp = get_task_analysis_service()
                        task_tmp = await task_service_tmp.get_task(task_id)
                        if task_tmp:
                            task_tmp.status = AnalysisStatus.FAILED
                            task_tmp.error_message = error_message
                            task_tmp.completed_at = now_tz()
                            await task_service_tmp._update_task(task_tmp)
                    except Exception as upd_err:
                        logger.error(f"❌ 数据校验失败后更新任务状态出错: {upd_err}")

                # 抛出异常，让上层统一处理（记录日志、释放 current_task 等）
                raise ValueError(error_message)
            
            # 检查引擎类型（默认使用 v2 引擎）
            engine_type = parameters_dict.get("engine", "v2")

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
                    symbol=stock_code,  # 使用 symbol 字段（必填）
                    stock_code=stock_code,  # 保留 stock_code 字段（兼容）
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

            # 🔥 更新 Worker 状态：任务失败
            try:
                from app.worker.__main__ import get_worker_state
                state = get_worker_state()
                _update_worker_state(
                    error_count=state.get("error_count", 0) + 1,
                    last_error=f"{task_id}: {str(e)[:200]}"
                )
            except Exception:
                pass

        finally:
            # 确认任务完成
            try:
                await self.queue_service.ack_task(task_id, success)
            except Exception as e:
                logger.error(f"确认任务失败: {task_id} - {e}")

            # 🔥 更新 Worker 状态：任务完成
            try:
                from app.worker.__main__ import get_worker_state
                state = get_worker_state()
                if success:
                    _update_worker_state(
                        task_count=state.get("task_count", 0) + 1,
                        status="idle"
                    )
                else:
                    _update_worker_state(status="idle")
            except Exception:
                pass

            self.current_task = None

    async def _validate_task_data(
        self,
        stock_code: str,
        parameters_dict: Dict[str, Any]
    ) -> 'DataValidationResult':
        """
        数据准备阶段：主动调用数据源 API 获取最新行情，并保存到 MongoDB。

        只有当 API 调用失败（网络异常/返回空数据）时才认为失败，
        这样可以确保分析始终使用最新数据，而不会因为后台同步服务未完成
        就用陈旧数据进行分析。

        Args:
            stock_code: 股票代码
            parameters_dict: 任务参数字典

        Returns:
            DataValidationResult: 准备结果
        """
        from app.services.data_validation_service import DataValidationResult

        if not stock_code:
            return DataValidationResult(
                is_valid=False,
                message="任务参数中缺少股票代码",
                missing_data=["symbol"],
                details={"error": "股票代码缺失"}
            )

        # 从参数中提取市场类型
        market_type = parameters_dict.get("market_type", "cn")
        market_type_map = {
            "A股": "cn", "港股": "hk", "美股": "us",
            "cn": "cn", "hk": "hk", "us": "us"
        }
        market_type = market_type_map.get(market_type, "cn")

        # 目前只对 A 股做主动拉取（HK/US 可后续扩展）
        if market_type != "cn":
            logger.info(f"ℹ️ 市场类型为 {market_type}，跳过主动数据拉取，使用现有数据")
            return DataValidationResult(
                is_valid=True,
                message=f"非A股市场（{market_type}），跳过主动数据拉取",
                details={"symbol": stock_code, "market_type": market_type, "skipped": True}
            )

        # 获取最近 60 个自然日的日线行情（足够覆盖最新交易日）
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

        # 按优先级获取启用的数据源列表（从数据库配置读取）
        from app.core.data_source_priority import get_enabled_data_sources_async
        all_sources = await get_enabled_data_sources_async("a_shares")

        # 只保留真正的 API 数据源（排除本地缓存类）
        api_sources = [s for s in all_sources if s not in ("local", "mongodb", "local_file")]
        if not api_sources:
            api_sources = ["tushare", "akshare", "baostock"]  # 默认兜底顺序

        logger.info(f"📡 数据准备：将按优先级依次尝试数据源 {api_sources}，获取 {stock_code} 最新行情 ({start_date} → {end_date})")

        # 数据源名称 → provider 获取函数的映射
        def _get_provider(source_name: str):
            if source_name == "tushare":
                from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
                return get_tushare_provider()
            elif source_name == "akshare":
                from tradingagents.dataflows.providers.china.akshare import get_akshare_provider
                return get_akshare_provider()
            elif source_name == "baostock":
                from tradingagents.dataflows.providers.china.baostock import get_baostock_provider
                return get_baostock_provider()
            return None

        from app.services.historical_data_service import HistoricalDataService
        from app.core.database import get_mongo_db

        last_error: str = ""
        for source_name in api_sources:
            try:
                provider = _get_provider(source_name)
                if provider is None:
                    logger.warning(f"⚠️ 数据源 {source_name} 不可用（未找到提供器），跳过")
                    continue

                hist_data = await provider.get_historical_data(stock_code, start_date, end_date, "daily")

                if hist_data is not None and not hist_data.empty:
                    # 成功拿到数据，保存到 MongoDB（覆盖同期旧数据）
                    db = get_mongo_db()
                    hist_service = HistoricalDataService()
                    hist_service.db = db
                    hist_service.collection = db.stock_daily_quotes
                    await hist_service._ensure_indexes()

                    saved_count = await hist_service.save_historical_data(
                        symbol=stock_code,
                        data=hist_data,
                        data_source=source_name,
                        market="CN",
                        period="daily"
                    )
                    logger.info(f"✅ 数据准备完成：{stock_code} 已从 {source_name} 同步 {saved_count} 条最新日线行情")
                    return DataValidationResult(
                        is_valid=True,
                        message=f"数据准备成功，已从 {source_name} 同步 {saved_count} 条最新行情",
                        details={"symbol": stock_code, "fetched_records": saved_count, "source": source_name}
                    )
                else:
                    last_error = f"{source_name} 返回空数据"
                    logger.warning(f"⚠️ 数据准备：{source_name} 未返回 {stock_code} 的行情数据，尝试下一数据源")

            except Exception as e:
                last_error = f"{source_name} 异常：{e}"
                logger.warning(f"⚠️ 数据准备：{source_name} 获取 {stock_code} 失败（{e}），尝试下一数据源")

        # 所有数据源均失败
        logger.error(f"❌ 数据准备失败：所有数据源 {api_sources} 均无法获取 {stock_code} 的行情数据，最后错误：{last_error}")
        return DataValidationResult(
            is_valid=False,
            message=(
                f"所有数据源（{'、'.join(api_sources)}）均未能返回 {stock_code} 的行情数据，"
                f"请确认股票代码正确，并在交易日 18:00 后重试（最后错误：{last_error}）"
            ),
            missing_data=["daily_quotes"],
            details={"symbol": stock_code, "tried_sources": api_sources, "last_error": last_error}
        )
    
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
        """Worker启动时处理未完成的任务（进程重启后）

        新策略：不自动恢复任务，而是标记为"挂起"状态，让用户决定是否继续

        检查两种情况：
        1. Redis队列中标记为"processing"的任务
        2. 数据库中状态为"processing"或"pending"的任务
        """
        try:
            logger.info("🔍 Worker启动：检查未完成的任务...")

            # 1. 清理Redis队列中的处理中任务（不重新入队）
            if self.queue_service:
                # 清空 processing 集合
                processing_tasks = await self.queue_service.r.smembers("queue:processing")
                if processing_tasks:
                    logger.info(f"📋 发现 {len(processing_tasks)} 个Redis处理中任务，将清理...")
                    await self.queue_service.r.delete("queue:processing")

                    # 清理用户处理中计数
                    user_keys = await self.queue_service.r.keys("queue:user:*:processing")
                    if user_keys:
                        await self.queue_service.r.delete(*user_keys)

            # 2. 检查数据库中的未完成任务
            from app.core.database import get_mongo_db_sync
            from app.models.analysis import AnalysisStatus

            db = get_mongo_db_sync()
            collection = db["unified_analysis_tasks"]

            # 查找所有"processing"或"pending"状态的任务
            unfinished_tasks = collection.find({
                "status": {"$in": [
                    AnalysisStatus.PROCESSING.value,
                    AnalysisStatus.PENDING.value
                ]}
            })

            suspended_count = 0
            user_notifications = {}  # 用户ID -> 任务列表

            for task_doc in unfinished_tasks:
                task_id = task_doc.get("task_id")
                user_id = task_doc.get("user_id")
                symbol = task_doc.get("symbol", "未知")

                if not task_id:
                    continue

                try:
                    # 标记为挂起状态
                    logger.info(f"⏸️ 将任务标记为挂起: {task_id} ({symbol})")
                    collection.update_one(
                        {"task_id": task_id},
                        {
                            "$set": {
                                "status": AnalysisStatus.SUSPENDED.value,
                                "error_message": "服务重启，任务已挂起。请手动恢复或取消任务。",
                                "suspended_at": datetime.utcnow()
                            }
                        }
                    )

                    # 从Redis队列中移除（如果存在）
                    if self.queue_service:
                        await self.queue_service.r.lrem("queue:ready", 0, task_id)
                        await self.queue_service.r.delete(f"queue:task:{task_id}")

                    suspended_count += 1

                    # 收集用户通知信息
                    if user_id:
                        if user_id not in user_notifications:
                            user_notifications[user_id] = []
                        user_notifications[user_id].append({
                            "task_id": task_id,
                            "symbol": symbol,
                            "created_at": task_doc.get("created_at")
                        })

                except Exception as e:
                    logger.error(f"标记任务为挂起失败: {task_id} - {e}")

            # 发送通知给用户
            if user_notifications:
                await self._send_suspended_task_notifications(user_notifications)

            if suspended_count > 0:
                logger.warning(f"⏸️ 已将 {suspended_count} 个未完成任务标记为挂起状态")
                logger.info(f"💡 用户可以在任务列表中手动恢复或取消这些任务")
            else:
                logger.info("✅ 没有发现未完成的任务")

        except Exception as e:
            logger.error(f"处理未完成任务失败: {e}")
            logger.error(traceback.format_exc())

    async def _send_suspended_task_notifications(self, user_notifications: Dict[str, List[Dict]]):
        """发送挂起任务通知给用户"""
        try:
            from app.core.database import get_mongo_db_sync

            db = get_mongo_db_sync()
            notifications_collection = db["notifications"]

            for user_id, tasks in user_notifications.items():
                task_count = len(tasks)
                task_list = "\n".join([
                    f"- {task['symbol']} (任务ID: {task['task_id'][:8]}...)"
                    for task in tasks[:5]  # 最多显示5个
                ])

                if task_count > 5:
                    task_list += f"\n... 还有 {task_count - 5} 个任务"

                notification = {
                    "user_id": user_id,
                    "type": "system",
                    "title": "服务重启通知",
                    "message": f"检测到 {task_count} 个未完成的分析任务已被挂起：\n\n{task_list}\n\n请在任务列表中查看并决定是否继续分析。",
                    "level": "warning",
                    "read": False,
                    "created_at": datetime.utcnow(),
                    "data": {
                        "suspended_tasks": [task["task_id"] for task in tasks]
                    }
                }

                notifications_collection.insert_one(notification)
                logger.info(f"📧 已发送挂起任务通知给用户: {user_id} ({task_count} 个任务)")

        except Exception as e:
            logger.error(f"发送挂起任务通知失败: {e}")

    async def _cleanup(self):
        """清理资源"""
        logger.info(f"🧹 清理Worker资源: {self.worker_id}")

        # 等待所有正在运行的任务完成（最多等待10秒）
        if self.running_tasks:
            logger.info(f"⏳ 等待 {len(self.running_tasks)} 个任务完成...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.running_tasks, return_exceptions=True),
                    timeout=10.0
                )
                logger.info("✅ 所有任务已完成")
            except asyncio.TimeoutError:
                logger.warning("⚠️ 等待任务超时，强制取消剩余任务")
                for task in self.running_tasks:
                    if not task.done():
                        task.cancel()
            except Exception as e:
                logger.error(f"等待任务完成时出错: {e}")

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
