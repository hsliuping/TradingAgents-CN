# tradingagents/core/engine/phase_executors/trade_decision.py
"""
交易决策阶段执行器

根据研究结论生成交易信号：
- Trader (交易员) - 生成具体的交易信号
"""

from typing import Any, Dict, Optional

from tradingagents.utils.logging_init import get_logger

from ..analysis_context import AnalysisContext
from ..data_access_manager import DataAccessManager
from ..data_contract import DataLayer
from .base import PhaseExecutor

logger = get_logger("default")


class TradeDecisionPhase(PhaseExecutor):
    """
    交易决策阶段执行器
    
    根据投资建议生成具体的交易信号
    """
    
    phase_name = "TradeDecisionPhase"
    
    def __init__(
        self,
        llm_provider: Any = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化交易决策阶段
        
        Args:
            llm_provider: LLM 提供者
            config: 阶段配置
        """
        super().__init__(llm_provider, config)
    
    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行交易决策阶段
        
        Args:
            context: 分析上下文
            data_manager: 数据访问管理器
            
        Returns:
            交易决策结果
        """
        self.log_start()
        
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.info(f"💹 [{self.phase_name}] 生成交易信号: {ticker}")
        
        outputs = {
            "ticker": ticker,
            "trade_signal": None
        }
        
        # 获取投资建议
        investment_plan = context.get(DataLayer.DECISIONS, "investment_plan")
        
        if investment_plan is None:
            logger.warning(f"⚠️ [{self.phase_name}] 未找到投资建议，跳过交易决策")
            return outputs
        
        # 生成交易信号
        trade_signal = self._generate_trade_signal(context, investment_plan)
        context.set(DataLayer.DECISIONS, "trade_signal", trade_signal, source="trader")
        outputs["trade_signal"] = trade_signal.get("action")
        
        self.log_end(outputs)
        return outputs
    
    def _generate_trade_signal(
        self,
        context: AnalysisContext,
        investment_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成交易信号
        
        TODO: 集成实际的 Trader Agent
        
        Args:
            context: 分析上下文
            investment_plan: 投资建议
            
        Returns:
            交易信号
        """
        ticker = context.get(DataLayer.CONTEXT, "ticker")
        recommendation = investment_plan.get("recommendation", "hold")
        confidence = investment_plan.get("confidence", 0.5)
        
        # 根据投资建议生成交易信号
        action_map = {
            "buy": "BUY",
            "sell": "SELL",
            "hold": "HOLD"
        }
        
        action = action_map.get(recommendation, "HOLD")
        
        # 根据置信度计算仓位
        if action == "HOLD":
            position_size = 0.0
        else:
            position_size = min(confidence, 1.0)  # 最大 100%
        
        return {
            "ticker": ticker,
            "action": action,
            "position_size": position_size,
            "confidence": confidence,
            "rationale": investment_plan.get("rationale", ""),
            "entry_price": None,  # 需要实时行情
            "stop_loss": None,
            "take_profit": None,
            "timestamp": None
        }

