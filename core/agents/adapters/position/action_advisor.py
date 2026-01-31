"""
操作建议师智能体

综合技术面、基本面、风险评估，给出持仓操作建议
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class ActionAdvisorAgent(BaseAgent):
    """
    操作建议师智能体
    
    综合各维度分析，给出操作建议:
    - 持有/加仓/减仓/清仓建议
    - 目标价位设置
    - 操作比例建议
    - 风险提示
    """
    
    metadata = BUILTIN_AGENTS["pa_advisor"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "ActionAdvisorAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行操作建议分析"""
        logger.info(f"💡 [操作建议师] 开始综合分析...")

        position_info = state.get("position_info", {})
        technical_analysis = state.get("technical_analysis", "")
        fundamental_analysis = state.get("fundamental_analysis", "")
        risk_analysis = state.get("risk_analysis", "")
        user_goal = state.get("user_goal", {})

        logger.info(f"   📋 股票: {position_info.get('code', 'N/A')}")

        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(
            position_info, technical_analysis, fundamental_analysis, 
            risk_analysis, user_goal, user_id, preference_id
        )
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 分析...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
            except Exception as e:
                logger.error(f"   ❌ LLM调用失败: {e}")
                analysis = f"操作建议生成失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法生成操作建议"

        logger.info(f"💡 [操作建议师] ✅ 分析完成")
        return {"action_advice": analysis}
    
    def _build_prompt(self, position_info: Dict, technical: str, fundamental: str,
                      risk: str, user_goal: Dict, user_id: str = None, 
                      preference_id: str = "neutral") -> str:
        """构建操作建议提示词"""
        template_variables = {
            "code": position_info.get("code", "N/A"),
            "name": position_info.get("name", "N/A"),
            "current_price": position_info.get("current_price", 0),
            "cost_price": position_info.get("cost_price", 0),
            "unrealized_pnl_pct": position_info.get("unrealized_pnl_pct", 0),
            "technical_analysis": technical[:1500] if technical else "无技术面分析",
            "fundamental_analysis": fundamental[:1500] if fundamental else "无基本面分析",
            "risk_analysis": risk[:1500] if risk else "无风险评估",
            "target_return": user_goal.get("target_return", 10),
            "stop_loss": user_goal.get("stop_loss", -10),
        }

        fallback_prompt = f"""你是一位专业的投资分析师。请综合以下分析，提供持仓分析观点:

## 持仓信息
- 股票: {position_info.get('code', 'N/A')} {position_info.get('name', 'N/A')}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2%}

## 技术面分析
{technical[:1500] if technical else '无'}

## 基本面分析
{fundamental[:1500] if fundamental else '无'}

## 风险评估
{risk[:1500] if risk else '无'}

## 用户目标
- 目标收益: {user_goal.get('target_return', 10)}%
- 止损线: {user_goal.get('stop_loss', -10)}%

## 输出要求
请给出JSON格式的持仓分析观点:
```json
{{
    "analysis_view": "看涨|看跌|中性",
    "position_analysis": "当前持仓分析（如：建议关注/建议谨慎/建议观望）",
    "price_analysis_range": {{
        "lower_bound": 价格区间下限,
        "upper_bound": 价格区间上限,
        "current_position": "当前价格在区间中的位置分析"
    }},
    "risk_reference_price": "风险控制参考价位（仅供参考，不构成操作建议）",
    "confidence": 0-100的信心度,
    "risk_level": "低|中|高",
    "summary": "综合评价",
    "reasoning": "分析依据",
    "risk_warning": "风险提示",
    "disclaimer": "本分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。"
}}
```

**免责声明**：
本分析报告仅供参考，不构成投资建议。所有价格区间、市场观点均为分析参考，
不构成买卖操作建议。投资有风险，决策需谨慎。投资者应根据自身情况，结合
专业投资顾问意见，独立做出投资决策。"""

        prompt = self._get_prompt_from_template(
            agent_type="position_analysis",
            agent_name="pa_advisor",
            variables=template_variables,
            context={"user_id": user_id, "preference_id": preference_id},
            fallback_prompt=fallback_prompt
        )
        if prompt:
            logger.info(f"✅ [操作建议师] 成功从模板系统获取提示词")
            return prompt
        logger.warning(f"⚠️ [操作建议师] 模板系统未返回提示词，使用降级提示词")
        return fallback_prompt

