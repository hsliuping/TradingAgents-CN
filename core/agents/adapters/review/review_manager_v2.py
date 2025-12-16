"""
复盘总结师 v2.0 (复盘分析)

基于ManagerAgent基类实现的复盘总结师
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
class ReviewManagerV2(ManagerAgent):
    """
    复盘总结师 v2.0 (复盘分析)
    
    功能：
    - 综合所有分析维度
    - 生成完整复盘报告
    - 给出改进建议
    
    工作流程：
    1. 读取各维度分析结果
    2. 使用LLM综合总结
    3. 生成复盘报告和改进建议
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("review_manager_v2", llm)

        result = agent.execute({
            "trade_info": {...},
            "timing_analysis": "...",
            "position_analysis": "...",
            "emotion_analysis": "...",
            "attribution_analysis": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="review_manager_v2",
        name="复盘总结师 v2.0",
        description="综合所有分析维度，生成完整复盘报告和改进建议",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )

    manager_type = "review_manager"
    output_field = "review_summary"
    enable_debate = False

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="review_analysis",
                    agent_name="review_manager",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取复盘总结师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        return """您是一位专业的复盘总结师。

您的职责是综合各维度分析，生成完整的复盘报告。

总结要点：
1. 整体评价 - 综合评分和总体评价
2. 优点识别 - 本次交易的优点
3. 不足分析 - 本次交易的不足
4. 改进建议 - 具体的改进措施
5. 经验总结 - 可复用的经验教训

请使用中文，基于真实数据进行总结。

输出格式要求：
请给出JSON格式的复盘报告：
```json
{
    "overall_score": 1-10的总体评分,
    "summary": "综合评价",
    "strengths": ["优点1", "优点2", ...],
    "weaknesses": ["不足1", "不足2", ...],
    "suggestions": ["建议1", "建议2", ...],
    "lessons": "经验教训总结"
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
        """构建用户提示词"""
        trade_info = state.get("trade_info", {})
        code = trade_info.get("code", ticker)
        
        # 提取各维度分析
        timing = state.get("timing_analysis", "无时机分析")
        position = state.get("position_analysis", "无仓位分析")
        emotion = state.get("emotion_analysis", "无情绪分析")
        attribution = state.get("attribution_analysis", "无归因分析")
        
        return f"""请综合以下分析，生成复盘报告：

=== 交易信息 ===
- 股票代码: {code}
- 收益率: {trade_info.get('pnl', 0):.2%}
- 持仓周期: {trade_info.get('holding_period', 0)}天

=== 时机分析 ===
{timing[:1500]}

=== 仓位分析 ===
{position[:1500]}

=== 情绪分析 ===
{emotion[:1500]}

=== 归因分析 ===
{attribution[:1500]}

请给出JSON格式的复盘报告。"""

    def _get_required_inputs(self) -> List[str]:
        """获取需要的输入列表"""
        return [
            "timing_analysis",
            "position_analysis",
            "emotion_analysis",
            "attribution_analysis"
        ]

