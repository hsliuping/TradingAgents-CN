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

            # 保存到数据库
            await self._update_task(task)

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
        limit: int = 50,
        skip: int = 0
    ) -> List[UnifiedAnalysisTask]:
        """列出用户的任务

        Args:
            user_id: 用户ID
            task_type: 任务类型过滤（可选）
            status: 状态过滤（可选）
            limit: 返回数量限制
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
        report_fields = [
            # 🆕 宏观分析报告（优先提取）
            'index_report',
            'sector_report',
            # 个股分析报告
            'market_report',
            'sentiment_report',
            'news_report',
            'fundamentals_report',
            'investment_plan',
            'trader_investment_plan',
            'final_trade_decision'
        ]

        # 从 raw_result 中提取报告内容
        for field in report_fields:
            value = raw_result.get(field)
            if value:
                if isinstance(value, dict):
                    # 如果是字典，提取 content 字段
                    text = value.get("content", str(value))
                else:
                    text = str(value)

                if isinstance(text, str) and len(text.strip()) > 10:  # 只保存有实际内容的报告
                    reports[field] = text.strip()
                    self.logger.info(f"📊 [REPORTS] 提取报告: {field} - 长度: {len(text.strip())}")
                else:
                    self.logger.debug(f"⚠️ [REPORTS] 跳过报告: {field} - 内容为空或太短")

        # 提取辩论状态中的报告
        investment_debate_state = raw_result.get("investment_debate_state", {})
        if isinstance(investment_debate_state, dict):
            if investment_debate_state.get("bull_history"):
                reports["bull_researcher"] = investment_debate_state["bull_history"]
            if investment_debate_state.get("bear_history"):
                reports["bear_researcher"] = investment_debate_state["bear_history"]
            if investment_debate_state.get("judge_decision"):
                reports["research_team_decision"] = investment_debate_state["judge_decision"]

        risk_debate_state = raw_result.get("risk_debate_state", {})
        if isinstance(risk_debate_state, dict):
            if risk_debate_state.get("risky_history"):
                reports["risky_analyst"] = risk_debate_state["risky_history"]
            if risk_debate_state.get("safe_history"):
                reports["safe_analyst"] = risk_debate_state["safe_history"]
            if risk_debate_state.get("neutral_history"):
                reports["neutral_analyst"] = risk_debate_state["neutral_history"]
            if risk_debate_state.get("judge_decision"):
                reports["risk_management_decision"] = risk_debate_state["judge_decision"]

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

