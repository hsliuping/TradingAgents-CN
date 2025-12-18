"""
仓位分析师 v2.0 (复盘分析)

基于ResearcherAgent基类实现的仓位分析师
"""

import logging
from typing import Dict, Any, List

from ...researcher import ResearcherAgent
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
class PositionAnalystV2(ResearcherAgent):
    """
    仓位分析师 v2.0 (复盘分析)
    
    功能：
    - 分析仓位控制和加减仓策略
    - 评估仓位与风险的匹配度
    - 分析资金利用效率
    
    工作流程：
    1. 读取交易信息和仓位历史
    2. 使用LLM分析仓位管理
    3. 生成仓位分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("position_analyst_v2", llm)

        result = agent.execute({
            "trade_info": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="position_analyst_v2",
        name="仓位分析师 v2.0",
        description="分析仓位控制和加减仓策略的合理性",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )

    researcher_type = "review_position"
    stance = "neutral"
    output_field = "position_analysis"

    def _build_system_prompt(self, stance: str) -> str:
        """构建系统提示词"""
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="reviewers_v2",
                    agent_name="position_analyst_v2",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取仓位分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        return """您是一位专业的仓位分析师。

您的职责是分析仓位管理的合理性。

分析要点：
1. 初始仓位 - 首次建仓比例是否合理
2. 加减仓策略 - 加减仓时机和比例
3. 风险匹配 - 仓位与风险的匹配度
4. 资金效率 - 资金利用效率
5. 仓位评分 - 1-10分的仓位管理评分

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """构建用户提示词"""
        trade_info = state.get("trade_info", {})
        code = trade_info.get("code", ticker)
        trades = trade_info.get("trades", [])
        
        # 分析仓位变化
        position_changes = []
        current_position = 0
        for t in trades:
            side = t.get("side", "")
            qty = t.get("quantity", 0)
            if side == "buy":
                current_position += qty
            else:
                current_position -= qty
            position_changes.append(
                f"- {t.get('date', 'N/A')}: {side} {qty}股, 当前持仓: {current_position}股"
            )
        position_str = "\n".join(position_changes) if position_changes else "无仓位变化"
        
        return f"""请分析以下交易的仓位管理：

=== 交易信息 ===
- 股票代码: {code}
- 交易次数: {len(trades)}
- 最终收益: {trade_info.get('pnl', 0):.2%}

=== 仓位变化 ===
{position_str}

请撰写详细的仓位分析报告，包括：
1. 初始仓位评估
2. 加减仓策略分析
3. 仓位与风险匹配度
4. 资金利用效率
5. 仓位管理评分（1-10分）"""

    def _get_required_reports(self) -> List[str]:
        """获取需要的数据列表"""
        return ["trade_info"]

