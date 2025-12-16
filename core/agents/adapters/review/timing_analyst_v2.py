"""
时机分析师 v2.0 (复盘分析)

基于ResearcherAgent基类实现的时机分析师
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
class TimingAnalystV2(ResearcherAgent):
    """
    时机分析师 v2.0 (复盘分析)
    
    功能：
    - 分析买入卖出时机
    - 评估交易时机选择的合理性
    - 与理论最优买卖点对比
    
    工作流程：
    1. 读取交易信息和市场数据
    2. 使用LLM分析时机选择
    3. 生成时机分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("timing_analyst_v2", llm)

        result = agent.execute({
            "trade_info": {...},
            "market_data": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="timing_analyst_v2",
        name="时机分析师 v2.0",
        description="分析买入卖出时机，评估交易时机选择的合理性",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )

    researcher_type = "review_timing"
    stance = "neutral"
    output_field = "timing_analysis"

    def _build_system_prompt(self, stance: str) -> str:
        """构建系统提示词"""
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="review_analysis",
                    agent_name="timing_analyst",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取时机分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        return """您是一位专业的时机分析师。

您的职责是分析交易时机的选择是否合理。

分析要点：
1. 买入时机 - 是否处于相对低位
2. 卖出时机 - 是否处于相对高位
3. 与最优点差距 - 与理论最优买卖点的差距
4. 持仓周期 - 持仓时间是否合理
5. 时机评分 - 1-10分的时机选择评分

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
        market_data = state.get("market_data", {})
        
        code = trade_info.get("code", ticker)
        trades = trade_info.get("trades", [])
        
        # 格式化交易记录
        trade_list = []
        for t in trades:
            trade_list.append(
                f"- {t.get('date', 'N/A')}: {t.get('side', 'N/A')} "
                f"{t.get('quantity', 0)}股 @ {t.get('price', 0):.2f}"
            )
        trade_str = "\n".join(trade_list) if trade_list else "无交易记录"
        
        return f"""请分析以下交易的时机选择：

=== 交易信息 ===
- 股票代码: {code}
- 持仓周期: {trade_info.get('holding_period', 0)}天
- 收益率: {trade_info.get('pnl', 0):.2%}

=== 交易记录 ===
{trade_str}

=== 市场数据 ===
{market_data.get('summary', '无市场数据')}

请撰写详细的时机分析报告，包括：
1. 买入时机评估
2. 卖出时机评估
3. 与最优点的差距
4. 持仓周期合理性
5. 时机选择评分（1-10分）"""

    def _get_required_reports(self) -> List[str]:
        """获取需要的数据列表"""
        return ["trade_info", "market_data"]

