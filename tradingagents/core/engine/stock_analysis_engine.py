# tradingagents/core/engine/stock_analysis_engine.py
"""
股票分析引擎

主引擎类，协调整个分析流程：
1. 数据收集 → 2. 分析师分析 → 3. 研究辩论 → 4. 交易决策 → 5. 风险评估

设计原则：
- 基于数据契约的 Agent 协作
- 分层数据管理（Context → RawData → AnalysisData → Reports → Decisions）
- 完整的数据血缘追踪
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type
from datetime import datetime

from tradingagents.utils.logging_init import get_logger

from .analysis_context import AnalysisContext
from .data_contract import DataLayer, AgentDataContract
from .data_access_manager import DataAccessManager
from .data_schema import data_schema

logger = get_logger("default")


class AnalysisPhase(str, Enum):
    """分析阶段枚举"""
    DATA_COLLECTION = "data_collection"
    ANALYSTS = "analysts"
    RESEARCH_DEBATE = "research_debate"
    TRADE_DECISION = "trade_decision"
    RISK_ASSESSMENT = "risk_assessment"


@dataclass
class PhaseResult:
    """阶段执行结果"""
    phase: AnalysisPhase
    success: bool
    duration_seconds: float
    error: Optional[str] = None
    outputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """分析结果"""
    ticker: str
    trade_date: str
    success: bool
    final_decision: Optional[Dict[str, Any]] = None
    phase_results: List[PhaseResult] = field(default_factory=list)
    context: Optional[AnalysisContext] = None
    error: Optional[str] = None
    total_duration_seconds: float = 0.0


class StockAnalysisEngine:
    """
    股票分析引擎
    
    协调多个 Agent 完成股票分析流程：
    1. 初始化分析上下文
    2. 按顺序执行各分析阶段
    3. 收集和返回分析结果
    
    用法:
        engine = StockAnalysisEngine(llm_provider=llm)
        result = engine.analyze(
            ticker="000858.SZ",
            trade_date="2024-01-15",
            company_name="五粮液"
        )
    """
    
    def __init__(
        self,
        llm_provider: Any = None,
        selected_analysts: Optional[List[str]] = None,
        enable_data_lineage: bool = True,
        debug_mode: bool = False
    ):
        """
        初始化分析引擎
        
        Args:
            llm_provider: LLM 提供者实例
            selected_analysts: 选择的分析师列表，None 表示使用全部
            enable_data_lineage: 是否启用数据血缘追踪
            debug_mode: 调试模式
        """
        self.llm_provider = llm_provider
        self.selected_analysts = selected_analysts
        self.enable_data_lineage = enable_data_lineage
        self.debug_mode = debug_mode
        
        # 阶段执行器（延迟初始化）
        self._phase_executors: Dict[AnalysisPhase, Any] = {}
        
        logger.info("📊 [StockAnalysisEngine] 引擎初始化完成")
    
    def analyze(
        self,
        ticker: str,
        trade_date: str,
        company_name: Optional[str] = None,
        market_type: str = "cn",
        **kwargs
    ) -> AnalysisResult:
        """
        执行股票分析
        
        Args:
            ticker: 股票代码，如 "000858.SZ"
            trade_date: 交易日期，如 "2024-01-15"
            company_name: 公司名称（可选）
            market_type: 市场类型，"cn" 或 "us"
            **kwargs: 其他上下文参数
            
        Returns:
            AnalysisResult: 分析结果
        """
        start_time = datetime.now()
        
        logger.info(f"🚀 [StockAnalysisEngine] 开始分析: {ticker} ({trade_date})")
        
        # 1. 创建分析上下文
        context = self._create_context(
            ticker=ticker,
            trade_date=trade_date,
            company_name=company_name,
            market_type=market_type,
            **kwargs
        )
        
        # 2. 创建数据访问管理器
        data_manager = DataAccessManager(context)
        
        # 3. 准备结果
        result = AnalysisResult(
            ticker=ticker,
            trade_date=trade_date,
            success=True,
            context=context
        )
        
        # 4. 按顺序执行各阶段
        phases = [
            AnalysisPhase.DATA_COLLECTION,
            AnalysisPhase.ANALYSTS,
            AnalysisPhase.RESEARCH_DEBATE,
            AnalysisPhase.TRADE_DECISION,
            AnalysisPhase.RISK_ASSESSMENT,
        ]
        
        for phase in phases:
            phase_result = self._execute_phase(phase, context, data_manager)
            result.phase_results.append(phase_result)
            
            if not phase_result.success:
                result.success = False
                result.error = f"阶段 {phase.value} 执行失败: {phase_result.error}"
                logger.error(f"❌ [StockAnalysisEngine] {result.error}")
                break
        
        # 5. 提取最终决策
        if result.success:
            result.final_decision = context.get(DataLayer.DECISIONS, "final_decision")

        # 6. 计算总耗时
        end_time = datetime.now()
        result.total_duration_seconds = (end_time - start_time).total_seconds()

        status = "✅" if result.success else "❌"
        logger.info(
            f"{status} [StockAnalysisEngine] 分析完成: {ticker} "
            f"耗时 {result.total_duration_seconds:.2f}s"
        )

        return result

    def _create_context(
        self,
        ticker: str,
        trade_date: str,
        company_name: Optional[str] = None,
        market_type: str = "cn",
        **kwargs
    ) -> AnalysisContext:
        """创建分析上下文"""
        context = AnalysisContext()

        # 设置基础上下文
        context.set(DataLayer.CONTEXT, "ticker", ticker, source="init")
        context.set(DataLayer.CONTEXT, "trade_date", trade_date, source="init")
        context.set(DataLayer.CONTEXT, "market_type", market_type, source="init")

        if company_name:
            context.set(DataLayer.CONTEXT, "company_name", company_name, source="init")

        # 设置额外参数
        for key, value in kwargs.items():
            context.set(DataLayer.CONTEXT, key, value, source="init")

        logger.debug(f"📋 [StockAnalysisEngine] 上下文创建完成: {context.context}")
        return context

    def _execute_phase(
        self,
        phase: AnalysisPhase,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> PhaseResult:
        """执行单个阶段"""
        start_time = datetime.now()

        logger.info(f"⏳ [StockAnalysisEngine] 执行阶段: {phase.value}")

        try:
            # 获取阶段执行器
            executor = self._get_phase_executor(phase)

            if executor is None:
                # 阶段执行器未实现，跳过
                logger.warning(f"⚠️ [StockAnalysisEngine] 阶段执行器未实现: {phase.value}")
                return PhaseResult(
                    phase=phase,
                    success=True,
                    duration_seconds=0.0,
                    outputs={"skipped": True}
                )

            # 执行阶段
            outputs = executor.execute(context, data_manager)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info(f"✅ [StockAnalysisEngine] 阶段完成: {phase.value} ({duration:.2f}s)")

            return PhaseResult(
                phase=phase,
                success=True,
                duration_seconds=duration,
                outputs=outputs or {}
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.error(f"❌ [StockAnalysisEngine] 阶段失败: {phase.value} - {str(e)}")

            return PhaseResult(
                phase=phase,
                success=False,
                duration_seconds=duration,
                error=str(e)
            )

    def _get_phase_executor(self, phase: AnalysisPhase) -> Optional[Any]:
        """获取阶段执行器"""
        if phase not in self._phase_executors:
            # 延迟导入和创建执行器
            self._phase_executors[phase] = self._create_phase_executor(phase)
        return self._phase_executors.get(phase)

    def _create_phase_executor(self, phase: AnalysisPhase) -> Optional[Any]:
        """创建阶段执行器"""
        from .phase_executors import (
            DataCollectionPhase,
            AnalystsPhase,
            ResearchDebatePhase,
            TradeDecisionPhase,
            RiskAssessmentPhase,
        )

        executor_map = {
            AnalysisPhase.DATA_COLLECTION: DataCollectionPhase,
            AnalysisPhase.ANALYSTS: AnalystsPhase,
            AnalysisPhase.RESEARCH_DEBATE: ResearchDebatePhase,
            AnalysisPhase.TRADE_DECISION: TradeDecisionPhase,
            AnalysisPhase.RISK_ASSESSMENT: RiskAssessmentPhase,
        }

        executor_class = executor_map.get(phase)
        if executor_class:
            return executor_class(
                llm_provider=self.llm_provider,
                config={"selected_analysts": self.selected_analysts}
            )
        return None

    def register_phase_executor(self, phase: AnalysisPhase, executor: Any) -> None:
        """
        注册阶段执行器

        允许外部注册自定义的阶段执行器

        Args:
            phase: 分析阶段
            executor: 执行器实例（需要有 execute(context, data_manager) 方法）
        """
        self._phase_executors[phase] = executor
        logger.debug(f"📋 [StockAnalysisEngine] 注册阶段执行器: {phase.value}")

    def get_context_summary(self, result: AnalysisResult) -> Dict[str, Any]:
        """
        获取分析上下文摘要

        Args:
            result: 分析结果

        Returns:
            上下文摘要字典
        """
        if result.context is None:
            return {}

        return {
            "context": result.context.context,
            "reports": list(result.context.reports.keys()),
            "decisions": list(result.context.decisions.keys()),
            "lineage_count": len(result.context.data_lineage),
        }

