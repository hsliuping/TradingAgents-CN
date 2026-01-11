"""
技术面分析师智能体

分析K线走势、技术指标、支撑阻力位，评估技术面状态
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class TechnicalAnalystAgent(BaseAgent):
    """
    技术面分析师智能体
    
    分析持仓股票的技术面，包括:
    - K线形态和趋势
    - 技术指标状态
    - 支撑阻力位分析
    - 短期走势预判
    """
    
    metadata = BUILTIN_AGENTS["pa_technical"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "TechnicalAnalystAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行技术面分析"""
        logger.info(f"📈 [技术面分析师] 开始分析...")

        position_info = state.get("position_info", {})
        market_data = state.get("market_data", {})

        logger.info(f"   📋 股票: {position_info.get('code', 'N/A')}")

        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(position_info, market_data, user_id, preference_id)
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 分析...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
            except Exception as e:
                logger.error(f"   ❌ LLM调用失败: {e}")
                analysis = f"技术面分析失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法进行技术面分析"

        logger.info(f"📈 [技术面分析师] ✅ 分析完成")
        return {"technical_analysis": analysis}
    
    def _build_prompt(self, position_info: Dict, market_data: Dict, 
                      user_id: str = None, preference_id: str = "neutral") -> str:
        """构建技术面分析提示词"""
        template_variables = {
            "code": position_info.get("code", "N/A"),
            "name": position_info.get("name", "N/A"),
            "current_price": position_info.get("current_price", 0),
            "cost_price": position_info.get("cost_price", 0),
            "quantity": position_info.get("quantity", 0),
            "unrealized_pnl_pct": position_info.get("unrealized_pnl_pct", 0),
            "kline_summary": market_data.get("summary", "无K线数据"),
            "technical_indicators": market_data.get("technical_indicators", "无技术指标数据"),
        }

        fallback_prompt = f"""你是一位专业的技术面分析师。请分析以下持仓股票的技术面:

## 持仓信息
- 股票代码: {position_info.get('code', 'N/A')}
- 股票名称: {position_info.get('name', 'N/A')}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2%}

## 市场数据
{market_data.get('summary', '无K线数据')}

## 技术指标
{market_data.get('technical_indicators', '无技术指标数据')}

## 分析要求
1. **趋势判断**: 当前处于上升/下降/震荡趋势
2. **支撑阻力**: 关键支撑位和阻力位
3. **技术指标**: MACD/KDJ/RSI等指标状态
4. **短期预判**: 未来3-5天可能走势
5. **技术评分**: 1-10分的技术面评分

请用简洁专业的语言回答。"""

        prompt = self._get_prompt_from_template(
            agent_type="position_analysis",
            agent_name="pa_technical",
            variables=template_variables,
            context={"user_id": user_id, "preference_id": preference_id},
            fallback_prompt=fallback_prompt
        )
        if prompt:
            logger.info(f"✅ [技术面分析师] 成功从模板系统获取提示词")
            return prompt
        logger.warning(f"⚠️ [技术面分析师] 模板系统未返回提示词，使用降级提示词")
        return fallback_prompt

