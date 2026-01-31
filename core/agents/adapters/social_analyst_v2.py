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

    def _build_system_prompt(self, market_type: str = None, context=None, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）

        Args:
            market_type: 市场类型（A股/港股/美股）（保留以兼容基类）
            context: AgentContext 对象（用于调试模式）
            state: 工作流状态（用于提取模板变量）

        Returns:
            系统提示词
        """
        logger.info("🔍 [SocialAnalystV2] 开始构建系统提示词")
        
        if state is None:
            state = {}
        
        # 从 state 中提取必要的变量（如果系统提示词模板需要）
        # 注意：虽然系统提示词通常不需要变量，但某些模板可能需要 ticker、current_date 等
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        template_variables = {}
        
        # 如果 state 中有 ticker 和 analysis_date，提取它们（系统提示词模板可能需要）
        if "ticker" in state:
            template_variables["ticker"] = state["ticker"]
        if "analysis_date" in state or "trade_date" in state:
            analysis_date = state.get("analysis_date") or state.get("trade_date")
            if analysis_date:
                # 确保日期格式正确
                if isinstance(analysis_date, str) and len(analysis_date) > 10:
                    analysis_date = analysis_date.split()[0]
                template_variables["current_date"] = analysis_date
                template_variables["analysis_date"] = analysis_date
        
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="social_analyst_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=context or state.get("context"),  # 优先使用传入的 context，否则从 state 获取
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")

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
5. 提供基于情绪的分析观点

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        tool_data: Dict[str, Any],  # 保留参数以兼容基类，但工具数据会通过 ToolMessage 传递
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（参考 research_manager_v2 和 fundamentals_analyst_v2 的实现）
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据（保留以兼容基类，但工具数据会通过 ToolMessage 传递）
            state: 工作流状态（用于提取模板变量）
            
        Returns:
            用户提示词
        """
        logger.info("🔍 [SocialAnalystV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        
        if state is None:
            state = {}
        
        # 获取公司名称和市场信息
        company_name = self._get_company_name(ticker, state)
        market_name = "中国A股"
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                market_name = market_info.get('market_name', "中国A股")
                currency_name = market_info.get('currency_name', "人民币")
                currency_symbol = market_info.get('currency_symbol', "¥")
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        # 🔑 关键：确保日期格式正确（YYYY-MM-DD），而不是 datetime 对象
        if isinstance(analysis_date, str):
            # 如果已经是字符串，确保格式正确
            if len(analysis_date) > 10:
                # 如果是 datetime 字符串（如 "2026-01-14 00:00:00"），只取日期部分
                analysis_date_str = analysis_date.split()[0]
            else:
                analysis_date_str = analysis_date
        else:
            # 如果是 datetime 对象，转换为字符串
            from datetime import datetime
            if isinstance(analysis_date, datetime):
                analysis_date_str = analysis_date.strftime("%Y-%m-%d")
            else:
                analysis_date_str = str(analysis_date)
        
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "market_name": market_name,
            "analysis_date": analysis_date_str,  # 🔑 确保是字符串格式 YYYY-MM-DD
            "current_date": analysis_date_str,  # 🔑 确保是字符串格式 YYYY-MM-DD
            "start_date": "",  # 可以计算1年前的日期
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
        }
        
        # 使用基类的通用方法获取用户提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        # 🔑 注意：工具返回的数据会通过 ToolMessage 传递，不需要在 user_prompt 中检查
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="social_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取社交媒体分析师 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        # 降级：使用默认提示词（不再检查 tool_data，因为工具数据会通过 ToolMessage 传递）
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        # 🔑 关键：在默认提示词中明确告诉LLM要使用什么日期调用工具
        return f"""请对股票 {ticker}（{company_name}）进行详细的社交媒体情绪分析：

**分析日期**：{analysis_date_str}

**重要提示**：调用工具 get_stock_sentiment_unified 时，必须使用 curr_date 参数，值为：{analysis_date_str}

请调用工具获取社交媒体数据，然后生成详细的中文分析报告。"""

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

