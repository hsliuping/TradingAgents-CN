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
        config: Optional[Dict[str, Any]] = None,
        memory_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化交易决策阶段

        Args:
            llm_provider: LLM 提供者
            config: 阶段配置
            memory_config: Memory 配置
        """
        super().__init__(llm_provider, config)
        self.memory_config = memory_config or {}
        self._trader = None
    
    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行交易决策阶段
        """
        self.log_start()

        ticker = context.get(DataLayer.CONTEXT, "ticker")
        logger.info(f"💹 [{self.phase_name}] 生成交易信号: {ticker}")

        outputs = {
            "ticker": ticker,
            "trade_signal": None,
            "trader_investment_plan": None
        }

        # 获取投资建议
        investment_plan = context.get(DataLayer.DECISIONS, "investment_plan")

        if investment_plan is None:
            logger.warning(f"⚠️ [{self.phase_name}] 未找到投资建议，跳过交易决策")
            self.log_end(outputs)
            return outputs

        # 使用实际的 Trader Agent
        trader_result = self._run_trader(context, investment_plan)

        if trader_result:
            trader_plan = trader_result.get("trader_investment_plan", "")

            # 保存交易员的投资计划
            context.set(DataLayer.DECISIONS, "trader_investment_plan", trader_plan, source="trader")
            outputs["trader_investment_plan"] = "generated" if trader_plan else None

            # 从交易员结果中解析交易信号
            trade_signal = self._parse_trade_signal(context, trader_plan, investment_plan)
            context.set(DataLayer.DECISIONS, "trade_signal", trade_signal, source="trader")
            outputs["trade_signal"] = trade_signal.get("action")

            logger.info(f"📝 [{self.phase_name}] 交易信号: {trade_signal.get('action')}, "
                       f"置信度: {trade_signal.get('confidence', 0):.2f}")
        else:
            # 回退到简单解析
            trade_signal = self._generate_trade_signal(context, investment_plan)
            context.set(DataLayer.DECISIONS, "trade_signal", trade_signal, source="trader")
            outputs["trade_signal"] = trade_signal.get("action")

        self.log_end(outputs)
        return outputs

    def _get_trader(self):
        """获取或创建 Trader Agent"""
        if self._trader is None:
            try:
                from tradingagents.agents.trader.trader import create_trader
                # 支持两种 key 格式: "trader" 或 "trader_memory"
                memory = self.memory_config.get("trader") or self.memory_config.get("trader_memory")
                self._trader = create_trader(self.llm_provider, memory)
                logger.debug("💰 [TradeDecision] 创建 Trader Agent")
            except Exception as e:
                logger.error(f"❌ [TradeDecision] 创建 Trader 失败: {e}")
        return self._trader

    def _run_trader(self, context: AnalysisContext, investment_plan: Any) -> Optional[Dict[str, Any]]:
        """运行 Trader Agent"""
        trader = self._get_trader()
        if not trader:
            logger.warning("⚠️ [TradeDecision] Trader 不可用，使用简单解析")
            return None

        try:
            # 构建兼容现有 Agent 的状态
            ticker = context.get(DataLayer.CONTEXT, "ticker") or ""
            trade_date = context.get(DataLayer.CONTEXT, "trade_date") or ""

            state = {
                "company_of_interest": ticker,
                "trade_date": trade_date,
                "investment_plan": investment_plan if isinstance(investment_plan, str) else str(investment_plan),
                # 收集所有分析报告
                "market_report": context.get(DataLayer.REPORTS, "market_report") or "",
                "sentiment_report": context.get(DataLayer.REPORTS, "sentiment_report") or "",
                "news_report": context.get(DataLayer.REPORTS, "news_report") or "",
                "fundamentals_report": context.get(DataLayer.REPORTS, "fundamentals_report") or "",
                "sector_report": context.get(DataLayer.REPORTS, "sector_report") or "",
                "index_report": context.get(DataLayer.REPORTS, "index_report") or "",
            }

            result = trader(state)
            logger.info("💰 [Trader] 交易决策生成完成")
            return result

        except Exception as e:
            logger.error(f"❌ [Trader] 执行失败: {e}")
            return None

    def _parse_trade_signal(
        self,
        context: AnalysisContext,
        trader_plan: str,
        investment_plan: Any
    ) -> Dict[str, Any]:
        """从交易员计划中解析交易信号"""
        ticker = context.get(DataLayer.CONTEXT, "ticker")

        # 合并文本进行分析
        combined_text = trader_plan
        if isinstance(investment_plan, str):
            combined_text = f"{investment_plan}\n{trader_plan}"

        recommendation, confidence = self._parse_recommendation_from_text(combined_text)

        action_map = {
            "buy": "BUY",
            "sell": "SELL",
            "hold": "HOLD"
        }
        action = action_map.get(recommendation.lower(), "HOLD")

        if action == "HOLD":
            position_size = 0.0
        else:
            position_size = min(confidence, 1.0)

        return {
            "ticker": ticker,
            "action": action,
            "position_size": position_size,
            "confidence": confidence,
            "rationale": trader_plan[:500] if len(trader_plan) > 500 else trader_plan,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "timestamp": None
        }
    
    def _generate_trade_signal(
        self,
        context: AnalysisContext,
        investment_plan: Any
    ) -> Dict[str, Any]:
        """
        生成交易信号

        TODO: 集成实际的 Trader Agent

        Args:
            context: 分析上下文
            investment_plan: 投资建议（可能是字典或字符串）

        Returns:
            交易信号
        """
        ticker = context.get(DataLayer.CONTEXT, "ticker")

        # 处理不同类型的投资建议
        if isinstance(investment_plan, dict):
            recommendation = investment_plan.get("recommendation", "hold")
            confidence = investment_plan.get("confidence", 0.5)
            rationale = investment_plan.get("rationale", "")
        elif isinstance(investment_plan, str):
            # 从文本中提取建议
            recommendation, confidence = self._parse_recommendation_from_text(investment_plan)
            rationale = investment_plan[:500] if len(investment_plan) > 500 else investment_plan
        else:
            recommendation = "hold"
            confidence = 0.5
            rationale = ""

        # 根据投资建议生成交易信号
        action_map = {
            "buy": "BUY",
            "sell": "SELL",
            "hold": "HOLD"
        }

        action = action_map.get(recommendation.lower(), "HOLD")

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
            "rationale": rationale,
            "entry_price": None,  # 需要实时行情
            "stop_loss": None,
            "take_profit": None,
            "timestamp": None
        }

    def _parse_recommendation_from_text(self, text: str) -> tuple:
        """
        从文本中解析投资建议

        Args:
            text: 投资建议文本

        Returns:
            (recommendation, confidence) 元组
        """
        text_lower = text.lower()

        # 简单的关键词匹配
        buy_keywords = ["买入", "增持", "看多", "建议买入", "buy", "bullish", "看涨"]
        sell_keywords = ["卖出", "减持", "看空", "建议卖出", "sell", "bearish", "看跌"]
        hold_keywords = ["持有", "观望", "hold", "neutral", "中性"]

        buy_score = sum(1 for kw in buy_keywords if kw in text_lower)
        sell_score = sum(1 for kw in sell_keywords if kw in text_lower)
        hold_score = sum(1 for kw in hold_keywords if kw in text_lower)

        # 确定建议
        if buy_score > sell_score and buy_score > hold_score:
            recommendation = "buy"
            confidence = min(0.5 + buy_score * 0.1, 0.9)
        elif sell_score > buy_score and sell_score > hold_score:
            recommendation = "sell"
            confidence = min(0.5 + sell_score * 0.1, 0.9)
        else:
            recommendation = "hold"
            confidence = 0.5

        return recommendation, confidence

