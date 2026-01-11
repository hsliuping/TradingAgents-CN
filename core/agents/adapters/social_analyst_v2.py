"""
社交媒体分析师 v2.0

基于AnalystAgent基类实现的社交媒体分析师
"""

import logging
from typing import Dict, Any, Optional

from core.agents.analyst import AnalystAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class SocialMediaAnalystV2(AnalystAgent):
    """
    社交媒体分析师 v2.0
    
    功能：
    - 获取社交媒体情绪数据
    - 分析投资者情绪和市场热度
    - 评估社交媒体对股价的影响
    
    工作流程：
    1. 调用统一情绪工具获取社交媒体数据
    2. 使用LLM分析情绪趋势
    3. 生成社交媒体分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("social_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="social_analyst_v2",
        name="社交媒体分析师 v2.0",
        description="分析社交媒体情绪，评估投资者情绪和市场热度",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_sentiment_unified"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="sentiment_report", type="string", description="社交媒体情绪分析报告"),
        ],
        requires_tools=True,
        output_field="sentiment_report",
        report_label="【社交媒体分析 v2】",
    )

    # 分析师类型
    analyst_type = "social"
    
    # 输出字段名
    output_field = "sentiment_report"

    def _build_system_prompt(self, market_type: str, context=None) -> str:
        """
        构建系统提示词

        Args:
            market_type: 市场类型（A股/港股/美股）
            context: AgentContext 对象（用于调试模式）

        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词
        template_variables = {
            "market_name": market_type,
            "ticker": "",
            "company_name": "",
            "current_date": "",
            "currency_name": "人民币",
            "currency_symbol": "¥",
            "tool_names": ""
        }

        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="social_analyst_v2",
            variables=template_variables,
            context=context,
            fallback_prompt=None
        )

        if prompt:
            return prompt
        
        # 降级：使用默认提示词
        return f"""您是一位专业的社交媒体情绪分析师。

您的职责是分析社交媒体上的投资者情绪，评估市场热度和情绪趋势。

分析要点：
1. 总结社交媒体上的主要讨论话题
2. 分析投资者情绪（看涨/看跌/中性）
3. 评估市场热度和关注度
4. 识别潜在的情绪驱动因素
5. 提供基于情绪的投资建议

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        tool_data: Dict[str, Any],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据
            state: 当前状态
            
        Returns:
            用户提示词
        """
        company_name = self._get_company_name(ticker, state)
        
        # 获取情绪数据
        sentiment_data = tool_data.get("get_stock_sentiment_unified", "")
        
        return f"""请基于以下社交媒体数据，对股票 {ticker}（{company_name}）进行详细的情绪分析：

=== 分析日期 ===
{analysis_date}

=== 社交媒体情绪数据 ===
{sentiment_data}

请撰写详细的中文分析报告，包括：
1. 投资者情绪总结
2. 市场热度评估
3. 情绪趋势分析
4. 潜在风险提示
5. 投资建议"""

    def _get_company_name(self, ticker: str, state: Dict[str, Any]) -> str:
        """获取公司名称"""
        # 优先从state获取
        if "company_name" in state:
            return state["company_name"]
        
        # 使用StockUtils获取
        if StockUtils:
            try:
                market_info = StockUtils.get_market_info(ticker)
                if market_info.get('is_china'):
                    from tradingagents.dataflows.interface import get_china_stock_info_unified
                    stock_info = get_china_stock_info_unified(ticker)
                    if "股票名称:" in stock_info:
                        return stock_info.split("股票名称:")[1].split("\n")[0].strip()
            except Exception as e:
                logger.debug(f"获取公司名称失败: {e}")
        
        return f"股票{ticker}"

