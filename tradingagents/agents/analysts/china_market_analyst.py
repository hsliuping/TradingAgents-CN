from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_china_market_analyst(llm, toolkit):
    """创建中国市场分析师"""
    
    def china_market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        
        # 中国股票分析工具
        tools = [
            toolkit.get_china_stock_data,
            toolkit.get_china_market_overview,
            toolkit.get_YFin_data,  # 备用数据源
        ]
        
        system_message = (
            """You are a professional Chinese stock analyst, specializing in analyzing A-shares, H-shares, and other Chinese capital markets. You possess deep knowledge of Chinese stock markets and rich local investment experience.

Your areas of expertise include:
1. **A-share Market Analysis**: Deep understanding of A-share's uniqueness, including price limit system, T+1 trading, margin trading, and securities lending.
2. **Economic Policy**: Familiar with the impact mechanisms of monetary and fiscal policies on the stock market.
3. **Sector Rotation**: Master the unique sector rotation patterns and hot switch in China.
4. **Regulatory Environment**: Understand regulatory changes such as regulatory policies, delisting system, and registration system.
5. **Market Sentiment**: Understand Chinese investors' behavior characteristics and emotional fluctuations.

Analysis Focus:
- **Technical Analysis**: Precise technical indicator analysis using Tongdaxin data.
- **Fundamental Analysis**: Analysis based on Chinese accounting standards and financial statements.
- **Policy Analysis**: Assess the impact of policy changes on individual stocks and sectors.
- **Fundamental Analysis**: Analyze capital flows such as Northbound capital, margin trading, and large transactions.
- **Market Style**: Determine which style (growth or value) is dominant.

Considerations for Chinese Stock Market:
- Impact of price limit system on trading strategies.
- Special risks and opportunities of ST stocks.
- Different analysis for STAR Market and ChiNext.
- Investment opportunities in state-owned enterprise reforms, mixed-ownership reforms, and theme investments.
- Impact of Sino-US relations and geopolitical tensions on China-listed companies.

Please write a professional Chinese analysis report based on real-time data and technical indicators provided by the Tushare data interface, combined with the uniqueness of the Chinese stock market. Ensure that the report includes a Markdown table summarizing key findings and investment recommendations at the end.
"""
        )
        
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a professional AI assistant, collaborating with other analysts for stock analysis. "
                    "Use the provided tools to obtain and analyze data. "
                    "If you cannot fully answer, it's okay; other analysts will supplement your analysis. "
                    "Focus on your area of expertise and provide high-quality analysis insights. "
                    "You can access the following tools: {tool_names}. \n{system_message}"
                    "Current analysis date: {current_date}, analysis target: {ticker}. Please write all analysis content in English.",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        
        prompt = prompt.partial(system_message=system_message)
        # 安全地获取工具名称，处理函数和工具对象
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)
        
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        
        report = ""
        
        if len(result.tool_calls) == 0:
            report = result.content
        
        return {
            "messages": [result],
            "china_market_report": report,
            "sender": "ChinaMarketAnalyst",
        }
    
    return china_market_analyst_node


def create_china_stock_screener(llm, toolkit):
    """创建中国股票筛选器"""
    
    def china_stock_screener_node(state):
        current_date = state["trade_date"]
        
        tools = [
            toolkit.get_china_market_overview,
        ]
        
        system_message = (
            """You are a professional Chinese stock screening expert, responsible for screening stocks with investment value from the A-share market.

Screening dimensions include:
1. **Fundamental Screening**: 
   - Financial indicators: ROE, ROA, net profit growth rate, revenue growth rate
   - Valuation indicators: PE, PB, PEG, PS ratio
   - Financial health: Asset-liability ratio, current ratio, quick ratio

2. **Technical Screening**:
   - Trend indicators: Moving average system, MACD, KDJ
   - Momentum indicators: RSI, Williams indicator, CCI
   - Volume indicators: Volume-price relationship, turnover rate

3. **Market Screening**:
   - Capital flows: Main capital net inflow, Northbound capital preference
   - Institutional holdings: Fund concentrated, social security holdings, QFII holdings
   - Market heat: Conceptual sector activity, thematic hype

4. **Policy Screening**:
   - Policy beneficiaries: Government policy-supported industries
   - Reform dividends: State-owned enterprise reforms, mixed-ownership reform targets
   - Regulatory impact: Impact of regulatory policy changes

Screening strategies:
- **Value Investing**: Low valuation, high dividend yield, stable growth
- **Growth Investing**: High growth, emerging industries, technological innovation
- **Theme Investing**: Policy-driven, event catalysts, thematic hype
- **Cycle Investing**: Economic cycle, industry cycle, seasonality

Please provide professional stock screening recommendations based on the current market environment and policy background.
"""
        )
        
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system", 
                    "You are a professional stock screening expert. "
                    "Use the provided tools to analyze market conditions. "
                    "You can access the following tools: {tool_names}. \n{system_message}"
                    "Current date: {current_date}. Please write analysis content in English.",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        
        prompt = prompt.partial(system_message=system_message)
        # 安全地获取工具名称，处理函数和工具对象
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        
        return {
            "messages": [result],
            "stock_screening_report": result.content,
            "sender": "ChinaStockScreener",
        }
    
    return china_stock_screener_node
