"""
时机分析师智能体

分析买入卖出时机，评估交易时机选择的合理性
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class TimingAnalystAgent(BaseAgent):
    """
    时机分析师智能体
    
    分析买入卖出时机，包括:
    - 买入时是否处于相对低位
    - 卖出时是否处于相对高位
    - 与理论最优买卖点的差距
    - 持仓周期是否合理
    """
    
    metadata = BUILTIN_AGENTS["timing_analyst"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "TimingAnalystAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行时机分析
        
        Args:
            state: 包含以下键的状态字典:
                - trade_info: 交易信息 (trades, holding_period, pnl 等)
                - market_data: 市场K线数据
                - benchmark_data: 基准数据
                
        Returns:
            更新后的状态，包含:
                - timing_analysis: 时机分析报告
        """
        logger.info(f"⏰ [时机分析师] 开始分析交易时机...")

        # 提取输入数据
        trade_info = state.get("trade_info", {})
        market_data = state.get("market_data", {})

        logger.info(f"   📋 股票: {trade_info.get('code', 'N/A')}, 交易次数: {len(trade_info.get('trades', []))}")

        # 构建提示词（支持用户偏好）
        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(trade_info, market_data, user_id, preference_id)
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        # 调用 LLM
        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 分析...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
                logger.info(f"   📄 LLM 返回内容: {analysis[:100]}..." if len(analysis) > 100 else f"   📄 LLM 返回内容: {analysis}")
            except Exception as e:
                logger.error(f"   ❌ [时机分析师] LLM调用失败: {e}")
                analysis = f"时机分析失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法进行时机分析"

        logger.info(f"⏰ [时机分析师] ✅ 分析完成")

        # 只返回新增的字段，不返回整个 state（避免并发更新冲突）
        return {
            "timing_analysis": analysis,
        }
    
    def _build_prompt(self, trade_info: Dict, market_data: Dict, user_id: str = None, preference_id: str = "neutral") -> str:
        """构建时机分析提示词"""
        trades = trade_info.get("trades", [])

        # 格式化交易记录
        trade_list = []
        for t in trades:
            trade_list.append(
                f"- {t.get('date', 'N/A')}: {t.get('side', 'N/A')} "
                f"{t.get('quantity', 0)}股 @ {t.get('price', 0):.2f}"
            )
        trades_str = "\n".join(trade_list) if trade_list else "无交易记录"

        # 提取K线数据摘要
        kline_summary = market_data.get("summary", "无K线数据")

        # 准备模板变量
        template_variables = {
            "trades_str": trades_str,
            "kline_summary": kline_summary,
            "holding_period": trade_info.get('holding_period', 'N/A'),
            "avg_buy_price": trade_info.get('avg_buy_price', 0),
            "avg_sell_price": trade_info.get('avg_sell_price', 0),
            "return_rate": trade_info.get('return_rate', 0)
        }

        # 硬编码的降级提示词
        fallback_prompt = f"""你是一位专业的交易时机分析师。请分析以下交易的时机选择:

## 交易记录
{trades_str}

## 市场数据摘要
{kline_summary}

## 交易统计
- 持仓周期: {trade_info.get('holding_period', 'N/A')}天
- 买入均价: {trade_info.get('avg_buy_price', 0):.2f}
- 卖出均价: {trade_info.get('avg_sell_price', 0):.2f}
- 实际收益率: {trade_info.get('return_rate', 0):.2%}

## 分析要求
请从以下角度分析时机选择:
1. **买入时机评估**: 买入时是否处于相对低位？是否追高？
2. **卖出时机评估**: 卖出时是否处于相对高位？是否割肉？
3. **持仓周期评估**: 持仓时间是否合理？是否过长或过短？
4. **理论最优对比**: 与理论最优买卖点相比，差距多少？
5. **时机评分**: 给出1-10分的时机选择评分

请用简洁专业的语言回答。"""

        # 尝试从模板系统获取提示词
        try:
            from tradingagents.utils.template_client import get_agent_prompt

            prompt = get_agent_prompt(
                agent_type="reviewers",
                agent_name="timing_analyst",
                variables=template_variables,
                user_id=user_id,
                preference_id=preference_id,
                fallback_prompt=fallback_prompt,
                context=None
            )
            logger.info(f"✅ [时机分析师] 成功从模板系统获取提示词 (长度: {len(prompt)})")
            return prompt

        except Exception as e:
            logger.warning(f"⚠️ [时机分析师] 模板系统获取失败，使用降级提示词: {e}")
            return fallback_prompt

