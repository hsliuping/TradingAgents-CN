"""
任务分析服务

基于 UnifiedAnalysisTask 模型的分析任务管理服务
提供统一的任务创建、执行、查询接口
"""

from typing import Dict, Any, Optional, List, Callable, Union
import logging
import uuid
import asyncio
from datetime import datetime

from app.models.analysis import (
    UnifiedAnalysisTask,
    AnalysisTaskType,
    AnalysisStatus
)
from app.models.user import PyObjectId
from app.services.unified_analysis_engine import UnifiedAnalysisEngine
from app.services.workflow_registry import AnalysisWorkflowRegistry
from app.core.database import get_mongo_db
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)


class TaskAnalysisService:
    """任务分析服务
    
    基于 UnifiedAnalysisTask 模型的分析任务管理
    
    使用示例:
        service = TaskAnalysisService()
        
        # 创建并执行任务
        task = await service.create_and_execute_task(
            user_id=user_id,
            task_type=AnalysisTaskType.STOCK_ANALYSIS,
            task_params={"symbol": "000858", "market_type": "cn"}
        )
        
        # 查询任务
        task = await service.get_task(task_id)
        
        # 查询用户的所有任务
        tasks = await service.list_user_tasks(user_id)
    """
    
    def __init__(self):
        """初始化服务"""
        self.engine = UnifiedAnalysisEngine()
        self.db = get_mongo_db()
        self.collection = self.db.unified_analysis_tasks
        self.logger = logger
    
    async def create_task(
        self,
        user_id: PyObjectId,
        task_type: AnalysisTaskType,
        task_params: Dict[str, Any],
        engine_type: str = "auto",
        preference_type: str = "neutral",
        workflow_id: Optional[str] = None,
        batch_id: Optional[str] = None
    ) -> UnifiedAnalysisTask:
        """创建分析任务
        
        Args:
            user_id: 用户ID
            task_type: 任务类型
            task_params: 任务参数
            engine_type: 引擎类型 (auto/workflow/legacy/llm)
            preference_type: 分析偏好 (aggressive/neutral/conservative)
            workflow_id: 工作流ID（可选）
            batch_id: 批次ID（可选）
            
        Returns:
            创建的任务对象
        """
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务对象
        task = UnifiedAnalysisTask(
            task_id=task_id,
            user_id=user_id,
            task_type=task_type,
            task_params=task_params,
            engine_type=engine_type,
            preference_type=preference_type,
            workflow_id=workflow_id,
            batch_id=batch_id,
            status=AnalysisStatus.PENDING,
            created_at=now_tz()
        )
        
        # 保存到数据库
        await self._save_task(task)
        
        self.logger.info(f"✅ 创建任务: {task_id} (类型: {task_type})")
        
        return task
    
    async def execute_task(
        self,
        task_or_id: Union[UnifiedAnalysisTask, str],
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> UnifiedAnalysisTask:
        """执行分析任务

        Args:
            task_or_id: 任务对象或任务ID
            progress_callback: 进度回调函数

        Returns:
            更新后的任务对象
        """
        # 如果传入的是 task_id，先获取任务对象
        if isinstance(task_or_id, str):
            task = await self.get_task(task_or_id)
            if not task:
                raise ValueError(f"任务不存在: {task_or_id}")
        else:
            task = task_or_id

        self.logger.info(f"🚀 执行任务: {task.task_id}")

        # 创建一个包装的进度回调，用于更新数据库和内存
        async def wrapped_progress_callback(progress: int, message: str, **kwargs):
            """包装的进度回调：更新任务进度并保存到数据库和内存"""
            # 🔑 关键：从 kwargs 中提取 step_name（简短名称）
            step_name = kwargs.get("step_name", "")

            # 更新任务对象
            task.progress = progress
            task.current_step = step_name or message  # ✅ 使用 step_name 而不是 message
            task.message = message  # ✅ 保存详细描述到 message 字段

            # 保存到数据库
            await self._update_task(task)

            # 🔑 关键：同时更新内存状态
            from app.services.memory_state_manager import get_memory_state_manager, TaskStatus
            memory_manager = get_memory_state_manager()
            await memory_manager.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.RUNNING,
                progress=progress,
                message=message,
                current_step=step_name or message,
                current_step_name=step_name,  # 🔑 传递步骤名称
                current_step_description=message  # 🔑 传递步骤描述
            )

            # 调用原始回调（如果有）
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(progress, message, **kwargs)
                else:
                    progress_callback(progress, message, **kwargs)

        try:
            # 更新任务状态为处理中
            task.status = AnalysisStatus.PROCESSING
            task.started_at = now_tz()
            task.progress = 0
            await self._update_task(task)

            # 🔑 关键：同时更新内存状态
            from app.services.memory_state_manager import get_memory_state_manager, TaskStatus
            memory_manager = get_memory_state_manager()
            await memory_manager.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.RUNNING,
                progress=0,
                message="开始分析...",
                current_step="initialization",
                current_step_name="初始化",  # 🔑 传递步骤名称
                current_step_description="开始分析..."  # 🔑 传递步骤描述
            )

            # 执行任务（引擎会更新 task 对象的状态）
            result = await self.engine.execute_task(task, wrapped_progress_callback)

            # 🔑 关键：格式化结果数据，确保包含前端需要的所有字段
            formatted_result = self._format_analysis_result(result, task)
            task.result = formatted_result
            
            # 🔑 关键：设置任务完成时间和执行时间
            task.completed_at = now_tz()
            task.progress = 100  # 确保进度为100
            if task.started_at:
                task.execution_time = (task.completed_at - task.started_at).total_seconds()
                self.logger.info(f"📊 任务执行时间: {task.execution_time:.2f}s")
            else:
                self.logger.warning(f"⚠️ 任务没有started_at，无法计算execution_time")

            # 保存到数据库
            await self._update_task(task)

            # 🔥 保存到 analysis_reports 集合（兼容旧版 API）
            if task.task_type == AnalysisTaskType.STOCK_ANALYSIS:
                await self._save_to_analysis_reports(task, formatted_result)

            # 🔑 关键：更新内存状态为完成
            await memory_manager.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                message="分析完成",
                current_step="completed",
                current_step_name="已完成",  # 🔑 传递步骤名称
                current_step_description="分析完成",  # 🔑 传递步骤描述
                result_data=task.result
            )

            self.logger.info(f"✅ 任务完成: {task.task_id}")

        except Exception as e:
            # 更新任务状态为失败
            task.status = AnalysisStatus.FAILED
            task.error_message = str(e)
            task.completed_at = now_tz()

            # 保存到数据库
            await self._update_task(task)

            # 🔑 关键：更新内存状态为失败
            from app.services.memory_state_manager import get_memory_state_manager, TaskStatus
            memory_manager = get_memory_state_manager()
            await memory_manager.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                progress=task.progress,
                message=f"分析失败: {str(e)}",
                current_step_name="失败",  # 🔑 传递步骤名称
                current_step_description=f"分析失败: {str(e)}",  # 🔑 传递步骤描述
                error_message=str(e)
            )

            self.logger.error(f"❌ 任务失败: {task.task_id} - {e}")
            raise

        return task
    
    async def create_and_execute_task(
        self,
        user_id: PyObjectId,
        task_type: AnalysisTaskType,
        task_params: Dict[str, Any],
        engine_type: str = "auto",
        preference_type: str = "neutral",
        workflow_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> UnifiedAnalysisTask:
        """创建并执行任务（一步到位）
        
        Args:
            user_id: 用户ID
            task_type: 任务类型
            task_params: 任务参数
            engine_type: 引擎类型
            preference_type: 分析偏好
            workflow_id: 工作流ID
            progress_callback: 进度回调
            
        Returns:
            完成的任务对象
        """
        # 创建任务
        task = await self.create_task(
            user_id=user_id,
            task_type=task_type,
            task_params=task_params,
            engine_type=engine_type,
            preference_type=preference_type,
            workflow_id=workflow_id
        )
        
        # 执行任务
        task = await self.execute_task(task, progress_callback)

        return task

    async def get_task(self, task_id: str) -> Optional[UnifiedAnalysisTask]:
        """获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象，如果不存在则返回 None
        """
        doc = await self.collection.find_one({"task_id": task_id})
        if not doc:
            return None

        return UnifiedAnalysisTask(**doc)

    async def list_user_tasks(
        self,
        user_id: PyObjectId,
        task_type: Optional[AnalysisTaskType] = None,
        status: Optional[AnalysisStatus] = None,
        limit: int = 999999,
        skip: int = 0
    ) -> List[UnifiedAnalysisTask]:
        """列出用户的任务

        Args:
            user_id: 用户ID
            task_type: 任务类型过滤（可选）
            status: 状态过滤（可选）
            limit: 返回数量限制（默认返回所有）
            skip: 跳过数量

        Returns:
            任务列表
        """
        self.logger.info(f"📋 查询用户任务列表 - user_id: {user_id} (类型: {type(user_id)})")
        self.logger.info(f"📋 查询条件 - task_type: {task_type}, status: {status}, limit: {limit}, skip: {skip}")

        query = {"user_id": user_id}

        if task_type:
            query["task_type"] = task_type

        if status:
            query["status"] = status

        self.logger.info(f"📋 MongoDB查询: {query}")

        # 先检查总数
        total = await self.collection.count_documents(query)
        self.logger.info(f"📋 匹配的任务总数: {total}")

        # 调试：检查数据库中所有任务
        all_tasks_count = await self.collection.count_documents({})
        self.logger.info(f"📊 数据库中所有任务总数: {all_tasks_count}")

        # 调试：按 task_type 统计
        task_type_stats = await self.collection.aggregate([
            {"$group": {"_id": "$task_type", "count": {"$sum": 1}}}
        ]).to_list(None)
        self.logger.info(f"📊 按 task_type 统计: {task_type_stats}")

        # 调试：查找所有 position_analysis 任务
        position_tasks = await self.collection.find({"task_type": "position_analysis"}).to_list(None)
        self.logger.info(f"📊 position_analysis 任务总数: {len(position_tasks)}")
        if position_tasks:
            for task in position_tasks[:3]:
                self.logger.info(f"  - task_id: {task.get('task_id')}, user_id: {task.get('user_id')} (类型: {type(task.get('user_id'))}), created_at: {task.get('created_at')}")

        # 调试：查看所有任务按 created_at 倒序排列的情况
        all_sorted = await self.collection.find({}).sort("created_at", -1).limit(20).to_list(20)
        self.logger.info(f"📊 按 created_at 倒序排列的前20个任务:")
        for i, task in enumerate(all_sorted):
            self.logger.info(f"  {i+1}. task_id: {task.get('task_id')}, task_type: {task.get('task_type')}, user_id: {task.get('user_id')} (类型: {type(task.get('user_id'))}), created_at: {task.get('created_at')}")

        # 调试：列出所有任务的 user_id 和 task_type
        if all_tasks_count > 0:
            all_docs = await self.collection.find({}).limit(10).to_list(10)
            self.logger.info(f"📊 数据库中前10个任务:")
            for doc in all_docs:
                self.logger.info(f"  - task_id: {doc.get('task_id')}, user_id: {doc.get('user_id')} (类型: {type(doc.get('user_id'))}), task_type: {doc.get('task_type')}, status: {doc.get('status')}")

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)

        tasks = []
        async for doc in cursor:
            tasks.append(UnifiedAnalysisTask(**doc))

        self.logger.info(f"📋 返回任务数量: {len(tasks)}")
        return tasks

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        result = await self.collection.update_one(
            {"task_id": task_id, "status": {"$in": [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING]}},
            {"$set": {"status": AnalysisStatus.CANCELLED, "completed_at": now_tz()}}
        )

        return result.modified_count > 0

    async def _save_task(self, task: UnifiedAnalysisTask) -> None:
        """保存任务到数据库

        Args:
            task: 任务对象
        """
        doc = task.model_dump(by_alias=True, mode='python')

        # 确保 user_id 是 ObjectId 类型，不是字符串
        if 'user_id' in doc and isinstance(doc['user_id'], str):
            from bson import ObjectId
            doc['user_id'] = ObjectId(doc['user_id'])
            self.logger.debug(f"🔄 转换 user_id 从字符串到 ObjectId: {doc['user_id']}")

        self.logger.debug(f"💾 保存任务文档: user_id={doc.get('user_id')} (类型: {type(doc.get('user_id'))})")

        await self.collection.insert_one(doc)
        self.logger.debug(f"💾 任务已保存: {task.task_id}")

    def _format_analysis_result(self, raw_result: Dict[str, Any], task: UnifiedAnalysisTask) -> Dict[str, Any]:
        """格式化分析结果，确保包含前端需要的所有字段

        Args:
            raw_result: 工作流引擎返回的原始结果
            task: 任务对象

        Returns:
            格式化后的结果
        """
        import uuid
        from datetime import datetime

        # 🔑 关键：从 final_trade_decision 中提取结构化决策
        decision_raw = raw_result.get("final_trade_decision", "")

        # 如果是字典，直接使用
        if isinstance(decision_raw, dict):
            decision_dict = self._format_decision_dict(decision_raw)
            self.logger.info(f"✅ 从字典提取决策: action={decision_dict.get('action')}, target_price={decision_dict.get('target_price')}")
        elif isinstance(decision_raw, str) and decision_raw.strip():
            # 如果是字符串，尝试从文本中提取
            decision_dict = self._extract_decision_from_text(decision_raw)
            self.logger.info(f"✅ 从文本提取决策: action={decision_dict.get('action')}, target_price={decision_dict.get('target_price')}")
        else:
            # 如果没有决策，使用默认值
            decision_dict = {
                "action": "持有",
                "target_price": None,
                "confidence": 0.5,
                "risk_score": 0.5,
                "reasoning": "暂无分析推理"
            }
            self.logger.warning(f"⚠️ 未找到 final_trade_decision，使用默认决策")

        # 提取投资计划
        investment_plan = raw_result.get("trader_investment_plan") or raw_result.get("investment_plan", "")
        if isinstance(investment_plan, dict):
            investment_plan_text = investment_plan.get("content", str(investment_plan))
        else:
            investment_plan_text = str(investment_plan) if investment_plan else ""

        # 🔑 关键：构建 reports 字典（完全按照旧版的方式）
        reports = {}
        
        # 🔑 提取文本的辅助函数（与旧流程保持一致）
        def _extract_text(v):
            """从各种格式中提取文本内容"""
            if isinstance(v, str):
                return v
            if isinstance(v, dict):
                # 尝试从字典中提取文本字段
                for k in ("content", "markdown", "text", "message", "report"):
                    x = v.get(k)
                    if isinstance(x, str) and x.strip():
                        return x
            return ""

        # 🔑 第一步：从顶层提取标准报告字段
        report_fields = [
            # 🆕 宏观分析报告（优先提取）
            'index_report',
            'sector_report',
            # 个股分析报告
            'market_report',
            'sentiment_report',
            'news_report',
            'fundamentals_report',
            # 投资计划
            'investment_plan',
            'trader_investment_plan',
            'final_trade_decision',
            # 🔥 新增：从顶层提取的研究员报告（v2.0工作流可能直接返回这些字段）
            'bull_report',
            'bear_report',
        ]

        # 从 raw_result 中提取报告内容（与旧流程保持一致）
        for field in report_fields:
            content_raw = raw_result.get(field, "")
            content = _extract_text(content_raw)
            if content and isinstance(content, str) and len(content.strip()) > 5:
                # 🔥 特殊处理：bull_report 和 bear_report 映射到 bull_researcher 和 bear_researcher
                if field == 'bull_report':
                    reports["bull_researcher"] = content.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: bull_researcher (来自 bull_report) - 长度: {len(content.strip())}")
                elif field == 'bear_report':
                    reports["bear_researcher"] = content.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: bear_researcher (来自 bear_report) - 长度: {len(content.strip())}")
                else:
                    reports[field] = content.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: {field} - 长度: {len(content.strip())}")
            else:
                self.logger.debug(f"⚠️ [REPORTS] 跳过报告: {field} - 内容为空或太短")

        # 🔑 第二步：处理研究团队辩论状态（字典类型）- 拆分为独立子报告（与旧流程保持一致）
        # 🔥 注意：如果顶层已经有 bull_report/bear_report，优先使用顶层的；否则从 investment_debate_state 提取
        investment_debate = raw_result.get("investment_debate_state", {})
        if investment_debate and isinstance(investment_debate, dict):
            # 1. 多头研究员报告（如果顶层没有，才从 investment_debate_state 提取）
            if "bull_researcher" not in reports:
                bull_history = _extract_text(investment_debate.get("bull_history", ""))
                if bull_history and len(bull_history.strip()) > 5:
                    reports["bull_researcher"] = bull_history.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: bull_researcher (来自 investment_debate_state.bull_history) - 长度: {len(bull_history.strip())}")

            # 2. 空头研究员报告（如果顶层没有，才从 investment_debate_state 提取）
            if "bear_researcher" not in reports:
                bear_history = _extract_text(investment_debate.get("bear_history", ""))
                if bear_history and len(bear_history.strip()) > 5:
                    reports["bear_researcher"] = bear_history.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: bear_researcher (来自 investment_debate_state.bear_history) - 长度: {len(bear_history.strip())}")

            # 3. 研究经理决策报告
            judge_decision = _extract_text(investment_debate.get("judge_decision", ""))
            if judge_decision and len(judge_decision.strip()) > 5:
                reports["research_team_decision"] = judge_decision.strip()
                self.logger.info(f"📊 [REPORTS] 提取报告: research_team_decision - 长度: {len(judge_decision.strip())}")

        # 🔑 第三步：处理风险管理团队辩论状态（字典类型）- 拆分为独立子报告（与旧流程保持一致）
        # 🔥 同时检查顶层是否有 risky_opinion, safe_opinion, neutral_opinion 等字段
        risk_debate = raw_result.get("risk_debate_state", {})
        
        # 🔥 备选字段映射（v2.0工作流可能将报告存储在顶层）
        risk_alternative_fields = {
            "risky_analyst": ["risky_opinion", "risky_history"],
            "safe_analyst": ["safe_opinion", "safe_history"],
            "neutral_analyst": ["neutral_opinion", "neutral_history"],
        }
        
        # 先从顶层提取
        for report_key, alt_fields in risk_alternative_fields.items():
            if report_key not in reports:
                for alt_field in alt_fields:
                    content_raw = raw_result.get(alt_field, "")
                    content = _extract_text(content_raw)
                    if content and isinstance(content, str) and len(content.strip()) > 5:
                        reports[report_key] = content.strip()
                        self.logger.info(f"📊 [REPORTS] 提取报告: {report_key} (来自顶层 {alt_field}) - 长度: {len(content.strip())}")
                        break
        
        # 然后从 risk_debate_state 提取（如果顶层没有）
        if risk_debate and isinstance(risk_debate, dict):
            # 1. 激进分析师报告
            if "risky_analyst" not in reports:
                risky_history = _extract_text(risk_debate.get("risky_history", ""))
                if risky_history and len(risky_history.strip()) > 5:
                    reports["risky_analyst"] = risky_history.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: risky_analyst (来自 risk_debate_state.risky_history) - 长度: {len(risky_history.strip())}")

            # 2. 保守分析师报告
            if "safe_analyst" not in reports:
                safe_history = _extract_text(risk_debate.get("safe_history", ""))
                if safe_history and len(safe_history.strip()) > 5:
                    reports["safe_analyst"] = safe_history.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: safe_analyst (来自 risk_debate_state.safe_history) - 长度: {len(safe_history.strip())}")

            # 3. 中性分析师报告
            if "neutral_analyst" not in reports:
                neutral_history = _extract_text(risk_debate.get("neutral_history", ""))
                if neutral_history and len(neutral_history.strip()) > 5:
                    reports["neutral_analyst"] = neutral_history.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: neutral_analyst (来自 risk_debate_state.neutral_history) - 长度: {len(neutral_history.strip())}")

            # 4. 投资组合经理决策报告
            judge_decision = _extract_text(risk_debate.get("judge_decision", ""))
            if judge_decision and len(judge_decision.strip()) > 5:
                reports["risk_management_decision"] = judge_decision.strip()
                self.logger.info(f"📊 [REPORTS] 提取报告: risk_management_decision - 长度: {len(judge_decision.strip())}")

        # 生成摘要和建议
        summary = decision_dict.get("reasoning", "")[:1000] if decision_dict.get("reasoning") else ""
        if not summary and investment_plan_text:
            summary = investment_plan_text[:1000]
        if not summary and reports.get("final_trade_decision"):
            summary = reports["final_trade_decision"][:1000]

        recommendation = decision_dict.get("reasoning", "")
        if not recommendation and investment_plan_text:
            recommendation = investment_plan_text
        if not recommendation and reports.get("final_trade_decision"):
            recommendation = reports["final_trade_decision"]

        # 计算风险等级（基于 risk_score）
        risk_score = decision_dict.get("risk_score", 0.5)
        if risk_score < 0.3:
            risk_level = "低"
        elif risk_score < 0.6:
            risk_level = "中等"
        else:
            risk_level = "高"

        # 🔑 获取模型信息
        quick_model = task.task_params.get("quick_analysis_model", "Unknown")
        deep_model = task.task_params.get("deep_analysis_model", "Unknown")
        model_info = f"{quick_model}/{deep_model}"
        
        # 构建格式化结果
        formatted_result = {
            "analysis_id": str(uuid.uuid4()),
            "stock_symbol": task.task_params.get("symbol") or task.task_params.get("stock_code"),
            "stock_code": task.task_params.get("stock_code") or task.task_params.get("symbol"),
            "analysis_date": task.task_params.get("analysis_date") or datetime.now().strftime("%Y-%m-%d"),
            "summary": summary or "分析完成",
            "recommendation": recommendation or "请查看详细报告",
            "confidence_score": decision_dict.get("confidence", 0.5),
            "risk_level": risk_level,
            "key_points": [],  # 可以从 reasoning 中提取关键点
            "execution_time": task.execution_time or 0,
            "tokens_used": raw_result.get("tokens_used", 0),
            "analysts": task.task_params.get("selected_analysts", []),
            "research_depth": task.task_params.get("research_depth", "快速"),
            "reports": reports,
            "state": raw_result,  # 保存完整的原始状态
            "detailed_analysis": raw_result,  # 兼容旧版
            "decision": decision_dict,  # 🔑 关键：决策信息（包含 action, target_price, confidence, risk_score, reasoning）
            "model_info": model_info,  # 🔥 关键：模型信息
            "quick_model": quick_model,  # 🔥 关键：快速模型
            "deep_model": deep_model,  # 🔥 关键：深度模型
        }

        self.logger.info(f"✅ 格式化结果完成: {len(reports)} 个报告, decision={decision_dict}")
        return formatted_result

    def _format_decision_dict(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """格式化决策字典

        Args:
            decision: 原始决策字典

        Returns:
            格式化后的决策字典
        """
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

        return {
            'action': chinese_action,
            'confidence': float(decision.get('confidence', 0.5)),
            'risk_score': float(decision.get('risk_score', 0.5)),
            'target_price': target_price,
            'reasoning': decision.get('reasoning', '') or decision.get('rationale', '') or '暂无分析推理'
        }

    def _extract_decision_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取决策信息

        Args:
            text: 决策文本

        Returns:
            决策字典
        """
        import re

        # 提取动作
        action = '持有'  # 默认
        if re.search(r'(强烈)?买入|建议买入|看多|BUY|STRONG_BUY', text, re.IGNORECASE):
            action = '买入'
        elif re.search(r'(强烈)?卖出|建议卖出|看空|减持|SELL|STRONG_SELL', text, re.IGNORECASE):
            action = '卖出'
        elif re.search(r'持有|观望|等待|HOLD', text, re.IGNORECASE):
            action = '持有'

        # 提取目标价格
        target_price = None
        price_patterns = [
            r'目标价[位格]?[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',  # 目标价位: 45.50
            r'\*\*目标价[位格]?\*\*[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',  # **目标价位**: 45.50
            r'目标[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',         # 目标: 45.50
            r'价格[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',         # 价格: 45.50
            r'[¥\$](\d+(?:\.\d+)?)',                      # ¥45.50 或 $190
            r'(\d+(?:\.\d+)?)元',                         # 45.50元
        ]

        for pattern in price_patterns:
            price_match = re.search(pattern, text)
            if price_match:
                try:
                    target_price = float(price_match.group(1))
                    break
                except ValueError:
                    continue

        # 提取置信度
        confidence = 0.7  # 默认
        confidence_match = re.search(r'置信度[：:]?\s*(\d+(?:\.\d+)?)', text)
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
                if confidence > 1:  # 如果是百分比形式
                    confidence = confidence / 100
            except ValueError:
                pass

        # 提取风险评分
        risk_score = 0.5  # 默认
        risk_match = re.search(r'风险[评分得分][：:]?\s*(\d+(?:\.\d+)?)', text)
        if risk_match:
            try:
                risk_score = float(risk_match.group(1))
                if risk_score > 1:  # 如果是百分比形式
                    risk_score = risk_score / 100
            except ValueError:
                pass

        # 提取决策理由（取前300字符）
        reasoning = text[:300].replace('#', '').replace('*', '').strip()
        if len(text) > 300:
            reasoning += "..."

        return {
            'action': action,
            'target_price': target_price,
            'confidence': confidence,
            'risk_score': risk_score,
            'reasoning': reasoning
        }

    async def _update_task(self, task: UnifiedAnalysisTask) -> None:
        """更新任务到数据库

        Args:
            task: 任务对象
        """
        doc = task.model_dump(by_alias=True, exclude={"_id"}, mode='python')

        # 确保 user_id 是 ObjectId 类型，不是字符串
        if 'user_id' in doc and isinstance(doc['user_id'], str):
            from bson import ObjectId
            doc['user_id'] = ObjectId(doc['user_id'])

        await self.collection.update_one(
            {"task_id": task.task_id},
            {"$set": doc}
        )
        self.logger.debug(f"💾 任务已更新: {task.task_id}")

    async def _save_to_analysis_reports(self, task: UnifiedAnalysisTask, result: Dict[str, Any]) -> None:
        """保存分析结果到 analysis_reports 集合（兼容旧版 API）

        Args:
            task: 任务对象
            result: 格式化后的分析结果
        """
        try:
            import uuid
            from datetime import datetime
            
            stock_code = task.task_params.get("symbol") or task.task_params.get("stock_code", "")
            market_type = task.task_params.get("market_type", "A股")
            
            # 解析股票名称（如果没有在result中）
            stock_name = result.get("stock_name", "")
            if not stock_name:
                stock_name = self._resolve_stock_name(stock_code)
            
            # 🔑 获取模型信息（与旧流程保持一致）
            quick_model = task.task_params.get("quick_analysis_model") or result.get("quick_model", "Unknown")
            deep_model = task.task_params.get("deep_analysis_model") or result.get("deep_model", "Unknown")
            model_info = result.get("model_info") or f"{quick_model}/{deep_model}"
            
            # 🔑 从报告中提取分析师列表（与旧流程保持一致）
            def _get_analysts_from_reports(reports_dict: Dict[str, Any]) -> List[str]:
                """根据实际保存的报告动态生成分析师列表"""
                analysts = []
                analyst_mapping = {
                    "index_report": "index_analyst",
                    "sector_report": "sector_analyst",
                    "market_report": "market_analyst",
                    "sentiment_report": "sentiment_analyst",
                    "news_report": "news_analyst",
                    "fundamentals_report": "fundamentals_analyst",
                    "bull_researcher": "bull_researcher",
                    "bear_researcher": "bear_researcher",
                    "risky_analyst": "risky_analyst",
                    "safe_analyst": "safe_analyst",
                    "neutral_analyst": "neutral_analyst",
                }
                for report_key, analyst_id in analyst_mapping.items():
                    if report_key in reports_dict and reports_dict[report_key]:
                        analysts.append(analyst_id)
                return analysts
            
            reports_dict = result.get("reports", {})
            analysts_list = _get_analysts_from_reports(reports_dict) or result.get("analysts", [])
            
            # 🔑 从最终决策中提取 recommendation 和 confidence_score（与旧流程保持一致）
            decision = result.get("decision", {})
            recommendation = result.get("recommendation", "")
            if not recommendation and decision.get("action"):
                recommendation = f"投资建议：{decision.get('action')}。"
                if decision.get("target_price"):
                    recommendation += f"目标价格：{decision.get('target_price')}元。"
                if decision.get("reasoning"):
                    reasoning = decision.get("reasoning", "")[:200]
                    recommendation += f"决策依据：{reasoning}"
            
            confidence_score = result.get("confidence_score", 0.0)
            if confidence_score == 0.0 and decision.get("confidence"):
                confidence_score = decision.get("confidence", 0.0)
            
            risk_level = result.get("risk_level", "中等")
            if risk_level == "中等" and decision.get("risk_score") is not None:
                risk_score = decision.get("risk_score", 0.5)
                if risk_score < 0.3:
                    risk_level = "低"
                elif risk_score < 0.6:
                    risk_level = "中等"
                else:
                    risk_level = "高"
            
            # 构建文档（与旧流程保持一致的完整结构）
            document = {
                "analysis_id": result.get("analysis_id", str(uuid.uuid4())),
                "stock_symbol": stock_code,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "market_type": market_type,
                "model_info": model_info,  # 🔥 关键：保存模型信息
                "quick_model": quick_model,
                "deep_model": deep_model,
                "analysis_date": result.get("analysis_date", datetime.now().strftime('%Y-%m-%d')),
                "timestamp": task.completed_at or now_tz(),
                "status": "completed",
                "source": "api",
                "engine": "v2" if task.engine_type in ["auto", "workflow"] else (task.engine_type or "v2"),
                
                # 分析参数
                "research_depth": result.get("research_depth", task.task_params.get("research_depth", "标准")),
                "analysts": analysts_list,  # 🔥 根据实际报告动态生成
                
                # 报告内容（包含所有字段）
                "reports": reports_dict,
                
                # 🔥 关键：decision 字段
                "decision": decision,
                
                # 摘要和建议
                "summary": result.get("summary", ""),
                "recommendation": recommendation,
                "confidence_score": confidence_score,
                "risk_level": risk_level,
                "key_points": result.get("key_points", []),
                
                # 元数据
                "task_id": task.task_id,
                "user_id": task.user_id,
                "created_at": task.created_at or now_tz(),
                "updated_at": task.completed_at or now_tz(),
                
                # 性能指标
                "execution_time": task.execution_time or 0,
                "tokens_used": result.get("tokens_used", 0),
            }
            
            # 保存到 analysis_reports 集合
            await self.db.analysis_reports.update_one(
                {"task_id": task.task_id},
                {"$set": document},
                upsert=True
            )
            
            self.logger.info(f"✅ 分析结果已保存到 analysis_reports: task_id={task.task_id}, engine={document['engine']}")
            
        except Exception as e:
            self.logger.error(f"❌ 保存到 analysis_reports 失败: {e}", exc_info=True)
    
    def _resolve_stock_name(self, stock_code: str) -> str:
        """解析股票名称
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票名称，如果解析失败则返回默认值
        """
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
            
            # 降级：尝试使用 get_stock_basic_info
            try:
                from tradingagents.dataflows.data_source_manager import get_stock_basic_info
                info_str = get_stock_basic_info(stock_code)
                
                if info_str and isinstance(info_str, str) and "股票名称:" in info_str:
                    stock_name = info_str.split("股票名称:")[1].split("\n")[0].strip()
                    if stock_name:
                        return stock_name
                elif info_str and isinstance(info_str, dict) and info_str.get("name"):
                    return info_str["name"]
            except Exception:
                pass
                
        except Exception as e:
            self.logger.warning(f"⚠️ 解析股票名称失败: {stock_code} - {e}")
        
        return f"股票{stock_code}"

    async def get_task_statistics(self, user_id: PyObjectId) -> Dict[str, Any]:
        """获取用户的任务统计

        Args:
            user_id: 用户ID

        Returns:
            统计信息字典
        """
        self.logger.info(f"📊 获取任务统计 - user_id: {user_id} (类型: {type(user_id)})")

        # 先检查总任务数
        total_count = await self.collection.count_documents({"user_id": user_id})
        self.logger.info(f"📊 用户任务总数: {total_count}")

        # 如果没有任务，直接返回空统计
        if total_count == 0:
            self.logger.warning(f"⚠️ 用户 {user_id} 没有任务")
            # 打印一些调试信息
            all_tasks = await self.collection.find().limit(5).to_list(5)
            self.logger.info(f"📋 数据库中的任务示例:")
            for task in all_tasks:
                self.logger.info(f"  - task_id: {task.get('task_id')}, user_id: {task.get('user_id')} (类型: {type(task.get('user_id'))})")

        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]

        cursor = self.collection.aggregate(pipeline)

        stats = {
            "total": 0,
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }

        async for doc in cursor:
            status = doc["_id"]
            count = doc["count"]
            self.logger.info(f"📊 状态统计: {status} = {count}")
            stats[status] = count
            stats["total"] += count

        self.logger.info(f"📊 最终统计结果: {stats}")
        return stats


# 单例实例
_task_service: Optional[TaskAnalysisService] = None


def get_task_analysis_service() -> TaskAnalysisService:
    """获取任务分析服务单例"""
    global _task_service
    if _task_service is None:
        _task_service = TaskAnalysisService()
    return _task_service

