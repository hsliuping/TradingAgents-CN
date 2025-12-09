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

from app.models.analysis import (
    AnalysisParameters,
    AnalysisResult,
    AnalysisStatus,
    AnalysisTask,
    SingleAnalysisRequest,
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
                depth_mapping = {
                    "快速": 1, "基础": 2, "标准": 3, "深度": 4, "全面": 5
                }
                config["research_depth"] = depth_mapping.get(parameters.research_depth, 3)

            if parameters.selected_analysts:
                config["selected_analysts"] = parameters.selected_analysts

            if parameters.market_type:
                config["market_type"] = parameters.market_type

        return config

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
            inputs = {
                "ticker": stock_code,
                "trade_date": analysis_date,
                "messages": [],
            }

            # 合并工作流配置中的参数
            if workflow.config:
                inputs.update({
                    k: v for k, v in workflow.config.items()
                    if k not in inputs
                })

            # 6. 执行工作流
            result = await engine.execute_async(
                inputs=inputs,
                progress_callback=progress_callback,
            )

            logger.info(f"分析完成: {stock_code}, task_id={task_id}")

            # 7. 格式化结果
            return self._format_result(result, stock_code, analysis_date, task_id)

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
            inputs = {
                "ticker": stock_code,
                "trade_date": analysis_date,
                "messages": [],
            }

            if workflow.config:
                inputs.update({
                    k: v for k, v in workflow.config.items()
                    if k not in inputs
                })

            # 6. 同步执行
            result = engine.execute(
                inputs=inputs,
                progress_callback=progress_callback,
            )

            logger.info(f"[同步] 分析完成: {stock_code}")
            return self._format_result(result, stock_code, analysis_date, task_id)

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
    ) -> Dict[str, Any]:
        """格式化分析结果"""
        # 从 LangGraph 状态中提取关键信息
        final_decision = raw_result.get("final_decision", {})

        return {
            "success": True,
            "task_id": task_id,
            "stock_code": stock_code,
            "analysis_date": analysis_date,

            # 决策信息
            "action": final_decision.get("action", "hold"),
            "confidence": final_decision.get("confidence", 0.0),
            "reasoning": final_decision.get("reasoning", ""),

            # 详细分析
            "market_analysis": raw_result.get("market_report", ""),
            "fundamentals_analysis": raw_result.get("fundamentals_report", ""),
            "news_analysis": raw_result.get("news_report", ""),
            "social_analysis": raw_result.get("social_report", ""),

            # 研究报告
            "bull_thesis": raw_result.get("bull_thesis", ""),
            "bear_thesis": raw_result.get("bear_thesis", ""),
            "research_summary": raw_result.get("research_summary", ""),

            # 交易计划
            "trade_plan": raw_result.get("trade_plan", {}),

            # 风险评估
            "risk_assessment": raw_result.get("risk_assessment", {}),

            # 原始结果（用于调试）
            "raw_result": raw_result,
        }

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


# 单例实例
_unified_service: Optional[UnifiedAnalysisService] = None


def get_unified_analysis_service() -> UnifiedAnalysisService:
    """获取统一分析服务单例"""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedAnalysisService()
    return _unified_service
