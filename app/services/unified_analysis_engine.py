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
        config = AnalysisWorkflowRegistry.get_config(task.task_type)
        if not config:
            raise ValueError(f"未注册的任务类型: {task.task_type}")
        
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
            
            if task.started_at:
                task.execution_time = (task.completed_at - task.started_at).total_seconds()
            
            self.logger.info(f"✅ 任务执行成功: {task.task_id} (耗时: {task.execution_time:.2f}秒)")
            
            return result
            
        except Exception as e:
            # 更新任务状态为失败
            task.status = AnalysisStatus.FAILED
            task.completed_at = now_tz()
            task.error_message = str(e)
            
            if task.started_at:
                task.execution_time = (task.completed_at - task.started_at).total_seconds()
            
            self.logger.error(f"❌ 任务执行失败: {task.task_id} - {e}")
            raise RuntimeError(f"任务执行失败: {e}") from e
    
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
        
        # 准备工作流输入
        workflow_inputs = task.task_params.copy()
        
        # 准备工作流配置
        workflow_config = {
            "preference_type": task.preference_type,
            "timeout": config.timeout
        }
        
        # 执行工作流
        result = await workflow_api.execute(
            workflow_id=task.workflow_id or config.workflow_id,
            inputs=workflow_inputs,
            config=workflow_config
        )

        return result

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

