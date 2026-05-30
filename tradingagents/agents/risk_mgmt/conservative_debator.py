from langchain_core.messages import AIMessage
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_safe_debator(llm):
    def safe_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        safe_history = risk_debate_state.get("safe_history", "")
        stage = "independent_initial_review" if risk_debate_state.get("count", 0) < 3 else "cross_examination"

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        # 📊 记录输入数据长度
        logger.info(f"📊 [Safe Analyst] 输入数据长度统计:")
        logger.info(f"  - market_report: {len(market_research_report):,} 字符")
        logger.info(f"  - sentiment_report: {len(sentiment_report):,} 字符")
        logger.info(f"  - news_report: {len(news_report):,} 字符")
        logger.info(f"  - fundamentals_report: {len(fundamentals_report):,} 字符")
        logger.info(f"  - trader_decision: {len(trader_decision):,} 字符")
        logger.info(f"  - history: {len(history):,} 字符")
        total_length = (len(market_research_report) + len(sentiment_report) +
                       len(news_report) + len(fundamentals_report) +
                       len(trader_decision) + len(history) +
                       len(current_risky_response) + len(current_neutral_response))
        logger.info(f"  - 总Prompt长度: {total_length:,} 字符 (~{total_length//4:,} tokens)")

        if stage == "independent_initial_review":
            prompt = f"""作为安全/保守风险分析师，您是风险管理团队中的“本金保护者”。您的职责不是简单反对买入，而是独立识别系统性风险、行业风险、流动性风险和个股下行风险，判断交易员计划是否具备足够安全边际。

当前是【独立初评阶段】。请不要回应激进或中性分析师，也不要引用尚未出现的观点。只基于交易员计划和四份报告形成您的独立风险评估。

请优先检查：
1. 大盘环境：指数趋势、市场风险偏好、成交额、系统性回撤压力是否支持当前交易。
2. 行业周期：行业景气度、政策环境、同业估值和行业资金流是否构成阻力。
3. 个股基本面：盈利质量、现金流、负债、估值安全边际、同业对比和历史分位。
4. 技术下行风险：关键支撑位、破位信号、放量下跌、相对大盘或行业走弱。
5. 尾部风险：政策、监管、诉讼、财务异常、流动性枯竭或重大负面新闻。

请区分“致命风险”和“可承受波动”，并说明什么条件满足后，您会从保守转为中性或支持小仓位参与。

交易员计划：
{trader_decision}

市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}

请按以下结构输出，使用中文：
【阶段】独立初评
【核心结论】
【大盘/行业风险】
【个股下行风险】
【致命风险与可承受波动】
【转为中性或参与的条件】
【仓位/止损建议】
【置信度】"""
        else:
            prompt = f"""作为安全/保守风险分析师，您现在进入【交叉质询阶段】。您的任务是针对激进和中性分析师的观点，检查他们是否低估了大盘、行业、财务、估值、流动性或尾部风险，并给出更稳健的替代方案。

请重点回应：
1. 激进分析师提出的机会和催化剂，哪些有足够证据，哪些只是乐观假设。
2. 中性分析师的折中方案是否仍然暴露在不可接受的系统性或个股风险中。
3. 如果反对买入，必须给出清晰的回避理由、重新观察条件和止损/减仓触发。
4. 如果风险已有补偿，也可以允许小仓位参与，但必须给出严格边界。

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

中性分析师最新观点：
{current_neutral_response}

请按以下结构输出，使用中文：
【阶段】交叉质询
【我认可的机会点】
【我反驳的激进/中性观点】
【最主要的本金损失风险】
【保守替代方案】
【转为可参与的触发条件】
【置信度】"""

        logger.info(f"⏱️ [Safe Analyst] 开始调用LLM...")
        llm_start_time = time.time()

        response = llm.invoke(prompt)

        llm_elapsed = time.time() - llm_start_time
        logger.info(f"⏱️ [Safe Analyst] LLM调用完成，耗时: {llm_elapsed:.2f}秒")

        argument = f"Safe Analyst: {response.content}"

        new_count = risk_debate_state["count"] + 1
        logger.info(f"🛡️ [保守风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": safe_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Safe",
            "stage": stage,
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return safe_node
