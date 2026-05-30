import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_risky_debator(llm):
    def risky_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        risky_history = risk_debate_state.get("risky_history", "")
        stage = "independent_initial_review" if risk_debate_state.get("count", 0) < 3 else "cross_examination"

        current_safe_response = risk_debate_state.get("current_safe_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        # 📊 记录输入数据长度
        logger.info(f"📊 [Risky Analyst] 输入数据长度统计:")
        logger.info(f"  - market_report: {len(market_research_report):,} 字符")
        logger.info(f"  - sentiment_report: {len(sentiment_report):,} 字符")
        logger.info(f"  - news_report: {len(news_report):,} 字符")
        logger.info(f"  - fundamentals_report: {len(fundamentals_report):,} 字符")
        logger.info(f"  - trader_decision: {len(trader_decision):,} 字符")
        logger.info(f"  - history: {len(history):,} 字符")
        total_length = (len(market_research_report) + len(sentiment_report) +
                       len(news_report) + len(fundamentals_report) +
                       len(trader_decision) + len(history) +
                       len(current_safe_response) + len(current_neutral_response))
        logger.info(f"  - 总Prompt长度: {total_length:,} 字符 (~{total_length//4:,} tokens)")

        if stage == "independent_initial_review":
            prompt = f"""作为激进风险分析师，您是风险管理团队中的“机会捕手”。您的职责不是盲目看多，而是独立识别市场可能低估的上行机会、催化剂和预期差，并判断这些机会是否值得承担风险。

当前是【独立初评阶段】。请不要回应保守或中性分析师，也不要引用尚未出现的观点。只基于交易员计划和四份报告形成您的独立机会评估。

请优先检查：
1. 上涨催化剂：业绩反转、政策利好、行业景气度改善、资金关注、技术突破或事件驱动。
2. 预期差：利空是否已被充分定价，利好是否尚未被市场反映。
3. 赔率空间：当前价格到合理目标价的潜在涨幅是否足以补偿风险。
4. 动量与相对强度：个股是否强于大盘或行业，是否有放量、突破、趋势延续等信号。
5. 行业风口/主题动量：公司所在细分行业或概念主题是否处于市场风口（如CPO、算力、有色金属、商业航天、机器人、低空经济、AI应用等），是否有政策、产业趋势、订单、涨价或资金共识支撑。
6. 可承受风险：哪些风险可以通过仓位、止损或分批参与来管理，而不是完全回避。

请必须说明乐观假设失败时的代价，包括止损条件、最大主要回撤来源和需要放弃交易的触发条件。如果判断行业处于风口，还必须说明风口持续性和拥挤交易/退潮风险；如果没有可靠风口证据，必须明确写“未发现可靠风口证据”。

交易员计划：
{trader_decision}

市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}

请按以下结构输出，使用中文：
【阶段】独立初评
【核心结论】
【最强机会依据】
【关键催化剂与预期差】
【行业风口与主题动量】
【可承受风险与止损条件】
【仓位/目标价倾向】
【置信度】"""
        else:
            prompt = f"""作为激进风险分析师，您现在进入【交叉质询阶段】。您的任务是针对保守和中性分析师的观点，指出他们可能低估机会、过度惩罚风险或忽略预期差的地方，但仍必须承认真实存在的风险边界。

请重点回应：
1. 保守分析师提出的大盘、行业、财务、估值或流动性风险中，哪些是致命风险，哪些只是可承受波动。
2. 中性分析师对风险收益比和证据质量的校准是否过于保守。
3. 行业风口或主题动量是否足以提高交易赔率；如果对方忽略了风口，请指出其机会成本；如果风口证据不足，也必须主动降权。
4. 如果仍支持进攻，必须给出更清晰的催化剂、目标价、止损位和仓位上限。
5. 如果发现机会不足以覆盖风险，也可以下调激进程度，但要解释原因。

交易员计划：
{trader_decision}

市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}

当前风险讨论历史：
{history}

保守分析师最新观点：
{current_safe_response}

中性分析师最新观点：
{current_neutral_response}

请按以下结构输出，使用中文：
【阶段】交叉质询
【我接受的风险点】
【我反驳的保守/中性观点】
【仍然值得进攻的理由】
【行业风口是否改变赔率】
【修正后的仓位、目标价和止损】
【置信度】"""

        logger.info(f"⏱️ [Risky Analyst] 开始调用LLM...")
        import time
        llm_start_time = time.time()

        response = llm.invoke(prompt)

        llm_elapsed = time.time() - llm_start_time
        logger.info(f"⏱️ [Risky Analyst] LLM调用完成，耗时: {llm_elapsed:.2f}秒")

        argument = f"Risky Analyst: {response.content}"

        new_count = risk_debate_state["count"] + 1
        logger.info(f"🔥 [激进风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risky_history + "\n" + argument,
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Risky",
            "stage": stage,
            "current_risky_response": argument,
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return risky_node
