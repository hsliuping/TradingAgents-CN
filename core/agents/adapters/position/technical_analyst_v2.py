"""
技术面分析师 v2.0 (持仓分析)

基于ResearcherAgent基类实现的技术面分析师
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
class TechnicalAnalystV2(ResearcherAgent):
    """
    技术面分析师 v2.0 (持仓分析)
    
    功能：
    - 分析K线走势和技术指标
    - 评估支撑阻力位
    - 判断短期走势
    
    工作流程：
    1. 读取持仓信息和市场数据
    2. 使用LLM分析技术面
    3. 生成技术面分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("pa_technical_v2", llm)

        result = agent.execute({
            "position_info": {...},
            "market_data": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="pa_technical_v2",
        name="技术面分析师 v2.0",
        description="分析持仓股票的技术面，包括K线形态、技术指标、支撑阻力位",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 不需要工具
    )

    # 研究员类型
    researcher_type = "position_technical"
    
    # 立场（中性）
    stance = "neutral"
    
    # 输出字段名
    output_field = "technical_analysis"

    def _build_system_prompt(self, stance: str) -> str:
        """
        构建系统提示词
        
        Args:
            stance: 立场（对于技术分析师，始终为neutral）
            
        Returns:
            系统提示词
        """
        # 从模板系统获取提示词
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="position_analysis",
                    agent_name="pa_technical",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取技术面分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        # 降级：使用默认提示词
        return """您是一位专业的技术面分析师。

您的职责是分析持仓股票的技术面状态。

分析要点：
1. 趋势判断 - 当前处于上升/下降/震荡趋势
2. 支撑阻力 - 关键支撑位和阻力位
3. 技术指标 - MACD/KDJ/RSI等指标状态
4. 短期预判 - 未来3-5天可能走势
5. 技术评分 - 1-10分的技术面评分

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词
        
        Args:
            ticker: 股票代码（从position_info中提取）
            analysis_date: 分析日期
            reports: 各类数据（position_info, market_data等）
            historical_context: 历史上下文
            state: 当前状态
            
        Returns:
            用户提示词
        """
        position_info = state.get("position_info", {})
        market_data = state.get("market_data", {})
        
        code = position_info.get("code", ticker)
        name = position_info.get("name", "N/A")
        
        return f"""请分析以下持仓股票的技术面：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2%}

=== 市场数据 ===
{market_data.get('summary', '无K线数据')}

=== 技术指标 ===
{market_data.get('technical_indicators', '无技术指标数据')}

请撰写详细的技术面分析报告，包括：
1. 趋势判断
2. 支撑阻力位
3. 技术指标分析
4. 短期走势预判
5. 技术面评分（1-10分）"""

    def _get_required_reports(self) -> List[str]:
        """
        获取需要的数据列表
        
        Returns:
            数据字段名列表
        """
        return [
            "position_info",
            "market_data"
        ]

