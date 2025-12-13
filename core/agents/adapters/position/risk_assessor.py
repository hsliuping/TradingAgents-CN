"""
风险评估师智能体

评估持仓风险、设置止损止盈、分析仓位合理性
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class RiskAssessorAgent(BaseAgent):
    """
    风险评估师智能体
    
    评估持仓风险，包括:
    - 仓位风险评估
    - 止损止盈设置
    - 波动性分析
    - 最大回撤预估
    """
    
    metadata = BUILTIN_AGENTS["pa_risk"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "RiskAssessorAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行风险评估"""
        logger.info(f"⚠️ [风险评估师] 开始评估...")

        position_info = state.get("position_info", {})
        capital_info = state.get("capital_info", {})
        market_data = state.get("market_data", {})

        logger.info(f"   📋 股票: {position_info.get('code', 'N/A')}")

        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(position_info, capital_info, market_data, user_id, preference_id)
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 分析...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
            except Exception as e:
                logger.error(f"   ❌ LLM调用失败: {e}")
                analysis = f"风险评估失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法进行风险评估"

        logger.info(f"⚠️ [风险评估师] ✅ 评估完成")
        return {"risk_analysis": analysis}
    
    def _build_prompt(self, position_info: Dict, capital_info: Dict, market_data: Dict,
                      user_id: str = None, preference_id: str = "neutral") -> str:
        """构建风险评估提示词"""
        # 计算仓位占比
        market_value = position_info.get("market_value", 0)
        total_assets = capital_info.get("total_assets", 0)
        position_ratio = (market_value / total_assets * 100) if total_assets > 0 else 0
        
        template_variables = {
            "code": position_info.get("code", "N/A"),
            "name": position_info.get("name", "N/A"),
            "current_price": position_info.get("current_price", 0),
            "cost_price": position_info.get("cost_price", 0),
            "quantity": position_info.get("quantity", 0),
            "market_value": market_value,
            "unrealized_pnl": position_info.get("unrealized_pnl", 0),
            "unrealized_pnl_pct": position_info.get("unrealized_pnl_pct", 0),
            "position_ratio": position_ratio,
            "total_assets": total_assets,
            "volatility": market_data.get("volatility", "未知"),
        }

        fallback_prompt = f"""你是一位专业的风险评估师。请评估以下持仓的风险:

## 持仓信息
- 股票代码: {position_info.get('code', 'N/A')}
- 股票名称: {position_info.get('name', 'N/A')}
- 持仓数量: {position_info.get('quantity', 0)} 股
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 持仓市值: {market_value:.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl', 0):.2f} ({position_info.get('unrealized_pnl_pct', 0):.2%})

## 资金信息
- 总资产: {total_assets:.2f}
- 仓位占比: {position_ratio:.2f}%

## 分析要求
1. **仓位风险**: 当前仓位是否过重
2. **止损设置**: 建议止损价位
3. **止盈设置**: 建议止盈价位
4. **波动风险**: 股票波动性评估
5. **风险等级**: 低/中/高风险评级

请用简洁专业的语言回答。"""

        try:
            from tradingagents.utils.template_client import get_agent_prompt
            prompt = get_agent_prompt(
                agent_type="position_analysis",
                agent_name="pa_risk",
                variables=template_variables,
                user_id=user_id,
                preference_id=preference_id,
                fallback_prompt=fallback_prompt,
                context=None
            )
            logger.info(f"✅ [风险评估师] 成功从模板系统获取提示词")
            return prompt
        except Exception as e:
            logger.warning(f"⚠️ [风险评估师] 模板系统获取失败: {e}")
            return fallback_prompt

