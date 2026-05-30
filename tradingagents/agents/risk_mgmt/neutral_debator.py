import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")
        stage = "independent_initial_review" if risk_debate_state.get("count", 0) < 3 else "cross_examination"

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_safe_response = risk_debate_state.get("current_safe_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        # 📊 记录所有输入数据的长度，用于性能分析
        logger.info(f"📊 [Neutral Analyst] 输入数据长度统计:")
        logger.info(f"  - market_report: {len(market_research_report):,} 字符 (~{len(market_research_report)//4:,} tokens)")
        logger.info(f"  - sentiment_report: {len(sentiment_report):,} 字符 (~{len(sentiment_report)//4:,} tokens)")
        logger.info(f"  - news_report: {len(news_report):,} 字符 (~{len(news_report)//4:,} tokens)")
        logger.info(f"  - fundamentals_report: {len(fundamentals_report):,} 字符 (~{len(fundamentals_report)//4:,} tokens)")
        logger.info(f"  - trader_decision: {len(trader_decision):,} 字符 (~{len(trader_decision)//4:,} tokens)")
        logger.info(f"  - history: {len(history):,} 字符 (~{len(history)//4:,} tokens)")
        logger.info(f"  - current_risky_response: {len(current_risky_response):,} 字符 (~{len(current_risky_response)//4:,} tokens)")
        logger.info(f"  - current_safe_response: {len(current_safe_response):,} 字符 (~{len(current_safe_response)//4:,} tokens)")

        # 计算总prompt长度
        total_prompt_length = (len(market_research_report) + len(sentiment_report) +
                              len(news_report) + len(fundamentals_report) +
                              len(trader_decision) + len(history) +
                              len(current_risky_response) + len(current_safe_response))
        logger.info(f"  - 🚨 总Prompt长度: {total_prompt_length:,} 字符 (~{total_prompt_length//4:,} tokens)")

        if stage == "independent_initial_review":
            prompt = f"""作为中性风险分析师，您是风险管理团队中的“风险收益校准者”。您的职责不是简单折中，而是独立判断这笔交易的上涨空间、下跌空间、证据质量和执行条件是否匹配。

当前是【独立初评阶段】。请不要回应激进或保守分析师，也不要引用尚未出现的观点。只基于交易员计划和四份报告形成您的独立校准。

请优先检查：
1. 风险收益比：目标价、止损位、潜在涨幅和潜在回撤是否对称。
2. 证据质量：哪些结论来自财报、估值、同业对比和公告，哪些只是技术面、情绪或推测。
3. 信号一致性：基本面、技术面、新闻面、情绪面是否互相印证，是否存在冲突。
4. 执行可行性：更适合买入、持有、等待、小仓位试探，还是卖出/回避。
5. 结论反转条件：哪些关键变量变化会让建议升级或降级。

请给出分层策略，而不是只有单一观点。

交易员计划：
{trader_decision}

市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}

请按以下结构输出，使用中文：
【阶段】独立初评
【核心结论】
【风险收益比校准】
【证据质量评估】
【信号冲突与取舍】
【分层策略：买入/试探/等待/卖出条件】
【置信度】"""
        else:
            prompt = f"""作为中性风险分析师，您现在进入【交叉质询阶段】。您的任务是校准激进和保守分析师的观点：既要指出激进观点是否低估风险，也要指出保守观点是否高估风险，最终形成可执行的中间方案或明确否决。

请重点回应：
1. 激进分析师的机会判断是否有足够证据支持，赔率是否真实。
2. 保守分析师的大盘、行业和本金风险是否已经被价格充分反映。
3. 双方是否重复计算同一风险，或忽略了关键冲突。
4. 当前最合理的执行方案：买入、持有、等待、小仓位试探、分批、减仓或卖出。
5. 必须给出目标价区间、止损/减仓条件、仓位倾向和结论反转条件。

交易员计划：
{trader_decision}

市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}

当前风险讨论历史：
{history}

激进分析师最新观点：
{current_risky_response}

保守分析师最新观点：
{current_safe_response}

请按以下结构输出，使用中文：
【阶段】交叉质询
【激进观点校准】
【保守观点校准】
【最合理风险收益判断】
【执行方案】
【结论反转条件】
【置信度】"""

        logger.info(f"⏱️ [Neutral Analyst] 开始调用LLM...")
        llm_start_time = time.time()

        response = llm.invoke(prompt)

        llm_elapsed = time.time() - llm_start_time
        logger.info(f"⏱️ [Neutral Analyst] LLM调用完成，耗时: {llm_elapsed:.2f}秒")
        logger.info(f"📝 [Neutral Analyst] 响应长度: {len(response.content):,} 字符")

        argument = f"Neutral Analyst: {response.content}"

        new_count = risk_debate_state["count"] + 1
        logger.info(f"⚖️ [中性风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "stage": stage,
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": argument,
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
