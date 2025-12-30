"""
统一分析服务

将所有分析入口统一到 WorkflowEngine + WorkflowBuilder
支持：
1. 单股分析 API
2. 批量分析 API
3. 前端工作流调试
4. 定时分析任务
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.utils.timezone import now_tz

from app.models.analysis import (
    AnalysisParameters,
    AnalysisResult,
    AnalysisStatus,
    AnalysisTask,
    AnalysisTaskType,
    SingleAnalysisRequest,
    UnifiedAnalysisTask,
)
from app.services.memory_state_manager import (
    get_memory_state_manager,
    TaskStatus,
)
from core.workflow.default_workflow_provider import (
    DefaultWorkflowProvider,
    get_default_workflow_provider,
)
from core.workflow.engine import WorkflowEngine
from core.workflow.models import WorkflowDefinition

logger = logging.getLogger(__name__)


class UnifiedAnalysisService:
    """
    统一分析服务

    所有分析入口都通过此服务执行，使用 WorkflowEngine 作为执行引擎。

    用法:
        service = UnifiedAnalysisService()

        # 单股分析
        result = await service.analyze(
            stock_code="000858",
            analysis_date="2024-01-15",
            progress_callback=lambda p, m, **kw: print(f"{p}% - {m}")
        )

        # 使用指定工作流
        result = await service.analyze(
            stock_code="AAPL",
            workflow_id="my_custom_workflow",
        )
    """

    def __init__(self):
        self._workflow_provider = get_default_workflow_provider()
        self._db = None

    def _get_db(self):
        """获取数据库连接（懒加载）"""
        if self._db is None:
            try:
                from pymongo import MongoClient
                from app.core.config import settings
                client = MongoClient(settings.MONGO_URI)
                self._db = client[settings.MONGO_DB]
            except Exception as e:
                logger.warning(f"无法连接数据库: {e}")
        return self._db

    def _build_legacy_config(
        self,
        parameters: Optional[AnalysisParameters] = None,
    ) -> Dict[str, Any]:
        """
        构建遗留配置（用于 WorkflowBuilder 创建 Agent）

        从数据库读取 LLM 配置，合并用户参数
        """
        config = {}

        # 从数据库获取 LLM 配置
        db = self._get_db()
        if db is not None:
            try:
                # 获取活动的系统配置
                system_config = db.system_configs.find_one(
                    {"is_active": True},
                    sort=[("version", -1)]
                )
                if system_config:
                    config["llm_provider"] = system_config.get("llm_provider", "dashscope")
                    config["deep_think_llm"] = system_config.get("deep_think_llm", "qwen-plus")
                    config["quick_think_llm"] = system_config.get("quick_think_llm", "qwen-turbo")
            except Exception as e:
                logger.warning(f"从数据库获取配置失败: {e}")

        # 合并用户参数
        if parameters:
            if parameters.research_depth:
                # 保持research_depth为字符串值，用于workflow inputs
                config["research_depth"] = parameters.research_depth

            if parameters.selected_analysts:
                config["selected_analysts"] = parameters.selected_analysts

            if parameters.market_type:
                config["market_type"] = parameters.market_type

        return config

    def _build_workflow_inputs(
        self,
        stock_code: str,
        analysis_date: str,
        workflow: WorkflowDefinition,
        parameters: Optional[AnalysisParameters] = None,
    ) -> Dict[str, Any]:
        research_depth = "标准"
        if parameters and getattr(parameters, "research_depth", None):
            research_depth = parameters.research_depth

        depth_mapping = {
            "快速": {"debate": 1, "risk": 1},
            "基础": {"debate": 1, "risk": 1},
            "标准": {"debate": 1, "risk": 2},
            "深度": {"debate": 2, "risk": 2},
            "全面": {"debate": 3, "risk": 3},
        }
        depth_config = depth_mapping.get(research_depth, depth_mapping["标准"])

        inputs: Dict[str, Any] = {
            "ticker": stock_code,
            "company_of_interest": stock_code,
            "analysis_date": analysis_date,
            "trade_date": analysis_date,
            "research_depth": research_depth,
            "_max_debate_rounds": depth_config["debate"],
            "_max_risk_rounds": depth_config["risk"],
            "messages": [],
        }

        if workflow.config:
            inputs.update({k: v for k, v in workflow.config.items() if k not in inputs})

        return inputs

    async def analyze(
        self,
        stock_code: str,
        analysis_date: Optional[str] = None,
        workflow_id: Optional[str] = None,
        parameters: Optional[AnalysisParameters] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行股票分析

        Args:
            stock_code: 股票代码
            analysis_date: 分析日期，默认今天
            workflow_id: 工作流 ID，None 则使用活动工作流
            parameters: 分析参数
            progress_callback: 进度回调函数
            task_id: 任务 ID，用于进度跟踪

        Returns:
            分析结果字典
        """
        # 生成任务 ID
        task_id = task_id or str(uuid.uuid4())

        # 设置默认日期
        if not analysis_date:
            analysis_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"开始分析: {stock_code} @ {analysis_date}, workflow={workflow_id}")

        try:
            # 1. 加载工作流
            workflow = self._workflow_provider.load_workflow(workflow_id)
            logger.info(f"已加载工作流: {workflow.id} - {workflow.name}")

            # 2. 构建配置
            legacy_config = self._build_legacy_config(parameters)

            # 3. 创建引擎
            engine = WorkflowEngine(
                legacy_config=legacy_config,
                task_id=task_id,
            )

            # 4. 加载并编译工作流
            engine.load(workflow)

            # 5. 准备输入
            inputs = self._build_workflow_inputs(
                stock_code=stock_code,
                analysis_date=analysis_date,
                workflow=workflow,
                parameters=parameters,
            )

            # 6. 执行工作流
            result = await engine.execute_async(
                inputs=inputs,
                progress_callback=progress_callback,
            )

            logger.info(f"分析完成: {stock_code}, task_id={task_id}")

            # 7. 格式化结果
            return self._format_result(result, stock_code, analysis_date, task_id, parameters)

        except Exception as e:
            logger.error(f"分析失败: {stock_code}, error={e}")
            return {
                "success": False,
                "task_id": task_id,
                "stock_code": stock_code,
                "error": str(e),
            }

    def analyze_sync(
        self,
        stock_code: str,
        analysis_date: Optional[str] = None,
        workflow_id: Optional[str] = None,
        parameters: Optional[AnalysisParameters] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        同步执行股票分析

        用于在线程池中执行，避免阻塞事件循环
        """
        task_id = task_id or str(uuid.uuid4())

        if not analysis_date:
            analysis_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"[同步] 开始分析: {stock_code} @ {analysis_date}")

        try:
            # 1. 加载工作流
            workflow = self._workflow_provider.load_workflow(workflow_id)

            # 2. 构建配置
            legacy_config = self._build_legacy_config(parameters)

            # 3. 创建引擎
            engine = WorkflowEngine(
                legacy_config=legacy_config,
                task_id=task_id,
            )

            # 4. 加载并编译工作流
            engine.load(workflow)

            # 5. 准备输入
            inputs = self._build_workflow_inputs(
                stock_code=stock_code,
                analysis_date=analysis_date,
                workflow=workflow,
                parameters=parameters,
            )

            # 6. 同步执行
            result = engine.execute(
                inputs=inputs,
                progress_callback=progress_callback,
            )

            logger.info(f"[同步] 分析完成: {stock_code}")
            return self._format_result(result, stock_code, analysis_date, task_id, parameters)

        except Exception as e:
            logger.error(f"[同步] 分析失败: {stock_code}, error={e}")
            return {
                "success": False,
                "task_id": task_id,
                "stock_code": stock_code,
                "error": str(e),
            }

    def _format_result(
        self,
        raw_result: Dict[str, Any],
        stock_code: str,
        analysis_date: str,
        task_id: str,
        parameters: Optional[AnalysisParameters] = None,
    ) -> Dict[str, Any]:
        """
        格式化分析结果 - 使用公共工具与 SimpleAnalysisService 保持一致

        包含所有报告类型：
        - 基础报告：market_report, sentiment_report, news_report, fundamentals_report
        - 交易计划：investment_plan, trader_investment_plan, final_trade_decision
        - 研究团队：bull_researcher, bear_researcher, research_team_decision
        - 风险团队：risky_analyst, safe_analyst, neutral_analyst, risk_management_decision
        """
        from app.utils.report_formatter import format_analysis_result

        # 从 parameters 中提取模型信息和分析师信息
        if parameters:
            analysts = parameters.selected_analysts or ["market", "fundamentals"]
            research_depth = parameters.research_depth or "标准"
            quick_model = getattr(parameters, 'quick_analysis_model', None) or getattr(parameters, 'quick_model', None) or "Unknown"
            deep_model = getattr(parameters, 'deep_analysis_model', None) or getattr(parameters, 'deep_model', None) or "Unknown"
        else:
            analysts = ["market", "fundamentals"]
            research_depth = "标准"
            quick_model = "Unknown"
            deep_model = "Unknown"

        # 使用公共工具格式化结果
        result = format_analysis_result(
            raw_result=raw_result,
            stock_code=stock_code,
            stock_name=self._resolve_stock_name(stock_code),
            analysis_date=analysis_date,
            task_id=task_id,
            analysts=analysts,
            research_depth=research_depth,
            quick_model=quick_model,
            deep_model=deep_model,
        )

        logger.info(f"✅ [统一引擎] 格式化结果完成: reports={len(result.get('reports', {}))}个")
        return result

    async def analyze_batch(
        self,
        stock_codes: List[str],
        analysis_date: Optional[str] = None,
        workflow_id: Optional[str] = None,
        parameters: Optional[AnalysisParameters] = None,
        progress_callback: Optional[Callable] = None,
        max_concurrent: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        批量分析股票

        Args:
            stock_codes: 股票代码列表
            analysis_date: 分析日期
            workflow_id: 工作流 ID
            parameters: 分析参数
            progress_callback: 进度回调
            max_concurrent: 最大并发数

        Returns:
            分析结果列表
        """
        results = []
        total = len(stock_codes)
        completed = 0

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_one(code: str, index: int) -> Dict[str, Any]:
            nonlocal completed
            async with semaphore:
                task_id = f"batch_{uuid.uuid4().hex[:8]}_{index}"

                # 单股进度回调
                def single_progress(progress, message, **kwargs):
                    if progress_callback:
                        # 计算总体进度
                        overall = (completed * 100 + progress) / total
                        progress_callback(
                            overall,
                            f"[{index+1}/{total}] {code}: {message}",
                            stock_code=code,
                            **kwargs
                        )

                result = await self.analyze(
                    stock_code=code,
                    analysis_date=analysis_date,
                    workflow_id=workflow_id,
                    parameters=parameters,
                    progress_callback=single_progress,
                    task_id=task_id,
                )

                completed += 1
                return result

        # 并发执行
        tasks = [
            analyze_one(code, i)
            for i, code in enumerate(stock_codes)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "success": False,
                    "stock_code": stock_codes[i],
                    "error": str(result),
                })
            else:
                final_results.append(result)

        return final_results


    async def execute_analysis_for_ab_test(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest,
        progress_tracker=None,
    ) -> Dict[str, Any]:
        """
        为 AB 测试提供的分析执行入口

        与 SimpleAnalysisService.execute_analysis_background() 接口兼容
        使用 WorkflowEngine 替代 TradingAgentsGraph

        Args:
            task_id: 任务 ID
            user_id: 用户 ID
            request: 分析请求
            progress_tracker: RedisProgressTracker 实例（可选，如不提供会自动创建）

        Returns:
            分析结果
        """
        import asyncio
        from app.services.progress.tracker import RedisProgressTracker

        stock_code = request.get_symbol()
        parameters = request.parameters
        memory_manager = get_memory_state_manager()

        try:
            logger.info(f"🔄 [AB测试-统一引擎] 开始分析: {stock_code}, task_id={task_id}")

            # 🔥 更新内存管理器状态为 RUNNING
            await memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=5,
                message="🚀 [统一引擎] 正在启动分析...",
                current_step="启动"
            )

            # 如果没有传入 progress_tracker，则自己创建
            if progress_tracker is None:
                def create_progress_tracker():
                    return RedisProgressTracker(
                        task_id=task_id,
                        analysts=parameters.selected_analysts if parameters else ["market", "fundamentals"],
                        research_depth=parameters.research_depth if parameters else "标准",
                        llm_provider="dashscope"
                    )
                progress_tracker = await asyncio.to_thread(create_progress_tracker)

            # 创建进度回调适配器
            def progress_callback(progress: float, message: str, **kwargs):
                """将统一引擎的进度回调转换为 RedisProgressTracker 格式"""
                if progress_tracker:
                    try:
                        # 🔑 关键：从 kwargs 中提取 step_name（简短名称）
                        step_name = kwargs.get("step_name", "")

                        progress_tracker.update_progress({
                            "progress_percentage": progress,
                            "last_message": message,
                            "current_step_name": step_name,  # ✅ 简短的步骤名称
                            "current_step_description": message,  # ✅ 详细的描述
                            **kwargs
                        })
                        # 🔥 同时更新内存管理器（使用 asyncio.create_task 避免事件循环冲突）
                        import asyncio
                        try:
                            # 获取当前运行的事件循环
                            loop = asyncio.get_running_loop()
                            # 创建后台任务，不等待完成
                            loop.create_task(
                                memory_manager.update_task_status(
                                    task_id=task_id,
                                    status=TaskStatus.RUNNING,
                                    progress=int(progress),
                                    message=message,
                                    current_step=step_name or message  # ✅ 使用 step_name 而不是 message
                                )
                            )
                        except RuntimeError:
                            # 如果没有运行的事件循环，跳过内存管理器更新
                            logger.debug("没有运行的事件循环，跳过内存管理器更新")
                    except Exception as e:
                        logger.warning(f"进度更新失败: {e}")

            # 获取分析日期
            analysis_date = None
            if parameters and parameters.analysis_date:
                if isinstance(parameters.analysis_date, datetime):
                    analysis_date = parameters.analysis_date.strftime("%Y-%m-%d")
                else:
                    analysis_date = str(parameters.analysis_date)[:10]

            # 获取工作流 ID
            workflow_id = None
            if parameters and hasattr(parameters, "workflow_id"):
                workflow_id = parameters.workflow_id

            # 初始化进度
            await asyncio.to_thread(
                progress_tracker.update_progress,
                {"progress_percentage": 10, "last_message": "🚀 [统一引擎] 开始股票分析"}
            )

            # 🔥 更新内存管理器状态
            await memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=10,
                message="🚀 [统一引擎] 开始股票分析",
                current_step="开始分析"
            )

            # 调用统一分析服务（已在 _format_result 中填充所有字段）
            result = await self.analyze(
                stock_code=stock_code,
                analysis_date=analysis_date,
                workflow_id=workflow_id,
                parameters=parameters,
                progress_callback=progress_callback,
                task_id=task_id,
            )

            # 分析完成，标记进度
            # 注意：mark_completed() 不接受参数
            await asyncio.to_thread(progress_tracker.mark_completed)

            # 保存分析结果到数据库
            await self._save_analysis_result(task_id, user_id, stock_code, result, parameters)

            # 🔥 更新内存管理器状态为 COMPLETED
            await memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                message="✅ 分析完成",
                current_step="完成",
                result_data=result
            )

            logger.info(f"✅ [AB测试-统一引擎] 分析完成: {stock_code}")
            return result

        except Exception as e:
            logger.error(f"❌ [AB测试-统一引擎] 分析失败: {stock_code}, error={e}")

            # 标记进度跟踪器失败
            if progress_tracker:
                try:
                    await asyncio.to_thread(progress_tracker.mark_failed, str(e))
                except Exception:
                    pass

            # 🔥 更新内存管理器状态为 FAILED
            await memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                message=f"❌ 分析失败: {str(e)}",
                error_message=str(e)
            )

            # 更新数据库状态为失败
            await self._update_task_failed(task_id, str(e))
            raise

    async def execute_analysis_for_v2_engine(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest,
        progress_tracker=None,
    ) -> Dict[str, Any]:
        import asyncio
        from app.services.progress.tracker import RedisProgressTracker

        stock_code = request.get_symbol()
        parameters = request.parameters
        memory_manager = get_memory_state_manager()

        try:
            await memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=5,
                message="🚀 [v2.0引擎] 正在启动分析...",
                current_step="启动"
            )

            if progress_tracker is None:
                def create_progress_tracker():
                    return RedisProgressTracker(
                        task_id=task_id,
                        analysts=parameters.selected_analysts if parameters else ["market", "fundamentals"],
                        research_depth=parameters.research_depth if parameters else "标准",
                        llm_provider="dashscope"
                    )
                progress_tracker = await asyncio.to_thread(create_progress_tracker)

            def progress_callback(progress: float, message: str, **kwargs):
                if progress_tracker:
                    try:
                        progress_tracker.update_progress({
                            "progress_percentage": progress,
                            "last_message": message,
                            **kwargs
                        })
                        import asyncio
                        try:
                            # 获取当前运行的事件循环
                            loop = asyncio.get_running_loop()
                            # 创建后台任务，不等待完成
                            loop.create_task(
                                memory_manager.update_task_status(
                                    task_id=task_id,
                                    status=TaskStatus.RUNNING,
                                    progress=int(progress),
                                    message=message,
                                    current_step=kwargs.get("step", "分析中")
                                )
                            )
                        except RuntimeError:
                            # 如果没有运行的事件循环，跳过内存管理器更新
                            logger.debug("没有运行的事件循环，跳过内存管理器更新")
                    except Exception as e:
                        logger.warning(f"进度更新失败: {e}")

            analysis_date = None
            if parameters and parameters.analysis_date:
                if isinstance(parameters.analysis_date, datetime):
                    analysis_date = parameters.analysis_date.strftime("%Y-%m-%d")
                else:
                    analysis_date = str(parameters.analysis_date)[:10]

            workflow_id = None
            if parameters and hasattr(parameters, "workflow_id"):
                workflow_id = parameters.workflow_id
            if not workflow_id:
                workflow_id = self._workflow_provider.get_active_workflow_id()

            try:
                wf = self._workflow_provider.load_workflow(workflow_id)
                tags = getattr(wf, "tags", []) or []
                wf_id = str(getattr(wf, "id", "") or "")
                wf_name = str(getattr(wf, "name", "") or "")
                wf_version = str(getattr(wf, "version", "") or "")
                is_v2 = (
                    "v2.0" in tags
                    or wf_id.endswith("_v2")
                    or "v2.0" in wf_name
                    or wf_version.startswith("2.")
                )
                if not is_v2:
                    workflow_id = "v2_stock_analysis"
            except Exception:
                workflow_id = "v2_stock_analysis"

            await asyncio.to_thread(
                progress_tracker.update_progress,
                {"progress_percentage": 10, "last_message": "🚀 [v2.0引擎] 开始股票分析"}
            )

            await memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=10,
                message="🚀 [v2.0引擎] 开始股票分析",
                current_step="开始分析"
            )


            result = await self.analyze(
                stock_code=stock_code,
                analysis_date=analysis_date,
                workflow_id=workflow_id,
                parameters=parameters,
                progress_callback=progress_callback,
                task_id=task_id,
            )

            await asyncio.to_thread(progress_tracker.mark_completed)
            await self._save_analysis_result(task_id, user_id, stock_code, result, parameters)

            await memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                message="✅ 分析完成",
                current_step="完成",
                result_data=result
            )

            return result
        except Exception as e:
            logger.error(f"❌ [v2.0引擎] 分析失败: {stock_code}, error={e}")
            if progress_tracker:
                try:
                    await asyncio.to_thread(progress_tracker.mark_failed, str(e))
                except Exception:
                    pass
            await memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                message=f"❌ 分析失败: {str(e)}",
                error_message=str(e)
            )
            await self._update_task_failed(task_id, str(e))
            raise

    async def _save_analysis_result(
        self,
        task_id: str,
        user_id: str,
        stock_code: str,
        result: Dict[str, Any],
        parameters=None
    ):
        """
        保存分析结果到 MongoDB - 与 SimpleAnalysisService 保持一致的格式
        """
        db = self._get_db()
        if db is None:
            logger.warning("无法保存分析结果：数据库未连接")
            return

        try:
            timestamp = now_tz()  # ✅ 使用 now_tz() 确保带时区信息
            analysis_id = result.get("analysis_id", str(uuid.uuid4()))

            # 获取股票名称
            stock_name = self._resolve_stock_name(stock_code)
            market_type = "A股" if stock_code.isdigit() and len(stock_code) == 6 else "美股"

            # 更新 analysis_tasks 状态
            db.analysis_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": "completed",
                        "progress": 100,
                        "completed_at": timestamp,
                        "updated_at": timestamp,
                        # 🔥 保存完整的 result 到 analysis_tasks（与 SimpleAnalysisService 一致）
                        "result": {
                            "analysis_id": analysis_id,
                            "stock_symbol": stock_code,
                            "stock_code": stock_code,
                            "analysis_date": result.get("analysis_date"),
                            "summary": result.get("summary", ""),
                            "recommendation": result.get("recommendation", ""),
                            "confidence_score": result.get("confidence_score", 0.0),
                            "risk_level": result.get("risk_level", "中等"),
                            "key_points": result.get("key_points", []),
                            "detailed_analysis": result.get("detailed_analysis", {}),
                            "execution_time": result.get("execution_time", 0),
                            "tokens_used": result.get("tokens_used", 0),
                            "reports": result.get("reports", {}),
                            "decision": result.get("decision", {}),
                        }
                    }
                }
            )

            # 🔥 保存到 analysis_reports（与 SimpleAnalysisService 格式一致）
            document = {
                "analysis_id": analysis_id,
                "stock_symbol": stock_code,
                "stock_name": result.get("stock_name", stock_name),  # 优先使用 result 中的名称
                "market_type": market_type,
                "model_info": result.get("model_info", "Unknown"),
                "quick_model": result.get("quick_model", "Unknown"),  # 🔥 添加快速模型字段
                "deep_model": result.get("deep_model", "Unknown"),    # 🔥 添加深度模型字段
                "analysis_date": timestamp.strftime('%Y-%m-%d'),
                "timestamp": timestamp,
                "status": "completed",
                "source": "api",
                "engine": (getattr(parameters, "engine", None) or "unified"),

                # 分析结果摘要
                "summary": result.get("summary", ""),
                "analysts": result.get("analysts", []),
                "research_depth": result.get("research_depth", "标准"),

                # 报告内容
                "reports": result.get("reports", {}),

                # 🔥 关键：decision 字段
                "decision": result.get("decision", {}),

                # 元数据
                "task_id": task_id,
                "user_id": user_id,
                "created_at": timestamp,
                "updated_at": timestamp,

                # 其他字段
                "recommendation": result.get("recommendation", ""),
                "confidence_score": result.get("confidence_score", 0.0),
                "risk_level": result.get("risk_level", "中等"),
                "key_points": result.get("key_points", []),
                "execution_time": result.get("execution_time", 0),
                "tokens_used": result.get("tokens_used", 0),
            }

            db.analysis_reports.update_one(
                {"task_id": task_id},
                {"$set": document},
                upsert=True
            )
            logger.info(f"✅ 分析结果已保存到数据库: {task_id}")
            logger.debug(f"📊 保存的 decision: {result.get('decision', {})}")
        except Exception as e:
            logger.error(f"❌ 保存分析结果失败: {e}")

    def _resolve_stock_name(self, stock_code: str) -> str:
        """解析股票名称 - 与 SimpleAnalysisService 一致的逻辑"""
        if not stock_code:
            return ""

        try:
            # 优先尝试从 data_source_manager 获取结构化数据
            try:
                from tradingagents.dataflows.data_source_manager import get_china_stock_info_unified as get_info_dict
                info_dict = get_info_dict(stock_code)
                if info_dict and isinstance(info_dict, dict) and info_dict.get('name'):
                    return info_dict['name']
            except Exception:
                pass

            # 备用方案：从 interface 获取字符串并解析
            from tradingagents.dataflows.interface import get_china_stock_info_unified
            info_str = get_china_stock_info_unified(stock_code)

            if info_str and isinstance(info_str, str) and "股票名称:" in info_str:
                stock_name = info_str.split("股票名称:")[1].split("\n")[0].strip()
                if stock_name:
                    return stock_name
            elif info_str and isinstance(info_str, dict) and info_str.get("name"):
                return info_str["name"]

        except Exception as e:
            logger.warning(f"⚠️ 解析股票名称失败: {stock_code} - {e}")

        return f"股票{stock_code}"

    # ==================== 持仓分析相关方法 ====================

    async def create_position_analysis_task(
        self,
        user_id: str,
        code: str,
        market: str = "CN",
        task_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建持仓分析任务

        Args:
            user_id: 用户ID
            code: 股票代码
            market: 市场类型 (CN/HK/US)
            task_params: 任务参数

        Returns:
            任务信息字典
        """
        logger.info(f"🔧 [持仓分析服务] create_position_analysis_task 被调用: user_id={user_id}, code={code}, market={market}")
        from bson import ObjectId
        from app.core.database import get_mongo_db

        task_id = str(uuid.uuid4())
        logger.info(f"📝 [持仓分析服务] 生成任务ID: {task_id}")
        task_params = task_params or {}

        # 创建统一分析任务
        logger.info(f"🔄 [持仓分析服务] 创建 UnifiedAnalysisTask 对象...")
        task = UnifiedAnalysisTask(
            task_id=task_id,
            user_id=ObjectId(user_id),
            task_type=AnalysisTaskType.POSITION_ANALYSIS,
            task_params={
                "code": code,
                "market": market,
                **task_params
            },
            engine_type="v2",  # 使用 v2.0 引擎
            status=AnalysisStatus.PENDING,
            created_at=now_tz(),  # ✅ 使用 now_tz() 确保带时区信息
        )

        # 保存到数据库
        logger.info(f"💾 [持仓分析服务] 准备保存到数据库...")
        try:
            db = get_mongo_db()
            task_dict = task.model_dump(by_alias=True, exclude={"id"})

            # ✅ 确保 user_id 是 ObjectId 类型，不是字符串
            if 'user_id' in task_dict and isinstance(task_dict['user_id'], str):
                task_dict['user_id'] = ObjectId(task_dict['user_id'])
                logger.info(f"🔄 [持仓分析服务] 转换 user_id 从字符串到 ObjectId: {task_dict['user_id']}")

            logger.info(f"💾 [持仓分析服务] 保存文档: user_id={task_dict.get('user_id')} (类型: {type(task_dict.get('user_id'))})")

            await db.unified_analysis_tasks.insert_one(task_dict)
            logger.info(f"✅ [持仓分析服务] 已保存到数据库，任务ID: {task_id}")
            logger.info(f"✅ [持仓分析服务] 任务已创建: {task_id} - {code}")
        except Exception as e:
            logger.error(f"❌ [持仓分析] 保存任务失败: {e}")
            raise

        # 保存到内存状态管理器
        logger.info(f"💾 [持仓分析服务] 准备保存到内存状态管理器...")
        memory_manager = get_memory_state_manager()
        await memory_manager.create_task(
            task_id=task_id,
            user_id=user_id,
            stock_code=code,
            stock_name=f"{code} 持仓分析",
            parameters=task_params,
        )
        logger.info(f"✅ [持仓分析服务] 已保存到内存状态管理器")

        logger.info(f"🎉 [持仓分析服务] 任务创建完成，准备返回结果")
        return {
            "task_id": task_id,
            "code": code,
            "market": market,
            "status": "pending",
            "message": "持仓分析任务已创建，预计需要2-5分钟",
            "created_at": task.created_at.isoformat()
        }

    async def execute_position_analysis(
        self,
        task_id: str,
        user_id: str,
        code: str,
        market: str = "CN",
        task_params: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """执行持仓分析

        Args:
            task_id: 任务ID
            user_id: 用户ID
            code: 股票代码
            market: 市场类型
            task_params: 任务参数
            progress_callback: 进度回调函数

        Returns:
            分析结果字典
        """
        logger.info(f"🚀 [持仓分析服务] execute_position_analysis 被调用: task_id={task_id}, code={code}")
        logger.info(f"📋 [持仓分析服务] 任务参数: {task_params}")

        try:
            # 更新任务状态为处理中
            await self._update_position_task_status(
                task_id=task_id,
                status=AnalysisStatus.PROCESSING,
                message="正在分析持仓..."
            )

            # 调用持仓分析服务
            from app.services.portfolio_service import get_portfolio_service
            from app.models.portfolio import PositionAnalysisByCodeRequest

            portfolio_service = get_portfolio_service()

            # 构建分析请求
            task_params = task_params or {}
            analysis_request = PositionAnalysisByCodeRequest(
                code=code,
                market=market,
                research_depth=task_params.get("research_depth", "标准"),
                include_add_position=task_params.get("include_add_position", True),
                target_profit_pct=task_params.get("target_profit_pct", 20.0),
                total_capital=task_params.get("total_capital"),
                max_position_pct=task_params.get("max_position_pct", 30.0),
                max_loss_pct=task_params.get("max_loss_pct", 10.0),
                risk_tolerance=task_params.get("risk_tolerance", "medium"),
                investment_horizon=task_params.get("investment_horizon", "medium"),
                analysis_focus=task_params.get("analysis_focus", "comprehensive"),
                position_type=task_params.get("position_type", "real"),
            )

            # 执行分析
            report = await portfolio_service.analyze_position_by_code(
                user_id=user_id,
                code=code,
                market=market,
                params=analysis_request
            )

            # 格式化结果
            result = {
                "success": True,
                "task_id": task_id,
                "code": code,
                "market": market,
                "analysis_id": report.analysis_id,
                "position_snapshot": report.position_snapshot.model_dump() if report.position_snapshot else None,
                "ai_analysis": report.ai_analysis.model_dump() if report.ai_analysis else None,
                "status": report.status.value,
                "execution_time": report.execution_time,
                "error_message": report.error_message,
            }

            # 更新任务状态为完成
            await self._update_position_task_status(
                task_id=task_id,
                status=AnalysisStatus.COMPLETED if report.status.value == "completed" else AnalysisStatus.FAILED,
                message="持仓分析完成" if report.status.value == "completed" else report.error_message,
                result=result
            )

            logger.info(f"✅ [持仓分析] 执行完成: {task_id} - {code}")
            return result

        except Exception as e:
            logger.error(f"❌ [持仓分析] 执行失败: {task_id} - {e}", exc_info=True)

            # 更新任务状态为失败
            await self._update_position_task_status(
                task_id=task_id,
                status=AnalysisStatus.FAILED,
                message=f"持仓分析失败: {str(e)}"
            )

            return {
                "success": False,
                "task_id": task_id,
                "code": code,
                "error": str(e),
            }

    async def _update_position_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ):
        """更新持仓分析任务状态"""
        from app.core.database import get_mongo_db

        try:
            db = get_mongo_db()

            update_data = {
                "status": status.value if hasattr(status, "value") else status,  # 确保存储为字符串值
                "message": message,
                "updated_at": now_tz(),  # ✅ 使用 now_tz() 确保带时区信息
            }

            if status == AnalysisStatus.PROCESSING:
                update_data["started_at"] = now_tz()  # ✅ 使用 now_tz() 确保带时区信息
            elif status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]:
                update_data["completed_at"] = now_tz()  # ✅ 使用 now_tz() 确保带时区信息

            if result is not None:
                update_data["result"] = result

            await db.unified_analysis_tasks.update_one(
                {"task_id": task_id},
                {"$set": update_data}
            )

            # 更新内存状态
            memory_manager = get_memory_state_manager()
            memory_status = TaskStatus.RUNNING if status == AnalysisStatus.PROCESSING else (
                TaskStatus.COMPLETED if status == AnalysisStatus.COMPLETED else TaskStatus.FAILED
            )
            await memory_manager.update_task_status(
                task_id=task_id,
                status=memory_status,
                message=message or "",
            )

        except Exception as e:
            logger.error(f"❌ [持仓分析] 更新任务状态失败: {e}")

    async def _update_task_failed(self, task_id: str, error_message: str):
        """更新任务状态为失败"""
        db = self._get_db()
        if db is None:
            return

        try:
            db.analysis_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": error_message,
                        "completed_at": now_tz(),  # ✅ 使用 now_tz() 确保带时区信息
                        "updated_at": now_tz(),  # ✅ 使用 now_tz() 确保带时区信息
                    }
                }
            )
        except Exception as e:
            logger.error(f"❌ 更新任务状态失败: {e}")


# 单例实例
_unified_service: Optional[UnifiedAnalysisService] = None


def get_unified_analysis_service() -> UnifiedAnalysisService:
    """获取统一分析服务单例"""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedAnalysisService()
    return _unified_service
