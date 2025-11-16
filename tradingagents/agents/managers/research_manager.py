import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入模板客户端
from tradingagents.utils.template_client import get_agent_prompt


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        # 安全检查：确保memory不为None
        if memory is not None:
            past_memories = memory.get_memories(curr_situation, n_matches=2)
        else:
            logger.warning(f"⚠️ [DEBUG] memory为None，跳过历史记忆检索")
            past_memories = []

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        # 🆕 使用模板系统获取提示词
        try:
            # 准备模板变量
            template_variables = {
                "ticker": state.get("company_of_interest", ""),
                "company_name": state.get("company_of_interest", ""),
                "market_name": "",
                "current_date": state.get("trade_date", ""),
                "start_date": state.get("trade_date", ""),
                "currency_name": "",
                "currency_symbol": "",
                "tool_names": ""
            }

            # 从模板系统获取提示词
            system_prompt = get_agent_prompt(
                agent_type="managers",
                agent_name="research_manager",
                variables=template_variables,
                preference_id="neutral",
                fallback_prompt=None
            )

            logger.info(f"✅ [研究经理] 成功从模板系统获取提示词 (长度: {len(system_prompt)})")

        except Exception as e:
            logger.error(f"❌ [研究经理] 从模板系统获取提示词失败: {e}")
            # 降级：使用硬编码提示词
            system_prompt = """作为投资组合经理和辩论主持人，您的职责是批判性地评估这轮辩论并做出明确决策。

简洁地总结双方的关键观点，重点关注最有说服力的证据或推理。

您的建议——买入、卖出或持有——必须明确且可操作。

为交易员制定详细的投资计划，包括建议、理由和战略行动。

提供具体的目标价格分析和时间范围。

请用中文撰写所有分析内容。"""
            logger.warning(f"⚠️ [研究经理] 使用降级提示词 (长度: {len(system_prompt)})")

        # 构建完整提示词
        prompt = f"""{system_prompt}

过去的反思和经验教训：
{past_memory_str}

综合分析报告：
市场研究：{market_research_report}
情绪分析：{sentiment_report}
新闻分析：{news_report}
基本面分析：{fundamentals_report}

辩论历史：
{history}

请基于以上信息做出明确的投资决策。"""

        # 📊 统计 prompt 大小
        prompt_length = len(prompt)
        estimated_tokens = int(prompt_length / 1.8)

        logger.info(f"📊 [Research Manager] Prompt 统计:")
        logger.info(f"   - 辩论历史长度: {len(history)} 字符")
        logger.info(f"   - 总 Prompt 长度: {prompt_length} 字符")
        logger.info(f"   - 估算输入 Token: ~{estimated_tokens} tokens")

        # ⏱️ 记录开始时间
        start_time = time.time()

        response = llm.invoke(prompt)

        # ⏱️ 记录结束时间
        elapsed_time = time.time() - start_time

        # 📊 统计响应信息
        response_length = len(response.content) if response and hasattr(response, 'content') else 0
        estimated_output_tokens = int(response_length / 1.8)

        logger.info(f"⏱️ [Research Manager] LLM调用耗时: {elapsed_time:.2f}秒")
        logger.info(f"📊 [Research Manager] 响应统计: {response_length} 字符, 估算~{estimated_output_tokens} tokens")

        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
