import functools
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        # 使用统一的股票类型检测
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(company_name)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        # 根据股票类型确定货币单位
        currency = market_info['currency_name']
        currency_symbol = market_info['currency_symbol']

        logger.debug(f"💰 [DEBUG] ===== 交易员节点开始 =====")
        logger.debug(f"💰 [DEBUG] 交易员检测股票类型: {company_name} -> {market_info['market_name']}, 货币: {currency}")
        logger.debug(f"💰 [DEBUG] 货币符号: {currency_symbol}")
        logger.debug(f"💰 [DEBUG] 市场详情: 中国A股={is_china}, 港股={is_hk}, 美股={is_us}")
        logger.debug(f"💰 [DEBUG] 基本面报告长度: {len(fundamentals_report)}")
        logger.debug(f"💰 [DEBUG] 基本面报告前200字符: {fundamentals_report[:200]}...")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        # 检查memory是否可用
        if memory is not None:
            logger.warning(f"⚠️ [DEBUG] memory可用，获取历史记忆")
            past_memories = memory.get_memories(curr_situation, n_matches=2)
            past_memory_str = ""
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            logger.warning(f"⚠️ [DEBUG] memory为None，跳过历史记忆检索")
            past_memories = []
            past_memory_str = "暂无历史记忆数据可参考。"

        context = {
            "role": "user",
            "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\nProposed Investment Plan: {investment_plan}\n\nLeverage these insights to make an informed and strategic decision.",
        }

        messages = [
            {
                "role": "system",
                "content": f"""You are a professional trader responsible for analyzing market data and making investment decisions. Based on your analysis, please provide specific buy, sell, or hold recommendations.

⚠️ Important Reminder: The current analysis is for stock code {company_name}, please use the correct currency unit: {currency} ({currency_symbol}).

🔴 Strict Requirements:
- The company name for stock code {company_name} must be strictly based on the real data in the fundamentals report
- Absolutely prohibited to use incorrect company names or confuse different stocks
- All analysis must be based on the provided real data, no assumptions or fabrication allowed
- **Must provide specific target prices, not null or empty**

Please include the following key information in your analysis:
1. **Investment Advice**: Clear buy/hold/sell decision
2. **Target Price**: Reasonable target price based on analysis ({currency}) - 🚨 Mandatory to provide specific numerical value
   - Buy recommendation: Provide target price and expected increase
   - Hold recommendation: Provide reasonable price range (e.g., {currency_symbol}XX-XX)
   - Sell recommendation: Provide stop-loss price and target sell price
3. **Confidence**: Confidence level of the decision (0-1)
4. **Risk Score**: Investment risk level (0-1, 0 for low risk, 1 for high risk)
5. **Detailed Reasoning**: Specific reasons supporting the decision

🎯 Target Price Calculation Guidance:
- Based on valuation data in fundamental analysis (P/E, P/B, DCF, etc.)
- Refer to support and resistance levels in technical analysis
- Consider industry average valuation levels
- Combine market sentiment and news impact
- Even if market sentiment is overly bullish, provide a target price based on reasonable valuation

Special Note:
- If it is a Chinese A-share (6-digit code), please use Renminbi (¥) as the price unit
- If it is a US or Hong Kong stock, please use US Dollar ($) as the price unit
- Target price must be consistent with the currency unit of the current stock price
- Must use the correct company name provided in the fundamentals report
- **Absolutely not allowed to say "cannot determine target price" or "need more information"**

Please write all analysis in English.

Please do not forget to utilize past decision experience to avoid repeating mistakes. Below are trading reflections and lessons learned from similar situations: {past_memory_str}""",
            },
            context,
        ]

        logger.debug(f"💰 [DEBUG] 准备调用LLM，系统提示包含货币: {currency}")
        logger.debug(f"💰 [DEBUG] 系统提示中的关键部分: 目标价格({currency})")

        result = llm.invoke(messages)

        logger.debug(f"💰 [DEBUG] LLM调用完成")
        logger.debug(f"💰 [DEBUG] 交易员回复长度: {len(result.content)}")
        logger.debug(f"💰 [DEBUG] 交易员回复前500字符: {result.content[:500]}...")
        logger.debug(f"💰 [DEBUG] ===== 交易员节点结束 =====")

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
