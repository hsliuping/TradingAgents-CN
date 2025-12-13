"""
情绪分析师智能体

分析交易中的情绪化操作和纪律执行情况
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class EmotionAnalystAgent(BaseAgent):
    """
    情绪分析师智能体
    
    分析交易情绪和纪律，包括:
    - 是否存在追涨杀跌行为
    - 是否因恐慌而抛售
    - 是否因贪婪而过度持有
    - 交易纪律执行情况
    """
    
    metadata = BUILTIN_AGENTS["emotion_analyst"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "EmotionAnalystAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行情绪分析
        
        Args:
            state: 包含以下键的状态字典:
                - trade_info: 交易信息
                - market_data: 市场数据 (用于判断追涨杀跌)
                
        Returns:
            更新后的状态，包含:
                - emotion_analysis: 情绪分析报告
        """
        trade_info = state.get("trade_info", {})
        market_data = state.get("market_data", {})

        logger.info(f"😤 [情绪分析师] 开始分析情绪控制...")
        logger.info(f"   📋 股票: {trade_info.get('code', 'N/A')}, 交易次数: {len(trade_info.get('trades', []))}")

        # 构建提示词（支持用户偏好）
        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(trade_info, market_data, user_id, preference_id)
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 分析...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
                logger.info(f"   📄 LLM 返回内容: {analysis[:100]}..." if len(analysis) > 100 else f"   📄 LLM 返回内容: {analysis}")
            except Exception as e:
                logger.error(f"   ❌ [情绪分析师] LLM调用失败: {e}")
                analysis = f"情绪分析失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法进行情绪分析"

        logger.info(f"😤 [情绪分析师] ✅ 分析完成")

        # 只返回新增的字段，不返回整个 state（避免并发更新冲突）
        return {
            "emotion_analysis": analysis,
        }
    
    def _build_prompt(self, trade_info: Dict, market_data: Dict, user_id: str = None, preference_id: str = "neutral") -> str:
        """构建情绪分析提示词"""
        trades = trade_info.get("trades", [])

        # 分析交易行为模式
        trade_patterns = []
        for t in trades:
            price_change = t.get("price_change_before", 0)  # 交易前价格变化
            pattern = "上涨中" if price_change > 0 else "下跌中" if price_change < 0 else "震荡中"
            trade_patterns.append(
                f"- {t.get('date', 'N/A')}: {t.get('side', 'N/A')} "
                f"(交易前市场{pattern}, 变化{price_change:.2%})"
            )

        pattern_str = "\n".join(trade_patterns) if trade_patterns else "无法分析交易模式"

        # 准备模板变量
        template_variables = {
            "pattern_str": pattern_str,
            "return_rate": trade_info.get('return_rate', 0),
            "max_profit": trade_info.get('max_profit', 0),
            "max_loss": trade_info.get('max_loss', 0),
            "holding_period": trade_info.get('holding_period', 0)
        }

        # 硬编码的降级提示词
        fallback_prompt = f"""你是一位专业的交易心理分析师。请分析以下交易中的情绪因素:

## 交易行为分析
{pattern_str}

## 交易结果
- 实际收益率: {trade_info.get('return_rate', 0):.2%}
- 最大浮盈: {trade_info.get('max_profit', 0):.2%}
- 最大浮亏: {trade_info.get('max_loss', 0):.2%}
- 持仓周期: {trade_info.get('holding_period', 0)}天

## 分析要求
请从以下角度分析交易情绪:
1. **追涨杀跌分析**: 是否在上涨时追买？是否在下跌时恐慌卖出？
2. **贪婪与恐惧**: 是否因贪婪错过最佳卖点？是否因恐惧过早止盈/止损？
3. **纪律执行评估**: 是否有明确的交易计划？是否严格执行？
4. **情绪化操作识别**: 指出可能的情绪化操作及其影响
5. **情绪评分**: 给出1-10分的情绪控制评分

请用简洁专业的语言回答，并给出改进建议。"""

        # 尝试从模板系统获取提示词
        try:
            from tradingagents.utils.template_client import get_agent_prompt

            prompt = get_agent_prompt(
                agent_type="reviewers",
                agent_name="emotion_analyst",
                variables=template_variables,
                user_id=user_id,
                preference_id=preference_id,
                fallback_prompt=fallback_prompt,
                context=None
            )
            logger.info(f"✅ [情绪分析师] 成功从模板系统获取提示词 (长度: {len(prompt)})")
            return prompt

        except Exception as e:
            logger.warning(f"⚠️ [情绪分析师] 模板系统获取失败，使用降级提示词: {e}")
            return fallback_prompt

