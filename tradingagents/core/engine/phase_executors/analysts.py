# tradingagents/core/engine/phase_executors/analysts.py
"""
分析师阶段执行器

并行执行多个分析师 Agent：
- MarketAnalyst (技术面分析)
- NewsAnalyst (新闻分析)
- SentimentAnalyst (情绪分析)
- FundamentalsAnalyst (基本面分析)
- SectorAnalyst (板块分析)
- IndexAnalyst (大盘分析)
"""

from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from tradingagents.utils.logging_init import get_logger

from ..analysis_context import AnalysisContext
from ..data_access_manager import DataAccessManager
from ..data_contract import DataLayer, AgentDataContract
from ..agent_integrator import AgentIntegrator
from .base import PhaseExecutor

logger = get_logger("default")


class AnalystsPhase(PhaseExecutor):
    """
    分析师阶段执行器

    并行执行所有选定的分析师 Agent，
    收集分析报告写入 Reports 层
    """

    phase_name = "AnalystsPhase"

    def __init__(
        self,
        llm_provider: Any = None,
        config: Optional[Dict[str, Any]] = None,
        selected_analysts: Optional[List[str]] = None,
        max_workers: int = 4,
        llm: Any = None,
        toolkit: Any = None,
        use_stub: bool = False
    ):
        """
        初始化分析师阶段

        Args:
            llm_provider: LLM 提供者（用于创建 LLM）
            config: 阶段配置
            selected_analysts: 选择的分析师列表，None 表示全部
            max_workers: 并行执行的最大工作线程数
            llm: 已创建的 LLM 实例（优先使用）
            toolkit: 工具集实例
            use_stub: 是否使用桩实现（用于测试）
        """
        super().__init__(llm_provider, config)
        self.selected_analysts = selected_analysts
        self.max_workers = max_workers
        self.use_stub = use_stub

        # Agent 集成器（延迟初始化）
        self._integrator: Optional[AgentIntegrator] = None
        self._llm = llm
        self._toolkit = toolkit
    
    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行分析师阶段
        
        Args:
            context: 分析上下文
            data_manager: 数据访问管理器
            
        Returns:
            分析结果摘要
        """
        self.log_start()
        
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.info(f"📊 [{self.phase_name}] 分析股票: {ticker}")
        
        # 获取要执行的分析师列表
        analysts_to_run = self._get_analysts_to_run()
        
        outputs = {
            "ticker": ticker,
            "analysts_run": [],
            "analysts_failed": [],
            "reports_generated": []
        }
        
        # 并行执行分析师
        if self.max_workers > 1 and len(analysts_to_run) > 1:
            self._run_parallel(analysts_to_run, context, data_manager, outputs)
        else:
            self._run_sequential(analysts_to_run, context, data_manager, outputs)
        
        self.log_end(outputs)
        return outputs
    
    def _get_analysts_to_run(self) -> List[str]:
        """获取要执行的分析师列表"""
        # 默认分析师列表
        default_analysts = [
            "market_analyst",
            "news_analyst",
            "sentiment_analyst",
            "fundamentals_analyst",
            "sector_analyst",
            "index_analyst",
        ]
        
        if self.selected_analysts:
            return [a for a in self.selected_analysts if a in default_analysts]
        return default_analysts
    
    def _run_sequential(
        self,
        analysts: List[str],
        context: AnalysisContext,
        data_manager: DataAccessManager,
        outputs: Dict[str, Any]
    ) -> None:
        """顺序执行分析师"""
        for analyst_id in analysts:
            try:
                result = self._run_single_analyst(analyst_id, context, data_manager)
                outputs["analysts_run"].append(analyst_id)
                if result.get("report_field"):
                    outputs["reports_generated"].append(result["report_field"])
            except Exception as e:
                logger.error(f"❌ [{self.phase_name}] {analyst_id} 执行失败: {e}")
                outputs["analysts_failed"].append(analyst_id)
    
    def _run_parallel(
        self,
        analysts: List[str],
        context: AnalysisContext,
        data_manager: DataAccessManager,
        outputs: Dict[str, Any]
    ) -> None:
        """并行执行分析师"""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._run_single_analyst, analyst_id, context, data_manager
                ): analyst_id
                for analyst_id in analysts
            }
            
            for future in as_completed(futures):
                analyst_id = futures[future]
                try:
                    result = future.result()
                    outputs["analysts_run"].append(analyst_id)
                    if result.get("report_field"):
                        outputs["reports_generated"].append(result["report_field"])
                except Exception as e:
                    logger.error(f"❌ [{self.phase_name}] {analyst_id} 执行失败: {e}")
                    outputs["analysts_failed"].append(analyst_id)

    def _get_integrator(self) -> Optional[AgentIntegrator]:
        """获取或创建 Agent 集成器"""
        if self._integrator is not None:
            return self._integrator

        if self._llm is not None and self._toolkit is not None:
            self._integrator = AgentIntegrator(self._llm, self._toolkit)
            logger.debug(f"🔧 [{self.phase_name}] 创建 Agent 集成器")
            return self._integrator

        return None

    def _run_single_analyst(
        self,
        analyst_id: str,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行单个分析师

        Args:
            analyst_id: 分析师 ID
            context: 分析上下文
            data_manager: 数据访问管理器

        Returns:
            执行结果
        """
        logger.info(f"🔍 [{self.phase_name}] 执行分析师: {analyst_id}")

        # 强制使用桩或没有集成器时使用桩
        if self.use_stub:
            return self._run_stub_analyst(analyst_id, context)

        # 获取 Agent 集成器
        integrator = self._get_integrator()
        if integrator is None:
            logger.debug(f"⚠️ [{self.phase_name}] 无集成器，使用桩: {analyst_id}")
            return self._run_stub_analyst(analyst_id, context)

        # 获取 Agent
        agent = integrator.get_agent(analyst_id)
        if agent is None:
            logger.debug(f"⚠️ [{self.phase_name}] Agent 不可用，使用桩: {analyst_id}")
            return self._run_stub_analyst(analyst_id, context)

        # 执行实际 Agent
        return self._run_real_analyst(analyst_id, agent, context, integrator)

    def _run_real_analyst(
        self,
        analyst_id: str,
        agent: Any,
        context: AnalysisContext,
        integrator: AgentIntegrator
    ) -> Dict[str, Any]:
        """
        执行实际的分析师 Agent

        Args:
            analyst_id: 分析师 ID
            agent: Agent 节点函数
            context: 分析上下文
            integrator: Agent 集成器

        Returns:
            执行结果
        """
        try:
            # 转换 Context 为 AgentState
            state = integrator.context_to_state(context)

            logger.debug(f"📤 [{self.phase_name}] 调用 Agent: {analyst_id}")

            # 执行 Agent
            result = agent(state)

            # 提取报告
            report_field, report_content = integrator.extract_report(analyst_id, result)

            if report_content:
                # 写入 Reports 层
                context.set(DataLayer.REPORTS, report_field, report_content, source=analyst_id)
                logger.info(f"📝 [{self.phase_name}] 生成报告: {report_field} ({len(report_content)} 字符)")
            else:
                logger.warning(f"⚠️ [{self.phase_name}] Agent 未返回报告: {analyst_id}")

            return {"analyst_id": analyst_id, "report_field": report_field}

        except Exception as e:
            logger.error(f"❌ [{self.phase_name}] Agent 执行异常 {analyst_id}: {e}")
            raise

    def _run_stub_analyst(
        self,
        analyst_id: str,
        context: AnalysisContext
    ) -> Dict[str, Any]:
        """
        运行桩分析师（用于测试）

        生成占位报告，写入 Reports 层
        """
        # 分析师输出字段映射
        output_field_map = {
            "market_analyst": "market_report",
            "news_analyst": "news_report",
            "sentiment_analyst": "sentiment_report",
            "fundamentals_analyst": "fundamentals_report",
            "sector_analyst": "sector_report",
            "index_analyst": "index_report",
        }

        report_field = output_field_map.get(analyst_id)
        if report_field:
            # 生成占位报告
            ticker = context.get(DataLayer.CONTEXT, "ticker")
            stub_report = f"[{analyst_id}] 分析报告占位 - {ticker}"

            # 写入 Reports 层
            context.set(DataLayer.REPORTS, report_field, stub_report, source=analyst_id)

            logger.debug(f"📝 [{self.phase_name}] 生成桩报告: {report_field}")

        return {"analyst_id": analyst_id, "report_field": report_field}

    def set_dependencies(self, llm: Any, toolkit: Any) -> "AnalystsPhase":
        """
        设置依赖项

        Args:
            llm: LLM 实例
            toolkit: 工具集实例

        Returns:
            self（支持链式调用）
        """
        self._llm = llm
        self._toolkit = toolkit
        self._integrator = None  # 重置集成器
        return self
