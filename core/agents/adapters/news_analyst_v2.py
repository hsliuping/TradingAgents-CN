"""
新闻分析师 v2.0

基于AnalystAgent基类实现的新闻分析师
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
class NewsAnalystV2(AnalystAgent):
    """
    新闻分析师 v2.0
    
    功能：
    - 获取股票相关新闻
    - 分析新闻对股价的影响
    - 评估市场情绪
    
    工作流程：
    1. 调用统一新闻工具获取新闻数据
    2. 使用LLM分析新闻内容
    3. 生成新闻分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("news_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="news_analyst_v2",
        name="新闻分析师 v2.0",
        description="分析股票相关新闻，评估新闻对股价的影响和市场情绪",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_news_unified"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="news_report", type="string", description="新闻分析报告"),
        ],
        requires_tools=True,
        output_field="news_report",
        report_label="【新闻分析 v2】",
    )

    # 分析师类型
    analyst_type = "news"
    
    # 输出字段名
    output_field = "news_report"

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
            agent_name="news_analyst_v2",
            variables=template_variables,
            context=context,
            fallback_prompt=None
        )

        if prompt:
            return prompt
        
        # 降级：使用默认提示词
        return f"""您是一位专业的财经新闻分析师。

您的职责是分析股票相关新闻，评估新闻对股价的影响和市场情绪。

分析要点：
1. 总结最新的新闻事件和市场动态
2. 分析新闻对股票的潜在影响
3. 评估市场情绪和投资者反应
4. 提供基于新闻的投资建议

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
        
        # 获取新闻数据
        news_data = tool_data.get("get_stock_news_unified", "")
        
        return f"""请基于以下新闻数据，对股票 {ticker}（{company_name}）进行详细的新闻分析：

=== 分析日期 ===
{analysis_date}

=== 最新新闻数据 ===
{news_data}

请撰写详细的中文分析报告，包括：
1. 新闻事件总结
2. 对股票的影响分析
3. 市场情绪评估
4. 投资建议"""

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

