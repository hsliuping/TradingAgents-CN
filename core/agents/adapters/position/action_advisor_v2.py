"""
操作建议师 v2.0 (持仓分析)

基于ManagerAgent基类实现的操作建议师
"""

import logging
from typing import Dict, Any, List

from ...manager import ManagerAgent
from ...config import AgentMetadata, AgentCategory, LicenseTier
from ...registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None


@register_agent
class ActionAdvisorV2(ManagerAgent):
    """
    操作建议师 v2.0 (持仓分析)
    
    功能：
    - 综合技术面、基本面、风险评估
    - 给出持仓操作建议
    - 设置目标价位和止损止盈
    
    工作流程：
    1. 读取各维度分析结果
    2. 使用LLM综合决策
    3. 生成操作建议
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("pa_advisor_v2", llm)

        result = agent.execute({
            "position_info": {...},
            "technical_analysis": "...",
            "fundamental_analysis": "...",
            "risk_analysis": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="pa_advisor_v2",
        name="操作建议师 v2.0",
        description="综合各维度分析，给出持仓操作建议",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 不需要工具
    )

    # 管理者类型
    manager_type = "position_advisor"
    
    # 输出字段名
    output_field = "action_advice"
    
    # 是否启用辩论（持仓分析不需要辩论）
    enable_debate = False

    def _build_system_prompt(self) -> str:
        """
        构建系统提示词
        
        Returns:
            系统提示词
        """
        # 从模板系统获取提示词
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="position_analysis",
                    agent_name="pa_advisor",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取操作建议师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        # 降级：使用默认提示词
        return """您是一位专业的投资顾问。

您的职责是综合各维度分析，给出持仓操作建议。

决策要点：
1. 操作建议 - 持有/加仓/减仓/清仓
2. 操作比例 - 建议操作的仓位比例
3. 目标价位 - 目标买入/卖出价格
4. 止损止盈 - 止损价位和止盈价位
5. 风险提示 - 主要风险点

请使用中文，基于真实数据进行决策。

输出格式要求：
请给出JSON格式的操作建议：
```json
{
    "action": "持有|加仓|减仓|清仓",
    "action_ratio": 0-100的百分比,
    "target_price": 目标价位,
    "stop_loss_price": 止损价位,
    "confidence": 0-100的信心度,
    "risk_level": "低|中|高",
    "summary": "综合评价",
    "reasoning": "操作依据",
    "risk_warning": "风险提示"
}
```"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        inputs: Dict[str, str],
        debate_summary: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词
        
        Args:
            ticker: 股票代码（从position_info中提取）
            analysis_date: 分析日期
            inputs: 各类分析结果（technical_analysis, fundamental_analysis等）
            debate_summary: 辩论总结（持仓分析不使用）
            state: 当前状态
            
        Returns:
            用户提示词
        """
        position_info = state.get("position_info", {})
        user_goal = state.get("user_goal", {})
        
        code = position_info.get("code", ticker)
        name = position_info.get("name", "N/A")
        
        # 提取各维度分析
        technical = state.get("technical_analysis", "无技术面分析")
        fundamental = state.get("fundamental_analysis", "无基本面分析")
        risk = state.get("risk_analysis", "无风险评估")
        
        return f"""请综合以下分析，给出持仓操作建议：

=== 持仓信息 ===
- 股票: {code} {name}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2%}

=== 技术面分析 ===
{technical[:1500]}

=== 基本面分析 ===
{fundamental[:1500]}

=== 风险评估 ===
{risk[:1500]}

=== 用户目标 ===
- 目标收益: {user_goal.get('target_return', 10)}%
- 止损线: {user_goal.get('stop_loss', -10)}%

请给出JSON格式的操作建议。"""

    def _get_required_inputs(self) -> List[str]:
        """
        获取需要的输入列表
        
        Returns:
            输入字段名列表
        """
        return [
            "technical_analysis",
            "fundamental_analysis",
            "risk_analysis"
        ]

