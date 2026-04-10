import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 导入模板客户端
from tradingagents.utils.template_client import get_agent_prompt
from tradingagents.agents.utils.compliance_prompting import apply_compliance_guardrails, build_research_only_closing


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state.get("company_of_interest", "")

        # 使用 .get() 安全访问辩论状态
        risk_debate_state = state.get("risk_debate_state", {})
        history = risk_debate_state.get("history", "")
        # 使用 .get() 安全访问，支持用户只选择部分分析师的情况
        market_research_report = state.get("market_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")
        sentiment_report = state.get("sentiment_report", "")
        trader_plan = state.get("investment_plan", "")

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

            from tradingagents.utils.template_client import get_template_client
            ctx = state.get("agent_context") or {}
            tpl_info = get_template_client().get_effective_template(
                agent_type="managers",
                agent_name="risk_manager",
                user_id=ctx.get("user_id"),
                preference_id=ctx.get("preference_id") or "neutral",
                context=None
            )
            if tpl_info:
                logger.info(f"📚 [模板选择] source={tpl_info.get('source')} id={tpl_info.get('template_id')} version={tpl_info.get('version')} agent=managers/risk_manager")

            # 从模板系统获取提示词
            system_prompt = get_agent_prompt(
                agent_type="managers",
                agent_name="risk_manager",
                variables=template_variables,
                preference_id="neutral",
                fallback_prompt=None
            )

            system_prompt = apply_compliance_guardrails(system_prompt, "risk_manager")
            logger.info(f"✅ [风险经理] 成功从模板系统获取提示词 (长度: {len(system_prompt)})")

        except Exception as e:
            logger.error(f"❌ [风险经理] 从模板系统获取提示词失败: {e}")
            # 降级：使用硬编码提示词
            system_prompt = """作为风险管理委员会主席和辩论主持人，您的目标是评估三位风险分析师的辩论，并形成风险治理视角的研究意见。

总结关键论点，提供详细推理，并根据分析师的见解调整交易员计划。

从过去的错误中学习，确保每个决策都能带来更好的结果。

请用中文撰写所有分析内容。"""
            system_prompt = apply_compliance_guardrails(system_prompt, "risk_manager")
            logger.warning(f"⚠️ [风险经理] 使用降级提示词 (长度: {len(system_prompt)})")

        # 构建完整提示词
        prompt = f"""{system_prompt}

交易员的原始计划：
{trader_plan}

过去的反思和经验教训：
{past_memory_str}

分析师辩论历史：
{history}

{build_research_only_closing(["请基于以上信息输出风险汇总、主要争议、约束条件、信息缺口和后续观察点。"])}"""

        # 📊 统计 prompt 大小
        prompt_length = len(prompt)
        # 粗略估算 token 数量（中文约 1.5-2 字符/token，英文约 4 字符/token）
        estimated_tokens = int(prompt_length / 1.8)  # 保守估计

        logger.info(f"📊 [Risk Manager] Prompt 统计:")
        logger.info(f"   - 辩论历史长度: {len(history)} 字符")
        logger.info(f"   - 交易员计划长度: {len(trader_plan)} 字符")
        logger.info(f"   - 历史记忆长度: {len(past_memory_str)} 字符")
        logger.info(f"   - 总 Prompt 长度: {prompt_length} 字符")
        logger.info(f"   - 估算输入 Token: ~{estimated_tokens} tokens")

        # 增强的LLM调用，包含错误处理和重试机制
        max_retries = 3
        retry_count = 0
        response_content = ""

        while retry_count < max_retries:
            try:
                logger.info(f"🔄 [Risk Manager] 调用LLM生成交易决策 (尝试 {retry_count + 1}/{max_retries})")

                # ⏱️ 记录开始时间
                start_time = time.time()

                response = llm.invoke(prompt)

                # ⏱️ 记录结束时间
                elapsed_time = time.time() - start_time
                
                if response and hasattr(response, 'content') and response.content:
                    response_content = response.content.strip()

                    # 📊 统计响应信息
                    response_length = len(response_content)
                    estimated_output_tokens = int(response_length / 1.8)

                    # 尝试获取实际的 token 使用情况（如果 LLM 返回了）
                    usage_info = ""
                    if hasattr(response, 'response_metadata') and response.response_metadata:
                        metadata = response.response_metadata
                        if 'token_usage' in metadata:
                            token_usage = metadata['token_usage']
                            usage_info = f", 实际Token: 输入={token_usage.get('prompt_tokens', 'N/A')} 输出={token_usage.get('completion_tokens', 'N/A')} 总计={token_usage.get('total_tokens', 'N/A')}"

                    logger.info(f"⏱️ [Risk Manager] LLM调用耗时: {elapsed_time:.2f}秒")
                    logger.info(f"📊 [Risk Manager] 响应统计: {response_length} 字符, 估算~{estimated_output_tokens} tokens{usage_info}")

                    if len(response_content) > 10:  # 确保响应有实质内容
                        logger.info(f"✅ [Risk Manager] LLM调用成功")
                        break
                    else:
                        logger.warning(f"⚠️ [Risk Manager] LLM响应内容过短: {len(response_content)} 字符")
                        response_content = ""
                else:
                    logger.warning(f"⚠️ [Risk Manager] LLM响应为空或无效")
                    response_content = ""

            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ [Risk Manager] LLM调用失败 (尝试 {retry_count + 1}): {str(e)}")
                logger.error(f"⏱️ [Risk Manager] 失败前耗时: {elapsed_time:.2f}秒")
                response_content = ""
            
            retry_count += 1
            if retry_count < max_retries and not response_content:
                logger.info(f"🔄 [Risk Manager] 等待2秒后重试...")
                time.sleep(2)
        
        # 如果所有重试都失败，生成默认决策
        if not response_content:
            logger.error(f"❌ [Risk Manager] 所有LLM调用尝试失败，使用默认决策")
            response_content = f"""**风险汇总**

由于技术原因无法生成详细分析，当前仅保留对 {company_name} 的风险观察。

**主要争议**
1. 市场信息不足，暂时无法确认关键分歧的方向。
2. 现有公开信息不足以支持更细化的研究结论。

**后续观察点**
- 持续跟踪市场动态和公司基本面变化
- 补充财务与经营数据后再进行复核
- 关注重大公告、行业变化与宏观环境扰动

注意：此为系统默认研究观察，不构成任何交易建议。"""

        new_risk_debate_state = {
            "judge_decision": response_content,
            "history": risk_debate_state.get("history", ""),
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Judge",
            "current_risky_response": risk_debate_state.get("current_risky_response", ""),
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
            "count": risk_debate_state.get("count", 0),
        }

        logger.info(f"📋 [Risk Manager] 最终决策生成完成，内容长度: {len(response_content)} 字符")

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response_content,  # ✅ 恢复：输出 final_trade_decision
        }

    return risk_manager_node
